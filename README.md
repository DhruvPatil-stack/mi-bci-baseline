# Motor imagery BCI v0.2 (CSP, FBCSP, tangent space, EEGNet-lite)

Decodes imagined left fist vs right fist from EEG. Healthy subjects (PhysioNet EEG Motor
Movement/Imagery, runs 4, 8, 12). This is not a stroke cohort and not a medical device. No clinical claim.
AI agents (Claude Code and Codex) wrote this code.

Run: `python run_all.py` (PhysioNet) or `python run_all.py --synthetic`. Results: `results.json`,
`results.md`, figures, `feedback.png`. Every reported number comes from `results.json`.

Data source: `physionet`. Commit: `4b790eb1d43d9bf07af9fc966e07b711696f5c14`.

## Model status

- `csp_lda`: timeout: time budget of 40 min exceeded during calibration
- `fbcsp_lr`: timeout: time budget of 40 min exceeded during permutation
- `ts_lr`: timeout: time budget of 40 min exceeded during calibration
- `eegnet_lite`: timeout: time budget of 40 min exceeded during cross_subject

## Finished blocks (from results.json, including models that timed out)

Balanced accuracy. A model with status timeout keeps the blocks it finished before the budget ran out.

| Model | Status | Within mean (std) | Cross mean (std) | Permutation within / cross | Calibration k done |
|---|---|---|---|---|---|
| csp_lda | timeout | 0.5479 (0.1653) | 0.5588 (0.0346) | 0.4902 / 0.5047 | [0, 4, 8, 16, 24] |
| fbcsp_lr | timeout | 0.5645 (0.1285) | 0.5597 (0.0477) | not finished | none |
| ts_lr | timeout | 0.5513 (0.1396) | 0.5534 (0.0471) | 0.4972 / 0.5030 | [0, 4, 8, 16, 24] |
| eegnet_lite | timeout | 0.5435 (0.0826) | not finished | not finished | none |

## Gate G4 (plausibility, physionet only)

- No G4 failure.
- WARNING: csp_lda: status timeout, not checked
- WARNING: fbcsp_lr: status timeout, not checked
- WARNING: ts_lr: status timeout, not checked
- WARNING: eegnet_lite: status timeout, not checked

The G4 ranges are plausibility limits from general experience, not published values.

## Feedback simulation

`feedback.png`: one trial of subject `1` replayed through the feedback model.

## Data and citations

PhysioNet data is open. Schalk et al., 2004 (BCI2000). Goldberger et al., 2000 (PhysioNet).
