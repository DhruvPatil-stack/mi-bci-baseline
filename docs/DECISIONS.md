# Integration decisions: calibration experiment (integration/v0.2)

Human-approved: `bci/config.yaml` on integration/v0.2 only. `calibration_repeats` 10 -> 3; new key
`calibration_time_budget_min: 120` for the calibration-only stage. No other setting changed. main is unchanged.

## Seconds per calibration fit (measured)
One fit + predict on PhysioNet subjects 1-20 (cached), first target of `calibration_splits(k=24, n_repeats=1)`,
single process, 2 BLAS threads (same as run_all workers). Probe: `.cache/time_calib.py` (git-excluded).

| Model | source + target fit (879 rows, predict 21) | target-only fit (24 rows, predict 21) |
|---|---:|---:|
| csp_lda | 7.77 s | 0.23 s |
| ts_lr | 7.41 s | 0.23 s |
| fbcsp_lr | 36.37 s | 0.69 s |

csp_lda breakdown of the 879-row fit: bandpass 0.90 s, CSP (mne, ledoit_wolf) 6.12 s, LDA 0.002 s.

## Why csp_lda hit the 40 min limit
Cause: fit count x per-fit cost, not a defect. With 10 repeats the calibration stage needs 20 + 4 x 20 x 10 =
820 source + target fits of about 880 rows each. At the measured 7.77 s per fit that is about 106 min for those
fits alone (estimate from the measured rate, not a measured run), on top of within / cross / permutation, so the
40 min model budget ran out during calibration after k = 0 (results.json: `time budget of 40 min exceeded during
calibration`). The per-fit cost sits in the CSP step of `bci/models_classical.py` (Claude C2 file), which is
outside the scope allowed for a fix here (evaluate.py or integration files). evaluate.py does no extra work per
fit (one fresh estimator, one fit, one predict), so there was no evaluate or integration cause to fix.
No fix applied. Contention in the first run (4 model workers in parallel) can only have made it slower.

## Estimates for 3 repeats (from the measured per-fit times)
Fits per model: 20 + 4 x 20 x 3 = 260 source + target, 240 target-only.
- csp_lda: 260 x 7.77 + 240 x 0.23 = about 2075 s (about 35 min). Run.
- ts_lr: 260 x 7.41 + 240 x 0.23 = about 1982 s (about 33 min). Run.
- fbcsp_lr: 260 x 36.37 + 240 x 0.69 = about 9622 s (about 160 min), above the 60 min limit. NOT run.

## Code changes for this stage
- `bci/evaluate.py` (Claude branch, 3f75445, merged): `_calibration` also returns `per_target` (mean bal_acc per
  target subject over its draws, per k); new `run_calibration(name, X, y, groups, budget_min)` runs only the
  calibration stage with its own budget and keeps finished k values on timeout. Locked G0/G1/G2 + tests/claude on
  the Claude branch: 31 passed, 6 skipped.
- `run_all.py --calibration-only MODEL...` (integration): reruns only calibration on PhysioNet, moves the old
  calibration block to `calibration_v1` (old numbers kept), stores the new block, its status and runtime.
- Bootstrap (run_all.py `add_bootstrap`): 10000 resamples of subjects with replacement, percentile 95% interval,
  seeded with SEED. Intervals for each curve mean, and for paired per-subject differences versus the same
  subject's k = 0 source-only score. "Beats k = 0" means the lower bound of the difference interval is above 0.

## Measured calibration-only run (3 repeats, csp_lda and ts_lr in parallel)
csp_lda: status ok, 4254.4 s. ts_lr: status ok, 5524.4 s (.sync/run_calib.log). Both took longer than the
single-process estimates above (about 2075 s and 1982 s). The two workers ran at the same time; the cause of the
overrun was not measured. fbcsp_lr was not run; with estimates running low by this much, the about 160 min
estimate for fbcsp_lr (already above 60 min) supports that decision more strongly. Within, cross and permutation blocks in results.json are unchanged (checked against the pre-run backup).
Results and intervals: docs/CALIBRATION.md.
