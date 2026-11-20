"""FROZEN contracts (PRD section 7, PRD_v0.3 section 7). Head chef, Phase 0. No cook edits this file.

v0.3 DATASET CONTRACT (dataset-dependent shapes; PRD_v0.3 section 7 item 2)
    DATASETS[name] = {"n_channels", "sfreq", "n_samples"}. "physionet" keeps 64, 160, 480 (the v0.2 constants
    N_CHANNELS, SFREQ, N_SAMPLES below are the PhysioNet values and stay for PhysioNet code and tests).
    The active dataset is os.environ[DATASET_ENV] ("BCI_DATASET"), default "physionet": dataset_spec() reads
    it AT CALL TIME. Registry factories take no argument, so every factory reads dataset_spec() when it
    builds the estimator (e.g. the band-pass sampling rate). No estimator may assume 64 channels or 160 Hz.
    validate_data(X, y, groups, dataset=None) raises ValueError if X, y, groups break the contract of that
    dataset (shape (n, n_channels, n_samples), float32, y integer in {0, 1}, equal lengths).
    "stroke" = Liu et al. 2024 (docs/STROKE_DATASET.md): 29 EEG channels (EOG dropped), 500 Hz (native, no
    resampling), window config stroke.window after the motor-imagery onset marker -> 1500 samples.

v0.3 TIME LIMIT CONTRACT
    config time_budget_min is a SAFETY STOP only. enforce_time_budget(cfg) returns config
    enforce_time_budget unless os.environ["BCI_ENFORCE_TIME_BUDGET"] is "0" or "1" (tests set "0").
    When it is False no wall-clock value may change any result (gate G10).

v0.3 EVALUATE CHECKPOINT CONTRACT (bci.evaluate, Claude, ticket S2)
    run_model(name, X, y, groups, calibration, checkpoint=None). checkpoint = path of a JSON file.
    After EACH finished stage (within_subject, cross_subject, permutation, calibration) the model block so
    far is written to that file atomically (write a temp file, then os.replace). On start, if the file holds
    the same fingerprint, finished stages are loaded and NOT recomputed. The fingerprint is a hash of the
    model name, X, y, groups and the config; any change means nothing is reused. The calibration flag is not
    part of the fingerprint (a rerun with calibration=True after a run without it fits calibration only).
    within_subject blocks keep "per_subject" (the per-subject score table).

v0.3 FILTER CACHE CONTRACT (bci.cache + models_classical.BandPass, Claude, ticket S1)
    BandPass(low, high, fs, order).transform(X) returns zero-phase Butterworth (sosfiltfilt, float64) output.
    With the cache on or off, outputs match to 1e-9 and predictions of csp_lda / fbcsp_lr match to 1e-9
    (gate G8). Cache key = (data content hash, band, order, sampling rate); a hash of the CONTENT, never id().
    Memory cache in-process plus .npy files in os.environ["BCI_FILTER_CACHE_DIR"] (default
    <repo>/.cache/filtered). os.environ["BCI_FILTER_CACHE"] == "0" disables memory and disk cache (read at call
    time). bci.cache.clear_memory() empties the in-process cache. Safe for several processes at once
    (atomic writes). The cache stores ONLY stateless filter output: nothing that depends on labels or on a
    fit (no CSP filters, no covariances, no scalers). The estimator API does not change.

v0.3 ANALYSIS CONTRACT (bci.analysis, Codex, ticket H1; responder rule = PRD_v0.3 section 4)
    subject_pvalue(estimator_factory, X, y, n_perm, seed) -> {"obs": float, "null": list of n_perm floats,
        "p": float}. X, y = ONE subject. obs = balanced accuracy of the pooled out-of-fold predictions of
        splits.within_subject_splits(y, groups=all-equal, n_splits=config n_splits, seed=SEED). Each null
        score repeats the same CV with the labels of the subject shuffled (seeded by seed). A new estimator
        from estimator_factory() for every fit. p = (1 + #(null >= obs)) / (1 + n_perm).
    classify_responders(pvalues, alpha) -> {"flags": {sid: bool}, "count": int, "n": int,
        "ci95": [lo, hi] (Clopper-Pearson exact 95 % interval of the responder PROPORTION),
        "expected_false_positives": alpha * n}. flag = p < alpha (strict).
    calibration_gain_by_group(per_target, flags, k, n_boot=10000, seed=SEED) -> {"k": list,
        "responders": list, "non_responders": list, "diff": list, "diff_ci95": list of [lo, hi],
        "n_responders": int, "n_non_responders": int}. per_target and k = the lists of a CALIBRATION block.
        gain(target, k) = source_plus_target(target, k) - source_plus_target(target, k=0). responders /
        non_responders = mean gain per k; diff = responders - non_responders; diff_ci95 = percentile bootstrap
        (resample targets with replacement inside each group). A value is None when a group is empty.

v0.3 ERD CONTRACT (bci.erd_check, Codex, ticket H2; LS = PRD_v0.3 section 4)
    band_power(X, sfreq, band) -> (n_trials, n_channels) float: scipy.signal.welch(nperseg=int(sfreq),
        density scaling) integrated over band (sum of bins in [lo, hi] times df). Unit uV^2 for X in uV.
    lateralization(X, y, groups, sfreq, ch_c3, ch_c4, band) -> {str(sid): LS}. P(ch, class) = mean band power
        over the trials of that class. LS = [ln P(C3,right) - ln P(C3,left)] - [ln P(C4,right) - ln P(C4,left)],
        right = label 1, left = label 0. Expected LS < 0 for a clear ERD.
    lateralization_vs_accuracy(ls, acc) -> {"rho": float, "p": float, "n": int}: scipy.stats.spearmanr over
        the subjects present in both dicts (ascending id).
    Channel indices come from bci.channels (CH_C3, CH_CZ, CH_C4 for PhysioNet).

v0.3 STROKE LOADER CONTRACT (bci.data_stroke, Claude, ticket S4, optional)
    load_stroke(subjects=None) -> (X, y, groups) following DATASETS["stroke"]; y 0 = left hand (trial_type 1),
    1 = right hand (trial_type 2); X in uV; groups = patient number. Never falls back to synthetic data.

DATA CONTRACT (v0.2, PhysioNet)
    X       np.ndarray, shape (n_trials, 64, 480), dtype float32, unit microvolt (uV).
    y       np.ndarray, shape (n_trials,), integer, values in {0, 1}. 0 = left fist (T1), 1 = right fist (T2).
    groups  np.ndarray, shape (n_trials,), integer subject id.

    bci.data must expose:
        epochs_from_raw(raw) -> (X, y)   # one mne Raw in VOLTS with T0/T1/T2 annotations -> uV epochs.
            Applies config reference (average), config filter_band to the continuous raw, keeps T1/T2 by
            annotation DESCRIPTION (not by event code), window config tmin..tmax (480 samples), x unit_scale.
            Must not depend on channel names or a montage (gate G1 feeds a RawArray named EEG000..EEG063).
        load_dataset(subjects, runs) -> (X, y, groups)                         # PhysioNet only, raises on failure
        load_with_fallback(subjects, runs) -> (X, y, groups, source)          # source in DATA_SOURCES
            calls the module-level load_dataset up to config["download_attempts"] times, then returns
            synthetic.make_synthetic() data with source == "synthetic".

ESTIMATOR CONTRACT
    Each model is a scikit-learn estimator (sklearn.base.clone works) with fit(X, y), predict(X) -> (n,) in {0, 1},
    predict_proba(X) -> (n, 2), rows sum to 1, column 1 = P(right). All scaling, filtering with learned state,
    covariance references and normalisation statistics are learned inside fit(). fit() never sees test data.
    The csp_lda pipeline has a step named "csp" with attribute filters_ (2D, rows are spatial filters over the
    n_channels channels of the dataset, rows 0 and 1 are the most discriminative filters).

REGISTRY CONTRACT
    bci.models_classical.REGISTRY == {"csp_lda": f, "fbcsp_lr": f}   (Claude)
    bci.models_advanced.REGISTRY  == {"ts_lr": f, "eegnet_lite": f}  (Codex)
    Each f takes no argument and returns a NEW unfitted estimator.

EVALUATOR CONTRACT (bci.evaluate, Claude)
    within_subject(name, X, y, groups)      -> WITHIN block
    cross_subject(name, X, y, groups)       -> CROSS block
    permutation_control(name, X, y, groups) -> PERMUTATION block (mean of config["n_permutations"] repeats)
    calibration_curve(name, X, y, groups)   -> CALIBRATION block
    Names are resolved AT CALL TIME from the REGISTRY dict objects of models_classical and (if importable)
    models_advanced, e.g. {**models_classical.REGISTRY, **models_advanced.REGISTRY} inside each call.
    Per-subject metrics use the out-of-fold predictions of that subject pooled over its folds.
    mean_* is the plain mean, std_* uses ddof = config["std_ddof"].

REPORT CONTRACT (bci.report, Codex)
    compute_stats(results) -> STATS block: for each model with status ok other than csp_lda,
                              scipy.stats.wilcoxon(model, csp_lda) with scipy defaults on per-subject within bal_acc
                              (common subjects, ascending id); p_raw = 1.0 when all differences are 0;
                              median_diff = median(model - csp_lda); Holm step-down over all comparisons.
    write_report(results_path, out_dir) -> str path of results.md. If results has no "stats", it calls
                              compute_stats and writes the block back into results_path first.
                              Writes results.md, fig1_models.png, fig2_calibration.png, fig3_permutation.png.
    Every decimal number in results.md must exist in results.json (gate G5). Allowed constants:
    REPORT_ALLOWED_CONSTANTS.

FEEDBACK CONTRACT (bci.feedback_sim, Codex)
    simulate_feedback(estimator, trial, sfreq, out_png) -> (times_s, p_right)  both 1D np.ndarray, times in s.

RESULTS SCHEMA (results/results.json)
    meta:    {data_source, seed, subjects, git_commit, timestamp}  (+ optional label)
    models:  {name: {within_subject, cross_subject, permutation, [calibration], [status]}}
    stats:   {comparisons: [{model, vs, median_diff, p_raw, p_holm}]}
    runtime_s: {name: seconds}
    A model block with status in {"timeout", "error"} may omit sub-blocks.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

SEED = 42
SFREQ = 160
N_CHANNELS = 64
N_SAMPLES = 480
LABELS = {0: "left", 1: "right"}

DATA_SOURCES = ("physionet", "synthetic", "stroke")
SYNTHETIC_LABEL = "SYNTHETIC - NOT VALID"
CLASSICAL_MODELS = ("csp_lda", "fbcsp_lr")
ADVANCED_MODELS = ("ts_lr", "eegnet_lite")
BASELINE_MODEL = "csp_lda"
REPORT_ALLOWED_CONSTANTS = (0.5, 0.05)
MODEL_STATUSES = ("ok", "timeout", "error")

Registry = Dict[str, Callable[[], Any]]

# ---------------------------------------------------------------- v0.3 datasets
DATASETS = {
    "physionet": {"n_channels": N_CHANNELS, "sfreq": SFREQ, "n_samples": N_SAMPLES},
    "stroke": {"n_channels": 29, "sfreq": 500, "n_samples": 1500},  # docs/STROKE_DATASET.md, config stroke
}
DATASET_ENV = "BCI_DATASET"
ENFORCE_ENV = "BCI_ENFORCE_TIME_BUDGET"


def dataset_name() -> str:
    """Active dataset: $BCI_DATASET, default physionet. Read at call time."""
    import os

    name = os.environ.get(DATASET_ENV, "physionet") or "physionet"
    if name not in DATASETS:
        raise ValueError(f"{DATASET_ENV}={name!r}; known datasets: {sorted(DATASETS)}")
    return name


def dataset_spec(name: str | None = None) -> dict:
    """Copy of DATASETS[name or active dataset]: {n_channels, sfreq, n_samples}."""
    name = name or dataset_name()
    if name not in DATASETS:
        raise ValueError(f"unknown dataset {name!r}; known: {sorted(DATASETS)}")
    return dict(DATASETS[name])


def validate_data(X, y, groups, dataset: str | None = None) -> None:
    """Raise ValueError if (X, y, groups) break the data contract of the dataset."""
    import numpy as np

    spec = dataset_spec(dataset)
    X, y, groups = np.asarray(X), np.asarray(y), np.asarray(groups)
    want = (spec["n_channels"], spec["n_samples"])
    if X.ndim != 3 or X.shape[1:] != want:
        raise ValueError(f"X shape {X.shape}, expected (n, {want[0]}, {want[1]})")
    if X.dtype != np.float32:
        raise ValueError(f"X dtype {X.dtype}, expected float32")
    if not np.issubdtype(y.dtype, np.integer) or not set(np.unique(y).tolist()) <= {0, 1}:
        raise ValueError("y must be integer with values in {0, 1}")
    if not (len(X) == len(y) == len(groups)):
        raise ValueError("X, y, groups lengths differ")
    if not np.issubdtype(groups.dtype, np.integer):
        raise ValueError("groups must be integer subject ids")


def enforce_time_budget(cfg: dict | None = None) -> bool:
    """config enforce_time_budget, overridden by $BCI_ENFORCE_TIME_BUDGET in {"0", "1"}. Read at call time."""
    import os

    env = os.environ.get(ENFORCE_ENV)
    if env in ("0", "1"):
        return env == "1"
    cfg = cfg if cfg is not None else load_config()
    return bool(cfg.get("enforce_time_budget", True))

CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_config(path: str | Path | None = None) -> dict:
    """Return config.yaml as a dict."""
    import yaml

    with open(path or CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------- schema checks
def _num(x, where):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{where}: expected a number, got {type(x).__name__}")
    if x != x:
        raise ValueError(f"{where}: NaN is not allowed")


def _score(x, where):
    _num(x, where)
    if not -1.0 <= x <= 1.0:
        raise ValueError(f"{where}: {x} outside [-1, 1]")


def _metrics(d, where):
    if not isinstance(d, dict):
        raise ValueError(f"{where}: expected dict")
    for key in ("acc", "bal_acc", "kappa"):
        if key not in d:
            raise ValueError(f"{where}: missing {key}")
        _score(d[key], f"{where}.{key}")
    if not 0.0 <= d["acc"] <= 1.0 or not 0.0 <= d["bal_acc"] <= 1.0:
        raise ValueError(f"{where}: acc/bal_acc outside [0, 1]")


def validate_within(block: dict, where: str = "within_subject") -> None:
    if not isinstance(block, dict):
        raise ValueError(f"{where}: expected dict")
    for key in ("per_subject", "mean_bal_acc", "std_bal_acc"):
        if key not in block:
            raise ValueError(f"{where}: missing {key}")
    ps = block["per_subject"]
    if not isinstance(ps, dict) or not ps:
        raise ValueError(f"{where}.per_subject: expected non-empty dict")
    for sid, m in ps.items():
        int(sid)  # keys are subject ids (str in JSON)
        _metrics(m, f"{where}.per_subject[{sid}]")
    _score(block["mean_bal_acc"], f"{where}.mean_bal_acc")
    _num(block["std_bal_acc"], f"{where}.std_bal_acc")


def validate_cross(block: dict, where: str = "cross_subject") -> None:
    if not isinstance(block, dict):
        raise ValueError(f"{where}: expected dict")
    for key in ("per_fold", "mean_bal_acc", "std_bal_acc"):
        if key not in block:
            raise ValueError(f"{where}: missing {key}")
    pf = block["per_fold"]
    if not isinstance(pf, list) or not pf:
        raise ValueError(f"{where}.per_fold: expected non-empty list")
    for i, m in enumerate(pf):
        _metrics(m, f"{where}.per_fold[{i}]")
        if "test_subjects" not in m:
            raise ValueError(f"{where}.per_fold[{i}]: missing test_subjects")
    _score(block["mean_bal_acc"], f"{where}.mean_bal_acc")
    _num(block["std_bal_acc"], f"{where}.std_bal_acc")


def validate_permutation(block: dict, where: str = "permutation") -> None:
    if not isinstance(block, dict):
        raise ValueError(f"{where}: expected dict")
    for key in ("within_mean_bal_acc", "cross_mean_bal_acc"):
        if key not in block:
            raise ValueError(f"{where}: missing {key}")
        _score(block[key], f"{where}.{key}")


def validate_calibration(block: dict, where: str = "calibration") -> None:
    if not isinstance(block, dict):
        raise ValueError(f"{where}: expected dict")
    for key in ("k", "source_plus_target", "target_only"):
        if key not in block or not isinstance(block[key], list):
            raise ValueError(f"{where}: missing list {key}")
    n = len(block["k"])
    if n == 0 or len(block["source_plus_target"]) != n or len(block["target_only"]) != n:
        raise ValueError(f"{where}: lists must have equal non-zero length")
    for k, a, b in zip(block["k"], block["source_plus_target"], block["target_only"]):
        if not isinstance(k, int) or k < 0 or k % 2:
            raise ValueError(f"{where}: k must be an even int >= 0, got {k!r}")
        _score(a, f"{where}.source_plus_target[k={k}]")
        if k == 0:
            if b is not None:
                raise ValueError(f"{where}.target_only[k=0] must be null (no target trials)")
        else:
            _score(b, f"{where}.target_only[k={k}]")


def validate_results(res: dict) -> None:
    """Raise ValueError if res does not follow the results schema."""
    for key in ("meta", "models", "stats", "runtime_s"):
        if key not in res:
            raise ValueError(f"results: missing {key}")
    meta = res["meta"]
    for key in ("data_source", "seed", "subjects", "git_commit", "timestamp"):
        if key not in meta:
            raise ValueError(f"meta: missing {key}")
    if meta["data_source"] not in DATA_SOURCES:
        raise ValueError(f"meta.data_source must be one of {DATA_SOURCES}")
    if not isinstance(res["models"], dict) or not res["models"]:
        raise ValueError("models: expected non-empty dict")
    for name, block in res["models"].items():
        status = block.get("status", "ok")
        if status not in MODEL_STATUSES:
            raise ValueError(f"models.{name}.status invalid: {status!r}")
        if status != "ok":
            continue
        validate_within(block["within_subject"], f"models.{name}.within_subject")
        validate_cross(block["cross_subject"], f"models.{name}.cross_subject")
        validate_permutation(block["permutation"], f"models.{name}.permutation")
        if "calibration" in block:
            validate_calibration(block["calibration"], f"models.{name}.calibration")
    comps = res["stats"].get("comparisons")
    if not isinstance(comps, list):
        raise ValueError("stats.comparisons: expected list")
    for i, c in enumerate(comps):
        for key in ("model", "vs", "median_diff", "p_raw", "p_holm"):
            if key not in c:
                raise ValueError(f"stats.comparisons[{i}]: missing {key}")
        for key in ("p_raw", "p_holm"):
            _num(c[key], f"stats.comparisons[{i}].{key}")
            if not 0.0 <= c[key] <= 1.0:
                raise ValueError(f"stats.comparisons[{i}].{key} outside [0, 1]")
        if c["p_holm"] + 1e-12 < c["p_raw"]:
            raise ValueError(f"stats.comparisons[{i}]: p_holm < p_raw")
    for name, sec in res["runtime_s"].items():
        _num(sec, f"runtime_s.{name}")


# ---------------------------------------------------------------- gate G4 rule
G4_WITHIN_RANGE = (0.55, 0.90)
G4_CROSS_RANGE = (0.50, 0.75)
G4_LEAK_LIMIT = 0.95


def g4_check(res: dict):
    """Gate G4 (physionet only). Return (fails, warnings), two lists of strings.

    FAIL: any model's mean within/cross bal_acc, any cross per-fold bal_acc, any calibration point, or any
          permutation mean above G4_LEAK_LIMIT (suspect leak).
    FAIL (v0.3): any of the 4 models (CLASSICAL_MODELS + ADVANCED_MODELS) missing or with status != ok, and
          ALWAYS when no model was checked (a gate that checks nothing fails).
    WARN: csp_lda within mean outside G4_WITHIN_RANGE, csp_lda cross mean outside G4_CROSS_RANGE,
          any per-subject bal_acc above G4_LEAK_LIMIT, any permutation mean outside 0.50 +/- 0.05.
    The non-physionet case returns ([], []); the caller (tests/locked/test_real_plausibility.py) skips it.
    """
    fails, warns = [], []
    if res["meta"]["data_source"] != "physionet":
        return fails, warns
    lim = G4_LEAK_LIMIT
    checked = 0
    for name in CLASSICAL_MODELS + ADVANCED_MODELS:
        if name not in res["models"]:
            fails.append(f"{name} missing from results")
    for name, block in res["models"].items():
        if block.get("status", "ok") != "ok":
            fails.append(f"{name}: status {block.get('status')}, not checked (G4 needs every model ok)")
            continue
        checked += 1
        w, c, p = block["within_subject"], block["cross_subject"], block["permutation"]
        for label, v in (("within mean", w["mean_bal_acc"]), ("cross mean", c["mean_bal_acc"]),
                         ("permutation within", p["within_mean_bal_acc"]),
                         ("permutation cross", p["cross_mean_bal_acc"])):
            if v > lim:
                fails.append(f"{name} {label} bal_acc {v:.4f} > {lim} (suspect leak)")
        for i, f in enumerate(c["per_fold"]):
            if f["bal_acc"] > lim:
                fails.append(f"{name} cross fold {i} bal_acc {f['bal_acc']:.4f} > {lim} (suspect leak)")
        cal = block.get("calibration")
        if cal:
            for k, a, b in zip(cal["k"], cal["source_plus_target"], cal["target_only"]):
                for lab, v in (("source_plus_target", a), ("target_only", b)):
                    if v is not None and v > lim:
                        fails.append(f"{name} calibration {lab} k={k} {v:.4f} > {lim} (suspect leak)")
        for sid, m in w["per_subject"].items():
            if m["bal_acc"] > lim:
                warns.append(f"{name} subject {sid} within bal_acc {m['bal_acc']:.4f} > {lim}")
        for label, v in (("within", p["within_mean_bal_acc"]), ("cross", p["cross_mean_bal_acc"])):
            if abs(v - 0.5) > 0.05:
                warns.append(f"{name} permutation {label} {v:.4f} outside 0.50 +/- 0.05")
    base = res["models"].get(BASELINE_MODEL)
    if base and base.get("status", "ok") == "ok":
        wm = base["within_subject"]["mean_bal_acc"]
        cm = base["cross_subject"]["mean_bal_acc"]
        if not G4_WITHIN_RANGE[0] <= wm <= G4_WITHIN_RANGE[1]:
            warns.append(f"csp_lda within mean {wm:.4f} outside {G4_WITHIN_RANGE}")
        if not G4_CROSS_RANGE[0] <= cm <= G4_CROSS_RANGE[1]:
            warns.append(f"csp_lda cross mean {cm:.4f} outside {G4_CROSS_RANGE}")
    if checked == 0:
        fails.append("G4 checked no model: a gate that checks nothing fails")
    return fails, warns
