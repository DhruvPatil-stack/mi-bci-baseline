# Codex progress

- X1: OAS/tangent-space logistic regression and EEGNet-lite implemented. Targeted registry, method, determinism, identity, and synthetic recovery checks passed after fixes.
- X2: feedback simulation implemented; direct synthetic `ts_lr` run produced nine windows and a PNG. A separate direction/time check passed.
- X3: report and figures implemented; locked fixture rendered, number matcher returned no unmatched decimals, and direct statistics check passed.
- X4: added paired-statistics and feedback-direction tests; both passed when run directly. Pytest `tmp_path` execution is blocked by the sandbox (see BLOCKERS.md).
- X5: docs written. Git add/commit blocked by sandbox; files remain in worktrees/codex.
