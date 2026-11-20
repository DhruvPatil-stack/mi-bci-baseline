# Codex v0.3 done record

- H1 responder analysis: focused locked checks passed for planted response, ties, seeding, responder classification, and calibration grouping. The ten-noise-subject locked case was not completed within the 30-second command window.
- H2 ERD check: locked G12 plus Codex tests passed: 8 passed, 1 skipped.
- H3 report: direct G5 fixture render and decimal matcher passed (`unmatched=[]`); pytest fixture setup is blocked by `PermissionError` on `.cache\\pytest_tmp`.
- H4 tests: 4 passed in 1.68 s.
- `codex exec` is blocked by `Access is denied`; every Git commit attempt is blocked by `.git/worktrees/v3-codex/index.lock: Permission denied`. Claude must commit the dirty worktree before merge.
