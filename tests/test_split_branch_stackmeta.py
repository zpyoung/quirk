from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "split-branch" / "scripts" / "stackmeta.sh"
SHA = "a" * 40


def run_stackmeta(*args: str, body: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        input=body,
        capture_output=True,
        text=True,
        check=False,
    )


def block(parent: str = "main", sha: str = SHA, position: str = "3/5") -> str:
    return (
        "<!-- split-branch:stack -->\n"
        f"parent: {parent}\n"
        f"base-sha: {sha}\n"
        f"position: {position}\n"
        "<!-- /split-branch:stack -->\n"
    )


def test_emit_round_trips_all_fields() -> None:
    emitted = run_stackmeta("emit", "main", SHA, "3", "5")
    assert emitted.returncode == 0, emitted.stderr
    assert emitted.stdout == block()

    for field, expected in (
        ("parent", "main"),
        ("base-sha", SHA),
        ("position", "3/5"),
    ):
        parsed = run_stackmeta("parse", field, body=emitted.stdout)
        assert parsed.returncode == 0, parsed.stderr
        assert parsed.stdout == f"{expected}\n"


def test_upsert_appends_then_replaces_one_block_and_is_idempotent() -> None:
    prose = "Title\n\nBody prose without metadata.\n"
    appended = run_stackmeta("upsert", "main", SHA, "3", "5", body=prose)
    assert appended.returncode == 0, appended.stderr
    assert appended.stdout == prose + "\n" + block()

    # Exercise replacement with byte-sensitive prose on both sides. In
    # particular, this catches implementations that accidentally drop the tail.
    prefix = "Title with trailing spaces  \n\n\tBefore metadata\n"
    suffix = "After metadata\t  \nfinal line without newline"
    existing = prefix + block() + suffix
    new_sha = "b" * 40
    expected = prefix + block("trunk", new_sha, "4/6") + suffix
    replaced = run_stackmeta("upsert", "trunk", new_sha, "4", "6", body=existing)
    assert replaced.returncode == 0, replaced.stderr
    assert replaced.stdout == expected
    assert replaced.stdout.count("<!-- split-branch:stack -->") == 1

    repeated = run_stackmeta("upsert", "trunk", new_sha, "4", "6", body=replaced.stdout)
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout == expected


def test_parse_rejects_two_blocks() -> None:
    result = run_stackmeta("parse", "parent", body=block() + "\n" + block("other"))
    assert result.returncode == 4


def test_parse_rejects_malformed_sha() -> None:
    result = run_stackmeta("parse", "base-sha", body=block(sha="a" * 39))
    assert result.returncode == 3


def test_parse_rejects_missing_required_field() -> None:
    malformed = block().replace(f"base-sha: {SHA}\n", "")
    result = run_stackmeta("parse", "parent", body=malformed)
    assert result.returncode == 3


def test_orphan_and_excess_closing_markers_are_malformed() -> None:
    closing = "<!-- /split-branch:stack -->\n"
    for body in (closing, closing + closing, block() + closing):
        result = run_stackmeta("parse", "parent", body=body)
        assert result.returncode == 3


def test_parse_reports_no_block() -> None:
    result = run_stackmeta("parse", "parent", body="Ordinary PR body\n")
    assert result.returncode == 2


def test_parse_rejects_unknown_field() -> None:
    result = run_stackmeta("parse", "bogus-field", body=block())
    assert result.returncode == 5


def test_emit_and_upsert_reject_invalid_sha_arguments() -> None:
    for command in ("emit", "upsert"):
        result = run_stackmeta(command, "main", "a" * 39, "3", "5", body="Prose\n")
        assert result.returncode == 5
        assert result.stdout == ""


def test_unknown_subcommand_is_bad_arguments() -> None:
    assert run_stackmeta("unknown").returncode == 5


def test_cli_operations_reject_wrong_arity() -> None:
    cases = (
        ("emit",),
        ("emit", "main", SHA, "3", "5", "extra"),
        ("parse",),
        ("parse", "parent", "extra"),
        ("upsert",),
        ("upsert", "main", SHA, "3", "5", "extra"),
    )
    for args in cases:
        assert run_stackmeta(*args, body=block()).returncode == 5
