"""Measured model comparison, paired statistics, and report figures."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

from bci.contracts import BASELINE_MODEL, SYNTHETIC_LABEL, validate_results


def compute_stats(results):
    """Paired within-subject Wilcoxon tests on every available subject block."""
    models = results["models"]
    base = models.get(BASELINE_MODEL)
    if base is None or "within_subject" not in base:
        return {"comparisons": [], "test": "wilcoxon signed-rank, within-subject per-subject bal_acc, Holm"}
    baseline = base["within_subject"]["per_subject"]
    comps = []
    for name, block in models.items():
        if name == BASELINE_MODEL or "within_subject" not in block:
            continue
        other = block["within_subject"]["per_subject"]
        ids = sorted(set(baseline) & set(other), key=int)
        if not ids:
            continue
        differences = np.array([other[s]["bal_acc"] - baseline[s]["bal_acc"] for s in ids])
        p_raw = 1.0 if np.all(differences == 0) else float(wilcoxon(differences).pvalue)
        comps.append({"model": name, "vs": BASELINE_MODEL,
                      "median_diff": float(np.median(differences)), "p_raw": p_raw,
                      "n_subjects": len(ids),
                      "partial": (base.get("status", "ok") != "ok" or block.get("status", "ok") != "ok")})
    order = sorted(range(len(comps)), key=lambda i: comps[i]["p_raw"])
    adjusted = 0.0
    for rank, i in enumerate(order):
        adjusted = max(adjusted, min(1.0, (len(comps) - rank) * comps[i]["p_raw"]))
        comps[i]["p_holm"] = adjusted
    return {"comparisons": comps, "test": "wilcoxon signed-rank, within-subject per-subject bal_acc, Holm"}


def _figures(results, out_dir):
    import matplotlib.pyplot as plt

    models = list(results["models"].items())
    names = [f"{n} ({b.get('status', 'ok')})" for n, b in models]
    x = np.arange(len(names))
    synthetic = results["meta"]["data_source"] == "synthetic"

    def save(fig, filename):
        if synthetic:
            fig.suptitle(SYNTHETIC_LABEL, color="darkred", fontweight="bold")
        fig.tight_layout()
        fig.savefig(out_dir / filename, dpi=150)
        plt.close(fig)

    def block_value(block, section, field):
        sub = block.get(section)
        return np.nan if sub is None else sub[field]

    fig, ax = plt.subplots(figsize=(8, 4))
    for shift, section, label in ((-0.18, "within_subject", "Within subject"),
                                  (0.18, "cross_subject", "Cross subject")):
        means = [block_value(b, section, "mean_bal_acc") for _, b in models]
        stds = [block_value(b, section, "std_bal_acc") for _, b in models]
        ax.bar(x + shift, means, 0.36, yerr=stds, label=label, capsize=3)
    ax.set(xticks=x, xticklabels=names, ylabel="Balanced accuracy", ylim=(0, 1), title="Model comparison")
    if models:
        ax.legend()
    save(fig, "fig1_models.png")

    fig, ax = plt.subplots(figsize=(8, 4))
    for name, block in models:
        cal = block.get("calibration")
        if cal:
            tag = f"{name} ({block.get('status', 'ok')})"
            ax.plot(cal["k"], cal["source_plus_target"], marker="o", label=f"{tag}: source + target")
            ax.plot(cal["k"], [np.nan if v is None else v for v in cal["target_only"]],
                    marker="x", linestyle="--", label=f"{tag}: target only")
    ax.set(xlabel="Calibration trials per target subject", ylabel="Balanced accuracy", ylim=(0, 1),
           title="Calibration curves")
    if ax.lines:
        ax.legend(fontsize=8)
    save(fig, "fig2_calibration.png")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x - 0.18, [block_value(b, "permutation", "within_mean_bal_acc") for _, b in models],
           0.36, label="Within subject")
    ax.bar(x + 0.18, [block_value(b, "permutation", "cross_mean_bal_acc") for _, b in models],
           0.36, label="Cross subject")
    ax.axhline(0.5, color="black", linestyle="--", linewidth=1, label="Chance")
    ax.set(xticks=x, xticklabels=names, ylabel="Balanced accuracy after label permutation",
           ylim=(0, 1), title="Permutation control")
    if models:
        ax.legend()
    save(fig, "fig3_permutation.png")


def write_report(results_path, out_dir):
    """Write Markdown and three figures from a results JSON file; return Markdown path."""
    source = Path(results_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = json.loads(source.read_text(encoding="utf-8"))
    validate_results({**results, "stats": results.get("stats", {"comparisons": []})})
    results["stats"] = compute_stats(results)
    subjects = results["meta"]["subjects"]
    n_trials = results["meta"].get("n_trials")
    if n_trials is not None and subjects:
        results["meta"]["mean_trials_per_subject"] = n_trials / len(subjects)
    validate_results(results)
    source.write_text(json.dumps(results, indent=2), encoding="utf-8")

    def metric_cell(block, section, count_key):
        part = block.get(section)
        if part is None:
            return "—"
        count = len(part[count_key])
        return f"{part['mean_bal_acc']:.4f} ± {part['std_bal_acc']:.4f} (n={count})"

    def perm_cell(block, key):
        part = block.get("permutation")
        return "—" if part is None else f"{part[key]:.4f}"

    def p_text(value):
        return f"{value:.2e}" if value < 1e-4 else f"{value:.4f}"

    lines = ["# Motor imagery model results", ""]
    if results["meta"]["data_source"] == "synthetic":
        lines += [f"**{SYNTHETIC_LABEL}**", ""]
    lines += ["Balanced accuracy, mean ± standard deviation. Counts are the number of finished "
              "subjects or folds (`len(per_subject)` or `len(per_fold)`). A status of partial means "
              "the model did not finish all evaluation steps.", "",
              "| Model | Status | Within subject | Cross subject | Permuted within | Permuted cross | Calibration k completed |",
              "|---|---|---:|---:|---:|---:|---|"]
    for name, block in results["models"].items():
        status = block.get("status", "ok")
        if status != "ok" and any(k in block for k in ("within_subject", "cross_subject", "permutation", "calibration")):
            status = f"partial ({status})"
        cal = block.get("calibration")
        ks = ", ".join(map(str, cal["k"])) if cal else "—"
        lines.append(f"| {name} | {status} | {metric_cell(block, 'within_subject', 'per_subject')} | "
                     f"{metric_cell(block, 'cross_subject', 'per_fold')} | "
                     f"{perm_cell(block, 'within_mean_bal_acc')} | "
                     f"{perm_cell(block, 'cross_mean_bal_acc')} | {ks} |")
    lines += ["", "## Calibration values", "",
              "Only completed calibration points are shown. Scores are balanced accuracy.", "",
              "| Model | Status | k | Source + target | Target only |", "|---|---|---:|---:|---:|"]
    for name, block in results["models"].items():
        cal = block.get("calibration")
        if not cal:
            continue
        status = block.get("status", "ok")
        for k, source_score, target_score in zip(cal["k"], cal["source_plus_target"], cal["target_only"]):
            target_text = "—" if target_score is None else f"{target_score:.4f}"
            lines.append(f"| {name} | {status} | {k} | {source_score:.4f} | {target_text} |")
    lines += ["", "## Paired comparisons", "",
              "Wilcoxon signed-rank on matched within-subject balanced accuracies; "
              "median difference is model minus csp_lda. Holm step-down adjusts p-values "
              f"across the {len(results['stats']['comparisons'])} available comparisons. "
              "A partial label means at least one model did not finish all evaluation steps.", "",
              "| Model | Shared subjects | Median difference | Raw p | Holm p |", "|---|---:|---:|---:|---:|"]
    for comp in results["stats"]["comparisons"]:
        label = comp["model"] + (" (partial)" if comp["partial"] else "")
        lines.append(f"| {label} | {comp['n_subjects']} | {comp['median_diff']:.4f} | "
                     f"{p_text(comp['p_raw'])} | {p_text(comp['p_holm'])} |")
    if not results["stats"]["comparisons"]:
        lines += ["", "No paired comparison is available because the baseline or other models "
                  "lack a shared within-subject results block."]
    n_subjects = len(subjects)
    if n_trials is None:
        cohort = f"The results metadata lists {n_subjects} subjects; trial count is unavailable."
    else:
        average = results["meta"]["mean_trials_per_subject"]
        average_text = str(int(average)) if float(average).is_integer() else f"{average:.4f}"
        cohort = (f"The results metadata lists {n_subjects} subjects and {n_trials} total trials, "
                  f"or {average_text} trials per subject on average (total trials / subjects).")
    if results["meta"]["data_source"] == "physionet":
        cohort += " The subjects are healthy volunteers."
    else:
        cohort += " These are synthetic subjects and trials."
    lines += ["", "## Figures", "", "![Model comparison](fig1_models.png)", "",
              "![Calibration curves](fig2_calibration.png)", "",
              "![Permutation control](fig3_permutation.png)", "", "## Limits", "",
              cohort + " Statistical power is limited by the cohort size. These results do not "
              "establish clinical benefit or performance for a stroke cohort.", ""]
    md = out / "results.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    _figures(results, out)
    return str(md)
