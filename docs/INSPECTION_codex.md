# Codex inspection of Claude branch

Scope: PRD C1-C5 and `git diff main..claude/foundation-classical`. The requested fresh `codex exec` session could not initialize (`Access is denied`); this is a manual read-only fallback. No Claude-owned or frozen files were edited.

## Findings

1. **High — the main calibration question may remain unanswered.** `bci/evaluate.py` computes 10 repeats for each positive k and each target, refitting source-plus-target and target-only models every time. `docs/claude/BLOCKERS.md` projects calibration alone beyond the configured 40-minute whole-model budget for CSP and FBCSP. `run_model` then marks the model `timeout` and retains only completed k values. This is disclosed in the branch, but the requested full calibration curves are unlikely on the 20-subject run. The projection is not a measured real-data result.
2. **Medium — the 40-minute budget can be exceeded by a fit.** `_check_time` runs immediately before `est.fit`, and neither the fit nor prediction is interruptible. A long fit that starts near the deadline can run past it. The status becomes `timeout` only before a later fit; a final overrun can return `ok`.
3. **Medium — any loader error triggers synthetic fallback.** `load_with_fallback` catches every `Exception`, including a shape assertion or a processing bug, then returns labeled synthetic data after three retries. The label prevents passing it off as PhysioNet, but a real-path defect can be masked unless `meta.data_source` and the logged error are inspected.
4. **Low — external cache path is accepted.** `data_dir()` creates the value of `BCI_DATA_DIR` without checking that it is inside the workspace. The default is internal; an externally set environment path would violate the platform folder constraint.

## Checks from the diff

- **Test-set fitting:** no direct fit on test data found. `_fit_predict` fits a fresh registry estimator on `X[fit_idx]` and predicts on `X[pred_idx]`; within, cross, and calibration use frozen split indices. Classical pipelines fit CSP, scaling, and logistic regression inside `fit`.
- **Labels and units:** `epochs_from_raw` selects annotations by T1/T2 description, maps T1→0 and T2→1, drops T0, multiplies MNE volts by `unit_scale`, casts to float32, and asserts 64×480. No label swap or unit error found in the diff.
- **Invented numbers and scope:** no hard-coded result scores or hyperparameter search found in the source. Documentation distinguishes measured timings from projections. I did not independently remeasure the documentation values during this diff-only inspection.
