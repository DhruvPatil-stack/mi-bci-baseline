"""Gate G10 (FROZEN, v0.3): results do not depend on wall-clock time; reruns skip finished stages.

TIME LIMIT CONTRACT and EVALUATE CHECKPOINT CONTRACT in bci/contracts.py. A fake clock that jumps 1 hour per
call must not change any result when BCI_ENFORCE_TIME_BUDGET=0, and must still trigger the safety stop when it
is 1. The test model is conftest.LogVarLDA (fast, deterministic), registered for the test only.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pytest

from conftest import LogVarLDA, required_module

OWNERS = ("claude/",)
NAME = "g10_logvar"


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        self.t += 3600.0
        return self.t


def _strip(block):
    """JSON round trip without timing fields."""
    b = json.loads(json.dumps(block))
    for k in ("runtime_s", "error"):
        b.pop(k, None)
    return b


@pytest.fixture()
def ev(monkeypatch):
    ev = required_module("evaluate", OWNERS)
    mc = required_module("models_classical", OWNERS)
    monkeypatch.setitem(mc.REGISTRY, NAME, LogVarLDA)
    monkeypatch.delenv("BCI_DATASET", raising=False)
    return ev, mc


def _fake_clock(monkeypatch):
    clock = _Clock()
    for attr in ("monotonic", "perf_counter", "time"):
        monkeypatch.setattr(time, attr, clock)


def test_result_independent_of_wall_clock(ev, monkeypatch, synth_small):
    ev, _ = ev
    X, y, groups = synth_small
    monkeypatch.setenv("BCI_ENFORCE_TIME_BUDGET", "0")
    real = ev.run_model(NAME, X, y, groups, calibration=True)
    assert real["status"] == "ok", real.get("error")
    _fake_clock(monkeypatch)
    slow = ev.run_model(NAME, X, y, groups, calibration=True)
    monkeypatch.undo()
    assert slow["status"] == "ok", f"time limit off, but status {slow['status']}: {slow.get('error')}"
    assert _strip(slow) == _strip(real), "a wall-clock value changed a result with the time limit off"


def test_safety_stop_still_works(ev, monkeypatch, synth_small):
    ev, _ = ev
    X, y, groups = synth_small
    monkeypatch.setenv("BCI_ENFORCE_TIME_BUDGET", "1")
    _fake_clock(monkeypatch)
    out = ev.run_model(NAME, X, y, groups, calibration=True)
    monkeypatch.undo()
    assert out["status"] == "timeout", f"enforce on + 1 h per clock call: status {out['status']}, expected timeout"


class _Boom(LogVarLDA):
    def fit(self, X, y):
        raise RuntimeError("G10: a finished stage was recomputed")


def test_rerun_skips_finished_stages(ev, monkeypatch, synth_small, tmp_path):
    ev, mc = ev
    X, y, groups = synth_small
    monkeypatch.setenv("BCI_ENFORCE_TIME_BUDGET", "0")
    ck = tmp_path / "ck.json"
    first = ev.run_model(NAME, X, y, groups, calibration=False, checkpoint=str(ck))
    assert first["status"] == "ok", first.get("error")
    assert ck.exists(), "checkpoint file not written"
    for stage in ("within_subject", "cross_subject", "permutation"):
        assert stage in first
    assert "per_subject" in first["within_subject"]

    monkeypatch.setitem(mc.REGISTRY, NAME, _Boom)
    again = ev.run_model(NAME, X, y, groups, calibration=False, checkpoint=str(ck))
    assert again["status"] == "ok", f"rerun refitted a finished stage: {again.get('error')}"
    assert _strip(again) == _strip(first)

    fits = []

    class _Count(LogVarLDA):
        def fit(self, X, y):
            fits.append(1)
            return super().fit(X, y)

    monkeypatch.setitem(mc.REGISTRY, NAME, _Count)
    n_cal = 0
    ev.calibration_curve(NAME, X, y, groups)
    n_cal, fits[:] = len(fits), []
    full = ev.run_model(NAME, X, y, groups, calibration=True, checkpoint=str(ck))
    assert full["status"] == "ok", full.get("error")
    assert len(fits) == n_cal, f"rerun with calibration fitted {len(fits)} times, calibration alone needs {n_cal}"
    for stage in ("within_subject", "cross_subject", "permutation"):
        assert _strip(full[stage]) == _strip(first[stage])

    monkeypatch.setitem(mc.REGISTRY, NAME, _Boom)
    X2 = np.array(X, copy=True)
    X2[0, 0, 0] += 1.0
    changed = ev.run_model(NAME, X2, y, groups, calibration=False, checkpoint=str(ck))
    assert changed["status"] == "error", "changed data reused a checkpoint made for other data"
