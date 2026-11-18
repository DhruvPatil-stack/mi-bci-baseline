"""Integration entry point (PRD section 10). Owner: integration.

    python run_all.py [--synthetic] [--out DIR]

Loads data (PhysioNet with the 3-attempt synthetic fallback, or synthetic with --synthetic), evaluates every
registered model with bci.evaluate.run_model (one worker process per model, each with its own config time
budget), writes DIR/results.json, runs bci.report.write_report, runs the feedback simulation, and writes
DIR/README.md (also ./README.md when DIR is the default results/).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent
CACHE = REPO / ".cache"
THREADS_PER_WORKER = "2"


def _set_env():
    """Keep every cache inside the repo and cap BLAS threads per worker (set before numpy/mne import)."""
    for var, sub in (("MPLCONFIGDIR", "mpl"), ("_MNE_FAKE_HOME_DIR", "mne_home"), ("TMP", "tmp"), ("TEMP", "tmp")):
        os.environ.setdefault(var, str(CACHE / sub))
        (CACHE / sub).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("BCI_DATA_DIR", str(CACHE / "mne_data"))
    os.environ.setdefault("MPLBACKEND", "Agg")
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ.setdefault(var, THREADS_PER_WORKER)


_set_env()

import numpy as np  # noqa: E402

MODEL_ORDER = ("csp_lda", "fbcsp_lr", "ts_lr", "eegnet_lite")


def _git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO,
                               capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:  # noqa: BLE001
        return "unknown"


def _worker(args):
    name, X, y, groups, calibration = args
    _set_env()
    from bci import evaluate

    return name, evaluate.run_model(name, X, y, groups, calibration=calibration)


def load(synthetic: bool):
    from bci.contracts import load_config

    cfg = load_config()
    if synthetic:
        from bci.synthetic import make_synthetic

        X, y, groups, _ = make_synthetic()
        return X, y, groups, "synthetic"
    from bci import data

    return data.load_with_fallback(cfg["subjects"], cfg["runs"])


def evaluate_all(X, y, groups, names, calibration_models):
    jobs = [(n, X, y, groups, n in calibration_models) for n in names]
    out = {}
    with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
        for name, block in pool.map(_worker, jobs):
            out[name] = block
            print(f"[run_all] {name}: status {block.get('status')} in {block.get('runtime_s', 0):.1f} s", flush=True)
    return out


N_BOOT = 10000


def _boot_ci(values, rng):
    """Percentile 95% CI of the mean over subjects (resample subjects with replacement)."""
    v = np.asarray(values, dtype=float)
    idx = rng.integers(0, len(v), size=(N_BOOT, len(v)))
    means = v[idx].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def add_bootstrap(cal: dict) -> dict:
    """Add bootstrap 95% CIs across subjects to a calibration block that has per_target.

    ci95_source_plus_target[i], ci95_target_only[i]: CI of the curve mean at k[i].
    vs_zero_shot: per k, paired per-subject differences against the k=0 source-only score of the same subject
    (mean difference and its CI). A curve "beats" zero-shot at k when the CI lower bound is above 0.
    Seeded with SEED; one generator per (k, curve) so the result does not depend on how many k finished.
    """
    from bci.contracts import SEED

    per = cal.get("per_target")
    if not per or cal["k"][0] != 0:
        return cal
    zero = {t: v["source_plus_target"] for t, v in per[0].items()}
    ci_spt, ci_to, vs = [], [], []
    for i, (k, row) in enumerate(zip(cal["k"], per)):
        ts = sorted(row, key=int)
        spt = [row[t]["source_plus_target"] for t in ts]
        ci_spt.append(_boot_ci(spt, np.random.default_rng([SEED, int(k), 0])))
        entry = {"k": int(k), "n_subjects": len(ts)}
        d_spt = [row[t]["source_plus_target"] - zero[t] for t in ts]
        entry["source_plus_target_minus_k0"] = float(np.mean(d_spt))
        entry["ci95_source_plus_target_minus_k0"] = _boot_ci(d_spt, np.random.default_rng([SEED, int(k), 2]))
        if k == 0:
            ci_to.append(None)
        else:
            to = [row[t]["target_only"] for t in ts]
            ci_to.append(_boot_ci(to, np.random.default_rng([SEED, int(k), 1])))
            d_to = [row[t]["target_only"] - zero[t] for t in ts]
            entry["target_only_minus_k0"] = float(np.mean(d_to))
            entry["ci95_target_only_minus_k0"] = _boot_ci(d_to, np.random.default_rng([SEED, int(k), 3]))
        vs.append(entry)
    cal["ci95_source_plus_target"] = ci_spt
    cal["ci95_target_only"] = ci_to
    cal["vs_zero_shot"] = vs
    cal["bootstrap"] = {"n_boot": N_BOOT, "unit": "subject", "interval": "percentile 95%", "seed": SEED}
    return cal


def calibration_only(models_wanted, out_dir: Path):
    """Run only the calibration stage on PhysioNet and merge it into an existing results.json.

    Old numbers are kept: the previous calibration block moves to "calibration_v1" (with its partial flag).
    Uses config calibration_time_budget_min per model (worker process per model).
    """
    from bci import report
    from bci.contracts import g4_check, load_config, validate_results

    cfg = load_config()
    rpath = out_dir / "results.json"
    res = json.loads(rpath.read_text(encoding="utf-8"))
    if res["meta"]["data_source"] != "physionet":
        raise SystemExit("calibration-only mode needs physionet results.json")
    X, y, groups, source = load(False)
    if source != "physionet":
        raise SystemExit("PhysioNet download failed; calibration-only mode refuses synthetic data")
    budget = float(cfg["calibration_time_budget_min"])
    jobs = [(n, X, y, groups, budget) for n in models_wanted]
    with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
        outs = list(pool.map(_calib_worker, jobs))
    for name, out in outs:
        block = res["models"][name]
        if "calibration" in block:
            v1 = block.pop("calibration")
            v1["partial"] = bool(block.pop("calibration_partial", False))
            v1["calibration_repeats"] = 10
            block["calibration_v1"] = v1
        if "calibration" in out:
            block["calibration"] = add_bootstrap(out["calibration"])
        block["calibration_partial"] = out["calibration_partial"]
        block["calibration_status"] = out["status"]
        block["calibration_runtime_s"] = out["runtime_s"]
        if out.get("error"):
            block["calibration_error"] = out["error"]
        print(f"[run_all] calibration {name}: {out['status']} in {out['runtime_s']:.1f} s", flush=True)
    res["meta"]["calibration_run"] = {
        "git_commit": _git_commit(), "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        "calibration_repeats": int(cfg["calibration_repeats"]), "calibration_time_budget_min": budget,
        "models": list(models_wanted)}
    validate_results(res)
    rpath.write_text(json.dumps(res, indent=2), encoding="utf-8")
    report.write_report(str(rpath), str(out_dir))
    fails, warns = g4_check(res)
    fb = {"png": "feedback.png", "subject": int(res["meta"]["subjects"][0])}
    write_readme(out_dir / "README.md", res, fails, warns, fb)
    if out_dir == (REPO / "results").resolve():
        write_readme(REPO / "README.md", res, fails, warns, fb)
    return 0


def _calib_worker(args):
    name, X, y, groups, budget = args
    _set_env()
    from bci import evaluate

    return name, evaluate.run_calibration(name, X, y, groups, budget)


def feedback(X, y, groups, out_dir: Path, source: str):
    """Fit the config feedback model on all subjects but the first and replay one trial of the first."""
    from bci.contracts import SFREQ, load_config
    from bci.evaluate import _registry
    from bci.feedback_sim import simulate_feedback

    cfg = load_config()
    first = int(np.unique(groups)[0])
    train = groups != first
    est = _registry()[cfg["feedback_model"]]().fit(X[train], y[train])
    idx = int(np.flatnonzero(groups == first)[0])
    png = out_dir / "feedback.png"
    simulate_feedback(est, X[idx], SFREQ, str(png))
    return {"png": png.name, "subject": first, "trial_index": idx, "trial_label": int(y[idx])}


def write_readme(path: Path, res: dict, g4_fails, g4_warns, fb):
    syn = res["meta"]["data_source"] == "synthetic"
    lines = []
    if syn:
        lines += ["# SYNTHETIC - NOT VALID", "", "These outputs come from synthetic data. They are not results.", ""]
    lines += [
        "# Motor imagery BCI v0.2 (CSP, FBCSP, tangent space, EEGNet-lite)",
        "",
        "Decodes imagined left fist vs right fist from EEG. Healthy subjects (PhysioNet EEG Motor",
        "Movement/Imagery, runs 4, 8, 12). This is not a stroke cohort and not a medical device. No clinical claim.",
        "AI agents (Claude Code and Codex) wrote this code.",
        "",
        "Run: `python run_all.py` (PhysioNet) or `python run_all.py --synthetic`. Results: `results.json`,",
        "`results.md`, figures, `feedback.png`. Every reported number comes from `results.json`.",
        "",
        f"Data source: `{res['meta']['data_source']}`. Commit: `{res['meta']['git_commit']}`.",
        "",
        "## Model status",
        "",
    ]
    for name, block in res["models"].items():
        extra = " (partial calibration curve)" if block.get("calibration_partial") else ""
        err = f": {block['error']}" if block.get("error") else ""
        lines.append(f"- `{name}`: {block.get('status', 'ok')}{extra}{err}")
    lines += ["", "## Finished blocks (from results.json, including models that timed out)", "",
              "Balanced accuracy. A model with status timeout keeps the blocks it finished before the budget ran out.",
              "", "| Model | Status | Within mean (std) | Cross mean (std) | Permutation within / cross | Calibration k done |",
              "|---|---|---|---|---|---|"]
    for name, block in res["models"].items():
        w, c, p, cal = (block.get(k) for k in ("within_subject", "cross_subject", "permutation", "calibration"))
        lines.append(
            f"| {name} | {block.get('status', 'ok')} "
            f"| {f'{w['mean_bal_acc']:.4f} ({w['std_bal_acc']:.4f})' if w else 'not finished'} "
            f"| {f'{c['mean_bal_acc']:.4f} ({c['std_bal_acc']:.4f})' if c else 'not finished'} "
            f"| {f'{p['within_mean_bal_acc']:.4f} / {p['cross_mean_bal_acc']:.4f}' if p else 'not finished'} "
            f"| {cal['k'] if cal else 'none'} |")
    lines += ["", "## Gate G4 (plausibility, physionet only)", ""]
    if res["meta"]["data_source"] != "physionet":
        lines.append("Not applicable: synthetic data.")
    else:
        lines += [f"- FAIL: {f}" for f in g4_fails] or ["- No G4 failure."]
        lines += [f"- WARNING: {w}" for w in g4_warns] or ["- No G4 warning."]
        lines.append("")
        lines.append("The G4 ranges are plausibility limits from general experience, not published values.")
    lines += ["", "## Feedback simulation", "",
              f"`{fb['png']}`: one trial of subject `{fb['subject']}` replayed through the feedback model."
              if fb else "Feedback simulation did not run.", "",
              "## Data and citations", "",
              "PhysioNet data is open. Schalk et al., 2004 (BCI2000). Goldberger et al., 2000 (PhysioNet).", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", default=str(REPO / "results"))
    ap.add_argument("--calibration-only", nargs="+", metavar="MODEL",
                    help="run only the calibration stage for these models and merge into OUT/results.json")
    args = ap.parse_args(argv)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.calibration_only:
        return calibration_only(args.calibration_only, out_dir)

    from bci.contracts import SEED, SYNTHETIC_LABEL, g4_check, load_config, validate_results
    from bci.evaluate import _registry

    cfg = load_config()
    X, y, groups, source = load(args.synthetic)
    print(f"[run_all] data {source}: X {X.shape} {X.dtype}, subjects {len(np.unique(groups))}", flush=True)
    if source == "synthetic":
        print(f"[run_all] {SYNTHETIC_LABEL}", flush=True)
    reg = _registry()
    names = [n for n in MODEL_ORDER if n in reg] + sorted(n for n in reg if n not in MODEL_ORDER)
    models = evaluate_all(X, y, groups, names, set(cfg["calibration_models"]))

    for b in models.values():
        if "calibration" in b:
            add_bootstrap(b["calibration"])
    runtime = {n: float(b.pop("runtime_s", 0.0)) for n, b in models.items()}
    res = {
        "meta": {"data_source": source, "seed": SEED, "subjects": [int(s) for s in np.unique(groups)],
                 "git_commit": _git_commit(), "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
                 "n_trials": int(len(y))},
        "models": models,
        "runtime_s": runtime,
    }
    if source == "synthetic":
        res["meta"]["label"] = SYNTHETIC_LABEL
    from bci import report

    res["stats"] = report.compute_stats(res)
    validate_results(res)
    rpath = out_dir / "results.json"
    rpath.write_text(json.dumps(res, indent=2), encoding="utf-8")
    md = report.write_report(str(rpath), str(out_dir))
    print(f"[run_all] report {md}", flush=True)

    fb = None
    try:
        fb = feedback(X, y, groups, out_dir, source)
    except Exception as exc:  # noqa: BLE001
        print(f"[run_all] feedback simulation failed: {exc!r}", file=sys.stderr, flush=True)
    g4_fails, g4_warns = g4_check(res)
    write_readme(out_dir / "README.md", res, g4_fails, g4_warns, fb)
    if out_dir == (REPO / "results").resolve():
        write_readme(REPO / "README.md", res, g4_fails, g4_warns, fb)
    for f in g4_fails:
        print(f"[run_all] G4 FAIL: {f}", flush=True)
    for w in g4_warns:
        print(f"[run_all] G4 WARNING: {w}", flush=True)
    print("[run_all] done", flush=True)
    return 1 if fb is None else 0


if __name__ == "__main__":
    sys.exit(main())
