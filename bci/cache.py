"""Filter cache (ticket S1, FILTER CACHE CONTRACT in bci/contracts.py).

Stores ONLY stateless band-pass output (zero-phase Butterworth, sosfiltfilt, float64, last axis = time).
Nothing learned, nothing that depends on labels.

Key design
    namespace = (low, high, fs, order, input dtype, row shape, scipy version, cache format version)
    row key   = sha256 of the bytes of ONE input row X[i] (the CONTENT, never id()).
    Filtering is independent per 1D series along the last axis, so a cache per row is exact: a new row
    subset X[idx] (cross-validation) hits for every row that was filtered before, in any order.

Storage
    memory: {namespace: {row key: float64 row copy}} in this process, filled until a byte cap
            ($BCI_FILTER_CACHE_MEM_MB, default 4096); rows past the cap are served from disk.
    disk:   <$BCI_FILTER_CACHE_DIR or <repo>/.cache/filtered>/<16 hex of namespace>/<32 hex of row>.npy,
            one float64 array of shape X.shape[1:] per file. Written atomically: temp file in the same
            directory (name ends in .tmp, never .npy) + os.replace; the temp file is always removed.

$BCI_FILTER_CACHE == "0" turns memory and disk cache off (read at call time).
"""
from __future__ import annotations

import hashlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import scipy
from scipy.signal import butter, sosfiltfilt

FORMAT_VERSION = "1"
ENV_ON = "BCI_FILTER_CACHE"
ENV_DIR = "BCI_FILTER_CACHE_DIR"
ENV_MEM_MB = "BCI_FILTER_CACHE_MEM_MB"
DEFAULT_MEM_MB = 4096
REPO = Path(__file__).resolve().parents[1]

_LOCK = threading.Lock()
_MEM: dict = {}          # namespace hex -> {row hex: float64 row (owned copy, never handed out)}
_MEM_BYTES = [0]
_HASH_THREADS = 4        # hashlib releases the GIL on large buffers; the digest does not depend on threads
_POOL: list = []


# ---------------------------------------------------------------- settings (read at call time)
def enabled() -> bool:
    return os.environ.get(ENV_ON, "1") != "0"


def cache_dir() -> Path:
    d = os.environ.get(ENV_DIR)
    return Path(d) if d else REPO / ".cache" / "filtered"


def _mem_cap_bytes() -> int:
    try:
        mb = float(os.environ.get(ENV_MEM_MB, DEFAULT_MEM_MB))
    except ValueError:
        mb = DEFAULT_MEM_MB
    return int(max(mb, 0.0) * 1024 * 1024)


def clear_memory() -> None:
    """Empty the in-process memory cache (disk files stay)."""
    with _LOCK:
        _MEM.clear()
        _MEM_BYTES[0] = 0


def memory_bytes() -> int:
    """Bytes of filter output held in this process."""
    return _MEM_BYTES[0]


# ---------------------------------------------------------------- filter (the only math)
def bandpass_direct(X, low, high, fs, order) -> np.ndarray:
    """Uncached zero-phase Butterworth band-pass over the last axis, float64."""
    sos = butter(order, [low, high], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, np.asarray(X, dtype=np.float64), axis=-1)


def _namespace(low, high, fs, order, dtype, row_shape) -> str:
    desc = repr(("bandpass", float(low), float(high), float(fs), int(order), np.dtype(dtype).str,
                 tuple(int(s) for s in row_shape), scipy.__version__, FORMAT_VERSION))
    return hashlib.sha256(desc.encode("ascii")).hexdigest()[:16]


# ---------------------------------------------------------------- disk helpers
def _load_row(path: Path, row_shape):
    try:
        a = np.load(path, allow_pickle=False)
    except (OSError, ValueError, EOFError):
        return None
    if a.dtype != np.float64 or a.shape != tuple(row_shape):
        return None
    return a


def _save_row(path: Path, row: np.ndarray) -> None:
    """Atomic write: temp file in the same directory, then os.replace. Never raises, never leaves the temp."""
    if path.exists():
        return
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "wb") as fh:
            np.save(fh, row, allow_pickle=False)
        try:
            os.replace(tmp, path)
        except OSError:
            pass  # Windows: another process holds the target open; its content is the same row
    except OSError:
        pass
    finally:
        try:
            if tmp.exists():
                os.remove(tmp)
        except OSError:
            pass


def _row_key(row) -> str:
    return hashlib.sha256(row).hexdigest()[:32]


def _row_keys(Xc) -> list:
    """sha256 of each C-contiguous row (content key). Threads only for speed; same keys in the same order."""
    if len(Xc) < 32:
        return [_row_key(Xc[i]) for i in range(len(Xc))]
    with _LOCK:
        if not _POOL:
            _POOL.append(ThreadPoolExecutor(max_workers=_HASH_THREADS, thread_name_prefix="bci-cache-hash"))
        pool = _POOL[0]
    return list(pool.map(_row_key, (Xc[i] for i in range(len(Xc))), chunksize=32))


# ---------------------------------------------------------------- cached band-pass
def filtered(X, low, high, fs, order) -> np.ndarray:
    """Band-pass X (rows = first axis, time = last axis) through the cache. Returns a NEW float64 array."""
    X = np.asarray(X)
    if not enabled() or X.ndim < 2 or X.size == 0:
        return bandpass_direct(X, low, high, fs, order)
    Xc = np.ascontiguousarray(X)
    row_shape = Xc.shape[1:]
    ns = _namespace(low, high, fs, order, Xc.dtype, row_shape)
    keys = _row_keys(Xc)

    out = np.empty(Xc.shape, dtype=np.float64)
    with _LOCK:
        mem = _MEM.get(ns)
        missing = {}  # row key -> first position (duplicates in X share one entry)
        for i, k in enumerate(keys):
            row = mem.get(k) if mem is not None else None
            if row is not None:
                out[i] = row
            elif k not in missing:
                missing[k] = i
    if not missing:
        return out

    ddir = cache_dir() / ns
    found = {}
    try:
        on_disk = {e.name for e in os.scandir(ddir)} if ddir.is_dir() else set()
    except OSError:
        on_disk = set()
    for k in missing:
        if k + ".npy" in on_disk:
            row = _load_row(ddir / (k + ".npy"), row_shape)
            if row is not None:
                found[k] = row
    todo = [k for k in missing if k not in found]
    if todo:
        rows = bandpass_direct(Xc[[missing[k] for k in todo]], low, high, fs, order)
        try:
            ddir.mkdir(parents=True, exist_ok=True)
            writable = True
        except OSError:
            writable = False
        for j, k in enumerate(todo):
            row = rows[j].copy()
            found[k] = row
            if writable:
                _save_row(ddir / (k + ".npy"), row)

    for i, k in enumerate(keys):
        if k in found:
            out[i] = found[k]
    _admit(ns, found)
    return out


def _admit(ns: str, rows: dict) -> None:
    """Add rows to memory until the byte cap; no eviction (a fixed working set never thrashes)."""
    cap = _mem_cap_bytes()
    with _LOCK:
        mem = _MEM.setdefault(ns, {})
        for k, row in rows.items():
            if k in mem:
                continue
            if _MEM_BYTES[0] + row.nbytes > cap:
                break
            mem[k] = row
            _MEM_BYTES[0] += row.nbytes
