"""Evaluator (C3, Claude). See the EVALUATOR CONTRACT in bci/contracts.py.

Rules kept here:
- Model names are resolved AT CALL TIME from models_classical.REGISTRY (+ models_advanced.REGISTRY if that
  module exists). Every fold gets a NEW estimator from the registry factory.
- X is never transformed: fit gets X[train_idx], predict gets X[test_idx], plain row slices of the given array.
  All preprocessing lives inside the estimators. fit never sees a test row.
- Splits come from bci.splits with the TRUE labels. The permutation control shuffles labels only inside each
  training set and inside each test set (after splitting), with seeded generators.
- Every estimator is fitted and then used for prediction before the next one is fitted.
- All numbers returned are plain Python floats / ints (JSON-serialisable). No unseeded randomness.

v0.3 (ticket S2; TIME LIMIT CONTRACT and EVALUATE CHECKPOINT CONTRACT in bci/contracts.py):
- The time budget is a SAFETY STOP only. A deadline exists only when contracts.enforce_time_budget(cfg) is True;
  otherwise no clock is read that can decide a branch (runtime_s is still measured and reported).
- run_model(..., checkpoint=path) writes the finished stages to a JSON file after every stage (temp file in the
  same folder + os.replace). A rerun with the same fingerprint (model name, X, y, groups, config) loads the
  finished stages instead of recomputing them. Timing and bookkeeping live only in the file, never in results.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, cohen_kappa_score

from bci import contracts, models_classical, splits
from bci.contracts import SEED


class _Timeout(Exception):
    """Internal: the model's time budget ran out between two fits."""


# ------------------------------------------------------------------ helpers
def _registry() -> dict:
    """Merged registry built at call time. A missing models_advanced.py is allowed; any other error is raised."""
    reg = dict(models_classical.REGISTRY)
    try:
        adv = importlib.import_module("bci.models_advanced")
    except ModuleNotFoundError as exc:
        if exc.name != "bci.models_advanced":
            raise
        return reg
    return {**reg, **adv.REGISTRY}


def _factory(name):
    reg = _registry()
    if name not in reg:
        raise KeyError(f"unknown model {name!r}; known: {sorted(reg)}")
    return reg[name]


def _check_time(deadline):
    if deadline is not None and time.monotonic() > deadline:
        raise _Timeout()


def _fit_predict(factory, X, y_fit, fit_idx, pred_idx, deadline):
    """Fresh estimator, fit on rows fit_idx with labels y_fit, predict rows pred_idx."""
    _check_time(deadline)
    est = factory()
    est.fit(X[fit_idx], y_fit)
    return np.asarray(est.predict(X[pred_idx]))


def _metrics(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    kappa = float(cohen_kappa_score(y_true, y_pred))
    if kappa != kappa:  # NaN only if truth and prediction are both one single class
        kappa = 0.0
    return {
        "acc": float(accuracy_score(y_true, y_pred)),
        "bal_acc": float(balanced_accuracy_score(y_true, y_pred)),
        "kappa": kappa,
    }


def _mean_std(values, ddof):
    v = np.asarray(values, dtype=float)
    std = float(np.std(v, ddof=ddof)) if len(v) > ddof else 0.0
    return float(np.mean(v)), std


def _labels(y, idx, rng):
    """True labels of rows idx, or a permutation of them inside this set when rng is given."""
    lab = np.asarray(y)[idx]
    return rng.permutation(lab) if rng is not None else lab.copy()


# ------------------------------------------------------------------ procedures
def _within(name, X, y, groups, *, rng=None, deadline=None, cfg=None):
    cfg = cfg or contracts.load_config()
    factory = _factory(name)
    y = np.asarray(y)
    groups = np.asarray(groups)
    pooled = {}  # sid -> ([y_true...], [y_pred...])
    for sid, tr, te in splits.within_subject_splits(y, groups, n_splits=cfg["n_splits"], seed=SEED):
        y_tr = _labels(y, tr, rng)
        y_te = _labels(y, te, rng)
        pred = _fit_predict(factory, X, y_tr, tr, te, deadline)
        t_list, p_list = pooled.setdefault(int(sid), ([], []))
        t_list.append(y_te)
        p_list.append(pred)
    per_subject = {}
    for sid in sorted(pooled):
        t_list, p_list = pooled[sid]
        per_subject[str(sid)] = _metrics(np.concatenate(t_list), np.concatenate(p_list))
    mean, std = _mean_std([m["bal_acc"] for m in per_subject.values()], cfg["std_ddof"])
    block = {"per_subject": per_subject, "mean_bal_acc": mean, "std_bal_acc": std}
    contracts.validate_within(block)
    return block


def _cross(name, X, y, groups, *, rng=None, deadline=None, cfg=None):
    cfg = cfg or contracts.load_config()
    factory = _factory(name)
    y = np.asarray(y)
    groups = np.asarray(groups)
    per_fold = []
    for fold, (tr, te) in enumerate(splits.cross_subject_splits(groups, n_splits=cfg["n_splits"], seed=SEED)):
        y_tr = _labels(y, tr, rng)
        y_te = _labels(y, te, rng)
        pred = _fit_predict(factory, X, y_tr, tr, te, deadline)
        m = _metrics(y_te, pred)
        per_fold.append({"fold": int(fold), "test_subjects": [int(s) for s in np.unique(groups[te])], **m})
    mean, std = _mean_std([f["bal_acc"] for f in per_fold], cfg["std_ddof"])
    block = {"per_fold": per_fold, "mean_bal_acc": mean, "std_bal_acc": std}
    contracts.validate_cross(block)
    return block


def _permutation(name, X, y, groups, *, deadline=None, cfg=None):
    cfg = cfg or contracts.load_config()
    _factory(name)  # unknown name -> KeyError before any work
    n_rep = cfg["n_permutations_eegnet"] if name == "eegnet_lite" else cfg["n_permutations"]
    within_means, cross_means = [], []
    for r in range(int(n_rep)):
        w = _within(name, X, y, groups, rng=np.random.default_rng([SEED, r, 0]), deadline=deadline, cfg=cfg)
        c = _cross(name, X, y, groups, rng=np.random.default_rng([SEED, r, 1]), deadline=deadline, cfg=cfg)
        within_means.append(w["mean_bal_acc"])
        cross_means.append(c["mean_bal_acc"])
    block = {"within_mean_bal_acc": float(np.mean(within_means)), "cross_mean_bal_acc": float(np.mean(cross_means))}
    contracts.validate_permutation(block)
    return block


def _calibration(name, X, y, groups, *, deadline=None, cfg=None, progress=None):
    """progress (optional dict) receives the finished k values, so a timeout can keep a partial curve."""
    cfg = cfg or contracts.load_config()
    factory = _factory(name)
    y = np.asarray(y)
    groups = np.asarray(groups)
    ks = sorted(int(k) for k in cfg["calibration_k"])  # ascending, k by k: every finished k is complete
    if progress is None:
        progress = {}
    progress.update(k=[], source_plus_target=[], target_only=[], per_target=[])
    spt_curve, to_curve = progress["source_plus_target"], progress["target_only"]
    per_target = progress["per_target"]  # one dict per finished k: {str(target): {source_plus_target, target_only}}
    for k in ks:
        spt, to = {}, {}  # target -> list of bal_acc over draws
        for target, src, cal, te in splits.calibration_splits(y, groups, k, n_repeats=cfg["calibration_repeats"],
                                                              seed=SEED):
            fit_idx = np.union1d(src, cal).astype(np.int64)
            pred = _fit_predict(factory, X, y[fit_idx], fit_idx, te, deadline)
            spt.setdefault(int(target), []).append(float(balanced_accuracy_score(y[te], pred)))
            if k > 0:
                pred = _fit_predict(factory, X, y[cal], cal, te, deadline)
                to.setdefault(int(target), []).append(float(balanced_accuracy_score(y[te], pred)))
        spt_curve.append(float(np.mean([np.mean(v) for _, v in sorted(spt.items())])))
        to_curve.append(float(np.mean([np.mean(v) for _, v in sorted(to.items())])) if k > 0 else None)
        per_target.append({str(t): {"source_plus_target": float(np.mean(spt[t])),
                                    "target_only": float(np.mean(to[t])) if k > 0 else None}
                           for t in sorted(spt)})
        progress["k"].append(k)  # appended last: k is listed only once both curve values exist
    block = _calibration_block(progress, len(progress["k"]))
    return block


def _calibration_block(progress, n):
    """Calibration block from the first n finished k values (n == all for a complete run)."""
    block = {"k": list(progress["k"][:n]), "source_plus_target": list(progress["source_plus_target"][:n]),
             "target_only": list(progress["target_only"][:n]), "per_target": list(progress["per_target"][:n])}
    contracts.validate_calibration(block)
    return block


def run_calibration(name, X, y, groups, budget_min, checkpoint=None):
    """Calibration stage only, with its own time budget in minutes (a safety stop, checked before every fit
    only when contracts.enforce_time_budget(cfg) is True).

    Returns {"calibration": block (absent if no k finished), "status": ok|timeout|error,
    "calibration_partial": bool, "runtime_s": float, ["error": str]}.
    checkpoint (optional path): same file and fingerprint as run_model; a finished calibration stage found there
    is loaded instead of recomputed, and a newly finished one is added to the file.
    """
    t0 = time.perf_counter()  # measured and reported only
    progress = {}
    out = {"status": "ok", "calibration_partial": False}
    try:
        cfg = contracts.load_config()
        deadline = _deadline(cfg, budget_min)
        ck = _Checkpoint(checkpoint, name, X, y, groups, cfg)
        if "calibration" in ck.stages:
            out["calibration"] = ck.stages["calibration"]
        else:
            ts = time.perf_counter()
            out["calibration"] = _calibration(name, X, y, groups, deadline=deadline, cfg=cfg, progress=progress)
            ck.save("calibration", out["calibration"], time.perf_counter() - ts)
        if ck.write_error:
            out["checkpoint_error"] = ck.write_error
    except _Timeout:
        out["status"] = "timeout"
        out["error"] = f"calibration budget of {budget_min} min exceeded"
        n = len(progress.get("k", []))
        if n > 0:
            out["calibration"] = _calibration_block(progress, n)
            out["calibration_partial"] = True
    except Exception as exc:  # noqa: BLE001 - recorded, never hidden
        out["status"] = "error"
        out["error"] = f"{type(exc).__name__}: {exc}"
    out["runtime_s"] = float(time.perf_counter() - t0)
    return out


# ------------------------------------------------------------------ time limit (safety stop only)
def _deadline(cfg, budget_min):
    """Monotonic deadline, or None when the time limit is off (then no clock read can change a result)."""
    if not contracts.enforce_time_budget(cfg):
        return None
    return time.monotonic() + float(budget_min) * 60.0


# ------------------------------------------------------------------ checkpoint (EVALUATE CHECKPOINT CONTRACT)
CHECKPOINT_VERSION = 1
STAGES = ("within_subject", "cross_subject", "permutation", "calibration")
_VALIDATORS = {"within_subject": contracts.validate_within, "cross_subject": contracts.validate_cross,
               "permutation": contracts.validate_permutation, "calibration": contracts.validate_calibration}


def _hash_array(h, label, a):
    a = np.ascontiguousarray(np.asarray(a))  # local copy only; the caller's X is never replaced
    h.update(f"{label}|{a.dtype.str}|{a.shape}|".encode("utf-8"))
    h.update(memoryview(a).cast("B"))


def fingerprint(name, X, y, groups, cfg) -> str:
    """sha256 hex of (checkpoint version, model name, X dtype/shape/bytes, y, groups as int64, config JSON).

    The calibration flag, the estimator class and environment variables are NOT part of it (contract).
    """
    h = hashlib.sha256()
    h.update(f"bci.evaluate.checkpoint.v{CHECKPOINT_VERSION}|model={name}|".encode("utf-8"))
    _hash_array(h, "X", X)
    _hash_array(h, "y", np.asarray(y).astype(np.int64))
    _hash_array(h, "groups", np.asarray(groups).astype(np.int64))
    h.update(json.dumps(cfg, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()


def _load_checkpoint(path, fp) -> dict:
    """Finished stages {stage: block} of the checkpoint at path if its fingerprint is fp, else {}.

    A missing, unreadable or foreign file is ignored (it is overwritten at the next finished stage). A stage
    block that fails its contract validator is dropped and recomputed.
    """
    if path is None or not Path(path).is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict) or doc.get("fingerprint") != fp or doc.get("version") != CHECKPOINT_VERSION:
        return {}
    stages = doc.get("stages")
    if not isinstance(stages, dict):
        return {}
    done = {}
    for key in STAGES:
        if key in stages:
            try:
                _VALIDATORS[key](stages[key])
            except (ValueError, KeyError, TypeError):
                continue
            done[key] = stages[key]
    return done


def _write_checkpoint(path, fp, name, stages, stage_runtime_s) -> None:
    """Atomic write: JSON to a temp file in the target folder, then os.replace (the old file stays intact)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"version": CHECKPOINT_VERSION, "fingerprint": fp, "model": name,
           "stages": {k: stages[k] for k in STAGES if k in stages},
           "stage_runtime_s": {k: float(v) for k, v in stage_runtime_s.items()}}
    text = json.dumps(doc, indent=1, allow_nan=False)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(5):  # Windows: a reader holding the target open makes os.replace fail briefly
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.1)  # retry pause only; never decides a result
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _read_stage_runtimes(path, fp) -> dict:
    """stage_runtime_s of a matching checkpoint (bookkeeping only, carried over so earlier times are kept)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        if doc.get("fingerprint") == fp and isinstance(doc.get("stage_runtime_s"), dict):
            return {k: float(v) for k, v in doc["stage_runtime_s"].items() if k in STAGES}
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return {}


class _Checkpoint:
    """Finished stages of one model run, mirrored to a JSON file (or kept in memory only when path is None)."""

    def __init__(self, path, name, X, y, groups, cfg):
        self.path = None if path is None else Path(path)
        self.name = name
        self.fp = fingerprint(name, X, y, groups, cfg) if self.path is not None else None
        self.stages = _load_checkpoint(self.path, self.fp) if self.path is not None else {}
        self.runtimes = _read_stage_runtimes(self.path, self.fp) if self.stages else {}
        self.write_error = None

    def save(self, key, block, seconds):
        self.stages[key] = block
        self.runtimes[key] = seconds
        if self.path is None:
            return
        try:
            _write_checkpoint(self.path, self.fp, self.name, self.stages, self.runtimes)
        except OSError as exc:  # the result is still valid; only the resume ability is lost, and that is reported
            self.write_error = f"{type(exc).__name__}: {exc}"


# ------------------------------------------------------------------ public API (contract)
def within_subject(name, X, y, groups):
    """WITHIN block: per-subject metrics on that subject's out-of-fold predictions pooled over its folds."""
    return _within(name, X, y, groups)


def cross_subject(name, X, y, groups):
    """CROSS block: one entry per cross-subject fold."""
    return _cross(name, X, y, groups)


def permutation_control(name, X, y, groups):
    """PERMUTATION block: labels shuffled inside each train set and each test set; mean over the repeats."""
    return _permutation(name, X, y, groups)


def calibration_curve(name, X, y, groups):
    """CALIBRATION block: source_plus_target and target_only curves over config calibration_k."""
    return _calibration(name, X, y, groups)


def run_model(name, X, y, groups, calibration: bool, checkpoint=None):
    """Model block {within_subject, cross_subject, permutation, [calibration], status, runtime_s}.

    Time limit (TIME LIMIT CONTRACT): config time_budget_min is a safety stop for the whole model, checked
    before every fit ONLY when contracts.enforce_time_budget(cfg) is True. When it is False no clock value
    decides anything; runtime_s is still measured and reported. On overrun the finished blocks are kept and
    status is "timeout". If the budget runs out during calibration, the k values that finished are kept as a
    valid calibration block (lists cut to the same length) and "calibration_partial" is True.

    Checkpoint (EVALUATE CHECKPOINT CONTRACT): checkpoint = path of a JSON file, or None (no file). After each
    finished stage the finished stages are written atomically to that file. On start, the stages of a file with
    the same fingerprint (model name, X, y, groups, config; not the calibration flag) are loaded and not
    recomputed. A file with another fingerprint is ignored and overwritten at the next finished stage. Only the
    stages asked for are returned (a calibration stored by an earlier run is kept in the file but not returned
    when calibration is False). A partial calibration (timeout) is never stored as finished.

    Any exception gives status "error" with an "error" string. A failed checkpoint write does not change the
    results; it is reported as "checkpoint_error".
    """
    t0 = time.perf_counter()  # measured and reported only, never compared
    out = {}
    progress = {}
    steps = [("within_subject", _within), ("cross_subject", _cross), ("permutation", _permutation)]
    if calibration:
        steps.append(("calibration", lambda *a, **kw: _calibration(*a, progress=progress, **kw)))
    status = "ok"
    key = None
    ck = None
    try:
        cfg = contracts.load_config()
        deadline = _deadline(cfg, cfg["time_budget_min"])
        ck = _Checkpoint(checkpoint, name, X, y, groups, cfg)
        for key, fn in steps:
            if key in ck.stages:
                out[key] = ck.stages[key]
                continue
            ts = time.perf_counter()
            out[key] = fn(name, X, y, groups, deadline=deadline, cfg=cfg)
            ck.save(key, out[key], time.perf_counter() - ts)
    except _Timeout:
        status = "timeout"
        out["error"] = f"time budget of {cfg['time_budget_min']} min exceeded during {key}"
        n = len(progress.get("k", []))
        if key == "calibration" and n > 0:
            out["calibration"] = _calibration_block(progress, n)
            out["calibration_partial"] = True
    except Exception as exc:  # noqa: BLE001 - recorded in the results, never hidden
        status = "error"
        out["error"] = f"{type(exc).__name__}: {exc}"
    if ck is not None and ck.write_error:
        out["checkpoint_error"] = ck.write_error
    out["status"] = status
    out["runtime_s"] = float(time.perf_counter() - t0)
    return out
