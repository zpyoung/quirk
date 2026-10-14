"""Contract for kit_docs.py: the generated components reference and the per-element example sources.

Everything is offline. The stale-file tests work on a tmp copy of the skill's kit and reference, never
on the committed file.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
SCRIPT = SKILL / "scripts" / "kit_docs.py"
COMPONENTS = SKILL / "references" / "components.md"
sys.path.insert(0, str(SKILL / "scripts"))

import kit_docs  # noqa: E402
from htmlkit import assemble, kitcheck  # noqa: E402

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


def _catalog() -> kitcheck.Catalog:
    return kit_docs.load(SKILL)


def _skill_copy(tmp_path: Path) -> Path:
    """A skill directory holding just what kit_docs reads: the registry, the kit, the report template, the reference."""
    skill = tmp_path / "skill"
    (skill / "vendor").mkdir(parents=True)
    shutil.copy(SKILL / "vendor" / "libraries.json", skill / "vendor" / "libraries.json")
    shutil.copytree(SKILL / "vendor" / "kit", skill / "vendor" / "kit")
    shutil.copytree(SKILL / "templates" / "report", skill / "templates" / "report")
    (skill / "references").mkdir()
    shutil.copy(COMPONENTS, skill / "references" / "components.md")
    return skill


def test_reference_check_is_clean_against_the_committed_file() -> None:
    result = _run("reference", "--check")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"stale": False}


def test_reference_check_writes_nothing() -> None:
    before = COMPONENTS.read_bytes()
    _run("reference", "--check")
    assert COMPONENTS.read_bytes() == before


def test_reference_check_reports_a_stale_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill = _skill_copy(tmp_path)
    target = skill / "references" / "components.md"
    target.write_text(target.read_text() + "\nhand edit\n")
    assert kit_docs.main(["reference", "--check"], skill_dir=skill) == 1
    assert json.loads(capsys.readouterr().out) == {"stale": True}
    assert target.read_text().endswith("hand edit\n")


def test_reference_check_reports_a_missing_file_as_stale(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill = _skill_copy(tmp_path)
    (skill / "references" / "components.md").unlink()
    assert kit_docs.main(["reference", "--check"], skill_dir=skill) == 1
    assert json.loads(capsys.readouterr().out) == {"stale": True}


def test_reference_writes_the_file_and_is_then_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill = _skill_copy(tmp_path)
    target = skill / "references" / "components.md"
    target.write_text("old\n")
    assert kit_docs.main(["reference"], skill_dir=skill) == 0
    assert json.loads(capsys.readouterr().out) == {"written": [str(target)]}
    assert target.read_text() == COMPONENTS.read_text()
    assert kit_docs.main(["reference", "--check"], skill_dir=skill) == 0
    assert json.loads(capsys.readouterr().out) == {"stale": False}


def test_reference_output_is_deterministic() -> None:
    assert kit_docs.render_reference(_catalog()) == kit_docs.render_reference(_catalog())


def test_reference_opens_with_the_generated_by_line() -> None:
    first = COMPONENTS.read_text().splitlines()[0:3]
    text = " ".join(first)
    assert "Generated from `vendor/kit/1.0.0/catalog.json` by `scripts/kit_docs.py reference`. Do not edit by hand." in text


def test_reference_explains_inclusion() -> None:
    text = COMPONENTS.read_text()
    assert "## How inclusion works" in text
    assert "q-chart" in text and "Chart.js" in text
    assert "`kit`" in text and "`kit` check" in text


def test_reference_has_an_index_and_a_section_per_element() -> None:
    text = COMPONENTS.read_text()
    for tag in _catalog().elements:
        assert f"[`{tag}`](#{tag})" in text, f"index entry for {tag}"
        assert re.search(rf"^## `{tag}`$", text, re.M), f"section for {tag}"


def test_reference_sections_carry_the_catalog_content() -> None:
    text = COMPONENTS.read_text()
    for element in _catalog().elements.values():
        assert element.use_when in text
        assert f"```html\n{element.example}\n```" in text
        for attribute in element.attributes:
            assert f"| `{attribute.name}` |" in text
    assert text.count("Companion option html: allowed") == 5
    assert text.count("Companion option html: not allowed (interactive)") == 4


def test_reference_attribute_table_columns() -> None:
    text = COMPONENTS.read_text()
    assert "| Name | Required | Kind | Values | Default | Description |" in text


def test_reference_links_resolve() -> None:
    for target in LINK.findall(COMPONENTS.read_text()):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        assert (COMPONENTS.parent / target.split("#", 1)[0]).exists(), target


def test_reference_anchors_resolve() -> None:
    text = COMPONENTS.read_text()
    for anchor in re.findall(r"\]\(#([^)]+)\)", text):
        assert re.search(rf"^## `{re.escape(anchor)}`$", text, re.M), anchor


def test_examples_write_one_source_per_element_except_the_note(tmp_path: Path) -> None:
    out = tmp_path / "examples"
    result = _run("examples", str(out))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    expected = sorted(t for t in _catalog().elements if t != "q-diff-note")
    assert sorted(Path(p).name for p in payload["written"]) == [f"{t}.src.html" for t in expected]
    assert sorted(p.name for p in out.iterdir()) == [f"{t}.src.html" for t in expected]
    assert not (out / "q-diff-note.src.html").exists()


def test_examples_parse_as_report_sources(tmp_path: Path) -> None:
    out = tmp_path / "examples"
    assert _run("examples", str(out)).returncode == 0
    catalog = _catalog()
    for tag in (t for t in catalog.elements if t != "q-diff-note"):
        source = assemble.parse_source(out / f"{tag}.src.html")
        assert source.template == "report"
        assert source.title == f"{tag} example"
        assert source.mode == "offline"
        assert source.interactions == []
        assert source.slots["main"].strip() == catalog.elements[tag].example.strip()


def test_examples_add_an_aside_only_when_the_template_requires_one(tmp_path: Path) -> None:
    skill = _skill_copy(tmp_path)
    plain = tmp_path / "plain"
    assert kit_docs.main(["examples", str(plain)], skill_dir=skill) == 0
    assert set(assemble.parse_source(plain / "q-code.src.html").slots) == {"main"}

    template = skill / "templates" / "report" / "template.json"
    data = json.loads(template.read_text())
    data["slots"]["aside"]["required"] = True
    template.write_text(json.dumps(data))
    needing = tmp_path / "needing"
    assert kit_docs.main(["examples", str(needing)], skill_dir=skill) == 0
    assert set(assemble.parse_source(needing / "q-code.src.html").slots) == {"main", "aside"}


def test_examples_are_deterministic(tmp_path: Path) -> None:
    for name in ("a", "b"):
        assert _run("examples", str(tmp_path / name)).returncode == 0
    for path in (tmp_path / "a").iterdir():
        assert path.read_bytes() == (tmp_path / "b" / path.name).read_bytes()


def test_usage_error_is_one_json_object_on_stdout() -> None:
    result = _run("bogus")
    assert result.returncode == 2
    assert "error" in json.loads(result.stdout)


@pytest.mark.parametrize("slots", [[], "main", None, {"main": []}])
def test_examples_report_a_malformed_template_manifest_as_one_json_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], slots: object
) -> None:
    skill = _skill_copy(tmp_path)
    template = skill / "templates" / "report" / "template.json"
    data = json.loads(template.read_text())
    data["slots"] = slots
    template.write_text(json.dumps(data))
    rc = kit_docs.main(["examples", str(tmp_path / "out")], skill_dir=skill)
    assert rc == 2
    assert "error" in json.loads(capsys.readouterr().out)
