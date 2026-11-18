"""Gate G2 (FROZEN): no subject or trial leaks between train and test.

Part A checks splits.py directly. Part B wraps a spy estimator into the registry and runs evaluate.py:
the spy reads the row id planted in X[:, 0, 0] and fails if any predicted row was in its fit set.
"""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.base import BaseEstimator, ClassifierMixin

from bci import contracts
from bci.splits import calibration_splits, cross_subject_splits, within_subject_splits
from conftest import id_tagged, optional_module


def _realistic_groups(seed=0):
    """20 subjects, 44-46 trials each, unequal class counts (like PhysioNet runs 4, 8, 12)."""
    rng = np.random.default_rng(seed)
    ys, gs = [], []
    for s in range(1, 21):
        n = int(rng.integers(44, 47))
        n0 = n // 2 + int(rng.integers(-1, 2))
        y = rng.permutation(np.r_[np.zeros(n0, int), np.ones(n - n0, int)])
        ys.append(y)
        gs.append(np.full(n, s))
    return np.concatenate(ys), np.concatenate(gs)


def _cases(synth):
    X, y, groups, _ = synth
    yield "synthetic", y, groups
    yield "realistic", *_realistic_groups()


# ------------------------------------------------------------------ Part A: splits.py
def test_within_subject_splits(synth):
    for label, y, groups in _cases(synth):
        seen = np.zeros(len(y), int)
        for sid, tr, te in within_subject_splits(y, groups):
            assert np.intersect1d(tr, te).size == 0, label
            assert set(np.unique(groups[tr])) == {sid} and set(np.unique(groups[te])) == {sid}, label
            assert set(np.unique(y[te])) == {0, 1}, f"{label}: test fold not stratified"
            seen[te] += 1
        assert np.all(seen == 1), f"{label}: each trial must be tested exactly once"


def test_cross_subject_splits(synth):
    for label, y, groups in _cases(synth):
        tested = []
        for tr, te in cross_subject_splits(groups):
            assert np.intersect1d(tr, te).size == 0
            assert set(groups[tr]).isdisjoint(set(groups[te])), f"{label}: subject in train and test"
            assert len(tr) + len(te) == len(groups)
            tested.extend(np.unique(groups[te]).tolist())
        assert sorted(tested) == sorted(np.unique(groups).tolist()), f"{label}: each subject tested once"


def test_calibration_splits(synth):
    ks = contracts.load_config()["calibration_k"]
    for label, y, groups in _cases(synth):
        for k in ks:
            n_draws = {}
            for target, src, cal, te in calibration_splits(y, groups, k):
                tmask = groups == target
                assert np.array_equal(np.sort(src), np.flatnonzero(~tmask)), f"{label}: source != other subjects"
                assert np.all(groups[cal] == target) and np.all(groups[te] == target)
                assert np.intersect1d(cal, te).size == 0, f"{label} k={k}: calib trial in test set"
                assert np.intersect1d(src, te).size == 0
                assert np.array_equal(np.sort(np.r_[cal, te]), np.flatnonzero(tmask))
                assert len(cal) == k
                assert np.sum(y[cal] == 0) == k // 2 and np.sum(y[cal] == 1) == k // 2
                n_draws[target] = n_draws.get(target, 0) + 1
            expected = 1 if k == 0 else 10
            assert set(n_draws.values()) == {expected}, f"{label} k={k}: draws per target {set(n_draws.values())}"
    with pytest.raises(ValueError):
        list(calibration_splits(y, groups, 3))


def test_splits_are_deterministic(synth):
    _, y, groups, _ = synth
    a = [te.tolist() for _, _, te in within_subject_splits(y, groups)]
    b = [te.tolist() for _, _, te in within_subject_splits(y, groups)]
    assert a == b
    a = [c.tolist() for _, _, c, _ in calibration_splits(y, groups, 8)]
    b = [c.tolist() for _, _, c, _ in calibration_splits(y, groups, 8)]
    assert a == b


# ------------------------------------------------------------------ Part B: evaluate.py with a spy
LOG: list = []
REF = {}  # "X": the id-tagged X given to evaluate, "y": true labels, "groups"


class Spy(BaseEstimator, ClassifierMixin):
    def fit(self, X, y):
        ids = np.asarray(X)[:, 0, 0].astype(np.int64)
        if not np.array_equal(np.asarray(X, dtype=np.float32), REF["X"][ids]):
            raise AssertionError("evaluate changed X before fit: all preprocessing must live inside the estimator")
        self.fit_ids_ = set(ids.tolist())
        LOG.append(("fit", ids, np.asarray(y).copy()))
        self.classes_ = np.array([0, 1])
        return self

    def _check(self, X):
        ids = np.asarray(X)[:, 0, 0].astype(np.int64)
        if not np.array_equal(np.asarray(X, dtype=np.float32), REF["X"][ids]):
            raise AssertionError("evaluate changed X before predict: all preprocessing must live inside the estimator")
        overlap = self.fit_ids_ & set(ids.tolist())
        if overlap:
            raise AssertionError(f"LEAK: {len(overlap)} test rows were in the fit set, e.g. {sorted(overlap)[:5]}")
        LOG.append(("predict", ids, None))
        return ids

    def predict(self, X):
        ids = self._check(X)
        return (ids % 2).astype(int)

    def predict_proba(self, X):
        ids = self._check(X)
        p = (ids % 2).astype(float) * 0.6 + 0.2
        return np.c_[1 - p, p]


@pytest.fixture()
def spy_env(monkeypatch, synth_small):
    ev = optional_module("evaluate")
    mc = optional_module("models_classical")
    if ev is None or mc is None:
        pytest.skip("needs evaluate.py and models_classical.py")
    monkeypatch.setitem(mc.REGISTRY, "spy", Spy)
    monkeypatch.setitem(mc.REGISTRY, "oracle", Oracle)
    LOG.clear()
    X, y, groups = synth_small
    Xt = id_tagged(X)
    REF.update(X=Xt, y=np.asarray(y), groups=np.asarray(groups))
    return ev, Xt, y, groups


def _pairs():
    """Group LOG into (fit_ids, fit_y, [predict_ids...]) in call order."""
    out = []
    for kind, ids, yy in LOG:
        if kind == "fit":
            out.append([ids, yy, []])
        else:
            assert out, "predict before any fit"
            out[-1][2].append(ids)
    return out


def test_evaluate_within_no_leak(spy_env):
    ev, X, y, groups = spy_env
    ev.within_subject("spy", X, y, groups)
    pairs = _pairs()
    assert len(pairs) >= len(np.unique(groups)) * contracts.load_config()["n_splits"]
    for fit_ids, _, preds in pairs:
        subj = set(groups[fit_ids].tolist())
        assert len(subj) == 1, f"within-subject fit used subjects {subj}"
        for p in preds:
            assert set(groups[p].tolist()) == subj


def test_evaluate_cross_no_leak(spy_env):
    ev, X, y, groups = spy_env
    ev.cross_subject("spy", X, y, groups)
    for fit_ids, _, preds in _pairs():
        for p in preds:
            assert set(groups[fit_ids].tolist()).isdisjoint(set(groups[p].tolist())), "subject in train and test"


def test_evaluate_permutation_shuffles_only_inside_sets(spy_env):
    ev, X, y, groups = spy_env
    ev.permutation_control("spy", X, y, groups)
    pairs = _pairs()
    assert pairs
    changed = 0
    for fit_ids, fit_y, preds in pairs:
        assert sorted(fit_y.tolist()) == sorted(y[fit_ids].tolist()), "labels must be shuffled inside the train set"
        changed += int(not np.array_equal(fit_y, y[fit_ids]))
        for p in preds:
            assert not set(fit_ids.tolist()) & set(p.tolist())
    assert changed >= len(pairs) // 2, "permutation_control did not shuffle the training labels"


def test_evaluate_calibration_no_leak(spy_env):
    ev, X, y, groups = spy_env
    ev.calibration_curve("spy", X, y, groups)
    pairs = _pairs()
    assert pairs
    for fit_ids, _, preds in pairs:
        for p in preds:
            tsub = set(groups[p].tolist())
            assert len(tsub) == 1, "calibration test set must be one target subject"
            (target,) = tsub
            n_target_in_fit = int(np.sum(groups[fit_ids] == target))
            assert n_target_in_fit in contracts.load_config()["calibration_k"], (
                f"fit holds {n_target_in_fit} target trials, not a k value")


class Oracle(Spy):
    """Predicts the TRUE label of a row if its subject was in the fit set, else the WRONG label.

    So a correct evaluator reports: within 1.0, cross 0.0, calibration source_plus_target 0.0 at k = 0 and
    1.0 at k > 0, target_only 1.0 at k > 0. Any other value means the curves or folds use the wrong sets.
    """

    def fit(self, X, y):
        super().fit(X, y)
        self.fit_subjects_ = set(REF["groups"][sorted(self.fit_ids_)].tolist())
        return self

    def predict(self, X):
        ids = self._check(X)
        seen = np.isin(REF["groups"][ids], list(self.fit_subjects_))
        true = REF["y"][ids]
        return np.where(seen, true, 1 - true).astype(int)

    def predict_proba(self, X):
        p = self.predict(X).astype(float) * 0.8 + 0.1
        return np.c_[1 - p, p]


def test_oracle_within_and_cross(spy_env):
    ev, X, y, groups = spy_env
    w = ev.within_subject("oracle", X, y, groups)
    assert np.isclose(w["mean_bal_acc"], 1.0), f"within oracle mean {w['mean_bal_acc']}"
    c = ev.cross_subject("oracle", X, y, groups)
    assert np.isclose(c["mean_bal_acc"], 0.0), f"cross oracle mean {c['mean_bal_acc']} (a test subject was in train?)"


def test_oracle_calibration_curves(spy_env):
    ev, X, y, groups = spy_env
    cal = ev.calibration_curve("oracle", X, y, groups)
    for k, spt, to in zip(cal["k"], cal["source_plus_target"], cal["target_only"]):
        if k == 0:
            assert np.isclose(spt, 0.0), f"k=0 source-only curve {spt}: target trials reached the fit"
            assert to is None
        else:
            assert np.isclose(spt, 1.0), f"k={k} source_plus_target {spt}: calib trials missing from the fit"
            assert np.isclose(to, 1.0), f"k={k} target_only {to}"