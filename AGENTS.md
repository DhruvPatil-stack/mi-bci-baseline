# AGENTS.md (FROZEN)

Read first: [PRD_v0.3.md](PRD_v0.3.md) (the v0.3 spec; it wins over [PRD.md](PRD.md)) and [docs/KITCHEN.md](docs/KITCHEN.md) (the kitchen rules and tier table).
Plan: [docs/PLAN.md](docs/PLAN.md). Contracts: `bci/contracts.py` (docstring). Settings: `bci/config.yaml`.

## File ownership rule (gate G0, `tests/locked/test_ownership.py`)
Edit ONLY the files your branch owns. Never edit a FROZEN file or `tests/locked/`.

| Owner | Branch | Files |
|---|---|---|
| Claude | `claude/speed-stroke` | `bci/data.py`, `bci/data_stroke.py`, `bci/cache.py`, `bci/models_classical.py`, `bci/evaluate.py`, `tests/claude/`, `docs/claude/` |
| Codex | `codex/heterogeneity` | `bci/models_advanced.py`, `bci/analysis.py`, `bci/erd_check.py`, `bci/feedback_sim.py`, `bci/report.py`, `tests/codex/`, `docs/codex/` |
| Integration | `integration/v0.3` | `run_all.py`, `README.md`, `results/`, `docs/INTEGRATION.md`, `docs/INSPECTION_*_v0.3.md`, `docs/MORNING_REPORT_v0.3.md`, one lesson in `docs/KITCHEN.md` |
| Head chef (FROZEN) | `base/v0.3` | everything else: `bci/contracts.py`, `bci/channels.py`, `bci/splits.py`, `bci/synthetic.py`, `bci/config.yaml`, `docs/STROKE_DATASET.md`, `.gitignore`, `LICENSE`, `requirements.txt`, `pytest.ini`, `tests/locked/`, `AGENTS.md`, `CLAUDE.md`, `docs/PLAN.md`, `docs/KITCHEN.md`, `.claude/` |

v0.2 branches (`claude/foundation-classical`, `codex/advanced-report`, `integration/v0.2`) keep their v0.2 file sets.

Need a new dependency? Write it in your `BLOCKERS.md`. Do not edit `requirements.txt`.

## Platform
- Windows 11, PowerShell (`;` not `&&`). Shared venv at the repo root: from a worktree use `..\..\.venv\Scripts\python.exe`.
- Worktrees (v0.3): `worktrees\v3-base`, `worktrees\v3-claude`, `worktrees\v3-codex`, `worktrees\v3-integration`. Sync folder `.sync3\` (never `.sync\`). Stay inside the repo folder.
- Run the locked checks: `<venv python> -m pytest tests/locked -q` (add `-m "not slow"` for a fast pass).
- Opt-in checks: `BCI_REAL_DATA=1` (PhysioNet subject check), `BCI_RUN_G7=1` (fresh venv), `BCI_EXPECT_STROKE=1` (G13).
- v0.3 env: `BCI_DATASET` (physionet|stroke), `BCI_ENFORCE_TIME_BUDGET` (0|1), `BCI_FILTER_CACHE` (0 disables), `BCI_FILTER_CACHE_DIR`.
- Keep caches in the repo: MNE data in `$env:BCI_DATA_DIR` (default `<repo>/.cache/mne_data`); call
  `mne.datasets.eegbci.load_data(..., path=<that dir>, update_path=False)`. `tests/locked/conftest.py` sets
  `MPLCONFIGDIR`, `_MNE_FAKE_HOME_DIR`, `TMP`, `TEMP` under `<repo>/.cache/`.

## Rules
No paid API, no API key, CPU only. No hyperparameter search: every setting comes from `bci/config.yaml`.
Write no number you did not measure. Never edit a check to make it pass. Synthetic output is labeled
`SYNTHETIC - NOT VALID`.
