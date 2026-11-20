"""Gate G8 (FROZEN, v0.3): the filter cache never changes results (FILTER CACHE CONTRACT in bci/contracts.py).

Cached and uncached BandPass outputs and csp_lda / fbcsp_lr predictions match to 1e-9. The key is the data
CONTENT (a changed or mutated array is a new key), plus band, order and sampling rate. The cache holds only
stateless filter output (.npy files that do not depend on labels). Several processes may use one cache at once.
bci/cache.py is required on claude/speed-stroke and integration/v0.3 (missing there = FAIL).
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

from bci.splits import cross_subject_splits
from conftest import REPO, required_module

TOL = 1e-9
OWNERS = ("claude/",)


@pytest.fixture()
def env(monkeypatch, tmp_path):
    cache = required_module("cache", OWNERS)
    mc = required_module("models_classical", OWNERS)
    monkeypatch.delenv("BCI_DATASET", raising=False)
    cdir = tmp_path / "filtered"
    monkeypatch.setenv("BCI_FILTER_CACHE_DIR", str(cdir))

    def mode(on: bool):
        monkeypatch.setenv("BCI_FILTER_CACHE", "1" if on else "0")
        cache.clear_memory()

    return cache, mc, cdir, mode


def _files(cdir: Path):
    return sorted(p for p in cdir.rglob("*") if p.is_file()) if cdir.exists() else []


def _maxdiff(a, b):
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    assert a.shape == b.shape, f"shapes {a.shape} vs {b.shape}"
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def test_transform_cached_equals_uncached(env, synth):
    cache, mc, cdir, mode = env
    X = synth[0]
    for band, fs, order in (((8.0, 30.0), 160, 4), ((8, 12), 160, 4), ((8.0, 30.0), 500, 4), ((8.0, 30.0), 160, 2)):
        bp = mc.BandPass(low=band[0], high=band[1], fs=fs, order=order)
        mode(False)
        n_before = len(_files(cdir))
        ref = bp.transform(X)
        assert len(_files(cdir)) == n_before, "BCI_FILTER_CACHE=0 must not write cache files"
        mode(True)
        cold = bp.transform(X)
        warm = bp.transform(X)
        cache.clear_memory()
        disk = bp.transform(X)
        for label, out in (("cold", cold), ("memory", warm), ("disk", disk)):
            assert _maxdiff(out, ref) <= TOL, f"{label} cache output differs from uncached for {band} {fs} Hz order {order}"
        sub = np.r_[3:40, 100:150, 7]
        assert _maxdiff(bp.transform(X[sub]), ref[sub]) <= TOL, "row subset differs from uncached"
    assert _files(cdir), "cache on, but no file was written to BCI_FILTER_CACHE_DIR: the cache does nothing"


def test_key_is_content_not_identity(env, synth):
    cache, mc, cdir, mode = env
    X = np.array(synth[0], copy=True)
    bp = mc.BandPass(low=8.0, high=30.0, fs=160, order=4)
    mode(True)
    bp.transform(X)
    X2 = X.copy()
    X2[5, 3, 100] += 1.0
    out2 = bp.transform(X2)
    X[0, 0, 0] += 5.0  # in-place mutation of an array that is already cached
    out_mut = bp.transform(X)
    mode(False)
    assert _maxdiff(out2, bp.transform(X2)) <= TOL, "a changed array got the output of the old array (key error)"
    assert _maxdiff(out_mut, bp.transform(X)) <= TOL, "an in-place mutated array got a stale cached output"


def test_band_order_fs_are_in_the_key(env, synth):
    cache, mc, cdir, mode = env
    X = synth[0][:40]
    mode(True)
    outs = {}
    for key in (((8, 30), 160, 4), ((8, 12), 160, 4), ((8, 30), 500, 4), ((8, 30), 160, 2)):
        (lo, hi), fs, order = key
        outs[key] = mc.BandPass(low=lo, high=hi, fs=fs, order=order).transform(X)
    keys = list(outs)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            assert _maxdiff(outs[keys[i]], outs[keys[j]]) > 1e-3, f"{keys[i]} and {keys[j]} share a cache entry"


@pytest.mark.parametrize("name", ["csp_lda", "fbcsp_lr"])
def test_predictions_cached_equal_uncached(env, synth, name):
    cache, mc, cdir, mode = env
    X, y, groups, _ = synth
    tr, te = next(iter(cross_subject_splits(groups)))
    out = {}
    for label, on in (("off", False), ("cold", True), ("warm", True)):
        if label != "warm":
            mode(on)
        est = mc.REGISTRY[name]().fit(X[tr], y[tr])
        out[label] = (np.asarray(est.predict_proba(X[te])), np.asarray(est.predict(X[te])))
    for label in ("cold", "warm"):
        assert _maxdiff(out[label][0], out["off"][0]) <= TOL, f"{name}: {label} cache predict_proba differs"
        assert np.array_equal(out[label][1], out["off"][1]), f"{name}: {label} cache predictions differ"


def test_cache_holds_no_learned_state(env, synth):
    """Only .npy filter outputs; refitting with permuted labels adds no file (output does not depend on y)."""
    cache, mc, cdir, mode = env
    X, y, groups, _ = synth
    mode(True)
    for name in ("csp_lda", "fbcsp_lr"):
        mc.REGISTRY[name]().fit(X, y)
    before = _files(cdir)
    assert before, "no cache file written"
    bad = [p.name for p in before if p.suffix != ".npy"]
    assert not bad, f"cache dir holds non-.npy files: {bad[:5]}"
    for p in before:
        a = np.load(p, allow_pickle=False)
        assert a.shape[-1] == X.shape[-1], f"{p.name}: last axis {a.shape[-1]} is not the time axis {X.shape[-1]}"
        assert a.dtype == np.float64, f"{p.name}: dtype {a.dtype}, filter output is float64"
    rng = np.random.default_rng(0)
    for name in ("csp_lda", "fbcsp_lr"):
        mc.REGISTRY[name]().fit(X, rng.permutation(y))
    after = _files(cdir)
    assert [p.name for p in after] == [p.name for p in before], "permuted labels created new cache entries"


def test_cache_is_safe_across_processes(env, synth, tmp_path):
    cache, mc, cdir, mode = env
    X = np.asarray(synth[0][:120])
    xpath = tmp_path / "x.npy"
    np.save(xpath, X)
    mode(False)
    ref = mc.BandPass(low=8.0, high=30.0, fs=160, order=4).transform(X)
    code = textwrap.dedent(f"""
        import sys, numpy as np
        sys.path.insert(0, {str(REPO)!r})
        from bci import cache
        from bci.models_classical import BandPass
        X = np.load({str(xpath)!r})
        for r in range(3):
            cache.clear_memory()
            out = BandPass(low=8.0, high=30.0, fs=160, order=4).transform(X)
        np.save(sys.argv[1], out)
    """)
    env_vars = {**os.environ, "BCI_FILTER_CACHE": "1", "BCI_FILTER_CACHE_DIR": str(cdir)}
    procs = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path / f"out{i}.npy")], cwd=REPO, env=env_vars,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(4)]
    for i, p in enumerate(procs):
        so, se = p.communicate(timeout=600)
        assert p.returncode == 0, f"worker {i} failed:\n{se[-3000:]}"
    for i in range(4):
        assert _maxdiff(np.load(tmp_path / f"out{i}.npy"), ref) <= TOL, f"worker {i} output differs from uncached"
    for p in _files(cdir):
        assert p.suffix == ".npy", f"leftover non-.npy file after concurrent use: {p.name}"
        np.load(p, allow_pickle=False)  # no torn file
