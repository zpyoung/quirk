"""Structure and script-contract checks for the building-mini-apps skill package."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "building-mini-apps"
SKILL_PATH = SKILL_DIR / "SKILL.md"
SCRIPTS_DIR = SKILL_DIR / "scripts"
PATTERNS_DIR = SKILL_DIR / "gallery" / "src" / "patterns"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

APPS = ["linear", "things", "raycast", "craft", "obsidian",
        "tableplus", "fantastical", "notion", "granola", "figma"]
PATTERNS = ["list-peek", "expand-in-place", "action-palette", "doc-collections", "workspace-panes",
            "staged-table-edit", "mini-full", "view-switcher", "assisted-notes", "inspector"]
STYLES = ["neutral-house", "calm-paper", "airy-white", "cool-tool",
          "dense-dark", "glass-launcher", "split-tone"]
REQUIRED_SECTIONS = ["When to use", "Pattern index", "Style index", "Building a new app",
                     "When no pattern fits", "Adding a pattern", "Changing an app's style",
                     "Rules"]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DESCRIPTION_RE = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)
H2_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
IMPORT_SPEC_RE = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)['"]([^'"]+)['"]""")
RENDERED_FORBIDDEN_RE = re.compile(r"<(AppShell|Toaster|TooltipProvider)\b")


def _run_script(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
    )


def _copy_skill(dest: Path) -> Path:
    """Copy the skill tree; scripts anchor on their own location, so the copy is self-contained."""
    target = dest / "building-mini-apps"
    shutil.copytree(SKILL_DIR, target, ignore=shutil.ignore_patterns("node_modules", "media"))
    return target


def _load_script(name: str) -> ModuleType:
    # the scripts import their sibling `_mini` by bare name
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(f"_bma_{name}", SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _missing_sections(text: str) -> List[str]:
    """Required `##` sections that are absent or appear out of the required order."""
    titles = H2_RE.findall(text)
    missing = []
    cursor = 0
    for required in REQUIRED_SECTIONS:
        try:
            cursor = titles.index(required, cursor) + 1
        except ValueError:
            missing.append(required)
    return missing


@pytest.fixture
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """Make any subprocess launch fail the test; returns the list of attempted commands."""
    attempts: List[str] = []

    def _forbidden(*args, **kwargs):
        attempts.append(str(args[0] if args else kwargs.get("args")))
        raise AssertionError(f"subprocess launched: {attempts[-1]}")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    return attempts


# --- SKILL.md frontmatter and structure ---


def test_skill_frontmatter_has_name_and_trigger_phrases() -> None:
    match = FRONTMATTER_RE.match(SKILL_PATH.read_text())
    assert match is not None, "SKILL.md missing YAML frontmatter"
    front = match.group(1)
    assert re.search(r"^name:\s*building-mini-apps\s*$", front, re.MULTILINE)
    description = DESCRIPTION_RE.search(front)
    assert description is not None, "frontmatter missing description"
    lowered = description.group(1).lower()
    assert "mini app" in lowered
    assert "build me" in lowered


def test_skill_has_required_sections_in_order() -> None:
    assert _missing_sections(SKILL_PATH.read_text()) == []


def test_section_check_detects_a_removed_section() -> None:
    text = SKILL_PATH.read_text()
    assert _missing_sections(text) == []
    assert _missing_sections(text.replace("## Rules", "## Other")) == ["Rules"]
    swapped = text.replace("## When to use", "## @@").replace("## Pattern index", "## When to use")
    swapped = swapped.replace("## @@", "## Pattern index")
    assert _missing_sections(swapped) != []


def test_skill_links_every_pattern_reference_and_each_exists() -> None:
    text = SKILL_PATH.read_text()
    for slug in PATTERNS:
        assert f"(references/patterns/{slug}.md)" in text, f"SKILL.md does not link {slug}"
        assert (SKILL_DIR / "references" / "patterns" / f"{slug}.md").is_file()


# --- check_docs.py ---


@pytest.mark.parametrize("app", APPS)
def test_study_note_passes_check_docs(app: str) -> None:
    result = _run_script(SCRIPTS_DIR / "check_docs.py", "study", app)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("pattern", PATTERNS)
def test_pattern_reference_passes_check_docs(pattern: str) -> None:
    result = _run_script(SCRIPTS_DIR / "check_docs.py", "pattern", pattern)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("style", STYLES)
def test_style_reference_passes_check_docs(style: str) -> None:
    result = _run_script(SCRIPTS_DIR / "check_docs.py", "style", style)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "kind,name,heading",
    [("pattern", "list-peek", "Anatomy"), ("study", "linear", "Unseen"),
     ("style", "calm-paper", "Leaves out")],
)
def test_check_docs_fails_when_a_required_heading_is_removed(
    tmp_path: Path, kind: str, name: str, heading: str
) -> None:
    skill = _copy_skill(tmp_path)
    script = skill / "scripts" / "check_docs.py"
    folder = {"pattern": "patterns", "study": "apps", "style": "styles"}[kind]
    doc = skill / "references" / folder / f"{name}.md"

    # the untouched copy must pass, or the failure below proves nothing
    assert _run_script(script, kind, name).returncode == 0

    original = doc.read_text()
    assert f"## {heading}\n" in original
    doc.write_text(original.replace(f"## {heading}\n", "", 1))
    result = _run_script(script, kind, name)
    assert result.returncode == 1
    assert heading in result.stdout


def test_check_docs_exits_2_on_usage_error() -> None:
    assert _run_script(SCRIPTS_DIR / "check_docs.py", "bogus", "x").returncode == 2


# --- build_registry.py --check ---


def test_registry_check_passes_on_the_real_tree() -> None:
    result = _run_script(SCRIPTS_DIR / "build_registry.py", "--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_registry_check_fails_naming_the_item_after_a_source_byte_changes(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    script = skill / "scripts" / "build_registry.py"
    assert _run_script(script, "--check").returncode == 0

    source = skill / "gallery" / "src" / "patterns" / "list-peek" / "index.ts"
    source.write_bytes(source.read_bytes() + b" ")
    result = _run_script(script, "--check")
    assert result.returncode == 1
    assert "stale: list-peek" in result.stderr


# --- pattern folders ---


def test_pattern_folders_match_the_pattern_list() -> None:
    folders = sorted(p.name for p in PATTERNS_DIR.iterdir() if p.is_dir())
    assert folders == sorted(PATTERNS)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_pattern_folder_has_required_files_and_a_valid_manifest(pattern: str) -> None:
    folder = PATTERNS_DIR / pattern
    for name in ("registry-item.json", "index.ts", "demo.tsx"):
        assert (folder / name).is_file(), f"{pattern} missing {name}"
    manifest = json.loads((folder / "registry-item.json").read_text())
    assert manifest["name"] == pattern
    assert "files" not in manifest, "files are derived by build_registry.py, not hand-written"


@pytest.mark.parametrize("pattern", PATTERNS)
def test_pattern_sources_stay_within_their_own_block(pattern: str) -> None:
    folder = PATTERNS_DIR / pattern
    sources = sorted(p for p in folder.rglob("*") if p.suffix in (".ts", ".tsx"))
    assert sources
    for source in sources:
        text = source.read_text()
        for spec in IMPORT_SPEC_RE.findall(text):
            where = f"{source.relative_to(SKILL_DIR)} imports {spec!r}"
            assert "gallery" not in spec, where
            if spec.startswith("@/patterns/"):
                assert spec.split("/")[2] == pattern, where
            elif spec.startswith("."):
                resolved = (source.parent / spec).resolve()
                assert resolved.is_relative_to(folder.resolve()), where
        for match in RENDERED_FORBIDDEN_RE.finditer(text):
            pytest.fail(f"{source.relative_to(SKILL_DIR)} renders <{match.group(1)}>")


def test_import_scan_detects_a_cross_pattern_import() -> None:
    specs = IMPORT_SPEC_RE.findall('import x from "../list-peek"\nconst y = import("@/patterns/inspector")')
    assert specs == ["../list-peek", "@/patterns/inspector"]
    assert RENDERED_FORBIDDEN_RE.search("return <AppShell title='x' />")


# --- new_app.py / add_patterns.py usage errors ---


def test_new_app_exits_2_on_unknown_pattern_without_running_a_subprocess(
    tmp_path: Path, no_subprocess: List[str]
) -> None:
    new_app = _load_script("new_app")
    target = tmp_path / "app"
    assert new_app.main([str(target), "--patterns", "no-such-pattern"]) == 2
    assert not target.exists()
    assert no_subprocess == []


def test_new_app_exits_2_on_existing_target_without_running_a_subprocess(
    tmp_path: Path, no_subprocess: List[str]
) -> None:
    new_app = _load_script("new_app")
    target = tmp_path / "app"
    target.mkdir()
    assert new_app.main([str(target), "--patterns", "list-peek"]) == 2
    assert no_subprocess == []


def test_new_app_exits_2_on_missing_parent_without_running_a_subprocess(
    tmp_path: Path, no_subprocess: List[str]
) -> None:
    new_app = _load_script("new_app")
    target = tmp_path / "missing-parent" / "app"
    assert new_app.main([str(target)]) == 2
    assert not target.parent.exists()
    assert no_subprocess == []


def test_subprocess_guard_trips_when_a_script_helper_launches_a_process(
    tmp_path: Path, no_subprocess: List[str]
) -> None:
    mini = _load_script("_mini")
    with pytest.raises(AssertionError, match="subprocess launched"):
        mini.run_step("probe", ["true"], tmp_path)
    assert len(no_subprocess) == 1


def test_add_patterns_exits_2_without_components_json(
    tmp_path: Path, no_subprocess: List[str]
) -> None:
    add_patterns = _load_script("add_patterns")
    assert add_patterns.main([str(tmp_path), "--patterns", "list-peek"]) == 2
    assert no_subprocess == []


def test_add_patterns_exits_2_on_unknown_pattern(tmp_path: Path, no_subprocess: List[str]) -> None:
    add_patterns = _load_script("add_patterns")
    (tmp_path / "components.json").write_text("{}")
    assert add_patterns.main([str(tmp_path), "--patterns", "no-such-pattern"]) == 2
    assert no_subprocess == []


# --- .gitignore ---


def test_gitignore_covers_reference_media() -> None:
    sample = "skills/building-mini-apps/references/media/linear/frame-01.png"
    if shutil.which("git"):
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", sample],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
        )
        if result.returncode in (0, 1):
            assert result.returncode == 0, f"{sample} is not git-ignored"
            return
    lines = [line.strip() for line in GITIGNORE_PATH.read_text().splitlines()]
    assert "skills/building-mini-apps/references/media/" in lines


# --- check_docs.py: names from disk, blueprint, observations ---

CHECK_DOCS = "check_docs.py"

BLUEPRINT_OK = """# Linear blueprint

## Core jobs

| ID | Job | State |
|----|-----|-------|
| J1 | Triage incoming issues | covered |
| J2 | Peek an issue from the list | confirmed |
| J10 | Filter the list | proposed |

## Screens

- Triage: two-pane list and detail, serves J1

## Coverage

| Row | Mark | Pattern | Evidence |
|-----|------|---------|----------|
| J1 triage list | matched | list-peek | `S1-t0042.png` |
| J2 peek | approximated | list-peek | S5, S6 |
| Screen: loading | left out | none | unseen |

## Composition

Shell with a list column and a detail pane.

## Proposed patterns

None

## Proposed revisions

None
"""

STUDY_STUB = """# Stub study note

## Sources

| ID | URL | Kind | Date | Shows |
|----|-----|------|------|-------|
| S1 | https://example.test/a | official | undated | a |
| S2 | https://example.test/b | official | undated | b |

## Observations

- S1, `references/media/stub/S1-t0001.png`: something. → feeds: list-peek

## Unseen

- nothing

## Patterns fed

- list-peek
"""


def _check_docs(skill: Path, *args: str) -> subprocess.CompletedProcess:
    return _run_script(skill / "scripts" / CHECK_DOCS, *args)


def _blueprint_skill(tmp_path: Path, text: str = BLUEPRINT_OK) -> Path:
    skill = _copy_skill(tmp_path)
    folder = skill / "references" / "blueprints"
    folder.mkdir(exist_ok=True)
    (folder / "linear.md").write_text(text)
    return skill


def test_check_docs_study_accepts_a_note_added_to_disk(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    (skill / "references" / "apps" / "stub.md").write_text(STUDY_STUB)
    result = _check_docs(skill, "study", "stub")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "study stub: ok" in result.stdout


def test_check_docs_pattern_accepts_a_reference_added_to_disk(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    source = skill / "references" / "patterns" / "list-peek.md"
    (skill / "references" / "patterns" / "brand-new.md").write_text(source.read_text())
    assert _check_docs(skill, "pattern", "brand-new").returncode == 0


@pytest.mark.parametrize("kind", ["study", "pattern", "blueprint"])
def test_check_docs_missing_file_exits_1_naming_the_path(tmp_path: Path, kind: str) -> None:
    skill = _copy_skill(tmp_path)
    result = _check_docs(skill, kind, "nonesuch")
    assert result.returncode == 1
    assert "missing file" in result.stdout and "nonesuch.md" in result.stdout


def test_check_docs_blueprint_without_a_study_note_names_the_app(tmp_path: Path) -> None:
    skill = _blueprint_skill(tmp_path)
    (skill / "references" / "blueprints" / "orphan.md").write_text(BLUEPRINT_OK)
    result = _check_docs(skill, "blueprint", "orphan")
    assert result.returncode == 1
    assert "no study note for orphan" in result.stdout


@pytest.mark.parametrize("kind,name", [
    ("study", "Linear"), ("study", "-linear"), ("study", "../linear"), ("pattern", "list_peek"),
    ("blueprint", "a b"), ("observations", "LINEAR"),
])
def test_check_docs_rejects_bad_names_with_exit_2(kind: str, name: str, tmp_path: Path) -> None:
    extra = [str(tmp_path / "bullets.md")] if kind == "observations" else []
    assert _run_script(SCRIPTS_DIR / CHECK_DOCS, kind, name, *extra).returncode == 2


def test_check_docs_exits_2_on_wrong_argument_counts() -> None:
    script = SCRIPTS_DIR / CHECK_DOCS
    assert _run_script(script).returncode == 2
    assert _run_script(script, "blueprint").returncode == 2
    assert _run_script(script, "study", "linear", "extra").returncode == 2
    assert _run_script(script, "observations", "linear").returncode == 2
    assert _run_script(script, "observations", "linear", "f.md", "--bogus").returncode == 2


def test_blueprint_valid_fixture_passes(tmp_path: Path) -> None:
    skill = _blueprint_skill(tmp_path)
    result = _check_docs(skill, "blueprint", "linear")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "blueprint linear: ok" in result.stdout


def _blueprint_problems(tmp_path: Path, text: str) -> str:
    skill = _blueprint_skill(tmp_path, text)
    result = _check_docs(skill, "blueprint", "linear")
    assert result.returncode == 1, result.stdout + result.stderr
    return result.stdout


def test_blueprint_missing_heading_is_named(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("## Composition\n", "", 1))
    assert "Composition" in out


def test_blueprint_headings_out_of_order_fail(tmp_path: Path) -> None:
    text = BLUEPRINT_OK.replace("## Screens", "## TMP").replace("## Composition", "## Screens") \
        .replace("## TMP", "## Composition")
    assert "out of order" in _blueprint_problems(tmp_path, text)


def test_blueprint_empty_section_fails_but_none_is_valid(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("None\n\n## Proposed revisions", "\n## Proposed revisions"))
    assert "Proposed patterns" in out and "empty" in out


def test_blueprint_confirmed_job_without_coverage_row_fails(tmp_path: Path) -> None:
    text = BLUEPRINT_OK.replace("| J2 peek | approximated | list-peek | S5, S6 |\n", "")
    out = _blueprint_problems(tmp_path, text)
    assert "J2" in out


def test_blueprint_coverage_prefix_respects_word_boundary(tmp_path: Path) -> None:
    text = BLUEPRINT_OK.replace("| J1 triage list |", "| J10 triage list |")
    out = _blueprint_problems(tmp_path, text)
    assert "J1" in out and "no coverage row" in out


def test_blueprint_proposed_job_needs_no_coverage_row(tmp_path: Path) -> None:
    skill = _blueprint_skill(tmp_path)
    assert _check_docs(skill, "blueprint", "linear").returncode == 0


def test_blueprint_unresolvable_frame_citation_is_named(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("S1-t0042.png", "S1-t9999.png"))
    assert "S1-t9999.png" in out


def test_blueprint_unresolvable_source_id_is_named(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("S5, S6", "S5, S99"))
    assert "S99" in out


def test_blueprint_empty_evidence_fails(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("S5, S6", "nothing here"))
    assert "J2" in out and "citation" in out


def test_blueprint_unseen_on_a_matched_row_fails(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("`S1-t0042.png`", "unseen"))
    assert "unseen" in out and "left out" in out


def test_blueprint_bad_state_fails(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("| J10 | Filter the list | proposed |",
                                                             "| J10 | Filter the list | done |"))
    assert "done" in out


def test_blueprint_bad_mark_fails(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("approximated", "mostly"))
    assert "mostly" in out


def test_blueprint_bad_job_id_and_duplicate_id_fail(tmp_path: Path) -> None:
    bad = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("| J10 |", "| X10 |"))
    assert "X10" in bad
    dup = _blueprint_problems(tmp_path / "dup", BLUEPRINT_OK.replace("| J10 |", "| J2 |"))
    assert "J2" in dup and "duplicate" in dup


def test_blueprint_coverage_row_must_start_with_job_id_or_screen(tmp_path: Path) -> None:
    out = _blueprint_problems(tmp_path, BLUEPRINT_OK.replace("| Screen: loading |", "| loading |"))
    assert "loading" in out


def test_blueprint_core_jobs_needs_at_least_one_row(tmp_path: Path) -> None:
    text = BLUEPRINT_OK
    for row in ("| J1 | Triage incoming issues | covered |\n", "| J2 | Peek an issue from the list | confirmed |\n",
                "| J10 | Filter the list | proposed |\n"):
        text = text.replace(row, "")
    text = text.replace("| J1 triage list | matched | list-peek | `S1-t0042.png` |\n", "") \
        .replace("| J2 peek | approximated | list-peek | S5, S6 |\n", "")
    assert "Core jobs" in _blueprint_problems(tmp_path, text)


def test_blueprint_frame_citation_resolves_against_the_observations_text(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    (skill / "references" / "apps" / "stub.md").write_text(STUDY_STUB)
    folder = skill / "references" / "blueprints"
    folder.mkdir(exist_ok=True)
    good = BLUEPRINT_OK.replace("S1-t0042.png", "S1-t0001.png").replace("S5, S6", "S1, S2")
    (folder / "stub.md").write_text(good)
    result = _check_docs(skill, "blueprint", "stub")
    assert result.returncode == 0, result.stdout
    (folder / "stub.md").write_text(good.replace("S1, S2", "S5"))
    assert "S5" in _check_docs(skill, "blueprint", "stub").stdout


# observations

LINEAR_FRAME = "references/media/linear/S1-t0042.png"


def _bullets(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "bullets.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def test_observations_clean_bullets_pass_and_file_is_untouched(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    bullets = _bullets(
        tmp_path,
        f"- S1, `{LINEAR_FRAME}`: a two-pane layout. → feeds: list-peek; jobs: J1",
        "",
        "- S5, text of the Peek section: Space opens peek. → feeds: list-peek; jobs: J2",
    )
    before = bullets.read_text()
    result = _check_docs(skill, "observations", "linear", str(bullets))
    assert result.returncode == 0, result.stdout + result.stderr
    assert bullets.read_text() == before


def test_observations_flags_unknown_source_id_with_line_number(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    bullets = _bullets(tmp_path, "- S5, text of a page: ok. → feeds: list-peek",
                       "- S99, text of a page: nope. → feeds: list-peek")
    result = _check_docs(skill, "observations", "linear", str(bullets))
    assert result.returncode == 1
    assert "line 2" in result.stdout and "S99" in result.stdout
    assert "line 1" not in result.stdout


def test_observations_flags_lines_that_are_not_bullets(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    bullets = _bullets(tmp_path, "S1, no dash", "- no source id here", "- S1 missing comma")
    result = _check_docs(skill, "observations", "linear", str(bullets))
    assert result.returncode == 1
    for n in ("line 1", "line 2", "line 3"):
        assert n in result.stdout


def test_observations_frames_flag_checks_files_on_disk(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    bullets = _bullets(tmp_path, f"- S1, `{LINEAR_FRAME}`: a layout. → feeds: list-peek")
    # without --frames the cited file is not checked
    assert _check_docs(skill, "observations", "linear", str(bullets)).returncode == 0
    missing = _check_docs(skill, "observations", "linear", str(bullets), "--frames")
    assert missing.returncode == 1
    assert "line 1" in missing.stdout and "S1-t0042.png" in missing.stdout
    frame = skill / LINEAR_FRAME
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"png")
    assert _check_docs(skill, "observations", "linear", "--frames", str(bullets)).returncode == 0


def test_observations_text_only_bullet_needs_no_frame_under_frames(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    bullets = _bullets(tmp_path, "- S5, text of a page: ok. → feeds: list-peek")
    assert _check_docs(skill, "observations", "linear", str(bullets), "--frames").returncode == 0


def test_observations_missing_bullets_file_or_study_note_exits_1(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    missing_file = _check_docs(skill, "observations", "linear", str(tmp_path / "none.md"))
    assert missing_file.returncode == 1 and "missing file" in missing_file.stdout
    bullets = _bullets(tmp_path, "- S1, text: x")
    no_note = _check_docs(skill, "observations", "nonesuch", str(bullets))
    assert no_note.returncode == 1 and "missing file" in no_note.stdout
