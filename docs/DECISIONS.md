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

---

# v0.3 Phase 0 decisions (Head chef, base/v0.3, 2026-11-20)

## v0.3 channel indices (PRD_v0.3 section 7 item 3)
Evidence: `mne.io.read_raw_edf(S001R04.edf)` then `mne.datasets.eegbci.standardize(raw)`, MNE 1.13.2, 64 channels,
160.0 Hz. Raw names 8, 10, 12 are `C3..`, `Cz..`, `C4..`; standardized names `C3`, `Cz`, `C4`; `raw.ch_names.index`
gives C3 = 8, Cz = 10, C4 = 12 (0-based). bci/data.py keeps all 64 EEG channels in file order (no reorder), so these
are the indices into X. The full standardized list is `bci/channels.py` PHYSIONET_CHANNELS. Gate G12 checks the map;
with BCI_REAL_DATA=1 it also checks the names in the EDF file.

## v0.3 speed baseline (PRD_v0.3 section 7 item 8)
One v0.2 `csp_lda` fit (base/v0.3 = main code, before any S1 change) on `make_synthetic(n_subjects=1,
trials_per_subject=850, seed=1)`, shape (850, 64, 480), OMP/OPENBLAS/MKL threads = 2, after one warm-up fit:
6.518 s, 6.243 s, 6.267 s. Median 6.267 s. G9 limit = 25 % = 1.567 s. Probe: `.cache/probes/p0_baseline.py`
(git-excluded). cProfile of one fit (5.92 s total): mne CSP `_csp_estimate` 4.83 s, of which rank estimation
(`_compute_rank_raw_array`, SVD) 3.55 s and the regularized covariance 1.07 s; the band-pass is the rest.
So the filter cache alone cannot reach 25 %: S1 must also remove the per-fit cost in the CSP step. Any change to the
CSP numerics must keep G3 and G8, and must be written in docs/claude/DECISIONS.md. v0.3 results are not required
to equal v0.2 results.
G9 times the fit as CV sees it: cache warm for a 900-trial array, each timed fit on a new 850-row subset.

## Other Phase 0 decisions
- PRD_v0.3.md was untracked on main. The rule is "do not edit the root folder, no merge into main", so the Head chef
  committed a copy on base/v0.3. All v0.3 branches see it there.
- Dataset-dependent contract: `contracts.DATASETS` + `$BCI_DATASET` read at call time, because registry factories take
  no argument (v0.2 contract). The v0.2 constants stay for PhysioNet.
- Stroke window 0.5 to 3.498 s after the motor-imagery onset (1500 samples at 500 Hz, native rate, no resampling),
  29 EEG channels, common average reference, 1 to 40 Hz: fixed in config.yaml before any stroke data was loaded.
- G4: a non-ok or missing model is now a FAIL, and checking no model is a FAIL. The v0.2 results/results.json
  (4 timeouts) therefore fails G4 on every branch until S5 replaces it. That failure is real, not a test bug.
- Owner-scoped gates: G8, G9, G10 (Claude) and G11, G12 (Codex) run on the owner branch and integration/v0.3, and
  FAIL there if the module is missing. On main, base/v0.3 and the other branch they skip (that code is not the
  branch's work). G1 stroke-shape test: classical models on claude/*, advanced models on codex/*, all on integration.
- G11/G12 were probed with Head-chef reference implementations (`.cache/probes/ref/`, git-excluded): all pass, and
  2 planted bugs (flipped LS sign, ">" instead of ">=" in p) are caught.
