# Integration v0.3 (integration/v0.3, worktrees\v3-integration)

The v0.2 integration notes are in this file on main and tag v0.2 (`git show v0.2:docs/INTEGRATION.md`).
Built 2026-11-20 by the Claude lead. Base: base/v0.3 (18b78b2). Merged: claude/speed-stroke (06eb7d3) as 7276571.
codex/heterogeneity was NOT merged: it holds no commit and no uncommitted file beyond base/v0.3 (checked with
`git -C worktrees/v3-codex status --short` and `git log`). Codex wrote no marker after P0_DONE
(.sync3/STATE_codex.md last changed 03:52: "wait for .sync3\P0_DONE"). Tickets H1-H4 were not delivered.

## run_all.py v0.3 (1e7df94)
Per-model checkpoint files under OUT/checkpoints (`--fresh` deletes them), results.json after every finished model,
`--dataset stroke` (default OUT results/stroke/, never a fallback), responder analysis and ERD check called only when
bci/analysis.py and bci/erd_check.py exist, else results.json records `"status": "not measured"` with the reason.
Synthetic smoke run (BCI_ENFORCE_TIME_BUDGET=0): exit 0, 4 models ok, 875 s wall time.

## S5 runs
- PhysioNet: `run_all.py --fresh`, 06:48 to 07:55, exit 0. All 4 models status ok with every stage complete.
  runtime_s: csp_lda 868.8, fbcsp_lr 3508.0, ts_lr 4001.1, eegnet_lite 3606.4 (v0.2: all 4 timeout at 40 min).
  The csp_lda, fbcsp_lr, ts_lr within/cross means and the calibration curves equal the v0.2 values to 4 decimals
  (e.g. csp_lda within 0.5479, ts_lr k = 4 difference 0.0258 [0.0032, 0.0520]), so the S1 cache and csp_rank change
  did not move these results. heterogeneity: responders and ERD "not measured" (Codex modules missing).
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
| G3 synthetic recovery | PASS (not slow) | 17 passed with G9 and G6-unit; slow eegnet recovery: see G6 line |
| G4 real plausibility | PASS | warnings: csp_lda and fbcsp_lr subject 7 within bal_acc 0.9783 > 0.95; csp_lda within mean 0.5479 outside (0.55, 0.9) |
| G5 report numbers | PASS | 9 passed, including results.md vs results.json on the real results |
| G6 two seeded runs | FAIL (run 1), rerun pending | 08:06-08:52: `AssertionError: two seeded runs gave different results.json`. The only differing key: meta.git_commit `23811659...` vs `23811659...-dirty` (I edited docs/INTEGRATION.md while run 1 ran). Every other value equal. Rerun on a clean tree: see the G6 rerun line below |
| G7 fresh venv | not run | opt-in (BCI_RUN_G7), not run this night |
| G8 cache | PASS | 7 passed |
| G9 speed | PASS alone, FAIL under load | PASS in the gate run (08:00, nothing else running). FAIL in the inspector's full-suite run, which ran at the same time as the G6 run_all workers (`test_csp_lda_fit_speed` failed). The S1 builder measured median 1.249 s under partial load and 1.573 s / 1.713 s at 79-94 % CPU. The margin under the 1.567 s limit is small; judge G9 on a quiet machine |
| G10 wall clock | PASS | 3 passed |
| G11 responders | FAIL | 6 errors: `Failed: bci/analysis.py is required on integration/v0.3 but does not exist` |
| G12 ERD | FAIL | 5 errors: `Failed: bci/erd_check.py is required on integration/v0.3 but does not exist`; the channel-map tests pass (also on the real EDF names) |
| G13 stroke loader | PASS | 2 passed with BCI_EXPECT_STROKE=1 |
| G14 hygiene | PASS | 3 passed |

The G1, G11 and G12 failures are in Codex-owned files. Integration fixes only integration files, so they stay failed.
