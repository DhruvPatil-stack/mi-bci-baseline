# S1 decisions (filter cache + BandPass + CSP rank), claude/speed-stroke, 2026-11-20

## D1. Cache key: one key per trial row, not per array
- Namespace = sha256 of repr(("bandpass", float(low), float(high), float(fs), int(order), input dtype, row shape,
  scipy version, cache format "1")), first 16 hex characters. A float 8 and a float 8.0 give the same filter, so
  both are cast before the key is made. Dtype and row shape stop byte-identical rows of another dtype or shape from
  colliding. The scipy version stops a disk cache from an older venv being reused.
- Row key = sha256 of the bytes of `X[i]` (C-contiguous), first 32 hex characters (128 bits). This is a hash of the
  CONTENT, never id(). An in-place change to a cached array changes the key.
- Why per row: sosfiltfilt filters each 1D series along the last axis on its own, so the output row depends only on
  the input row. Cross-validation gives each fit a NEW subset X[idx]. A per-row key hits for every row filtered
  before, in any order and with repeated rows (G9 needs this).
- Per-fit lookup cost: 850 rows hash in 0.03 s (4 threads; hashlib releases the GIL; the digests do not depend on the
  thread count) against 0.062 s serial. Measured on (850, 64, 480) float32 on this PC.
- No id() memo and no "same object as last call" shortcut. The in-place mutation test in G8 forbids both. Each call
  hashes again.

## D2. Storage layout
- Memory: `{namespace: {row key: float64 row}}` in the process. The stored rows are owned copies. A call builds a
  new output array and copies the rows into it, so a caller that mutates its output does not change the cache.
- Disk: `<$BCI_FILTER_CACHE_DIR or <repo>/.cache/filtered>/<ns16>/<row32>.npy`. Each file is one float64 array of
  shape X.shape[1:] (last axis = time). Nothing else is stored: no index, no manifest, no lock file, nothing learned,
  nothing that depends on labels.
- Lookup order: memory, then disk (one os.scandir of the namespace folder per call, then np.load of the hits), then
  one sosfiltfilt over all remaining misses as a batch.
- Path length: the longest cache path measured in the probe is 145 characters, under the Windows 260 limit. The
  G8 pytest temp dir adds about 60 more.

## D3. Atomic writes (several processes)
- A temp file goes in the same folder, named `<row32>.<pid>.<8 hex>.tmp`. It is written through a file handle, so
  np.save adds no `.npy` suffix. Then `os.replace` moves it to the final name.
- A row that already has a file is not written again.
- On Windows `os.replace` fails with PermissionError when another process holds the target open (np.load). That
  error is swallowed, because the other file holds the same row. A failed write never raises. The temp file is
  removed in `finally`.
- A file that cannot be loaded (OSError, ValueError, EOFError, wrong shape or dtype) counts as a miss and the row is
  filtered again. Torn files cannot occur, because only complete files are renamed into place.
- `$BCI_FILTER_CACHE == "0"` gives the plain sosfiltfilt path, with no memory and no disk use. All env vars are read
  at call time.

## D4. Memory policy
- Sizes: one band on 900 x 64 x 480 float64 is 221 MB (measured: 210.9 MiB in memory after one csp_lda fit on
  900 trials). In run_all each worker runs one model: csp_lda uses 1 band (0.22 GB) and fbcsp_lr 5 bands
  (1.1 GB). ts_lr and eegnet_lite do not use BandPass. With 4 workers the total is about 1.3 GB.
- Cap: `$BCI_FILTER_CACHE_MEM_MB`, default 4096 per process. This is an engineering limit, not a model setting:
  rows past the cap are served from disk with the same values, and G8 shows cache on and off agree to 1e-9. That
  is why the cap is not in config.yaml (frozen) and is not a hyperparameter.
- Policy: rows are admitted until the cap, with no eviction. FBCSP cycles through its 5 bands, and an LRU cap
  smaller than that working set would miss on every access. Admit-until-full keeps the first bands in memory and
  never thrashes. clear_memory() empties the cache (the tests use it).
- Stroke: one row is 29 x 1500 x 8 = 348 KB. 2000 trials would be 696 MB per band and 3.5 GB for 5 fbcsp bands,
  which is under the 4 GB default.

## D5. CSP rank (Head-chef probe)
- `_csp(n_components, reg, rank)` passes config `csp_rank` ("full") as mne `CSP(rank=...)` in both csp_lda and
  fbcsp_lr. That is the frozen config value; nothing was searched.

## D6. Sampling rate in factories
- Both factories read `fs = contracts.dataset_spec()["sfreq"]` at build time. This is the natural place, and S3
  would add it anyway. PhysioNet gives 160, the same as v0.2. The BandPass default `fs=SFREQ` is unchanged.

## Measurements (this PC, 2 BLAS threads, another builder's tests running at the same time)
- G9-style fit: 900 trials, warm cache, new 850-row subset per fit. Probe `.cache/s1_interleave.py`, 6 fits
  interleaved with CSP+LDA on precomputed filter output.
  - Cached pipeline median: 1.249 s.
  - Precomputed reference median: 1.218 s.
  - Cache overhead: 0.043 s per fit (median of pairs).
  - Under heavier load (CPU 79-94 %) the same fit measured 1.573 s and 1.713 s. The cost is the mne CSP, not
    the cache.
- Cold filter and write of 900 rows (one band): 1.9 to 2.8 s.
- Memory hit for 900 rows: 0.11 to 0.12 s, hashing included.
- Disk read of 900 rows:
  - 19 to 22 s on the FIRST open after the files were written (probably antivirus scanning new files).
  - 0.40 s on a second read.
