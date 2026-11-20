"""Additional H1 behavior checks that complement locked G11."""
import numpy as np

from bci.analysis import calibration_gain_by_group, classify_responders


def test_empty_responder_set_is_explicit():
    out = classify_responders({}, 0.05)
    assert out["count"] == 0 and out["n"] == 0
    assert out["ci95"] == [None, None]


def test_group_bootstrap_is_seeded_and_paired_to_its_k0_baseline():
    k = [0, 4]
    per_target = [
        {"1": {"source_plus_target": 0.5}, "2": {"source_plus_target": 0.6},
         "3": {"source_plus_target": 0.4}, "4": {"source_plus_target": 0.5}},
        {"1": {"source_plus_target": 0.7}, "2": {"source_plus_target": 0.7},
         "3": {"source_plus_target": 0.45}, "4": {"source_plus_target": 0.55}},
    ]
    flags = {"1": True, "2": True, "3": False, "4": False}
    a = calibration_gain_by_group(per_target, flags, k, n_boot=100, seed=7)
    b = calibration_gain_by_group(per_target, flags, k, n_boot=100, seed=7)
    assert a == b
    assert np.allclose(a["responders"], [0.0, 0.15])
    assert np.allclose(a["non_responders"], [0.0, 0.05])
