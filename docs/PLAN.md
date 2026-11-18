1. PLAN v0.2 (Head chef). Goal: leak-proof CSP+LDA baseline on PhysioNet MI (subjects 1-20, runs 4/8/12), then 3 more models, paired stats, calibration curve, feedback sim.
2. Bottleneck: evaluation leaks. Defense: frozen `splits.py` + spy-estimator leak tests (G2) + permutation-to-chance (G3).
3. Frozen on main: `bci/contracts.py` (all interfaces + schema validators + G4 rule), `splits.py`, `synthetic.py`, `config.yaml`, `tests/locked/` G0-G7, fixture.
4. Claude branch (worktrees\claude): C1 data.py (Sous chef, Opus) -> C2 models_classical.py (Line cook, Sonnet) -> C3 evaluate.py (Sous chef, Opus) -> C4/C5 tests+docs (Prep cook, Haiku).
5. Codex branch (worktrees\codex): X1 ts_lr + eegnet_lite -> X2 feedback_sim.py -> X3 report.py (compute_stats + write_report) -> X4/X5.
6. Each ticket: build -> NEW sous-chef check on ticket+PRD+diff -> locked checks -> commit. 2 returns max, then one tier up; then BLOCKERS.md.
7. Physical checks: median |X| in 1-100 uV (C1); top CSP filters on ch 0/1 (C2); TS(I, ref=I) = 0 (X1); planted 10 Hz ERD map (G3).
8. Integration (worktrees\integration, integration/v0.2): merge claude then codex, write run_all.py (`--synthetic`, `--out`), run real data, gates G0-G7.
9. G4 warnings go in README; G5 forbids any decimal in results.md not in results.json; G6 compares two seeded synthetic runs.
10. Close: cross-vendor inspections, MORNING_REPORT.md with numbers from results.json only, one KITCHEN lesson. No merge into main.
