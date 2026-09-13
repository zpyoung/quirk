"""Contract pins for the simplifying-safely skill.

Modelled on test_writing_scannable_prose_skill.py — there is no shared skill-test
helper in tests/conftest.py, so this file reimplements its own frontmatter and
table-row parsing rather than importing one. These are static string/structure
assertions only; none of them judge prose quality, and none of them run the
skill.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
SKILL_DIR = SKILLS_DIR / "simplifying-safely"
SKILL_PATH = SKILL_DIR / "SKILL.md"
EVIDENCE_AND_LIMITS_PATH = SKILL_DIR / "evidence-and-limits.md"
README_PATH = REPO_ROOT / "README.md"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DESCRIPTION_RE = re.compile(r'^description:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)

# tech.md § SCHEMA: shipped rule ids — one letter per tier, sequential, no
# collisions with the audit record's overloaded ids (S1/S2 name two rules
# there; D1/D2/D4 repeat across tiers). Per-tier sizes: 7/6/4/3/4/2/6 = 32.
SHIPPED_TIERS = {
    "core": ["G1", "G2", "G3", "G4", "D1", "D2", "D3"],
    "code": ["C1", "C2", "C3", "C4", "C5", "C6"],
    "agent-facing docs": ["A1", "A2", "A3", "A4"],
    "specs": ["S1", "S2", "S3"],
    "human-facing docs": ["H1", "H2", "H3", "H4"],
    "conversational output": ["V1", "V2"],
    "meta": ["M1", "M2", "M3", "M4", "M5", "M6"],
}
ALL_SHIPPED_IDS = [id_ for ids in SHIPPED_TIERS.values() for id_ in ids]
EXPECTED_TIER_COUNTS = [7, 6, 4, 3, 4, 2, 6]

# Exact ids pinned by the tech spec, not derived from audited-ruleset.json —
# the audit's own ids (S1(code), D1-coevolution, HD1, P1B-1(chat), ...) don't
# line up positionally with the shipped scheme, so guessing a mapping back
# from tier + list order is a trap, not a derivation.
GROUNDED_IDS = ["G4", "D3", "C6", "M1"]
DIAGNOSIS_IDS = ["D3", "C1", "A4", "S2", "S3", "M4", "V1"]
EXPECTED_GROUNDED_COUNT = 4
EXPECTED_PRECAUTIONARY_COUNT = 14
EXPECTED_JUDGMENT_COUNT = 14
EXPECTED_DIAGNOSIS_COUNT = 7
EXPECTED_FALSIFICATION_COUNT = 15

BLOCKLIST_ANCHORS = [
    "Cursor",
    "Aider",
    "CONVENTIONS.md",
    "Karpathy",
    "McCabe",
    "preference data",
    "unused",
]

# tech.md § REGEX: no magnitudes in the hub, verbatim. An earlier draft ended
# the percent branch with \b, which cannot match right after a bare "%" — the
# test would have certified the leak it exists to catch. Do not "simplify" it.
NO_MAGNITUDES_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|per\s?cent|percent)|"
    r"ρ\s*=|"
    r"\bR\s*(?:²|\^2|2)\b|"
    r"\b\d+/\d+/\d+\b"
)

# tech.md § Testing strategy item 9, mirroring
# tests/test_writing_scannable_prose_skill.py:123-129's body.index() pattern.
# Headings are a best-effort rendering of tech.md's named order, following the
# sentence-case "## Heading" convention this repo's other skills use for the
# shared section names ("## When to Use", "## Integration", and the sibling
# skill's own "## Do-not-cite blocklist" / "## Links out").
SECTION_ORDER_MARKERS = [
    "## Overview",
    "## When to Use",
    "## Always-on core",
    "## Surface routing",
    # The per-surface tiers ship as one heading each rather than under an umbrella;
    # the tech spec pinned their order, not the literal heading strings.
    "## Code",
    "## Agent-facing docs",
    "## Specs",
    "## Human-facing docs",
    "## Conversational output",
    "## Meta",
    "## Falsification",
    "## Do-not-cite blocklist",
    "## Integration",
    "## Links out",
]


def _read_skill() -> str:
    return SKILL_PATH.read_text()


def _frontmatter_block(body: str) -> str:
    match = FRONTMATTER_RE.match(body)
    assert match is not None, "SKILL.md missing YAML frontmatter"
    return match.group(1)


def _description(fm_body: str) -> str:
    match = DESCRIPTION_RE.search(fm_body)
    assert match is not None, "frontmatter missing 'description'"
    return match.group(1)


def _table_rows(body: str) -> list[tuple[str, str, str]]:
    """Parse "| ID | Rule | Tag |" rows keyed by a shipped id in column 1.

    Cheap column split rather than a markdown parser — the contract format has
    no pipes inside cell text, and this repo's convention is stdlib-only,
    per-file parsing (see module docstring).
    """
    rows: list[tuple[str, str, str]] = []
    row_re = re.compile(r"^\s*\|\s*([A-Z]\d)\s*\|(.*)\|\s*`?([a-z]+(?:\s*·\s*diagnosis)?)`?\s*\|?\s*$")
    for line in body.splitlines():
        match = row_re.match(line)
        if match:
            rows.append((match.group(1), match.group(2).strip(), match.group(3).strip()))
    return rows


def test_frontmatter_has_exactly_name_and_description() -> None:
    """Test 1a: frontmatter parses, and carries only name + description.

    Guards tech.md's CONTRACT: frontmatter — no carried-over `proactive:` or
    `triggers:` keys from the superseded applying-simplicity-principles skill.
    """
    body = _read_skill()
    fm_body = _frontmatter_block(body)
    keys = set(re.findall(r"^([A-Za-z_-]+):", fm_body, re.MULTILINE))
    assert keys == {"name", "description"}, f"frontmatter keys {keys} != {{'name', 'description'}}"
    assert not re.search(r"^proactive:", fm_body, re.MULTILINE), "frontmatter must not carry 'proactive'"
    assert not re.search(r"^triggers:", fm_body, re.MULTILINE), "frontmatter must not carry 'triggers'"


def test_frontmatter_name_matches_directory() -> None:
    """Test 1b: frontmatter name equals the parent directory name"""
    body = _read_skill()
    fm_body = _frontmatter_block(body)
    name_match = re.search(r"^name:\s*(.+?)\s*$", fm_body, re.MULTILINE)
    assert name_match, "frontmatter missing 'name'"
    expected = SKILL_PATH.parent.name
    assert name_match.group(1) == expected, f"frontmatter name {name_match.group(1)!r} != directory {expected!r}"


def test_frontmatter_description_length_in_range() -> None:
    """Test 1c: description is non-trivial and within the 1024-char frontmatter limit"""
    body = _read_skill()
    fm_body = _frontmatter_block(body)
    description = _description(fm_body)
    assert 50 <= len(description) <= 1024, f"description length {len(description)} out of range [50, 1024]"


def test_description_contains_narrow_triggers() -> None:
    """Test 2a: description names each of logic.md's narrow triggers.

    logic.md § Data flow: "a simplification or cleanup request, a review,
    authoring an agent-facing document, writing a spec". Stem-matched so a
    plausible paraphrase ("simplifying" vs "simplification") still passes.
    """
    body = _read_skill()
    fm_body = _frontmatter_block(body)
    description = _description(fm_body)
    required_patterns = {
        "simplification/cleanup": r"simplif\w*|clean\s?-?up",
        "review": r"\breview\b",
        "agent-facing document": r"agent-facing",
        "spec": r"\bspecs?\b|specification",
    }
    missing = [label for label, pattern in required_patterns.items() if not re.search(pattern, description, re.IGNORECASE)]
    assert not missing, f"description missing narrow triggers: {missing}"


def test_description_excludes_always_proactive_framing() -> None:
    """Test 2b: description never drifts back to the superseded skill's always-proactive framing"""
    body = _read_skill()
    fm_body = _frontmatter_block(body)
    description = _description(fm_body)
    # word-bounded and negative-lookahead so this skill's own "always-on core"
    # vocabulary doesn't false-positive against the superseded skill's tell
    forbidden_patterns = [r"\balways\b(?!-on)", r"\bproactively\b", r"\bany code-related task\b"]
    present = [pattern for pattern in forbidden_patterns if re.search(pattern, description, re.IGNORECASE)]
    assert not present, f"description contains always-proactive framing: {present}"


def test_description_avoids_writing_scannable_prose_territory() -> None:
    """Test 3: description excludes writing-scannable-prose's trigger vocabulary.

    Mirrors tests/test_writing_scannable_prose_skill.py:73-85 — both skills
    would otherwise fire on one prompt.
    """
    body = _read_skill()
    fm_body = _frontmatter_block(body)
    description = _description(fm_body)
    # word-bounded so "guide" doesn't false-positive against logic.md's own
    # "quality guidance" / "prompt guidance" vocabulary
    forbidden_patterns = [r"\btighten\b", r"\bscannable\b", r"\breadme\b", r"\bguide\b", r"\bchangelog\b"]
    present = [pattern for pattern in forbidden_patterns if re.search(pattern, description, re.IGNORECASE)]
    assert not present, f"description overlaps writing-scannable-prose's territory: {present}"


def test_all_32_shipped_ids_present() -> None:
    """Test 4a: every one of the 32 shipped ids appears as a whole word in SKILL.md"""
    body = _read_skill()
    missing = [id_ for id_ in ALL_SHIPPED_IDS if not re.search(rf"\b{id_}\b", body)]
    assert not missing, f"shipped ids missing from SKILL.md: {missing}"


def test_shipped_id_tier_counts() -> None:
    """Test 4b: per-tier counts are 7/6/4/3/4/2/6 = 32, and each tier's table rows match"""
    assert [len(ids) for ids in SHIPPED_TIERS.values()] == EXPECTED_TIER_COUNTS
    assert len(ALL_SHIPPED_IDS) == 32, f"expected 32 shipped ids, constant has {len(ALL_SHIPPED_IDS)}"

    body = _read_skill()
    rows = _table_rows(body)
    row_ids = {row[0] for row in rows}
    for tier_name, ids in SHIPPED_TIERS.items():
        present = [id_ for id_ in ids if id_ in row_ids]
        assert len(present) == len(ids), (
            f"tier {tier_name!r} expected {len(ids)} table rows, found {len(present)} of {ids}"
        )


def test_tag_tallies_match_audit() -> None:
    """Test 5a: tag tallies across all rule tables are 4 grounded, 14 precautionary, 14 judgment"""
    body = _read_skill()
    rows = _table_rows(body)
    base_tags = [tag.split("·")[0].strip() for _, _, tag in rows]
    assert base_tags.count("grounded") == EXPECTED_GROUNDED_COUNT, (
        f"expected {EXPECTED_GROUNDED_COUNT} 'grounded' tags, found {base_tags.count('grounded')}"
    )
    assert base_tags.count("precautionary") == EXPECTED_PRECAUTIONARY_COUNT, (
        f"expected {EXPECTED_PRECAUTIONARY_COUNT} 'precautionary' tags, found {base_tags.count('precautionary')}"
    )
    assert base_tags.count("judgment") == EXPECTED_JUDGMENT_COUNT, (
        f"expected {EXPECTED_JUDGMENT_COUNT} 'judgment' tags, found {base_tags.count('judgment')}"
    )


def test_diagnosis_marker_count_and_ids() -> None:
    """Test 5b: exactly 7 diagnosis markers, on exactly D3, C1, A4, S2, S3, M4, V1

    These are the rules whose reviewer_test_holds is false in the audit record.
    """
    body = _read_skill()
    rows = _table_rows(body)
    diagnosis_ids = {id_ for id_, _, tag in rows if "diagnosis" in tag}
    assert len(diagnosis_ids) == EXPECTED_DIAGNOSIS_COUNT, (
        f"expected {EXPECTED_DIAGNOSIS_COUNT} diagnosis markers, found {len(diagnosis_ids)}: {sorted(diagnosis_ids)}"
    )
    assert diagnosis_ids == set(DIAGNOSIS_IDS), f"diagnosis ids {sorted(diagnosis_ids)} != {sorted(DIAGNOSIS_IDS)}"


def test_grounded_ids_are_exactly_g4_d3_c6_m1() -> None:
    """Test 5c: the 4 grounded rows are exactly G4, D3, C6, M1 — no substitution, no extra"""
    body = _read_skill()
    rows = _table_rows(body)
    grounded_ids = {id_ for id_, _, tag in rows if tag.split("·")[0].strip() == "grounded"}
    assert grounded_ids == set(GROUNDED_IDS), f"grounded ids {sorted(grounded_ids)} != {sorted(GROUNDED_IDS)}"


def test_falsification_lines_present_and_keyed_by_id() -> None:
    """Test 6: 15 falsification lines (14 precautionary + C6), each keyed by a shipped id.

    tech.md's content source copies audited-ruleset.json's trailing
    "Falsification: ..." sentence verbatim per rule.
    """
    body = _read_skill()
    falsification_lines = [line for line in body.splitlines() if "Falsification:" in line]
    assert len(falsification_lines) == EXPECTED_FALSIFICATION_COUNT, (
        f"expected {EXPECTED_FALSIFICATION_COUNT} falsification lines, found {len(falsification_lines)}"
    )

    id_pattern = re.compile(r"\b(" + "|".join(ALL_SHIPPED_IDS) + r")\b")
    unkeyed = [line for line in falsification_lines if not id_pattern.search(line)]
    assert not unkeyed, f"falsification lines not keyed by a shipped id: {unkeyed}"

    keyed_ids = {id_pattern.search(line).group(1) for line in falsification_lines}
    assert "C6" in keyed_ids, "C6 must carry a falsification line despite being grounded, not precautionary"


def test_blocklist_anchors_present_verbatim() -> None:
    """Test 7: all seven do-not-cite blocklist anchors appear verbatim in SKILL.md"""
    body = _read_skill()
    missing = [anchor for anchor in BLOCKLIST_ANCHORS if anchor not in body]
    assert not missing, f"blocklist anchors missing from SKILL.md: {missing}"


def test_no_magnitudes_regex_finds_no_match() -> None:
    """Test 8a: the no-magnitudes regex finds zero matches in SKILL.md.

    logic.md locks direction only, never magnitudes, in the hub.
    """
    body = _read_skill()
    match = NO_MAGNITUDES_RE.search(body)
    assert match is None, f"magnitude leaked into SKILL.md: {match.group(0)!r}"


def test_constraint_count_figure_absent() -> None:
    """Test 8b: the 7-11 simultaneous-constraint figure is absent from SKILL.md.

    audited-ruleset.json's assembly.budget_note states those counts are for
    the audit only; logic.md and the companion may carry it, the hub may not.
    """
    body = _read_skill()
    assert "seven to eleven" not in body.lower(), "constraint-count figure ('seven to eleven') leaked into SKILL.md"
    assert not re.search(r"\b7\s*(?:-|–|to)\s*11\b", body), "constraint-count figure ('7-11') leaked into SKILL.md"


def test_section_order_holds() -> None:
    """Test 9: hub sections appear in the locked order, via body.index() comparisons.

    Mirrors tests/test_writing_scannable_prose_skill.py:123-129. Core precedes
    every surface tier because it applies at every firing; the blocklist sits
    before Links out so it is never below the fold.
    """
    body = _read_skill()
    positions = []
    for marker in SECTION_ORDER_MARKERS:
        assert marker in body, f"expected section heading not found: {marker!r}"
        positions.append(body.index(marker))
    for earlier, later, earlier_marker, later_marker in zip(
        positions, positions[1:], SECTION_ORDER_MARKERS, SECTION_ORDER_MARKERS[1:]
    ):
        assert earlier < later, f"{earlier_marker!r} must precede {later_marker!r}"


def test_m6_subagent_gate_restatement_fence_present() -> None:
    """Test 10: a fenced, copy-pasteable block restates G1-G3 in the imperative.

    tech.md § CONTRACT (M6): a rule that says "restate the gate" and leaves the
    agent to compose the restatement gets a paraphrase — ship the literal
    fence instead.
    """
    body = _read_skill()
    fences = re.findall(r"```.*?```", body, re.DOTALL)
    matching = [
        fence for fence in fences
        if all(re.search(rf"\b{gate_id}\b", fence) for gate_id in ("G1", "G2", "G3"))
    ]
    assert matching, "no fenced block restates G1, G2 and G3 for subagent dispatch"


def test_links_are_relative_never_at_prefixed() -> None:
    """Test 11a: evidence-and-limits.md is linked with a bare relative link, never @-force-loaded"""
    body = _read_skill()
    assert "[evidence-and-limits.md](evidence-and-limits.md)" in body, "missing link to evidence-and-limits.md"
    assert "@evidence-and-limits.md" not in body, "evidence-and-limits.md must not be force-loaded with @-syntax"
    assert not re.search(r"@[\w-]+\.md\b", body), "no reference file may be force-loaded with @-syntax"


def test_evidence_and_limits_file_exists_and_nonempty() -> None:
    """Test 11b: the companion reference file exists and is non-empty"""
    assert EVIDENCE_AND_LIMITS_PATH.exists(), f"reference file not found: {EVIDENCE_AND_LIMITS_PATH}"
    assert len(EVIDENCE_AND_LIMITS_PATH.read_text().strip()) > 0, "evidence-and-limits.md is empty"


def test_readme_skill_count_matches_skill_directory() -> None:
    """Test 12: README's skill count equals the number of skills/*/SKILL.md directories.

    tests/test_adhd_skill.py:157-164 already enforces this bump; this test
    only pins that the counting convention still holds once this skill ships.
    """
    readme = README_PATH.read_text()
    skill_dirs = [path for path in SKILLS_DIR.iterdir() if (path / "SKILL.md").exists()]

    match = re.search(r"\*\*(\d+) skills\*\*", readme)
    assert match, "README missing skill count in What ships section"
    assert int(match.group(1)) == len(skill_dirs), (
        f"README claims {match.group(1)} skills, found {len(skill_dirs)} skills/*/SKILL.md directories"
    )
