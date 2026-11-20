"""Stroke motor-imagery loader (ticket S4; contracts.py STROKE LOADER CONTRACT; docs/STROKE_DATASET.md).

Liu et al. 2024, Scientific Data 11, 131 (CC BY 4.0). Pre-processed EDF release (figshare edffile.zip).
Evidence for every rule below, with measured numbers: docs/claude/DECISIONS_S4.md.

Output (contracts.DATASETS["stroke"])
    X       (n_trials, 29, 1500) float32, microvolt (uV); channels in bci.channels.STROKE_CHANNELS order
    y       (n_trials,) int64, 0 = left hand (trial_type 1), 1 = right hand (trial_type 2), config stroke.label_map
    groups  (n_trials,) int64 patient number (sub-XX -> XX)

What the EDF files hold (measured on all 50 files)
    33 signals, 500 Hz, 160000 samples (40 trials x 8 s), header unit "uV" for every signal, no annotations.
    Signals: the 29 EEG channels of STROKE_CHANNELS, CPz (recorded reference, all zeros), HEOL and HEOR (EOG;
    the BIDS sidecar calls the second one VEOR) and one marker signal with an EMPTY name whose values are the
    event codes 0/1/2/3 (1 instruction, 2 motor-imagery onset, 3 break; task-motor-imagery_events.json).
    The file is the concatenation of 40 epochs of 4000 samples, one per trial, each starting at its code 1.
    The marker signal does not say left or right. The class order comes from task-motor-imagery_events.tsv
    (BIDS top level, one file for every patient). It matches the per-patient `label` vector of the raw .mat
    files for all 50 patients (DECISIONS_S4.md).

Pipeline per patient (all settings from config.yaml, block stroke, plus the top-level unit_scale)
    1. read the marker codes from the unfiltered signal; motor-imagery onset = a rising edge of code 2 whose next
       event is code 3 after the motor-imagery duration of events.tsv (4000 ms) +/- MI_TO_BREAK_TOL samples.
       Exactly one onset per 4000-sample trial epoch is required, else ValueError.
    2. keep the 29 EEG channels by NAME (drop CPz, HEOL, HEOR, marker); check the header unit is uV.
    3. common average reference over the 29 channels (config stroke.reference).
    4. band-pass the continuous signal with config stroke.filter_band (MNE FIR, as bci.data does).
    5. epoch config stroke.window after each onset (1500 samples), baseline None, volts -> uV (config unit_scale).

Duplicate recordings: the EDF files of patients 5, 15 and 49 hold the recordings of patients 4, 11 and 47
(DUPLICATE_EDF). load_stroke() leaves them out by default and raises if they are asked for explicitly, unless
include_duplicates=True (audit only: a duplicate under a second patient id leaks across cross-subject folds).

Data location: $BCI_STROKE_DIR (config stroke.data_dir_env), default <repo>/.cache/stroke. If the extracted
edffile/ folder is missing, edffile.zip is md5-checked and extracted there; if the zip is missing it is downloaded
(config download_attempts tries, md5-checked). Any failure raises. There is no substitute data source.
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

from .channels import STROKE_CHANNELS
from .contracts import dataset_spec, load_config, validate_data

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / ".cache"
CFG = load_config()
SCFG = CFG["stroke"]
_SPEC = dataset_spec("stroke")
N_CHANNELS, N_SAMPLES, SFREQ = _SPEC["n_channels"], _SPEC["n_samples"], _SPEC["sfreq"]

# MNE reads and writes its config file under the home folder. Point it inside the repo BEFORE mne is imported.
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(CACHE / "mne_home"))
Path(os.environ["_MNE_FAKE_HOME_DIR"]).mkdir(parents=True, exist_ok=True)

import mne  # noqa: E402  (must follow the _MNE_FAKE_HOME_DIR setup above)

# Files of figshare record 21679035 v5 (docs/STROKE_DATASET.md; md5 = figshare computed_md5).
EDF_ZIP = {"name": "edffile.zip", "url": "https://ndownloader.figshare.com/files/38516654",
           "size": 462843633, "md5": "aa4f96a0e8456f377f30d1ee8f41be40"}
EVENTS_TSV = {"name": "task-motor-imagery_events.tsv", "url": "https://ndownloader.figshare.com/files/38516084",
              "size": 3732, "md5": "f1c1f482471b90a7e067d9c502889647"}
EDF_ROOT = "edffile"
_MEMBER_RE = re.compile(r"edffile/(sub-\d{2}/(eeg/(sub-\d{2}_task-motor-imagery_eeg\.edf)?)?)?")

MARKER_CHANNEL = ""                 # the event-code signal has an empty name in every file (measured)
REFERENCE_CHANNEL = "CPz"           # recorded reference, stored as zeros (measured); not one of the 29
EOG_CHANNELS = ("HEOL", "HEOR")     # names in the EDF files (the sidecar channels.tsv says HEOL, VEOR)
EXPECTED_CHANNELS = frozenset(STROKE_CHANNELS) | {REFERENCE_CHANNEL, *EOG_CHANNELS, MARKER_CHANNEL}
UNIT_SPELLINGS = (b"uV", b"\xb5V")  # EDF header physical dimension accepted as microvolt (files say b"uV")
CODE_INSTRUCTION, CODE_MI, CODE_BREAK = 1, 2, 3  # task-motor-imagery_events.json "value" levels
MI_TO_BREAK_TOL = 25                # samples (50 ms). Measured code 2 -> code 3 gaps: DECISIONS_S4.md
MARKER_INT_TOL = 1e-3               # a marker sample is an event code only if it is this close to an integer

# copy patient -> patient whose recording the copy holds. Measured on edffile.zip md5 aa4f96a0e8456f377f30d1ee8f41be40:
# EDF-EDF r = 1.0 (4, 5), 0.9998 (47, 49), 0.9998 (11, 15); next highest pair r = 0.1246. Each copy matches the
# source patient's raw .mat trial by trial, not its own (DECISIONS_S4.md).
DUPLICATE_EDF = {5: 4, 15: 11, 49: 47}

RETRY_SLEEP_S = 2.0
DOWNLOAD_TIMEOUT_S = 60


# ---------------------------------------------------------------- files
def stroke_dir() -> Path:
    """$<config stroke.data_dir_env> if set, else <repo>/.cache/stroke. Created if missing."""
    env = os.environ.get(SCFG["data_dir_env"])
    path = Path(env) if env else CACHE / "stroke"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(spec: dict, dest: Path) -> Path:
    """Download spec["url"] to dest (atomic: .part file, md5 check, os.replace). Raises after the last attempt."""
    n = int(CFG["download_attempts"])
    part = dest.with_name(f"{dest.name}.{os.getpid()}.part")
    last = None
    for attempt in range(1, n + 1):
        try:
            with urllib.request.urlopen(spec["url"], timeout=DOWNLOAD_TIMEOUT_S) as r, open(part, "wb") as fh:
                shutil.copyfileobj(r, fh, 1 << 20)
            got = _md5(part)
            if got != spec["md5"]:
                raise OSError(f"{spec['name']}: md5 {got}, expected {spec['md5']}")
            os.replace(part, dest)
            return dest
        except Exception as exc:  # noqa: BLE001  (any network or checksum failure: retry, then raise)
            last = exc
            print(f"[bci.data_stroke] download {spec['name']} attempt {attempt}/{n} failed: "
                  f"{type(exc).__name__}: {exc}")
            if part.exists():
                part.unlink()
            if attempt < n:
                time.sleep(RETRY_SLEEP_S)
    raise RuntimeError(f"could not download {spec['name']} from {spec['url']} after {n} attempts: {last!r}")


def _safe_extract(zip_path: Path, dest: Path) -> None:
    """Extract the EDF zip into dest/edffile. Only the expected member names are allowed (no path tricks)."""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        bad = [m for m in names if not _MEMBER_RE.fullmatch(m)]
        if bad:
            raise ValueError(f"{zip_path}: unexpected member names {bad[:5]}")
        tmp = dest / f".{EDF_ROOT}.tmp-{os.getpid()}"
        if tmp.exists():
            shutil.rmtree(tmp)
        zf.extractall(tmp)  # zipfile checks each member's CRC while it extracts
    try:
        os.replace(tmp / EDF_ROOT, dest / EDF_ROOT)
    except OSError:
        if not (dest / EDF_ROOT).is_dir():  # another process may have finished first
            raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def edf_root() -> Path:
    """Folder holding sub-XX/eeg/*.edf. Extracts (and if needed downloads) edffile.zip once. Raises on failure."""
    base = stroke_dir()
    root = base / EDF_ROOT
    if root.is_dir():
        return root
    zpath = base / EDF_ZIP["name"]
    if not zpath.exists():
        _download(EDF_ZIP, zpath)
    got = _md5(zpath)
    if got != EDF_ZIP["md5"]:
        raise OSError(f"{zpath}: md5 {got}, expected {EDF_ZIP['md5']} (delete it to download again)")
    _safe_extract(zpath, base)
    return root


def edf_path(subject: int) -> Path:
    s = int(subject)
    path = edf_root() / f"sub-{s:02d}" / "eeg" / f"sub-{s:02d}_task-motor-imagery_eeg.edf"
    if not path.is_file():
        raise FileNotFoundError(f"patient {s}: {path} not found")
    return path


def events_tsv_path() -> Path:
    """task-motor-imagery_events.tsv in the stroke folder (downloaded and md5-checked if missing)."""
    path = stroke_dir() / EVENTS_TSV["name"]
    if not path.exists():
        _download(EVENTS_TSV, path)
    got = _md5(path)
    if got != EVENTS_TSV["md5"]:
        raise OSError(f"{path}: md5 {got}, expected {EVENTS_TSV['md5']}")
    return path


# ---------------------------------------------------------------- trial table
def trial_table() -> dict:
    """Trial facts from events.tsv: trial_type per motor-imagery row, MI duration and trial period in samples.

    onset and duration are in milliseconds (task-motor-imagery_events.json).
    """
    with open(events_tsv_path(), "r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    mi = [r for r in rows if int(r["value"]) == CODE_MI]
    instr = [r for r in rows if int(r["value"]) == CODE_INSTRUCTION]
    trial_type = np.array([int(r["trial_type"]) for r in mi], dtype=np.int64)
    mi_ms = {int(r["duration"]) for r in mi}
    period_ms = set(np.diff([int(r["onset"]) for r in instr]).tolist())
    if len(mi_ms) != 1 or len(period_ms) != 1 or len(instr) != len(mi):
        raise ValueError(f"events.tsv: irregular trials (MI durations {mi_ms}, periods {period_ms})")
    to_samples = SFREQ / 1000.0
    return {"trial_type": trial_type,
            "mi_samples": int(round(mi_ms.pop() * to_samples)),
            "trial_samples": int(round(period_ms.pop() * to_samples))}


def labels_from_trial_type(trial_type) -> np.ndarray:
    """trial_type 1 -> 0 (left), 2 -> 1 (right) via config stroke.label_map (YAML keys may be int or str)."""
    lmap = {int(k): int(v) for k, v in SCFG["label_map"].items()}
    unknown = sorted(set(np.asarray(trial_type).tolist()) - set(lmap))
    if unknown:
        raise ValueError(f"trial_type values {unknown} not in config stroke.label_map {lmap}")
    return np.array([lmap[int(t)] for t in trial_type], dtype=np.int64)


def marker_codes(marker):
    """Marker signal in its header unit -> (codes int64, nonint bool mask).

    Event codes are the exactly-integer samples (within MARKER_INT_TOL). Some files carry non-integer values
    (e.g. 2.8147) after the break of a trial; the raw .mat files hold the same values. They are not events:
    they become code 0 and are flagged in nonint. An integer value outside 0-3 raises ValueError.
    """
    marker = np.asarray(marker, dtype=np.float64)
    near = np.rint(marker)
    nonint = np.abs(marker - near) > MARKER_INT_TOL
    code = np.where(nonint, 0, near).astype(np.int64)
    bad = sorted(set(np.unique(code).tolist()) - {0, CODE_INSTRUCTION, CODE_MI, CODE_BREAK})
    if bad:
        raise ValueError(f"marker codes {bad} are not event codes 0-3")
    return code, nonint


def mi_onsets(code, n_trials: int, mi_samples: int, trial_samples: int) -> np.ndarray:
    """Motor-imagery onset samples from the marker codes (1D int array). One per trial, in trial order.

    Events are rising edges (code != 0 and different from the previous sample). An onset is an event with code 2
    whose NEXT event is code 3, mi_samples +/- MI_TO_BREAK_TOL later. Onset i must lie in trial epoch i
    (onset // trial_samples == i). Anything else raises ValueError.
    """
    code = np.asarray(code)
    prev = np.r_[0, code[:-1]]
    edges = np.flatnonzero((code != 0) & (code != prev))
    ev = code[edges]
    onsets = [int(edges[j]) for j in range(len(edges) - 1)
              if ev[j] == CODE_MI and ev[j + 1] == CODE_BREAK
              and abs(int(edges[j + 1] - edges[j]) - mi_samples) <= MI_TO_BREAK_TOL]
    onsets = np.array(onsets, dtype=np.int64)
    if len(onsets) != n_trials:
        raise ValueError(f"found {len(onsets)} motor-imagery onsets, expected {n_trials}")
    if not np.array_equal(onsets // trial_samples, np.arange(n_trials)):
        raise ValueError(f"motor-imagery onsets not one per {trial_samples}-sample trial epoch: {onsets.tolist()}")
    return onsets


def _header_units(path: Path) -> dict:
    """Physical dimension (bytes) of every signal, read from the EDF header."""
    with open(path, "rb") as fh:
        head = fh.read(256)
        ns = int(head[252:256].decode("ascii").strip())
        sig = fh.read(256 * ns)
    labels = [sig[16 * i:16 * i + 16].decode("latin-1").strip() for i in range(ns)]
    off = (16 + 80) * ns
    dims = [sig[off + 8 * i:off + 8 * i + 8].strip() for i in range(ns)]
    return dict(zip(labels, dims))


# ---------------------------------------------------------------- epochs
def epochs_from_edf(path, table: dict | None = None):
    """One patient EDF -> (X uV float32 (40, 29, 1500), y int64 (40,), info dict). Raises on any irregularity."""
    table = table or trial_table()
    path = Path(path)
    raw = mne.io.read_raw_edf(path, preload=True, verbose="error")
    if abs(raw.info["sfreq"] - SFREQ) > 1e-6:
        raise ValueError(f"{path.name}: sampling rate {raw.info['sfreq']} Hz, expected {SFREQ} Hz")
    names = list(raw.ch_names)
    if set(names) != EXPECTED_CHANNELS or len(names) != len(EXPECTED_CHANNELS):
        raise ValueError(f"{path.name}: channels {names}, expected the set {sorted(EXPECTED_CHANNELS)}")
    units = _header_units(path)
    wrong = {ch: units.get(ch) for ch in STROKE_CHANNELS if units.get(ch) not in UNIT_SPELLINGS}
    if wrong:
        raise ValueError(f"{path.name}: EEG channels not in microvolt in the EDF header: {wrong}")

    scale = float(CFG["unit_scale"])  # volts -> microvolts; MNE returns volts for a "uV" EDF signal
    code, nonint = marker_codes(raw.get_data(picks=[names.index(MARKER_CHANNEL)])[0] * scale)
    n_trials = len(table["trial_type"])
    if raw.n_times != n_trials * table["trial_samples"]:
        raise ValueError(f"{path.name}: {raw.n_times} samples, expected {n_trials} x {table['trial_samples']}")
    onsets = mi_onsets(code, n_trials, table["mi_samples"], table["trial_samples"])
    for o in onsets:  # a non-integer marker value inside a motor-imagery interval would make its timing doubtful
        if nonint[o:o + table["mi_samples"]].any():
            raise ValueError(f"{path.name}: non-integer marker values inside the motor-imagery interval at {o}")

    raw.pick(list(STROKE_CHANNELS))
    if list(raw.ch_names) != list(STROKE_CHANNELS):
        raw.reorder_channels(list(STROKE_CHANNELS))
    assert list(raw.ch_names) == list(STROKE_CHANNELS)
    if SCFG["reference"] != "average":
        raise ValueError(f"unsupported stroke reference {SCFG['reference']!r}")
    raw.set_eeg_reference("average", projection=False, verbose="error")
    lo, hi = (float(f) for f in SCFG["filter_band"])
    raw.filter(lo, hi, picks="all", verbose="error")

    events = np.column_stack([onsets + raw.first_samp, np.zeros(n_trials, dtype=np.int64),
                              np.arange(1, n_trials + 1, dtype=np.int64)])  # code = trial number (1-based)
    w = SCFG["window"]
    epochs = mne.Epochs(raw, events, tmin=float(w["tmin"]), tmax=float(w["tmax"]), baseline=None, picks="all",
                        preload=True, reject_by_annotation=False, verbose="error")
    kept = epochs.events[:, 2] - 1
    if not np.array_equal(kept, np.arange(n_trials)):
        raise ValueError(f"{path.name}: epochs dropped, kept trials {kept.tolist()}")
    X = (epochs.get_data(copy=False) * scale).astype(np.float32)
    y = labels_from_trial_type(table["trial_type"])
    if X.shape != (n_trials, N_CHANNELS, N_SAMPLES):
        raise ValueError(f"{path.name}: epoch shape {X.shape}, expected ({n_trials}, {N_CHANNELS}, {N_SAMPLES})")
    offsets = onsets - np.arange(n_trials) * table["trial_samples"]
    info = {"onsets": onsets, "n_short_instruction": int(np.sum(offsets < table["trial_samples"] // 8)),
            "n_nonint_marker": int(nonint.sum())}
    return X, y, info


def load_patient(subject: int, table: dict | None = None):
    """(X, y, info) for one patient number."""
    return epochs_from_edf(edf_path(subject), table)


def _subject_list(subjects, include_duplicates: bool):
    if subjects is None:
        subjects = [int(s) for s in SCFG["subjects"]]
        if not include_duplicates:
            dropped = [s for s in subjects if s in DUPLICATE_EDF]
            subjects = [s for s in subjects if s not in DUPLICATE_EDF]
            if dropped:
                print(f"[bci.data_stroke] left out patients {dropped}: their EDF files hold the recordings of "
                      f"patients {[DUPLICATE_EDF[s] for s in dropped]} (DUPLICATE_EDF)")
        return subjects
    subjects = [int(s) for s in subjects]
    dup = [s for s in subjects if s in DUPLICATE_EDF]
    if dup and not include_duplicates:
        raise ValueError(f"patients {dup}: their EDF files hold the recordings of patients "
                         f"{[DUPLICATE_EDF[s] for s in dup]} (DUPLICATE_EDF); pass include_duplicates=True "
                         "only for an audit")
    if len(set(subjects)) != len(subjects):
        raise ValueError(f"repeated patient numbers in {subjects}")
    return subjects


def load_stroke(subjects=None, *, include_duplicates: bool = False):
    """Return (X, y, groups) for the given patient numbers (default config stroke.subjects minus DUPLICATE_EDF).

    X (n, 29, 1500) float32 uV, y int64 (0 left, 1 right), groups int64 patient number. Raises on any failure.
    """
    subjects = _subject_list(subjects, include_duplicates)
    if not subjects:
        raise ValueError("no patients to load")
    table = trial_table()
    Xs, ys, gs = [], [], []
    for s in subjects:
        X, y, _info = load_patient(s, table)
        Xs.append(X)
        ys.append(y)
        gs.append(np.full(len(y), s, dtype=np.int64))
    X = np.concatenate(Xs).astype(np.float32, copy=False)
    y = np.concatenate(ys).astype(np.int64, copy=False)
    groups = np.concatenate(gs).astype(np.int64, copy=False)
    validate_data(X, y, groups, "stroke")
    return X, y, groups
