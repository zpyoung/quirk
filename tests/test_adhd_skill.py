from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "adhd" / "SKILL.md"
FRAMES_PATH = REPO_ROOT / "skills" / "adhd" / "frames.md"
UPSTREAM_LICENSE_PATH = REPO_ROOT / "skills" / "adhd" / "UPSTREAM-LICENSE"
PLUGIN_JSON_PATH = REPO_ROOT / ".claude-plugin" / "plugin.json"


def test_adhd_skill_has_valid_frontmatter() -> None:
    """Test 1: YAML frontmatter parse — valid YAML structure"""
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert fm is not None, "ADHD skill missing YAML frontmatter"
    fm_body = fm.group(1)
    assert re.search(r"^name:\s*adhd\s*$", fm_body, re.MULTILINE), "frontmatter missing 'name: adhd'"
    assert re.search(r"^description:\s*.+$", fm_body, re.MULTILINE), "frontmatter missing description"


def test_adhd_skill_description_length() -> None:
    """Test 2: Description length — ≥50 characters (sufficient for routing)"""
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert fm is not None
    fm_body = fm.group(1)
    desc_match = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm_body, re.MULTILINE)
    assert desc_match, "description field not found"
    description = desc_match.group(1).strip('"')
    assert len(description) >= 50, f"description too short ({len(description)} chars)"


def test_adhd_skill_routing_guard() -> None:
    """Test 3: Routing guard — description does NOT contain generic 'brainstorm' or 'ideate' triggers"""
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert fm is not None
    fm_body = fm.group(1)
    desc_match = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm_body, re.MULTILINE)
    assert desc_match
    description = desc_match.group(1).lower()

    # Should NOT contain generic brainstorm/ideate triggers that would collide with brainstorming skill
    forbidden_patterns = [
        r'\bbrainstorm\b',  # generic "brainstorm" (but /adhd and "brainstorming delegates" are OK)
        r'\bideate\b',
        r'\bcreative work\b',
    ]

    for pattern in forbidden_patterns:
        assert not re.search(pattern, description), f"description contains forbidden trigger: {pattern}"


def test_adhd_skill_upstream_attribution() -> None:
    """Test 4: Upstream attribution — SKILL.md contains 'Attribution' section"""
    body = SKILL_PATH.read_text()
    assert re.search(r"^##\s+Attribution\s*$", body, re.MULTILINE), "SKILL.md missing Attribution section"
    assert "upstream" in body.lower(), "Attribution section should mention upstream source"


def test_adhd_upstream_license_exists() -> None:
    """Test 5: UPSTREAM-LICENSE file — exists and is readable"""
    assert UPSTREAM_LICENSE_PATH.exists(), f"UPSTREAM-LICENSE not found at {UPSTREAM_LICENSE_PATH}"
    content = UPSTREAM_LICENSE_PATH.read_text()
    assert "MIT License" in content, "UPSTREAM-LICENSE should contain MIT License text"
    assert len(content) > 100, "UPSTREAM-LICENSE appears empty or truncated"


def test_adhd_skill_hard_gate_presence() -> None:
    """Test 6: HARD-GATE presence — SKILL.md contains HARD-GATE tag with clarification"""
    body = SKILL_PATH.read_text()
    assert "HARD-GATE" in body, "SKILL.md should document HARD-GATE behavior"
    # Should clarify that ADHD does NOT trigger mandatory gates
    assert re.search(r"(does NOT|no mandatory|advisory|opt-in)", body, re.IGNORECASE), \
        "HARD-GATE should clarify advisory/opt-in nature"


def test_adhd_skill_standalone_exit() -> None:
    """Test 7: Standalone exit — SKILL.md documents exit behavior after /adhd"""
    body = SKILL_PATH.read_text()
    assert re.search(r"(standalone exit|release control|normal agent loop)", body, re.IGNORECASE), \
        "SKILL.md should document standalone exit behavior"


def test_adhd_skill_score_cluster_inline() -> None:
    """Test 8: Score/Cluster inline — SKILL.md clarifies these phases run inline"""
    body = SKILL_PATH.read_text()
    assert re.search(r"(score.*inline|cluster.*inline|inline.*score|inline.*cluster)", body, re.IGNORECASE), \
        "SKILL.md should clarify Score/Cluster run inline by main agent"


def test_adhd_skill_context_handling() -> None:
    """Test 9: Context handling — SKILL.md documents 'summarize in next turn' approach"""
    body = SKILL_PATH.read_text()
    assert re.search(r"(next turn|summarize|cannot intercept|tool_result)", body, re.IGNORECASE), \
        "SKILL.md should document context handling (summarize in next turn)"


def test_adhd_skill_nesting_fallback() -> None:
    """Test 10: Nesting fallback — SKILL.md documents sequential deepen fallback"""
    body = SKILL_PATH.read_text()
    assert re.search(r"(nesting|fallback|sequential|in-context)", body, re.IGNORECASE), \
        "SKILL.md should document nesting fallback for deepen phase"


def test_adhd_frames_all_fifteen_present() -> None:
    """Test 11: 15 frames in frames.md — all frames present with descriptions"""
    body = FRAMES_PATH.read_text()

    expected_frames = [
        "Constraint inversion",
        "Opposite day",
        "Time travel",
        "Cross-domain analogy",
        "Stakeholder rotation",
        "Failure pre-mortem",
        "Sensory shift",
        "Scale extremes",
        "Role reversal",
        "Material substitution",
        "Process reversal",
        "Success post-mortem",
        "Beginner's mind",
        "Expert blind spots",
        "Adjacent possible",
    ]

    for frame in expected_frames:
        assert frame.lower() in body.lower(), f"frames.md missing frame: {frame}"


def test_adhd_skill_output_shape() -> None:
    """Test 12: Output shape sections — SKILL.md includes 'Option A/B/C' + 'Recommendation' structure"""
    body = SKILL_PATH.read_text()
    assert re.search(r"Option A", body), "SKILL.md should document Option A format"
    assert re.search(r"Option B", body), "SKILL.md should document Option B format"
    assert re.search(r"Option C", body), "SKILL.md should document Option C format"
    assert re.search(r"Recommendation", body), "SKILL.md should document Recommendation section"


def test_adhd_plugin_keywords() -> None:
    """Test 13: Plugin keywords — plugin.json contains adhd, divergent-ideation, divergent-thinking"""
    import json

    content = PLUGIN_JSON_PATH.read_text()
    data = json.loads(content)

    keywords = data.get("keywords", [])
    assert "adhd" in keywords, "plugin.json missing 'adhd' keyword"
    assert "divergent-ideation" in keywords, "plugin.json missing 'divergent-ideation' keyword"
    assert "divergent-thinking" in keywords, "plugin.json missing 'divergent-thinking' keyword"
