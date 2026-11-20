1. PLAN v0.3 (Head chef, base/v0.3). Goal: fast pipeline, then Q1-Q4 of PRD_v0.3 section 1 answered with measured numbers.
2. Bottleneck: speed (6.267 s per csp_lda fit, mostly mne CSP rank SVD) and gates that pass on nothing. Defense: G8-G10, G4 fix.
3. Frozen on base/v0.3: contracts.py (dataset, time-limit, checkpoint, cache, analysis, ERD, stroke contracts), channels.py, config.yaml, STROKE_DATASET.md, tests/locked G0-G14, .gitignore, LICENSE.
4. Claude (worktrees\v3-claude, claude/speed-stroke): S1 cache.py + BandPass + CSP per-fit cost (Sous chef) -> S2 evaluate checkpoint/time-limit (Sous chef) -> S3 no 64 ch / 160 Hz (Line cook) -> S4 stroke loader (Sous chef, optional).
5. Codex (worktrees\v3-codex, codex/heterogeneity): H1 analysis.py responder rule -> H2 erd_check.py -> H3 report.py -> H4 tests/docs.
6. Each ticket: build -> NEW sous-chef check (ticket + PRD + diff) -> locked checks -> commit. 2 returns max, then one tier up, then BLOCKERS.md.
7. Physical checks: cache = uncached to 1e-9 (S1); planted ERD flagged (H1); LS < 0 on planted ERD and 50 uV^2 for a 10 uV sine (H2); stroke median |X| 1-100 uV (S4).
8. Gates by branch: G8/G9/G10 on claude + integration; G11/G12 on codex + integration; G4/G5-real fail on v0.2 results until S5 (expected).
9. Integration (worktrees\v3-integration, integration/v0.3): merge both, run_all.py runs 4 models complete (S5) + responders + ERD (+ stroke if S4), gates G0-G14.
10. Close: cross-vendor inspections, MORNING_REPORT_v0.3.md (Q1-Q4: number, interval, limit or "not measured"), one KITCHEN lesson. No merge into main.
