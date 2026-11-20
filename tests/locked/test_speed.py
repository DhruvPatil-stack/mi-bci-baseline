"""Gate G9 (FROZEN, v0.3): 1 csp_lda fit on (850, 64, 480) takes at most 25 % of the v0.2 time.

v0.2 baseline (docs/DECISIONS.md, "v0.3 speed baseline"): 6.267 s, median of 3 fits of the v0.2 csp_lda on
make_synthetic(n_subjects=1, trials_per_subject=850, seed=1), 2 BLAS threads, this PC, 2026-11-20.
The timed fit is the fit as cross-validation sees it: the cache is warm for the full 900-trial array, and each
timed fit gets a NEW 850-row subset (3 different subsets, median). A cache keyed only on whole arrays gives no
speedup here, so it fails this gate. bci/cache.py is required on claude/speed-stroke and integration/v0.3.
"""
from __future__ import annotations

import time

import numpy as np

from bci.synthetic import make_synthetic
from conftest import required_module

V02_BASELINE_S = 6.267
LIMIT_S = 0.25 * V02_BASELINE_S
OWNERS = ("claude/",)


def test_csp_lda_fit_speed(monkeypatch, tmp_path):
    cache = required_module("cache", OWNERS)
    mc = required_module("models_classical", OWNERS)
    monkeypatch.delenv("BCI_DATASET", raising=False)
    monkeypatch.setenv("BCI_FILTER_CACHE", "1")
    monkeypatch.setenv("BCI_FILTER_CACHE_DIR", str(tmp_path / "filtered"))
    cache.clear_memory()
    X, y, _, _ = make_synthetic(n_subjects=1, trials_per_subject=900, seed=1)
    mc.REGISTRY["csp_lda"]().fit(X, y)  # warm: imports and the filter cache for all 900 trials
    times = []
    for r in range(3):
        idx = np.sort(np.random.default_rng(100 + r).choice(len(X), size=850, replace=False))
        Xs, ys = X[idx], y[idx]
        t0 = time.perf_counter()
        mc.REGISTRY["csp_lda"]().fit(Xs, ys)
        times.append(time.perf_counter() - t0)
    med = float(np.median(times))
    assert med <= LIMIT_S, (f"csp_lda fit median {med:.3f} s (runs {[round(t, 3) for t in times]}) > "
                            f"{LIMIT_S:.3f} s = 25 % of the v0.2 {V02_BASELINE_S} s")
