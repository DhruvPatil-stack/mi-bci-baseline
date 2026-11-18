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
"""
from __future__ import annotations

import importlib
import time

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


def run_calibration(name, X, y, groups, budget_min):
    """Calibration stage only, with its own time budget in minutes (checked before every fit).

    Returns {"calibration": block (absent if no k finished), "status": ok|timeout|error,
    "calibration_partial": bool, "runtime_s": float, ["error": str]}.
    """
    t0 = time.monotonic()
    deadline = t0 + float(budget_min) * 60.0
    progress = {}
    out = {"status": "ok", "calibration_partial": False}
    try:
        out["calibration"] = _calibration(name, X, y, groups, deadline=deadline, progress=progress)
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
    out["runtime_s"] = float(time.monotonic() - t0)
    return out


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


def run_model(name, X, y, groups, calibration: bool):
    """Model block {within_subject, cross_subject, permutation, [calibration], status, runtime_s}.

    The whole model gets config time_budget_min, checked before every fit. On overrun the finished blocks are
    kept and status is "timeout". If the budget runs out during calibration, the k values that finished are kept
    as a valid calibration block (lists cut to the same length) and "calibration_partial" is True.
    Any exception gives status "error" with an "error" string.
    """
    cfg = contracts.load_config()
    t0 = time.monotonic()
    deadline = t0 + float(cfg["time_budget_min"]) * 60.0
    out = {}
    progress = {}
    steps = [("within_subject", _within), ("cross_subject", _cross), ("permutation", _permutation)]
    if calibration:
        steps.append(("calibration", lambda *a, **kw: _calibration(*a, progress=progress, **kw)))
    status = "ok"
    try:
        for key, fn in steps:
            out[key] = fn(name, X, y, groups, deadline=deadline, cfg=cfg)
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
    out["status"] = status
    out["runtime_s"] = float(time.monotonic() - t0)
    return out
