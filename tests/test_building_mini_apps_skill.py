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
REQUIRED_SECTIONS = ["When to use", "Pattern index", "Building a new app",
                     "When no pattern fits", "Adding a pattern", "Rules"]

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


@pytest.mark.parametrize(
    "kind,name,heading",
    [("pattern", "list-peek", "Anatomy"), ("study", "linear", "Unseen")],
)
def test_check_docs_fails_when_a_required_heading_is_removed(
    tmp_path: Path, kind: str, name: str, heading: str
) -> None:
    skill = _copy_skill(tmp_path)
    script = skill / "scripts" / "check_docs.py"
    doc = skill / "references" / ("patterns" if kind == "pattern" else "apps") / f"{name}.md"

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
