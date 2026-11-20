"""Gate G14 (FROZEN, v0.3): repo hygiene. .gitignore and LICENSE exist. No tracked root file name has a space."""
from __future__ import annotations

import subprocess

from conftest import REPO

REQUIRED_IGNORES = (".venv/", ".venv_g7/", ".cache/", ".sync*/", "worktrees/", "__pycache__/", "*.pyc")


def test_gitignore():
    p = REPO / ".gitignore"
    assert p.exists(), ".gitignore missing"
    lines = {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()}
    missing = [e for e in REQUIRED_IGNORES if e not in lines]
    assert not missing, f".gitignore lacks {missing}"


def test_license():
    p = REPO / "LICENSE"
    assert p.exists(), "LICENSE missing"
    txt = p.read_text(encoding="utf-8")
    assert "MIT License" in txt and "Dhruv Patil" in txt


def test_no_space_in_root_names():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    files = [f for f in out.split("\n") if f.strip()]
    assert files, "git ls-files returned nothing"
    roots = {f.split("/")[0] for f in files}
    bad = sorted(r for r in roots if " " in r)
    assert not bad, f"root names with a space: {bad}"
    assert (REPO / "docs" / "fable-playbook.md").exists(), "docs/fable-playbook.md missing"
