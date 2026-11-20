"""FROZEN shared fixtures for the locked gate checks (Head chef, Phase 0)."""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / ".cache"
# Keep every library cache inside the repo (PLATFORM rule: never write outside the folder).
for _var, _sub in (("MPLCONFIGDIR", "mpl"), ("_MNE_FAKE_HOME_DIR", "mne_home"), ("TMP", "tmp"), ("TEMP", "tmp")):
    os.environ.setdefault(_var, str(CACHE / _sub))
    (CACHE / _sub).mkdir(parents=True, exist_ok=True)
os.environ.setdefault("BCI_DATA_DIR", str(CACHE / "mne_data"))
os.environ.setdefault("MPLBACKEND", "Agg")


def optional_module(name: str):
    """Import bci.<name>, or return None if the file does not exist on this branch.

    An ImportError raised INSIDE an existing module is not hidden: the test fails.
    """
    path = REPO / "bci" / f"{name}.py"
    if not path.exists():
        return None
    return importlib.import_module(f"bci.{name}")


def all_registries():
    """Merged REGISTRY of the model modules present on this branch."""
    reg = {}
    for mod_name in ("models_classical", "models_advanced"):
        mod = optional_module(mod_name)
        if mod is not None:
            reg.update(mod.REGISTRY)
    return reg


@pytest.fixture(scope="session")
def synth():
    from bci.synthetic import make_synthetic

    X, y, groups, truth = make_synthetic()
    return X, y, groups, truth


@pytest.fixture(scope="session")
def synth_small():
    """Small synthetic set for contract checks (5 subjects so cross-subject 5-fold works)."""
    from bci.synthetic import make_synthetic

    X, y, groups, truth = make_synthetic(n_subjects=5, trials_per_subject=40, seed=7)
    return X, y, groups


def id_tagged(X):
    """Copy of X whose sample [i, 0, 0] holds the row index i (exact in float32 below 2**24)."""
    Xt = np.array(X, dtype=np.float32, copy=True)
    Xt[:, 0, 0] = np.arange(len(Xt), dtype=np.float32)
    return Xt


# ---------------------------------------------------------------- v0.3 helpers (Head chef, Phase 0 v0.3)
def current_branch() -> str:
    import subprocess

    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO, capture_output=True, text=True)
    return r.stdout.strip()


def required_module(name: str, owner_prefixes):
    """Import bci.<name> for a gate that belongs to the branches in owner_prefixes (and integration).

    On an owner branch a missing file is a FAIL (a gate must not pass by checking nothing there).
    On any other branch (main, base/v0.3, the other agent's branch) the gate is skipped with the reason:
    the module there is not that branch's work. Integration branches are always owners.
    """
    branch = current_branch()
    owners = tuple(owner_prefixes) + ("integration/v0.3",)
    if not any(branch.startswith(p) for p in owners):
        pytest.skip(f"gate for bci/{name}.py runs on {owners}, not on {branch}")
    mod = optional_module(name)
    if mod is None:
        pytest.fail(f"bci/{name}.py is required on {branch} but does not exist")
    return mod


def model_owner_prefixes(model_name: str):
    """Branches whose work a registry model is: classical -> claude, advanced -> codex."""
    from bci.contracts import ADVANCED_MODELS, CLASSICAL_MODELS

    if model_name in CLASSICAL_MODELS:
        return ("claude/",)
    if model_name in ADVANCED_MODELS:
        return ("codex/",)
    return ()


from sklearn.base import BaseEstimator, ClassifierMixin  # noqa: E402


class LogVarLDA(BaseEstimator, ClassifierMixin):
    """Fast deterministic test estimator: log variance of channels 0 and 1 -> LDA. Not a project model."""

    def fit(self, X, y):
        from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

        self.lda_ = LinearDiscriminantAnalysis().fit(self._f(X), y)
        self.classes_ = self.lda_.classes_
        return self

    @staticmethod
    def _f(X):
        X = np.asarray(X, dtype=np.float64)
        return np.log(X[:, :2, :].var(axis=-1))

    def predict(self, X):
        return self.lda_.predict(self._f(X))

    def predict_proba(self, X):
        return self.lda_.predict_proba(self._f(X))
