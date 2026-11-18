"""Unit checks for C1 (bci/data.py), C2 (bci/models_classical.py) and C3 (bci/evaluate.py). Ticket C4.

Fast and seeded. Everything here is additional to tests/locked/: no offline PhysioNet check, no
fresh-venv check, no leak spy, no oracle, no recovery check. Synthetic data only (SYNTHETIC - NOT VALID).
Never downloads anything.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from bci import data, evaluate, models_classical
from bci.contracts import SFREQ
from bci.synthetic import make_synthetic

REPO = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ C1: bci/data.py
def test_data_dir_honours_env_var(monkeypatch, tmp_path):
    target = tmp_path / "custom_mne_cache"
    monkeypatch.setenv("BCI_DATA_DIR", str(target))
    assert data.data_dir() == target
    assert target.is_dir(), "data_dir() must create the folder when it is missing"


def test_data_dir_default_is_inside_repo(monkeypatch):
    monkeypatch.delenv("BCI_DATA_DIR", raising=False)
    assert data.data_dir() == REPO / ".cache" / "mne_data"


def test_epochs_from_raw_rejects_non_160hz():
    import mne

    n_ch, sf = 64, 200.0  # wrong rate on purpose; the sampling-rate guard runs before any filtering
    rng = np.random.default_rng(0)
    raw = mne.io.RawArray(rng.standard_normal((n_ch, int(sf * 20))) * 1e-5,
                          mne.create_info([f"EEG{i:03d}" for i in range(n_ch)], sf, "eeg"), verbose="error")
    raw.set_annotations(mne.Annotations([2.0, 8.0], [4.1, 4.1], ["T1", "T2"]))
    with pytest.raises(ValueError, match="sampling rate"):
        data.epochs_from_raw(raw)


# ------------------------------------------------------------------ C2: bci/models_classical.py
def test_bandpass_is_stateless_and_fit_returns_self():
    bp = models_classical.BandPass(low=8.0, high=30.0, fs=SFREQ, order=4)
    rng = np.random.default_rng(1)
    X = rng.standard_normal((3, 64, 480))
    before = bp.transform(X)
    assert bp.fit(X) is bp, "fit must return self"
    after = bp.transform(X)
    np.testing.assert_array_equal(before, after)
    assert before.dtype == np.float64


def test_bandpass_attenuates_out_of_band_sine():
    bp = models_classical.BandPass(low=8.0, high=30.0, fs=SFREQ, order=4)
    t = np.arange(480) / SFREQ
    low = np.sin(2 * np.pi * 2.0 * t)   # 2 Hz: outside the csp_lda band (8-30 Hz)
    mid = np.sin(2 * np.pi * 15.0 * t)  # 15 Hz: inside the band
    X = np.stack([low, mid])[None]      # shape (1, 2, 480): band-pass acts on the last axis
    out = bp.transform(X)[0]
    std_low = out[0, 60:-60].std()      # trim filter edges
    std_mid = out[1, 60:-60].std()
    assert std_mid > 0.6, f"15 Hz sine kept only {std_mid:.3f}"
    assert std_low < 0.05 * std_mid, f"2 Hz sine leaked: {std_low:.4f} vs 15 Hz {std_mid:.4f}"


def test_csp_lda_band_is_8_to_30():
    pipe = models_classical.make_csp_lda()
    bp = pipe.named_steps["bandpass"]
    assert (bp.low, bp.high) == (8.0, 30.0)


def test_fbcsp_feature_step_gives_20_features():
    syn = make_synthetic(n_subjects=2, trials_per_subject=20, seed=11)
    X, y = syn[0], syn[1]
    est = models_classical.make_fbcsp_lr()
    features = est.named_steps["features"]
    F = features.fit_transform(X, y)
    assert F.shape == (len(X), 20), f"expected 5 bands x 4 CSP components = 20, got {F.shape}"
    assert np.all(np.isfinite(F))


# ------------------------------------------------------------------ C3: bci/evaluate.py
@pytest.mark.parametrize("fn", [evaluate.within_subject, evaluate.cross_subject])
def test_unknown_model_name_raises_keyerror(fn):
    X, y, groups, _ = make_synthetic(n_subjects=5, trials_per_subject=40, seed=3)
    with pytest.raises(KeyError):
        fn("no_such_model", X, y, groups)


def test_within_subject_per_subject_keys_are_1_to_5():
    X, y, groups, _ = make_synthetic(n_subjects=5, trials_per_subject=40, seed=3)
    block = evaluate.within_subject("csp_lda", X, y, groups)
    assert sorted(block["per_subject"], key=int) == ["1", "2", "3", "4", "5"]
    for m in block["per_subject"].values():
        assert set(m) == {"acc", "bal_acc", "kappa"}
        assert 0.0 <= m["acc"] <= 1.0
