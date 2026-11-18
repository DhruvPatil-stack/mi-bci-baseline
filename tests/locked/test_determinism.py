"""Gate G6 (FROZEN): seed 42 gives identical outputs.

RUN_ALL CONTRACT (integration): `python run_all.py --synthetic --out DIR` writes DIR/results.json
(and the report files) using synthetic.make_synthetic() defaults. Without --synthetic it uses PhysioNet with
the 3-attempt synthetic fallback. --out defaults to results/.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from bci.synthetic import make_synthetic
from conftest import all_registries

REPO = Path(__file__).resolve().parents[2]
IGNORE_META = ("timestamp",)
IGNORE_TOP = ("runtime_s",)


def test_synthetic_is_deterministic():
    a = make_synthetic(n_subjects=2, trials_per_subject=10)
    b = make_synthetic(n_subjects=2, trials_per_subject=10)
    for u, v in zip(a[:3], b[:3]):
        assert np.array_equal(u, v)


@pytest.mark.parametrize("name", sorted(all_registries()) or ["<none>"])
def test_two_fits_same_predictions(name, synth_small):
    if name == "<none>":
        pytest.skip("no model module on this branch")
    X, y, _ = synth_small
    p = [np.asarray(all_registries()[name]().fit(X[:160], y[:160]).predict_proba(X[160:])) for _ in range(2)]
    assert np.array_equal(p[0], p[1]), f"{name}: two fits with the same seed differ"


def _strip(res):
    res = dict(res)
    for k in IGNORE_TOP:
        res.pop(k, None)
    res["meta"] = {k: v for k, v in res["meta"].items() if k not in IGNORE_META}
    return res


@pytest.mark.slow
def test_run_all_twice_same_results(tmp_path):
    if not (REPO / "run_all.py").exists():
        pytest.skip("run_all.py not on this branch")
    outs = []
    for i in range(2):
        out = tmp_path / f"run{i}"
        r = subprocess.run([sys.executable, "run_all.py", "--synthetic", "--out", str(out)], cwd=REPO,
                           capture_output=True, text=True)
        assert r.returncode == 0, f"run_all.py failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}"
        outs.append(json.loads((out / "results.json").read_text(encoding="utf-8")))
    assert outs[0]["meta"]["data_source"] == "synthetic"
    assert _strip(outs[0]) == _strip(outs[1]), "two seeded runs gave different results.json"
