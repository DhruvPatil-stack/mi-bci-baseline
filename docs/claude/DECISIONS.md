# Claude branch decisions

## C1 `bci/data.py` (Sous chef)

1. **Data cache inside the repo.** PRD section 5 says "cache outside the repo", but AGENTS.md and the ticket say
   `$BCI_DATA_DIR`, else `<repo>/.cache/mne_data` (git-excluded via `.git/info/exclude`). AGENTS.md / the ticket win.
   `_MNE_FAKE_HOME_DIR` is set (setdefault) to `<repo>/.cache/mne_home` before `import mne`.
2. **Internal MNE event codes 1..k.** MNE event ids should be non-zero, so T1/T2 get internal codes 1/2 (sorted by
   description) and are mapped back to config `event_map` labels (T1 -> 0, T2 -> 1). Selection is by annotation
   description only; T0 and any other annotation are ignored.
3. **Order: average reference, then band-pass** (both linear, so the order does not change the result). Reference
   with `set_eeg_reference("average", projection=False)`; filter with MNE's default zero-phase FIR
   (`raw.filter(1.0, 40.0)`), no other parameter tuned.
4. **Runs are concatenated** with `mne.concatenate_raws`. The filter respects the run boundaries (MNE default
   `skip_by_annotation` includes "edge"); `Epochs` keeps `reject_by_annotation=True`, so an epoch crossing a
   run boundary would be dropped. Measured: no epoch was dropped for subjects 1-3 (each run epoched alone gives
   15 trials; concatenated, 45 per subject).
5. **No `eegbci.standardize`, no montage.** Channels are picked by type (EEG), never by name.
6. **Sampling-rate guard.** `epochs_from_raw` raises if sfreq != 160 Hz (defensive guard; not verified against any
   specific subject here); the 480-sample shape is also asserted.
7. **Fallback.** `load_with_fallback` calls the module-level `load_dataset` (monkeypatchable) up to
   `download_attempts` times, catching any `Exception`, with `time.sleep(2.0)` between attempts (none after the last),
   then prints a `SYNTHETIC - NOT VALID` line and returns `synthetic.make_synthetic()` with source "synthetic".

Measured (subjects 1-3, runs 4/8/12): X (135, 64, 480) float32; 45 trials per subject (23 left / 22 right each);
median |X| = 11.10 uV.
