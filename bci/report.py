"""Measured model comparison, paired statistics, and report figures."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

from bci.contracts import BASELINE_MODEL, SYNTHETIC_LABEL, validate_results


def compute_stats(results):
    """Paired within-subject Wilcoxon tests with Holm step-down correction."""
    models = results["models"]
    base = models.get(BASELINE_MODEL)
    if base is None or base.get("status", "ok") != "ok":
        return {"comparisons": [], "test": "wilcoxon signed-rank, within-subject per-subject bal_acc, Holm"}
    baseline = base["within_subject"]["per_subject"]
    comps = []
    for name, block in models.items():
        if name == BASELINE_MODEL or block.get("status", "ok") != "ok":
            continue
        other = block["within_subject"]["per_subject"]
        ids = sorted(set(baseline) & set(other), key=int)
        if not ids:
            continue
        differences = np.array([other[s]["bal_acc"] - baseline[s]["bal_acc"] for s in ids])
        p_raw = 1.0 if np.all(differences == 0) else float(wilcoxon(differences).pvalue)
        comps.append({"model": name, "vs": BASELINE_MODEL,
                      "median_diff": float(np.median(differences)), "p_raw": p_raw})
    order = sorted(range(len(comps)), key=lambda i: comps[i]["p_raw"])
    adjusted = 0.0
    for rank, i in enumerate(order):
        adjusted = max(adjusted, min(1.0, (len(comps) - rank) * comps[i]["p_raw"]))
        comps[i]["p_holm"] = adjusted
    return {"comparisons": comps, "test": "wilcoxon signed-rank, within-subject per-subject bal_acc, Holm"}


def _figures(results, out_dir):
    import matplotlib.pyplot as plt

    models = [(n, b) for n, b in results["models"].items() if b.get("status", "ok") == "ok"]
    names = [n for n, _ in models]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8, 4))
    w = [b["within_subject"] for _, b in models]
    c = [b["cross_subject"] for _, b in models]
    ax.bar(x - 0.18, [b["mean_bal_acc"] for b in w], 0.36,
           yerr=[b["std_bal_acc"] for b in w], label="Within subject", capsize=3)
    ax.bar(x + 0.18, [b["mean_bal_acc"] for b in c], 0.36,
           yerr=[b["std_bal_acc"] for b in c], label="Cross subject", capsize=3)
    ax.set(xticks=x, xticklabels=names, ylabel="Balanced accuracy", ylim=(0, 1), title="Model comparison")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig1_models.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for name, block in models:
        cal = block.get("calibration")
        if cal:
            ax.plot(cal["k"], cal["source_plus_target"], marker="o", label=f"{name}: source + target")
            ax.plot(cal["k"], [np.nan if v is None else v for v in cal["target_only"]],
                    marker="x", linestyle="--", label=f"{name}: target only")
    ax.set(xlabel="Calibration trials per target subject", ylabel="Balanced accuracy", ylim=(0, 1),
           title="Calibration curves")
    if ax.lines:
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig2_calibration.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x - 0.18, [b["permutation"]["within_mean_bal_acc"] for _, b in models],
           0.36, label="Within subject")
    ax.bar(x + 0.18, [b["permutation"]["cross_mean_bal_acc"] for _, b in models],
           0.36, label="Cross subject")
    ax.axhline(0.5, color="black", linestyle="--", linewidth=1, label="Chance")
    ax.set(xticks=x, xticklabels=names, ylabel="Balanced accuracy after label permutation",
           ylim=(0, 1), title="Permutation control")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig3_permutation.png", dpi=150)
    plt.close(fig)


def write_report(results_path, out_dir):
    """Write Markdown and three figures from a results JSON file; return Markdown path."""
    source = Path(results_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = json.loads(source.read_text(encoding="utf-8"))
    if "stats" not in results:
        results["stats"] = compute_stats(results)
        source.write_text(json.dumps(results, indent=2), encoding="utf-8")
    validate_results(results)
    lines = ["# Motor imagery model results", ""]
    if results["meta"]["data_source"] == "synthetic":
        lines += [f"**{SYNTHETIC_LABEL}**", ""]
    lines += ["Balanced accuracy, mean ± standard deviation:", "",
              "| Model | Within subject | Cross subject |", "|---|---:|---:|"]
    for name, block in results["models"].items():
        if block.get("status", "ok") != "ok":
            lines.append(f"| {name} | {block['status']} | {block['status']} |")
            continue
        w, c = block["within_subject"], block["cross_subject"]
        lines.append(f"| {name} | {w['mean_bal_acc']:.4f} ± {w['std_bal_acc']:.4f} | "
                     f"{c['mean_bal_acc']:.4f} ± {c['std_bal_acc']:.4f} |")
    lines += ["", "## Paired comparisons", "",
              "Wilcoxon signed-rank on matched within-subject balanced accuracies; "
              "median difference is model minus csp_lda. Holm step-down adjusts p-values.", "",
              "| Model | Median difference | Raw p | Holm p |", "|---|---:|---:|---:|"]
    for comp in results["stats"]["comparisons"]:
        lines.append(f"| {comp['model']} | {comp['median_diff']:.4f} | "
                     f"{comp['p_raw']:.4f} | {comp['p_holm']:.4f} |")
    lines += ["", "## Figures", "", "![Model comparison](fig1_models.png)", "",
              "![Calibration curves](fig2_calibration.png)", "",
              "![Permutation control](fig3_permutation.png)", "", "## Limits", "",
              "The intended PhysioNet cohort contains 20 healthy subjects with about 45 trials each. "
              "Statistical power is low. These results do not establish clinical benefit or performance "
              "for a stroke cohort.", ""]
    md = out / "results.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    _figures(results, out)
    return str(md)
