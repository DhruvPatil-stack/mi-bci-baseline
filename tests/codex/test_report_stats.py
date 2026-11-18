"""Check inference against a small hand-calculable paired case."""
from bci.report import compute_stats


def test_zero_differences_and_holm_monotonicity():
    def block(vals):
        return {"within_subject": {"per_subject": {
            str(i): {"bal_acc": v} for i, v in enumerate(vals, 1)}}}

    results = {"models": {
        "csp_lda": block([0.5] * 6),
        "same": block([0.5] * 6),
        "better": block([0.8] * 6),
    }}
    comps = {c["model"]: c for c in compute_stats(results)["comparisons"]}
    assert comps["same"]["p_raw"] == 1.0
    assert comps["same"]["median_diff"] == 0.0
    assert comps["better"]["median_diff"] > 0
    assert comps["better"]["p_raw"] <= comps["better"]["p_holm"] <= 1.0
    assert comps["better"]["p_holm"] <= comps["same"]["p_holm"]
