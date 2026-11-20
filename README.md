# Motor imagery BCI v0.3 (CSP, FBCSP, tangent space, EEGNet-lite)

Decodes imagined left vs right hand movement from EEG. This folder: Healthy subjects (PhysioNet EEG Motor Movement/Imagery, runs 4, 8, 12).
Healthy-subject and stroke-patient results are kept in separate folders (`results/` and `results/stroke/`).
Not a medical device. No clinical claim. AI agents (Claude Code and Codex) wrote this code.

Run: `python run_all.py` (PhysioNet), `python run_all.py --dataset stroke --out results/stroke`, or
`python run_all.py --synthetic`. Every reported number comes from `results.json` in the same folder.

Data source: `physionet`. Commit: `1e7df9457ae747cdc24ead71138a029ef7f51ba6`.

## Model status

- `csp_lda`: ok
- `fbcsp_lr`: ok
- `ts_lr`: ok
- `eegnet_lite`: ok

## Blocks (from results.json)

Balanced accuracy.

| Model | Status | Within mean (std) | Cross mean (std) | Permutation within / cross | Calibration k done |
|---|---|---|---|---|---|
| csp_lda | ok | 0.5479 (0.1653) | 0.5588 (0.0346) | 0.4902 / 0.5047 | [0, 4, 8, 16, 24] |
| fbcsp_lr | ok | 0.5645 (0.1285) | 0.5597 (0.0477) | 0.5075 / 0.5103 | [0, 4, 8, 16, 24] |
| ts_lr | ok | 0.5513 (0.1396) | 0.5534 (0.0471) | 0.4972 / 0.5030 | [0, 4, 8, 16, 24] |
| eegnet_lite | ok | 0.5435 (0.0826) | 0.7072 (0.0784) | 0.5039 / 0.4790 | none |

## Responders and ERD check

Responders (csp_lda, 200 label shuffles, p < 0.05): 3 of 20, 95% Clopper-Pearson interval of the proportion [0.0321, 0.3789]; expected false responders 1.00.
ERD lateralization (mu): LS < 0 in 13 of 20 subjects; Spearman rho vs csp_lda within score -0.6351, p 0.0026, n 20.

## Gate G4 (plausibility, physionet only)

- No G4 failure.
- WARNING: csp_lda subject 7 within bal_acc 0.9783 > 0.95
- WARNING: fbcsp_lr subject 7 within bal_acc 0.9783 > 0.95
- WARNING: csp_lda within mean 0.5479 outside (0.55, 0.9)

The G4 ranges are plausibility limits from general experience, not published values.

## Feedback simulation

`feedback.png`: one trial of subject `1` replayed through the feedback model.

## Data and citations

PhysioNet data is open. Schalk et al., 2004 (BCI2000). Goldberger et al., 2000 (PhysioNet).
Stroke data: Liu et al., An EEG motor imagery dataset for brain computer interface in acute stroke patients, Scientific Data 11, 131 (2024), CC BY 4.0. Raw data is not redistributed here.
Code license: MIT (`LICENSE`).
