# Codex progress

- H1: implemented responder permutation p-values, strict responder classification with exact Clopper-Pearson intervals, and seeded paired calibration-group bootstrap analysis. Focused G11 checks passed for planted response, ties, repeatability, classification, and calibration grouping; the ten-noise-subject locked case was not completed in the 30-second command window.
- H2: implemented Welch mu-band power, PRD lateralization score, and overlap-only Spearman association. Locked G12 plus Codex H2 checks: 8 passed, 1 skipped.
- H3: report renders optional measured responder, calibration-group, and ERD blocks from results.json, including the regression-to-the-mean limit. Direct locked-G5 matcher check on the fixture found no unmatched decimals and rendered all three figures; pytest fixture setup remains blocked by its temporary-directory permission error.
- H4: added focused analysis and ERD validation tests; `tests/codex/test_analysis.py tests/codex/test_erd_check.py`: 4 passed in 1.68 s.
- X1: OAS/tangent-space logistic regression and EEGNet-lite implemented. Targeted registry, method, determinism, identity, and synthetic recovery checks passed after fixes.
- X2: feedback simulation implemented; direct synthetic `ts_lr` run produced nine windows and a PNG. A separate direction/time check passed.
- X3: report and figures implemented; locked fixture rendered, number matcher returned no unmatched decimals, and direct statistics check passed.
- X4: added paired-statistics and feedback-direction tests; both passed when run directly. Pytest `tmp_path` execution is blocked by the sandbox (see BLOCKERS.md).
- X5: docs written. Git add/commit blocked by sandbox; files remain in worktrees/codex.
