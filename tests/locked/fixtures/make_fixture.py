"""Generate tests/locked/fixtures/results_fixture.json: FAKE values for testing report.py only."""
import json
import sys

import numpy as np
from scipy.stats import wilcoxon

rng = np.random.default_rng(123)
subjects = [1, 2, 3, 4, 5, 6]
base = {"csp_lda": 0.68, "fbcsp_lr": 0.71, "ts_lr": 0.73, "eegnet_lite": 0.64}
cross_base = {"csp_lda": 0.60, "fbcsp_lr": 0.61, "ts_lr": 0.63, "eegnet_lite": 0.58}
models = {}
per_subj = {}
for name, b in base.items():
    ps = {}
    vals = []
    for s in subjects:
        ba = round(float(np.clip(b + 0.08 * rng.standard_normal(), 0.4, 0.92)), 4)
        acc = round(ba + 0.004 * rng.standard_normal(), 4)
        kappa = round(2 * ba - 1, 4)
        ps[str(s)] = {"acc": acc, "bal_acc": ba, "kappa": kappa}
        vals.append(ba)
    per_subj[name] = np.array(vals)
    folds = []
    for i, ts in enumerate([[1, 4], [2], [3], [5], [6]]):
        ba = round(float(cross_base[name] + 0.04 * rng.standard_normal()), 4)
        folds.append({"fold": i, "test_subjects": ts, "acc": round(ba + 0.003, 4), "bal_acc": ba,
                      "kappa": round(2 * ba - 1, 4)})
    fv = [f["bal_acc"] for f in folds]
    block = {
        "within_subject": {"per_subject": ps, "mean_bal_acc": round(float(np.mean(vals)), 4),
                           "std_bal_acc": round(float(np.std(vals, ddof=1)), 4)},
        "cross_subject": {"per_fold": folds, "mean_bal_acc": round(float(np.mean(fv)), 4),
                          "std_bal_acc": round(float(np.std(fv, ddof=1)), 4)},
        "permutation": {"within_mean_bal_acc": round(0.5 + 0.01 * rng.standard_normal(), 4),
                        "cross_mean_bal_acc": round(0.5 + 0.01 * rng.standard_normal(), 4)},
        "status": "ok",
    }
    if name != "eegnet_lite":
        ks = [0, 4, 8, 16, 24]
        spt = [round(float(cross_base[name] + 0.004 * k + 0.01 * rng.standard_normal()), 4) for k in ks]
        to = [None] + [round(float(0.52 + 0.007 * k + 0.01 * rng.standard_normal()), 4) for k in ks[1:]]
        block["calibration"] = {"k": ks, "source_plus_target": spt, "target_only": to}
    models[name] = block

comps = []
raw = []
for name in ("fbcsp_lr", "ts_lr", "eegnet_lite"):
    d = per_subj[name] - per_subj["csp_lda"]
    p = float(wilcoxon(per_subj[name], per_subj["csp_lda"]).pvalue)
    raw.append(p)
    comps.append({"model": name, "vs": "csp_lda", "median_diff": round(float(np.median(d)), 4), "p_raw": round(p, 4)})
# Holm
order = np.argsort(raw)
m = len(raw)
adj = np.empty(m)
running = 0.0
for rank, i in enumerate(order):
    running = max(running, min(1.0, (m - rank) * raw[i]))
    adj[i] = running
for c, a in zip(comps, adj):
    c["p_holm"] = round(float(a), 4)

res = {
    "meta": {"data_source": "synthetic", "seed": 42, "subjects": subjects, "git_commit": "fixture",
             "timestamp": "2026-11-18T00:00:00", "label": "FAKE FIXTURE - NOT A RESULT",
             "note": "Fake values for testing report.py only. Not measured."},
    "models": models,
    "stats": {"comparisons": comps, "test": "wilcoxon signed-rank, within-subject per-subject bal_acc, Holm"},
    "runtime_s": {"csp_lda": 12.5, "fbcsp_lr": 30.25, "ts_lr": 20.75, "eegnet_lite": 300.5},
}
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(res, fh, indent=2)
print(json.dumps(comps, indent=1))
