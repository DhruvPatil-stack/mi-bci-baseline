# Claude branch progress (`claude/foundation-classical`)

Sources: `git log --oneline main..HEAD`, `docs/claude/DECISIONS.md`, `docs/claude/BLOCKERS.md`, and the
test output recorded below. Synthetic results are labeled SYNTHETIC - NOT VALID.

## C1 `bci/data.py`

- **Status:** committed (`62f9ae3`, "sous-chef check PASS" in the commit message).
- **Files:** `bci/data.py`, decisions in `docs/claude/DECISIONS.md` (section C1).
- **Checks:** the commit message records a sous-chef check PASS. No other check result is recorded in the sources.
- **Measured (DECISIONS, subjects 1-3, runs 4/8/12):** X (135, 64, 480) float32; 45 trials per subject
  (23 left / 22 right each); median |X| = 11.10 uV.

## C2 `bci/models_classical.py`

- **Status:** committed (`c419460`, "sous-chef check PASS" in the commit message).
- **Files:** `bci/models_classical.py`. No DECISIONS section exists for C2.
- **Checks:** the commit message records a sous-chef check PASS. No other check result is recorded in the sources.

## C3 `bci/evaluate.py`

- **Status:** in progress. Not committed on this branch yet. `bci/evaluate.py` is untracked and was being
  edited by another cook when this file was written.
- **Files:** `bci/evaluate.py`, decisions in `docs/claude/DECISIONS.md` (section C3).
- **Checks (BLOCKERS.md):** all C3 locked checks pass (G2 no-leak, `contracts -k evaluate`,
  `synthetic recovery -k evaluate`).
- **Open blocker (BLOCKERS.md):** the calibration block is projected to exceed `time_budget_min` (40 min).
  The projection (about 69 min for csp_lda and about 5.6 h for fbcsp_lr) is not measured. The measured
  end-to-end run was `run_model("csp_lda", make_synthetic(), calibration=True)` on 8 x 40 trials: 808.4 s, status ok.
  Config is frozen, so the Head chef must choose the fix (see BLOCKERS.md "Options").

## C4 `tests/claude/test_claude_units.py`

- **Status:** done. 10 tests, all passing.
- **Files:** `tests/claude/test_claude_units.py`.
- **Coverage (not duplicating `tests/locked/`):**
  - C1: `data_dir()` honours `BCI_DATA_DIR` and defaults to `<repo>/.cache/mne_data`; `epochs_from_raw` raises
    `ValueError` on a 200 Hz raw.
  - C2: `BandPass` is stateless and `fit` returns self; a 2 Hz sine is attenuated well below a 15 Hz sine;
    csp_lda band is 8-30 Hz; fbcsp_lr feature step gives 20 features.
  - C3: unknown model name raises `KeyError` in `within_subject` and `cross_subject`; `within_subject` on
    `make_synthetic(n_subjects=5, trials_per_subject=40, seed=3)` returns per_subject keys "1".."5".
- **Run:** `..\..\.venv\Scripts\python.exe -m pytest tests/claude -q`
- **Result:**
  ```
  ..........                                                               [100%]
  10 passed in 12.45s
  ```

## C5 `docs/claude/PROGRESS.md`

- **Status:** this file. Written from the sources listed above.
