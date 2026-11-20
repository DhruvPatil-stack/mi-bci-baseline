"""Integration entry point v0.3 (PRD_v0.3 section 10). Owner: integration.

    python run_all.py [--synthetic] [--dataset physionet|stroke] [--out DIR] [--fresh]

Loads data (PhysioNet with the 3-attempt synthetic fallback; synthetic with --synthetic; the Liu et al. 2024
stroke data with --dataset stroke, never a fallback), evaluates every registered model with
bci.evaluate.run_model (one worker process per model, a checkpoint file per model under DIR/checkpoints, so a
rerun skips finished stages), writes DIR/results.json after each finished model, then the responder analysis
and the ERD check (only when bci.analysis / bci.erd_check exist; otherwise recorded as "not measured"),
bci.report.write_report, the feedback simulation, and DIR/README.md (also ./README.md for the default results/).
Healthy (PhysioNet) and stroke results are written to separate folders (default results/ and results/stroke/).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
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
    name, X, y, groups, calibration, checkpoint = args
    _set_env()
    from bci import evaluate

    return name, evaluate.run_model(name, X, y, groups, calibration=calibration, checkpoint=checkpoint)


def load(synthetic: bool, dataset: str = "physionet"):
    """(X, y, groups, source). Stroke never falls back to another source."""
    from bci.contracts import load_config

    cfg = load_config()
    if synthetic:
        from bci.synthetic import make_synthetic

        X, y, groups, _ = make_synthetic()
        return X, y, groups, "synthetic"
    if dataset == "stroke":
        from bci import data_stroke

        X, y, groups = data_stroke.load_stroke()
        return X, y, groups, "stroke"
    from bci import data

    return data.load_with_fallback(cfg["subjects"], cfg["runs"])


def _optional(name):
    """bci.<name> or None when the file does not exist (Codex modules may be missing)."""
    if not (REPO / "bci" / f"{name}.py").exists():
        return None
    return importlib.import_module(f"bci.{name}")


def _write_results(rpath: Path, res: dict):
    tmp = rpath.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(res, indent=2), encoding="utf-8")
    os.replace(tmp, rpath)


def evaluate_all(X, y, groups, names, calibration_models, ck_dir: Path, on_model=None):
    jobs = [(n, X, y, groups, n in calibration_models, str(ck_dir / f"{n}.json")) for n in names]
    out = {}
    with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
        futs = [pool.submit(_worker, j) for j in jobs]
        for fut in as_completed(futs):
            name, block = fut.result()
            out[name] = block
            print(f"[run_all] {name}: status {block.get('status')} in {block.get('runtime_s', 0):.1f} s", flush=True)
            if on_model is not None:
                on_model(dict(out))
    return {n: out[n] for n in names if n in out}


# ------------------------------------------------------------------ responder analysis and ERD check (Codex modules)
def _pvalue_worker(args):
    sid, Xs, ys, n_perm, seed, dataset = args
    _set_env()
    os.environ["BCI_DATASET"] = dataset
    from bci import analysis, evaluate

    factory = evaluate._registry()["csp_lda"]
    return sid, analysis.subject_pvalue(factory, Xs, ys, n_perm, seed)


def heterogeneity(X, y, groups, models: dict, dataset: str, n_workers: int = 4) -> dict:
    """Responder rule (PRD_v0.3 section 4) and ERD lateralization. Needs bci.analysis / bci.erd_check."""
    from bci import channels
    from bci.contracts import SEED, dataset_spec, load_config

    cfg = load_config()
    out = {}
    an = _optional("analysis")
    erd = _optional("erd_check")
    base = models.get("csp_lda", {})
    within = (base.get("within_subject") or {}).get("per_subject")
    if an is None:
        out["responders"] = {"status": "not measured",
                             "reason": "bci/analysis.py not on this branch (Codex ticket H1 not delivered)"}
    elif within is None:
        out["responders"] = {"status": "not measured", "reason": "csp_lda within_subject block missing"}
    else:
        try:
            n_perm = int(cfg["n_permutations_subject"])
            jobs = [(str(int(s)), X[groups == s], y[groups == s], n_perm, int(SEED) + int(s), dataset)
                    for s in np.unique(groups)]
            pv = {}
            with ProcessPoolExecutor(max_workers=n_workers) as pool:
                for sid, r in pool.map(_pvalue_worker, jobs):
                    pv[sid] = r
            cls = an.classify_responders({s: r["p"] for s, r in pv.items()}, float(cfg["responder_alpha"]))
            per_subject = {s: {"obs": float(pv[s]["obs"]), "p": float(pv[s]["p"]), "responder": bool(cls["flags"][s]),
                               "within_bal_acc_csp_lda": float(within[s]["bal_acc"]) if s in within else None}
                           for s in sorted(pv, key=int)}
            mismatch = [s for s, v in per_subject.items() if v["within_bal_acc_csp_lda"] is not None
                        and abs(v["obs"] - v["within_bal_acc_csp_lda"]) > 1e-9]
            resp = {"status": "ok", "model": "csp_lda", "n_perm": n_perm, "alpha": float(cfg["responder_alpha"]),
                    "per_subject": per_subject, "count": int(cls["count"]), "n": int(cls["n"]),
                    "ci95_proportion": [float(v) for v in cls["ci95"]],
                    "expected_false_positives": float(cls["expected_false_positives"]),
                    "obs_matches_within_block": not mismatch, "obs_mismatch_subjects": mismatch}
            cal = base.get("calibration")
            if cal and cal.get("per_target"):
                resp["calibration_gain"] = an.calibration_gain_by_group(cal["per_target"], cls["flags"], cal["k"],
                                                                        n_boot=10000, seed=SEED)
            else:
                resp["calibration_gain"] = {"status": "not measured", "reason": "csp_lda calibration block missing"}
            out["responders"] = resp
        except Exception as exc:  # noqa: BLE001 - recorded, never hidden
            out["responders"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
    if erd is None:
        out["erd"] = {"status": "not measured",
                      "reason": "bci/erd_check.py not on this branch (Codex ticket H2 not delivered)"}
    else:
        try:
            ch = channels.MOTOR["stroke" if dataset == "stroke" else "physionet"]
            sf = dataset_spec("stroke" if dataset == "stroke" else "physionet")["sfreq"]
            ls_mu = erd.lateralization(X, y, groups, sf, ch["C3"], ch["C4"], cfg["erd_band_mu"])
            ls_beta = erd.lateralization(X, y, groups, sf, ch["C3"], ch["C4"], cfg["erd_band_beta"])
            acc = {s: float(v["bal_acc"]) for s, v in (within or {}).items()}
            out["erd"] = {"status": "ok", "channels": {"C3": ch["C3"], "C4": ch["C4"]},
                          "band_mu": list(cfg["erd_band_mu"]), "band_beta": list(cfg["erd_band_beta"]),
                          "ls_mu": ls_mu, "ls_beta": ls_beta,
                          "n_ls_mu_negative": int(sum(v < 0 for v in ls_mu.values())),
                          "ls_mu_vs_csp_lda_within": erd.lateralization_vs_accuracy(ls_mu, acc) if acc else None}
        except Exception as exc:  # noqa: BLE001
            out["erd"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
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
    from bci.contracts import dataset_spec, load_config
    from bci.evaluate import _registry
    from bci.feedback_sim import simulate_feedback

    cfg = load_config()
    first = int(np.unique(groups)[0])
    train = groups != first
    est = _registry()[cfg["feedback_model"]]().fit(X[train], y[train])
    idx = int(np.flatnonzero(groups == first)[0])
    png = out_dir / "feedback.png"
    simulate_feedback(est, X[idx], dataset_spec()["sfreq"], str(png))
    return {"png": png.name, "subject": first, "trial_index": idx, "trial_label": int(y[idx])}


def _fmt_ci(ci):
    return f"[{ci[0]:.4f}, {ci[1]:.4f}]"


def write_readme(path: Path, res: dict, g4_fails, g4_warns, fb):
    src = res["meta"]["data_source"]
    syn = src == "synthetic"
    lines = []
    if syn:
        lines += ["# SYNTHETIC - NOT VALID", "", "These outputs come from synthetic data. They are not results.", ""]
    cohort = ("Acute stroke patients (Liu et al., Scientific Data 2024, CC BY 4.0)." if src == "stroke" else
              "Healthy subjects (PhysioNet EEG Motor Movement/Imagery, runs 4, 8, 12).")
    lines += [
        "# Motor imagery BCI v0.3 (CSP, FBCSP, tangent space, EEGNet-lite)",
        "",
        f"Decodes imagined left vs right hand movement from EEG. This folder: {cohort}",
        "Healthy-subject and stroke-patient results are kept in separate folders (`results/` and `results/stroke/`).",
        "Not a medical device. No clinical claim. AI agents (Claude Code and Codex) wrote this code.",
        "",
        "Run: `python run_all.py` (PhysioNet), `python run_all.py --dataset stroke --out results/stroke`, or",
        "`python run_all.py --synthetic`. Every reported number comes from `results.json` in the same folder.",
        "",
        f"Data source: `{src}`. Commit: `{res['meta']['git_commit']}`.",
        "",
        "## Model status",
        "",
    ]
    for name, block in res["models"].items():
        extra = " (partial calibration curve)" if block.get("calibration_partial") else ""
        err = f": {block['error']}" if block.get("error") else ""
        lines.append(f"- `{name}`: {block.get('status', 'ok')}{extra}{err}")
    lines += ["", "## Blocks (from results.json)", "",
              "Balanced accuracy.", "",
              "| Model | Status | Within mean (std) | Cross mean (std) | Permutation within / cross | Calibration k done |",
              "|---|---|---|---|---|---|"]
    for name, block in res["models"].items():
        w, c, p, cal = (block.get(k) for k in ("within_subject", "cross_subject", "permutation", "calibration"))
        ws = f"{w['mean_bal_acc']:.4f} ({w['std_bal_acc']:.4f})" if w else "not finished"
        cs = f"{c['mean_bal_acc']:.4f} ({c['std_bal_acc']:.4f})" if c else "not finished"
        ps = f"{p['within_mean_bal_acc']:.4f} / {p['cross_mean_bal_acc']:.4f}" if p else "not finished"
        lines.append(f"| {name} | {block.get('status', 'ok')} | {ws} | {cs} | {ps} | {cal['k'] if cal else 'none'} |")
    het = res.get("heterogeneity", {})
    lines += ["", "## Responders and ERD check", ""]
    r = het.get("responders", {})
    if r.get("status") == "ok":
        lines.append(f"Responders (csp_lda, {r['n_perm']} label shuffles, p < {r['alpha']}): {r['count']} of {r['n']}, "
                     f"95% Clopper-Pearson interval of the proportion {_fmt_ci(r['ci95_proportion'])}; "
                     f"expected false responders {r['expected_false_positives']:.2f}.")
    else:
        lines.append(f"Responders: {r.get('status', 'not measured')} ({r.get('reason') or r.get('error', '')}).")
    e = het.get("erd", {})
    if e.get("status") == "ok" and e.get("ls_mu_vs_csp_lda_within"):
        sp = e["ls_mu_vs_csp_lda_within"]
        lines.append(f"ERD lateralization (mu): LS < 0 in {e['n_ls_mu_negative']} of {len(e['ls_mu'])} subjects; "
                     f"Spearman rho vs csp_lda within score {sp['rho']:.4f}, p {sp['p']:.4f}, n {sp['n']}.")
    else:
        lines.append(f"ERD check: {e.get('status', 'not measured')} ({e.get('reason') or e.get('error', '')}).")
    lines += ["", "## Gate G4 (plausibility, physionet only)", ""]
    if src != "physionet":
        lines.append(f"Not applicable: data source {src}.")
    else:
        lines += [f"- FAIL: {f}" for f in g4_fails] or ["- No G4 failure."]
        lines += [f"- WARNING: {w}" for w in g4_warns] or ["- No G4 warning."]
        lines.append("")
        lines.append("The G4 ranges are plausibility limits from general experience, not published values.")
    lines += ["", "## Feedback simulation", "",
              f"`{fb['png']}`: one trial of subject `{fb['subject']}` replayed through the feedback model."
              if fb else "Feedback simulation did not run.", "",
              "## Data and citations", "",
              "PhysioNet data is open. Schalk et al., 2004 (BCI2000). Goldberger et al., 2000 (PhysioNet).",
              "Stroke data: Liu et al., An EEG motor imagery dataset for brain computer interface in acute stroke "
              "patients, Scientific Data 11, 131 (2024), CC BY 4.0. Raw data is not redistributed here.",
              "Code license: MIT (`LICENSE`).", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _meta(source, groups, y, dataset):
    from bci.contracts import SEED, SYNTHETIC_LABEL

    meta = {"data_source": source, "dataset": dataset, "seed": SEED,
            "subjects": [int(s) for s in np.unique(groups)], "git_commit": _git_commit(),
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"), "n_trials": int(len(y))}
    if source == "synthetic":
        meta["label"] = SYNTHETIC_LABEL
    return meta


def _report_blocks(res: dict) -> None:
    """Copy heterogeneity values into the top-level keys bci.report reads (responder_analysis, erd). No new numbers."""
    het = res.get("heterogeneity", {})
    r = het.get("responders", {})
    if r.get("status") == "ok":
        res["responder_analysis"] = {
            "per_subject": {s: {"score": v["obs"], "p_value": v["p"], "responder": v["responder"]}
                            for s, v in r["per_subject"].items()},
            "summary": {"count": r["count"], "n": r["n"], "ci95": r["ci95_proportion"],
                        "expected_false_positives": r["expected_false_positives"], "alpha": r["alpha"],
                        "n_perm": r["n_perm"]},
            "calibration_gain": r.get("calibration_gain") if isinstance(r.get("calibration_gain"), dict)
            and r["calibration_gain"].get("k") else None}
    else:
        res.pop("responder_analysis", None)
    e = het.get("erd", {})
    if e.get("status") == "ok":
        res["erd"] = {"lateralization": e["ls_mu"], "association": e.get("ls_mu_vs_csp_lda_within"),
                      "band": e["band_mu"]}
    else:
        res.pop("erd", None)


def analysis_only(out_dir: Path, dataset: str):
    """Responder analysis + ERD check on the SAME data as the stored model blocks, then the report and README.

    The data is reloaded and must match the stored meta (subjects and n_trials); no model block is refitted or
    changed. The previous heterogeneity block (if any) is replaced.
    """
    from bci import report
    from bci.contracts import g4_check, validate_results

    rpath = out_dir / "results.json"
    res = json.loads(rpath.read_text(encoding="utf-8"))
    X, y, groups, source = load(False, dataset)
    if source != res["meta"]["data_source"]:
        raise SystemExit(f"data source {source} != stored {res['meta']['data_source']}: refusing to mix data")
    if [int(s) for s in np.unique(groups)] != res["meta"]["subjects"] or int(len(y)) != res["meta"]["n_trials"]:
        raise SystemExit("reloaded data does not match the stored subjects / n_trials")
    res["heterogeneity"] = heterogeneity(X, y, groups, res["models"], dataset)
    _report_blocks(res)
    res["meta"]["analysis_run"] = {"git_commit": _git_commit(),
                                   "timestamp": _dt.datetime.now().isoformat(timespec="seconds")}
    validate_results(res)
    _write_results(rpath, res)
    md = report.write_report(str(rpath), str(out_dir))
    print(f"[run_all] report {md}", flush=True)
    res = json.loads(rpath.read_text(encoding="utf-8"))
    fails, warns = g4_check(res)
    fb = {"png": "feedback.png", "subject": int(res["meta"]["subjects"][0])} if (out_dir / "feedback.png").exists() else None
    write_readme(out_dir / "README.md", res, fails, warns, fb)
    if out_dir == (REPO / "results").resolve():
        write_readme(REPO / "README.md", res, fails, warns, fb)
    print(f"[run_all] heterogeneity: responders {res['heterogeneity']['responders'].get('status')}, "
          f"erd {res['heterogeneity']['erd'].get('status')}", flush=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--dataset", choices=("physionet", "stroke"), default="physionet")
    ap.add_argument("--out", default=None, help="default results/ (physionet) or results/stroke/ (stroke)")
    ap.add_argument("--fresh", action="store_true", help="delete OUT/checkpoints first (new code = new checkpoints)")
    ap.add_argument("--skip-heterogeneity", action="store_true")
    ap.add_argument("--analysis-only", action="store_true",
                    help="keep OUT/results.json model blocks; rerun only responders/ERD, the report and README")
    ap.add_argument("--calibration-only", nargs="+", metavar="MODEL",
                    help="v0.2 mode: run only the calibration stage for these models and merge into OUT/results.json")
    args = ap.parse_args(argv)
    dataset = "physionet" if args.synthetic else args.dataset
    os.environ["BCI_DATASET"] = dataset  # read at call time by the factories; inherited by worker processes
    default_out = REPO / "results" / ("stroke" if dataset == "stroke" else "")
    out_dir = Path(args.out).resolve() if args.out else default_out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.calibration_only:
        return calibration_only(args.calibration_only, out_dir)
    if args.analysis_only:
        return analysis_only(out_dir, dataset)

    from bci.contracts import SYNTHETIC_LABEL, g4_check, load_config, validate_results
    from bci.evaluate import _registry

    cfg = load_config()
    ck_dir = out_dir / "checkpoints"
    if args.fresh and ck_dir.exists():
        shutil.rmtree(ck_dir)
    ck_dir.mkdir(parents=True, exist_ok=True)
    X, y, groups, source = load(args.synthetic, dataset)
    print(f"[run_all] data {source}: X {X.shape} {X.dtype}, subjects {len(np.unique(groups))}", flush=True)
    if source == "synthetic":
        print(f"[run_all] {SYNTHETIC_LABEL}", flush=True)
    reg = _registry()
    names = [n for n in MODEL_ORDER if n in reg] + sorted(n for n in reg if n not in MODEL_ORDER)
    rpath = out_dir / "results.json"
    meta = _meta(source, groups, y, dataset)

    def on_model(done):  # results.json after every finished model (stages live in the checkpoints)
        part = {"meta": {**meta, "partial": True}, "models": {n: {k: v for k, v in b.items() if k != "runtime_s"}
                                                               for n, b in done.items()},
                "stats": {"comparisons": []}, "runtime_s": {n: float(b.get("runtime_s", 0.0)) for n, b in done.items()}}
        _write_results(rpath, part)

    models = evaluate_all(X, y, groups, names, set(cfg["calibration_models"]), ck_dir, on_model)
    for b in models.values():
        if "calibration" in b:
            add_bootstrap(b["calibration"])
    runtime = {n: float(b.pop("runtime_s", 0.0)) for n, b in models.items()}
    res = {"meta": meta, "models": models, "runtime_s": runtime}
    from bci import report

    res["stats"] = report.compute_stats(res)
    validate_results(res)
    _write_results(rpath, res)
    if not args.skip_heterogeneity:
        res["heterogeneity"] = heterogeneity(X, y, groups, models, dataset)
        _report_blocks(res)
        _write_results(rpath, res)
    md = report.write_report(str(rpath), str(out_dir))
    print(f"[run_all] report {md}", flush=True)
    res = json.loads(rpath.read_text(encoding="utf-8"))

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
