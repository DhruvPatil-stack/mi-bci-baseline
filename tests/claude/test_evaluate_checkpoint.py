"""Ticket S2 branch checks for the evaluate checkpoint (additional to tests/locked/test_wallclock.py, G10).

G10 already checks: results independent of a fake clock, the safety stop, rerun skips finished stages, the
calibration-only rerun fit count, and that changed X is not reused. These tests cover what G10 does not:
fingerprint content, the file layout, foreign/corrupt files, the calibration flag on a rerun, run_calibration
with a checkpoint, and that the atomic write leaves no temp file. Synthetic data only (SYNTHETIC - NOT VALID).
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from bci import contracts, evaluate, models_classical
from bci.synthetic import make_synthetic

NAME = "s2_logvar"


class _LogVar(BaseEstimator, ClassifierMixin):
    """Fast deterministic test estimator (log variance of channels 0, 1 -> LDA). Not a project model."""

    def fit(self, X, y):
        self.lda_ = LinearDiscriminantAnalysis().fit(self._f(X), y)
        self.classes_ = self.lda_.classes_
        return self

    @staticmethod
    def _f(X):
        return np.log(np.asarray(X, dtype=np.float64)[:, :2, :].var(axis=-1))

    def predict(self, X):
        return self.lda_.predict(self._f(X))

    def predict_proba(self, X):
        return self.lda_.predict_proba(self._f(X))


class _Boom(_LogVar):
    def fit(self, X, y):
        raise RuntimeError("recomputed")


@pytest.fixture(scope="module")
def small():
    X, y, groups, _ = make_synthetic(n_subjects=5, trials_per_subject=40, seed=7)
    return X, y, groups


@pytest.fixture()
def reg(monkeypatch):
    monkeypatch.setenv("BCI_ENFORCE_TIME_BUDGET", "0")
    monkeypatch.delenv("BCI_DATASET", raising=False)
    monkeypatch.setitem(models_classical.REGISTRY, NAME, _LogVar)
    return monkeypatch


def _strip(b):
    b = json.loads(json.dumps(b))
    for k in ("runtime_s", "error"):
        b.pop(k, None)
    return b


def test_fingerprint_content(small):
    X, y, groups = small
    cfg = contracts.load_config()
    fp = evaluate.fingerprint(NAME, X, y, groups, cfg)
    assert fp == evaluate.fingerprint(NAME, np.array(X, copy=True), list(y), groups, dict(cfg))
    assert fp != evaluate.fingerprint("other", X, y, groups, cfg)
    y2 = np.array(y, copy=True)
    y2[0] = 1 - y2[0]
    assert fp != evaluate.fingerprint(NAME, X, y2, groups, cfg)
    g2 = np.array(groups, copy=True)
    g2[0] = g2[-1]
    assert fp != evaluate.fingerprint(NAME, X, y, g2, cfg)
    assert fp != evaluate.fingerprint(NAME, X, y, groups, {**cfg, "n_splits": 4})


def test_checkpoint_layout_and_no_temp_left(reg, small, tmp_path):
    X, y, groups = small
    ck = tmp_path / "sub" / "ck.json"  # folder created on demand
    out = evaluate.run_model(NAME, X, y, groups, calibration=False, checkpoint=str(ck))
    assert out["status"] == "ok", out.get("error")
    doc = json.loads(ck.read_text(encoding="utf-8"))
    assert doc["fingerprint"] == evaluate.fingerprint(NAME, X, y, groups, contracts.load_config())
    assert doc["model"] == NAME
    assert set(doc["stages"]) == {"within_subject", "cross_subject", "permutation"}
    assert "per_subject" in doc["stages"]["within_subject"]
    assert [p.name for p in ck.parent.iterdir()] == ["ck.json"], "atomic write left a temp file"
    for key in doc["stages"]:
        assert _strip(doc["stages"][key]) == _strip(out[key])


def test_calibration_kept_in_file_but_not_returned(reg, small, tmp_path):
    X, y, groups = small
    ck = tmp_path / "ck.json"
    full = evaluate.run_model(NAME, X, y, groups, calibration=True, checkpoint=str(ck))
    assert full["status"] == "ok", full.get("error")
    reg.setitem(models_classical.REGISTRY, NAME, _Boom)
    short = evaluate.run_model(NAME, X, y, groups, calibration=False, checkpoint=str(ck))
    assert short["status"] == "ok", short.get("error")
    assert "calibration" not in short
    assert "calibration" in json.loads(ck.read_text(encoding="utf-8"))["stages"]
    cal = evaluate.run_calibration(NAME, X, y, groups, 1.0, checkpoint=str(ck))
    assert cal["status"] == "ok", cal.get("error")
    assert _strip(cal["calibration"]) == _strip(full["calibration"])


def test_foreign_and_corrupt_checkpoint_ignored(reg, small, tmp_path):
    X, y, groups = small
    ref = evaluate.run_model(NAME, X, y, groups, calibration=False)
    ck = tmp_path / "ck.json"
    ck.write_text("{not json", encoding="utf-8")
    out = evaluate.run_model(NAME, X, y, groups, calibration=False, checkpoint=str(ck))
    assert _strip(out) == _strip(ref)
    doc = json.loads(ck.read_text(encoding="utf-8"))  # overwritten with a valid checkpoint
    doc["fingerprint"] = "0" * 64
    doc["stages"]["within_subject"]["mean_bal_acc"] = 0.123
    ck.write_text(json.dumps(doc), encoding="utf-8")
    out = evaluate.run_model(NAME, X, y, groups, calibration=False, checkpoint=str(ck))
    assert _strip(out) == _strip(ref), "a checkpoint with another fingerprint was reused"


def test_run_calibration_writes_and_resumes(reg, small, tmp_path):
    X, y, groups = small
    ck = tmp_path / "ck.json"
    first = evaluate.run_calibration(NAME, X, y, groups, 1.0, checkpoint=str(ck))
    assert first["status"] == "ok", first.get("error")
    assert set(json.loads(ck.read_text(encoding="utf-8"))["stages"]) == {"calibration"}
    reg.setitem(models_classical.REGISTRY, NAME, _Boom)
    again = evaluate.run_calibration(NAME, X, y, groups, 1.0, checkpoint=str(ck))
    assert again["status"] == "ok", again.get("error")
    assert _strip(again) == _strip(first)


def test_no_checkpoint_means_no_file(reg, small, tmp_path, monkeypatch):
    X, y, groups = small
    monkeypatch.chdir(tmp_path)
    out = evaluate.run_model(NAME, X, y, groups, calibration=False)
    assert out["status"] == "ok", out.get("error")
    assert list(tmp_path.iterdir()) == []
