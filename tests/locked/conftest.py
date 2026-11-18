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
