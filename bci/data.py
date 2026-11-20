"""PhysioNet EEG Motor Movement/Imagery loader (ticket C1, PRD section 5, contracts.py DATA CONTRACT).

Output contract
    X       (n_trials, n_channels, n_samples) float32, microvolt (uV); PhysioNet spec 64 x 480 at 160 Hz
            (read from contracts.dataset_spec("physionet"))
    y       (n_trials,) int64, 0 = left fist (T1), 1 = right fist (T2); rest (T0) is dropped
    groups  (n_trials,) int64 subject id

Every setting (reference, filter band, window, event map, unit scale, attempts, data dir env var) is read
from bci/config.yaml. All MNE caches stay inside the repository (AGENTS.md platform rule).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

from . import synthetic
from .contracts import SYNTHETIC_LABEL, dataset_spec, load_config

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / ".cache"
CFG = load_config()
_PN = dataset_spec("physionet")  # this loader is PhysioNet only: shape and rate come from the dataset contract
N_CHANNELS, N_SAMPLES, SFREQ = _PN["n_channels"], _PN["n_samples"], _PN["sfreq"]

# MNE reads and writes its config file under the home folder. Point it inside the repo BEFORE mne is imported.
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(CACHE / "mne_home"))
Path(os.environ["_MNE_FAKE_HOME_DIR"]).mkdir(parents=True, exist_ok=True)

import mne  # noqa: E402  (must follow the _MNE_FAKE_HOME_DIR setup above)

RETRY_SLEEP_S = 2.0  # pause between download attempts (<= 5 s)


def data_dir() -> Path:
    """MNE data cache: $<config data_dir_env> if set, else <repo>/.cache/mne_data. Created if missing."""
    env = os.environ.get(CFG["data_dir_env"])
    path = Path(env) if env else CACHE / "mne_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def epochs_from_raw(raw):
    """One continuous mne Raw in VOLTS with T0/T1/T2 annotations -> (X uV float32, y int64).

    Steps: common average reference, band-pass the continuous signal with config filter_band, keep T1/T2 by
    annotation description (config event_map), epoch config window tmin..tmax (480 samples), baseline=None,
    multiply by config unit_scale. No channel names or montage are used. The input raw is not modified.
    """
    raw = raw.copy().load_data()
    picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    if len(picks) != raw.info["nchan"]:
        raw.pick(picks)
    if abs(raw.info["sfreq"] - SFREQ) > 1e-6:
        raise ValueError(f"sampling rate {raw.info['sfreq']} Hz, expected {SFREQ} Hz")
    if CFG["reference"] != "average":
        raise ValueError(f"unsupported reference {CFG['reference']!r}")
    raw.set_eeg_reference("average", projection=False, verbose="error")
    lo, hi = (float(f) for f in CFG["filter_band"])
    raw.filter(lo, hi, picks="all", verbose="error")

    event_map = {str(k): int(v) for k, v in CFG["event_map"].items()}  # {"T1": 0, "T2": 1}
    # MNE event codes must be non-zero: use internal codes 1..k, then map back to the config labels.
    names = sorted(event_map)
    code_of = {name: i + 1 for i, name in enumerate(names)}
    label_of_code = {code_of[name]: event_map[name] for name in names}
    present = set(raw.annotations.description)
    event_id = {name: code for name, code in code_of.items() if name in present}
    if not event_id:
        raise ValueError(f"no {names} annotations in raw (found {sorted(present)})")
    events, _ = mne.events_from_annotations(raw, event_id=event_id, verbose="error")

    w = CFG["window"]
    epochs = mne.Epochs(raw, events, event_id=event_id, tmin=float(w["tmin"]), tmax=float(w["tmax"]),
                        baseline=None, picks="all", preload=True, verbose="error")
    X = (epochs.get_data(copy=False) * float(CFG["unit_scale"])).astype(np.float32)
    y = np.array([label_of_code[int(c)] for c in epochs.events[:, 2]], dtype=np.int64)
    assert X.ndim == 3 and X.shape[1:] == (N_CHANNELS, N_SAMPLES), f"epoch shape {X.shape}"
    assert len(X) == len(y)
    return X, y


def _load_subject(subject: int, runs, path: Path):
    files = mne.datasets.eegbci.load_data(int(subject), list(runs), path=str(path), update_path=False,
                                          verbose="error")
    raws = [mne.io.read_raw_edf(f, preload=True, verbose="error") for f in files]
    raw = mne.concatenate_raws(raws, verbose="error")  # run joins get BAD/EDGE boundary annotations
    return epochs_from_raw(raw)


def load_dataset(subjects, runs):
    """PhysioNet only. Return (X, y, groups) for the given subjects and runs. Raises on any failure."""
    path = data_dir()
    Xs, ys, gs = [], [], []
    for s in subjects:
        X, y = _load_subject(int(s), runs, path)
        if len(X) == 0:
            raise RuntimeError(f"subject {s}: no T1/T2 trials")
        Xs.append(X)
        ys.append(y)
        gs.append(np.full(len(y), int(s), dtype=np.int64))
    X = np.concatenate(Xs).astype(np.float32, copy=False)
    y = np.concatenate(ys).astype(np.int64, copy=False)
    groups = np.concatenate(gs).astype(np.int64, copy=False)
    assert X.shape[1:] == (N_CHANNELS, N_SAMPLES), X.shape
    return X, y, groups


def load_with_fallback(subjects, runs):
    """Try the module-level load_dataset up to config download_attempts times, else synthetic data.

    Returns (X, y, groups, source) with source "physionet" or "synthetic".
    """
    n = int(CFG["download_attempts"])
    last = None
    for attempt in range(1, n + 1):
        try:
            X, y, groups = load_dataset(subjects, runs)  # module global: a test may monkeypatch it
            return X, y, groups, "physionet"
        except Exception as exc:  # noqa: BLE001  (any download/read failure triggers a retry)
            last = exc
            print(f"[bci.data] PhysioNet load attempt {attempt}/{n} failed: {type(exc).__name__}: {exc}")
            if attempt < n:
                time.sleep(RETRY_SLEEP_S)
    print(f"[bci.data] {SYNTHETIC_LABEL}: PhysioNet failed {n} times (last error: {last!r}); "
          "using synthetic.make_synthetic() data")
    X, y, groups, _truth = synthetic.make_synthetic()
    return X, y, groups, "synthetic"
