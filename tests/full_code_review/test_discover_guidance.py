import json
from pathlib import Path

import discover_guidance as m


def test_normalize_scp(tmp_path):
    assert m.normalize_repo_key(
        "git@git.example.com:engineering/frontend/frontend.git"
    ) == "engineering--frontend--frontend"


def test_normalize_https(tmp_path):
    assert m.normalize_repo_key(
        "https://git.example.com/engineering/frontend/frontend.git"
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


def test_gather_skill_references_capped(tmp_path, monkeypatch):
    root = Path(tmp_path) / "repo"
    refs = root / ".claude" / "skills" / "review-x" / "references"
    refs.mkdir(parents=True)
    for i in range(5):
        (refs / ("r%02d.md" % i)).write_text("r")

    monkeypatch.setattr(m, "REFERENCE_CAP", 3)
    target = m.gather(str(root), [])

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


def _guidance_repo(tmp_path):
    root = Path(tmp_path) / "repo"
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "rules" / "a.md").write_text("a")
    (root / "CLAUDE.md").write_text("root")
    (root / "AGENTS.md").write_text("agents")
    (root / "pkg").mkdir()
    (root / "pkg" / "CLAUDE.md").write_text("pkg")
    (root / "pkg" / "f.py").write_text("code")
    return root


def test_gather_drops_symlinks_that_resolve_outside_the_root(tmp_path):
    root = _guidance_repo(tmp_path)
    secret = Path(tmp_path) / "secret.md"
    secret.write_text("token")
    (root / "AGENTS.md").unlink()
    (root / "AGENTS.md").symlink_to(secret)
    (root / "pkg" / "CLAUDE.md").unlink()
    (root / "pkg" / "CLAUDE.md").symlink_to(secret)
    (root / ".claude" / "rules" / "x.md").symlink_to(secret)

    target = m.gather(str(root), ["pkg/f.py"])

    assert target["other"] == []
    assert [Path(p).relative_to(root.resolve()).as_posix() for p in target["claude_md"]] == ["CLAUDE.md"]
    assert [Path(p).name for p in target["rules"]] == ["a.md"]


def test_gather_keeps_symlinks_that_stay_inside_the_root(tmp_path):
    root = _guidance_repo(tmp_path)
    (root / "CONVENTIONS.md").symlink_to(root / "AGENTS.md")
    target = m.gather(str(root), [])
    assert sorted(Path(p).name for p in target["other"]) == ["AGENTS.md", "CONVENTIONS.md"]


def test_exclude_changed_withholds_guidance_the_change_touches(tmp_path):
    root = _guidance_repo(tmp_path)
    target = m.gather(str(root), ["pkg/f.py", "pkg/CLAUDE.md", ".claude/rules/a.md"], exclude_changed=True)

    assert target["changed_guidance"] == [".claude/rules/a.md", "pkg/CLAUDE.md"]
    assert [Path(p).relative_to(root.resolve()).as_posix() for p in target["claude_md"]] == ["CLAUDE.md"]
    assert target["rules"] == []
    assert [Path(p).name for p in target["other"]] == ["AGENTS.md"]


def test_changed_guidance_is_kept_unless_exclude_changed_is_set(tmp_path):
    root = _guidance_repo(tmp_path)
    target = m.gather(str(root), ["pkg/CLAUDE.md"])
    assert target["changed_guidance"] == []
    assert any(p.endswith("pkg/CLAUDE.md") for p in target["claude_md"])


def test_exclude_changed_flag_reads_the_changed_files_list(tmp_path, capsys):
    root = _guidance_repo(tmp_path)
    changed = Path(tmp_path) / "changed.txt"
    changed.write_text("AGENTS.md\npkg/f.py\n")
    assert m.main(["--git-root", str(root), "--changed-files", str(changed), "--exclude-changed"]) == 0
    target = json.loads(capsys.readouterr().out)["target_repo"]
    assert target["changed_guidance"] == ["AGENTS.md"]
    assert target["other"] == []
