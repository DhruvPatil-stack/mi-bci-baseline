"""Gate G13 (FROZEN, v0.3): stroke loader shapes, labels, uV range (STROKE LOADER CONTRACT, docs/STROKE_DATASET.md).

The data check runs only when BCI_EXPECT_STROKE=1 (PRD_v0.3 section 12). The static check (no synthetic
fallback) runs whenever bci/data_stroke.py exists.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from bci import contracts
from conftest import REPO, optional_module


def test_no_synthetic_fallback_in_stroke_loader():
    path = REPO / "bci" / "data_stroke.py"
    if not path.exists():
        pytest.skip("bci/data_stroke.py not on this branch (S4 is optional)")
    src = path.read_text(encoding="utf-8")
    assert "synthetic" not in src.replace("SYNTHETIC_LABEL", ""), (
        "data_stroke.py mentions synthetic data: the stroke loader must never fall back to synthetic data")


def test_stroke_loader_real():
    if os.environ.get("BCI_EXPECT_STROKE") != "1":
        pytest.skip("set BCI_EXPECT_STROKE=1 to check the stroke loader on the downloaded data")
    ds = optional_module("data_stroke")
    assert ds is not None, "BCI_EXPECT_STROKE=1 but bci/data_stroke.py does not exist"
    X, y, groups = ds.load_stroke([1, 2])
    contracts.validate_data(X, y, groups, "stroke")
    X, y, groups = np.asarray(X), np.asarray(y), np.asarray(groups)
    assert set(np.unique(groups).tolist()) == {1, 2}
    for s in (1, 2):
        m = groups == s
        assert int(m.sum()) == 40, f"patient {s}: {int(m.sum())} trials, expected 40"
        assert int(np.sum(y[m] == 0)) == 20 and int(np.sum(y[m] == 1)) == 20, f"patient {s}: not 20 left + 20 right"
    med = float(np.median(np.abs(X)))
    assert 1.0 <= med <= 100.0, f"median |X| = {med} uV; outside 1-100 uV means a unit error"
    assert np.isfinite(X).all()
    # no flat channel (a kept reference or marker channel would be flat or a step function)
    sd = X.std(axis=-1).mean(axis=0)
    assert sd.min() > 0.1, f"channel {int(sd.argmin())} is flat (mean sd {sd.min():.3g} uV)"
