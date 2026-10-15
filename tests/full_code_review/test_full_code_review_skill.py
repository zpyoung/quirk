import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "full-code-review"
SKILL_MD = SKILL_DIR / "SKILL.md"
LENSES = SKILL_DIR / "references" / "lenses"
RUN_WHEN = {"always", "has_description", "code_changed", "source_or_config_changed",
            "tests_changed", "source_without_tests", "not_diff_only"}
MODELS = {"sonnet", "opus", "haiku"}


def _front_matter(text):
    # flat key: value front matter only; the lens files never nest
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    assert match, "missing front matter"
    pairs = (line.split(":", 1) for line in match.group(1).splitlines() if line.strip())
    return {key.strip(): value.strip() for key, value in pairs}


def _lens_ids():
    return sorted(p.stem for p in LENSES.glob("*.md") if not p.name.startswith("_"))


def test_skill_md_stays_within_the_line_budget():
    assert len(SKILL_MD.read_text(encoding="utf-8").splitlines()) <= 500


def test_skill_name_matches_its_directory():
    assert _front_matter(SKILL_MD.read_text(encoding="utf-8"))["name"] == SKILL_DIR.name


def test_every_bundled_path_skill_md_names_exists():
    text = SKILL_MD.read_text(encoding="utf-8")
    roots = {"$SCRIPTS": SKILL_DIR / "scripts", "$REFS": SKILL_DIR / "references"}
    referenced = re.findall(r"(\$SCRIPTS|\$REFS)/([A-Za-z0-9_./-]+)", text)
    assert referenced
    missing = [root + "/" + rel for root, rel in referenced
               if "<" not in rel and not (roots[root] / rel.rstrip(".")).exists()]
    assert missing == []


def test_every_lens_has_valid_front_matter():
    assert len(_lens_ids()) == 14
    for lens_id in _lens_ids():
        meta = _front_matter((LENSES / (lens_id + ".md")).read_text(encoding="utf-8"))
        assert meta["id"] == lens_id
        assert meta["run_when"] in RUN_WHEN, lens_id
        assert meta["model"] in MODELS, lens_id
        assert meta["escalate"] in {"true", "false"}, lens_id
        assert meta["batched"] in {"true", "false"}, lens_id


def test_memory_roster_and_orchestration_table_match_the_lens_files():
    skill = SKILL_MD.read_text(encoding="utf-8")
    assert sorted(set(re.findall(r"--dimension ([a-z-]+)", skill))) == _lens_ids()
    orchestration = (SKILL_DIR / "references" / "orchestration.md").read_text(encoding="utf-8")
    table = re.findall(r"^\| `([a-z-]+)` \| (?:sonnet|opus|haiku)", orchestration, re.M)
    assert sorted(table) == _lens_ids()
