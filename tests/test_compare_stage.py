"""Behavioral contract for stage 3 (compare approaches) in the interactive renderer."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "writing-specs" / "interactive" / "render_spec.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "interactive" / "v2"
COMPARE = FIXTURES / "compare"
STAGE2 = FIXTURES / "stage2"
SAMPLE = REPO_ROOT / "tests" / "fixtures" / "interactive" / "sample"
INVALID = COMPARE / "invalid"
EXPORTS = COMPARE / "exports"

sys.path.insert(0, str(SCRIPT.parent))
import render_spec  # noqa: E402

PAYLOAD_OPEN = '<script type="application/json" id="quirk-logic-spec-payload">'
UNSIGNED_WARNING = "comparison.json ignored: stage 3 waits for stage-2 sign-off"
STAGE3_REFUSAL = "stage-3 exports carry challenges, not decisions; use check-export or challenges"
EXPECTED_HASHES = json.loads((COMPARE / "expected-hashes.json").read_text(encoding="utf-8"))
INVALID_EXPECTED = json.loads((INVALID / "expected.json").read_text(encoding="utf-8"))
INVALID_FILES = sorted(INVALID_EXPECTED)


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


def make_compare_dir(tmp_path: Path, comparison: Path | None = COMPARE / "comparison.json") -> Path:
    spec_dir = tmp_path / "compare"
    spec_dir.mkdir(parents=True)
    shutil.copy(COMPARE / "logic.json", spec_dir / "logic.json")
    if comparison is not None:
        shutil.copy(comparison, spec_dir / "comparison.json")
    return spec_dir


def payload_of(spec_dir: Path) -> Dict[str, Any]:
    html = (spec_dir / "review.html").read_text(encoding="utf-8")
    start = html.index(PAYLOAD_OPEN) + len(PAYLOAD_OPEN)
    return json.loads(html[start : html.index("</script>", start)])


def load_fixture_comparison() -> Dict[str, Any]:
    return json.loads((COMPARE / "comparison.json").read_text(encoding="utf-8"))


def load_fixture_logic() -> Dict[str, Any]:
    return json.loads((COMPARE / "logic.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", INVALID_FILES)
@pytest.mark.parametrize("command", ["render", "validate"])
def test_invalid_comparison_exits_1_with_pointer(tmp_path: Path, name: str, command: str) -> None:
    spec_dir = make_compare_dir(tmp_path, INVALID / name)
    result = run_cli(command, str(spec_dir))
    assert result.returncode == 1, result.stderr
    prefix = INVALID_EXPECTED[name]
    assert any(line.startswith(prefix) for line in result.stderr.splitlines()), result.stderr
    assert not (spec_dir / "review.html").exists()


def test_unsigned_spec_ignores_comparison_with_warning(tmp_path: Path) -> None:
    spec_dir = tmp_path / "stage2"
    spec_dir.mkdir()
    shutil.copy(STAGE2 / "logic.json", spec_dir / "logic.json")
    shutil.copy(COMPARE / "comparison.json", spec_dir / "comparison.json")
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    assert UNSIGNED_WARNING in result.stderr
    payload = payload_of(spec_dir)
    assert "comparison" not in payload
    assert "comparisonId" not in payload


def test_absent_comparison_is_silent_and_adds_no_payload_keys(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path, None)
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    assert "comparison" not in result.stderr
    payload = payload_of(spec_dir)
    assert "comparison" not in payload
    assert "comparisonId" not in payload


def test_render_embeds_comparison_without_changing_render_id(tmp_path: Path) -> None:
    with_comparison = make_compare_dir(tmp_path / "with")
    without = make_compare_dir(tmp_path / "without", None)
    rendered = run_cli("render", str(with_comparison))
    baseline = run_cli("render", str(without))
    assert rendered.returncode == 0, rendered.stderr
    assert baseline.returncode == 0, baseline.stderr
    assert rendered.stdout.strip() == baseline.stdout.strip()
    payload = payload_of(with_comparison)
    assert payload["comparison"] == load_fixture_comparison()
    assert payload["comparisonId"] == EXPECTED_HASHES["comparisonId"]
    assert payload["renderId"] == baseline.stdout.strip()
    rest = {key: value for key, value in payload.items() if key not in ("comparison", "comparisonId")}
    assert rest == payload_of(without)
    assert (with_comparison / "logic.md").read_text(encoding="utf-8") == (without / "logic.md").read_text(encoding="utf-8")


def test_render_warns_about_requirement_scored_against_older_text(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path)
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    stale_lines = [line for line in result.stderr.splitlines() if "/scores/REQ-03/C" in line]
    assert len(stale_lines) == 1
    assert "older" in stale_lines[0]
    assert "REQ-01" not in result.stderr


def test_validate_accepts_fixture(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path)
    result = run_cli("validate", str(spec_dir))
    assert result.returncode == 0, result.stderr


def test_signoff_render_id_mismatch_warns(tmp_path: Path) -> None:
    comparison = load_fixture_comparison()
    comparison["builtAgainst"]["signoffRenderId"] = "ffffffffffff"
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(comparison), encoding="utf-8")
    spec_dir = make_compare_dir(tmp_path / "spec", path)
    result = run_cli("validate", str(spec_dir))
    assert result.returncode == 0, result.stderr
    assert "signoffRenderId" in result.stderr


def test_fold_does_not_embed_comparison(tmp_path: Path) -> None:
    spec_dir = tmp_path / "stage2"
    spec_dir.mkdir()
    shutil.copy(STAGE2 / "logic.json", spec_dir / "logic.json")
    shutil.copy(COMPARE / "comparison.json", spec_dir / "comparison.json")
    result = run_cli("fold", str(spec_dir), str(STAGE2 / "exports" / "signed.json"))
    assert result.returncode == 0, result.stderr
    payload = payload_of(spec_dir)
    assert "comparison" not in payload
    assert "comparisonId" not in payload


def test_check_export_valid(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path)
    result = run_cli("check-export", str(spec_dir), str(EXPORTS / "valid.json"))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "stage-3: 2 challenges, 1 stars"


@pytest.mark.parametrize(
    ("name", "code"),
    [("stale-comparison", 3), ("wrong-slug", 3), ("bad-shape", 1), ("unresolved-target", 1)],
)
def test_check_export_failures(tmp_path: Path, name: str, code: int) -> None:
    spec_dir = make_compare_dir(tmp_path)
    result = run_cli("check-export", str(spec_dir), str(EXPORTS / (name + ".json")))
    assert result.returncode == code, result.stderr
    assert "stage-3:" not in result.stdout
    if code == 1:
        assert any(line.startswith("/challenges/") for line in result.stderr.splitlines())


def test_check_export_rejects_non_iso_exported_at(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path)
    export = json.loads((EXPORTS / "valid.json").read_text(encoding="utf-8"))
    export["exportedAt"] = "yesterday"
    bad = tmp_path / "bad-exported-at.json"
    bad.write_text(json.dumps(export), encoding="utf-8")
    result = run_cli("check-export", str(spec_dir), str(bad))
    assert result.returncode == 1, result.stderr
    assert any(line.startswith("/exportedAt") for line in result.stderr.splitlines()), result.stderr


def test_check_export_without_loaded_comparison_is_stale(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path, None)
    result = run_cli("check-export", str(spec_dir), str(EXPORTS / "valid.json"))
    assert result.returncode == 3


def test_check_export_with_invalid_comparison_exits_1(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path, INVALID / "bad-status.json")
    result = run_cli("check-export", str(spec_dir), str(EXPORTS / "valid.json"))
    assert result.returncode == 1
    assert "/scores/REQ-01/B" in result.stderr


@pytest.mark.parametrize("command", ["fold", "reapprove"])
def test_fold_and_reapprove_refuse_stage3_export(tmp_path: Path, command: str) -> None:
    spec_dir = make_compare_dir(tmp_path)
    before = (spec_dir / "logic.json").read_text(encoding="utf-8")
    result = run_cli(command, str(spec_dir), str(EXPORTS / "valid.json"))
    assert result.returncode == 2
    assert result.stderr.strip() == STAGE3_REFUSAL
    assert (spec_dir / "logic.json").read_text(encoding="utf-8") == before


def test_stage2_check_export_is_unchanged(tmp_path: Path) -> None:
    spec_dir = tmp_path / "stage2"
    spec_dir.mkdir()
    shutil.copy(STAGE2 / "logic.json", spec_dir / "logic.json")
    result = run_cli("check-export", str(spec_dir), str(STAGE2 / "exports" / "signed.json"))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "signed"


def test_challenges_text_groups_by_approach(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path)
    result = run_cli("challenges", str(spec_dir), str(EXPORTS / "valid.json"))
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.index("Approach A") < out.index("Approach B")
    a_block, b_block = out.split("Approach B")
    assert "A-1" in a_block and "Streaming writer" in a_block
    assert "The streaming writer looks bigger than L." in a_block
    assert "L-XL" in a_block
    assert "target changed" in a_block
    assert "REQ-02" in b_block
    assert "The staging copy should name the unreadable file before compression." in b_block
    assert "target changed" not in b_block
    assert out.count("target changed") == 1


def test_challenges_json_keys_by_approach_plus_stars(tmp_path: Path) -> None:
    spec_dir = make_compare_dir(tmp_path)
    result = run_cli("challenges", str(spec_dir), str(EXPORTS / "valid.json"), "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert set(data) == {"A", "B", "stars"}
    assert data["stars"] == ["REQ-01"]
    assert [entry["id"] for entry in data["A"]] == ["ch-2"]
    assert [entry["id"] for entry in data["B"]] == ["ch-1"]
    assert data["A"][0]["targetChanged"] is True
    assert data["B"][0]["targetChanged"] is False


@pytest.mark.parametrize(
    ("name", "code"),
    [("stale-comparison", 3), ("wrong-slug", 3), ("bad-shape", 1), ("unresolved-target", 1)],
)
def test_challenges_applies_check_export_rules(tmp_path: Path, name: str, code: int) -> None:
    spec_dir = make_compare_dir(tmp_path)
    result = run_cli("challenges", str(spec_dir), str(EXPORTS / (name + ".json")))
    assert result.returncode == code, result.stderr
    assert result.stdout == ""


def test_target_hash_matches_expected_fixture_values() -> None:
    comparison = load_fixture_comparison()
    checked = 0
    for key, expected in EXPECTED_HASHES["targets"].items():
        kind, *parts = key.split("|")
        if kind == "score":
            requirement_id, approach_id = parts
            target = comparison["scores"][requirement_id][approach_id]
        else:
            approach_id, slice_id = parts
            approach = next(item for item in comparison["approaches"] if item["id"] == approach_id)
            target = next(item for item in approach["slices"] if item["id"] == slice_id)
        assert render_spec.target_hash(target, kind) == expected, key
        checked += 1
    assert checked == len(EXPECTED_HASHES["targets"]) > 0


def test_target_hash_ignores_check_and_history_but_not_note() -> None:
    score = dict(load_fixture_comparison()["scores"]["REQ-01"]["C"])
    base = render_spec.target_hash(score, "score")
    assert base == EXPECTED_HASHES["targets"]["score|REQ-01|C"]
    assert render_spec.target_hash({**score, "check": "verified", "history": []}, "score") == base
    assert render_spec.target_hash({**score, "note": "changed"}, "score") != base
    with pytest.raises(ValueError):
        render_spec.target_hash(score, "other")


def test_comparison_id_matches_expected() -> None:
    assert render_spec.comparison_id(load_fixture_comparison()) == EXPECTED_HASHES["comparisonId"]


def test_signed_predicate() -> None:
    signed = load_fixture_logic()
    assert render_spec.spec_is_signed_stage2(signed) is True
    unsigned = json.loads((STAGE2 / "logic.json").read_text(encoding="utf-8"))
    assert render_spec.spec_is_signed_stage2(unsigned) is False
    assert render_spec.spec_is_signed_stage2({**signed, "status": "Stage 1 approved"}) is False
    assert render_spec.spec_is_signed_stage2({**signed, "schemaVersion": 1}) is False
    without_signoff = {key: value for key, value in signed.items() if key != "signoff"}
    assert render_spec.spec_is_signed_stage2(without_signoff) is False


def test_point_map_covers_size_labels() -> None:
    assert render_spec.POINT_MAP == {
        "S": (2, 2),
        "S-M": (2, 3),
        "M": (3, 3),
        "M-L": (3, 5),
        "L": (5, 5),
        "L-XL": (5, 8),
        "XL": (8, 8),
    }


def test_validate_comparison_reports_required_keys_and_types() -> None:
    logic = load_fixture_logic()
    errors, _ = render_spec.validate_comparison(load_fixture_comparison(), logic)
    assert errors == []

    broken = load_fixture_comparison()
    del broken["approaches"][0]["title"]
    broken["approaches"][1]["deploy"]["status"] = "maybe"
    broken["approaches"][2]["slices"][0]["band"] = "later"
    broken["approaches"][0]["repos"][0]["files"] = "7"
    broken["scores"]["REQ-01"]["A"]["history"] = [
        {"previous": {"status": "met"}, "challenge": "x", "reply": "y", "outcome": "ignored"}
    ]
    broken["guidance"]["recommendation"]["confidence"] = "certain"
    paths = [path for path, _ in render_spec.validate_comparison(broken, logic)[0]]
    for expected in (
        "/approaches/0/title",
        "/approaches/1/deploy/status",
        "/approaches/2/slices/0/band",
        "/approaches/0/repos/0/files",
        "/scores/REQ-01/A/history/0/outcome",
        "/guidance/recommendation/confidence",
    ):
        assert any(path.startswith(expected) for path in paths), (expected, paths)


def test_validate_comparison_rejects_non_ascii_repo_name() -> None:
    broken = load_fixture_comparison()
    broken["approaches"][0]["repos"][0]["name"] = "côre"
    paths = [path for path, _ in render_spec.validate_comparison(broken, load_fixture_logic())[0]]
    assert "/approaches/0/repos/0/name" in paths


def test_validate_comparison_rejects_non_object() -> None:
    errors, _ = render_spec.validate_comparison([], load_fixture_logic())
    assert errors and errors[0][0] == "/"


def test_load_comparison_v1_spec_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec_dir = tmp_path / "sample"
    spec_dir.mkdir()
    shutil.copy(COMPARE / "comparison.json", spec_dir / "comparison.json")
    assert render_spec.load_comparison(spec_dir, {"schemaVersion": 1}) == (None, None, 0)
    assert capsys.readouterr().err == ""


def test_v1_render_ignores_comparison(tmp_path: Path) -> None:
    spec_dir = tmp_path / "sample"
    spec_dir.mkdir()
    shutil.copy(SAMPLE / "logic.json", spec_dir / "logic.json")
    shutil.copy(COMPARE / "comparison.json", spec_dir / "comparison.json")
    result = run_cli("render", str(spec_dir))
    assert result.returncode == 0, result.stderr
    assert "comparison" not in result.stderr


APP_DIR = SCRIPT.parent / "app"
TSX = APP_DIR / "node_modules" / ".bin" / "tsx"
MUTATION_VALUES = (("{}", {}), ("[]", []), ("7", 7), ("-1", -1), ("1.5", 1.5), ('""', ""), ("null", None))


def _walk_paths(value: Any, path: tuple = ()):
    yield path
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_paths(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_paths(item, path + (index,))


def _replace_at(root: Any, path: tuple, replacement: Any) -> Any:
    if not path:
        return replacement
    mutant = json.loads(json.dumps(root))
    parent = mutant
    for part in path[:-1]:
        parent = parent[part]
    parent[path[-1]] = replacement
    return mutant


def _pointer_of(path: tuple) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)


@pytest.fixture(scope="module")
def comparison_mutants(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    """Every single-value replacement of the fixture comparison, each written to disk beside a manifest of Python's verdicts."""
    directory = tmp_path_factory.mktemp("comparison-mutants")
    logic = load_fixture_logic()
    base = load_fixture_comparison()
    entries = []
    for path in _walk_paths(base):
        for label, replacement in MUTATION_VALUES:
            mutant = _replace_at(base, path, replacement)
            if mutant == base:
                continue
            name = f"m{len(entries):05d}.json"
            (directory / name).write_text(json.dumps(mutant), encoding="utf-8")
            entry: Dict[str, Any] = {"file": name, "path": _pointer_of(path) or "/", "replacement": label}
            try:
                errors, _warnings = render_spec.validate_comparison(mutant, logic)
            except Exception as error:  # noqa: BLE001 - the sweep exists to catch any crash
                entry["crash"] = f"{type(error).__name__}: {error}"
            else:
                entry["accepted"] = not errors
                entry["pointer"] = errors[0][0] if errors else None
            entries.append(entry)
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({"mutants": entries}), encoding="utf-8")
    return {"directory": directory, "manifest": manifest, "entries": entries}


def test_validate_comparison_never_raises_on_replaced_values(comparison_mutants: Dict[str, Any]) -> None:
    entries = comparison_mutants["entries"]
    assert len(entries) > 1000
    crashes = [f"{entry['path']} -> {entry['replacement']}: {entry['crash']}" for entry in entries if "crash" in entry]
    assert crashes == [], crashes[:10]


@pytest.mark.skipif(not TSX.exists(), reason="app dependencies are not installed (pnpm install in the interactive app)")
def test_ts_guard_matches_python_verdict_on_replaced_values(comparison_mutants: Dict[str, Any]) -> None:
    result = subprocess.run(
        [str(TSX), "scripts/check-compare.ts", "--mutants", str(comparison_mutants["manifest"])],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
