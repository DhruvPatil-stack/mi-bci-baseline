# Integration v0.2 (integration/v0.2)

Merges: claude/foundation-classical (21ab4f5) first, then codex/advanced-report (b0451ea). No conflict.
Not merged into main.

## Gates

| Gate | Result | Evidence |
|---|---|---|
| G0 ownership | PASS | `test_ownership.py` 2 passed on integration (incl. branch files identical to owner tips) |
| G1 contracts | PASS | fast suite: 65 passed, 6 skipped, 2 deselected (tests/locked + tests/claude + tests/codex), 1710.54 s |
| G2 no leak | PASS | same fast suite (Spy + Oracle on evaluate.py) |
| G3 synthetic recovery | PASS | fast suite + slow `test_eegnet_recovers` passed |
| G4 real plausibility | PASS, VACUOUS | 0 fails; every model has status timeout, so `g4_check` checked no value (4 warnings "status timeout, not checked") |
| G5 report numbers | PASS, WEAK | results.md shows "timeout" for every model and holds no decimals, so the number check had nothing to match |
| G6 determinism | PASS | `test_run_all_twice_same_results` passed (2 passed, 5026.40 s with G3-eegnet); fbcsp_lr timed out at the same k in both runs |
| G7 fresh venv | PASS (synthetic) | `test_fresh_venv.py` 1 passed in 2838.78 s: fresh .venv_g7, pip install -r requirements.txt, `run_all.py --synthetic` exit 0, valid results.json. Real-data path ran clean in the shared venv (exit 0) |

## Failures and events (exact text)

1. Codex could not commit: `fatal: Unable to create .git/worktrees/codex/index.lock: Permission denied`
   (.sync/CODEX_COMMIT_BLOCKED). Per the user's instruction the lead committed the untracked Codex files on
   codex/advanced-report as b0451ea "codex work" before the merge.
2. Real run (PhysioNet, 20 subjects, 900 trials): every model hit the frozen 40 min budget.
   - csp_lda: `time budget of 40 min exceeded during calibration` (calibration k done: [0])
   - fbcsp_lr: `time budget of 40 min exceeded during permutation`
   - ts_lr: `time budget of 40 min exceeded during calibration` (calibration k done: [0])
   - eegnet_lite: `time budget of 40 min exceeded during cross_subject`
   Cause: config time_budget_min (40) vs calibration fit count (820 full-source fits per model). Config is
   FROZEN, so no change. The research question (calibration crossover k) is NOT answered by this run.
3. report.py (Codex-owned) hides finished blocks of models with status timeout; stats.comparisons is empty
   because compute_stats skips non-ok models. Inspection finding HIGH-1 in docs/INSPECTION_claude.md.
   RETURNED to the Codex Line cook tier (ticket X3). The Codex session has ended, so it is open.
   Integration mitigation: README.md lists the finished blocks straight from results.json.
4. G4 rule (frozen `g4_check`) skips non-ok models, so a full timeout makes G4 vacuous. Not edited.

## Integration files
run_all.py (one worker process per model, 2 BLAS threads each), README.md, results/, this file.
