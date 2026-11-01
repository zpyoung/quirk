"""Structural checks for the explaining-features skill: entry point, references, links, evals, honesty strings."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "explaining-features"
SKILL_PATH = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
EVALS_PATH = SKILL_DIR / "evals" / "trigger-evals.json"
MAKING_VIDEOS_EVALS = REPO_ROOT / "skills" / "making-videos" / "evals" / "trigger-evals.json"
README_PATH = REPO_ROOT / "README.md"

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SCRIPT_REF = re.compile(r"scripts/([A-Za-z0-9_./-]+\.py)")
SIBLING_PATH = re.compile(r"skills/(making-videos|writing-html-artifacts|using-apps-like-a-user)\b")

PRESSURE_HEADINGS = ("## Scenario", "## Your Options", "## Choose A, B, or C", "## Correct choice")

# Phrases from the logic spec's Then clauses and Decisions Locked, so a rewrite can't quietly drop one.
REQUIRED_STRINGS: dict[str, tuple[str, ...]] = {
    "SKILL.md": (
        "SKILL_DIR",
        "quirk:making-videos",
        "quirk:writing-html-artifacts",
        "quirk:using-apps-like-a-user",
        "--unattended",
        "stops: none",
        "--scale 2",
        "macOS only",
        "only when asked",
        "doesn't wait",
        "no film, because nothing moves",
        "before the user walks away",
        "clip per behavior",
        "main behavior",
        "mock up",
        "no footage was captured",
        "seeded data",
        "frame check",
        "verify_outcome.py",
        "code_tour.py",
        "code tour",
        "crosses",
        "references/code-tour.md",
        "size_limit",
        "ship_disclosed",
        "outside_calls",
        "not proven",
        "disappears with the worktree",
        "versions are never overwritten",
        "run the skill again",
        "storyboard",
        "~/Studio/explainers/",
        ".quirk/html",
        "Never",
        "self-ignoring",
        "This skill's own scripts",
    ),
    "references/evidence.md": (
        "Behavior | Claim | Result | How checked | Proof",
        "Pass",
        "Partly",
        "Unit test only",
        "Not proven",
        "Failed",
        "pass_without_effect",
        "one file at a time",
        "sources.md",
        "diagram",
        "using-apps-like-a-user",
    ),
    "references/capture.md": (
        "private instance",
        "seeded",
        "persisted",
        "parent commit",
        "git archive",
        "fps=1/3",
        "home directory",
        "username",
        "alt text",
        "captions",
        "beats.json",
        "copy",
        "fresh home",
        "fixture's repo path",
    ),
    "references/code-tour.md": (
        "code tour",
        "source files",
        "tests, docs, lockfiles and generated files",
        "tour.json",
        "code_tour.py",
        "studio.py project new",
        "voice.py say",
        "voice.py align",
        "voice.py captions",
        "hf.py",
        "verify.py",
        "verify_outcome.py",
        "sources.md",
        "stops: none",
        "cloud_allow",
        "highlight",
        "skip",
        "no scene generator",
        "reading of",
        "ledger",
        "tour.mp4",
        "media/",
    ),
    "references/page.md": (
        "Staged for the camera",
        "seeded data",
        "drawn pointer",
        "added labels",
        "sped up",
        "parent commit",
        "at this commit",
        "customer",
        "How it's built",
        "What's still open",
        "size_limit",
        "compressing images",
        "base64",
        "data-inline",
        "names the code or spec",
        "ledger",
    ),
}


def _frontmatter() -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", SKILL_PATH.read_text(), re.DOTALL)
    assert match is not None, "SKILL.md is missing YAML frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        assert sep, f"unparseable frontmatter line: {line!r}"
        fields[key.strip()] = value.strip()
    return fields


def _body() -> str:
    return re.sub(r"^---\n.*?\n---\n", "", SKILL_PATH.read_text(), count=1, flags=re.DOTALL)


def _markdown_files() -> list[Path]:
    return [SKILL_PATH, *sorted(REFERENCES_DIR.glob("*.md"))]


def _skill_files() -> list[Path]:
    return sorted(p for p in SKILL_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def test_frontmatter_has_only_name_and_description() -> None:
    assert set(_frontmatter()) == {"name", "description"}


def test_frontmatter_name_equals_directory() -> None:
    assert _frontmatter()["name"] == SKILL_DIR.name == "explaining-features"


def test_description_length_and_opening() -> None:
    description = _frontmatter()["description"]
    assert 50 <= len(description) <= 1024
    assert description.startswith("Use when")


def test_description_covers_the_trigger_phrases_and_routes_video_only_requests() -> None:
    description = _frontmatter()["description"].lower()
    for phrase in ("walkthrough", "explain this feature", "feature explainer", "show what this pr does"):
        assert phrase in description, phrase
    assert "making-videos" in description


def test_skill_body_is_under_300_lines() -> None:
    assert len(_body().splitlines()) < 300


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_every_relative_link_resolves(doc: Path) -> None:
    for target in LINK.findall(doc.read_text()):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        assert (doc.parent / path).exists(), f"{doc.name}: broken link {target}"


def test_every_script_named_in_the_skill_exists() -> None:
    named: set[str] = set()
    for doc in _markdown_files():
        named.update(SCRIPT_REF.findall(doc.read_text()))
    assert {"verify_outcome.py", "code_tour.py", "leftovers.py"} <= named
    assert "fit_video.py" not in named
    for name in named:
        assert (SKILL_DIR / "scripts" / name).is_file(), name
    assert not (SKILL_DIR / "scripts" / "fit_video.py").exists()


def test_skill_does_not_use_plugin_root_variable() -> None:
    for path in _skill_files():
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        assert "CLAUDE_PLUGIN_ROOT" not in text, path.relative_to(SKILL_DIR)


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_sibling_skills_are_named_not_pathed(doc: Path) -> None:
    assert not SIBLING_PATH.search(doc.read_text()), f"{doc.name} builds a sibling skill's path"


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_docs_have_no_em_dashes(doc: Path) -> None:
    assert "—" not in doc.read_text()


def test_stopping_processes_is_a_hard_rule_in_skill_and_capture() -> None:
    skill = SKILL_PATH.read_text()
    assert "Stop only what you started" in skill
    for text in (skill, (REFERENCES_DIR / "capture.md").read_text()):
        for needle in ("PID", "pkill", "killall", "by name or pattern"):
            assert needle in text, needle
    capture = (REFERENCES_DIR / "capture.md").read_text()
    section = capture.split("## Stopping what you started", 1)[1].split("\n## ", 1)[0]
    for needle in ("working directory", "HOME", "$E", "outlive"):
        assert needle in section, needle


def test_capture_requires_checking_that_a_yours_entry_is_a_command_you_started() -> None:
    capture = (REFERENCES_DIR / "capture.md").read_text()
    section = capture.split("## Stopping what you started", 1)[1].split("\n## ", 1)[0]
    assert "only if its command is one you started" in section
    assert "out of text" in section


def test_capture_finds_survivors_with_leftovers_not_a_lsof_sweep() -> None:
    capture = (REFERENCES_DIR / "capture.md").read_text()
    section = capture.split("## Stopping what you started", 1)[1].split("\n## ", 1)[0]
    assert "leftovers.py" in section
    assert "lsof -w +D" not in capture
    assert "+D" not in capture
    assert "Anything listed is yours" not in capture
    assert re.search(r"[Nn]ever stop anything in `check_by_hand`", section)
    assert "$E/harness/" in capture and "HOME" in capture
    assert "temp folder or `$E`" not in capture
    assert "leftovers.py" in SKILL_PATH.read_text()


def test_skill_points_at_every_reference() -> None:
    body = SKILL_PATH.read_text()
    for ref in sorted(REFERENCES_DIR.glob("*.md")):
        assert f"references/{ref.name}" in body, ref.name
    assert {p.name for p in REFERENCES_DIR.glob("*.md")} == {"evidence.md", "capture.md", "page.md", "code-tour.md"}


def test_skill_points_at_every_pressure_scenario() -> None:
    body = SKILL_PATH.read_text()
    for n in (1, 2, 3, 4, 5, 6):
        assert f"test-pressure-{n}.md" in body


@pytest.mark.parametrize("rel", sorted(REQUIRED_STRINGS))
def test_required_strings_are_present(rel: str) -> None:
    text = (SKILL_DIR / rel).read_text().lower()
    for needle in REQUIRED_STRINGS[rel]:
        assert needle.lower() in text, f"{rel} is missing {needle!r}"


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6])
def test_pressure_scenario_follows_the_house_layout(n: int) -> None:
    text = (SKILL_DIR / f"test-pressure-{n}.md").read_text()
    assert text.startswith(f"# Pressure Test {n}:")
    assert "**IMPORTANT: This is a real scenario." in text
    assert f"skills/explaining-features" in text
    positions = [text.find(h) for h in PRESSURE_HEADINGS]
    assert all(p >= 0 for p in positions), PRESSURE_HEADINGS
    assert positions == sorted(positions)
    for option in ("**A)", "**B)", "**C)"):
        assert option in text
    assert re.search(r"## Correct choice\n\n\*\*[ABC]\.\*\*", text)


def test_pressure_scenario_4_covers_the_sourced_reasoning_rule_and_the_blocked_stop() -> None:
    text = (SKILL_DIR / "test-pressure-4.md").read_text().lower()
    for needle in ("blocked", "login", "stop 2", "from reading the code", "design reason", "names the code or spec"):
        assert needle in text, needle
    assert re.search(r"## correct choice\n\n\*\*c\.\*\*", text)


def _page_section(heading: str) -> str:
    return (REFERENCES_DIR / "page.md").read_text().split(f"## {heading}", 1)[1].split("\n## ", 1)[0]


def test_page_outline_links_the_poster_and_the_problem_sentence() -> None:
    outline = _page_section("The outline")
    assert "(#the-poster)" in outline
    assert "(#the-problem-sentence)" in outline


def test_problem_sentence_needs_a_source_and_never_a_guess() -> None:
    section = _page_section("The problem sentence")
    for needle in ("source", "No spec, commit or issue says why", "Never infer", "evidence.md", "stays out of the film"):
        assert needle in section, needle
    assert "problem sentence" in _page_section("Readers")
    assert "problem sentence" in (REFERENCES_DIR / "evidence.md").read_text()


def test_poster_is_a_real_checked_frame_of_the_result() -> None:
    section = _page_section("The poster")
    for needle in ("main behavior", "real frame", "ffmpeg", "Never composite", "frame check", "clip per behavior", "no film"):
        assert needle in section, needle


def test_cold_read_is_fresh_bounded_and_reports_when_it_did_not_run() -> None:
    section = _page_section("The cold read")
    for needle in (
        "no conversation history",
        "can't tell",
        "$E/cold-read.md",
        "two reads",
        "not a stop",
        "never the ledger",
        "not run, because",
        "first frame",
    ):
        assert needle in section, needle


def test_skill_runs_the_cold_read_and_reports_it_at_hand_over() -> None:
    skill = SKILL_PATH.read_text()
    assert "references/page.md#the-cold-read" in skill
    assert "cold-read.md" in skill
    hand_over = skill.split("### 7. Hand over", 1)[1].split("\n## ", 1)[0]
    assert "Cold read:" in hand_over


def test_pressure_scenario_5_covers_the_invented_reason_and_the_skipped_cold_read() -> None:
    text = (SKILL_DIR / "test-pressure-5.md").read_text().lower()
    for needle in ("no spec, commit or issue says why", "can't tell", "cold read", "fresh"):
        assert needle in text, needle
    assert re.search(r"## correct choice\n\n\*\*b\.\*\*", text)


def test_pressure_scenario_6_covers_the_unsourced_tour_line() -> None:
    text = (SKILL_DIR / "test-pressure-6.md").read_text().lower()
    for needle in ("code tour", "sources.md", "conclusion", "caption", "ledger", "cut"):
        assert needle in text, needle
    assert re.search(r"## correct choice\n\n\*\*b\.\*\*", text)


def _code_tour() -> str:
    return (REFERENCES_DIR / "code-tour.md").read_text()


def test_plan_step_states_when_a_tour_is_proposed_and_when_it_is_not() -> None:
    plan = SKILL_PATH.read_text().split("### 1. Plan, and don't wait", 1)[1].split("\n### 2.", 1)[0]
    for needle in ("code tour, because it crosses", "3 or more source files", "technical reader", "override", "customer"):
        assert needle in plan, needle
    reference = _code_tour()
    for needle in ("3 or more source files", "unless the user asks", "customer", "however many source files"):
        assert needle in reference, needle


def test_tour_step_follows_the_film_step_and_points_at_the_reference() -> None:
    skill = SKILL_PATH.read_text()
    film = skill.index("### 5. Film")
    tour = skill.index("### 5b. Code tour")
    page = skill.index("### 6. Page")
    assert film < tour < page
    step = skill[tour:page]
    assert "references/code-tour.md" in step
    assert "code_tour.py" in step
    assert "no scene generator" in step


def test_tour_sourcing_rule_is_stated_once_and_keeps_the_ledger_rule_for_the_behavior_film() -> None:
    reference = _code_tour()
    for needle in ("a file and line, a commit or a spec", "names it as a conclusion", "reading of", "doesn't loosen", "every line cites a ledger row"):
        assert needle in reference, needle
    assert "ledger result" in reference
    table = SKILL_PATH.read_text().split("## When you're tempted to skip a rule", 1)[1].split("Pressure scenarios", 1)[0]
    assert "in the tour" in table and "sources.md" in table


def test_tour_commands_run_in_the_documented_order() -> None:
    commands = [
        "studio.py project new",
        "code_tour.py lines",
        "voice.py say",
        "voice.py align",
        "hf.py",
        "code_tour.py build",
        "voice.py captions",
        "code_tour.py check",
        "studio.py version new",
        "verify.py",
        "verify_outcome.py",
    ]
    reference = _code_tour().replace('"', "")
    positions = [reference.find(c) for c in commands]
    assert all(p >= 0 for p in positions), dict(zip(commands, positions))
    assert positions == sorted(positions)
    assert "CLAUDE.md" in reference and "AGENTS.md" in reference
    assert "$E/media/" in reference


def test_tour_failing_verify_leaves_the_behavior_film_alone() -> None:
    reference = _code_tour()
    for needle in ("tour alone", "written notes", "outside_calls", "behavior film"):
        assert needle in reference, needle


def test_behavior_film_rules_stay_with_it_on_a_page_with_both() -> None:
    section = _page_section("The code tour on the page")
    for needle in ("behavior film only", "poster rule", "cold read", "$E/media/film.mp4", "plain frame", "caption", "drawn", "generated", "What's still open"):
        assert needle in section, needle
    assert "film at the top" in _page_section("The outline") or "behavior film" in _page_section("The outline")
    assert "$E/media/tour.mp4" in section or "tour.mp4" in section


def test_no_size_limit_on_an_explainer_page() -> None:
    skill = SKILL_PATH.read_text()
    page = (REFERENCES_DIR / "page.md").read_text()
    for text in (skill, page):
        assert '"size_limit": "none"' in text
        assert "10 MiB" not in text
        assert "budget" not in text.lower()
    assert "## Compressing images" in page
    assert "sips" in _page_section("Compressing images")
    assert "#the-size-budget" not in page and "#the-size-budget" not in (REFERENCES_DIR / "capture.md").read_text()
    assert "2 MB" in skill.split("### 7. Hand over", 1)[1].split("\n## ", 1)[0]
    assert "film.mp4" in skill and "as rendered" in skill


def test_no_doc_mentions_the_fit_script_or_the_raw_film() -> None:
    for path in _skill_files():
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for gone in ("fit_video", "film-raw"):
            assert gone not in text, f"{path.relative_to(SKILL_DIR)} mentions {gone}"


def test_trigger_evals_are_balanced() -> None:
    data = json.loads(EVALS_PATH.read_text())
    assert data["skill_name"] == "explaining-features"
    queries = data["queries"]
    assert all(set(q) == {"query", "should_trigger"} for q in queries)
    assert all(isinstance(q["query"], str) and q["query"] for q in queries)
    assert sum(q["should_trigger"] is True for q in queries) >= 12
    assert sum(q["should_trigger"] is False for q in queries) >= 12
    assert len({q["query"] for q in queries}) == len(queries)


def test_trigger_evals_cover_the_routing_table() -> None:
    queries = {q["query"]: q["should_trigger"] for q in json.loads(EVALS_PATH.read_text())["queries"]}
    assert queries["Make a walkthrough of this feature"] is True
    assert queries["Explain what this PR does, with screenshots"] is True
    assert queries["Make a 30 second video announcing our release"] is False
    assert queries["Build a dashboard page for these numbers"] is False
    assert queries["Try this flow in the app"] is False


def test_trigger_evals_cover_a_code_walkthrough_of_a_features_change() -> None:
    queries = [q["query"] for q in json.loads(EVALS_PATH.read_text())["queries"] if q["should_trigger"]]
    walkthroughs = [q for q in queries if "code" in q.lower() and ("walk" in q.lower() or "tour" in q.lower())]
    assert len(walkthroughs) >= 2


def test_making_videos_evals_carry_near_misses_for_this_skill() -> None:
    queries = {q["query"]: q["should_trigger"] for q in json.loads(MAKING_VIDEOS_EVALS.read_text())["queries"]}
    for query in ("Make a walkthrough of this feature", "Explain what this PR does, with screenshots"):
        assert queries[query] is False
    own = {q["query"] for q in json.loads(EVALS_PATH.read_text())["queries"] if q["should_trigger"]}
    assert len(own & {q for q, t in queries.items() if t is False}) >= 3


def test_readme_counts_and_names_the_skill() -> None:
    readme = README_PATH.read_text()
    assert "**31 skills**" in readme
    assert "explaining-features" in readme
