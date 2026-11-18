# PRD v0.2: Motor Imagery BCI, Two-Layer Build

Status: DRAFT v0.2. Replaces PRD v0.1.
Builders: AI agents only. 1 Claude Code agent and 1 Codex agent. Each agent works on its own branch.
Kitchen rules: save the kitchen file as `docs/KITCHEN.md`. This PRD uses its tier table.

---

## 0. How to read this file

- The Claude Code agent reads sections 1 to 7, section 8 (its tickets), and sections 10 to 14.
- The Codex agent reads sections 1 to 7, section 9 (its tickets), and sections 10 to 14.
- The integration session reads all sections.
- An agent must not edit a file that it does not own. Gate G0 checks this.
- An agent must not edit section 7 files. The Head chef freezes them in Phase 0.

---

## 1. Goal

**Layer 1 (solid baseline).** Decode imagined left-fist vs imagined right-fist from EEG with CSP + LDA. Use a leak-proof evaluation.

**Layer 2 (comparison).** Add 3 more models. Compare all 4 with paired statistics. Measure how many calibration trials a new subject needs. Simulate rehab feedback.

Success: `python run_all.py` runs clean in a fresh venv. All locked checks pass. Every reported number comes from `results.json`.

## 2. Non-goals

- No hardware, no robot, no live headset.
- No paid API. No API key. CPU only.
- No hyperparameter search. All settings come from `config.yaml`.
- No clinical claim. No stroke data in this version.

## 3. Research question

Main question: how many calibration trials does a new subject need before a model trained with that subject's data beats a model that never saw that subject?

Second question: which model family is best across subjects: CSP, filter-bank CSP, tangent space, or a small CNN?

The answers are measured, not assumed. State the limit in the report: 20 subjects give low statistical power.

## 4. Theory brief

Motor imagery lowers EEG power in the mu band (8-13 Hz) and beta band (13-30 Hz) over the motor cortex. This drop is event-related desynchronization (ERD).

**CSP** finds spatial filters that separate 2 classes by variance.

w = argmax (wᵀ C₁ w) / (wᵀ C₂ w)

- w = spatial filter vector
- C₁ = mean covariance matrix of class 1 (left)
- C₂ = mean covariance matrix of class 2 (right)

**Filter-bank CSP (FBCSP)** applies CSP in several narrow bands. The best band is different for each subject. The model joins the features from all bands.

**Tangent space (TS)** uses the covariance matrix of each trial. A covariance matrix is symmetric positive definite (SPD). The method maps each SPD matrix to a flat vector space.

sᵢ = upper( logm( C_ref^(-1/2) · Cᵢ · C_ref^(-1/2) ) )

- sᵢ = feature vector of trial i
- Cᵢ = spatial covariance matrix of trial i
- C_ref = reference matrix (the mean covariance of the training set)
- logm = matrix logarithm
- upper = operator that keeps the upper triangle as a vector

**EEGNet-lite** is a small CNN. Its temporal convolution learns a band-pass filter. Its depthwise spatial convolution learns a spatial filter. This is the CSP idea with learned weights.

## 5. Data and units

- Source: PhysioNet EEG Motor Movement/Imagery, loaded with `mne.datasets.eegbci.load_data`. Cache outside the repo.
- Population: healthy subjects. This is NOT a stroke dataset.
- Subjects 1 to 20. Runs 4, 8, 12. Annotation T1 = left fist (label 0). T2 = right fist (label 1). T0 (rest) is dropped.
- Signal: 64 channels, 160 Hz. Reference: common average (set in `config.yaml`).
- Epoch window: 0.5 s to 3.5 s after the cue. The array has **480 samples**. MNE includes the end point. Use `tmax = 3.5 - 1/160`.
- **Unit: µV.** MNE returns volts. Multiply by 1e6. Output type: float32.
- Expect about 45 trials for each subject.
- Fallback: if the download fails 3 times, use `synthetic.py`. Label every output "SYNTHETIC - NOT VALID".

## 6. Repository layout and ownership

```
bci/
  contracts.py          FROZEN  (Head chef)
  splits.py             FROZEN  (Head chef)
  synthetic.py          FROZEN  (Head chef)
  config.yaml           FROZEN  (Head chef)
  data.py               CLAUDE
  models_classical.py   CLAUDE
  evaluate.py           CLAUDE
  models_advanced.py    CODEX
  feedback_sim.py       CODEX
  report.py             CODEX
run_all.py              INTEGRATION
requirements.txt        FROZEN
tests/locked/           FROZEN  (Head chef)
tests/claude/           CLAUDE
tests/codex/            CODEX
docs/KITCHEN.md         FROZEN
docs/claude/            CLAUDE  (PROGRESS.md, DECISIONS.md, BLOCKERS.md)
docs/codex/             CODEX   (PROGRESS.md, DECISIONS.md, BLOCKERS.md)
AGENTS.md               FROZEN  (CLAUDE.md is a link to AGENTS.md)
results/                INTEGRATION
```

Git rules:

1. Phase 0 happens on `main`. The Head chef commits all FROZEN files.
2. Each agent works in its own **git worktree**. The 2 agents never share a working folder.
   - `git worktree add ../bci-claude -b claude/foundation-classical main`
   - `git worktree add ../bci-codex -b codex/advanced-report main`
3. Each agent commits only to its own branch. Commit after each ticket.
4. The integration session merges `claude/foundation-classical` first, then `codex/advanced-report`, into `integration/v0.2`.
5. If an agent needs a new dependency, it writes the need in its `BLOCKERS.md`. It does not edit `requirements.txt`.

## 7. Section Z: frozen files (Phase 0)

The Head chef writes these files before any branch starts.

**`contracts.py`**

- `SEED = 42`, `SFREQ = 160`, `N_CHANNELS = 64`, `N_SAMPLES = 480`, `LABELS = {0: "left", 1: "right"}`.
- Data contract: `X` has shape (n_trials, 64, 480), type float32, unit µV. `y` is int 0 or 1. `groups` is the subject id.
- Estimator contract: each model is a scikit-learn estimator with `fit(X, y)`, `predict(X)`, and `predict_proba(X)`. All scaling happens inside `fit`. A model must never see test data in `fit`.
- Registry contract: a module exposes `REGISTRY: dict[str, Callable[[], estimator]]`. Each callable takes no argument.
- Results schema (see below).

**`splits.py`**

```python
def within_subject_splits(y, groups, n_splits=5, seed=SEED):
    """Yield (subject_id, train_idx, test_idx). Stratified. One subject only."""

def cross_subject_splits(groups, n_splits=5, seed=SEED):
    """Yield (train_idx, test_idx). No subject appears in both sets."""

def calibration_splits(y, groups, k, n_repeats=10, seed=SEED):
    """Yield (target_subject, source_idx, calib_idx, test_idx).
    source_idx = all other subjects. calib_idx = k trials of the target, k/2 per class.
    test_idx = the other trials of the target."""
```

**`synthetic.py`**: `make_synthetic(n_subjects=8, trials_per_subject=40, seed=SEED)` returns `X, y, groups, truth`. It plants a known ERD. Class 0 has 50% less 10 Hz power on channel 0. Class 1 has 50% less 10 Hz power on channel 1. It adds 1/f noise and a gain that differs for each subject.

**`config.yaml`**: subjects, runs, filter band, window, reference, CSP components (6), FBCSP bands (8-12, 12-16, 16-20, 20-24, 24-30 Hz), calibration k values (0, 4, 8, 16, 24), `calibration_models` (csp_lda, fbcsp_lr, ts_lr), EEGNet settings (fixed epochs, learning rate, batch size), time budget for each model (40 min), feedback model (csp_lda).

**`requirements.txt`**: mne, numpy, scipy, scikit-learn, pyriemann, torch (CPU), matplotlib, pandas, pyyaml, pytest.

**Results schema (`results/results.json`)**

```
meta: data_source ("physionet" | "synthetic"), seed, subjects, git_commit, timestamp
models: {name: {
  within_subject: {per_subject: {id: {acc, bal_acc, kappa}}, mean_bal_acc, std_bal_acc},
  cross_subject:  {per_fold: [...], mean_bal_acc, std_bal_acc},
  permutation:    {within_mean_bal_acc, cross_mean_bal_acc},
  calibration:    {k: [...], source_plus_target: [...], target_only: [...]}   # optional
}}
stats: {comparisons: [{model, vs, median_diff, p_raw, p_holm}]}
runtime_s: {name: seconds}
```

**`tests/locked/`** (see section 12): all gate checks, plus `fixtures/results_fixture.json` (a fake results file for `report.py`).

## 8. Section C: Claude Code tickets

Branch: `claude/foundation-classical`. Work only on the Claude-owned files. Use `synthetic.py` until `data.py` is ready.

**C1. `data.py`**
- Goal: `load_dataset(subjects, runs) -> (X, y, groups)` that obeys section 5 and `contracts.py`.
- Done: shape (n, 64, 480), float32, µV, labels 0/1, no rest trials, about 45 trials per subject. A synthetic fallback exists.
- Physical check: the median absolute amplitude is between 1 and 100 µV. A value near 1e-5 means the µV conversion is missing.

**C2. `models_classical.py`**
- Goal: `REGISTRY` with 2 models.
  1. `csp_lda`: CSP (6 components) then LDA. This is the Layer 1 baseline.
  2. `fbcsp_lr`: band-pass in each FBCSP band, CSP (4 components) in each band, join features, standardize, logistic regression.
- Done: both models fit and predict on synthetic data. The `csp_lda` model scores above 0.85 balanced accuracy on synthetic data.
- Physical check: for `csp_lda` on synthetic data, the top CSP filter puts most weight on channels 0 and 1.

**C3. `evaluate.py`**
- Goal: 4 functions. Each takes a model name from the registries and returns a dict that follows the results schema.
  1. `within_subject(name, X, y, groups)` uses `within_subject_splits`.
  2. `cross_subject(name, X, y, groups)` uses `cross_subject_splits`.
  3. `permutation_control(name, X, y, groups)` shuffles `y` inside each training set and each test set, then repeats 1 and 2.
  4. `calibration_curve(name, X, y, groups)` uses `calibration_splits`. It measures 2 curves: model trained on source + k target trials, and model trained on k target trials only.
- The evaluator loads `models_classical.REGISTRY` and `models_advanced.REGISTRY`. If the second module does not exist yet, it loads only the first.
- Metrics: balanced accuracy (main), accuracy, Cohen's kappa.
- Done: gates G1 and G2 pass on synthetic data for both Claude-owned models.

**C4. `tests/claude/`**: tests for C1 to C3 that do not duplicate `tests/locked/`.

**C5. `docs/claude/`**: `PROGRESS.md`, `DECISIONS.md`, `BLOCKERS.md`. Update after each ticket.

## 9. Section X: Codex tickets

Branch: `codex/advanced-report`. Work only on the Codex-owned files. Import only `contracts.py`, `splits.py`, and `synthetic.py`. Do not import `data.py` or `evaluate.py`. They may not exist yet.

**X1. `models_advanced.py`**
- Goal: `REGISTRY` with 2 models.
  1. `ts_lr`: covariance (OAS estimator), tangent space (pyriemann), logistic regression.
  2. `eegnet_lite`: a small PyTorch CNN (temporal convolution, depthwise spatial convolution, separable convolution, adaptive average pooling, linear output). It follows the scikit-learn estimator contract. It standardizes each channel inside `fit` with training statistics only. It uses `SEED`. It uses CPU only. It uses the fixed training settings in `config.yaml`.
- Done: both models fit and predict on synthetic data. `ts_lr` scores above 0.85 balanced accuracy. `eegnet_lite` scores above 0.70. Two fits with the same seed give the same predictions.
- Physical check: for `ts_lr`, the tangent-space vector of an identity covariance matrix with `C_ref = I` is all zeros.

**X2. `feedback_sim.py`**
- Goal: `simulate_feedback(estimator, trial, sfreq, out_png)`. It slides a 1 s window with a 0.25 s step over 1 trial. It converts `predict_proba` into a feedback bar in the terminal and a PNG plot.
- Done: it works with `csp_lda` and `ts_lr` fitted on synthetic data. The PNG exists and has a time axis in seconds.

**X3. `report.py`**
- Goal: read `results/results.json` and write `results/results.md` and figures.
  - Table: all models, within-subject and cross-subject balanced accuracy (mean ± standard deviation).
  - Paired Wilcoxon signed-rank test for each model against `csp_lda` (within-subject, per-subject means). Holm correction. Report the median difference.
  - Figure 1: model comparison. Figure 2: calibration curves. Figure 3: permutation control.
  - A "Limits" paragraph: 20 healthy subjects, about 45 trials each, low power.
  - A `SYNTHETIC - NOT VALID` banner when `meta.data_source` is `synthetic`.
- Done: it runs on `tests/locked/fixtures/results_fixture.json`. Every number in `results.md` exists in the fixture or follows from it by a stated formula.

**X4. `tests/codex/`**: tests for X1 to X3 that do not duplicate `tests/locked/`.

**X5. `docs/codex/`**: `PROGRESS.md`, `DECISIONS.md`, `BLOCKERS.md`. Update after each ticket.

## 10. Section I: integration (Phase 2 and Phase 3)

1. Create `integration/v0.2` from `main`. Merge the 2 branches. There must be no conflict, because the file sets are disjoint.
2. Write `run_all.py`. It runs: load data, run all models, write `results.json`, run `report.py`, run the feedback simulation, and write a short `README.md`.
3. Run all gates (section 12) in a new session.
4. Cross-vendor inspection (new sessions):
   - Codex reviews `data.py`, `models_classical.py`, `evaluate.py`.
   - Claude reviews `models_advanced.py`, `feedback_sim.py`, `report.py`.
   - Each reviewer reads only the PRD, the ticket, and the diff. Each reviewer writes findings to `docs/INSPECTION_<vendor>.md`.
5. Close: update `docs/`. Add one lesson to `docs/KITCHEN.md`.

## 11. Kitchen assignment

Rule 1: choose the cook by the cost of a mistake. Tier names come from `docs/KITCHEN.md`.

| Ticket | Branch | Tier | Model and effort | Cost of a mistake |
|--------|--------|------|------------------|-------------------|
| Phase 0 plan, frozen files, locked checks | main | Head chef | Opus 5.5 + fable-thinking, xhigh | Every later step depends on it |
| Phase 0 plan review | main | Head chef (other vendor) | GPT-6.2 Astra, xhigh | A bad check passes bad code |
| C1 `data.py` | claude | Sous chef | Opus 5.5, xhigh | Wrong labels or wrong unit give plausible wrong results |
| C2 `models_classical.py` | claude | Line cook | Sonnet 5.5 | Fixed recipe. Locked checks catch errors |
| C3 `evaluate.py` | claude | Sous chef | Opus 5.5, xhigh | A leak gives high accuracy that looks good |
| C4, C5 tests and docs | claude | Prep cook | Haiku 5.5 | Low. Locked checks cover the risk |
| X1 `ts_lr` | codex | Line cook | GPT-6.2 Sol, medium | Fixed recipe |
| X1 `eegnet_lite` | codex | Sous chef | GPT-6.2 Sol, xhigh | A wrong training loop still gives plausible numbers |
| X2 `feedback_sim.py` | codex | Line cook | GPT-6.2 Sol, medium | Low. A person can see the plot |
| X3 `report.py` | codex | Line cook | GPT-6.2 Sol, medium | Medium. A locked check compares numbers |
| X4, X5 tests and docs | codex | Prep cook | GPT-6 Luna, low | Low |
| Phase 2 integration and gates | integration | Sous chef | Opus 5.5, xhigh, new session | Merge and gate errors hide defects |
| Phase 3 inspection of Claude files | integration | Sous chef (other vendor) | GPT-6.2 Sol, xhigh, new session | A second vendor finds different errors |
| Phase 3 inspection of Codex files | integration | Sous chef (other vendor) | Opus 5.5, xhigh, new session | Same reason |

Overnight adaptations of the kitchen rules:

- Kitchen rule 9 says "stop and ask the human". Nobody answers at night. Instead: write the problem in `BLOCKERS.md` and go to the next ticket that does not depend on it. Never retry at the same tier.
- A cook that fails the same check 2 times moves up 1 tier. A Sous chef that fails at xhigh writes `BLOCKERS.md` and stops that ticket.
- Parallel limit: the Claude agent runs at most 2 subagents at a time. The Codex agent runs at most 1. The total is 3.
- Compact the context at 40%.

## 12. Locked checks and acceptance gates

The Head chef writes these checks in Phase 0. No cook can edit them.

| Gate | Check | Fails when |
|------|-------|-----------|
| G0 | `test_ownership.py`: all changed files on a branch are inside the file set of that branch | An agent edited a file that it does not own |
| G1 | `test_contracts.py`: shapes, types, registry format, estimator methods | A signature or a shape differs from section 7 |
| G2 | `test_no_leak.py`: cross-subject folds share no subject. Within-subject folds contain 1 subject. Calibration splits never place a calib trial in the test set | Any overlap |
| G3 | `test_synthetic_recovery.py`: on planted-ERD data, `csp_lda` and `ts_lr` reach above 0.85. The label-permuted score is within 0.50 ± 0.05 | A model fails to find a known signal, or a leak exists |
| G4 | `test_real_plausibility.py` (physionet only): `csp_lda` mean within-subject balanced accuracy is in 0.55 to 0.90. Cross-subject is in 0.50 to 0.75. Any value above 0.95 is a **fail** (suspect leak). A value outside the first ranges is a **warning** that goes in the README | Leak suspected |
| G5 | `test_report_numbers.py`: every number in `results.md` exists in `results.json` | An agent invented a number |
| G6 | `test_determinism.py`: 2 runs on synthetic data with seed 42 give the same `results.json` (ignore timestamp) | A random source has no seed |
| G7 | `run_all.py` runs clean in a fresh venv | A missing dependency or path |

NOTE: the G4 ranges are plausibility limits from general experience. They are not published values. Check them against the literature before you quote them.

## 13. Known failure modes

- **Trial-level split.** Epochs of 1 subject appear in train and test. Gate G2 catches it.
- **Fit before split.** A scaler, a CSP, or a reference matrix sees test data. Gate G3 (permutation) catches it.
- **Unit error.** Data in volts instead of µV. The physical check in C1 catches it.
- **Window error.** 481 samples instead of 480. Gate G1 catches it.
- **Label map error.** T1 and T2 swap. Accuracy would be below 50% only if a leak is absent. Gate G3 checks the planted-ERD map.
- **Calibration leak.** A calibration trial appears in the test set. Gate G2 catches it.
- **Unseeded random source.** Gate G6 catches it.
- **Invented result.** An agent writes a number it did not measure. Gate G5 catches it.
- **Scope drift.** An agent adds a hyperparameter search or a larger network. The reviewer checks `config.yaml` use.
- **Compute overrun.** EEGNet takes too long. The time budget in `config.yaml` stops it. The agent writes the stop in `BLOCKERS.md`.

## 14. Diligence

- Data license: PhysioNet data is open. Cite Schalk et al., 2004 (BCI2000) and Goldberger et al., 2000 (PhysioNet).
- No patient data and no private lab data enters the repo.
- The README states: healthy subjects, not a stroke cohort, not a medical device.
- Synthetic output is always labeled. It is never a result.
- AI wrote this code. Say so in the README before any external share.

## 15. Run order

1. **Phase 0** (before you sleep, in the main folder). Run Prompt 0 in Claude Code. Then run Prompt 0R in Codex.
2. **Phase 1** (overnight, 2 terminals). Run Prompt C in the Claude worktree. Run Prompt X in the Codex worktree. They run in parallel.
3. **Phase 2 and 3** (morning). Run Prompt I in a new Claude Code session. Then run the 2 inspection prompts in new sessions.

## 16. Open questions for tomorrow

1. Which stroke EEG dataset replaces PhysioNet?
2. Did the calibration curve show a crossover point? At which k?
3. Did EEGNet-lite beat the classical models? If not, why? (Do not guess. Look at the per-fold results.)
4. Did any model score outside the G4 ranges? Find out why before you trust it.
5. Does the tier table work? Which cook failed its job most often?

---

## Appendix A: prompts

**Prompt 0 (Claude Code, Opus 5.5 xhigh, main folder)**
```
Load the fable-thinking skill. Read PRD.md and docs/KITCHEN.md.
You are the Head chef. Write no feature code.
Do Phase 0: create all files marked FROZEN in PRD section 6 and section 7.
Write the locked checks in tests/locked/ (gates G0 to G7) and the fixture results_fixture.json.
Write AGENTS.md (short: link to PRD.md and docs/KITCHEN.md, name the file ownership rule). Link CLAUDE.md to AGENTS.md.
Run the checks that can run now. Commit to main. Write a 10-line summary of the plan in docs/PLAN.md.
```

**Prompt 0R (Codex, GPT-6.2 Astra xhigh, main folder, new session)**
```
Read PRD.md, docs/PLAN.md, and tests/locked/. You are the other-vendor Head chef.
Review the plan and the locked checks. Do not edit files.
List every case where a wrong model could pass the checks. Write the list to docs/PLAN_REVIEW.md.
```
After this, read `docs/PLAN_REVIEW.md` once. If it lists a serious hole, fix it before Phase 1.

**Prompt C (Claude Code, in the worktree `../bci-claude`)**
```
Read PRD.md sections 1 to 7, section 8, sections 10 to 14, and docs/KITCHEN.md.
You are the Claude branch lead. Work only on the Claude-owned files. Branch: claude/foundation-classical.
Do tickets C1 to C5. Use the tier table in PRD section 11 to pick the subagent model for each ticket.
Run at most 2 subagents at a time. Run the locked checks that apply after each ticket. Commit after each ticket.
Do not edit locked files. Do not stop to ask questions. On a block, write docs/claude/BLOCKERS.md and go on.
When done, write docs/claude/DONE.md with the gate results.
```

**Prompt X (Codex, in the worktree `../bci-codex`)**
```
Read PRD.md sections 1 to 7, section 9, sections 10 to 14, and docs/KITCHEN.md.
You are the Codex branch lead. Work only on the Codex-owned files. Branch: codex/advanced-report.
Do tickets X1 to X5. Use the tier table in PRD section 11 to pick the model and effort for each ticket.
Run at most 1 subagent at a time. Run the locked checks that apply after each ticket. Commit after each ticket.
Do not import data.py or evaluate.py. Do not edit locked files. Do not stop to ask questions.
On a block, write docs/codex/BLOCKERS.md and go on.
When done, write docs/codex/DONE.md with the gate results.
```

**Prompt I (Claude Code, Opus 5.5 xhigh, new session, main folder)**
```
Read PRD.md section 10 and section 12. Do Phase 2: create integration/v0.2, merge the 2 branches, write run_all.py,
run gates G0 to G7, and write any failure with its exact error text to docs/INTEGRATION.md.
Fix only integration files. For a failure inside a branch file, return the ticket to its owner tier with the error text. Return a ticket 2 times at most.
```
