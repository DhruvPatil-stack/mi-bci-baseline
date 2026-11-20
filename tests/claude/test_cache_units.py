"""Branch tests for bci/cache.py (S1). They cover cases tests/locked/test_cache.py does not: the memory cap,
duplicate rows, 2D and tiny inputs, sklearn clone/get_params, and that no temp file is left behind."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.base import clone

from bci import cache
from bci.models_classical import REGISTRY, BandPass

TOL = 1e-9


@pytest.fixture()
def cdir(monkeypatch, tmp_path):
    d = tmp_path / "filtered"
    monkeypatch.setenv("BCI_FILTER_CACHE", "1")
    monkeypatch.setenv("BCI_FILTER_CACHE_DIR", str(d))
    monkeypatch.delenv("BCI_FILTER_CACHE_MEM_MB", raising=False)
    cache.clear_memory()
    yield d
    cache.clear_memory()


def _X(n=40, c=4, t=320, seed=0):
    return np.random.default_rng(seed).standard_normal((n, c, t)).astype(np.float32)


def test_duplicate_rows_and_order(cdir):
    X = _X()
    ref = cache.bandpass_direct(X, 8.0, 30.0, 160, 4)
    idx = np.array([5, 5, 0, 39, 5, 12, 0])
    out = BandPass(8.0, 30.0, 160, 4).transform(X[idx])  # cold, with duplicates
    assert np.max(np.abs(out - ref[idx])) <= TOL
    assert len(list(cdir.rglob("*.npy"))) == len(set(idx.tolist()))
    out2 = BandPass(8.0, 30.0, 160, 4).transform(X[::-1])  # partly warm, reversed order
    assert np.max(np.abs(out2 - ref[::-1])) <= TOL


def test_memory_cap_zero_falls_back_to_disk(cdir, monkeypatch):
    monkeypatch.setenv("BCI_FILTER_CACHE_MEM_MB", "0")
    X = _X()
    ref = cache.bandpass_direct(X, 8.0, 30.0, 160, 4)
    bp = BandPass(8.0, 30.0, 160, 4)
    for _ in range(2):
        assert np.max(np.abs(bp.transform(X) - ref)) <= TOL
    assert cache.memory_bytes() == 0


def test_output_is_a_fresh_array(cdir):
    X = _X()
    bp = BandPass(8.0, 30.0, 160, 4)
    a = bp.transform(X)
    a[:] = 0.0  # a caller that mutates the output must not poison the cache
    b = bp.transform(X)
    assert np.max(np.abs(b - cache.bandpass_direct(X, 8.0, 30.0, 160, 4))) <= TOL


def test_2d_and_single_row(cdir):
    X = _X(n=3)
    bp = BandPass(8.0, 30.0, 160, 4)
    assert np.max(np.abs(bp.transform(X[0]) - cache.bandpass_direct(X[0], 8.0, 30.0, 160, 4))) <= TOL
    assert np.max(np.abs(bp.transform(X[:1]) - cache.bandpass_direct(X[:1], 8.0, 30.0, 160, 4))) <= TOL


def test_no_temp_files_and_float64(cdir):
    BandPass(8.0, 30.0, 160, 4).transform(_X())
    files = [p for p in cdir.rglob("*") if p.is_file()]
    assert files and all(p.suffix == ".npy" for p in files)
    assert all(np.load(p).dtype == np.float64 for p in files)


def test_clone_and_params_unchanged(cdir):
    bp = BandPass(low=8.0, high=30.0, fs=160, order=4)
    assert sorted(bp.get_params()) == ["fs", "high", "low", "order"]
    bp.transform(_X())
    assert clone(bp).get_params() == bp.get_params()
    for name in ("csp_lda", "fbcsp_lr"):
        est = REGISTRY[name]()
        assert clone(est).get_params().keys() == est.get_params().keys()
