"""Gate G0 (FROZEN): every file changed on a branch is inside the file set of that branch.

Branch is read from git. Changed files = committed diff against the merge base with the branch's base
(base/v0.3 for the v0.3 branches, main for the v0.2 branches), plus uncommitted and untracked files.
On main and on base/v0.3 the gate is skipped (Head chef). On integration/* the branch-owned files must also be
byte-identical to the tip of their owner branch (integration fixes only integration files).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- v0.2 (kept for the old branches)
CLAUDE_FILES = {"bci/data.py", "bci/models_classical.py", "bci/evaluate.py"}
CLAUDE_DIRS = ("tests/claude/", "docs/claude/")
CODEX_FILES = {"bci/models_advanced.py", "bci/feedback_sim.py", "bci/report.py"}
CODEX_DIRS = ("tests/codex/", "docs/codex/")
INTEGRATION_FILES = {"run_all.py", "README.md", "docs/INTEGRATION.md", "docs/INSPECTION_claude.md",
                     "docs/INSPECTION_codex.md", "docs/MORNING_REPORT.md", "docs/KITCHEN.md"}
INTEGRATION_DIRS = ("results/",)
CLAUDE_BRANCH = "claude/foundation-classical"
CODEX_BRANCH = "codex/advanced-report"

# ---------------------------------------------------------------- v0.3 (PRD_v0.3 section 6)
V3_BASE = "base/v0.3"
V3_CLAUDE_BRANCH = "claude/speed-stroke"
V3_CODEX_BRANCH = "codex/heterogeneity"
V3_INTEGRATION_BRANCH = "integration/v0.3"
V3_CLAUDE_FILES = CLAUDE_FILES | {"bci/data_stroke.py", "bci/cache.py"}
V3_CLAUDE_DIRS = CLAUDE_DIRS
V3_CODEX_FILES = CODEX_FILES | {"bci/analysis.py", "bci/erd_check.py"}
V3_CODEX_DIRS = CODEX_DIRS
V3_INTEGRATION_FILES = {"run_all.py", "README.md", "docs/INTEGRATION.md", "docs/INSPECTION_claude_v0.3.md",
                        "docs/INSPECTION_codex_v0.3.md", "docs/MORNING_REPORT_v0.3.md", "docs/KITCHEN.md"}
V3_INTEGRATION_DIRS = ("results/",)

V3_BRANCHES = {V3_CLAUDE_BRANCH, V3_CODEX_BRANCH, V3_INTEGRATION_BRANCH}


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def _owned(path: str, files, dirs) -> bool:
    return path in files or any(path.startswith(d) for d in dirs)


def _branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").strip()


def _base_of(branch: str) -> str:
    if branch in V3_BRANCHES or branch.endswith("/v0.3"):
        return V3_BASE
    return "main"


def _changed_files(base_ref: str) -> set[str]:
    base = _git("merge-base", "HEAD", base_ref).strip()
    changed = set(_git("diff", "--name-only", base, "HEAD").split("\n"))
    changed |= set(_git("diff", "--name-only", "HEAD").split("\n"))
    changed |= set(_git("ls-files", "--others", "--exclude-standard").split("\n"))
    # __pycache__ and similar are git-excluded; nothing else is ignored.
    return {c.strip().replace("\\", "/") for c in changed if c.strip()}


def _file_sets(branch: str):
    """(allowed predicate) for the branch, or None if the branch is unknown."""
    if branch == V3_CLAUDE_BRANCH:
        return lambda p: _owned(p, V3_CLAUDE_FILES, V3_CLAUDE_DIRS)
    if branch == V3_CODEX_BRANCH:
        return lambda p: _owned(p, V3_CODEX_FILES, V3_CODEX_DIRS)
    if branch == V3_INTEGRATION_BRANCH:
        return lambda p: (_owned(p, V3_CLAUDE_FILES, V3_CLAUDE_DIRS) or _owned(p, V3_CODEX_FILES, V3_CODEX_DIRS)
                          or _owned(p, V3_INTEGRATION_FILES, V3_INTEGRATION_DIRS))
    if branch.startswith("claude/"):
        return lambda p: _owned(p, CLAUDE_FILES, CLAUDE_DIRS)
    if branch.startswith("codex/"):
        return lambda p: _owned(p, CODEX_FILES, CODEX_DIRS)
    if branch.startswith("integration/"):
        return lambda p: (_owned(p, CLAUDE_FILES, CLAUDE_DIRS) or _owned(p, CODEX_FILES, CODEX_DIRS)
                          or _owned(p, INTEGRATION_FILES, INTEGRATION_DIRS))
    return None


def test_branch_edits_only_owned_files():
    branch = _branch()
    if branch in ("main", V3_BASE):
        pytest.skip(f"G0 does not apply on {branch} (Phase 0 owner is the Head chef)")
    allowed = _file_sets(branch)
    if allowed is None:
        pytest.fail(f"unknown branch {branch!r}: no file set defined")
    changed = _changed_files(_base_of(branch))
    bad = sorted(p for p in changed if not allowed(p))
    assert not bad, f"branch {branch} changed files it does not own: {bad}"


def test_v3_file_sets_are_disjoint():
    """No file is owned by both the Claude and the Codex v0.3 branch; frozen files belong to nobody."""
    assert not (V3_CLAUDE_FILES & V3_CODEX_FILES)
    frozen = {"bci/contracts.py", "bci/splits.py", "bci/synthetic.py", "bci/config.yaml", "bci/channels.py",
              "docs/STROKE_DATASET.md", ".gitignore", "LICENSE", "requirements.txt", "pytest.ini"}
    for p in frozen:
        for files, dirs in ((V3_CLAUDE_FILES, V3_CLAUDE_DIRS), (V3_CODEX_FILES, V3_CODEX_DIRS),
                            (V3_INTEGRATION_FILES, V3_INTEGRATION_DIRS)):
            assert not _owned(p, files, dirs), f"frozen file {p} is in a branch file set"
    assert not any(_owned("tests/locked/x.py", f, d) for f, d in ((V3_CLAUDE_FILES, V3_CLAUDE_DIRS),
                                                                 (V3_CODEX_FILES, V3_CODEX_DIRS),
                                                                 (V3_INTEGRATION_FILES, V3_INTEGRATION_DIRS)))


def _branch_exists(name: str) -> bool:
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", name], cwd=REPO, capture_output=True)
    return r.returncode == 0


def test_integration_did_not_edit_branch_files():
    branch = _branch()
    if not branch.startswith("integration/"):
        pytest.skip("only on integration/*")
    if branch == V3_INTEGRATION_BRANCH:
        owners = ((V3_CLAUDE_BRANCH, V3_CLAUDE_FILES, V3_CLAUDE_DIRS),
                  (V3_CODEX_BRANCH, V3_CODEX_FILES, V3_CODEX_DIRS))
    else:
        owners = ((CLAUDE_BRANCH, CLAUDE_FILES, CLAUDE_DIRS), (CODEX_BRANCH, CODEX_FILES, CODEX_DIRS))
    checked = 0
    for owner, files, dirs in owners:
        if not _branch_exists(owner):
            continue
        checked += 1
        owner_files = set(_git("ls-tree", "-r", "--name-only", owner).split("\n"))
        head_files = set(_git("ls-tree", "-r", "--name-only", "HEAD").split("\n"))
        for p in sorted((owner_files | head_files) - {""}):
            if not _owned(p, files, dirs):
                continue
            a = subprocess.run(["git", "rev-parse", f"{owner}:{p}"], cwd=REPO, capture_output=True, text=True)
            b = subprocess.run(["git", "rev-parse", f"HEAD:{p}"], cwd=REPO, capture_output=True, text=True)
            assert a.stdout.strip() == b.stdout.strip(), (
                f"{p} on integration differs from {owner}: return the fix to the owner branch")
        # uncommitted edits to branch files on integration are also forbidden
        dirty = set(_git("diff", "--name-only", "HEAD").split("\n"))
        assert not [p for p in dirty if p and _owned(p, files, dirs)], f"uncommitted edits to {owner} files"
    assert checked > 0, "no owner branch exists: the integration check checked nothing"
