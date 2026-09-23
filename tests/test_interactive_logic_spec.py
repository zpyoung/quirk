"""Behavioral contract for the interactive logic-spec renderer CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "writing-specs" / "interactive" / "render_spec.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "interactive"
SAMPLE = FIXTURES / "sample"
EXPORTS = SAMPLE / "exports"
PLACEHOLDER = '<script type="application/json" id="quirk-logic-spec-payload">null</script>'


def run_script(
    script: Path, *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return run_script(SCRIPT, *args, cwd=cwd)


def make_spec(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "sample"
    spec_dir.mkdir(parents=True)
    shutil.copy(SAMPLE / "logic.json", spec_dir / "logic.json")
    return spec_dir


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PayloadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_payload = False
        self.payload: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "quirk-logic-spec-payload":
            self.in_payload = True

    def handle_data(self, data: str) -> None:
        if self.in_payload:
            self.payload.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_payload:
            self.in_payload = False


def extract_payload(html: str) -> tuple[str, Dict[str, Any]]:
    parser = PayloadParser()
    parser.feed(html)
    raw = "".join(parser.payload)
    return raw, json.loads(raw)


def export_fixture(name: str) -> Path:
    return EXPORTS / (name + ".json")


def test_validate_accepts_complete_fixture_and_reports_invalid_variants(tmp_path: Path) -> None:
    result = run_cli("validate", str(SAMPLE))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""

    expected_pointers = {
        "missing-key": "/title:",
        "bad-enum": "/requirements/0/provenance:",
        "dangling-dependson": "/requirements/0/dependsOn/0:",
        "duplicate-id": "/assumptions/0/id:",
    }
    for name, pointer in expected_pointers.items():
        invalid_spec = tmp_path / name
        invalid_spec.mkdir()
        shutil.copy(FIXTURES / "invalid" / (name + ".json"), invalid_spec / "logic.json")
        result = run_cli("validate", str(invalid_spec))
        assert result.returncode == 1
        assert pointer in result.stderr
        assert result.stdout == ""


def test_validate_rejects_object_prototype_names_as_ids(tmp_path: Path) -> None:
    for index, unsafe_id in enumerate(("__proto__", "constructor", "toString")):
        spec_dir = tmp_path / str(index)
        spec_dir.mkdir()
        logic = load_json(SAMPLE / "logic.json")
        logic["requirements"][0]["id"] = unsafe_id
        save_json(spec_dir / "logic.json", logic)
        result = run_cli("validate", str(spec_dir))
        assert result.returncode == 1
        assert "/requirements/0/id:" in result.stderr
        assert "reserved JavaScript object property" in result.stderr


def test_render_embeds_safe_deterministic_payload_and_generates_markdown(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    first_html = (spec_dir / "review.html").read_text(encoding="utf-8")
    first_markdown = (spec_dir / "logic.md").read_text(encoding="utf-8")
    ignored = (spec_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert len(result.stdout.strip()) == 12
    int(result.stdout.strip(), 16)
    assert first_html.count(PLACEHOLDER) == 0
    assert ignored.count("review.html") == 1
    assert ignored.count("*-decisions-*.json") == 1
    raw, payload = extract_payload(first_html)
    assert "<" not in raw
    assert payload["slug"] == "sample"
    assert payload["spec"]["title"] == "Local archive workflow"
    assert payload["renderId"] == result.stdout.strip()
    assert payload["priorDecisions"] is None

    for heading in (
        "## Status & amendments",
        "## Purpose",
        "## Conceptual model",
        "## Data flow",
        "## Behavior & scenarios",
        "## Requirements",
        "## Assumptions & blind spots",
        "## Decisions Locked",
        "## Industry Insights",
        "## Scope & non-goals",
        "## Deferred Ideas",
        "## Glossary",
    ):
        assert heading in first_markdown
    assert first_markdown.startswith("<!-- generated from logic.json by render_spec.py — do not edit -->\n")
    assert "[tech-spec] Add archive signing" in first_markdown
    assert "### Conditionally in scope" in first_markdown
    assert "Research finding" in first_markdown
    assert "destination permission check can be performed before writing" in first_markdown

    repeated = run_cli("render", str(spec_dir))
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout == result.stdout
    assert (spec_dir / "review.html").read_text(encoding="utf-8") == first_html
    assert (spec_dir / "logic.md").read_text(encoding="utf-8") == first_markdown
    assert (spec_dir / ".gitignore").read_text(encoding="utf-8").splitlines() == ignored


def test_relative_dot_spec_dir_uses_folder_name_as_slug(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    assert run_cli("render", ".", cwd=spec_dir).returncode == 0
    payload = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]
    assert payload["slug"] == "sample"
    # the signed fixture targets the unmodified sample, so a correct slug makes it current
    check = run_cli("check-export", ".", str(export_fixture("signed")), cwd=spec_dir)
    assert check.returncode == 0, check.stderr


def test_render_escapes_script_content_and_hashes_only_changed_item(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    assert run_cli("render", str(spec_dir)).returncode == 0
    before = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]

    logic = load_json(spec_dir / "logic.json")
    logic["requirements"][0]["detail"] = 'Literal adversarial content </script><script>alert("x")</script>.'
    save_json(spec_dir / "logic.json", logic)
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    html = (spec_dir / "review.html").read_text(encoding="utf-8")
    raw, after = extract_payload(html)
    assert "<" not in raw
    assert after["spec"]["requirements"][0]["detail"] == logic["requirements"][0]["detail"]
    assert html.count('<script type="application/json" id="quirk-logic-spec-payload">') == 1
    assert after["renderId"] != before["renderId"]
    for item_id, old_hash in before["itemHashes"].items():
        if item_id == "REQ-01":
            assert after["itemHashes"][item_id] != old_hash
        else:
            assert after["itemHashes"][item_id] == old_hash


def test_render_embeds_stale_prior_without_rejecting_it(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    result = run_cli("render", str(spec_dir), "--prior", str(export_fixture("stale")))
    assert result.returncode == 0, result.stderr
    payload = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))[1]
    assert payload["priorDecisions"]["renderId"] == "000000000000"
    html_before = (spec_dir / "review.html").read_text(encoding="utf-8")
    wrong_slug = load_json(export_fixture("stale"))
    wrong_slug["slug"] = "other-spec"
    wrong_slug_path = tmp_path / "wrong-slug-prior.json"
    save_json(wrong_slug_path, wrong_slug)
    rejected = run_cli("render", str(spec_dir), "--prior", str(wrong_slug_path))
    assert rejected.returncode == 3
    assert "different spec" in rejected.stderr
    assert (spec_dir / "review.html").read_text(encoding="utf-8") == html_before


def test_find_export_prefers_current_render_then_newest_across_folders(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    old_local = load_json(export_fixture("signed"))
    old_local["exportedAt"] = "2026-09-20T09:00:00Z"
    newest_download = load_json(export_fixture("signed"))
    newest_download["exportedAt"] = "2026-09-22T09:00:00Z"
    newer_stale = load_json(export_fixture("stale"))
    newer_stale["exportedAt"] = "2026-09-23T09:00:00Z"
    save_json(spec_dir / "local-old.json", old_local)
    save_json(downloads / "download-newest.json", newest_download)
    save_json(downloads / "stale-newer.json", newer_stale)
    (spec_dir / "broken.json").write_text("{invalid", encoding="utf-8")
    # mtime disagrees with exportedAt so ordering by mtime would pick the wrong file
    os.utime(spec_dir / "local-old.json", (9_999_999_999, 9_999_999_999))

    result = run_cli("find-export", str(spec_dir), "--downloads", str(downloads))
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == (downloads / "download-newest.json").resolve()
    assert "broken.json" not in result.stderr

    stale_only = tmp_path / "stale-only" / "sample"
    stale_only.mkdir(parents=True)
    shutil.copy(SAMPLE / "logic.json", stale_only / "logic.json")
    older_stale = load_json(export_fixture("stale"))
    older_stale["exportedAt"] = "2026-09-21T09:00:00Z"
    save_json(stale_only / "stale-older.json", older_stale)
    fallback = run_cli("find-export", str(stale_only), "--downloads", str(downloads))
    assert fallback.returncode == 0, fallback.stderr
    assert Path(fallback.stdout.strip()) == (downloads / "download-newest.json").resolve()
    no_current = tmp_path / "no-current"
    no_current.mkdir()
    only_stale = run_cli("find-export", str(stale_only), "--downloads", str(no_current))
    assert only_stale.returncode == 0, only_stale.stderr
    assert Path(only_stale.stdout.strip()) == (stale_only / "stale-older.json").resolve()

    (spec_dir / "local-old.json").unlink()
    missing = run_cli("find-export", str(spec_dir), "--downloads", str(tmp_path / "empty-downloads"))
    assert missing.returncode == 5
    assert "no matching" in missing.stderr


def test_check_export_distinguishes_current_stale_wrong_slug_and_invalid(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    current = run_cli("check-export", str(spec_dir), str(export_fixture("signed")))
    assert current.returncode == 0
    assert current.stdout.strip() == "signed"

    for name in ("stale", "wrong-slug"):
        result = run_cli("check-export", str(spec_dir), str(export_fixture(name)))
        assert result.returncode == 3
        assert result.stdout.strip() == "signed"

    malformed = run_cli("check-export", str(spec_dir), str(export_fixture("malformed")))
    assert malformed.returncode == 1
    assert "/state:" in malformed.stderr
    invalid_choice = load_json(export_fixture("signed"))
    invalid_choice["state"]["scenarioOutcomes"]["SC-01"]["choice"] = "alt-9"
    invalid_path = tmp_path / "invalid-choice.json"
    save_json(invalid_path, invalid_choice)
    bad_choice = run_cli("check-export", str(spec_dir), str(invalid_path))
    assert bad_choice.returncode == 1
    assert "alternative index is out of range" in bad_choice.stderr
    blank_custom = load_json(export_fixture("signed"))
    blank_custom["state"]["scenarioOutcomes"]["SC-01"] = {"choice": "custom", "custom": "  "}
    blank_custom_path = tmp_path / "blank-custom.json"
    save_json(blank_custom_path, blank_custom)
    rejected_custom = run_cli("check-export", str(spec_dir), str(blank_custom_path))
    assert rejected_custom.returncode == 1
    assert "custom scenario outcome must not be blank" in rejected_custom.stderr


def test_fold_applies_every_decision_and_is_stale_after_first_fold(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path)
    result = run_cli("fold", str(spec_dir), str(export_fixture("signed")))
    assert result.returncode == 0, result.stderr
    logic = load_json(spec_dir / "logic.json")
    requirements = {item["id"]: item for item in logic["requirements"]}
    assert requirements["REQ-01"]["scope"] == "in"
    assert requirements["REQ-01"]["condition"] == "under-10"
    assert requirements["REQ-01"]["reviewReason"] == "Keep the archive within the agreed small implementation."
    assert requirements["REQ-02"]["scope"] == "out"
    assert requirements["REQ-02"]["reviewReason"] == "Automated source discovery is not wanted."
    assert logic["assumptions"][0]["ruling"] == "verify-first"
    assert logic["assumptions"][0]["rulingNote"] == "Check permissions before writing."
    assert logic["blindSpots"][0]["acceptance"] == "I accept the destination permission risk after preflight."
    assert logic["scenarios"][0]["then"] == "Write a compact index."
    assert logic["signoff"] == {"signedAt": "2026-09-23T16:00:00Z", "renderId": load_json(export_fixture("signed"))["renderId"]}
    assert logic["status"] == "Approved"
    assert (spec_dir / "logic.md").is_file()
    assert (spec_dir / "review.html").is_file()

    again = run_cli("fold", str(spec_dir), str(export_fixture("signed")))
    assert again.returncode == 3


def test_fold_requires_and_persists_reason_for_conditional_limit_changes(tmp_path: Path) -> None:
    for include_reason in (False, True):
        case = "with-reason" if include_reason else "without-reason"
        spec_dir = make_spec(tmp_path / case)
        export = load_json(export_fixture("signed"))
        export["state"]["conditions"]["REQ-03"] = "under-10"
        reason = "Keep the optional compression limit narrow."
        if include_reason:
            export["state"]["moveReasons"]["REQ-03"] = reason
        export_path = tmp_path / (case + ".json")
        save_json(export_path, export)

        result = run_cli("fold", str(spec_dir), str(export_path))
        if include_reason:
            assert result.returncode == 0, result.stderr
            folded = {item["id"]: item for item in load_json(spec_dir / "logic.json")["requirements"]}
            assert folded["REQ-03"]["condition"] == "under-10"
            assert folded["REQ-03"]["reviewReason"] == reason
        else:
            assert result.returncode == 4
            assert "gate move-reasons" in result.stderr
            assert load_json(spec_dir / "logic.json")["status"] == "Draft"


def test_fold_tech_spec_status_unsigned_and_gate_failures(tmp_path: Path) -> None:
    approved_dir = make_spec(tmp_path / "approved")
    result = run_cli("fold", str(approved_dir), str(export_fixture("signed")), "--tech-spec-requested")
    assert result.returncode == 0, result.stderr
    assert load_json(approved_dir / "logic.json")["status"] == "Approved — Tech spec: requested"

    unsigned_dir = make_spec(tmp_path / "unsigned")
    unsigned = run_cli("fold", str(unsigned_dir), str(export_fixture("unsigned")))
    assert unsigned.returncode == 4
    assert "unsigned" in unsigned.stderr

    gate_dir = make_spec(tmp_path / "gate")
    gate_export = load_json(export_fixture("signed"))
    gate_export["state"]["assumptions"]["ASM-01"]["ruling"] = "verify-first"
    gate_export["state"]["assumptions"]["ASM-01"]["note"] = ""
    gate_path = tmp_path / "gate-fail.json"
    save_json(gate_path, gate_export)
    failed = run_cli("fold", str(gate_dir), str(gate_path))
    assert failed.returncode == 4
    assert "gate assumptions" in failed.stderr


def test_fold_rechecks_each_python_authoritative_gate(tmp_path: Path) -> None:
    cases = (
        ("queue", lambda export: export["state"]["placements"].pop("REQ-01")),
        ("assumptions", lambda export: export["state"]["assumptions"]["ASM-01"].update(note="")),
        ("blind-spots", lambda export: export["state"]["blindSpots"]["BS-01"].update(accepted=False)),
        ("scenarios", lambda export: export["state"]["scenarioApproved"].update({"SC-01": False})),
        ("move-reasons", lambda export: export["state"]["moveReasons"].pop("REQ-01")),
        (
            "scope-warnings",
            lambda export: (
                export["state"]["placements"].update({"OOS-01": "in"}),
                export["state"]["moveReasons"].update({"OOS-01": "Reviewer includes this item."}),
            ),
        ),
    )
    for gate, mutate in cases:
        spec_dir = make_spec(tmp_path / gate)
        export = load_json(export_fixture("signed"))
        mutate(export)
        export_path = tmp_path / (gate + ".json")
        save_json(export_path, export)
        result = run_cli("fold", str(spec_dir), str(export_path))
        assert result.returncode == 4
        assert "gate " + gate in result.stderr


def test_fold_refuses_stale_and_wrong_slug_exports(tmp_path: Path) -> None:
    for name in ("stale", "wrong-slug"):
        spec_dir = make_spec(tmp_path / name)
        result = run_cli("fold", str(spec_dir), str(export_fixture(name)))
        assert result.returncode == 3
        assert "stale" in result.stderr
        assert load_json(spec_dir / "logic.json")["status"] == "Draft"


def test_fold_prepares_template_before_writing_any_artifacts(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path / "template-failure")
    tool_dir = tmp_path / "isolated-tool"
    tool_dir.mkdir()
    script = tool_dir / "render_spec.py"
    shutil.copy(SCRIPT, script)
    (tool_dir / "review-template.html").write_text("missing payload marker", encoding="utf-8")

    result = run_script(script, "fold", str(spec_dir), str(export_fixture("signed")))
    assert result.returncode == 1
    assert load_json(spec_dir / "logic.json")["status"] == "Draft"
    assert not (spec_dir / "review.html").exists()
    assert not (spec_dir / "logic.md").exists()


def test_fold_preflights_output_paths_before_approving_source(tmp_path: Path) -> None:
    spec_dir = make_spec(tmp_path / "blocked-output")
    (spec_dir / "logic.md").mkdir()

    result = run_cli("fold", str(spec_dir), str(export_fixture("signed")))
    assert result.returncode == 1
    assert load_json(spec_dir / "logic.json")["status"] == "Draft"
    assert not (spec_dir / "review.html").exists()
