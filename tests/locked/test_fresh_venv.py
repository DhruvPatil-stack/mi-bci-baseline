"""Gate G7 (FROZEN): run_all.py runs clean in a fresh venv.

Opt-in (it installs requirements.txt): set BCI_RUN_G7=1. The venv is made at <repo>/.venv_g7
(inside the repo, git-excluded). Then `python run_all.py --synthetic --out .cache/g7_out` must exit 0 and
write a valid results.json. Set BCI_G7_REAL=1 to run without --synthetic (PhysioNet).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bci.contracts import validate_results

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.g7
def test_run_all_in_fresh_venv():
    if os.environ.get("BCI_RUN_G7") != "1":
        pytest.skip("set BCI_RUN_G7=1 to run the fresh-venv gate")
    if not (REPO / "run_all.py").exists():
        pytest.fail("run_all.py does not exist")
    venv = REPO / ".venv_g7"
    if venv.exists():
        shutil.rmtree(venv)
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    r = subprocess.run([str(py), "-m", "pip", "install", "-r", "requirements.txt"], cwd=REPO,
                       capture_output=True, text=True)
    assert r.returncode == 0, f"pip install failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}"
    out = REPO / ".cache" / "g7_out"
    args = [str(py), "run_all.py", "--out", str(out)]
    if os.environ.get("BCI_G7_REAL") != "1":
        args.insert(2, "--synthetic")
    r = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"run_all.py failed in fresh venv:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}"
    validate_results(json.loads((out / "results.json").read_text(encoding="utf-8")))
