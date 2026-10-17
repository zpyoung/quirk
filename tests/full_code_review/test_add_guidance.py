import contextlib
import io
import json
import shlex
import subprocess

import pytest

import add_guidance as m


def _git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def _run(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = m.main(args)
    return rc, json.loads(buf.getvalue())


def test_review_md_target_scaffolds_front_matter_then_appends(tmp_path):
    repo = _git_repo(tmp_path / "repo")
    rc, out = _run(["--note", "first lesson", "--target", "review-md", "--git-root", str(repo)])
    assert rc == 0
    path = repo / "REVIEW.md"
    assert out["path"] == str(path)
    assert "git -C" in out["commit_hint"] and "REVIEW.md" in out["commit_hint"]
    rc, _ = _run(["--note", "second lesson", "--target", "review-md", "--git-root", str(repo)])
    assert rc == 0
    text = path.read_text()
    # empty front matter keeps the file a valid REVIEW.md for resolve_policy
    assert text.startswith("---\n---\n")
    assert text.count("---\n---\n") == 1
    assert text.index("first lesson") < text.index("second lesson")


def test_review_md_target_appends_without_touching_existing_front_matter(tmp_path):
    repo = _git_repo(tmp_path / "repo")
    (repo / "REVIEW.md").write_text("---\nseverity_floor: Must fix\n---\n\nKeep it tight.\n")
    rc, _ = _run(["--note", "new lesson", "--target", "review-md", "--git-root", str(repo)])
    assert rc == 0
    text = (repo / "REVIEW.md").read_text()
    assert text.startswith("---\nseverity_floor: Must fix\n---\n\nKeep it tight.\n")
    assert text.rstrip().endswith("new lesson")


def test_project_pack_target_writes_lessons_file(tmp_path):
    repo = _git_repo(tmp_path / "repo")
    rc, out = _run(["--note", "pack lesson", "--target", "project-pack", "--git-root", str(repo)])
    assert rc == 0
    path = repo / ".quirk" / "review" / "guidance" / "lessons.md"
    assert out["path"] == str(path)
    assert "pack lesson" in path.read_text()
    assert out["commit_hint"]


def test_commit_hint_shell_quotes_paths_with_metacharacters(tmp_path):
    repo = _git_repo(tmp_path / "re$po `x`")
    rc, out = _run(["--note", "lesson", "--target", "review-md", "--git-root", str(repo)])
    assert rc == 0
    assert shlex.split(out["commit_hint"])[:5] == [
        "git", "-C", str(repo.resolve()), "add", str(repo.resolve() / "REVIEW.md")]


def test_user_pack_target_uses_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    rc, out = _run(["--note", "user lesson", "--target", "user-pack", "--git-root", str(tmp_path)])
    assert rc == 0
    path = tmp_path / "config" / "quirk" / "review" / "guidance" / "lessons.md"
    assert out["path"] == str(path)
    assert "user lesson" in path.read_text()
    # not inside a git repo, so there is nothing to commit
    assert out["commit_hint"] is None


@pytest.mark.parametrize("args, message", [
    (["--note", "x", "--target", "review-md"], "git work tree"),
    (["--note", "x", "--target", "project-pack"], "git work tree"),
    (["--note", "x", "--target", "elsewhere"], "--target"),
    (["--note", "   ", "--target", "review-md"], "--note"),
])
def test_errors_exit_2_with_a_json_error(tmp_path, args, message):
    rc, out = _run(args + ["--git-root", str(tmp_path / "not-a-repo")])
    assert rc == 2
    assert message in out["error"]
