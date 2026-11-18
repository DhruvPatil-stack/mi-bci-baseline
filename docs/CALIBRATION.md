# Calibration experiment (integration/v0.2)

Source: `results/results.json`, `models.<m>.calibration` (run `meta.calibration_run`: commit dd71c11,
calibration_repeats 3, budget 120 min, PhysioNet subjects 1-20). Both models finished all k with status `ok`
(csp_lda 4254.4 s, ts_lr 5524.4 s). Scores are balanced accuracy averaged over 20 target subjects.
The old 10-repeat block is kept as `calibration_v1` (k = 0 only). The new k = 0 values equal the old ones
(0.5639 csp_lda, 0.5557 ts_lr).

Reference = each subject's k = 0 source-only (zero-shot) score. Difference = paired per-subject difference
versus that reference. 95% interval = bootstrap over subjects (10000 resamples, percentile).
"Beats" = lower bound of the difference interval above 0.

## (a) Smallest k where source_plus_target beats k = 0
| Model | k | Mean | Difference vs k = 0 | 95% CI of difference |
|---|---:|---:|---:|---|
| ts_lr | 4 | 0.5815 | 0.0258 | [0.0032, 0.0520] |
| csp_lda | none | - | - | no crossover: every interval includes 0 (k = 16: 0.0074, [-0.0120, 0.0272]) |

ts_lr also beats k = 0 at k = 8 (0.0310, [0.0037, 0.0623]) and k = 16 (0.0453, [0.0129, 0.0827]), but not
at k = 24 (0.0229, [-0.0165, 0.0653]).

## (b) Smallest k where target_only beats the k = 0 zero-shot score
No crossover for either model at any k up to 24.
| Model | k | target_only mean | Difference vs k = 0 | 95% CI of difference |
|---|---:|---:|---:|---|
| csp_lda | 24 | 0.5619 | -0.0020 | [-0.0678, 0.0659] |
| ts_lr | 24 | 0.5297 | -0.0259 | [-0.0867, 0.0387] |

At small k target_only is below zero-shot: csp_lda k = 4 -0.0564 [-0.0979, -0.0149]; ts_lr k = 4
-0.0594 [-0.0944, -0.0257], k = 16 -0.0389 [-0.0761, -0.0037].

## Limits
- fbcsp_lr not run: estimated about 160 min at 3 repeats (docs/DECISIONS.md), above the 60 min rule.
  eegnet_lite is not in `calibration_models`.
- 3 draws per target per k; 20 subjects. All scores sit near 0.55 to 0.60, close to chance (0.5).
- No correction for testing several k values.
