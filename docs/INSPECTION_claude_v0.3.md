# Inspection of the Codex files, v0.3 (Claude, cross-vendor, KITCHEN rule 10)

Inspector: Claude (Opus 5.5, xhigh), new session, 2026-11-20. Read: PRD_v0.3.md (incl. tickets H1-H4), the diffs
below, bci/models_advanced.py, bci/report.py, bci/evaluate.py (procedures), bci/splits.py, tests/locked/
test_contracts.py:348-372, results/results.json, results/results.md, results/stroke/results.json. No tracked file edited.

**Diffs.** `git diff base/v0.3 codex/heterogeneity -- <Codex paths>`: EMPTY (both refs = 18b78b2).
`git -C worktrees/v3-codex status --short --ignored`: EMPTY. `git diff main integration/v0.3 -- <Codex paths>`: EMPTY,
so integration runs the v0.2 Codex files. `git log --all -- bci/analysis.py bci/erd_check.py`: no commit anywhere;
`git stash list`: empty; `.sync3\` has no `P0_REVIEW_DONE` or `CODEX_DONE`; `tests/codex/` holds only the 3 v0.2 files.

## HIGH
1. **H1-H4 not delivered; Q1-Q3 unanswerable.** bci/analysis.py and bci/erd_check.py do not exist. results.json
   `heterogeneity.responders`: `"status": "not measured", "reason": "bci/analysis.py not on this branch (Codex ticket
   H1 not delivered)"`; `erd` the same for H2. No responder count, p-value, LS or Spearman value exists. Locked G11/G12
   give 11 errors (`Failed: bci/erd_...`, `Failed: bci...` in test_erd.py, test_responders.py). PRD 1, 9 H1-H4, 12 G11/G12.
2. **eegnet_lite assumes 64 channels: fails G1, crashed the stroke run.** bci/models_advanced.py:11 imports PhysioNet
   `N_CHANNELS`; :38 spatial conv `(N_CHANNELS, 1)`; :56-57 reject other counts. results/stroke/results.json:
   `"ValueError: expected trials x 64 channels x samples, got (32, 29, 1500)"`, status `error`, 5.87 s (32 = 4/5 of
   40 trials per patient, 1880/47: the first within-subject fit). Locked run here: `FAILED tests/locked/
   test_contracts.py::test_estimators_work_on_stroke_shape[eegnet_lite]` with `ValueError: expected trials x 64
   channels x samples, got (48, 29, 1500)`. PRD 7 item 2, G1, Q4. Fix: use `X.shape[1]` or `dataset_spec()["n_channels"]`.
   ts_lr passes the same test.

## MEDIUM
3. **report.py has none of the H3 sections.** `write_report` (bci/report.py:97-184) never reads `results["heterogeneity"]`.
   results.md lacks the per-subject table (score, p, flag), responder count + interval + expected false positives,
   LS + Spearman, and calibration gain by group; it does not even print "not measured". PRD 9 H3, PRD 1.
4. **Limits paragraph omits regression to the mean.** report.py:178-180 / results.md:54 name 20 subjects and 900
   trials only. PRD 4, PRD 9 H3.
5. **Stroke cohort would be labeled synthetic.** report.py:172-175: any `data_source` other than `physionet` prints
   "These are synthetic subjects and trials."; stroke meta has `"data_source": "stroke"`. :179-180 always says results
   "do not establish ... performance for a stroke cohort". PRD 14. No stroke results.md exists yet (results/stroke has
   only results.json), so no wrong file has been written.
6. **eegnet_lite null is one draw.** config.yaml:18 `n_permutations_eegnet: 1`: the 0.4790 cross permutation is a single
   shuffled run, and a label shuffle cannot detect test-feature leakage. Weak G3/G4 support for 0.7072 (config FROZEN).

## LOW
7. **eegnet_lite cross 0.7072 vs within 0.5435: no leak visible.** evaluate.py:66-71 builds a fresh estimator per fold;
   fit sees only `X[fit_idx]`. models_advanced.py:73-75: channel mean/std from fit rows only; :88, :94 `eval()`, so
   BatchNorm uses running statistics at predict. Cross folds in results.json have disjoint test subjects covering 1-20
   (splits.py:28-41). Per-fold eegnet 0.7556/0.6917/0.6280/0.6449/0.8160 beat every classical fold (max 0.6233).
   My probe, SYNTHETIC data only (5 subjects, 1 fold): batch vs one-trial-at-a-time predictions differ <= 5.96e-08;
   shuffled order 0.0; |mean_ - train mean| 2.07e-16 vs |mean_ - test mean| 6.62e-09; std_ rel. error vs train 1.47e-08.
   Plausible cause: cross folds train on ~4/5 of 900 trials, within folds on ~4/5 of one subject. Not run, would test it:
   (a) cross-subject fit subsampled to within-subject size; (b) per-subject scores from cross predictions (only per-fold
   stored); (c) more permutation repeats on real data; (d) fit after deleting test-subject rows from X.
8. **Holm family size named.** report.py:157-158 prints "across the 3 completed-model comparisons"; step-down :32-36
   is monotone. PRD 9 H3 met for its one Holm use.
9. **G5 holds.** My matcher: 60 decimals in results.md, 0 absent from results.json (at printed precision); integers
   0, 3, 4, 5, 8, 16, 20, 24, 900 also present.
10. report.py:104-107 rewrites results.json (adds `stats`) when missing: a report step mutating results. eegnet_lite has
    no calibration block (results.md "—"): integration choice, not a Codex defect.
11. ts_lr (models_advanced.py:14-21): covariance and tangent reference fit on train rows inside the pipeline; no channel
    or sfreq constant. No leak, unit or label defect found in either estimator.

**Locked suite** `-m "not slow"`, this session: `2 failed, 82 passed, 4 skipped, 2 deselected, 4 warnings, 11 errors in
864.30s`. Failed: the eegnet_lite stroke-shape test (finding 2) and `test_speed.py::test_csp_lda_fit_speed` (G9,
Claude-owned, not inspected here). Errors: finding 1.
