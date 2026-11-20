# Blockers

- `eegnet_lite` cannot finish within the fixed 40 min budget at the configured settings; the real run timed out during `cross_subject`.

- `codex exec` cannot start a build or fresh checker session: `Error: failed to initialize in-process app-server client: Access is denied. (os error 5)`. It attempts to use `C:\Users\dhruv\.codex\tmp`, outside the permitted workspace.
- Git cannot add or commit on `codex/advanced-report`: `fatal: Unable to create .../.git/worktrees/codex/index.lock: Permission denied`. Three attempts failed for X1. The integration agent should record and commit these uncommitted files before merging, as already noted in `.sync/LOG.md`.
- Pytest tests using `tmp_path` error, then pytest itself fails at session finish with `PermissionError: [WinError 5] Access is denied` while scanning its `--basetemp` directory, including a new in-worktree path. Direct fixture and behavioral checks passed, but the affected locked pytest tests remain unverified here.

- H3 locked G5 fixture tests cannot create their `tmp_path`: `PermissionError: [WinError 5] Access is denied: '...worktrees\\v3-codex\\.cache\\pytest_tmp'`. Directly rendering the locked fixture and applying its decimal matcher returned `unmatched=[]`; all three figures existed.
