# AGENTS.md (FROZEN)

Read first: [PRD.md](PRD.md) (the spec) and [docs/KITCHEN.md](docs/KITCHEN.md) (the kitchen rules and tier table).
Plan: [docs/PLAN.md](docs/PLAN.md). Contracts: `bci/contracts.py` (docstring). Settings: `bci/config.yaml`.

## File ownership rule (gate G0, `tests/locked/test_ownership.py`)
Edit ONLY the files your branch owns. Never edit a FROZEN file or `tests/locked/`.

| Owner | Branch | Files |
|---|---|---|
| Claude | `claude/foundation-classical` | `bci/data.py`, `bci/models_classical.py`, `bci/evaluate.py`, `tests/claude/`, `docs/claude/` |
| Codex | `codex/advanced-report` | `bci/models_advanced.py`, `bci/feedback_sim.py`, `bci/report.py`, `tests/codex/`, `docs/codex/` |
| Integration | `integration/v0.2` | `run_all.py`, `README.md`, `results/`, `docs/INTEGRATION.md`, `docs/INSPECTION_*.md`, `docs/MORNING_REPORT.md`, one lesson in `docs/KITCHEN.md` |
| Head chef (FROZEN) | `main` | everything else: `bci/__init__.py`, `bci/contracts.py`, `bci/splits.py`, `bci/synthetic.py`, `bci/config.yaml`, `requirements.txt`, `pytest.ini`, `tests/locked/`, `AGENTS.md`, `CLAUDE.md`, `docs/PLAN.md`, `docs/KITCHEN.md`, `.claude/` |

Need a new dependency? Write it in your `BLOCKERS.md`. Do not edit `requirements.txt`.

## Platform
- Windows 11, PowerShell (`;` not `&&`). Shared venv at the repo root: from a worktree use `..\..\.venv\Scripts\python.exe`.
- Worktrees: `worktrees\claude`, `worktrees\codex`, `worktrees\integration`. Stay inside the repo folder.
- Run the locked checks: `<venv python> -m pytest tests/locked -q` (add `-m "not slow"` for a fast pass).
- Opt-in checks: `BCI_REAL_DATA=1` (PhysioNet subject check), `BCI_RUN_G7=1` (fresh venv).
- Keep caches in the repo: MNE data in `$env:BCI_DATA_DIR` (default `<repo>/.cache/mne_data`); call
  `mne.datasets.eegbci.load_data(..., path=<that dir>, update_path=False)`. `tests/locked/conftest.py` sets
  `MPLCONFIGDIR`, `_MNE_FAKE_HOME_DIR`, `TMP`, `TEMP` under `<repo>/.cache/`.

## Rules
No paid API, no API key, CPU only. No hyperparameter search: every setting comes from `bci/config.yaml`.
Write no number you did not measure. Never edit a check to make it pass. Synthetic output is labeled
`SYNTHETIC - NOT VALID`.
