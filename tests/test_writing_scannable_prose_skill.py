from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "writing-scannable-prose" / "SKILL.md"
WORKED_EXAMPLES_PATH = REPO_ROOT / "skills" / "writing-scannable-prose" / "worked-examples.md"
EVIDENCE_AND_LIMITS_PATH = REPO_ROOT / "skills" / "writing-scannable-prose" / "evidence-and-limits.md"

ALL_CHECK_IDS = [
    "F1", "F2", "F3", "F4",
    "A1", "A2", "A3", "A4", "A5", "A6",
    "B1", "B2", "B3", "B4", "B5",
    "C1", "C2", "C3", "C4",
    "D1", "D2", "D3", "D4", "D5", "D6",
    "E1", "E2", "E3",
]


def test_skill_has_valid_frontmatter() -> None:
    """Test 1: YAML frontmatter parse — name and description fields both present"""
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert fm is not None, "SKILL.md missing YAML frontmatter"
    fm_body = fm.group(1)
    assert re.search(r"^name:\s*.+$", fm_body, re.MULTILINE), "frontmatter missing 'name'"
    assert re.search(r"^description:\s*.+$", fm_body, re.MULTILINE), "frontmatter missing 'description'"


def test_skill_name_matches_directory() -> None:
    """Test 2: frontmatter name equals the parent directory name"""
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert fm is not None
    fm_body = fm.group(1)
    name_match = re.search(r"^name:\s*(.+?)\s*$", fm_body, re.MULTILINE)
    assert name_match, "frontmatter missing 'name'"
    expected = SKILL_PATH.parent.name
    assert name_match.group(1) == expected, f"frontmatter name {name_match.group(1)!r} != directory {expected!r}"


def test_skill_description_has_trigger_phrases() -> None:
    """Test 3: description contains every documented trigger phrase"""
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert fm is not None
    fm_body = fm.group(1)
    desc_match = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm_body, re.MULTILINE)
    assert desc_match, "description field not found"
    description = desc_match.group(1)

    required_phrases = [
        "README",
        "guide",
        "ADR",
        "PR description",
        "changelog",
        "tighten this",
        "too long",
        "hard to scan",
        "make this scannable",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in description]
    assert not missing, f"description missing trigger phrases: {missing}"


def test_skill_description_avoids_voice_tone_vocabulary() -> None:
    """Test 4: description avoids voice/tone vocabulary — mirrors test_adhd_skill_routing_guard"""
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert fm is not None
    fm_body = fm.group(1)
    desc_match = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm_body, re.MULTILINE)
    assert desc_match
    description = desc_match.group(1).lower()

    forbidden_terms = ["voice", "tone", "de-ai", "humanize"]
    for term in forbidden_terms:
        assert term not in description, f"description contains forbidden term: {term}"


def test_skill_blocklist_entries_present() -> None:
    """Test 5: body contains each of the 5 do-not-cite blocklist items.

    Matched on the shortest substring that still distinguishes each item, so the
    test pins the claim rather than the sentence someone wrote around it. "30%"
    alone would not distinguish the bold-ceiling item from the scanning-speed one,
    so those two carry one extra word each."""
    body = SKILL_PATH.read_text()
    required_substrings = [
        "30%-bold",
        "25% faster",
        "7±2",
        "faster scanning",
        "F-pattern",
    ]
    missing = [s for s in required_substrings if s not in body]
    assert not missing, f"blocklist entries missing from SKILL.md: {missing}"


def test_skill_all_28_check_ids_present() -> None:
    """Test 6: every one of the 28 check IDs appears in the body"""
    body = SKILL_PATH.read_text()
    missing = [check_id for check_id in ALL_CHECK_IDS if not re.search(rf"\b{check_id}\b", body)]
    assert not missing, f"check IDs missing from SKILL.md: {missing}"


def test_skill_group_f_ids_explicitly_present() -> None:
    """Test 7: F1-F4 explicitly present — separate from the loop above so a stale
    check-count contract can't let group F silently disappear while the loop-based
    28-count test still (wrongly) passes because some other check was duplicated"""
    body = SKILL_PATH.read_text()
    for check_id in ("F1", "F2", "F3", "F4"):
        assert re.search(rf"\b{check_id}\b", body), f"group F check {check_id} missing from SKILL.md"


def test_skill_group_f_precedes_group_a() -> None:
    """Test 8: group F heading precedes group A heading — F runs first per the protocol"""
    body = SKILL_PATH.read_text()
    f_index = body.index("### F —")
    a_index = body.index("### A —")
    assert f_index < a_index, "group F heading does not precede group A heading"


def test_skill_links_to_reference_files_not_forced() -> None:
    """Test 9: reference files are linked, not force-loaded with @-syntax"""
    body = SKILL_PATH.read_text()
    assert "[worked-examples.md](worked-examples.md)" in body, "missing link to worked-examples.md"
    assert "[evidence-and-limits.md](evidence-and-limits.md)" in body, "missing link to evidence-and-limits.md"
    assert "@worked-examples.md" not in body, "worked-examples.md must not be force-loaded with @-syntax"
    assert "@evidence-and-limits.md" not in body, "evidence-and-limits.md must not be force-loaded with @-syntax"


def test_reference_files_exist() -> None:
    """Test 10: both reference files exist and are non-empty"""
    for path in (WORKED_EXAMPLES_PATH, EVIDENCE_AND_LIMITS_PATH):
        assert path.exists(), f"reference file not found: {path}"
        assert len(path.read_text().strip()) > 0, f"reference file is empty: {path}"
