"""Gate G3 (FROZEN): models find the planted ERD; permuted labels give chance.

Scores here come from this file's own loop over splits.cross_subject_splits (it does not trust evaluate.py),
and, when evaluate.py exists, from evaluate.permutation_control as well.
Data: synthetic.make_synthetic() defaults (8 subjects x 40 trials, seed 42).
Why cross-subject: with 64 channels and 32 training trials, CSP noise eigenvalues (about 0.31-0.37) overlap the
planted one (1/3 at infinite SNR for a 50 % power drop), so within-subject recovery is not a fair test of a
correct model. Pooled training sets (about 256 trials) recover the planted ERD. See .sync/LOG.md (Phase 0).
"""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold

from bci.contracts import SEED
from bci.splits import cross_subject_splits
from conftest import all_registries, optional_module

N_PERM = 5  # permutation repeats: 5 x 320 test trials -> chance-level sd about 0.0125
RECOVERY = {"csp_lda": 0.85, "ts_lr": 0.85, "fbcsp_lr": 0.80}  # fbcsp_lr: Head-chef probe measured 0.863
EEGNET_MIN = 0.70


def _cross_score(name, X, y, groups, permute_seed=None):
    reg = all_registries()
    y_true, y_pred = [], []
    rng = np.random.default_rng(permute_seed) if permute_seed is not None else None
    for tr, te in cross_subject_splits(groups):
        ytr, yte = y[tr].copy(), y[te].copy()
        if rng is not None:
            ytr, yte = rng.permutation(ytr), rng.permutation(yte)
        est = reg[name]().fit(X[tr], ytr)
        y_true.append(yte)
        y_pred.append(est.predict(X[te]))
    return balanced_accuracy_score(np.concatenate(y_true), np.concatenate(y_pred))


@pytest.mark.parametrize("name", sorted(RECOVERY))
def test_recovers_planted_erd(name, synth):
    if name not in all_registries():
        pytest.skip(f"{name} not on this branch")
    X, y, groups, _ = synth
    score = _cross_score(name, X, y, groups)
    assert score > RECOVERY[name], f"{name} cross-subject bal_acc {score:.3f} <= {RECOVERY[name]}"


@pytest.mark.parametrize("name", sorted(RECOVERY))
def test_permuted_labels_give_chance(name, synth):
    if name not in all_registries():
        pytest.skip(f"{name} not on this branch")
    X, y, groups, _ = synth
    scores = [_cross_score(name, X, y, groups, permute_seed=SEED + r) for r in range(N_PERM)]
    m = float(np.mean(scores))
    assert abs(m - 0.5) <= 0.05, f"{name} permuted bal_acc {m:.3f} not in 0.50 +/- 0.05 (leak?)"


@pytest.mark.slow
def test_eegnet_recovers(synth):
    """X1 done-condition: eegnet_lite > 0.70 on synthetic data (pooled stratified 5-fold, 256 train trials)."""
    if "eegnet_lite" not in all_registries():
        pytest.skip("eegnet_lite not on this branch")
    X, y, groups, _ = synth
    yt, yp = [], []
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y):
        est = all_registries()["eegnet_lite"]().fit(X[tr], y[tr])
        yt.append(y[te])
        yp.append(est.predict(X[te]))
    score = balanced_accuracy_score(np.concatenate(yt), np.concatenate(yp))
    assert score > EEGNET_MIN, f"eegnet_lite bal_acc {score:.3f} <= {EEGNET_MIN}"


def test_label_map_not_swapped(synth):
    """Planted map: class 0 has less 10 Hz power on channel 0, class 1 on channel 1."""
    from scipy.signal import welch

    X, y, _, truth = synth
    f, P = welch(X[:, :2, :], fs=160, nperseg=160, axis=-1)
    p10 = P[:, :, np.argmin(np.abs(f - 10))]
    assert p10[y == 0, 0].mean() < p10[y == 1, 0].mean()
    assert p10[y == 1, 1].mean() < p10[y == 0, 1].mean()


def test_csp_top_filter_on_planted_channels(synth):
    """C2 physical check: the top CSP filters of csp_lda put the most weight on channels 0 and 1."""
    mc = optional_module("models_classical")
    if mc is None:
        pytest.skip("models_classical.py not on this branch")
    X, y, groups, _ = synth
    pipe = mc.REGISTRY["csp_lda"]().fit(X, y)
    csp = pipe.named_steps["csp"]
    W = np.asarray(csp.filters_)
    assert W.ndim == 2 and W.shape[1] == 64, f"filters_ shape {W.shape}, rows must be filters over 64 channels"
    tops = {int(np.argmax(np.abs(W[i]))) for i in (0, 1)}
    assert tops <= {0, 1}, f"top-2 CSP filters peak on channels {tops}, expected within {{0, 1}}"


def test_ts_identity_maps_to_zero(synth_small):
    """X1 physical check: tangent vector of I with C_ref = I is all zeros."""
    ma = optional_module("models_advanced")
    if ma is None:
        pytest.skip("models_advanced.py not on this branch")
    from pyriemann.tangentspace import TangentSpace

    X, y, _ = synth_small
    pipe = ma.REGISTRY["ts_lr"]().fit(X[:160], y[:160])
    steps = pipe.named_steps.values() if hasattr(pipe, "named_steps") else [pipe]
    ts = [s for s in steps if isinstance(s, TangentSpace)]
    assert ts, "ts_lr pipeline has no pyriemann TangentSpace step"
    ts = ts[0]
    ts.reference_ = np.eye(64)
    v = ts.transform(np.eye(64)[None])
    assert np.allclose(v, 0.0, atol=1e-10)


def test_evaluate_permutation_control_chance(synth):
    ev = optional_module("evaluate")
    if ev is None:
        pytest.skip("evaluate.py not on this branch")
    X, y, groups, _ = synth
    p = ev.permutation_control("csp_lda", X, y, groups)
    for key in ("within_mean_bal_acc", "cross_mean_bal_acc"):
        assert abs(p[key] - 0.5) <= 0.05, f"evaluate.permutation_control {key} = {p[key]:.3f}"


def test_evaluate_cross_recovers(synth):
    ev = optional_module("evaluate")
    if ev is None:
        pytest.skip("evaluate.py not on this branch")
    X, y, groups, _ = synth
    c = ev.cross_subject("csp_lda", X, y, groups)
    assert c["mean_bal_acc"] > 0.85, f"evaluate.cross_subject csp_lda mean {c['mean_bal_acc']:.3f}"
