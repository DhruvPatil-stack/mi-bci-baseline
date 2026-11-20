# PRD v0.3: Speed, Responders, and Stroke Data

Status: DRAFT v0.3. Builds on v0.2 (tag `v0.2`, on `main`). `PRD.md` stays as history.
Where this file and `PRD.md` differ, this file wins.
Builders: AI agents only. 1 Claude Code agent and 1 Codex agent. Each works on its own branch.
Kitchen rules: `docs/KITCHEN.md`. The tier names come from that file.

---

## 0. How to read this file

- The Claude Code agent reads sections 1 to 7, section 8 (its tickets), and sections 10 to 16.
- The Codex agent reads sections 1 to 7, section 9 (its tickets), and sections 10 to 16.
- The integration session reads all sections.
- An agent must not edit a file that it does not own. Gate G0 checks this.
- An agent must not edit a file in section 7. The Head chef freezes those files in Phase 0.

---

## 1. Goal and questions

v0.2 gave a working pipeline and a weak result. Balanced accuracy is about 0.55 for all 4 models. The mean hides a split: 2 subjects score above 0.89, and 9 of 20 score 0.50 or lower.

v0.3 makes the pipeline fast. Then it asks 4 questions with data:

1. **Q1.** How many subjects are real responders? Define the rule before you look at the result (section 4).
2. **Q2.** Does the ERD pattern at C3 and C4 match the decoder score? If yes, the pipeline is correct and the non-responders are a physiology effect. If no, look for a pipeline defect.
3. **Q3.** Does calibration help responders, non-responders, or neither?
4. **Q4.** Do Q1 to Q3 hold on stroke patients? (Only if the stroke ticket ships.)

Success: the 4 answers are in `docs/MORNING_REPORT_v0.3.md`. Each answer has a number, an interval, and a limit. An answer of "not measured" is allowed. An invented number is not.

## 2. Non-goals

- No new model families. No hyperparameter search.
- No hardware. No paid API. No API key. CPU only.
- No clinical claim.
- No merge into `main`. The human decides that.

## 3. What changes from v0.2

| v0.2 evidence | v0.3 change |
|---|---|
| The band-pass filter sits inside each estimator. Every fit and predict filters all trials again. | Cache the filtered arrays. Results stay identical (G8). |
| 4 models hit the 40 min limit. Calibration took 4254 s and 5524 s. | Speed gate (G9). The time limit becomes a safety stop only. |
| G6 failed. A wall-clock limit cut 2 runs at different places. | G6 runs without wall-clock limits (G10). |
| G4 passed without checking any model. | G4 fails when it checks nothing. |
| The mean score hides 2 strong and 9 weak subjects. | Responder analysis (H1). |
| No ERD check on real data. | ERD check (H2). |
| `fbcsp_lr` and `eegnet_lite` have no complete results. | Full run on all 4 models (S5). |
| No `.gitignore`, no license, a file named `fable-playbook (2).md` in the root. | Phase 0 fixes these (G14). |

## 4. Theory additions

**ERD lateralization.** Imagined right-fist movement lowers mu power (8-13 Hz) over the left motor cortex (channel C3). Imagined left-fist movement lowers it over the right motor cortex (channel C4).

LS = [ln P(C3, right) − ln P(C3, left)] − [ln P(C4, right) − ln P(C4, left)]

- LS = lateralization score of 1 subject
- P(ch, class) = mean mu-band power at channel ch over the trials of that class
- Expected sign for a healthy subject with a clear ERD: LS < 0

**Responder rule (fixed now, before any result).**

1. Take the within-subject 5-fold balanced accuracy of `csp_lda` for 1 subject. Call it `obs`.
2. Shuffle the labels of that subject 200 times. Repeat the same cross-validation each time. This gives 200 null scores.
3. p = (1 + number of null scores ≥ obs) / (1 + 200).
4. A subject is a **responder** if p < 0.05.
5. With 20 subjects, expect 1 false responder by chance (0.05 × 20). Report this number.
6. Report the responder count with a 95% Clopper-Pearson interval.

**Regression to the mean.** A subject picked for a high score tends to score lower on the next test. Any "responders gain more or less from calibration" result carries this limit. State it in the report.

## 5. Data

**PhysioNet (unchanged).** Subjects 1 to 20. Runs 4, 8, 12. T1 = left fist (0). T2 = right fist (1). 64 channels, 160 Hz, 480 samples, µV, common average reference.

**Stroke dataset (new, optional ticket S4).** Liu et al., "An EEG motor imagery dataset for brain computer interface in acute stroke patients", Scientific Data, 2024. DOI 10.1038/s41597-023-02787-8. It has 50 acute stroke patients and 40 left- or right-hand motor imagery trials for each patient.

The Head chef records these facts in `docs/STROKE_DATASET.md`. Each fact needs a source line (the paper or the data page):

- download URL and file size
- license
- number of channels, channel names, sampling rate
- trial timing and labels
- the patient characteristics file, and whether it holds the affected side

If the license does not allow redistribution of derived results, or the download fails, ticket S4 does not ship. Nothing else depends on it.

## 6. Branches, worktrees, and ownership

Branches:

- `base/v0.3` from `main`. The Head chef commits all frozen files here.
- `claude/speed-stroke` from `base/v0.3`.
- `codex/heterogeneity` from `base/v0.3`.
- `integration/v0.3` from `base/v0.3`.

The folder `worktrees\` already holds v0.2 worktrees. Use new folder names:

```
worktrees\v3-base
worktrees\v3-claude
worktrees\v3-codex
worktrees\v3-integration
```

Sync folder: `.sync3\`. Never use `.sync\`. It holds old v0.2 markers.

Ownership:

```
bci/contracts.py, splits.py, synthetic.py, config.yaml   FROZEN  (Head chef)
bci/channels.py                                          FROZEN  (Head chef)
bci/data.py                  CLAUDE
bci/data_stroke.py           CLAUDE   (new, optional)
bci/cache.py                 CLAUDE   (new)
bci/models_classical.py      CLAUDE
bci/evaluate.py              CLAUDE
bci/models_advanced.py       CODEX    (change only if a test needs it)
bci/analysis.py              CODEX    (new)
bci/erd_check.py             CODEX    (new)
bci/report.py                CODEX
bci/feedback_sim.py          CODEX    (no change planned)
run_all.py, README.md        INTEGRATION
tests/locked/                FROZEN
tests/claude/, docs/claude/  CLAUDE
tests/codex/, docs/codex/    CODEX
docs/STROKE_DATASET.md       FROZEN
.gitignore, LICENSE          FROZEN
```

## 7. Section Z: frozen files (Phase 0, Head chef)

1. **Hygiene (G14).** Write `.gitignore` (`.venv/`, `.venv_g7/`, `.cache/`, `.sync*/`, `worktrees/`, `__pycache__/`, `*.pyc`). Write `LICENSE` (MIT, holder: Dhruv Patil). Move `fable-playbook (2).md` to `docs/fable-playbook.md`.
2. **Contract.** Make the data contract dataset-dependent. A dataset has `n_channels`, `sfreq`, and `n_samples`. PhysioNet keeps 64, 160, and 480. All v0.2 tests keep passing for PhysioNet. No estimator may assume 64 channels or 160 Hz.
3. **`channels.py`.** Give the PhysioNet channel index of C3, Cz, and C4. Verify the indices against the real channel names with MNE (`mne.datasets.eegbci.standardize`). Write the evidence in `docs/DECISIONS.md`.
4. **`config.yaml`.**
   - `time_budget_min` becomes a safety stop. Set it to 180.
   - Add `enforce_time_budget: true`. Tests set it to `false`.
   - Add `n_permutations_subject: 200` and `responder_alpha: 0.05`.
   - Add `erd_band_mu: [8, 13]` and `erd_band_beta: [13, 30]`.
5. **`STROKE_DATASET.md`.** Facts only, with a source line for each (section 5).
6. **Ownership test (G0).** Update the file sets for the 3 new branches and the new files above.
7. **Locked checks.** Write G8 to G14 (section 12). Fix G4 so that it fails when it checks no model.
8. **Speed baseline.** Time 1 `csp_lda` fit on 850 trials of shape (64, 480). Write the seconds in `docs/DECISIONS.md`. G9 uses 25% of that value as the limit.
9. **Plan.** `docs/PLAN.md`, 10 lines at most.
10. **Subagents.** Keep `.claude\agents\` from v0.2.

## 8. Section C: Claude Code tickets

Branch `claude/speed-stroke`, in `worktrees\v3-claude`.

**S1. `bci/cache.py` and `BandPass` change.**
- Goal: filter each array once for each (data hash, band, order, sampling rate). Store the result in memory and in `.cache\filtered\` as `.npy` files. `BandPass.transform` reads from the cache. The estimator API does not change.
- Done: G8 and G9 pass. The cache is safe when several worker processes use it at once.
- Physical check: cached and uncached predictions match to 1e-9 on synthetic data.

**S2. `bci/evaluate.py` changes.**
- Goal: write results to `results.json` after each stage. A rerun skips finished stages. The time limit is a safety stop only. Add the per-subject score table to the output if it is missing.
- Done: G10 passes.

**S3. `bci/models_classical.py` and `bci/data.py`.**
- Goal: no assumption of 64 channels or 160 Hz. All code reads `n_channels` and `sfreq` from the dataset contract.
- Done: all v0.2 tests pass.

**S4. `bci/data_stroke.py` (optional).**
- Goal: `load_stroke(...) -> (X, y, groups)` that follows the new contract. Use the facts in `docs/STROKE_DATASET.md`. Resample or select channels only if the dataset needs it. Write each choice in `docs/claude/DECISIONS.md`.
- Failure rule: if the download or the license check fails, write `docs/claude/BLOCKERS.md`. Do not fall back to synthetic data. Skip the ticket.
- Done: G13 passes.
- Physical check: the median absolute amplitude is between 1 and 100 µV.

**S5. Full run (in `integration/v0.3`, by the lead).**
- Run all 4 models on PhysioNet with every stage complete. Run the same on stroke data if S4 passed.

## 9. Section X: Codex tickets

Branch `codex/heterogeneity`, in `worktrees\v3-codex`.
Import only `contracts.py`, `splits.py`, `synthetic.py`, and `channels.py`. Never import `data.py` or `evaluate.py`.
Develop against `results/results.json` from v0.2 (it is committed on `main`) and against synthetic data.

**H1. `bci/analysis.py`.**
- Goal: `subject_pvalue(estimator_factory, X, y, n_perm, seed)` implements the responder rule of section 4. `classify_responders(...)` returns flags, the count, the Clopper-Pearson interval, and the expected false positives. `calibration_gain_by_group(per_target, flags)` returns the mean gain at each k for responders and non-responders. It includes a bootstrap 95% interval of the difference.
- Done: G11 passes.
- Physical check: a subject with a planted ERD is flagged. Pure-noise subjects are rarely flagged.

**H2. `bci/erd_check.py`.**
- Goal: pure functions on arrays. `band_power(X, sfreq, band)` uses a Welch estimate. `lateralization(X, y, groups, sfreq, ch_c3, ch_c4, band)` returns LS for each subject (section 4). `lateralization_vs_accuracy(ls, acc)` returns the Spearman correlation and its p-value.
- Done: G12 passes.
- Physical check: on synthetic data with a planted ERD, the sign of LS is as expected.

**H3. `bci/report.py` changes.**
- Goal: add these to `results.md`:
  - per-subject table (score, p-value, responder flag)
  - responder count with interval and expected false positives
  - LS for each subject, and the Spearman result
  - calibration gain for responders and non-responders
  - a "Limits" paragraph that names the regression-to-the-mean effect and the 20-subject sample
- Name the Holm family size wherever you use Holm.
- Done: G5 passes. Every number in `results.md` exists in `results.json`.

**H4. `tests/codex/`, `docs/codex/`.** Tests for H1 to H3 that do not repeat `tests/locked/`.

## 10. Section I: integration

1. Create `integration/v0.3` from `base/v0.3` in `worktrees\v3-integration`.
2. Before the merge, check `worktrees\v3-codex` for uncommitted files. The Codex sandbox could not commit in v0.2. If files are uncommitted, commit them on `codex/heterogeneity`:
   `git -C worktrees\v3-codex add -A; git -C worktrees\v3-codex commit -m "codex work"`
3. Merge both branches. Update `run_all.py`: run the ERD check and the responder analysis on real data, and the stroke run if S4 passed.
4. Run all gates. Write each failure with its exact error text in `docs/INTEGRATION.md`.
5. Cross-vendor inspection in new sessions. Codex reviews the Claude files. Claude reviews the Codex files. Each writes `docs/INSPECTION_<vendor>_v0.3.md`.
6. Write `docs/MORNING_REPORT_v0.3.md` (40 lines at most). It must answer Q1 to Q4 with numbers, intervals, and limits.

## 11. Kitchen assignment

Rule 1: choose the cook by the cost of a mistake. GPT-6.2 Astra is not available. Use GPT-6.2 Sol at the highest effort in its place.

| Ticket | Branch | Tier | Model and effort | Cost of a mistake |
|---|---|---|---|---|
| Phase 0 plan, frozen files, locked checks | base | Head chef | Opus 5.5 + fable-thinking, xhigh | Every later step depends on it |
| Phase 0 plan review | base | Head chef (other vendor) | GPT-6.2 Sol, xhigh | A weak check passes bad code |
| S1 cache | claude | Sous chef | Opus 5.5, xhigh | A wrong cache gives plausible wrong scores |
| S2 evaluate changes | claude | Sous chef | Opus 5.5, xhigh | A leak or a lost stage |
| S3 model and data changes | claude | Line cook | Sonnet 5.5 | Tests catch errors |
| S4 stroke loader | claude | Sous chef | Opus 5.5, xhigh | Wrong labels or units look plausible |
| tests and docs | claude | Prep cook | Haiku 5.5 | Low |
| H1 responder analysis | codex | Sous chef | GPT-6.2 Sol, xhigh | A wrong null gives false responders |
| H2 ERD check | codex | Line cook | GPT-6.2 Sol, medium | A locked check covers the sign |
| H3 report | codex | Line cook | GPT-6.2 Sol, medium | G5 compares the numbers |
| H4 tests and docs | codex | Prep cook | GPT-6 Luna, low | Low |
| Integration and gates | integration | Sous chef | Opus 5.5, xhigh, new session | Merge errors hide defects |
| Inspection of Claude files | integration | Sous chef (other vendor) | GPT-6.2 Sol, xhigh, new session | A second vendor finds different errors |
| Inspection of Codex files | integration | Sous chef (other vendor) | Opus 5.5, xhigh, new session | Same reason |

Overnight rules:

- Nobody answers questions. On a block, write `BLOCKERS.md` and go to the next ticket that does not depend on it. Never retry at the same tier.
- A cook that fails the same check 2 times moves up 1 tier.
- Claude runs at most 2 subagents at once. Codex runs at most 1.
- If `codex exec` fails with "Access is denied", do the ticket in the main Codex session and log it.
- Compact the context at 40%.

## 12. Gates

| Gate | Check | Fails when |
|---|---|---|
| G0 | Changed files on a branch are inside the file set of that branch | An agent edited a file that it does not own |
| G1 | Shapes, types, registry, and estimator methods follow the contract for each dataset | A signature or shape differs |
| G2 | No subject in both train and test (cross-subject). 1 subject per fold (within-subject). No calibration trial in the test set | Any overlap |
| G3 | On planted-ERD data, models recover the signal. Permuted labels give about 0.50 | A model misses a known signal, or a leak exists |
| G4 | On real data: all 4 models have status `ok`. `csp_lda` within-subject is below 0.95. **Fails when no model is checked** | A leak is suspected, or the check ran on nothing |
| G5 | Every number in `results.md` exists in `results.json` | An invented number |
| G6 | 2 seeded runs on synthetic data give the same `results.json`. Time limits are off | A random source has no seed |
| G7 | `run_all.py` runs clean in a fresh venv | A missing dependency |
| G8 | Cached and uncached predictions match to 1e-9 for `csp_lda` and `fbcsp_lr` | The cache changes results |
| G9 | 1 `csp_lda` fit on (850, 64, 480) takes at most 25% of the v0.2 time | The speedup is missing |
| G10 | Results do not depend on wall-clock time | A time limit decides a result |
| G11 | The responder rule flags a planted-ERD subject. It flags at most 2 of 10 pure-noise subjects | The null is wrong |
| G12 | The LS sign matches the planted ERD on synthetic data | A sign error |
| G13 | Stroke loader: shapes, labels, µV range. Runs only when `BCI_EXPECT_STROKE=1` | A wrong unit or label |
| G14 | `.gitignore` and `LICENSE` exist. No root file name has a space | Repo hygiene |

The G4 rule from v0.2 ("a gate that checks nothing must fail") applies to every gate.

## 13. Failure modes

- **Cache key error.** Two different arrays share a key. G8 catches this.
- **Cache leak.** The cache stores a learned value (such as a CSP filter). It may store only stateless filter output.
- **Responder rule drift.** An agent changes the rule after it sees the data. The rule is in section 4 and in G11.
- **Selection after the fact.** An agent picks channels or windows from test results. Forbidden.
- **Wrong channel index.** C3 and C4 swap. The sign of LS flips. G12 and the evidence in `DECISIONS.md` catch this.
- **Stroke label or unit error.** G13 catches this.
- **Silent synthetic fallback.** The stroke loader never falls back to synthetic data.
- **Invented result.** G5 catches this.
- **Scope drift.** A new model family or a hyperparameter search. The reviewer checks this.

## 14. Diligence

- PhysioNet: cite Schalk et al., 2004 (BCI2000) and Goldberger et al., 2000 (PhysioNet).
- Stroke data: cite Liu et al., Scientific Data, 2024. Check the license first. Do not redistribute raw data.
- The README states: healthy subjects and stroke patients appear in separate results, no clinical claim, not a medical device, AI wrote the code.
- Synthetic output is always labeled. It is never a result.
- No private lab data enters this repo.

## 15. Run order (automatic)

The human starts 2 sessions with 1 prompt each. The agents sync through marker files in `.sync3\`.

| Marker | Written by | Meaning |
|---|---|---|
| `P0_DONE` | Claude | Frozen files are committed on `base/v0.3` |
| `P0_REVIEW_DONE` | Codex | `.sync3\PLAN_REVIEW.md` is written |
| `P0_LOCKED` | Claude | Review holes are fixed. The worktrees exist |
| `CLAUDE_DONE` / `CODEX_DONE` | each lead | Branch tickets are finished |
| `INTEGRATION_DONE` | Claude | `integration/v0.3` is built and gated |
| `INSPECTION_CODEX_DONE` | Codex | `.sync3\INSPECTION_codex.md` is written |

Each wait has a time limit and a fallback.

## 16. Open questions for tomorrow

1. How many responders? Is the count above the chance level of 1?
2. Does LS match the decoder score? If not, which pipeline step do you test first?
3. Did calibration help the non-responders? State the regression-to-the-mean limit.
4. Did the stroke ticket ship? If yes, how do the stroke results differ from the healthy results?
5. Which claim goes on your CV, and which number supports it?
