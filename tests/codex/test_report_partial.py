"""Regression checks for reports with unfinished, but measured, models."""
import json
import re
from pathlib import Path

from bci.report import write_report


FIXTURE = Path(__file__).resolve().parents[1] / "locked" / "fixtures" / "results_fixture.json"


def test_partial_blocks_and_source_metadata_are_visible(tmp_path, monkeypatch):
    from matplotlib.figure import Figure

    result = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result["meta"]["n_trials"] = 240
    result["models"]["csp_lda"]["status"] = "timeout"
    result["models"]["ts_lr"]["status"] = "error"
    result["models"]["eegnet_lite"]["status"] = "timeout"
    del result["models"]["eegnet_lite"]["cross_subject"]
    del result["models"]["eegnet_lite"]["permutation"]
    del result["stats"]
    titles = []
    original = Figure.suptitle

    def record(self, title, *args, **kwargs):
        titles.append(title)
        return original(self, title, *args, **kwargs)

    monkeypatch.setattr(Figure, "suptitle", record)
    path = tmp_path / "results.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    md = Path(write_report(path, tmp_path)).read_text(encoding="utf-8")
    assert "csp_lda | partial (timeout) | 0.6849" in md
    assert "ts_lr | partial (error) | 0.6966" in md
    assert "eegnet_lite | partial (timeout) | 0.6642" in md
    assert "0, 4, 8, 16, 24" in md
    assert "6 subjects and 240 total trials" in md
    assert "20 healthy subjects" not in md
    assert "No paired comparison is available" in md
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["stats"]["comparisons"] == []
    assert "mean_trials_per_subject" not in saved["meta"]
    assert len(titles) == 3 and set(titles) == {"SYNTHETIC - NOT VALID"}


def test_small_p_values_use_scientific_notation(tmp_path):
    result = json.loads(FIXTURE.read_text(encoding="utf-8"))
    baseline = result["models"]["csp_lda"]["within_subject"]["per_subject"]
    target = result["models"]["ts_lr"]["within_subject"]["per_subject"]
    for i in range(1, 21):
        baseline[str(i)] = {"acc": 0.5, "bal_acc": 0.5, "kappa": 0.0}
        target[str(i)] = {"acc": 0.6, "bal_acc": 0.6, "kappa": 0.2}
    result["meta"]["subjects"] = list(range(1, 21))
    del result["stats"]
    path = tmp_path / "results.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    md = Path(write_report(path, tmp_path)).read_text(encoding="utf-8")
    comparisons = md.split("## Paired comparisons", 1)[1]
    row = next(line for line in comparisons.splitlines() if line.startswith("| ts_lr |"))
    assert re.search(r"\d\.\d+e-\d+", row)
    assert "0.0000" not in row


def test_existing_stats_and_metadata_are_not_rewritten(tmp_path):
    original = FIXTURE.read_text(encoding="utf-8")
    path = tmp_path / "results.json"
    path.write_text(original, encoding="utf-8")
    write_report(path, tmp_path)
    assert path.read_text(encoding="utf-8") == original
