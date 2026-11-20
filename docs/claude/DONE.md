# Claude branch DONE (claude/speed-stroke, v0.3)

Tickets: S1 366a14c, S2 7771ad3, S3 f509e3d, S4 602bd2e. Each built by a subagent of the section 11 tier
(S1, S2, S4 Sous chef Opus; S3 Line cook Sonnet) and checked by a NEW sous-chef session: 4 of 4 PASS, 0 returns.

## Gate results on this branch (measured by the checks, after S3 and with S4 present)
`pytest tests/locked -q -m "not slow"`: 1 failed, 81 passed, 17 skipped, 2 deselected (S4 check run, 424.93 s).
- G0 ownership: PASS
- G1 contracts (incl. stroke-shape for csp_lda, fbcsp_lr; sfreq follows dataset): PASS
- G2 no leak: PASS
- G3 synthetic recovery (not slow): PASS
- G4 real plausibility: FAIL, expected: it reads the v0.2 results/results.json (4 models status timeout,
  "G4 checked no model"). Only the S5 full run on integration/v0.3 can change it.
- G5 report numbers: the tests that ran passed (real-results tests read the v0.2 files).
- G6 two seeded run_all runs: not run here (slow; run_all.py belongs to integration).
- G7 fresh venv: not run (opt-in).
- G8 cache = uncached to 1e-9: PASS (7 tests incl. 4 concurrent processes)
- G9 csp_lda fit <= 1.567 s: PASS (S1 builder probe median 1.249 s under partial load; G9 prints only on failure)
- G10 wall clock / checkpoint: PASS (3 tests)
- G11, G12: skipped here (Codex gates)
- G13 stroke loader with BCI_EXPECT_STROKE=1: PASS (2 passed)
- G14 hygiene: PASS
