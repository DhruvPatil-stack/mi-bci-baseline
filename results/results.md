# Motor imagery model results

Balanced accuracy, mean ± standard deviation. Counts are the number of finished subjects or folds (`len(per_subject)` or `len(per_fold)`). A status of partial means the model did not finish all evaluation steps.

| Model | Status | Within subject | Cross subject | Permuted within | Permuted cross | Calibration k completed |
|---|---|---:|---:|---:|---:|---|
| csp_lda | ok | 0.5479 ± 0.1653 (n=20) | 0.5588 ± 0.0346 (n=5) | 0.4902 | 0.5047 | 0, 4, 8, 16, 24 |
| fbcsp_lr | ok | 0.5645 ± 0.1285 (n=20) | 0.5597 ± 0.0477 (n=5) | 0.5075 | 0.5103 | 0, 4, 8, 16, 24 |
| ts_lr | ok | 0.5513 ± 0.1396 (n=20) | 0.5534 ± 0.0471 (n=5) | 0.4972 | 0.5030 | 0, 4, 8, 16, 24 |
| eegnet_lite | ok | 0.5435 ± 0.0826 (n=20) | 0.7072 ± 0.0784 (n=5) | 0.5039 | 0.4790 | — |

## Calibration values

Only completed calibration points are shown. Scores are balanced accuracy.

| Model | Status | k | Source + target | Target only |
|---|---|---:|---:|---:|
| csp_lda | ok | 0 | 0.5639 | — |
| csp_lda | ok | 4 | 0.5640 | 0.5075 |
| csp_lda | ok | 8 | 0.5665 | 0.5243 |
| csp_lda | ok | 16 | 0.5712 | 0.5610 |
| csp_lda | ok | 24 | 0.5638 | 0.5619 |
| fbcsp_lr | ok | 0 | 0.5506 | — |
| fbcsp_lr | ok | 4 | 0.5549 | 0.5015 |
| fbcsp_lr | ok | 8 | 0.5579 | 0.5145 |
| fbcsp_lr | ok | 16 | 0.5628 | 0.5184 |
| fbcsp_lr | ok | 24 | 0.5775 | 0.5291 |
| ts_lr | ok | 0 | 0.5557 | — |
| ts_lr | ok | 4 | 0.5815 | 0.4963 |
| ts_lr | ok | 8 | 0.5866 | 0.5074 |
| ts_lr | ok | 16 | 0.6010 | 0.5168 |
| ts_lr | ok | 24 | 0.5785 | 0.5297 |

## Paired comparisons

Wilcoxon signed-rank on matched within-subject balanced accuracies; median difference is model minus csp_lda. Holm step-down adjusts p-values across the 3 completed-model comparisons.

| Model | Median difference | Raw p | Holm p |
|---|---:|---:|---:|
| fbcsp_lr | 0.0208 | 0.3719 | 1.0000 |
| ts_lr | -0.0459 | 0.8408 | 1.0000 |
| eegnet_lite | 0.0336 | 0.8408 | 1.0000 |

## Figures

![Model comparison](fig1_models.png)

![Calibration curves](fig2_calibration.png)

![Permutation control](fig3_permutation.png)

## Limits

The results metadata lists 20 subjects and 900 total trials. The subjects are healthy volunteers. Statistical power is limited by the cohort size. These results do not establish clinical benefit or performance for a stroke cohort.
