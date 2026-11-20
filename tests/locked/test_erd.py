"""Gate G12 (FROZEN, v0.3): ERD lateralization sign and units (ERD CONTRACT in bci/contracts.py), and the
channel map (bci/channels.py, evidence in docs/DECISIONS.md).

Synthetic data (bci/synthetic.py): class 0 (left) desynchronizes channel 0, class 1 (right) desynchronizes
channel 1. Right-hand imagery lowers mu power at C3, so channel 1 plays C3 and channel 0 plays C4: LS < 0.
Swapping C3 and C4 flips the sign. bci/erd_check.py is required on codex/heterogeneity and integration/v0.3.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from bci import channels, contracts
from conftest import required_module

OWNERS = ("codex/",)
MU = contracts.load_config()["erd_band_mu"]


@pytest.fixture()
def erd():
    return required_module("erd_check", OWNERS)


def test_channel_map():
    assert channels.PHYSIONET_CHANNELS[channels.CH_C3] == "C3"
    assert channels.PHYSIONET_CHANNELS[channels.CH_CZ] == "Cz"
    assert channels.PHYSIONET_CHANNELS[channels.CH_C4] == "C4"
    assert (channels.CH_C3, channels.CH_CZ, channels.CH_C4) == (8, 10, 12)
    assert channels.STROKE_CHANNELS[channels.STROKE_CH_C3] == "C3"
    assert channels.STROKE_CHANNELS[channels.STROKE_CH_C4] == "C4"
    assert len(channels.STROKE_CHANNELS) == contracts.DATASETS["stroke"]["n_channels"]


@pytest.mark.real
def test_channel_map_on_real_file():
    if os.environ.get("BCI_REAL_DATA") != "1":
        pytest.skip("set BCI_REAL_DATA=1 to check the channel names in the PhysioNet EDF file")
    import mne

    path = os.environ.get("BCI_DATA_DIR")
    f = mne.datasets.eegbci.load_data(1, [4], path=path, update_path=False, verbose="error")[0]
    raw = mne.io.read_raw_edf(f, preload=False, verbose="error")
    mne.datasets.eegbci.standardize(raw)
    assert tuple(raw.ch_names) == channels.PHYSIONET_CHANNELS


@pytest.mark.parametrize("sfreq", [160, 500])
def test_band_power_units(erd, sfreq):
    """A 10 Hz sinusoid of amplitude 10 uV has power A^2/2 = 50 uV^2; nearly all of it lies in 8-13 Hz."""
    n = 3 * sfreq
    t = np.arange(n) / sfreq
    X = np.zeros((2, 3, n))
    X[0, 0] = 10.0 * np.sin(2 * np.pi * 10 * t)
    X[1, 1] = 20.0 * np.sin(2 * np.pi * 10 * t)
    P = np.asarray(erd.band_power(X, sfreq, MU))
    assert P.shape == (2, 3)
    assert abs(P[0, 0] - 50.0) < 5.0, f"band power {P[0, 0]:.2f} uV^2, expected about 50"
    assert abs(P[1, 1] - 200.0) < 20.0, f"band power {P[1, 1]:.2f} uV^2, expected about 200"
    assert P[0, 1] < 1e-6 and P[0, 2] < 1e-6


def test_ls_formula(erd):
    """Right trials: C3 has half the power; C4 equal. LS = ln(0.5) - 0 = -0.693."""
    sf, n = 160, 480
    t = np.arange(n) / sf
    rng = np.random.default_rng(0)
    y = np.repeat([0, 1], 10)
    X = np.zeros((20, 3, n))
    for i, lab in enumerate(y):
        X[i, 2] = 10.0 * np.sin(2 * np.pi * 10 * t + rng.uniform(0, 6.28))  # ch 2 = C4, equal in both classes
        a = 10.0 * (np.sqrt(0.5) if lab == 1 else 1.0)
        X[i, 0] = a * np.sin(2 * np.pi * 10 * t + rng.uniform(0, 6.28))  # ch 0 = C3
    ls = erd.lateralization(X, y, np.full(20, 7), sf, 0, 2, MU)
    assert set(ls) == {"7"}
    assert abs(ls["7"] - np.log(0.5)) < 0.05, f"LS {ls['7']:.4f}, expected ln(0.5) = {np.log(0.5):.4f}"


def test_ls_sign_on_planted_erd(erd, synth):
    X, y, groups, truth = synth
    assert truth["erd_channel_by_class"] == {0: 0, 1: 1}
    ls = erd.lateralization(X, y, groups, contracts.SFREQ, 1, 0, MU)  # C3 = ch 1, C4 = ch 0
    assert set(ls) == {str(s) for s in np.unique(groups)}
    assert all(v < 0 for v in ls.values()), f"LS should be < 0 for every planted subject: {ls}"
    swapped = erd.lateralization(X, y, groups, contracts.SFREQ, 0, 1, MU)
    assert all(v > 0 for v in swapped.values()), "swapping C3 and C4 must flip the sign"
    for s in ls:
        assert abs(ls[s] + swapped[s]) < 1e-9


def test_lateralization_vs_accuracy(erd):
    from scipy.stats import spearmanr

    ls = {"1": -0.5, "2": -0.1, "3": 0.2, "4": -0.9, "9": 0.0}
    acc = {"1": 0.7, "2": 0.55, "3": 0.5, "4": 0.9, "5": 0.6}
    r = erd.lateralization_vs_accuracy(ls, acc)
    ids = ["1", "2", "3", "4"]
    ref = spearmanr([ls[i] for i in ids], [acc[i] for i in ids])
    assert r["n"] == 4
    assert abs(r["rho"] - ref.statistic) < 1e-12 and abs(r["p"] - ref.pvalue) < 1e-12
