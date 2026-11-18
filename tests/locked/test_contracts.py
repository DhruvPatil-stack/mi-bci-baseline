"""Gate G1 (FROZEN): shapes, types, registry format, estimator methods, evaluator and report signatures."""
from __future__ import annotations

import inspect
import os

import numpy as np
import pytest
from sklearn.base import clone

from bci import contracts
from bci.contracts import N_CHANNELS, N_SAMPLES, SFREQ
from conftest import all_registries, optional_module


# ------------------------------------------------------------------ frozen constants
def test_constants():
    assert contracts.SEED == 42
    assert contracts.SFREQ == 160
    assert contracts.N_CHANNELS == 64
    assert contracts.N_SAMPLES == 480
    assert contracts.LABELS == {0: "left", 1: "right"}


def test_config_window_gives_480_samples():
    cfg = contracts.load_config()
    w = cfg["window"]
    n = int(round((w["tmax"] - w["tmin"]) * SFREQ)) + 1  # MNE includes the end point
    assert n == N_SAMPLES
    assert cfg["event_map"] == {"T1": 0, "T2": 1}
    assert cfg["runs"] == [4, 8, 12]
    assert cfg["subjects"] == list(range(1, 21))
    assert cfg["csp_components"] == 6
    assert cfg["calibration_k"] == [0, 4, 8, 16, 24]
    assert cfg["calibration_models"] == ["csp_lda", "fbcsp_lr", "ts_lr"]
    assert cfg["fbcsp_bands"] == [[8, 12], [12, 16], [16, 20], [20, 24], [24, 30]]
    assert cfg["time_budget_min"] == 40
    assert cfg["feedback_model"] == "csp_lda"


def test_synthetic_contract(synth):
    X, y, groups, truth = synth
    assert X.shape == (8 * 40, N_CHANNELS, N_SAMPLES)
    assert X.dtype == np.float32
    assert set(np.unique(y)) == {0, 1}
    assert len(np.unique(groups)) == 8
    med = float(np.median(np.abs(X)))
    assert 1.0 < med < 100.0, f"median |X| = {med} uV"
    assert truth["erd_channel_by_class"] == {0: 0, 1: 1}


# ------------------------------------------------------------------ data.py (Claude)
def _check_data_contract(X, y, groups):
    assert X.ndim == 3 and X.shape[1:] == (N_CHANNELS, N_SAMPLES), X.shape
    assert X.dtype == np.float32
    assert np.issubdtype(np.asarray(y).dtype, np.integer)
    assert set(np.unique(y)) <= {0, 1}
    assert len(y) == len(X) == len(groups)


def test_data_module_signature():
    data = optional_module("data")
    if data is None:
        pytest.skip("bci/data.py not on this branch")
    assert callable(data.load_dataset)
    assert list(inspect.signature(data.load_dataset).parameters)[:2] == ["subjects", "runs"]
    assert callable(data.load_with_fallback)
    assert list(inspect.signature(data.load_with_fallback).parameters)[:2] == ["subjects", "runs"]


@pytest.mark.real
def test_data_real_subject():
    """C1 physical check on real data. Needs the download: set BCI_REAL_DATA=1."""
    if os.environ.get("BCI_REAL_DATA") != "1":
        pytest.skip("set BCI_REAL_DATA=1 to run the PhysioNet check")
    data = optional_module("data")
    if data is None:
        pytest.skip("bci/data.py not on this branch")
    X, y, groups = data.load_dataset([1, 2], [4, 8, 12])
    _check_data_contract(X, y, groups)
    assert set(np.unique(y)) == {0, 1}
    assert set(np.unique(groups)) == {1, 2}
    for s in (1, 2):
        n = int(np.sum(groups == s))
        assert 40 <= n <= 50, f"subject {s} has {n} trials, expected about 45"
    med = float(np.median(np.abs(X)))
    assert 1.0 <= med <= 100.0, f"median |X| = {med}; a value near 1e-5 means the uV conversion is missing"


# ------------------------------------------------------------------ registries
EXPECTED = {"models_classical": set(contracts.CLASSICAL_MODELS), "models_advanced": set(contracts.ADVANCED_MODELS)}


@pytest.mark.parametrize("mod_name", sorted(EXPECTED))
def test_registry_format(mod_name):
    mod = optional_module(mod_name)
    if mod is None:
        pytest.skip(f"bci/{mod_name}.py not on this branch")
    reg = mod.REGISTRY
    assert isinstance(reg, dict)
    assert set(reg) == EXPECTED[mod_name], f"{mod_name}.REGISTRY keys {set(reg)}"
    for name, factory in reg.items():
        assert callable(factory)
        assert len(inspect.signature(factory).parameters) == 0, f"{name} factory must take no argument"
        a, b = factory(), factory()
        assert a is not b, f"{name} factory must return a new estimator each call"


def _model_names():
    return sorted(all_registries())


@pytest.mark.parametrize("name", _model_names() or ["<none>"])
def test_estimator_methods(name, synth_small):
    if name == "<none>":
        pytest.skip("no model module on this branch")
    X, y, groups = synth_small
    est = all_registries()[name]()
    clone(est)  # scikit-learn estimator contract
    for m in ("fit", "predict", "predict_proba"):
        assert callable(getattr(est, m, None)), f"{name} lacks {m}"
    tr, te = np.arange(0, 160), np.arange(160, 200)
    assert est.fit(X[tr], y[tr]) is not None
    pred = np.asarray(est.predict(X[te]))
    assert pred.shape == (len(te),)
    assert set(np.unique(pred)) <= {0, 1}
    proba = np.asarray(est.predict_proba(X[te]))
    assert proba.shape == (len(te), 2)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)
    assert np.all((proba >= 0) & (proba <= 1))
    assert np.array_equal(pred, (proba[:, 1] > 0.5).astype(int)) or np.array_equal(pred, proba.argmax(1))


# ------------------------------------------------------------------ evaluate.py (Claude)
def test_evaluate_blocks_follow_schema(synth_small):
    ev = optional_module("evaluate")
    if ev is None:
        pytest.skip("bci/evaluate.py not on this branch")
    X, y, groups = synth_small
    for fn in ("within_subject", "cross_subject", "permutation_control", "calibration_curve"):
        assert list(inspect.signature(getattr(ev, fn)).parameters)[:4] == ["name", "X", "y", "groups"]
    w = ev.within_subject("csp_lda", X, y, groups)
    contracts.validate_within(w)
    assert set(w["per_subject"]) == {str(s) for s in np.unique(groups)} or \
        set(map(int, w["per_subject"])) == set(np.unique(groups).tolist())
    vals = [m["bal_acc"] for m in w["per_subject"].values()]
    assert np.isclose(w["mean_bal_acc"], np.mean(vals))
    assert np.isclose(w["std_bal_acc"], np.std(vals, ddof=contracts.load_config()["std_ddof"]))
    c = ev.cross_subject("csp_lda", X, y, groups)
    contracts.validate_cross(c)
    assert len(c["per_fold"]) == contracts.load_config()["n_splits"]
    fv = [f["bal_acc"] for f in c["per_fold"]]
    assert np.isclose(c["mean_bal_acc"], np.mean(fv))
    contracts.validate_permutation(ev.permutation_control("csp_lda", X, y, groups))
    cal = ev.calibration_curve("csp_lda", X, y, groups)
    contracts.validate_calibration(cal)
    assert cal["k"] == contracts.load_config()["calibration_k"]


# ------------------------------------------------------------------ Codex modules
def test_report_signature():
    rep = optional_module("report")
    if rep is None:
        pytest.skip("bci/report.py not on this branch")
    assert list(inspect.signature(rep.write_report).parameters)[:2] == ["results_path", "out_dir"]
    assert callable(rep.compute_stats)


def test_feedback_signature():
    fb = optional_module("feedback_sim")
    if fb is None:
        pytest.skip("bci/feedback_sim.py not on this branch")
    params = list(inspect.signature(fb.simulate_feedback).parameters)
    assert params[:4] == ["estimator", "trial", "sfreq", "out_png"]


def test_feedback_runs(synth_small, tmp_path):
    fb = optional_module("feedback_sim")
    mc = optional_module("models_classical")
    if fb is None or mc is None:
        pytest.skip("needs feedback_sim.py and models_classical.py")
    X, y, groups = synth_small
    est = mc.REGISTRY["csp_lda"]().fit(X[:160], y[:160])
    out = tmp_path / "fb.png"
    times, p = fb.simulate_feedback(est, X[180], SFREQ, str(out))
    times, p = np.asarray(times), np.asarray(p)
    assert out.exists() and out.stat().st_size > 0
    # 3 s trial, 1 s window, 0.25 s step -> 9 windows
    assert len(times) == len(p) == 9
    assert np.all(np.diff(times) > 0) and times.max() <= N_SAMPLES / SFREQ
    assert np.all((p >= 0) & (p <= 1))
