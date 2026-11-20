"""Responder and calibration-group analysis (v0.3 H1)."""
from __future__ import annotations

import numpy as np
from scipy.stats import binomtest
from sklearn.metrics import balanced_accuracy_score

from bci.contracts import SEED, load_config
from bci.splits import within_subject_splits


def _oof_balanced_accuracy(estimator_factory, X, y, seed):
    """Balanced accuracy from pooled within-subject out-of-fold predictions."""
    cfg = load_config()
    groups = np.ones(len(y), dtype=np.int64)
    actual, predicted = [], []
    for _, train_idx, test_idx in within_subject_splits(
        y, groups, n_splits=cfg["n_splits"], seed=seed
    ):
        estimator = estimator_factory()
        estimator.fit(X[train_idx], y[train_idx])
        actual.append(y[test_idx])
        predicted.append(np.asarray(estimator.predict(X[test_idx])))
    return float(balanced_accuracy_score(np.concatenate(actual), np.concatenate(predicted)))


def subject_pvalue(estimator_factory, X, y, n_perm, seed):
    """Compute the pre-specified, one-subject permutation p-value for response."""
    X, y = np.asarray(X), np.asarray(y)
    if X.ndim != 3 or y.ndim != 1 or len(X) != len(y):
        raise ValueError("X must be trials x channels x samples and y one label per trial")
    if not isinstance(n_perm, (int, np.integer)) or n_perm < 1:
        raise ValueError("n_perm must be a positive integer")
    if set(np.unique(y).tolist()) != {0, 1}:
        raise ValueError("responder analysis needs both labels 0 and 1")
    # The responder rule fixes CV folds to the project seed.  The argument
    # controls only the reproducible null-label sequence.
    obs = _oof_balanced_accuracy(estimator_factory, X, y, SEED)
    rng = np.random.default_rng(seed)
    null = [
        _oof_balanced_accuracy(estimator_factory, X, rng.permutation(y), SEED)
        for _ in range(int(n_perm))
    ]
    pvalue = (1 + sum(score >= obs for score in null)) / (1 + int(n_perm))
    return {"obs": obs, "null": [float(score) for score in null], "p": float(pvalue)}


def classify_responders(pvalues, alpha):
    """Classify strict p < alpha responders and exact-binomial uncertainty."""
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    flags = {str(subject): float(pvalue) < float(alpha) for subject, pvalue in pvalues.items()}
    count, n = sum(flags.values()), len(flags)
    if n:
        interval = binomtest(count, n).proportion_ci(confidence_level=0.95, method="exact")
        ci95 = [float(interval.low), float(interval.high)]
    else:
        ci95 = [None, None]
    return {
        "flags": flags,
        "count": int(count),
        "n": int(n),
        "ci95": ci95,
        "expected_false_positives": float(alpha) * n,
    }


def calibration_gain_by_group(per_target, flags, k, n_boot=10_000, seed=SEED):
    """Compare source-plus-target gains for responders and non-responders.

    Targets are resampled with replacement separately inside the two fixed responder
    groups.  The gain baseline is each target's source-plus-target score at k=0.
    """
    if len(per_target) != len(k) or not k or 0 not in k:
        raise ValueError("per_target and non-empty k must align and include k=0")
    if not isinstance(n_boot, (int, np.integer)) or n_boot < 1:
        raise ValueError("n_boot must be a positive integer")
    baseline_at = list(k).index(0)
    flags = {str(subject): bool(flag) for subject, flag in flags.items()}

    gains = {True: [[] for _ in k], False: [[] for _ in k]}
    baseline = per_target[baseline_at]
    for subject, flag in flags.items():
        row0 = baseline.get(subject)
        if not isinstance(row0, dict) or row0.get("source_plus_target") is None:
            continue
        zero = float(row0["source_plus_target"])
        for i, targets_at_k in enumerate(per_target):
            row = targets_at_k.get(subject)
            if isinstance(row, dict) and row.get("source_plus_target") is not None:
                gains[flag][i].append(float(row["source_plus_target"]) - zero)

    def averages(flag):
        return [float(np.mean(values)) if values else None for values in gains[flag]]

    responders, non_responders = averages(True), averages(False)
    diff, intervals = [], []
    rng = np.random.default_rng(seed)
    for i in range(len(k)):
        left, right = np.asarray(gains[True][i]), np.asarray(gains[False][i])
        if not len(left) or not len(right):
            diff.append(None)
            intervals.append(None)
            continue
        observed = float(left.mean() - right.mean())
        left_draws = rng.integers(0, len(left), size=(int(n_boot), len(left)))
        right_draws = rng.integers(0, len(right), size=(int(n_boot), len(right)))
        boot = left[left_draws].mean(axis=1) - right[right_draws].mean(axis=1)
        diff.append(observed)
        intervals.append([float(v) for v in np.percentile(boot, [2.5, 97.5])])
    return {
        "k": list(k),
        "responders": responders,
        "non_responders": non_responders,
        "diff": diff,
        "diff_ci95": intervals,
        "n_responders": sum(bool(v) for v in flags.values()),
        "n_non_responders": sum(not bool(v) for v in flags.values()),
    }
