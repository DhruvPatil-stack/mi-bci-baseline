# Calibration experiment (integration/v0.2)

Source: `results/results.json`, `models.<m>.calibration` (run `meta.calibration_run`: commit dd71c11,
calibration_repeats 3, budget 120 min, PhysioNet subjects 1-20). Both models finished all k with status `ok`
(csp_lda 4254.4 s, ts_lr 5524.4 s). Scores are balanced accuracy averaged over 20 target subjects.
The old 10-repeat block is kept as `calibration_v1` (k = 0 only). The new k = 0 values equal the old ones
(0.5639 csp_lda, 0.5557 ts_lr; equal to full float precision).

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

## All k values (mean and 95% CI; differences versus k = 0)

csp_lda

| k | source_plus_target | target_only | source_plus_target - k0 | target_only - k0 |
|---:|---|---|---|---|
| 0 | 0.5639 [0.5202, 0.6096] | - | 0.0000 [0.0000, 0.0000] | - |
| 4 | 0.5640 [0.5220, 0.6106] | 0.5075 [0.4836, 0.5405] | 0.0001 [-0.0179, 0.0191] | -0.0564 [-0.0979, -0.0149] |
| 8 | 0.5665 [0.5250, 0.6122] | 0.5243 [0.4948, 0.5602] | 0.0026 [-0.0124, 0.0191] | -0.0395 [-0.0771, 0.0008] |
| 16 | 0.5712 [0.5204, 0.6249] | 0.5610 [0.5107, 0.6237] | 0.0074 [-0.0120, 0.0272] | -0.0028 [-0.0522, 0.0490] |
| 24 | 0.5638 [0.5201, 0.6104] | 0.5619 [0.5022, 0.6314] | -0.0001 [-0.0301, 0.0298] | -0.0020 [-0.0678, 0.0659] |

ts_lr

| k | source_plus_target | target_only | source_plus_target - k0 | target_only - k0 |
|---:|---|---|---|---|
| 0 | 0.5557 [0.5227, 0.5966] | - | 0.0000 [0.0000, 0.0000] | - |
| 4 | 0.5815 [0.5475, 0.6230] | 0.4963 [0.4760, 0.5189] | 0.0258 [0.0032, 0.0520] | -0.0594 [-0.0944, -0.0257] |
| 8 | 0.5866 [0.5487, 0.6314] | 0.5074 [0.4823, 0.5359] | 0.0310 [0.0037, 0.0623] | -0.0483 [-0.0847, -0.0132] |
| 16 | 0.6010 [0.5539, 0.6518] | 0.5168 [0.4802, 0.5611] | 0.0453 [0.0129, 0.0827] | -0.0389 [-0.0761, -0.0037] |
| 24 | 0.5785 [0.5346, 0.6270] | 0.5297 [0.4748, 0.5882] | 0.0229 [-0.0165, 0.0653] | -0.0259 [-0.0867, 0.0387] |

## Limits
- fbcsp_lr not run: estimated about 160 min at 3 repeats (docs/DECISIONS.md), above the 60 min rule.
  eegnet_lite is not in `calibration_models`.
- 3 draws per target per k; 20 subjects. All curve means lie between 0.4963 and 0.6010 (chance 0.5).
- No correction for testing several k values.
