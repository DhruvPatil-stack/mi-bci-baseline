"""Gate G1 (FROZEN): shapes, types, registry format, estimator methods, evaluator and report signatures.

v0.3: the data contract is dataset-dependent (contracts.DATASETS). Estimators must work on the stroke shape.
"""
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
    assert cfg["time_budget_min"] == 180  # v0.3: safety stop only
    assert cfg["enforce_time_budget"] is True
    assert cfg["n_permutations_subject"] == 200
    assert cfg["responder_alpha"] == 0.05
    assert cfg["erd_band_mu"] == [8, 13] and cfg["erd_band_beta"] == [13, 30]
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


# ------------------------------------------------------------------ data.py offline (no download)
def _fake_physionet_raw():
    """64-ch RawArray in VOLTS with T0/T1/T2 annotations and a known planted signal.

    T1 (left, 0): 10 Hz, 50e-6 V burst on ch 0 exactly from cue+0.5 s to cue+3.5 s.
    T2 (right, 1): the same burst on ch 1. T0 (rest): the same burst on ch 2 (must be dropped).
    Common mode: 20 Hz, 100e-6 V on every channel all the time (the average reference must remove it).
    """
    import mne

    sf = SFREQ
    n_cyc = 9
    onsets = [2.0 + 8.5 * i for i in range(n_cyc)]
    descs = ["T0", "T1", "T2"] * (n_cyc // 3)
    n = int((onsets[-1] + 6.0) * sf)
    t = np.arange(n) / sf
    rng = np.random.default_rng(0)
    data = 1e-7 * rng.standard_normal((N_CHANNELS, n)) + 100e-6 * np.sin(2 * np.pi * 20 * t)
    chan = {"T0": 2, "T1": 0, "T2": 1}
    for on, d in zip(onsets, descs):
        m = (t >= on + 0.5) & (t < on + 3.5)
        data[chan[d], m] += 50e-6 * np.sin(2 * np.pi * 10 * t[m])
    info = mne.create_info([f"EEG{i:03d}" for i in range(N_CHANNELS)], sf, "eeg")
    raw = mne.io.RawArray(data, info, verbose="error")
    raw.set_annotations(mne.Annotations(onsets, [4.1] * n_cyc, descs))
    return raw


def test_data_epochs_from_raw_offline():
    """C1 checks without a download: label map, rest drop, uV unit, 480-sample window placement, average reference."""
    data = optional_module("data")
    if data is None:
        pytest.skip("bci/data.py not on this branch")
    X, y = data.epochs_from_raw(_fake_physionet_raw())
    X, y = np.asarray(X), np.asarray(y)
    assert X.shape == (6, N_CHANNELS, N_SAMPLES), f"shape {X.shape}: expected 3 T1 + 3 T2 trials, T0 dropped"
    assert X.dtype == np.float32
    assert y.tolist() == [0, 1, 0, 1, 0, 1], f"labels {y.tolist()}: T1 must be 0 (left), T2 must be 1 (right)"
    rms = np.sqrt((X.astype(np.float64) ** 2).mean(-1))  # (trials, channels) in uV
    burst = 50.0 * 63 / 64 / np.sqrt(2)  # rms of the planted burst after the average reference, uV
    for i, lab in enumerate(y):
        ch, other = (0, 1) if lab == 0 else (1, 0)
        assert 0.75 * burst < rms[i, ch] < 1.25 * burst, f"trial {i}: burst rms {rms[i, ch]:.3g} uV, expected {burst:.3g}"
        assert rms[i, other] < 3.0
        assert rms[i, 2] < 3.0, "rest (T0) signal found in a kept trial"
        assert rms[i, 5] < 3.0, f"common-mode 20 Hz survives (rms {rms[i, 5]:.3g} uV): average reference missing"
        seg = X[i, ch].astype(np.float64)
        mid = np.sqrt((seg[200:280] ** 2).mean())
        assert np.sqrt((seg[:40] ** 2).mean()) > 0.6 * mid, "window starts before cue+0.5 s"
        assert np.sqrt((seg[-40:] ** 2).mean()) > 0.6 * mid, "window ends after cue+3.5 s"


def test_data_fallback_to_synthetic(monkeypatch):
    data = optional_module("data")
    if data is None:
        pytest.skip("bci/data.py not on this branch")
    calls = []

    def broken(subjects, runs, *a, **k):
        calls.append(1)
        raise OSError("simulated download failure")

    monkeypatch.setattr(data, "load_dataset", broken)
    monkeypatch.setattr("time.sleep", lambda s: None)
    X, y, groups, source = data.load_with_fallback([1, 2], [4, 8, 12])
    assert source == "synthetic"
    assert len(calls) == contracts.load_config()["download_attempts"]
    _check_data_contract(X, y, groups)


def test_feedback_direction(synth_small, tmp_path):
    """Class-1 (right) trials give a higher mean P(right) than class-0 trials."""
    fb = optional_module("feedback_sim")
    mc = optional_module("models_classical")
    if fb is None or mc is None:
        pytest.skip("needs feedback_sim.py and models_classical.py")
    X, y, groups = synth_small
    est = mc.REGISTRY["csp_lda"]().fit(X[:160], y[:160])
    means = {0: [], 1: []}
    for i in range(160, 200):
        _, p = fb.simulate_feedback(est, X[i], SFREQ, str(tmp_path / f"fb{i}.png"))
        means[int(y[i])].append(float(np.mean(p)))
    assert np.mean(means[1]) > np.mean(means[0]), "feedback P(right) is not higher for right-hand trials"

# ------------------------------------------------------------------ v0.3 dataset contract
def test_datasets_contract():
    assert contracts.DATASETS["physionet"] == {"n_channels": 64, "sfreq": 160, "n_samples": 480}
    st = contracts.DATASETS["stroke"]
    cfg = contracts.load_config()["stroke"]
    assert st["sfreq"] == cfg["sfreq"] == 500
    assert st["n_channels"] == cfg["n_eeg_channels"] == 29
    w = cfg["window"]
    assert int(round((w["tmax"] - w["tmin"]) * st["sfreq"])) + 1 == st["n_samples"] == 1500
    assert cfg["label_map"] == {1: 0, 2: 1}
    assert "stroke" in contracts.DATA_SOURCES


def test_dataset_selection_by_env(monkeypatch):
    monkeypatch.delenv(contracts.DATASET_ENV, raising=False)
    assert contracts.dataset_name() == "physionet"
    assert contracts.dataset_spec()["sfreq"] == 160
    monkeypatch.setenv(contracts.DATASET_ENV, "stroke")
    assert contracts.dataset_spec()["sfreq"] == 500
    monkeypatch.setenv(contracts.DATASET_ENV, "nope")
    with pytest.raises(ValueError):
        contracts.dataset_spec()


def test_validate_data():
    X = np.zeros((4, 64, 480), np.float32)
    y = np.array([0, 1, 0, 1])
    g = np.array([1, 1, 2, 2])
    contracts.validate_data(X, y, g, "physionet")
    for bad in (X.astype(np.float64), X[:, :63], X[:, :, :479]):
        with pytest.raises(ValueError):
            contracts.validate_data(bad, y, g, "physionet")
    with pytest.raises(ValueError):
        contracts.validate_data(X, np.array([0, 1, 2, 1]), g, "physionet")
    with pytest.raises(ValueError):
        contracts.validate_data(X, y, g, "stroke")
    contracts.validate_data(np.zeros((4, 29, 1500), np.float32), y, g, "stroke")


def test_enforce_time_budget_env(monkeypatch):
    monkeypatch.delenv(contracts.ENFORCE_ENV, raising=False)
    assert contracts.enforce_time_budget() is True
    monkeypatch.setenv(contracts.ENFORCE_ENV, "0")
    assert contracts.enforce_time_budget() is False
    monkeypatch.setenv(contracts.ENFORCE_ENV, "1")
    assert contracts.enforce_time_budget() is True


def _stroke_shaped(n=60, seed=3):
    """Random data in the stroke shape with a planted 10 Hz ERD on channels 13 (C3) and 14 (C4)."""
    spec = contracts.DATASETS["stroke"]
    rng = np.random.default_rng(seed)
    t = np.arange(spec["n_samples"]) / spec["sfreq"]
    y = np.repeat([0, 1], n // 2)
    X = 10.0 * rng.standard_normal((n, spec["n_channels"], spec["n_samples"]))
    for i, lab in enumerate(y):
        for ch, cls in ((14, 0), (13, 1)):  # left (0) desynchronizes C4, right (1) desynchronizes C3
            amp = 30.0 * (np.sqrt(0.3) if lab == cls else 1.0)
            X[i, ch] += amp * np.sin(2 * np.pi * 10 * t + rng.uniform(0, 2 * np.pi))
    return X.astype(np.float32), y.astype(np.int64)


@pytest.mark.parametrize("name", _model_names() or ["<none>"])
def test_estimators_work_on_stroke_shape(name, monkeypatch):
    """S3 / PRD_v0.3 section 7 item 2: no estimator may assume 64 channels or 160 Hz."""
    if name == "<none>":
        pytest.skip("no model module on this branch")
    from conftest import current_branch, model_owner_prefixes

    branch = current_branch()
    owners = model_owner_prefixes(name) + ("integration/v0.3",)
    if not any(branch.startswith(p) for p in owners):
        pytest.skip(f"{name} is the work of {owners}; not checked on {branch}")
    monkeypatch.setenv(contracts.DATASET_ENV, "stroke")
    X, y = _stroke_shaped()
    est = all_registries()[name]()
    # every sampling-rate parameter of the estimator must be the stroke rate
    for key, val in est.get_params(deep=True).items():
        leaf = key.split("__")[-1]
        if leaf in ("fs", "sfreq", "sampling_rate", "srate"):
            assert val == 500, f"{name}: parameter {key} = {val}, expected the dataset sfreq 500"
    tr = np.r_[0:24, 30:54]
    te = np.r_[24:30, 54:60]
    est.fit(X[tr], y[tr])
    proba = np.asarray(est.predict_proba(X[te]))
    assert proba.shape == (len(te), 2)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)


def test_classical_sfreq_follows_dataset(monkeypatch):
    """BandPass must take the sampling rate from the active dataset, not from the PhysioNet constant."""
    from conftest import required_module

    mc = required_module("models_classical", ("claude/",))
    for ds, fs in (("physionet", 160), ("stroke", 500)):
        monkeypatch.setenv(contracts.DATASET_ENV, ds)
        for name in ("csp_lda", "fbcsp_lr"):
            params = mc.REGISTRY[name]().get_params(deep=True)
            fss = [v for k, v in params.items() if k.split("__")[-1] == "fs"]
            assert fss and all(v == fs for v in fss), f"{name} on {ds}: fs values {fss}, expected {fs}"
