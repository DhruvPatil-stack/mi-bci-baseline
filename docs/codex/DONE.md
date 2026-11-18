# Codex gate results

- G0: branch ownership inspection found only Codex-owned source, test, and doc files; Git gate not completed because worktree commit is blocked.
- G1: targeted registry/method tests passed; feedback signature and report signature verified by inspection. `tmp_path` feedback gate could not run.
- G2: frozen split checks were not rerun; Codex code does not implement evaluation splits.
- G3: `ts_lr` planted ERD recovery and EEGNet-lite pooled synthetic recovery passed. TS identity and deterministic fit tests passed. Full permutation suite was interrupted after taking longer than expected; no pass claimed.
- G4: real-data results not available on this branch; skipped.
- G5: fixture report rendered; every decimal matched the fixture. Locked pytest test with `tmp_path` could not finish because of sandbox directory access.
- G6: targeted two-fit determinism checks passed. `run_all.py` is integration-owned and absent.
- G7: integration-owned `run_all.py` absent; fresh-venv gate not run.

Codex source is uncommitted due to `.git/worktrees/codex/index.lock` permission denial. See BLOCKERS.md and `.sync/CODEX_COMMIT_BLOCKED`.
