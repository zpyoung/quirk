from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from .conftest import load_filing_module, run_filing_script

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "filing-requests" / "canonical"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture(scope="module")
def markdown_render():
    return load_filing_module("markdown_render")


def _gh_stub(tmp_path: Path, *, marker: Path, exit_code: int = 0, stdout: str = "", stderr: str = "") -> Path:
    """A `gh` stub that records invocation (by touching `marker`) and echoes canned output.

    Used both to assert the argv/exit-code shape of a real `--execute` call and, via the
    marker file, to prove a gated path never invoked `gh` at all.
    """
    stub = tmp_path / "gh-stub.py"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"open({str(marker)!r}, 'w').close()\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({exit_code})\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return stub


def _argv_echo_stub(tmp_path: Path, *, marker: Path) -> Path:
    """A `gh` stub that echoes its own argv (as JSON) to stdout, for shape assertions."""
    stub = tmp_path / "gh-stub.py"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(marker)!r}, 'w').close()\n"
        "sys.stdout.write(json.dumps(sys.argv[1:]))\n"
        "sys.exit(0)\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return stub


# ---- dry run ---------------------------------------------------------------


def test_dry_run_exits_0_with_expected_shape(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GH_BIN", "gh")
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["repo"] == "acme/reports"
    assert payload["title"] == doc["title"]
    assert payload["would_execute"] == [
        "gh", "issue", "create",
        "--repo", "acme/reports",
        "--title", doc["title"],
        "--body", payload["body_preview"],
    ]


def test_dry_run_would_execute_uses_gh_bin_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GH_BIN", "/opt/tools/gh")
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["would_execute"][0] == "/opt/tools/gh"


def test_dry_run_never_invokes_gh(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker)
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists()


def test_dry_run_body_preview_is_byte_identical_to_markdown_render(
    tmp_path: Path, monkeypatch, markdown_render,
) -> None:
    # the single most important constraint: the filed/previewed body must never diverge
    # from markdown_render.render()'s own output for the same document.
    monkeypatch.setenv("GH_BIN", "gh")
    doc = _load_fixture("valid-feature.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", doc["target"]["repo"],
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["body_preview"] == markdown_render.render(doc)


# ---- --execute: success -----------------------------------------------------


def test_execute_success_returns_gh_stdout_and_exit_0(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker, exit_code=0, stdout="https://github.com/acme/reports/issues/42\n")
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "https://github.com/acme/reports/issues/42\n"
    assert marker.exists()


def test_execute_invokes_gh_with_contract_argv_shape(
    tmp_path: Path, monkeypatch, markdown_render,
) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _argv_echo_stub(tmp_path, marker=marker)
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    seen_argv = json.loads(result.stdout)
    assert seen_argv == [
        "issue", "create",
        "--repo", "acme/reports",
        "--title", doc["title"],
        "--body", markdown_render.render(doc),
    ]


# ---- --execute: gh failure ---------------------------------------------------


def test_execute_gh_nonzero_exit_maps_to_5_and_forwards_stderr(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker, exit_code=17, stderr="gh: rate limited\n")
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 5
    assert "gh: rate limited" in result.stderr
    assert marker.exists()  # gh *was* invoked here -- it just failed


def test_execute_gh_binary_not_found_exits_5(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GH_BIN", str(tmp_path / "no-such-gh-binary"))
    doc = _load_fixture("valid-bug.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 5


# ---- --execute: defense-in-depth gates, each proven independently ----------


def test_execute_refuses_halted_document_exit_3_gh_never_invoked(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker)
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("halted-feature.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/app", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    assert not marker.exists()


def test_execute_refuses_document_with_secret_exit_1_gh_never_invoked(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker)
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("valid-bug.json")
    # inject a secret into an otherwise-valid, for-emission-ready document
    doc["fields"][3]["value"] += " AKIA1234567890ABCDEF"
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 1
    assert not marker.exists()
    payload = json.loads(result.stdout)
    assert any(f["pattern"] == "aws_access_key_id" for f in payload)


def test_execute_refuses_headless_document_exit_3_gh_never_invoked(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker)
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("headless.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    assert not marker.exists()


# ---- unsupported target.kind -------------------------------------------------


def test_unsupported_target_kind_exits_6(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker)
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("valid-bug.json")
    doc["target"]["kind"] = "gitlab"
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 6
    assert not marker.exists()


# ---- schema_version guard ----------------------------------------------------


def test_schema_version_too_new_exits_8(tmp_path: Path) -> None:
    doc = _load_fixture("valid-bug.json")
    doc["schema_version"] = 999
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 8


# ---- usage errors -------------------------------------------------------------


def test_malformed_json_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "acme/reports",
        cwd=tmp_path, stdin="{not json",
    )
    assert result.returncode == 2


def test_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "github_file.py", "--input", str(tmp_path / "missing.json"), "--repo", "acme/reports",
        cwd=tmp_path,
    )
    assert result.returncode == 2


# ---- wave-3 checkpoint regressions ---------------------------------------


def test_repo_mismatching_target_repo_exits_2_and_never_renders(tmp_path: Path, monkeypatch) -> None:
    # the body's disclosure footer is derived from *this document's* target, so filing it
    # at another repo can send a disclosure-free body to a public or third-party tracker.
    monkeypatch.setenv("GH_BIN", "gh")
    doc = _load_fixture("valid-feature.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "someone-else/fork",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 2
    assert "target.repo" in result.stderr
    assert result.stdout == ""


def test_execute_repo_mismatching_target_repo_never_invokes_gh(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker)
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("valid-feature.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", "someone-else/fork", "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 2
    assert not marker.exists()


def test_structurally_invalid_document_exits_3_rather_than_crashing(tmp_path: Path, monkeypatch) -> None:
    # render() assumes a validated document and indexes keys directly -- rendering before
    # validating turns a missing `title` into a KeyError traceback instead of exit 3.
    monkeypatch.setenv("GH_BIN", "gh")
    doc = _load_fixture("valid-feature.json")
    del doc["title"]
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", doc["target"]["repo"], "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3, result.stderr
    assert "Traceback" not in result.stderr
    assert json.loads(result.stdout)["valid"] is False


def test_dry_run_of_a_structurally_invalid_document_exits_3(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GH_BIN", "gh")
    doc = _load_fixture("valid-feature.json")
    del doc["title"]
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", doc["target"]["repo"],
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3, result.stderr
    assert "Traceback" not in result.stderr


def test_dry_run_of_a_halted_document_is_refused_before_rendering(tmp_path: Path, monkeypatch) -> None:
    # "a halted or core-incomplete document is never rendered, including for the on-screen
    # draft preview" -- the dry run is that preview, so it is gated too.
    monkeypatch.setenv("GH_BIN", "gh")
    doc = _load_fixture("halted-feature.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", doc["target"]["repo"],
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["halted"] is not None
    assert "body_preview" not in payload


def test_execute_refuses_a_document_carrying_a_stored_halt(tmp_path: Path, monkeypatch) -> None:
    # the halted-feature fixture is *computed* halted; this one carries the gate's own saved
    # output, which is what a resumed session hands back
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker, exit_code=0, stdout="https://example.invalid/filed\n")
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("resumed-halted-feature.json")
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", doc["target"]["repo"], "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    assert not marker.exists()
    assert json.loads(result.stdout)["halted"]["field"] == "acceptance_criteria"


def test_execute_refuses_a_headless_feature_before_reaching_the_headless_gate(
    tmp_path: Path, monkeypatch,
) -> None:
    marker = tmp_path / "gh-invoked.marker"
    stub = _gh_stub(tmp_path, marker=marker)
    monkeypatch.setenv("GH_BIN", str(stub))
    doc = _load_fixture("valid-feature.json")
    doc["headless"] = True
    result = run_filing_script(
        "github_file.py", "--input", "-", "--repo", doc["target"]["repo"], "--execute",
        cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 3
    assert not marker.exists()
