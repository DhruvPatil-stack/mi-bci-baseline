# Morning report v0.2 (integration/v0.2, not merged into main)
**What ran:** Phase 0 + Codex plan review (20 items; 11 closed in the locked checks, rest logged as accepted risk). Claude C1-C5: each checked by a new Opus sous-chef, all PASS, 0 returns. Codex X1-X5: built but its sandbox could not commit; lead committed as b0451ea (your instruction). Merge clean. `run_all.py` on PhysioNet: 20 subjects, 900 trials, commit 4b790eb.
**Measured (results/results.json, balanced accuracy, all 4 models status `timeout` at the 40 min budget):**
| Model | Within mean (std) | Cross mean (std) | Perm within / cross | Calib k=0 (source only) |
|---|---|---|---|---|
| csp_lda | 0.5479 (0.1653) | 0.5588 (0.0346) | 0.4902 / 0.5047 | 0.5639 |
| fbcsp_lr | 0.5645 (0.1285) | 0.5597 (0.0477) | not finished | not finished |
| ts_lr | 0.5513 (0.1396) | 0.5534 (0.0471) | 0.4972 / 0.5030 | 0.5557 |
| eegnet_lite | 0.5435 (0.0826) | not finished | not finished | not finished |
Runtime_s: 2405.9, 2415.0, 2413.8, 2422.7. No paired stats (compute_stats skips non-ok models). **The main question (calibration crossover k) is NOT answered:** only k=0 finished.
**Gates:** G0 PASS, G1 PASS, G2 PASS, G3 PASS, G4 PASS but vacuous (no ok model was checked), G5 PASS but weak (results.md has no decimals), G6 PASS (fbcsp_lr timed out at the same k in both synthetic runs), G7 PASS (fresh venv, synthetic). Details: docs/INTEGRATION.md.
**Blockers:**
- Frozen budget too small: 40 min per model vs 820 full-source calibration fits. Fix in v0.3: raise `time_budget_min` or lower `calibration_repeats` (Head-chef decision on main).
- report.py hides finished blocks of timed-out models (INSPECTION_claude HIGH-1). Returned to the Codex X3 Line cook, still open. README lists the blocks as a workaround.
- Codex sandbox: no git commit, no `codex exec`, no pytest tmp_path (docs/codex/BLOCKERS.md).
**G4 warnings:** 4x "status timeout, not checked". If the rule were applied to the partial blocks, csp_lda within 0.5479 would sit below the 0.55 lower limit. That is a warning, not a fail.
**Inspections:** Claude on Codex files: 1 HIGH, 4 MEDIUM, 5 LOW. Codex on Claude files: 1 High (calibration budget), 2 Medium, 1 Low; no leak found.
**Lessons:**
1. Size the compute budget against the fit count before freezing config: 820 fits x seconds per fit was knowable in Phase 0.
2. A gate that skips non-ok results passes vacuously; gates must fail or warn loudly when they check nothing.
3. Probe the synthetic data against a reference model before locking thresholds (within-subject CSP recovery proved impossible at 64 ch / 32 trials).
4. Test YAML types: `1.0e6` loads as a string; only an end-to-end offline data test caught it.
5. Check the other agent's sandbox permissions (git index.lock, temp dirs) in Phase 0, not at the end.
