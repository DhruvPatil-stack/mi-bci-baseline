"""Gate G5 (FROZEN): every decimal number in results.md exists in results.json.

A number written with d decimals matches a JSON number x when |x - v| <= 0.5 * 10**-d (rounding), or
when it is followed by "%" and |100 x - v| <= 0.5 * 10**-d. Scientific notation uses the mantissa decimals.
Integers (counts, k values, subject ids, figure numbers) are not checked. Allowed constants:
contracts.REPORT_ALLOWED_CONSTANTS (chance 0.5, alpha 0.05).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from bci.contracts import REPORT_ALLOWED_CONSTANTS, SYNTHETIC_LABEL, validate_results
from conftest import optional_module

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name("fixtures") / "results_fixture.json"
NUM = re.compile(r"(?<![\w.])(-?\d+\.(\d+))(?:[eE]([-+]?\d+))?(%?)")
FIGURES = ("fig1_models.png", "fig2_calibration.png", "fig3_permutation.png")


def _json_numbers(obj, out):
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _json_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _json_numbers(v, out)
    return out


def _strip_links(md: str) -> str:
    md = re.sub(r"\]\([^)]*\)", "]", md)       # markdown link / image targets
    md = re.sub(r"`[^`]*`", "", md)            # inline code (paths, names)
    md = re.sub(r"\bv\d+(\.\d+)+", "", md)     # version strings like v0.2
    return md


def unmatched_numbers(md: str, res: dict) -> list[str]:
    nums = _json_numbers(res, []) + list(REPORT_ALLOWED_CONSTANTS)
    bad = []
    for m in NUM.finditer(_strip_links(md)):
        token, dec, exp, pct = m.group(1), m.group(2), m.group(3), m.group(4)
        v = abs(float(token) * (10 ** int(exp) if exp else 1))
        tol = 0.5 * 10 ** (-len(dec) + (int(exp) if exp else 0)) + 1e-12
        cands = [abs(x) * (100 if pct else 1) for x in nums]
        if not any(abs(c - v) <= tol for c in cands):
            bad.append(m.group(0))
    return bad


def test_matcher_rejects_invented_number():
    res = {"a": 0.6123, "b": 0.0312}
    assert unmatched_numbers("acc 0.61 and 61.2% and p = 3.12e-02", res) == []
    assert unmatched_numbers("acc 0.73", res) == ["0.73"]


def test_fixture_is_valid():
    validate_results(json.loads(FIXTURE.read_text(encoding="utf-8")))


def _run_report(tmp_path, data_source):
    rep = optional_module("report")
    if rep is None:
        pytest.skip("report.py not on this branch")
    res = json.loads(FIXTURE.read_text(encoding="utf-8"))
    res["meta"]["data_source"] = data_source
    rpath = tmp_path / "results.json"
    rpath.write_text(json.dumps(res), encoding="utf-8")
    md_path = Path(rep.write_report(str(rpath), str(tmp_path)))
    assert md_path.exists()
    return md_path.read_text(encoding="utf-8"), json.loads(rpath.read_text(encoding="utf-8"))


def test_report_on_fixture_has_no_invented_numbers(tmp_path):
    md, res = _run_report(tmp_path, "synthetic")
    bad = unmatched_numbers(md, res)
    assert not bad, f"numbers in results.md not found in results.json: {bad}"
    assert SYNTHETIC_LABEL in md, "synthetic results need the SYNTHETIC - NOT VALID banner"
    assert "Limits" in md
    for name, block in res["models"].items():
        assert name in md, f"model {name} missing from the table"
        target = block["within_subject"]["mean_bal_acc"]
        shown = [float(m.group(1)) for m in NUM.finditer(md)]
        assert any(abs(s - target) <= 0.005 or abs(s - 100 * target) <= 0.5 for s in shown), (
            f"{name} within-subject mean {target} is not reported")
    for fig in FIGURES:
        assert (tmp_path / fig).exists(), f"{fig} missing"


def test_report_physionet_has_no_banner(tmp_path):
    md, _ = _run_report(tmp_path, "physionet")
    assert SYNTHETIC_LABEL not in md


def test_report_on_real_results():
    md_path = REPO / "results" / "results.md"
    js_path = REPO / "results" / "results.json"
    if not (md_path.exists() and js_path.exists()):
        pytest.skip("results/results.md not produced yet")
    res = json.loads(js_path.read_text(encoding="utf-8"))
    md = md_path.read_text(encoding="utf-8")
    bad = unmatched_numbers(md, res)
    assert not bad, f"numbers in results.md not found in results.json: {bad}"
    if res["meta"]["data_source"] == "synthetic":
        assert SYNTHETIC_LABEL in md
