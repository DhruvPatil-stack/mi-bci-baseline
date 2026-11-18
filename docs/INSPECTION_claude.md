# INSPECTION_claude: cross-vendor review of the Codex files (bci/models_advanced.py, bci/feedback_sim.py, bci/report.py, tests/codex, docs/codex) by Claude Opus 5.5, new session, 2026-11-18, branch integration/v0.2 (these files are identical to codex/advanced-report)

Scope: PRD.md, tickets X1-X5, `git diff main...codex/advanced-report` for the Codex files, bci/contracts.py, bci/config.yaml. I ran no pytest suites. Probes: `.cache/inspect_probe.py` and `.cache/inspect_probe2.py`, run on `make_synthetic(n_subjects=5, trials_per_subject=40)` and on hand-built results dicts.

Checks that found no defect:
- Leaks. `ts_lr` fits the TangentSpace reference inside the pipeline on training covariances only. The EEGNet `mean_` equals the float64 mean of the training data (max abs diff 1.66e-16). Neither `fit` reads test data. The model has no early stopping, and `epochs` comes from config.
- The TS identity check passes: `tangent_space(I, ref=I)` gives a max abs of 0.0.
- Determinism: two EEGNet fits give `np.array_equal(proba_a, proba_b) == True`. The code seeds the torch RNG and the DataLoader generator, and sets threads from config.
- Wilcoxon pairing: the p from `compute_stats` (7.74421643104407e-06) is the same as `scipy.stats.wilcoxon(model, base)` (7.74421643104407e-06). `median_diff` is model minus csp_lda (+0.1000 in the probe). The Holm step-down with the running max is correct.
- Feedback: the window is 160 samples (1 s) and the step is 40 samples (0.25 s). The times are window ends in seconds, `[1.0, 1.25, ..., 3.0]`. P(right) comes from column 1 and points the right way: for ts_lr on a held-out subject, a class-1 trial has mean P(right) 0.899 and a class-0 trial has 0.416.
- `results.md` shows the SYNTHETIC banner when `meta.data_source == "synthetic"`.
- EEGNet pooled recovery: on held-out trials of seen subjects the probe scored bal_acc 0.949, which is above the 0.70 target.

## Findings

1. **HIGH**: `bci/report.py:104-106`, `:17`, `:22`, `:43`. A model with status `timeout` or `error` disappears from every part of the report, even when its results block still holds finished `within_subject` / `cross_subject` data.
   - What is wrong:
     - The table prints the status string in place of the numbers.
     - `compute_stats` skips the model. When the baseline `csp_lda` is not `ok`, `compute_stats` returns `comparisons: []`, and the report gives no reason.
     - `_figures` drops the model, so the figures can be empty axes.
     - The Holm family size shrinks without any note.
   - Consequence: on the real run, where every model timed out, `results.md` holds no measured number. The measured per-subject and per-fold data stays hidden in `results.json`.
   - Evidence: probe with csp_lda and ts_lr both `status: "timeout"`, each with 20 per-subject values and a cross block. Output:
     ```
     | csp_lda | timeout | timeout |
     | ts_lr | timeout | timeout |
     | eegnet_lite | timeout | timeout |
     ...
     | Model | Median difference | Raw p | Holm p |
     |---|---:|---:|---:|
     ```
     The comparisons table is empty and `stats written back: {'comparisons': []}`. `fig1_models.png` is an empty axis with only a legend.
   - Fix:
     - When a sub-block is present, report it with a "partial (timeout)" marker and its subject or fold count.
     - Run the comparison on the subjects both models actually finished, labeled partial, or print one sentence that says why there is no comparison.
     - Name the Holm family (m) in the text.
     - Owner: Codex Line cook (X3).

2. **MEDIUM**: `bci/report.py:115-116`. Small p-values print as zero.
   - What is wrong: the format `{p_raw:.4f}` and `{p_holm:.4f}` turns a real p-value into `0.0000`. With 20 subjects, an exact Wilcoxon p can go as low as about 2e-6, so this case is realistic.
   - Second effect: the token `0.0000` does not appear in results.json, so it can also trip G5 unless the matcher rounds.
   - Evidence: the stats hold `p_raw: 7.74421643104407e-06`, and the markdown row is `| ts_lr | 0.1000 | 0.0000 | 0.0000 |`.
   - Fix: format p with `.3g` (or show `< 0.0001` and keep the exact value in results.json). Owner: Codex Line cook (X3).

3. **MEDIUM**: `bci/report.py:52-84` (all three figures) and `bci/feedback_sim.py:31-41` (feedback PNG). The figures carry no SYNTHETIC label.
   - What is wrong: PRD section 5 says "Label every output 'SYNTHETIC - NOT VALID'", and section 14 says synthetic output is always labeled. Only `results.md` carries the banner.
   - Evidence: the fig1, fig2 and fig3 titles are fixed strings ("Model comparison", ...). `simulate_feedback` has no data-source input and writes no label.
   - Fix:
     - In `_figures`, add `fig.suptitle(SYNTHETIC_LABEL)` when `meta.data_source == "synthetic"`.
     - Give `simulate_feedback` an optional keyword `label=None` that is drawn on the plot. The 4 positional arguments of the contract stay as they are.
     - Owner: Codex Line cook (X2, X3).

4. **MEDIUM**: `bci/report.py:120`. The text holds two hard-coded numbers that do not come from results.json: "20 healthy subjects with about 45 trials each".
   - What is wrong: X3 "Done" requires every number in results.md to exist in the input or follow from it by a stated formula. G5 only checks decimals, so these integers slip past it.
   - The text is printed even on a synthetic run, where the subject count is 8 (or 5), and on a partial run.
   - Fix:
     - Take the subject count from `len(results["meta"]["subjects"])`.
     - Mark "about 45 trials" as the PRD section 5 expectation, not a measured value, or drop it.
     - On synthetic data, say that the cohort numbers do not apply.
     - Owner: Codex Line cook (X3).

5. **MEDIUM**: `bci/models_advanced.py:59-83`. With the fixed config settings, `eegnet_lite` cannot finish within `time_budget_min: 40`, and docs/codex does not record this.
   - Evidence: one fit on 120 trials (30 epochs, 2 threads) took **57.4 s**. That is about 0.016 s per trial-epoch.
   - Rough projection for 20 subjects with about 45 trials each: within-subject is 100 fits of about 36 trials (about 29 min), and cross-subject is 5 fits of about 720 trials (about 29 min). One permutation repeat doubles this, so the total is about 2 h, against a budget of 40 min.
   - Side effect: `padding="same"` with the even `kernel_length` 64 (line 36) raises a torch warning that it makes a zero-padded copy of the input on every forward pass.
   - This is a compute limit, not a correctness bug. PRD section 13 asks the agent to record the overrun in BLOCKERS.md, and that did not happen.
   - Fix: write the measured cost per fit and the projection to `docs/codex/BLOCKERS.md`. Any change to the epochs, the threads or the budget needs a Head chef config decision, not a code edit. Owner: Codex Sous chef (X1 eegnet), escalation to the Head chef for config.

6. **LOW**: `bci/models_advanced.py:41, 43, 47`. The EEGNet layers use hard-coded settings that config.yaml does not hold: the separable kernel `(1, 16)` and the pool sizes `(1, 4)` and `(1, 8)`.
   - These are the standard EEGNet values and do not make the network larger. The rule "all settings come from config.yaml" is only bent, not broken.
   - The code also adds no max-norm constraint. That is acceptable, but DECISIONS.md does not record it.
   - Fix: name the fixed constants in DECISIONS.md, or ask the Head chef to add them to config. Owner: Codex Sous chef (X1).

7. **LOW**: `bci/models_advanced.py:65-67`. `fit` changes torch settings for the whole process and never restores them: `torch.set_num_threads(...)` and `torch.use_deterministic_algorithms(True)`.
   - Evidence: after a fit, `torch.get_num_threads() == 2` and `are_deterministic_algorithms_enabled() == True`.
   - Any other torch code in the same process (run_all) inherits these settings and can raise on a non-deterministic op.
   - Fix: save and restore both settings in a try/finally, or document them. Owner: Codex Sous chef (X1).

8. **LOW**: `bci/feedback_sim.py:22-25, 37`. Two points about the time axis.
   - The axis starts at the epoch start, which is 0.5 s after the cue, not at the cue. The label "Time after epoch start (s)" is accurate, but nothing says that t = 0 means cue + 0.5 s.
   - The estimator learns from 3 s epochs (480 samples) and is then applied to 1 s windows (160 samples). Covariance and log-variance estimates from 160 samples are noisier, so the probabilities are not calibrated the same way. Nothing documents this.
   - Fix: add "(cue + 0.5 s)" to the axis label and add a sentence to DECISIONS.md. Owner: Codex Line cook (X2).

9. **LOW**: `bci/feedback_sim.py:26`. The code takes column 1 as P(right) without checking `estimator.classes_`.
   - The contract guarantees this column order, and the probe confirms the direction is right. A cheap assert would protect against an estimator fitted on remapped labels.
   - Fix: `assert list(getattr(estimator, "classes_", [0, 1])) == [0, 1]`. Owner: Codex Line cook (X2).

10. **LOW**: `bci/report.py:94-97`. `write_report` calls `compute_stats` and writes the stats back into `results.json` *before* `validate_results`.
    - With a malformed input (an `ok` model that lacks `within_subject`), the report crashes with a raw KeyError instead of a schema error. In other cases it can change the results file before validation fails.
    - Fix: validate every part except `stats` first, or validate after computing but before the write. Owner: Codex Line cook (X3).

Count: 1 HIGH, 4 MEDIUM, 5 LOW.

Verdict: models_advanced.py and feedback_sim.py are leak-free, deterministic and point the class direction the right way (minor fixes only), but report.py goes back to the Codex Line cook (X3) for finding 1 (it hides measured data from timed-out models) and findings 2 to 4, and Codex must log the EEGNet budget overrun (finding 5) before the results can be called complete.
