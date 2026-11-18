"""FROZEN split functions (PRD section 7). Head chef, Phase 0.

All index arrays are global row indices into X, dtype int64, sorted ascending.
"""
from __future__ import annotations

import numpy as np
from sklearn.model_selection import StratifiedKFold

from .contracts import SEED


def within_subject_splits(y, groups, n_splits=5, seed=SEED):
    """Yield (subject_id, train_idx, test_idx). Stratified. One subject only.

    Subjects are visited in ascending id order. Inside a subject, StratifiedKFold(shuffle=True,
    random_state=seed) over that subject's trials. Every trial of a subject is in exactly one test fold.
    """
    y = np.asarray(y)
    groups = np.asarray(groups)
    for sid in np.unique(groups):
        idx = np.flatnonzero(groups == sid)
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        for tr, te in skf.split(np.zeros(len(idx)), y[idx]):
            yield int(sid), np.sort(idx[tr]).astype(np.int64), np.sort(idx[te]).astype(np.int64)


def cross_subject_splits(groups, n_splits=5, seed=SEED):
    """Yield (train_idx, test_idx). No subject appears in both sets.

    Unique subject ids are permuted with np.random.RandomState(seed) and cut into n_splits nearly equal
    folds (np.array_split). Every subject is in exactly one test fold.
    """
    groups = np.asarray(groups)
    subjects = np.unique(groups)
    if len(subjects) < n_splits:
        raise ValueError(f"need at least {n_splits} subjects, got {len(subjects)}")
    perm = np.random.RandomState(seed).permutation(subjects)
    for test_subjects in np.array_split(perm, n_splits):
        test_mask = np.isin(groups, test_subjects)
        yield (np.flatnonzero(~test_mask).astype(np.int64), np.flatnonzero(test_mask).astype(np.int64))


def calibration_splits(y, groups, k, n_repeats=10, seed=SEED):
    """Yield (target_subject, source_idx, calib_idx, test_idx).

    source_idx = all trials of all other subjects. calib_idx = k trials of the target, k/2 per class.
    test_idx = the other trials of the target.
    Targets are visited in ascending id order. For k == 0 there is no randomness, so ONE draw is yielded per
    target (calib_idx empty). For k > 0, n_repeats draws per target, draw r uses
    np.random.default_rng([seed, target, k, r]).
    k must be even and >= 0, and each class of the target must keep at least 1 test trial.
    """
    y = np.asarray(y)
    groups = np.asarray(groups)
    if not isinstance(k, (int, np.integer)) or k < 0 or k % 2:
        raise ValueError(f"k must be an even int >= 0, got {k!r}")
    half = int(k) // 2
    for target in np.unique(groups):
        tmask = groups == target
        source_idx = np.flatnonzero(~tmask).astype(np.int64)
        tidx = np.flatnonzero(tmask)
        if k == 0:
            yield int(target), source_idx, np.zeros(0, dtype=np.int64), np.sort(tidx).astype(np.int64)
            continue
        for cls in (0, 1):
            n_cls = int(np.sum(y[tidx] == cls))
            if n_cls <= half:
                raise ValueError(f"subject {target} class {cls} has {n_cls} trials, need > {half} for k={k}")
        for r in range(n_repeats):
            rng = np.random.default_rng([int(seed), int(target), int(k), int(r)])
            calib = []
            for cls in (0, 1):
                cidx = tidx[y[tidx] == cls]
                calib.append(rng.choice(cidx, size=half, replace=False))
            calib_idx = np.sort(np.concatenate(calib)).astype(np.int64)
            test_idx = np.setdiff1d(tidx, calib_idx).astype(np.int64)
            yield int(target), source_idx, calib_idx, test_idx
