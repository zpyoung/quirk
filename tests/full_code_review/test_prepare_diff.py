import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import prepare_diff as m

SAMPLE = (
    "diff --git a/foo.py b/foo.py\n"
    "index 111..222 100644\n"
    "--- a/foo.py\n"
    "+++ b/foo.py\n"
    "@@ -1,3 +1,4 @@\n"
    " a\n+b\n c\n"
    "diff --git a/bar/baz.txt b/bar/baz.txt\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/bar/baz.txt\n"
    "@@ -0,0 +1,2 @@\n"
    "+hello\n+world\n"
)

@pytest.fixture
def gitlab_origin(monkeypatch):
    monkeypatch.setattr(m, "get_origin_url", lambda cwd=".": "git@x:grp/proj.git")
    monkeypatch.setattr(m, "detect_target_branch", lambda cwd=".": "main")


def test_count_changed_lines_counts_header_like_hunk_content():
    diff = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1 +1 @@\n"
        "---- foo\n"
        "++++ b/x.py\n"
    )
    assert m.count_changed_lines(diff) == 2


def test_count_changed_lines_excludes_file_headers():
    diff = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    assert m.count_changed_lines(diff) == 2


def test_count_changed_lines_resets_hunk_state_per_file():
    diff = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/y.py b/y.py\n"
        "--- /dev/null\n"
        "+++ b/y.py\n"
        "@@ -0,0 +1 @@\n"
        "+added\n"
    )
    assert m.count_changed_lines(diff) == 3


def test_count_changed_lines_excludes_no_newline_markers():
    diff = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "\\ No newline at end of file\n"
        "+new\n"
        "\\ No newline at end of file\n"
    )
    assert m.count_changed_lines(diff) == 2


def test_parse_files():
    files = m.parse_unified_diff(SAMPLE)
    assert [f["file"] for f in files] == ["foo.py", "bar/baz.txt"]
    assert len(files[0]["hunks"]) == 1


def test_changed_files():
    assert m.changed_files_from_diff(SAMPLE) == ["foo.py", "bar/baz.txt"]


def test_split_by_file():
    parts = m.split_diff_by_file(SAMPLE)
    assert set(parts) == {"foo.py", "bar/baz.txt"}
    assert "hello" in parts["bar/baz.txt"]


def test_added_diff_metadata_text_is_not_parsed_as_metadata():
    diff = (
        "diff --git a/parser.py b/parser.py\n"
        "index 111..222 100644\n"
        "--- a/parser.py\n"
        "+++ b/parser.py\n"
        "@@ -1 +1,8 @@\n"
        "-old\n"
        "+Binary files a/x and b/x differ\n"
        "+GIT binary patch\n"
        "+diff --git a/fake b/fake\n"
        "+@@ -1 +1 @@\n"
        "+index abc..def\n"
        "+new file mode 100644\n"
        "+\\ No newline at end of file\n"
        "+ordinary\n"
        "diff --git a/image.png b/image.png\n"
        "index 333..444 100644\n"
        "Binary files a/image.png and b/image.png differ\n"
        "diff --git a/patch.bin b/patch.bin\n"
        "new file mode 100644\n"
        "index 000..555\n"
        "GIT binary patch\n"
        "literal 1\n"
        "Ic${Nk000310RR91\n"
    )

    sections = m.split_diff_by_file(diff)
    assert set(sections) == {"parser.py", "image.png", "patch.bin"}
    assert "+diff --git a/fake b/fake" in sections["parser.py"]
    assert m.changed_files_from_diff(diff) == ["parser.py", "image.png", "patch.bin"]
    assert m.not_text_reviewable_from_diff(diff) == ["image.png", "patch.bin"]
    assert m.count_changed_lines(diff) == 9


def test_added_plus_header_text_does_not_replace_file_path():
    diff = (
        "diff --git a/parser.py b/parser.py\n"
        "--- a/parser.py\n"
        "+++ b/parser.py\n"
        "@@ -0,0 +1 @@\n"
        "+++ b/phantom.py\n"
    )
    assert m.changed_files_from_diff(diff) == ["parser.py"]


def test_batch_under_budget():
    b = m.batch_files({"a": "x" * 10, "b": "y" * 10}, 1000)
    assert len(b) == 1 and set(b[0]["files"]) == {"a", "b"}


def test_batch_splits():
    b = m.batch_files({"a": "x" * 600, "b": "y" * 600, "c": "z" * 600}, 1000)
    assert len(b) == 3


def test_batch_oversized_single():
    b = m.batch_files({"big": "x" * 5000, "small": "y" * 10}, 1000)
    assert any(set(x["files"]) == {"big"} for x in b)


def test_host_and_project_flags_override_the_detected_remote(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    seen = []

    def fake_change_diff(forge, number, cwd=".", metadata=None):
        seen.append((forge.name, forge.host, forge.project))
        return None

    monkeypatch.setattr(m, "change_diff", fake_change_diff)
    for extra, expected in (([], ("gitlab", "x", "grp/proj")),
                            (["--host", "h1", "-R", "p1"], ("gitlab", "h1", "p1"))):
        with contextlib.redirect_stderr(io.StringIO()):
            m.main(["--forge", "gitlab", "--change", "1", "--out", str(out)] + extra)
        assert seen[-1] == expected


def _gitlab(host, project):
    return m.make_forge("gitlab", host, project, run=m._late_run)


def test_decision_branch_gitlab_first(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    monkeypatch.setattr(m, "find_change_for_branch", lambda forge, b: 42)
    monkeypatch.setattr(m, "change_diff", lambda forge, number, cwd=".", metadata=None: (
        "diff --git a/z b/z\n--- a/z\n+++ b/z\n@@ -1 +1 @@\n-x\n+y\n",
        {"base": "b" * 40, "start": "c" * 40, "head": "a" * 40},
        {"number": number, "title": "Support locked credit rates", "description": "no behavior change",
         "source_branch": "feature"}))
    monkeypatch.setattr(m, "change_details", lambda forge, number: {
        "number": 42, "state": "opened", "open": True, "author_id": 9, "author_username": "other",
        "source_branch": "feature", "target_branch": "main", "sha": "a" * 40,
        "base_sha": "b" * 40, "start_sha": "c" * 40})
    monkeypatch.setattr(m, "current_user", lambda forge: {"id": 10, "username": "me"})
    monkeypatch.setattr(m, "commit_authors", lambda forge, number: [])
    monkeypatch.setattr(m, "git_diff_branch", lambda *a, **k: "SHOULD_NOT_BE_USED")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = m.main(["--forge", "gitlab", "--branch", "feature", "--out", str(out)])
    assert rc == 0
    meta = json.loads(buf.getvalue())
    assert meta["source"] == "gitlab" and meta["refs"]["head"] == "a" * 40
    assert meta["seat"] == "reviewer"
    ctx = json.loads(out.read_text())
    assert ctx["seat"] == "reviewer" and ctx["change"]["number"] == 42
    assert ctx["change"]["current_user_id"] == 10
    assert "a/z" in ctx["diff"] and "SHOULD_NOT_BE_USED" not in ctx["diff"]
    assert ctx["host"] == "x" and ctx["project"] == "grp/proj"
    assert ctx["source_branch"] == "feature"
    # adversarial gates on the change description reaching the context
    assert ctx["change"]["description"] == "no behavior change"
    assert ctx["has_description"] is True and meta["has_description"] is True
    assert ctx["size"] == {"files": 1, "lines": 2}
    assert ctx["scope_intent"] == {
        "guess": "Support locked credit rates (feature)",
        "basis": "change.title + source_branch",
    }
    assert meta["scope_intent"] == ctx["scope_intent"]


def test_decision_branch_git_fallback(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    monkeypatch.setattr(m, "find_change_for_branch", lambda forge, b: None)
    monkeypatch.setattr(m, "change_diff", lambda *a, **k: None)

    def branch_diff(branch, target, cl, cwd=".", metadata=None):
        metadata["refs"] = {"base": "BASE", "start": "BASE", "head": "HEAD"}
        return "diff --git a/q b/q\n--- a/q\n+++ b/q\n@@ -1 +1 @@\n-1\n+2\n"

    monkeypatch.setattr(m, "git_diff_branch", branch_diff)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = m.main(["--forge", "gitlab", "--branch", "feature", "--out", str(out)])
    assert rc == 0
    meta = json.loads(buf.getvalue())
    assert rc == 0
    assert meta["source"] == "git" and "fallback_reason" in meta
    ctx = json.loads(out.read_text())
    assert "a/q" in ctx["diff"]
    assert ctx["host"] == "x" and ctx["project"] == "grp/proj"
    assert ctx["source_branch"] == "feature"
    assert ctx["refs"] == {"base": "BASE", "start": "BASE", "head": "HEAD"}
    # no change request → no description → adversarial must skip
    assert ctx["change"] is None and ctx["has_description"] is False
    assert ctx["scope_intent"] == {"guess": "feature", "basis": "source_branch"}
    assert meta["scope_intent"] == ctx["scope_intent"]


def test_empty_gitlab_diff_recovered_from_git(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    payload = {
        "iid": 15, "title": "Recover empty diff", "source_branch": "feature/direct-change", "changes_count": "1",
        "diff_refs": {"base_sha": "b" * 40, "start_sha": "c" * 40, "head_sha": "a" * 40},
        "changes": [{
            "old_path": "large.py", "new_path": "large.py",
            "new_file": True, "deleted_file": False, "renamed_file": False,
            "a_mode": "0", "b_mode": "100755", "diff": "",
        }],
    }
    recovered = (
        "diff --git a/large.py b/large.py\n"
        "--- a/large.py\n"
        "+++ b/large.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+one\n+two\n"
    )
    diff_calls = []
    fetched = []

    def fake_run(cmd, timeout=90):
        if cmd[0] == "glab":
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
        if cmd[:3] == ["git", "-C", "."] and "diff" in cmd:
            diff_calls.append(cmd)
            assert "large.py" in cmd
            if fetched:
                return SimpleNamespace(returncode=0, stdout=recovered)
            return SimpleNamespace(returncode=1, stdout="")
        if "cat-file" in cmd:
            return SimpleNamespace(
                returncode=1 if ("b" * 40 + "^{commit}") in cmd else 0, stdout="")
        if "fetch" in cmd:
            assert cmd[-1] == "b" * 40
            fetched.append(cmd)
            return SimpleNamespace(returncode=0, stdout="")
        raise AssertionError(cmd)

    monkeypatch.setattr(m, "_run", fake_run)
    # the shared fake_run answers every glab call with the MR payload, so seat
    # detection is stubbed rather than fed a second fixture
    monkeypatch.setattr(m, "change_details", lambda *a, **k: {
        "number": 15, "state": "opened", "open": True, "author_id": 1, "author_username": "author",
        "sha": "a" * 40, "base_sha": "b" * 40, "start_sha": "c" * 40})
    monkeypatch.setattr(m, "current_user", lambda forge: {"id": 1, "username": "author"})
    monkeypatch.setattr(m, "commit_authors", lambda forge, number: [])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert m.main(["--forge", "gitlab", "--change", "15", "--out", str(out)]) == 0
    meta = json.loads(buf.getvalue())
    ctx = json.loads(out.read_text())
    assert recovered.strip() in ctx["diff"]
    assert ctx["source_branch"] == "feature/direct-change"
    assert ctx["diff_unavailable"] == []
    assert meta["diff_unavailable"] == []
    assert ctx["size"] == {"files": 1, "lines": 2}
    assert ctx["scope_intent"] == {
        "guess": "Recover empty diff (feature/direct-change)",
        "basis": "change.title + source_branch",
    }
    assert meta["scope_intent"] == ctx["scope_intent"]
    assert fetched and diff_calls


def test_collapsed_nonempty_gitlab_diff_is_recovered(monkeypatch):
    change = {
        "old_path": "large.py", "new_path": "large.py", "collapsed": True,
        "diff": "@@ -1 +1 @@\n-untrusted\n+partial\n",
    }
    recovered = (
        "diff --git a/large.py b/large.py\n"
        "--- a/large.py\n+++ b/large.py\n"
        "@@ -1 +1 @@\n-old\n+complete\n"
    )
    calls = []

    def recover(base, head, path, cwd=".", metadata=None):
        calls.append((base, head, path, cwd))
        return recovered

    monkeypatch.setattr(m, "_git_diff_path", recover)
    diff_text, changed_files, unavailable, not_text = m._prepare_change_records(
        [change], {"base": "BASE", "head": "HEAD"})
    assert calls == [("BASE", "HEAD", "large.py", ".")]
    assert diff_text == recovered
    assert "untrusted" not in diff_text
    assert changed_files == ["large.py"]
    assert unavailable == []
    assert not_text == []


def test_truncated_new_file_without_recovery_is_unavailable(monkeypatch):
    change = {
        "old_path": "large.py", "new_path": "large.py",
        "new_file": True, "a_mode": "0", "b_mode": "100755", "diff": "",
    }
    calls = []

    def no_recovery(base, head, path, cwd=".", metadata=None):
        calls.append((base, head, path, cwd))
        return None

    monkeypatch.setattr(m, "_git_diff_path", no_recovery)
    diff_text, changed_files, unavailable, not_text = m._prepare_change_records(
        [change], {"base": "BASE", "head": "HEAD"})
    assert calls == [("BASE", "HEAD", "large.py", ".")]
    assert diff_text == ""
    assert changed_files == ["large.py"]
    assert unavailable == ["large.py"]
    assert not_text == []


def test_truncated_deleted_file_attempts_recovery(monkeypatch):
    change = {
        "old_path": "removed.py", "new_path": "removed.py",
        "deleted_file": True, "a_mode": "100644", "b_mode": "0", "diff": "",
    }
    calls = []

    def no_recovery(base, head, path, cwd=".", metadata=None):
        calls.append(path)
        return None

    monkeypatch.setattr(m, "_git_diff_path", no_recovery)
    _, changed_files, unavailable, _ = m._prepare_change_records(
        [change], {"base": "BASE", "head": "HEAD"})
    assert calls == ["removed.py"]
    assert changed_files == ["removed.py"]
    assert unavailable == ["removed.py"]


def test_truncated_rename_content_is_recovered(tmp_path):
    repo = Path(tmp_path) / "rename"
    repo.mkdir()
    _repo_git(repo, "init", "-q")
    (repo / "old.py").write_text("one\ntwo\nthree\nfour\n")
    _repo_git(repo, "add", "old.py")
    _repo_git(repo, "commit", "-qm", "base")
    base = _repo_git(repo, "rev-parse", "HEAD")
    _repo_git(repo, "mv", "old.py", "new.py")
    (repo / "new.py").write_text("one\ntwo\ninserted\nthree\nfour\n")
    _repo_git(repo, "add", "new.py")
    _repo_git(repo, "commit", "-qm", "rename and edit")
    head = _repo_git(repo, "rev-parse", "HEAD")
    change = {
        "old_path": "old.py", "new_path": "new.py",
        "renamed_file": True, "diff": "",
    }

    diff_text, changed_files, unavailable, not_text = m._prepare_change_records(
        [change], {"base": base, "head": head}, str(repo))

    assert "diff --git a/old.py b/new.py" in diff_text
    assert "similarity index" in diff_text
    assert "rename from old.py\nrename to new.py" in diff_text
    assert "--- a/old.py\n+++ b/new.py" in diff_text
    assert m.count_changed_lines(diff_text) == 1
    assert changed_files == ["new.py"]
    assert unavailable == []
    assert not_text == []


def test_pure_rename_is_expected_empty_after_recovery(monkeypatch):
    change = {
        "old_path": "old.py", "new_path": "new.py",
        "renamed_file": True, "diff": "",
    }
    calls = []

    def no_content_delta(base, head, path, cwd=".", old_path=None, metadata=None):
        calls.append((old_path, path))
        return ""

    monkeypatch.setattr(m, "_git_diff_path", no_content_delta)
    diff_text, changed_files, unavailable, not_text = m._prepare_change_records(
        [change], {"base": "BASE", "head": "HEAD"})
    assert calls == [("old.py", "new.py")]
    assert diff_text == ""
    assert changed_files == ["new.py"]
    assert unavailable == []
    assert not_text == []


def test_failed_rename_and_mode_recovery_is_unavailable(monkeypatch):
    changes = [
        {"old_path": "old.py", "new_path": "new.py", "renamed_file": True, "diff": ""},
        {"old_path": "run.sh", "new_path": "run.sh", "a_mode": "100644",
         "b_mode": "100755", "diff": ""},
    ]
    monkeypatch.setattr(m, "_git_diff_path", lambda *args, **kwargs: None)
    _, changed_files, unavailable, _ = m._prepare_change_records(
        changes, {"base": "BASE", "head": "HEAD"})
    assert changed_files == ["new.py", "run.sh"]
    assert unavailable == ["new.py", "run.sh"]


def test_identical_blobs_prove_metadata_only_change(monkeypatch):
    change = {
        "old_path": "old.py", "new_path": "new.py", "renamed_file": True,
        "a_blob_id": "SAME", "b_blob_id": "SAME", "diff": "",
    }
    monkeypatch.setattr(m, "_git_diff_path", lambda *args, **kwargs: None)
    _, _, unavailable, _ = m._prepare_change_records(
        [change], {"base": "BASE", "head": "HEAD"})
    assert unavailable == []


def test_binary_change_skips_recovery(monkeypatch):
    change = {
        "old_path": "image.png", "new_path": "image.png",
        "binary_file": True, "diff": "",
    }
    def fail_recovery(*args, **kwargs):
        raise AssertionError("binary recovery attempted")

    monkeypatch.setattr(m, "_git_diff_path", fail_recovery)
    diff_text, changed_files, unavailable, not_text = m._prepare_change_records(
        [change], {"base": "BASE", "head": "HEAD"})
    assert diff_text == ""
    assert changed_files == ["image.png"]
    assert unavailable == []
    assert not_text == ["image.png"]


def test_empty_gitlab_diff_unavailable_is_not_rendered(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    payload = {
        "iid": 16, "changes_count": "2",
        "diff_refs": {"base_sha": "b" * 40, "start_sha": "c" * 40, "head_sha": "a" * 40},
        "changes": [
            {
                "old_path": "normal.py", "new_path": "normal.py",
                "new_file": False, "deleted_file": False, "renamed_file": False,
                "diff": "@@ -1 +1 @@\n-old\n+new\n",
            },
            {
                "old_path": "missing.py", "new_path": "missing.py",
                "new_file": False, "deleted_file": False, "renamed_file": False,
                "diff": "  \n",
            },
        ],
    }
    def fake_run(cmd, timeout=90):
        if cmd[0] == "glab":
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
        if "diff" in cmd:
            return SimpleNamespace(returncode=1, stdout="")
        if "cat-file" in cmd:
            return SimpleNamespace(returncode=0, stdout="")
        raise AssertionError(cmd)

    monkeypatch.setattr(m, "_run", fake_run)
    # the shared fake_run answers every glab call with the MR payload, so seat
    # detection is stubbed rather than fed a second fixture
    monkeypatch.setattr(m, "change_details", lambda *a, **k: {
        "number": 16, "state": "opened", "open": True, "author_id": 1, "author_username": "author",
        "sha": "a" * 40, "base_sha": "b" * 40, "start_sha": "c" * 40})
    monkeypatch.setattr(m, "current_user", lambda forge: {"id": 1, "username": "author"})
    monkeypatch.setattr(m, "commit_authors", lambda forge, number: [])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert m.main(["--forge", "gitlab", "--change", "16", "--out", str(out)]) == 0
    meta = json.loads(buf.getvalue())
    ctx = json.loads(out.read_text())
    assert ctx["diff_unavailable"] == ["missing.py"]
    assert meta["diff_unavailable"] == ["missing.py"]
    assert ctx["changed_files"] == ["normal.py", "missing.py"]
    assert "diff --git a/normal.py b/normal.py" in ctx["diff"]
    assert "diff --git a/missing.py b/missing.py" not in ctx["diff"]


def test_expected_empty_gitlab_changes_are_not_unavailable(monkeypatch):
    payload = {
        "iid": 17, "changes_count": "2",
        "diff_refs": {"base_sha": "BASE", "start_sha": "START", "head_sha": "HEAD"},
        "changes": [
            {
                "old_path": "image.png", "new_path": "image.png",
                "binary_file": True, "diff": "",
            },
            {
                "old_path": "old.py", "new_path": "new.py",
                "renamed_file": True, "a_blob_id": "SAME", "b_blob_id": "SAME",
                "diff": "",
            },
        ],
    }
    def fake_run(cmd, timeout=90):
        if cmd[0] == "glab":
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
        raise AssertionError(cmd)

    monkeypatch.setattr(m, "_run", fake_run)
    metadata = {}
    diff_text, refs, change = m.change_diff(_gitlab("host", "grp/proj"), 17, ".", metadata)
    assert diff_text == ""
    assert refs["head"] == "HEAD" and change["number"] == 17
    assert metadata["changed_files"] == ["image.png", "new.py"]
    assert metadata["diff_unavailable"] == []
    assert metadata["not_text_reviewable"] == ["image.png"]


def test_normal_gitlab_reconstruction_is_unchanged():
    changes = [
        {
            "old_path": "foo.py", "new_path": "foo.py",
            "new_file": False, "deleted_file": False, "renamed_file": False,
            "diff": "@@ -1 +1 @@\n-old\n+new\n",
        },
        {
            "old_path": "added.txt", "new_path": "added.txt",
            "new_file": True, "deleted_file": False, "renamed_file": False,
            "a_mode": "0", "b_mode": "100755",
            "diff": "@@ -0,0 +1 @@\n+added\n",
        },
    ]
    expected = (
        "diff --git a/foo.py b/foo.py\n"
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        "diff --git a/added.txt b/added.txt\n"
        "new file mode 100755\n"
        "--- /dev/null\n"
        "+++ b/added.txt\n"
        "@@ -0,0 +1 @@\n+added\n"
    )
    assert m.reconstruct_diff_from_changes(changes) == expected


def test_reconstruction_uses_change_modes():
    deleted = {
        "old_path": "run.sh", "new_path": "run.sh", "deleted_file": True,
        "a_mode": "100755", "b_mode": "0", "diff": "@@ -1 +0,0 @@\n-exit 0\n",
    }
    modified = {
        "old_path": "deploy.sh", "new_path": "deploy.sh",
        "a_mode": "100644", "b_mode": "100755", "diff": "@@ -1 +1 @@\n-old\n+new\n",
    }
    rendered = m.reconstruct_diff_from_changes([deleted, modified])
    assert "deleted file mode 100755" in rendered
    assert "old mode 100644\nnew mode 100755" in rendered


def test_gitlab_overflow_recovers_full_diff(monkeypatch):
    full_diff = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+A\n"
        "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n-b\n+B\n"
    )
    payload = {
        "iid": 18, "overflow": True, "changes_count": "2",
        "diff_refs": {"base_sha": "BASE", "start_sha": "START", "head_sha": "HEAD"},
        "changes": [{"old_path": "a.py", "new_path": "a.py", "diff": "@@ -1 +1 @@\n-a\n+A\n"}],
    }
    def fake_run(cmd, timeout=90):
        if cmd[0] == "glab":
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
        if cmd[:3] == ["git", "-C", "."] and "diff" in cmd and cmd[-1] == "BASE..HEAD":
            stdout = "a.py\0b.py\0" if "--name-only" in cmd else full_diff
            return SimpleNamespace(returncode=0, stdout=stdout)
        raise AssertionError(cmd)

    monkeypatch.setattr(m, "_run", fake_run)
    metadata = {}
    diff_text, refs, _ = m.change_diff(_gitlab("host", "grp/proj"), 18, ".", metadata)
    assert diff_text == full_diff and refs["head"] == "HEAD"
    assert metadata["changed_files"] == ["a.py", "b.py"]
    assert metadata["file_list_recovery"] == {
        "api_file_count": 1, "reported_changes_count": "2", "overflow": True,
        "recovered_file_count": 2, "recovered_from": "git",
    }


def test_gitlab_count_mismatch_fails_when_full_diff_cannot_be_recovered(monkeypatch):
    payload = {
        "iid": 19, "overflow": False, "changes_count": "2",
        "diff_refs": {"base_sha": "BASE", "head_sha": "HEAD"},
        "changes": [{"old_path": "a.py", "new_path": "a.py", "diff": "x"}],
    }
    def fake_run(cmd, timeout=90):
        if cmd[0] == "glab":
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(m, "_run", fake_run)
    metadata = {}
    assert m.change_diff(_gitlab("host", "grp/proj"), 19, ".", metadata) is None
    assert "truncated" in metadata["error"]


def test_gitlab_malformed_change_count_fails_without_full_recovery(monkeypatch):
    payload = {
        "iid": 20, "changes_count": "unknown",
        "diff_refs": {"base_sha": "BASE", "head_sha": "HEAD"},
        "changes": [{
            "old_path": "a.py", "new_path": "a.py",
            "diff": "@@ -1 +1 @@\n-old\n+new\n",
        }],
    }
    def fake_run(cmd, timeout=90):
        if cmd[0] == "glab":
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(m, "_run", fake_run)
    metadata = {}
    assert m.change_diff(_gitlab("host", "grp/proj"), 20, ".", metadata) is None
    assert "truncated" in metadata["error"]


def test_mr_failure_is_nonzero_structured_and_removes_output(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    out.write_text("stale")

    def failed_change(forge, number, cwd=".", metadata=None):
        metadata["error"] = "request failed"
        return None

    monkeypatch.setattr(m, "change_diff", failed_change)
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = m.main(["--forge", "gitlab", "--change", "999999", "--out", str(out)])
    assert rc != 0 and not out.exists() and stdout.getvalue() == ""
    error = json.loads(stderr.getvalue())
    assert error["status"] == "error"
    assert error["error"]["code"] == "diff_source_failed"


def test_branch_and_local_git_failures_are_nonzero(tmp_path, monkeypatch, gitlab_origin):
    monkeypatch.setattr(m, "find_change_for_branch", lambda forge, branch: None)
    monkeypatch.setattr(m, "git_diff_branch", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "git_diff_local", lambda *args, **kwargs: None)
    for selector in (["--forge", "gitlab", "--branch", "bad"], ["--local"]):
        out = Path(tmp_path) / (selector[0][2:] + ".json")
        with contextlib.redirect_stderr(io.StringIO()):
            assert m.main(selector + ["--out", str(out)]) != 0
        assert not out.exists()


def test_glab_branch_lookup_uses_resolved_host(monkeypatch):
    calls = []

    def fake_run(cmd, timeout=90):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="[]")

    monkeypatch.setattr(m, "_run", fake_run)
    assert m.find_change_for_branch(
        _gitlab("other.gitlab.example", "group/project"), "feature") is None
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[:3] == ["glab", "mr", "list"]
    assert "--hostname" not in cmd
    assert cmd[cmd.index("-R") + 1] == "https://other.gitlab.example/group/project"


def test_manifest_without_diff_section_fails_closed(tmp_path, monkeypatch):
    out = Path(tmp_path) / "context.json"
    out.write_text("stale")
    monkeypatch.setattr(m, "get_origin_url", lambda cwd=".": "")
    monkeypatch.setattr(m, "detect_target_branch", lambda cwd=".": "main")

    def corrupt_diff(context_lines, cwd=".", metadata=None, excluded_path=None):
        metadata["changed_files"] = ["review.py"]
        metadata["refs"] = {"base": "HEAD", "start": "HEAD", "head": "HEAD"}
        return "arbitrary external diff output\n"

    monkeypatch.setattr(m, "git_diff_local", corrupt_diff)
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        rc = m.main(["--local", "--out", str(out)])
    error = json.loads(stderr.getvalue())
    assert rc != 0
    assert not out.exists()
    assert error["error"]["paths"] == ["review.py"]


def test_local_diff_ignores_hostile_repo_config(tmp_path):
    repo = Path(tmp_path) / "hostile"
    repo.mkdir()
    _repo_git(repo, "init", "-q")
    _repo_git(repo, "checkout", "-b", "feature/local-review")
    (repo / ".gitattributes").write_text("*.txt diff=hostile\n")
    (repo / "review.txt").write_text("old\n")
    _repo_git(repo, "add", ".")
    _repo_git(repo, "commit", "-qm", "base")
    _repo_git(repo, "config", "color.ui", "always")
    _repo_git(repo, "config", "diff.external", "/bin/echo")
    _repo_git(repo, "config", "diff.noprefix", "true")
    _repo_git(repo, "config", "diff.hostile.textconv", "/bin/echo")
    (repo / "review.txt").write_text("new\n")

    out = Path(tmp_path) / "hostile.json"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert m.main(["--local", "--cwd", str(repo), "--out", str(out)]) == 0
    meta = json.loads(buf.getvalue())
    ctx = json.loads(out.read_text())
    assert ctx["changed_files"] == ["review.txt"]
    assert ctx["size"] == {"files": 1, "lines": 2}
    assert ctx["source_branch"] == "feature/local-review"
    assert ctx["scope_intent"] == {"guess": "feature/local-review", "basis": "source_branch"}
    assert meta["source_branch"] == "feature/local-review"
    assert meta["scope_intent"] == ctx["scope_intent"]
    assert "diff --git a/review.txt b/review.txt" in ctx["diff"]
    assert "-old\n+new" in ctx["diff"]
    assert "\x1b" not in ctx["diff"]
    assert ctx["diff_unavailable"] == []


def test_local_output_inside_repo_is_excluded_from_untracked_manifest(tmp_path):
    repo = Path(tmp_path) / "repo-with-output"
    repo.mkdir()
    _repo_git(repo, "init", "-q")
    reviewed = repo / "review.py"
    reviewed.write_text("old\n")
    _repo_git(repo, "add", "review.py")
    _repo_git(repo, "commit", "-qm", "base")
    reviewed.write_text("new\n")
    (repo / "nested").mkdir()
    output = repo / "context.json"
    output.write_text('{"stale": true}\n')
    output_with_parent = repo / "nested" / ".." / "context.json"

    assert m.main(["--local", "--cwd", str(repo),
                   "--out", str(output_with_parent)]) == 0
    ctx = json.loads(output.read_text())
    assert ctx["changed_files"] == ["review.py"]
    assert ctx["untracked_files"] == []
    assert ctx["size"] == {"files": 1, "lines": 2}
    assert "context.json" not in ctx["diff"]


def test_local_staged_unstaged_and_untracked_are_preserved_when_batched(tmp_path):
    repo = Path(tmp_path) / "repo"
    repo.mkdir()

    def git(*args):
        return _repo_git(repo, *args)

    git("init", "-q")
    collision = repo / "COLLIDE_TEST.txt"
    collision.write_text("one\ntwo\nthree\n")
    git("add", "COLLIDE_TEST.txt")
    git("commit", "-qm", "init")
    collision.write_text("ONE\ntwo\nthree\n")
    git("add", "COLLIDE_TEST.txt")
    collision.write_text("ONE\nTWO\nthree\n")
    (repo / "new.spec.ts").write_text("test('x', () => {})\n")

    out = Path(tmp_path) / "ctx.json"
    assert m.main(["--local", "--cwd", str(repo), "--max-chars", "1",
                   "--out", str(out)]) == 0
    ctx = json.loads(out.read_text())
    assert ctx["changed_files"] == ["COLLIDE_TEST.txt", "new.spec.ts"]
    assert ctx["size"]["files"] == 2
    collision_batches = [b for b in ctx["batches"] if b["files"] == ["COLLIDE_TEST.txt"]]
    assert len(collision_batches) == 1
    assert "+ONE" in collision_batches[0]["diff"]
    assert "+TWO" in collision_batches[0]["diff"]
    assert ctx["untracked_files"] == ["new.spec.ts"]
    assert ctx["test_files"] == ["new.spec.ts"]
    assert ctx["refs"]["base"] and ctx["refs"]["head"]


def test_test_file_classifier():
    tests = [
        "tests/unit/foo.py", "pkg/test_widget.py", "pkg/widget_test.py", "conftest.py",
        "web/foo.test.ts", "web/foo.spec.js", "web/foo.test.d.ts",
        "web/__tests__/foo.tsx", "go/widget_test.go", "src/main/WidgetTest.java",
        "module/src/test/kotlin/Foo.kt",
        "lib/widget_spec.rb", "spec/widget.rb",
        "test/foo.js", "test/models/user_test.rb", "Billing/InvoiceTests.cs",
    ]
    sources = ["src/widget.py", "web/widget.ts", "go/widget.go", "src/main/Widget.java"]
    test_files, source_files = m.classify_files(tests + sources + [tests[0]])
    assert test_files == tests
    assert source_files == sources


def test_local_diff_of_a_non_utf8_file_is_written_and_round_trips(tmp_path):
    repo = Path(tmp_path) / "latin1"
    repo.mkdir()
    _repo_git(repo, "init", "-q")
    (repo / "menu.txt").write_bytes(b"base\n")
    _repo_git(repo, "add", ".")
    _repo_git(repo, "commit", "-qm", "base")
    (repo / "menu.txt").write_bytes(b"caf\xe9\n")
    out = Path(tmp_path) / "latin1.json"
    with contextlib.redirect_stdout(io.StringIO()):
        assert m.main(["--local", "--cwd", str(repo), "--out", str(out)]) == 0
    ctx = json.loads(out.read_text(encoding="utf-8"))
    assert ctx["changed_files"] == ["menu.txt"]
    assert b"caf\xe9" in ctx["diff"].encode("utf-8", "surrogateescape")


def test_c_quoted_paths_round_trip_through_diff_helpers():
    diff = (
        'diff --git "a/a\\tb.py" "b/a\\tb.py"\n'
        '--- "a/a\\tb.py"\n'
        '+++ "b/a\\tb.py"\n'
        '@@ -1 +1 @@\n-old\n+new\n'
        'diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\n'
        '--- "a/caf\\303\\251.py"\n'
        '+++ "b/caf\\303\\251.py"\n'
        '@@ -1 +1 @@\n-old\n+new\n'
    )
    expected = ["a\tb.py", "café.py"]
    assert m.changed_files_from_diff(diff) == expected
    assert list(m.split_diff_by_file(diff)) == expected
    assert m.batch_files(m.split_diff_by_file(diff), 1)[0]["files"] == ["a\tb.py"]


def test_c_quoted_control_character_escapes_decode_to_their_bytes():
    path = "a\x0bb\x0cc\x07d\x08e.py"
    quoted = m._quote_git_path(path)
    assert quoted == '"a\\vb\\fc\\ad\\be.py"'
    assert m._decode_git_path(quoted) == path


def test_octal_escape_above_a_byte_degrades_instead_of_raising():
    diff = 'diff --git "a/x\\777" "b/x\\777"\n@@ -1 +1 @@\n-a\n+b\n'
    assert m.changed_files_from_diff(diff) == ["x\udcff"]


def test_local_diff_keeps_paths_with_control_characters_in_the_manifest(tmp_path):
    repo = Path(tmp_path) / "ctl"
    repo.mkdir()
    _repo_git(repo, "init", "-q")
    odd = repo / "a\x0bb\x0cc\x07d.py"
    odd.write_text("old\n")
    _repo_git(repo, "add", ".")
    _repo_git(repo, "commit", "-qm", "init")
    odd.write_text("new\n")
    out = Path(tmp_path) / "ctl.json"
    assert m.main(["--local", "--cwd", str(repo), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["changed_files"] == ["a\x0bb\x0cc\x07d.py"]


def test_git_output_keeps_carriage_returns(repo):
    (repo / "win.txt").write_bytes(b"one\r\ntwo\rzz\n")
    _repo_git(repo, "add", ".")
    diff_text = m.git_diff_local(3, str(repo))
    assert "+one\r\n" in diff_text
    assert "+two\rzz\n" in diff_text
    assert list(m.split_diff_by_file(diff_text)) == ["win.txt"]


def test_local_diff_keeps_reviewing_when_one_untracked_file_cannot_be_diffed(repo, monkeypatch):
    (repo / "bad.py").write_text("bad\n")
    (repo / "good.py").write_text("good\n")
    real = m._untracked_diff
    monkeypatch.setattr(m, "_untracked_diff",
                        lambda path, cwd: None if path == "bad.py" else real(path, cwd))
    metadata = {}
    diff_text = m.git_diff_local(3, str(repo), metadata)
    assert diff_text is not None and "diff --git a/good.py b/good.py" in diff_text
    assert metadata["untracked_files"] == ["good.py"]
    assert metadata["diff_unavailable"] == ["bad.py"]
    assert sorted(metadata["changed_files"]) == ["bad.py", "good.py"]


def test_unescaped_spaces_in_diff_git_paths_are_parsed():
    diff = (
        "diff --git a/a b.py b/a b.py\n"
        "--- a/a b.py\t\n"
        "+++ b/a b.py\t\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    assert m._path_from_diff_git("diff --git a/a b.py b/a b.py") == "a b.py"
    assert m.changed_files_from_diff(diff) == ["a b.py"]
    assert list(m.split_diff_by_file(diff)) == ["a b.py"]


def test_quoted_paths_survive_local_manifest_batching_and_classification(tmp_path):
    repo = Path(tmp_path) / "quoted"
    repo.mkdir()

    def git(*args):
        return _repo_git(repo, *args)

    git("init", "-q")
    source = repo / "src" / "a\tb.py"
    binary_test = repo / "tests" / "café.py"
    source.parent.mkdir()
    binary_test.parent.mkdir()
    source.write_text("old\n")
    binary_test.write_bytes(b"\0old")
    git("add", ".")
    git("commit", "-qm", "init")
    source.write_text("new\n")
    binary_test.write_bytes(b"\0new")

    out = Path(tmp_path) / "quoted.json"
    assert m.main(["--local", "--cwd", str(repo), "--max-chars", "1",
                   "--out", str(out)]) == 0
    ctx = json.loads(out.read_text())
    expected = ["src/a\tb.py", "tests/café.py"]
    assert ctx["changed_files"] == expected
    assert [path for batch in ctx["batches"] for path in batch["files"]] == expected
    assert ctx["source_files"] == ["src/a\tb.py"]
    assert ctx["test_files"] == ["tests/café.py"]
    assert ctx["not_text_reviewable"] == ["tests/café.py"]


def test_literal_pathspec_failure_is_reported_unavailable(monkeypatch):
    change = {"old_path": ":(exclude)secret.py", "new_path": ":(exclude)secret.py",
              "diff": ""}
    calls = []
    def fake_run(cmd, timeout=90):
        calls.append(cmd)
        if "diff" in cmd:
            return SimpleNamespace(returncode=0, stdout="")
        if "cat-file" in cmd:
            return SimpleNamespace(returncode=0, stdout="")
        raise AssertionError(cmd)

    monkeypatch.setattr(m, "_run", fake_run)
    _, changed, unavailable, _ = m._prepare_change_records(
        [change], {"base": "BASE", "head": "HEAD"})
    assert changed == [":(exclude)secret.py"]
    assert unavailable == [":(exclude)secret.py"]
    diff_cmd = next(cmd for cmd in calls if "diff" in cmd)
    assert "--literal-pathspecs" in diff_cmd
    assert diff_cmd[-2:] == ["--", ":(exclude)secret.py"]


def test_docs_only_diff_has_no_source_files():
    diff = (
        "diff --git a/docs/guide.md b/docs/guide.md\n"
        "--- a/docs/guide.md\n+++ b/docs/guide.md\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    changed = m.changed_files_from_diff(diff)
    tests, sources = m.classify_files(changed)
    assert changed == ["docs/guide.md"]
    assert tests == []
    assert sources == []
    assert m.classify_files([
        "settings.yaml", "package.json", "pyproject.toml", "Cargo.lock", "go.sum"
    ])[1] == []


@pytest.mark.parametrize("path, expected", [
    ("package-lock.json", False), ("poetry.lock", False), ("yarn.lock", False),
    ("pnpm-lock.yaml", False), ("Cargo.lock", False), ("Gemfile.lock", False),
    ("composer.lock", False), ("go.sum", False), ("uv.lock", False), ("bun.lockb", False),
    ("web/package-lock.json", False),
    ("src/distributed_lock.py", True), ("file-lock.ts", True), ("src/lock.go", True),
    ("pkg/lockfile.py", True), ("app/unlock.rb", True),
    ("LICENSE", False), ("NOTICE", False), (".gitignore", False), ("web/logo.png", False),
    ("assets/icon.svg", False), ("notes.txt", False), ("src/licensing.py", True),
])
def test_is_source_file_separates_lockfiles_from_source_with_lock_in_the_name(path, expected):
    assert m.is_source_file(path) is expected


def test_change_touching_only_lock_named_source_still_has_source_files():
    assert m.classify_files(["src/distributed_lock.py", "package-lock.json"]) == (
        [], ["src/distributed_lock.py"])


def _repo_git(repo, *args):
    result = m._run(["git", "-C", str(repo)] + list(args), timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _branch_repo(tmp_path, divergent=False):
    origin = Path(tmp_path) / "origin.git"
    seed = Path(tmp_path) / "seed"
    review = Path(tmp_path) / "review"
    assert m._run(["git", "init", "--bare", "-q", str(origin)], timeout=30).returncode == 0
    assert m._run(["git", "clone", "-q", str(origin), str(seed)], timeout=30).returncode == 0
    (seed / "base.txt").write_text("base\n")
    _repo_git(seed, "add", ".")
    _repo_git(seed, "commit", "-qm", "base")
    _repo_git(seed, "branch", "-M", "main")
    _repo_git(seed, "push", "-q", "-u", "origin", "main")
    base = _repo_git(seed, "rev-parse", "HEAD")

    _repo_git(seed, "checkout", "-qb", "feature")
    if not divergent:
        (seed / "shared.txt").write_text("shared\n")
        _repo_git(seed, "add", ".")
        _repo_git(seed, "commit", "-qm", "shared")
        target = _repo_git(seed, "rev-parse", "HEAD")
    else:
        target = None
    (seed / "feature.txt").write_text("feature\n")
    _repo_git(seed, "add", ".")
    _repo_git(seed, "commit", "-qm", "feature")
    head = _repo_git(seed, "rev-parse", "HEAD")
    _repo_git(seed, "push", "-q", "origin", "feature")

    _repo_git(seed, "checkout", "-q", "main")
    if divergent:
        (seed / "target.txt").write_text("target\n")
        _repo_git(seed, "add", ".")
        _repo_git(seed, "commit", "-qm", "target")
        target = _repo_git(seed, "rev-parse", "HEAD")
    else:
        _repo_git(seed, "merge", "--ff-only", target)
    _repo_git(seed, "push", "-q", "origin", "main")
    _repo_git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    assert m._run(["git", "clone", "-q", str(origin), str(review)], timeout=30).returncode == 0
    return review, base, target, head


def _assert_remote_target_diff(review, expected_base):
    metadata = {}
    diff = m.git_diff_branch("feature", "main", 3, str(review), metadata)
    assert diff is not None
    assert metadata["refs"]["base"] == expected_base
    assert metadata["changed_files"] == ["feature.txt"]
    assert m.changed_files_from_diff(diff) == ["feature.txt"]


def test_branch_diff_ignores_stale_local_target(tmp_path):
    review, base, target, _ = _branch_repo(tmp_path)
    _repo_git(review, "checkout", "-q", "-B", "main", base)
    _assert_remote_target_diff(review, target)


def test_branch_diff_ignores_locally_ahead_target(tmp_path):
    review, _, target, head = _branch_repo(tmp_path)
    _repo_git(review, "checkout", "-q", "-B", "main", head)
    _assert_remote_target_diff(review, target)


def test_branch_diff_uses_divergent_remote_target(tmp_path):
    review, base, _, _ = _branch_repo(tmp_path, divergent=True)
    _repo_git(review, "checkout", "-q", "-B", "main", base)
    _assert_remote_target_diff(review, base)


def test_detect_seat_prefers_numeric_identity():
    assert m.detect_seat("same", "same", 1, 2) == "reviewer"
    assert m.detect_seat("renamed", "other", 7, 7) == "author"
    assert m.detect_seat("Me", "me") == "author"
    assert m.detect_seat(None, "me") is None


def test_mr_snapshot_race_blocks_seat_and_output(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    monkeypatch.setattr(m, "change_diff", lambda *args, **kw: (
        SAMPLE, {"base": "b" * 40, "start": "c" * 40, "head": "a" * 40},
        {"number": 42, "title": "t", "description": "d", "source_branch": "feature"}))
    monkeypatch.setattr(m, "change_details", lambda *args: {"number": 42, "state": "opened", "open": True, "sha": "d" * 40,
                                               "author_id": 1, "author_username": "other"})
    monkeypatch.setattr(m, "current_user", lambda forge: {"id": 2, "username": "me"})
    monkeypatch.setattr(m, "commit_authors", lambda forge, number: [])
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        rc = m.main(["--forge", "gitlab", "--change", "42", "--out", str(out)])
    assert rc == 1 and not out.exists()
    failure = json.loads(buf.getvalue())
    assert failure["seat"] == "unknown"
    assert "head moved" in failure["error"]["message"]


def test_change_details_retains_all_refs(monkeypatch):
    def fake_run(cmd, timeout=90):
        body = {"number": 42, "state": "opened", "open": True, "sha": "a" * 40,
                "diff_refs": {"base_sha": "b" * 40, "start_sha": "c" * 40, "head_sha": "a" * 40},
                "author": {"id": 1, "username": "other"},
                "source_branch": "feature", "target_branch": "main"}
        return type("Result", (), {"returncode": 0, "stdout": json.dumps(body), "stderr": ""})()
    monkeypatch.setattr(m, "_run", fake_run)
    details = m.change_details(_gitlab("gitlab.example", "grp/proj"), 42)
    assert details["base_sha"] == "b" * 40 and details["start_sha"] == "c" * 40


def test_mr_target_movement_between_reads_blocks_seat_and_output(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    monkeypatch.setattr(m, "change_diff", lambda *args, **kw: (
        SAMPLE, {"base": "b" * 40, "start": "c" * 40, "head": "a" * 40},
        {"number": 42, "title": "t", "description": "d", "source_branch": "feature"}))
    monkeypatch.setattr(m, "change_details", lambda *args: {"number": 42, "state": "opened", "open": True, "sha": "a" * 40,
                                       "base_sha": "b" * 40, "start_sha": "e" * 40,
                                       "author_id": 1, "author_username": "other"})
    monkeypatch.setattr(m, "current_user", lambda forge: {"id": 2, "username": "me"})
    monkeypatch.setattr(m, "commit_authors", lambda forge, number: [])
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        rc = m.main(["--forge", "gitlab", "--change", "42", "--out", str(out)])
    assert rc == 1 and not out.exists()
    failure = json.loads(buf.getvalue())
    assert failure["seat"] == "unknown"
    assert "diff refs changed" in failure["error"]["message"]


def test_mr_details_without_base_start_refs_blocks_seat(tmp_path, monkeypatch, gitlab_origin):
    out = Path(tmp_path) / "ctx.json"
    monkeypatch.setattr(m, "change_diff", lambda *args, **kw: (
        SAMPLE, {"base": "b" * 40, "start": "c" * 40, "head": "a" * 40},
        {"number": 42, "title": "t", "description": "d", "source_branch": "feature"}))
    monkeypatch.setattr(m, "change_details", lambda *args: {"number": 42, "state": "opened", "open": True, "sha": "a" * 40,
                                       "author_id": 1, "author_username": "other"})
    monkeypatch.setattr(m, "current_user", lambda forge: {"id": 2, "username": "me"})
    monkeypatch.setattr(m, "commit_authors", lambda forge, number: [])
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        rc = m.main(["--forge", "gitlab", "--change", "42", "--out", str(out)])
    assert rc == 1 and not out.exists()
    failure = json.loads(buf.getvalue())
    assert failure["seat"] == "unknown"
    assert "diff refs changed" in failure["error"]["message"]


def test_branch_discovery_pins_requested_host_in_repo_url(monkeypatch):
    calls = []
    def fake_run(cmd, timeout=90):
        calls.append(cmd)
        return type("Result", (), {"returncode": 0, "stdout": '[{"iid": 42}]', "stderr": ""})()
    monkeypatch.setattr(m, "_run", fake_run)
    assert m.find_change_for_branch(_gitlab("gitlab.example", "group/project"), "feature") == 42
    assert calls[0][calls[0].index("-R") + 1] == "https://gitlab.example/group/project"


def test_local_scope_intent_detached_head(tmp_path):
    repo = Path(tmp_path) / "detached"
    repo.mkdir()
    _repo_git(repo, "init", "-q")
    (repo / "file.txt").write_text("old\n")
    _repo_git(repo, "add", ".")
    _repo_git(repo, "commit", "-qm", "base")
    _repo_git(repo, "checkout", "--detach", "HEAD")
    (repo / "file.txt").write_text("new\n")

    out = Path(tmp_path) / "detached.json"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert m.main(["--local", "--cwd", str(repo), "--out", str(out)]) == 0
    meta = json.loads(buf.getvalue())
    ctx = json.loads(out.read_text())
    assert ctx["source_branch"] is None
    assert ctx["scope_intent"] == {"guess": "", "basis": "none"}
    assert meta["source_branch"] is None
    assert meta["scope_intent"] == ctx["scope_intent"]


def _stub_branch_run(monkeypatch, stderr):
    def fake_run(cmd, timeout=90):
        return SimpleNamespace(returncode=128, stdout="", stderr=stderr)

    monkeypatch.setattr(m, "_run", fake_run)


def test_branch_git_failure_keeps_a_bounded_stderr_snippet(monkeypatch):
    _stub_branch_run(monkeypatch, "fatal: could not read from remote repository " + "x" * 1000)
    metadata = {}
    assert m.git_diff_branch("feature", "main", 3, ".", metadata) is None
    assert "git fetch of feature failed: fatal: could not read from remote" in metadata["error"]
    assert len(metadata["error"]) < 450


def test_local_git_failure_keeps_a_stderr_snippet(monkeypatch):
    _stub_branch_run(monkeypatch, "fatal: not a git repository")
    metadata = {}
    assert m.git_diff_local(3, ".", metadata) is None
    assert metadata["error"] == "git diff failed: fatal: not a git repository"


def test_branch_fallback_reason_names_the_forge_error(monkeypatch, tmp_path, gitlab_origin):
    out = tmp_path / "ctx.json"
    monkeypatch.setattr(m, "find_change_for_branch", lambda forge, branch: 42)

    def failing_change_diff(forge, number, cwd=".", metadata=None):
        metadata["error"] = "glab reported HTTP 404 for the merge request"
        return None

    def branch_diff(branch, target, context_lines, cwd=".", metadata=None):
        metadata["refs"] = {"base": "BASE", "start": "BASE", "head": "HEAD"}
        return SAMPLE

    monkeypatch.setattr(m, "change_diff", failing_change_diff)
    monkeypatch.setattr(m, "git_diff_branch", branch_diff)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        assert m.main(["--forge", "gitlab", "--branch", "feature", "--out", str(out)]) == 0
    assert "HTTP 404 for the merge request" in json.loads(stdout.getvalue())["fallback_reason"]


def test_branch_fallback_reason_carries_the_branch_lookup_cause(monkeypatch, tmp_path, gitlab_origin, capsys):
    def failing_lookup(forge, branch):
        forge.last_error = "glab: 401 Unauthorized"

    def branch_diff(branch, target, context_lines, cwd=".", metadata=None):
        metadata["refs"] = {"base": "BASE", "start": "BASE", "head": "HEAD"}
        return SAMPLE

    monkeypatch.setattr(m, "find_change_for_branch", failing_lookup)
    monkeypatch.setattr(m, "git_diff_branch", branch_diff)
    assert m.main(["--forge", "gitlab", "--branch", "feature", "--out", str(tmp_path / "ctx.json")]) == 0
    reason = json.loads(capsys.readouterr().out)["fallback_reason"]
    assert "no change request found" in reason and "glab: 401 Unauthorized" in reason


def test_branch_and_local_failure_messages_carry_the_underlying_causes(monkeypatch, tmp_path, gitlab_origin):
    def branch_diff(branch, target, context_lines, cwd=".", metadata=None):
        metadata["error"] = "git fetch of feature failed: fatal: Authentication failed"

    def local_diff(context_lines, cwd=".", metadata=None, excluded_path=None):
        metadata["error"] = "git diff failed: fatal: bad object"

    monkeypatch.setattr(m, "find_change_for_branch", lambda forge, branch: None)
    monkeypatch.setattr(m, "git_diff_branch", branch_diff)
    monkeypatch.setattr(m, "git_diff_local", local_diff)
    messages = []
    for selector in (["--forge", "gitlab", "--branch", "bad"], ["--local"]):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            assert m.main(selector + ["--out", str(tmp_path / "ctx.json")]) == 1
        messages.append(json.loads(stderr.getvalue())["error"]["message"])
    assert "Authentication failed" in messages[0] and "no change request found" in messages[0]
    assert "fatal: bad object" in messages[1]


GOOD_DETAILS = {"number": 42, "state": "opened", "open": True, "sha": "a" * 40,
                "base_sha": "b" * 40, "start_sha": "c" * 40, "author_id": 1, "author_username": "other",
                "source_branch": "feature", "target_branch": "main"}
GOOD_REFS = {"base": "b" * 40, "start": "c" * 40, "head": "a" * 40}
GOOD_VIEWER = {"id": 2, "username": "me"}


@pytest.fixture
def seat_gate(monkeypatch, tmp_path, gitlab_origin):
    """Factory that runs main against a stubbed GitLab change; the callable returns (rc, context path, stderr JSON or None, stdout text)."""
    def run(details=GOOD_DETAILS, viewer=GOOD_VIEWER, refs=GOOD_REFS, selector=("--change", "42"), metadata=None):
        out = tmp_path / "ctx.json"
        monkeypatch.setattr(m, "find_change_for_branch", lambda forge, branch: 42)

        def change_diff(forge, number, cwd=".", metadata_out=None):
            metadata_out.update(metadata or {})
            return SAMPLE, dict(refs), {"number": 42, "title": "t", "description": "d", "source_branch": "feature"}

        monkeypatch.setattr(m, "change_diff", change_diff)
        monkeypatch.setattr(m, "change_details", lambda forge, number: details)
        monkeypatch.setattr(m, "current_user", lambda forge: viewer or None)
        monkeypatch.setattr(m, "commit_authors", lambda forge, number: [])
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = m.main(["--forge", "gitlab", *selector, "--out", str(out)])
        error = json.loads(stderr.getvalue()) if stderr.getvalue().strip() else None
        return rc, out, error, stdout.getvalue()

    return run


@pytest.mark.parametrize("kwargs, message", [
    ({"details": None}, "could not resolve MR !42 metadata"),
    ({"details": {**GOOD_DETAILS, "open": False, "state": "closed"}}, "MR !42 is not open"),
    ({"details": {**GOOD_DETAILS, "number": 43}}, "metadata came back for a different change"),
    ({"details": {**GOOD_DETAILS, "source_branch": "other"}, "selector": ("--branch", "feature")},
     "source branch does not match"),
    ({"details": {**GOOD_DETAILS, "sha": "d" * 40}}, "head moved"),
    ({"details": {**GOOD_DETAILS, "start_sha": "e" * 40}}, "diff refs changed"),
    ({"refs": {**GOOD_REFS, "head": "not-a-sha"}}, "incomplete or malformed diff refs"),
    ({"viewer": {}}, "could not resolve the authenticated forge user"),
    ({"details": {**GOOD_DETAILS, "author_id": None, "author_username": None}},
     "author identity is incomplete"),
])
def test_seat_detection_gates_fail_closed(seat_gate, kwargs, message):
    rc, out, error, stdout = seat_gate(**kwargs)
    assert rc == 1 and not out.exists() and stdout == ""
    assert error["status"] == "error" and error["seat"] == "unknown"
    assert message in error["error"]["message"]


def test_unanchorable_files_are_copied_into_the_context(seat_gate):
    rc, out, _, _ = seat_gate(metadata={"unanchorable_files": ["big.json"]})
    assert rc == 0
    assert json.loads(out.read_text())["unanchorable_files"] == ["big.json"]


@pytest.mark.parametrize("details, viewer, message", [
    (None, GOOD_VIEWER, "could not resolve MR !42 metadata for seat detection: glab: 404 Not Found"),
    (GOOD_DETAILS, None, "could not resolve the authenticated forge user for seat detection: glab: 401"),
])
def test_seat_failures_report_the_adapter_cause(monkeypatch, tmp_path, gitlab_origin, details, viewer, message):
    class Forge:
        name, host, project = "gitlab", "x", "grp/proj"
        last_error = message.split("detection: ")[1]

        def change_label(self, number):
            return "MR !%s" % number

        def change_details(self, number):
            return details

        def current_user(self):
            return viewer

    monkeypatch.setattr(m, "make_forge", lambda *args, **kwargs: Forge())
    monkeypatch.setattr(m, "change_diff", lambda forge, number, cwd=".", metadata=None: (
        SAMPLE, dict(GOOD_REFS), {"number": 42, "title": "t", "description": "d", "source_branch": "feature"}))
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        assert m.main(["--forge", "gitlab", "--change", "42", "--out", str(tmp_path / "ctx.json")]) == 1
    assert json.loads(stderr.getvalue())["error"]["message"] == message


LINE_BREAKERS = ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029", "\r"]


@pytest.mark.parametrize("char", LINE_BREAKERS)
def test_diff_helpers_only_break_lines_on_newline(char):
    text = ("diff --git a/f.txt b/f.txt\n--- a/f.txt\n+++ b/f.txt\n"
            "@@ -1,2 +1,2 @@\n-a\n+b%s-c\n ctx\n" % char)

    assert m.split_diff_by_file(text) == {"f.txt": text.rstrip("\n")}
    assert m.count_changed_lines(text) == 2
    assert m.parse_unified_diff(text)[0]["hunks"] == ["@@ -1,2 +1,2 @@"]


def test_binary_metadata_check_ignores_content_split_on_exotic_breaks():
    section = ("diff --git a/f b/f\n@@ -1 +1 @@\n+x\u2028diff --git a/y b/y\n"
               "+z\u2028GIT binary patch\n")
    assert m._section_has_binary_metadata(section) is False


def test_late_run_maps_launch_failures_and_timeouts_to_a_failed_result(monkeypatch):
    def missing(cmd, timeout=90):
        raise FileNotFoundError("gh not found")

    def hung(cmd, timeout=90):
        raise m.subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(m, "_run", missing)
    result = m._late_run(["gh", "api", "x"])
    assert result.returncode == 127 and "gh not found" in result.stderr

    monkeypatch.setattr(m, "_run", hung)
    assert m._late_run(["gh", "api", "x"]).returncode == 127


def test_context_file_is_written_atomically_into_missing_parent_dirs(tmp_path, monkeypatch, gitlab_origin, capsys):
    out = tmp_path / "nested" / "dir" / "ctx.json"
    monkeypatch.setattr(m, "change_diff", lambda forge, number, cwd=".", metadata=None: (
        SAMPLE, dict(GOOD_REFS), {"number": 42, "title": "t", "description": "d", "source_branch": "feature"}))
    monkeypatch.setattr(m, "change_details", lambda forge, number: GOOD_DETAILS)
    monkeypatch.setattr(m, "current_user", lambda forge: GOOD_VIEWER)
    monkeypatch.setattr(m, "commit_authors", lambda forge, number: [])

    assert m.main(["--forge", "gitlab", "--change", "42", "--out", str(out)]) == 0
    capsys.readouterr()
    assert json.loads(out.read_text())["changed_files"] == ["foo.py", "bar/baz.txt"]
    assert [p.name for p in out.parent.iterdir()] == ["ctx.json"]


def test_reconstructed_rename_lines_quote_hostile_paths():
    change = {"old_path": "evil\ndiff --git a/innocent.py b/innocent.py", "new_path": "new.py",
              "renamed_file": True, "diff": "@@ -1 +1 @@\n-a\n+b\n"}
    diff_text = m.reconstruct_diff_from_changes([change])

    assert list(m.split_diff_by_file(diff_text)) == ["new.py"]
    assert 'rename from "evil\\ndiff --git a/innocent.py b/innocent.py"\nrename to new.py' in diff_text


@pytest.mark.parametrize("ref, expected", [
    ("refs/remotes/origin/main\n", "main"),
    ("refs/remotes/origin/release/2.0\n", "release/2.0"),
])
def test_detect_target_branch_keeps_slashes_in_the_branch_name(monkeypatch, ref, expected):
    monkeypatch.setattr(m, "_run", lambda cmd, timeout=90: SimpleNamespace(returncode=0, stdout=ref, stderr=""))
    assert m.detect_target_branch(".") == expected


def test_range_diff_failure_carries_git_stderr(monkeypatch):
    base, head = "a" * 40, "b" * 40

    def fake_run(cmd, timeout=90):
        if "diff" in cmd:
            return SimpleNamespace(returncode=128, stdout="", stderr="fatal: bad object " + head)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(m, "_run", fake_run)
    metadata = {}
    assert m._git_diff_range(base, head, ".", None, metadata) is None
    assert metadata["error"] == "git diff of %s..%s failed: fatal: bad object %s" % (base[:12], head[:12], head)


def test_range_fetch_failure_carries_git_stderr(monkeypatch):
    def fake_run(cmd, timeout=90):
        if "fetch" in cmd:
            return SimpleNamespace(returncode=128, stdout="", stderr="fatal: could not read from remote")
        return SimpleNamespace(returncode=1, stdout="", stderr="unknown revision")

    monkeypatch.setattr(m, "_run", fake_run)
    metadata = {}
    assert m._git_diff_range("a" * 40, "b" * 40, ".", None, metadata) is None
    assert metadata["error"] == "git fetch of %s failed: fatal: could not read from remote" % ("a" * 12)


def test_name_only_failure_carries_git_stderr(monkeypatch):
    monkeypatch.setattr(m, "_run", lambda cmd, timeout=90: SimpleNamespace(
        returncode=128, stdout="", stderr="fatal: ambiguous argument"))
    metadata = {}
    assert m._git_changed_files_range("a" * 40, "b" * 40, ".", metadata) is None
    assert "failed: fatal: ambiguous argument" in metadata["error"]


def test_branch_diff_failure_keeps_the_range_stderr(monkeypatch):
    def fake_run(cmd, timeout=90):
        if "rev-parse" in cmd:
            return SimpleNamespace(returncode=0, stdout=("c" if "origin/main^{commit}" in cmd[-1] else "d") * 40 + "\n", stderr="")
        if "merge-base" in cmd:
            return SimpleNamespace(returncode=0, stdout="a" * 40 + "\n", stderr="")
        if "diff" in cmd:
            return SimpleNamespace(returncode=128, stdout="", stderr="fatal: bad revision")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(m, "_run", fake_run)
    metadata = {}
    assert m.git_diff_branch("feature", "main", 3, ".", metadata) is None
    assert metadata["error"].endswith("failed: fatal: bad revision")


@pytest.fixture
def repo(tmp_path):
    root = Path(tmp_path) / "work"
    root.mkdir()
    _repo_git(root, "init", "-q")
    (root / "base.py").write_text("base\n")
    _repo_git(root, "add", ".")
    _repo_git(root, "commit", "-qm", "base")
    return root


def test_local_diff_from_a_subdirectory_reports_root_relative_untracked_files(repo):
    (repo / "sub").mkdir()
    (repo / "rootnew.py").write_text("one\n")
    (repo / "sub" / "subnew.py").write_text("two\n")
    metadata = {}
    diff_text = m.git_diff_local(3, str(repo / "sub"), metadata)
    assert diff_text is not None
    assert sorted(metadata["untracked_files"]) == ["rootnew.py", "sub/subnew.py"]
    assert "diff --git a/sub/subnew.py b/sub/subnew.py" in diff_text
    assert "diff --git a/rootnew.py b/rootnew.py" in diff_text


def test_local_diff_reports_an_untracked_nested_repo_as_unavailable(repo, tmp_path):
    nested = repo / "vendored"
    nested.mkdir()
    _repo_git(nested, "init", "-q")
    (nested / "x.py").write_text("x\n")
    (repo / "new.py").write_text("new\n")
    out = Path(tmp_path) / "ctx.json"
    assert m.main(["--local", "--cwd", str(repo), "--out", str(out)]) == 0
    ctx = json.loads(out.read_text())
    assert ctx["diff_unavailable"] == ["vendored/"]
    assert ctx["changed_files"] == ["new.py"]
    assert ctx["untracked_files"] == ["new.py"]


def test_per_file_recovery_failure_cause_is_recorded(monkeypatch):
    change = {"old_path": "big.py", "new_path": "big.py", "collapsed": True, "diff": ""}

    def fake_run(cmd, timeout=90):
        if "diff" in cmd:
            return SimpleNamespace(returncode=128, stdout="", stderr="fatal: bad object")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(m, "_run", fake_run)
    metadata = {}
    _, _, unavailable, _ = m._prepare_change_records(
        [change], {"base": "BASE", "head": "HEAD"}, metadata=metadata)
    assert unavailable == ["big.py"]
    assert metadata["diff_unavailable_cause"] == "git diff of big.py failed: fatal: bad object"


def _fix_commit(tmp_path, review, name="fix.txt", merge_side=False):
    """Push a follow-up commit to origin/feature and fetch it into `review`; return its sha."""
    seed = Path(tmp_path) / "seed"
    _repo_git(seed, "checkout", "-q", "feature")
    if merge_side:
        _repo_git(seed, "checkout", "-q", "-b", "side", "HEAD~1")
        (seed / "side.txt").write_text("side\n")
        _repo_git(seed, "add", ".")
        _repo_git(seed, "commit", "-qm", "side")
        _repo_git(seed, "checkout", "-q", "feature")
        _repo_git(seed, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    (seed / name).write_text("fix\n")
    _repo_git(seed, "add", ".")
    _repo_git(seed, "commit", "-qm", "fix")
    _repo_git(seed, "push", "-q", "origin", "feature")
    _repo_git(review, "fetch", "-q", "origin")
    return _repo_git(seed, "rev-parse", "HEAD")


def _run_main(argv, tmp_path):
    out = Path(tmp_path) / "since_ctx.json"
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = m.main(argv + ["--out", str(out)])
    return rc, out, stdout.getvalue(), stderr.getvalue()


def _branch_args(review, *extra):
    return ["--forge", "none", "--branch", "feature", "--target-branch", "main",
            "--cwd", str(review), *extra]


def test_branch_since_reviews_only_later_commits_and_keeps_full_refs(tmp_path):
    review, base, target, first_head = _branch_repo(tmp_path)
    new_head = _fix_commit(tmp_path, review)
    rc, full_out, _, _ = _run_main(_branch_args(review), tmp_path)
    assert rc == 0
    full = json.loads(full_out.read_text())
    rc, out, stdout, stderr = _run_main(_branch_args(review, "--since", first_head), tmp_path)
    assert rc == 0 and stderr == ""
    ctx = json.loads(out.read_text())
    assert full["changed_files"] == ["feature.txt", "fix.txt"]
    assert ctx["changed_files"] == ["fix.txt"]
    assert "fix.txt" in ctx["diff"] and "feature.txt" not in ctx["diff"]
    assert ctx["refs"] == full["refs"] and ctx["refs"]["head"] == new_head
    assert ctx["since"] == {"ref": first_head, "sha": first_head, "merge_commits": 0}
    assert json.loads(stdout)["since"] == ctx["since"]
    assert ctx["size"]["files"] == 1


def test_branch_since_resolves_symbolic_refs_and_records_the_ref_as_given(tmp_path):
    review, base, target, first_head = _branch_repo(tmp_path)
    _fix_commit(tmp_path, review)
    rc, out, _, _ = _run_main(_branch_args(review, "--since", "origin/feature~1"), tmp_path)
    assert rc == 0
    since = json.loads(out.read_text())["since"]
    assert since["ref"] == "origin/feature~1" and since["sha"] == first_head


def test_no_since_key_without_the_flag(tmp_path):
    review, *_ = _branch_repo(tmp_path)
    rc, out, stdout, _ = _run_main(_branch_args(review), tmp_path)
    assert rc == 0
    assert "since" not in json.loads(out.read_text())
    assert "since" not in json.loads(stdout)


def _since_error(rc, out, stderr):
    assert rc == 1 and not out.exists()
    return json.loads(stderr)["error"]["message"]


def test_branch_since_unknown_ref_fails_naming_the_ref(tmp_path):
    review, *_ = _branch_repo(tmp_path)
    rc, out, _, stderr = _run_main(_branch_args(review, "--since", "no-such-ref"), tmp_path)
    message = _since_error(rc, out, stderr)
    assert "no-such-ref" in message and "run without --since for a full review" in message


@pytest.mark.parametrize("value", ["", "   "])
def test_branch_since_empty_value_is_rejected_not_ignored(tmp_path, value):
    review, *_ = _branch_repo(tmp_path)
    rc, out, _, stderr = _run_main(_branch_args(review, "--since", value), tmp_path)
    message = _since_error(rc, out, stderr)
    assert "empty" in message and "run without --since for a full review" in message


def test_branch_since_not_an_ancestor_of_head_fails(tmp_path):
    review, base, target, head = _branch_repo(tmp_path)
    _repo_git(review, "checkout", "-q", "-b", "side", base)
    (review / "side.txt").write_text("side\n")
    _repo_git(review, "add", ".")
    _repo_git(review, "commit", "-qm", "side")
    side = _repo_git(review, "rev-parse", "HEAD")
    rc, out, _, stderr = _run_main(_branch_args(review, "--since", side), tmp_path)
    message = _since_error(rc, out, stderr)
    assert "not an ancestor" in message and "run without --since for a full review" in message


def test_branch_since_older_than_the_merge_base_fails(tmp_path):
    review, base, target, head = _branch_repo(tmp_path)
    rc, out, _, stderr = _run_main(_branch_args(review, "--since", base), tmp_path)
    message = _since_error(rc, out, stderr)
    assert "merge base" in message and "run without --since for a full review" in message


def test_branch_since_equal_to_head_fails(tmp_path):
    review, base, target, head = _branch_repo(tmp_path)
    rc, out, _, stderr = _run_main(_branch_args(review, "--since", head), tmp_path)
    message = _since_error(rc, out, stderr)
    assert "nothing to review" in message and "run without --since for a full review" in message


def test_branch_since_warns_and_counts_merge_commits_in_range(tmp_path):
    review, base, target, first_head = _branch_repo(tmp_path)
    _fix_commit(tmp_path, review, merge_side=True)
    rc, out, _, stderr = _run_main(_branch_args(review, "--since", first_head), tmp_path)
    assert rc == 0
    assert json.loads(out.read_text())["since"]["merge_commits"] == 1
    warnings = [line for line in stderr.splitlines() if line.strip()]
    assert len(warnings) == 1 and "1 merge commit" in warnings[0]


def _local_since_repo(repo):
    first = _repo_git(repo, "rev-parse", "HEAD")
    (repo / "committed.py").write_text("committed\n")
    _repo_git(repo, "add", ".")
    _repo_git(repo, "commit", "-qm", "committed")
    return first


def test_local_since_covers_committed_working_tree_and_untracked_changes(repo, tmp_path):
    since = _local_since_repo(repo)
    head = _repo_git(repo, "rev-parse", "HEAD")
    (repo / "base.py").write_text("base\nunstaged\n")
    (repo / "staged.py").write_text("staged\n")
    _repo_git(repo, "add", "staged.py")
    (repo / "untracked.py").write_text("untracked\n")
    rc, out, stdout, _ = _run_main(["--local", "--cwd", str(repo), "--since", since], tmp_path)
    assert rc == 0
    ctx = json.loads(out.read_text())
    assert sorted(ctx["changed_files"]) == ["base.py", "committed.py", "staged.py", "untracked.py"]
    assert ctx["untracked_files"] == ["untracked.py"]
    assert ctx["refs"] == {"base": head, "start": head, "head": head}
    assert ctx["since"] == {"ref": since, "sha": since, "merge_commits": 0}
    assert json.loads(stdout)["since"] == ctx["since"]


def test_local_since_at_head_reviews_the_dirty_tree(repo, tmp_path):
    head = _repo_git(repo, "rev-parse", "HEAD")
    (repo / "base.py").write_text("base\nedit\n")
    rc, out, _, _ = _run_main(["--local", "--cwd", str(repo), "--since", head], tmp_path)
    assert rc == 0
    assert json.loads(out.read_text())["changed_files"] == ["base.py"]


def test_local_since_at_head_with_a_clean_tree_fails(repo, tmp_path):
    head = _repo_git(repo, "rev-parse", "HEAD")
    rc, out, _, stderr = _run_main(["--local", "--cwd", str(repo), "--since", head], tmp_path)
    message = _since_error(rc, out, stderr)
    assert "nothing to review" in message and "run without --since for a full review" in message


def test_local_since_not_an_ancestor_of_head_fails(repo, tmp_path):
    _repo_git(repo, "checkout", "-q", "-b", "other")
    (repo / "other.py").write_text("other\n")
    _repo_git(repo, "add", ".")
    _repo_git(repo, "commit", "-qm", "other")
    other = _repo_git(repo, "rev-parse", "HEAD")
    _repo_git(repo, "checkout", "-q", "-")
    rc, out, _, stderr = _run_main(["--local", "--cwd", str(repo), "--since", other], tmp_path)
    assert "not an ancestor" in _since_error(rc, out, stderr)


def test_git_diff_local_since_uses_one_diff_against_the_commit(repo):
    since = _local_since_repo(repo)
    (repo / "base.py").write_text("base\nmore\n")
    metadata = {}
    diff = m.git_diff_local(3, str(repo), metadata, since=since)
    assert m.changed_files_from_diff(diff) == ["base.py", "committed.py"]
    assert metadata["changed_files"] == ["base.py", "committed.py"]


def test_change_since_substitutes_the_delta_after_the_identity_check(seat_gate, monkeypatch):
    since_sha = "9" * 40
    delta = ("diff --git a/fix.py b/fix.py\nnew file mode 100644\n--- /dev/null\n+++ b/fix.py\n"
             "@@ -0,0 +1 @@\n+fix\n")
    real_run = m._run
    calls = []

    def fake_run(cmd, timeout=90):
        tail = cmd[3:]
        if tail[:2] == ["rev-parse", "--verify"]:
            return SimpleNamespace(returncode=0, stdout=since_sha + "\n", stderr="")
        if tail[:2] == ["merge-base", "--is-ancestor"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if tail[:2] == ["rev-list", "--merges"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return real_run(cmd, timeout)

    def fake_range(base, head, cwd=".", context_lines=None, metadata=None):
        calls.append((base, head, context_lines))
        return delta

    monkeypatch.setattr(m, "_run", fake_run)
    monkeypatch.setattr(m, "_git_diff_range", fake_range)
    monkeypatch.setattr(m, "_git_changed_files_range",
                        lambda base, head, cwd=".", metadata=None: ["fix.py"])
    rc, out, _, _ = seat_gate(
        selector=("--change", "42", "--since", "feature~1"),
        metadata={"changed_files": ["foo.py", "bar/baz.txt"], "diff_unavailable": ["gone.py"],
                  "diff_unavailable_cause": "boom", "not_text_reviewable": ["img.png"],
                  "unanchorable_files": ["big.json"], "file_list_recovery": {"recovered_from": "git"}})
    assert rc == 0
    ctx = json.loads(out.read_text())
    assert calls == [(since_sha, GOOD_REFS["head"], 3)]
    assert ctx["refs"] == GOOD_REFS
    assert ctx["diff"] == delta and ctx["changed_files"] == ["fix.py"]
    assert ctx["since"] == {"ref": "feature~1", "sha": since_sha, "merge_commits": 0}
    assert ctx["diff_unavailable"] == [] and ctx["diff_unavailable_cause"] is None
    assert ctx["not_text_reviewable"] == [] and ctx["unanchorable_files"] == []
    assert ctx["file_list_recovery"] is None
    assert ctx["size"]["files"] == 1


def test_change_since_is_not_resolved_when_the_identity_check_fails(seat_gate, monkeypatch):
    def fail_run(cmd, timeout=90):
        raise AssertionError("since must not be resolved before the identity check passes")

    real_run = m._run
    monkeypatch.setattr(m, "_run", lambda cmd, timeout=90: (
        fail_run(cmd) if cmd[3:5] == ["rev-parse", "--verify"] else real_run(cmd, timeout)))
    rc, out, error, _ = seat_gate(details={**GOOD_DETAILS, "sha": "d" * 40},
                                  selector=("--change", "42", "--since", "x"))
    assert rc == 1 and "head moved" in error["error"]["message"]
