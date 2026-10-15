import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "skills", "full-code-review", "scripts"))
import discover_guidance as m  # noqa: E402


def test_normalize_scp(tmp_path):
    assert m.normalize_repo_key(
        "git@gitlab.rechargeapps.net:engineering/frontend/frontend.git"
    ) == "engineering--frontend--frontend"


def test_normalize_https(tmp_path):
    assert m.normalize_repo_key(
        "https://gitlab.rechargeapps.net/engineering/frontend/frontend.git"
    ) == "engineering--frontend--frontend"


def test_gather_sources(tmp_path):
    root = Path(tmp_path) / "repo"
    (root / ".claude" / "skills" / "review-x").mkdir(parents=True)
    (root / ".claude" / "skills" / "review-x" / "SKILL.md").write_text("x")
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "rules" / "a.md").write_text("a")
    (root / "CLAUDE.md").write_text("root")
    (root / "AGENTS.md").write_text("agents")
    sub = root / "pkg" / "deep"
    sub.mkdir(parents=True)
    (root / "pkg" / "CLAUDE.md").write_text("pkg")
    (sub / "f.py").write_text("code")

    target = m.gather(str(root), ["pkg/deep/f.py"])
    assert any("review-x" in s for s in target["repo_skills"])
    assert any(p.endswith("/CLAUDE.md") and "/pkg/" not in p for p in target["claude_md"])
    assert any(p.endswith("pkg/CLAUDE.md") for p in target["claude_md"])
    assert any(p.endswith("rules/a.md") for p in target["rules"])
    assert any(p.endswith("AGENTS.md") for p in target["other"])


def test_gather_skill_references(tmp_path):
    root = Path(tmp_path) / "repo"
    refs = root / ".claude" / "skills" / "review-x" / "references"
    (refs / "high-risk-files").mkdir(parents=True)
    (root / ".claude" / "skills" / "review-x" / "SKILL.md").write_text("router only")
    (refs / "index.md").write_text("routing table")
    (refs / "high-risk-files" / "extending.md").write_text("the actual rule")

    target = m.gather(str(root), [])
    assert any(p.endswith("high-risk-files/extending.md") for p in target["repo_skill_references"])
    assert any(p.endswith("references/index.md") for p in target["repo_skill_reference_indexes"])
    assert target["repo_skill_references_dropped"] == 0


def test_gather_skill_references_capped(tmp_path):
    root = Path(tmp_path) / "repo"
    refs = root / ".claude" / "skills" / "review-x" / "references"
    refs.mkdir(parents=True)
    for i in range(5):
        (refs / ("r%02d.md" % i)).write_text("r")

    original = m.REFERENCE_CAP
    m.REFERENCE_CAP = 3
    try:
        target = m.gather(str(root), [])
    finally:
        m.REFERENCE_CAP = original

    assert len(target["repo_skill_references"]) == 3
    assert target["repo_skill_references_dropped"] == 2


def test_gather_absent(tmp_path):
    root = Path(tmp_path) / "repo"
    root.mkdir()
    target = m.gather(str(root), [])
    assert target["repo_skills"] == []
    assert target["repo_skill_references"] == []
    assert target["repo_skill_reference_indexes"] == []
    assert target["repo_skill_references_dropped"] == 0
    assert target["claude_md"] == []
    assert target["rules"] == []
    assert target["other"] == []


if __name__ == "__main__":
    import tempfile
    import traceback
    fails = 0
    for name in sorted(n for n in dict(globals()) if n.startswith("test_")):
        fn = globals()[name]
        if not callable(fn):
            continue
        with tempfile.TemporaryDirectory() as td:
            try:
                fn(Path(td))
                print("PASS", name)
            except Exception:
                fails += 1
                print("FAIL", name)
                traceback.print_exc()
    print("DONE fails=%d" % fails)
    sys.exit(1 if fails else 0)
