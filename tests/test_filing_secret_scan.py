from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_filing_module, run_filing_script


def _doc(**overrides) -> dict:
    """A minimal canonical document; tests overlay only the keys they care about."""
    base = {
        "schema_version": 1,
        "type": "bug",
        "headless": False,
        "depth": "read",
        "title": "clean title",
        "target": {"kind": "github", "repo": "acme/widgets", "writable": True, "third_party": "no", "visibility": "private"},
        "template": {"applied": False, "path": None, "fields": []},
        "fields": [],
        "verified_against": [],
        "disclosure_required": False,
    }
    base.update(overrides)
    return base


@pytest.fixture(scope="module")
def secret_scan():
    return load_filing_module("secret_scan")


# ---- positive fixtures, one per REGEX: pattern -------------------------


def test_aws_access_key_id_detected(secret_scan) -> None:
    doc = _doc(title="key is AKIA1234567890ABCDEF here")
    findings = secret_scan.scan(doc)
    assert any(f["pattern"] == "aws_access_key_id" for f in findings)


def test_aws_access_key_id_benign_negative(secret_scan) -> None:
    # too few trailing chars to complete the 16-char id -- looks similar, isn't one
    doc = _doc(title="key is AKIA1234EXAMPLE here")
    findings = secret_scan.scan(doc)
    assert not any(f["pattern"] == "aws_access_key_id" for f in findings)


def test_github_pat_detected(secret_scan) -> None:
    doc = _doc(title="token ghp_" + "a1B2c3D4" * 4 + "a1B2 here")
    findings = secret_scan.scan(doc)
    assert any(f["pattern"] == "github_pat" for f in findings)


def test_github_pat_benign_negative(secret_scan) -> None:
    # right prefix, far too short to be a real PAT
    doc = _doc(title="token ghp_shortvalue123 here")
    findings = secret_scan.scan(doc)
    assert not any(f["pattern"] == "github_pat" for f in findings)


def test_github_oauth_token_detected(secret_scan) -> None:
    doc = _doc(title="token gho_" + "a1B2c3D4" * 5 + " here")
    findings = secret_scan.scan(doc)
    assert any(f["pattern"] == "github_oauth_token" for f in findings)


def test_github_oauth_token_benign_negative(secret_scan) -> None:
    doc = _doc(title="token ghu_shortvalue123 here")
    findings = secret_scan.scan(doc)
    assert not any(f["pattern"] == "github_oauth_token" for f in findings)


def test_slack_token_detected(secret_scan) -> None:
    doc = _doc(title="slack xoxb-1234567890-abcdef here")
    findings = secret_scan.scan(doc)
    assert any(f["pattern"] == "slack_token" for f in findings)


def test_slack_token_benign_negative(secret_scan) -> None:
    doc = _doc(title="slack xoxb-123 here")
    findings = secret_scan.scan(doc)
    assert not any(f["pattern"] == "slack_token" for f in findings)


def test_jwt_detected(secret_scan) -> None:
    doc = _doc(title="jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dQw4w9WgXcQ_signature here")
    findings = secret_scan.scan(doc)
    assert any(f["pattern"] == "jwt" for f in findings)


def test_jwt_benign_negative(secret_scan) -> None:
    # only two dot-separated segments -- not a well-formed JWT shape
    doc = _doc(title="jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0 here")
    findings = secret_scan.scan(doc)
    assert not any(f["pattern"] == "jwt" for f in findings)


def test_private_key_block_detected(secret_scan) -> None:
    doc = _doc(title="-----BEGIN RSA PRIVATE KEY----- inline")
    findings = secret_scan.scan(doc)
    assert any(f["pattern"] == "private_key_block" for f in findings)


def test_private_key_block_benign_negative(secret_scan) -> None:
    doc = _doc(title="-----BEGIN CERTIFICATE----- inline")
    findings = secret_scan.scan(doc)
    assert not any(f["pattern"] == "private_key_block" for f in findings)


def test_connection_string_credential_detected(secret_scan) -> None:
    doc = _doc(title="conn postgres://dbuser:hunter2pass@dbhost/mydb")
    findings = secret_scan.scan(doc)
    assert any(f["pattern"] == "connection_string_credential" for f in findings)


def test_connection_string_credential_benign_negative(secret_scan) -> None:
    # userinfo present but no embedded password (no colon before the @)
    doc = _doc(title="conn postgres://dbuser@dbhost/mydb")
    findings = secret_scan.scan(doc)
    assert not any(f["pattern"] == "connection_string_credential" for f in findings)


def test_generic_assignment_detected(secret_scan) -> None:
    doc = _doc(title="config api_key: 'abcdef0123456789'")
    findings = secret_scan.scan(doc)
    assert any(f["pattern"] == "generic_assignment" for f in findings)


def test_generic_assignment_benign_negative(secret_scan) -> None:
    # right shape, value far too short to satisfy the 16-char minimum
    doc = _doc(title="config api_key: 'short'")
    findings = secret_scan.scan(doc)
    assert not any(f["pattern"] == "generic_assignment" for f in findings)


# ---- path labeling across locator shapes --------------------------------


def test_path_labeling_across_locator_shapes(secret_scan) -> None:
    doc = _doc(
        title="leaked AKIA1234567890ABCDEF in title",
        fields=[
            {"name": "current_behavior", "provenance": "observed", "source": "src", "value": "token ghp_" + "a1B2c3D4" * 4 + "a1B2"},
            {"name": "workaround", "provenance": "missing", "reason": "leaked slack xoxb-1234567890-abcdef in reason"},
        ],
        proposed_solution={
            "value": "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dQw4w9WgXcQ_signature",
            "attributed_to": "reporter",
        },
        verified_against=["conn postgres://dbuser:hunter2pass@dbhost/mydb"],
    )
    findings = secret_scan.scan(doc)
    paths = {f["path"] for f in findings}
    assert "title" in paths
    assert "fields[0].value" in paths
    assert "fields[1].reason" in paths
    assert "proposed_solution.value" in paths
    assert "verified_against[0]" in paths


def test_field_reason_and_value_do_not_cross_label(secret_scan) -> None:
    # a finding located in fields[0].value must never be mislabeled as fields[0].reason or vice versa
    doc = _doc(
        fields=[
            {"name": "current_behavior", "provenance": "observed", "source": "src", "value": "AKIA1234567890ABCDEF"},
        ],
    )
    findings = secret_scan.scan(doc)
    matching = [f for f in findings if f["pattern"] == "aws_access_key_id"]
    assert len(matching) == 1
    assert matching[0]["path"] == "fields[0].value"


# ---- redaction -----------------------------------------------------------


@pytest.mark.parametrize(
    "title,secret",
    [
        ("aws is AKIA1234567890ABCDEF here", "AKIA1234567890ABCDEF"),
        ("slack is xoxb-1234567890-abcdef here", "xoxb-1234567890-abcdef"),
        ("key api_key: 'abcdef0123456789'", "abcdef0123456789"),
    ],
)
def test_redacted_match_never_contains_the_full_secret(secret_scan, title, secret) -> None:
    doc = _doc(title=title)
    findings = secret_scan.scan(doc)
    assert findings, "expected at least one finding"
    for f in findings:
        assert secret not in f["match"]
        assert "…" in f["match"]


def test_redacted_match_keeps_first_and_last_four_chars(secret_scan) -> None:
    doc = _doc(title="aws is AKIA1234567890ABCDEF here")
    findings = secret_scan.scan(doc)
    match = next(f for f in findings if f["pattern"] == "aws_access_key_id")["match"]
    assert match == "AKIA…CDEF"


def test_span_locates_the_match_in_the_source_string(secret_scan) -> None:
    title = "aws is AKIA1234567890ABCDEF here"
    doc = _doc(title=title)
    findings = secret_scan.scan(doc)
    finding = next(f for f in findings if f["pattern"] == "aws_access_key_id")
    start, end = finding["span"]
    assert title[start:end] == "AKIA1234567890ABCDEF"


# ---- clean document -------------------------------------------------------


def test_clean_document_has_no_findings(secret_scan) -> None:
    doc = _doc()
    assert secret_scan.scan(doc) == []


# ---- CLI contract ----------------------------------------------------------


def test_cli_clean_document_exits_0(tmp_path: Path) -> None:
    doc = _doc()
    result = run_filing_script(
        "secret_scan.py", "--input", "-", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def test_cli_document_with_finding_exits_1(tmp_path: Path) -> None:
    doc = _doc(title="leaked AKIA1234567890ABCDEF here")
    result = run_filing_script(
        "secret_scan.py", "--input", "-", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any(f["pattern"] == "aws_access_key_id" for f in payload)


def test_cli_malformed_json_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "secret_scan.py", "--input", "-", cwd=tmp_path, stdin="{not json",
    )
    assert result.returncode == 2


def test_cli_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "secret_scan.py", "--input", str(tmp_path / "missing.json"), cwd=tmp_path,
    )
    assert result.returncode == 2


def test_cli_schema_version_too_new_exits_8(tmp_path: Path) -> None:
    doc = _doc(schema_version=999)
    result = run_filing_script(
        "secret_scan.py", "--input", "-", cwd=tmp_path, stdin=json.dumps(doc),
    )
    assert result.returncode == 8


def test_cli_reads_from_file_path(tmp_path: Path) -> None:
    doc = _doc(title="leaked AKIA1234567890ABCDEF here")
    input_path = tmp_path / "doc.json"
    input_path.write_text(json.dumps(doc))
    result = run_filing_script(
        "secret_scan.py", "--input", str(input_path), cwd=tmp_path,
    )
    assert result.returncode == 1
