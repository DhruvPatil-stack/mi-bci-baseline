# Claude branch DONE (claude/foundation-classical)

Commits: 62f9ae3 C1 data.py, c419460 C2 models_classical.py, dae4685 C3-C5 evaluate.py + tests/claude + docs.
Each ticket: built by its tier cook, then checked by a NEW Opus sous-chef that read only ticket + PRD + diff. All 3 checks: VERDICT PASS, 0 returns.

| Gate | Result on this branch | Source |
|---|---|---|
| G0 ownership | PASS (1 passed, 1 skipped: integration-only test) | lead run after dae4685 |
| G1 contracts | PASS, incl. offline epochs_from_raw check and BCI_REAL_DATA=1 subject check (4 passed) | C1 check |
| G2 no leak | PASS (10 passed: splits, Spy, Oracle) | C3 build and C3-C5 check |
| G3 synthetic recovery | PASS for csp_lda and fbcsp_lr, evaluate permutation and cross recovery | C2 check, C3-C5 check |
| G4 real plausibility | not run (needs results.json; integration) | - |
| G5 report numbers | not run (report.py is Codex-owned) | - |
| G6 determinism | two-fit check PASS for csp_lda, fbcsp_lr; run_all part needs integration | C2 check |
| G7 fresh venv | not run (needs run_all.py; integration) | - |

Full locked run `-m "not slow"` in the C3-C5 check: 36 passed, 19 skipped, 2 deselected. tests/claude: 10 passed.

Open: BLOCKERS.md runtime. Projected (not measured) real calibration time exceeds the 40 min budget; config stays frozen; evaluate keeps a partial calibration block on timeout.
Minor (accepted): tests/claude has no test of the run_model timeout/partial path (C3-C5 check note).
