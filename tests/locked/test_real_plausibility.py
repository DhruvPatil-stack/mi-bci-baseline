"""Gate G4 (FROZEN, physionet only): leak-suspect values fail; out-of-range values warn.

Reads $BCI_RESULTS or results/results.json. Rule: bci.contracts.g4_check.
The ranges are plausibility limits from general experience, not published values (PRD section 12 NOTE).
"""
from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import pytest

from bci.contracts import g4_check, validate_results

REPO = Path(__file__).resolve().parents[2]


def _results():
    path = Path(os.environ.get("BCI_RESULTS", REPO / "results" / "results.json"))
    if not path.exists():
        pytest.skip(f"{path} not found")
    res = json.loads(path.read_text(encoding="utf-8"))
    if res["meta"]["data_source"] != "physionet":
        pytest.skip("G4 applies to physionet results only")
    return res


def test_results_schema():
    validate_results(_results())


def test_real_plausibility():
    fails, warns = g4_check(_results())
    for w in warns:
        warnings.warn(f"G4 WARNING: {w}")
    assert not fails, "G4 FAIL:\n" + "\n".join(fails)


def test_g4_rule_on_planted_values():
    """The rule itself: a 0.97 mean is a fail, a 0.50 csp_lda within mean is a warning."""
    def block(w, c):
        return {"within_subject": {"per_subject": {"1": {"acc": w, "bal_acc": w, "kappa": 0.0}},
                                   "mean_bal_acc": w, "std_bal_acc": 0.0},
                "cross_subject": {"per_fold": [{"test_subjects": [1], "acc": c, "bal_acc": c, "kappa": 0.0}],
                                  "mean_bal_acc": c, "std_bal_acc": 0.0},
                "permutation": {"within_mean_bal_acc": 0.5, "cross_mean_bal_acc": 0.5}}
    res = {"meta": {"data_source": "physionet"}, "models": {"csp_lda": block(0.97, 0.6)}}
    fails, _ = g4_check(res)
    assert fails
    res = {"meta": {"data_source": "physionet"}, "models": {"csp_lda": block(0.50, 0.6)}}
    fails, warns = g4_check(res)
    assert not fails and any("within" in w for w in warns)
