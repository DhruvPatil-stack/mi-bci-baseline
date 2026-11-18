# Blockers

- `codex exec` cannot start a build or fresh checker session: `Error: failed to initialize in-process app-server client: Access is denied. (os error 5)`. It attempts to use `C:\Users\dhruv\.codex\tmp`, outside the permitted workspace.
- Git cannot add or commit on `codex/advanced-report`: `fatal: Unable to create .../.git/worktrees/codex/index.lock: Permission denied`. Three attempts failed for X1. The integration agent should record and commit these uncommitted files before merging, as already noted in `.sync/LOG.md`.
- Pytest tests using `tmp_path` error, then pytest itself fails at session finish with `PermissionError: [WinError 5] Access is denied` while scanning its `--basetemp` directory, including a new in-worktree path. Direct fixture and behavioral checks passed, but the affected locked pytest tests remain unverified here.
