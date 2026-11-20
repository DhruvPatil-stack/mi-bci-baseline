"""Gate G11 (FROZEN, v0.3): the responder rule (PRD_v0.3 section 4, ANALYSIS CONTRACT in bci/contracts.py).

A planted-ERD subject is flagged. At most 2 of 10 pure-noise subjects are flagged. The p-value formula uses
">=" and (1 + n_perm) in the denominator. obs is the same within-subject CV as evaluate (splits.py, SEED).
The test model is conftest.LogVarLDA (fast); the rule does not depend on the model.
bci/analysis.py is required on codex/heterogeneity and integration/v0.3.
"""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import balanced_accuracy_score

from bci import contracts
from bci.splits import within_subject_splits
from bci.synthetic import make_synthetic
from conftest import LogVarLDA, required_module

OWNERS = ("codex/",)
CFG = contracts.load_config()
N_PERM = CFG["n_permutations_subject"]
ALPHA = CFG["responder_alpha"]


@pytest.fixture()
def an():
    return required_module("analysis", OWNERS)


def _planted():
    X, y, _, _ = make_synthetic(n_subjects=1, trials_per_subject=60, seed=11)
    return X, y


def _own_obs(X, y):
    g = np.ones(len(y), dtype=np.int64)
    yt, yp = [], []
    for _, tr, te in within_subject_splits(y, g, n_splits=CFG["n_splits"], seed=contracts.SEED):
        yt.append(y[te])
        yp.append(LogVarLDA().fit(X[tr], y[tr]).predict(X[te]))
    return balanced_accuracy_score(np.concatenate(yt), np.concatenate(yp))


def test_planted_subject_is_flagged(an):
    X, y = _planted()
    r = an.subject_pvalue(LogVarLDA, X, y, N_PERM, contracts.SEED)
    assert len(r["null"]) == N_PERM
    assert abs(r["obs"] - _own_obs(X, y)) < 1e-12, f"obs {r['obs']} is not the within-subject CV score"
    assert r["p"] < ALPHA, f"planted ERD subject p = {r['p']} (obs {r['obs']:.3f}) not < {ALPHA}"
    assert abs(r["p"] - (1 + sum(v >= r["obs"] for v in r["null"])) / (1 + N_PERM)) < 1e-12, "p formula"
    m = float(np.mean(r["null"]))
    assert abs(m - 0.5) < 0.05, f"null mean {m:.3f}: the null labels are not shuffled"


def test_noise_subjects_rarely_flagged(an):
    flagged = 0
    for s in range(10):
        rng = np.random.default_rng([contracts.SEED, 500, s])
        X = (10.0 * rng.standard_normal((40, 4, 480))).astype(np.float32)
        y = rng.permutation(np.repeat([0, 1], 20)).astype(np.int64)
        r = an.subject_pvalue(LogVarLDA, X, y, N_PERM, contracts.SEED + s)
        k = r["p"] * (1 + N_PERM)
        assert abs(k - round(k)) < 1e-9 and 1 <= round(k) <= 1 + N_PERM, f"p = {r['p']} is not j / {1 + N_PERM}"
        flagged += int(r["p"] < ALPHA)
    assert flagged <= 2, f"{flagged} of 10 pure-noise subjects flagged (expected about {ALPHA * 10})"


class _Constant(LogVarLDA):
    def predict(self, X):
        return np.zeros(len(X), dtype=int)


def test_ties_count_against_the_subject(an):
    """A model that always predicts class 0: obs = 0.5 and every null = 0.5, so p = 1 (ties use >=)."""
    X, y = _planted()
    r = an.subject_pvalue(_Constant, X, y, 20, contracts.SEED)
    assert r["obs"] == 0.5 and all(v == 0.5 for v in r["null"])
    assert r["p"] == 1.0, f"p = {r['p']}; ties must count as null >= obs"


def test_subject_pvalue_is_seeded(an):
    X, y = _planted()
    a = an.subject_pvalue(LogVarLDA, X, y, 30, 7)
    b = an.subject_pvalue(LogVarLDA, X, y, 30, 7)
    assert a == b


def test_classify_responders(an):
    from scipy.stats import binomtest

    pv = {"1": 0.004975, "2": 0.05, "3": 0.2, "4": 0.01}
    r = an.classify_responders(pv, ALPHA)
    assert r["flags"] == {"1": True, "2": False, "3": False, "4": True}, "flag must be p < alpha (strict)"
    assert r["count"] == 2 and r["n"] == 4
    ci = binomtest(2, 4).proportion_ci(confidence_level=0.95, method="exact")
    assert abs(r["ci95"][0] - ci.low) < 1e-9 and abs(r["ci95"][1] - ci.high) < 1e-9, "not Clopper-Pearson"
    assert abs(r["expected_false_positives"] - ALPHA * 4) < 1e-12


def test_calibration_gain_by_group(an):
    k = [0, 4, 8]
    spt = {"1": [0.60, 0.70, 0.75], "2": [0.62, 0.70, 0.79],   # responders: gains 0.08/0.10 and 0.13/0.17
           "3": [0.50, 0.52, 0.50], "4": [0.48, 0.50, 0.48]}   # non-responders: gains 0.02 and 0.00
    per_target = [{sid: {"source_plus_target": v[i], "target_only": None if i == 0 else 0.5}
                   for sid, v in spt.items()} for i in range(len(k))]
    flags = {"1": True, "2": True, "3": False, "4": False}
    r = an.calibration_gain_by_group(per_target, flags, k, n_boot=2000, seed=contracts.SEED)
    assert r["k"] == k and r["n_responders"] == 2 and r["n_non_responders"] == 2
    exp_r = [0.0, np.mean([0.10, 0.08]), np.mean([0.15, 0.17])]
    exp_n = [0.0, 0.02, np.mean([0.0, 0.0])]
    assert np.allclose(r["responders"], exp_r) and np.allclose(r["non_responders"], exp_n)
    assert np.allclose(r["diff"], np.array(exp_r) - np.array(exp_n)), "diff must be responders - non_responders"
    for d, (lo, hi) in zip(r["diff"], r["diff_ci95"]):
        assert lo - 1e-12 <= d <= hi + 1e-12
    assert r["diff_ci95"][0] == [0.0, 0.0] or np.allclose(r["diff_ci95"][0], 0.0)
    empty = an.calibration_gain_by_group(per_target, {s: True for s in flags}, k, n_boot=100, seed=0)
    assert all(v is None for v in empty["non_responders"]), "an empty group must give None"
