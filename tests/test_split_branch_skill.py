import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "split-branch" / "SKILL.md"
SCRIPT_DIR = SKILL_PATH.parent / "scripts"


def skill_text() -> str:
    return SKILL_PATH.read_text()


def test_frontmatter_names_skill_and_describes_triggers() -> None:
    text = skill_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match
    frontmatter = match.group(1)
    assert re.search(r"^name:\s*split-branch\s*$", frontmatter, re.MULTILINE)
    description = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE).group(1)
    assert len(description) >= 50
    assert re.search(r"split(?:ting)? (?:a |an )?(?:PR|MR|branch)", description, re.IGNORECASE)
    assert re.search(r"make|making", description, re.IGNORECASE)
    assert re.search(r"PR smaller", description, re.IGNORECASE)


def test_strategies_and_probe_are_documented() -> None:
    text = skill_text()
    for phrase in ("MVP-first vertical", "layer-first", "--vertical", "--layers", "auto-detect"):
        assert phrase.lower() in text.lower()
    for phrase in ("entry point", "route", "handler", "CLI command", "event registration", "compile closure", "cap"):
        assert phrase.lower() in text.lower()
    assert re.search(r"recommend.*layer-first", text, re.IGNORECASE)
    assert re.search(r"name.*blocker", text, re.IGNORECASE)


def test_grouping_contract_and_intent_vocabulary() -> None:
    text = skill_text()
    assert "file-first" in text.lower()
    assert re.search(r"hunk.*conflicting intent tags", text, re.IGNORECASE)
    assert re.search(r"dependency graph.*orders and validates but never groups", text, re.IGNORECASE)
    vocabulary = (
        "FEATURE-CORE", "FEATURE-VARIANT", "VALIDATION", "ERROR-HANDLING",
        "PERF", "REFACTOR/PREFACTOR", "CONFIG-INFRA", "TEST", "DOCS",
        "COSMETIC", "UNRELATED",
    )
    for tag in vocabulary:
        assert tag in text


def test_deferral_ladder_and_never_defer_set() -> None:
    text = skill_text()
    assert "deferral ladder" in text.lower()
    assert "never defer" in text.lower()
    for phrase in ("entry point", "state change", "outcome observable", "one proving test"):
        assert phrase in text.lower()


def test_single_gate_plan_path_and_pipeline() -> None:
    text = skill_text()
    assert re.search(r"exactly one|single.*approval gate", text, re.IGNORECASE)
    assert ".git/split-branch/<branch>.plan.md" in text
    pipeline = "pre-flight → analyze → label → probe → group → plan → GATE → materialize → verify → conserve → publish"
    assert pipeline in text


def test_all_guardrails_are_rules_with_reasons() -> None:
    text = skill_text()
    required = (
        "Never pass `--recount` to `git apply`",
        "Never use `git apply --check` as a pre-flight",
        "Never use `--check --3way`",
        "Generate grouping diffs at `-U0` only",
        "Never use `--unidiff-zero` against a drifted tree",
        "dedicated `git worktree` per slice",
        "Never use a `git checkout` loop",
        "Conservation compares trees",
        "Never compare diff-of-diffs",
        "`git push --force-with-lease`",
        "Never use bare `--force`",
        "Never hardcode `origin`",
        "`--remote`",
        "`remote.pushDefault`",
        "fall back to `origin`",
        "No interactive commands",
        "`--3way` requires `--full-index`",
        "mutually exclusive with `--reject`",
    )
    for phrase in required:
        assert phrase.lower() in text.lower()
    guardrail_section = re.search(r"## Guardrails(.*?)(?=\n## )", text, re.DOTALL | re.IGNORECASE)
    assert guardrail_section
    assert guardrail_section.group(1).count(" — ") >= 12, "each guardrail should state its reason"


def test_fallbacks_are_documented() -> None:
    text = skill_text()
    assert re.search(r"commit-boundary.*hunk surgery.*blocked", text, re.IGNORECASE)
    assert re.search(r"merge cycling slices.*dependency cycle", text, re.IGNORECASE)
    assert re.search(r"refuse.*(?:under|<).*200 weighted", text, re.IGNORECASE)


def test_script_reference_is_complete_and_obsolete_script_is_retired() -> None:
    text = skill_text()
    for script in ("analyze.sh", "slice.sh", "verify.sh", "publish.sh", "restack.sh", "stackmeta.sh"):
        assert re.search(rf"`{re.escape(script)}`[^\n]+ — [^\n]+", text)
    obsolete_name = "extract" + ".sh"
    assert obsolete_name not in text
    assert not (SCRIPT_DIR / obsolete_name).exists()


def test_forge_gotchas_are_documented() -> None:
    text = skill_text()
    assert re.search(r"GitLab never auto-retargets fork MRs", text, re.IGNORECASE)
    assert re.search(r"Delete source branch.*suppress(?:es|ing) retargeting", text, re.IGNORECASE)
    assert re.search(r"squash and rebase both rewrite SHAs", text, re.IGNORECASE)


def test_build_and_test_discovery_ladder_is_in_order_and_skill_side() -> None:
    text = skill_text()
    phrases = (
        "explicit value already recorded for this repo",
        "convention detection",
        "Makefile",
        "package.json",
        "pyproject.toml",
        "pytest",
        "cargo",
        "go test",
        "repo's CI config",
        "ask the user once",
        "record the answer in the plan file",
    )
    positions = [text.lower().index(phrase.lower()) for phrase in phrases]
    assert positions == sorted(positions)
    assert re.search(r"script-side auto-detection.*out of scope", text, re.IGNORECASE)
    assert re.search(r"skill.*passes.*verify\.sh", text, re.IGNORECASE)


def test_slice_ordering_sizing_and_bottom_bar() -> None:
    text = skill_text()
    assert re.search(r"leftovers.*prep slice.*below.*MVP slice", text, re.IGNORECASE)
    assert re.search(r"#2\.\.N.*descending user-facing value", text, re.IGNORECASE)
    assert re.search(r"coherence beats line targets.*600-line hard cap", text, re.IGNORECASE)
    assert "green + mergeable + main stays releasable" in text
    assert re.search(r"MVP-first.*strong default.*not.*validity gate", text, re.IGNORECASE)
