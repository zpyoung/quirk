import subprocess

import pytest

import forge


def _fake_run(ok_for):
    """Return a runner recording argv; `auth status` succeeds only for CLIs in `ok_for`."""
    calls = []

    def run(cmd, timeout=20):
        calls.append(cmd)
        code = 0 if cmd[0] in ok_for else 1
        return subprocess.CompletedProcess(cmd, code, "", "")

    return run, calls


@pytest.mark.parametrize("origin, name, host, project", [
    ("git@github.com:owner/repo.git", "github", "github.com", "owner/repo"),
    ("https://github.com/owner/repo", "github", "github.com", "owner/repo"),
    ("https://gitlab.com/group/sub/project.git", "gitlab", "gitlab.com", "group/sub/project"),
    ("ssh://git@gitlab.com/group/project.git", "gitlab", "gitlab.com", "group/project"),
])
def test_public_hosts_are_recognized_without_probing(origin, name, host, project):
    run, calls = _fake_run(ok_for=set())
    choice = forge.detect_forge(origin, run=run)
    assert (choice.name, choice.host, choice.project) == (name, host, project)
    assert calls == []


@pytest.mark.parametrize("ok_for, expected", [({"gh"}, "github"), ({"glab"}, "gitlab")])
def test_self_hosted_host_is_classified_by_the_one_authenticated_cli(ok_for, expected):
    run, calls = _fake_run(ok_for=ok_for)
    choice = forge.detect_forge("git@git.corp.example:team/app.git", run=run)
    assert choice.name == expected
    assert choice.host == "git.corp.example"
    assert choice.project == "team/app"
    # both probes target the remote's host explicitly
    assert ["gh", "auth", "status", "--hostname", "git.corp.example"] in calls
    assert ["glab", "auth", "status", "--hostname", "git.corp.example"] in calls


@pytest.mark.parametrize("ok_for", [{"gh", "glab"}, set()])
def test_ambiguous_or_unauthenticated_self_hosted_host_falls_back_to_none(ok_for):
    choice = forge.detect_forge("https://git.corp.example/team/app.git", run=_fake_run(ok_for)[0])
    assert choice.name == "none"
    assert "--forge" in choice.reason
    assert choice.host == "git.corp.example"


def test_override_wins_over_the_remote_and_skips_probing():
    run, calls = _fake_run(ok_for=set())
    choice = forge.detect_forge("git@github.com:owner/repo.git", override="gitlab", run=run)
    assert (choice.name, choice.host, choice.project) == ("gitlab", "github.com", "owner/repo")
    assert calls == []
    assert forge.detect_forge("git@github.com:o/r.git", override="none", run=run).name == "none"


@pytest.mark.parametrize("origin", [None, "", "   "])
def test_missing_origin_means_no_forge(origin):
    choice = forge.detect_forge(origin, run=_fake_run(ok_for={"gh"})[0])
    assert choice.name == "none"
    assert choice.host is None
    assert "origin" in choice.reason


def test_filesystem_remote_has_no_host():
    choice = forge.detect_forge("/srv/mirrors/app.git", run=_fake_run(ok_for={"gh"})[0])
    assert choice.name == "none"
    assert choice.host is None


def test_unknown_override_is_rejected():
    with pytest.raises(ValueError):
        forge.detect_forge("git@github.com:o/r.git", override="bitbucket")


def test_probe_launch_failure_counts_as_unauthenticated():
    def run(cmd, timeout=20):
        if cmd[0] == "gh":
            raise FileNotFoundError("gh")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    assert forge.detect_forge("git@git.corp.example:t/a.git", run=run).name == "gitlab"
