# Claude branch blockers

## C3 `bci/evaluate.py`: calibration block projected to exceed time_budget_min (40 min)

All C3 locked checks pass (G2 no-leak, contracts -k evaluate, synthetic recovery -k evaluate). The open problem is
runtime, which needs a Head-chef config decision. evaluate.py cannot fix it alone: it must not transform or cache X,
and parallel fits would break the G2 spy.

Measured, fit+predict seconds per fit, min of 3 runs, on make_synthetic(n_subjects=20, trials_per_subject=44)
(SYNTHETIC - NOT VALID). Another python process (PID 15764) was using the CPU at the same time.

| model    | 836 train rows | 280 rows | 24 rows |
|----------|---------------:|---------:|--------:|
| csp_lda  | 5.033 | 1.730 | 0.157 |
| fbcsp_lr | 24.774 | 9.004 | 0.752 |

Calibration fit count for 20 subjects, with calibration_k [0, 4, 8, 16, 24] and 10 repeats:
20 + 4 x 10 x 20 = 820 source_plus_target fits (about 836 rows each), plus 800 target_only fits (4-24 rows each).

Projection, not measured: the calibration block alone takes about 69 min for csp_lda and about 5.6 h for fbcsp_lr.
Both are over the 40 min whole-model budget. run_model will return status "timeout" and keep within_subject,
cross_subject and permutation, but drop calibration.

Measured end to end: run_model("csp_lda", make_synthetic(), calibration=True) on 8 x 40 took 808.4 s, status ok.

**Resolution (Head chef):** config.yaml is kept as is (40 min budget, 10 repeats). The Head chef chose the
partial-curve option. run_model computes calibration k by k in ascending order. On a timeout during calibration
it keeps the finished k values as a valid calibration block and sets "calibration_partial": true, with status
"timeout" (PRD: stop, record, report). Implemented in bci/evaluate.py (see DECISIONS.md C3 item 11).
