# Integration v0.3 (integration/v0.3, worktrees\v3-integration)

The v0.2 integration notes are in this file on main and tag v0.2 (`git show v0.2:docs/INTEGRATION.md`).
Built 2026-11-20 by the Claude lead. Base: base/v0.3 (18b78b2). Merged: claude/speed-stroke (06eb7d3) as 7276571.
codex/heterogeneity: Codex was idle from 03:52 to about 09:50 (cause not measured), then wrote H1-H4 between
09:52 and 10:03 (CODEX_DONE 10:02, inside the 4 h limit). Its sandbox could not commit (index.lock), so the lead
committed the files as bf21a5b ("codex work") and merged it as 860004d. models_advanced.py did not change, so the
ts_lr and eegnet_lite blocks of the S5 run stand. The plan review (.sync3/PLAN_REVIEW.md, 15 hardening items,
"not evidence of an implementation defect") came after the lock and build: accepted as risk, no locked check edited.

## run_all.py v0.3 (1e7df94)
Per-model checkpoint files under OUT/checkpoints (`--fresh` deletes them), results.json after every finished model,
`--dataset stroke` (default OUT results/stroke/, never a fallback), responder analysis and ERD check called only when
bci/analysis.py and bci/erd_check.py exist, else results.json records `"status": "not measured"` with the reason.
Synthetic smoke run (BCI_ENFORCE_TIME_BUDGET=0): exit 0, 4 models ok, 875 s wall time.

## S5 runs
- PhysioNet: `run_all.py --fresh`, 06:48 to 07:55, exit 0. All 4 models status ok with every stage complete.
  runtime_s: csp_lda 868.8, fbcsp_lr 3508.0, ts_lr 4001.1, eegnet_lite 3606.4 (v0.2: all 4 timeout at 40 min).
  csp_lda within, cross and calibration, and fbcsp_lr within and cross, equal the v0.2 values to 4 decimals (e.g.
  csp_lda within 0.5479, cross 0.5588). These are the models that use the S1 cache and csp_rank, so those changes did
  not move the results. (fbcsp_lr had no v0.2 calibration/permutation block; ts_lr does not use the changed code.)
  Only csp_lda (868.8 s vs v0.2 timeout) shows the speedup; the other 3 models ran longer than 2400 s and finished
  because time_budget_min is now 180. heterogeneity: responders and ERD "not measured" (Codex modules missing).
- Stroke: `run_all.py --dataset stroke --fresh` (BCI_STROKE_DIR = <root>\.cache\stroke), started 07:56.
  STOPPED by Claude Code: "Background command ... was stopped because the system is running low on memory".
  The harness rule is to not restart it without the human, so it was not restarted. Finished before the stop
  (results/stroke/results.json, meta.partial = true, and results/stroke/checkpoints): csp_lda within_subject and
  ts_lr within_subject only (47 patients). eegnet_lite: status error,
  `ValueError: expected trials x 64 channels x samples, got (32, 29, 1500)` (bci/models_advanced.py, Codex file).
  Cause of the memory shortage: not measured. A likely factor: 4 worker processes, each with a filter cache of up to
  4096 MB ($BCI_FILTER_CACHE_MEM_MB) for 1880 x 29 x 1500 float64 rows.

## Gates on integration/v0.3 (commit 2381165, env BCI_EXPECT_REAL=1, BCI_EXPECT_STROKE=1, BCI_REAL_DATA=1)
| Gate | Result | Exact text / note |
|---|---|---|
| G0 ownership | PASS | 3 passed (incl. integration did not edit branch files) |
| G1 contracts | FAIL | `test_estimators_work_on_stroke_shape[eegnet_lite]`: `ValueError: expected trials x 64 channels x samples, got (48, 29, 1500)`. 42 passed, 1 skipped. Owner: Codex (bci/models_advanced.py); no Codex session to return it to |
| G2 no leak | PASS | in the 42 passed above |
| G3 synthetic recovery | PASS | 17 passed (not slow, with G9 and G6-unit); slow test_eegnet_recovers passed in the G6 run-1 batch |
| G4 real plausibility | PASS | warnings: csp_lda and fbcsp_lr subject 7 within bal_acc 0.9783 > 0.95; csp_lda within mean 0.5479 outside (0.55, 0.9) |
| G5 report numbers | PASS | 9 passed, including results.md vs results.json on the real results |
| G6 two seeded runs | FAIL (run 1), rerun pending | 08:06-08:52: `AssertionError: two seeded runs gave different results.json`. The only differing key: meta.git_commit `23811659...` vs `23811659...-dirty` (I edited docs/INTEGRATION.md while run 1 ran). Every other value equal. Rerun on a clean tree (29539e7, 08:53-09:38): PASS, `1 passed in 2714.11s` |
| G7 fresh venv | not run | opt-in (BCI_RUN_G7), not run this night |
| G8 cache | PASS | 7 passed |
| G9 speed | PASS alone, FAIL under load | PASS in the gate run (08:00, nothing else running). FAIL in the inspector's full-suite run, which ran at the same time as the G6 run_all workers (`test_csp_lda_fit_speed` failed). The S1 builder measured median 1.249 s under partial load and 1.573 s / 1.713 s at 79-94 % CPU. The margin under the 1.567 s limit is small; judge G9 on a quiet machine |
| G10 wall clock | PASS | 3 passed |
| G11 responders | PASS after the Codex merge | before: 6 errors `Failed: bci/analysis.py is required on integration/v0.3 but does not exist`; after 860004d: G0+G5+G11+G12+tests/codex 34 passed |
| G12 ERD | PASS after the Codex merge | before: 5 errors (`bci/erd_check.py ... does not exist`); after: pass, incl. the channel map on the real EDF names |
| G13 stroke loader | PASS | 2 passed with BCI_EXPECT_STROKE=1 |
| G14 hygiene | PASS | 3 passed |

The G1 failure is in a Codex-owned file (models_advanced.py). Integration fixes only integration files, so it stays failed.

## Stroke interval (added after the gates)
results/stroke/within_ci.json: percentile bootstrap 95% CI of the mean within-subject bal_acc over the 47 patients,
10000 resamples, numpy default_rng([42, 0, 0]), computed from results/stroke/checkpoints (script
.cache/probes/stroke_ci.py, git-excluded). csp_lda 0.5064 [0.4707, 0.5436]; ts_lr 0.5622 [0.5080, 0.6181].

## Not done
- Stroke rerun: needs a human go-ahead (host stopped it for low memory).
- G7 fresh venv: not run.

## Responder analysis and ERD check on PhysioNet (after the Codex merge)
`run_all.py --analysis-only` (15c3449), 10:53 to 11:25: reloads the same data (subjects and n_trials checked against
the stored meta), keeps every model block, adds `heterogeneity` (+ the report keys responder_analysis / erd), rerenders
results.md. Responders 3 of 20, CI [0.0321, 0.3789]; obs equals the stored csp_lda within score for all 20 subjects.
LS < 0 in 13 of 20; Spearman rho -0.6351, p 0.0026. Afterwards G0 + G4 + G5: 16 passed.
Inspections: docs/INSPECTION_claude_v0.3.md (Claude on the Codex diff; the earlier version, written when the diff was
empty, is in commit 29539e7) and docs/INSPECTION_codex_v0.3.md (Codex on the Claude diff).
