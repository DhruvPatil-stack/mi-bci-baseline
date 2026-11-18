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
    args = ap.parse_args(argv)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

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
