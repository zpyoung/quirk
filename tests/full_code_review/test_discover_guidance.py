import json
from pathlib import Path

import discover_guidance as m


def _rel(root, paths):
    return [Path(p).relative_to(root.resolve()).as_posix() for p in paths]


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
    assert _rel(root, target["repo_skills"]) == [".claude/skills/review-x/SKILL.md"]
    assert _rel(root, target["claude_md"]) == ["CLAUDE.md", "pkg/CLAUDE.md"]
    assert _rel(root, target["rules"]) == [".claude/rules/a.md"]
    assert _rel(root, target["other"]) == ["AGENTS.md"]


def test_gather_skill_references(tmp_path):
    root = Path(tmp_path) / "repo"
    refs = root / ".claude" / "skills" / "review-x" / "references"
    (refs / "high-risk-files").mkdir(parents=True)
    (root / ".claude" / "skills" / "review-x" / "SKILL.md").write_text("router only")
    (refs / "index.md").write_text("routing table")
    (refs / "high-risk-files" / "extending.md").write_text("the actual rule")

    target = m.gather(str(root), [])
    base = ".claude/skills/review-x/references/"
    assert _rel(root, target["repo_skill_references"]) == [base + "high-risk-files/extending.md", base + "index.md"]
    assert _rel(root, target["repo_skill_reference_indexes"]) == [base + "index.md"]
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


def test_exclude_changed_fails_when_the_changed_files_list_is_unreadable(tmp_path, capsys):
    root = _guidance_repo(tmp_path)
    missing = Path(tmp_path) / "nope.txt"
    assert m.main(["--git-root", str(root), "--changed-files", str(missing), "--exclude-changed"]) == 2
    assert "cannot read --changed-files" in json.loads(capsys.readouterr().out)["error"]


def test_exclude_changed_requires_a_changed_files_list(tmp_path, capsys):
    root = _guidance_repo(tmp_path)
    assert m.main(["--git-root", str(root), "--exclude-changed"]) == 2
    assert "requires --changed-files" in json.loads(capsys.readouterr().out)["error"]


def test_unreadable_changed_files_is_tolerated_without_exclude_changed(tmp_path, capsys):
    root = _guidance_repo(tmp_path)
    missing = Path(tmp_path) / "nope.txt"
    assert m.main(["--git-root", str(root), "--changed-files", str(missing)]) == 0
    assert json.loads(capsys.readouterr().out)["target_repo"]["changed_guidance"] == []


def test_exclude_changed_withholds_a_symlink_whose_target_the_change_edits(tmp_path):
    root = _guidance_repo(tmp_path)
    (root / "CLAUDE.md").unlink()
    (root / "CLAUDE.md").symlink_to("AGENTS.md")

    target = m.gather(str(root), ["AGENTS.md"], exclude_changed=True)

    assert target["changed_guidance"] == ["AGENTS.md", "CLAUDE.md"]
    assert target["claude_md"] == []
    assert target["other"] == []


def test_gather_drops_symlink_loops(tmp_path):
    root = _guidance_repo(tmp_path)
    (root / ".claude" / "rules" / "loop.md").symlink_to("loop.md")
    (root / "pkg" / "loop.py").symlink_to("loop.py")

    target = m.gather(str(root), ["pkg/loop.py"])

    assert [Path(p).name for p in target["rules"]] == ["a.md"]
    assert [Path(p).relative_to(root.resolve()).as_posix() for p in target["claude_md"]] == ["CLAUDE.md"]


def test_gather_finds_guidance_under_a_root_with_glob_metacharacters(tmp_path):
    root = Path(tmp_path) / "proj[1]"
    refs = root / ".claude" / "skills" / "review-x" / "references"
    refs.mkdir(parents=True)
    (root / ".claude" / "skills" / "review-x" / "SKILL.md").write_text("x")
    (refs / "index.md").write_text("i")
    (root / ".claude" / "rules").mkdir()
    (root / ".claude" / "rules" / "a.md").write_text("a")

    target = m.gather(str(root), [])

    assert _rel(root, target["repo_skills"]) == [".claude/skills/review-x/SKILL.md"]
    assert _rel(root, target["repo_skill_references"]) == [".claude/skills/review-x/references/index.md"]
    assert _rel(root, target["rules"]) == [".claude/rules/a.md"]


def test_gather_skill_references_does_not_follow_directory_symlink_cycles(tmp_path):
    root = Path(tmp_path) / "repo"
    refs = root / ".claude" / "skills" / "review-x" / "references"
    (refs / "sub").mkdir(parents=True)
    (refs / "index.md").write_text("i")
    (refs / "sub" / "a.md").write_text("a")
    (refs / "sub" / "back").symlink_to(refs)
    (refs / "self").symlink_to(refs)

    target = m.gather(str(root), [])

    assert _rel(root, target["repo_skill_references"]) == [
        ".claude/skills/review-x/references/index.md", ".claude/skills/review-x/references/sub/a.md"]
    assert target["repo_skill_references_dropped"] == 0


def test_exclude_changed_fails_when_the_changed_files_list_is_empty(tmp_path, capsys):
    root = _guidance_repo(tmp_path)
    empty = Path(tmp_path) / "changed.txt"
    empty.write_text("")
    assert m.main(["--git-root", str(root), "--changed-files", str(empty), "--exclude-changed"]) == 2
    assert "empty" in json.loads(capsys.readouterr().out)["error"]


def test_changed_files_list_with_non_utf8_names_is_read_and_withholds_guidance(tmp_path, capsys):
    root = _guidance_repo(tmp_path)
    changed = Path(tmp_path) / "changed.txt"
    changed.write_bytes(b"caf\xe9.py\nAGENTS.md\n")
    assert m.main(["--git-root", str(root), "--changed-files", str(changed), "--exclude-changed"]) == 0
    target = json.loads(capsys.readouterr().out)["target_repo"]
    assert target["changed_guidance"] == ["AGENTS.md"]
    assert target["other"] == []


def test_gather_avoids_the_python_310_glob_root_dir_keyword(tmp_path, monkeypatch):
    root = Path(tmp_path) / "repo"
    (root / ".claude" / "skills" / "review-x" / "references").mkdir(parents=True)
    (root / ".claude" / "skills" / "review-x" / "SKILL.md").write_text("x")
    (root / ".claude" / "skills" / "review-x" / "references" / "index.md").write_text("i")
    real_glob = m.glob.glob

    def glob_39(pattern, *, recursive=False):
        return real_glob(pattern, recursive=recursive)

    monkeypatch.setattr(m.glob, "glob", glob_39)

    target = m.gather(str(root), [])

    assert _rel(root, target["repo_skills"]) == [".claude/skills/review-x/SKILL.md"]
    assert _rel(root, target["repo_skill_references"]) == [".claude/skills/review-x/references/index.md"]
