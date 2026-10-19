import fnmatch
import re
from pathlib import Path

import resolve_policy

REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / "skills" / "full-code-review"
SKILL_MD = SKILL_DIR / "SKILL.md"
LENSES = SKILL_DIR / "references" / "lenses"
RUN_WHEN = {"always", "has_description", "code_changed", "source_or_config_changed",
            "tests_changed", "source_without_tests", "not_diff_only"}
MODELS = {"sonnet", "opus", "haiku"}
LENS_COUNT = 14
DEEP_PROMPTS = ("_area-finder", "_contract", "_checker")


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


def test_deep_flag_routes_to_its_runbook_without_expanding_the_skill():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "[--deep [minutes]]" in _front_matter(text)["argument-hint"]
    assert "| `--deep [minutes]` |" in text
    assert "$REFS/deep.md" in text
    for script in ("deep_sandbox.py", "build_area_map.py", "merge_deep_findings.py",
                   "score_deep_report.py"):
        assert "$SCRIPTS/" + script not in text
    for lens_id in ("_area-finder", "_contract", "_checker"):
        assert "$REFS/lenses/" + lens_id + ".md" not in text


def test_deep_prompts_are_separate_from_the_standard_lens_roster():
    assert not set(DEEP_PROMPTS) & set(_lens_ids())
    for lens_id, escalation in (("_area-finder", "false"), ("_contract", "false"),
                                ("_checker", "true")):
        path = LENSES / (lens_id + ".md")
        assert path.is_file(), path
        meta = _front_matter(path.read_text(encoding="utf-8"))
        assert meta["id"] == lens_id
        assert meta["model"] == "sonnet"
        assert meta["escalate"] == escalation


def test_deep_runbook_and_report_guidance_cover_verification_and_delivery():
    refs = SKILL_DIR / "references"
    runbook = (refs / "deep.md").read_text(encoding="utf-8")
    for path in ("deep_sandbox.py", "build_area_map.py", "merge_deep_findings.py",
                 "score_deep_report.py"):
        assert "$SCRIPTS/" + path in runbook
    for lens_id in ("_area-finder", "_contract", "_checker"):
        assert "$REFS/lenses/" + lens_id + ".md" in runbook
    for term in ("check-trust", "acquire", "release", "80%", "unreached",
                 "checked_and_dropped", "plausible"):
        assert term in runbook
    for filename in ("html-report.md", "report-template.md", "posting.md",
                     "degradation.md"):
        text = (refs / filename).read_text(encoding="utf-8")
        assert "verification_status" in text, filename
        assert "plausible" in text, filename
        assert "checked_and_dropped" in text, filename


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
    assert len(_lens_ids()) == LENS_COUNT
    for lens_id in _lens_ids():
        meta = _front_matter((LENSES / (lens_id + ".md")).read_text(encoding="utf-8"))
        assert meta["id"] == lens_id
        assert meta["run_when"] in RUN_WHEN, lens_id
        assert meta["model"] in MODELS, lens_id
        assert meta["escalate"] in {"true", "false"}, lens_id
        assert meta["batched"] in {"true", "false"}, lens_id


def test_memory_roster_and_orchestration_table_match_the_lens_files():
    skill = SKILL_MD.read_text(encoding="utf-8")
    assert re.findall(r"--dimension ([a-z-]+)", skill) == []
    assert "d['lenses']+d['skipped']" in skill
    orchestration = (SKILL_DIR / "references" / "orchestration.md").read_text(encoding="utf-8")
    table = re.findall(r"^\| `([a-z-]+)` \| (?:sonnet|opus|haiku)", orchestration, re.M)
    assert sorted(table) == _lens_ids()


def test_every_lens_opens_with_its_id_and_dimension():
    for lens_id in _lens_ids():
        text = (LENSES / (lens_id + ".md")).read_text(encoding="utf-8")
        assert "You are the `%s` lens" % lens_id in text, lens_id
        if lens_id != "risk":  # risk returns a rating block, not findings
            assert '`dimension: "%s"`' % lens_id in text, lens_id


def test_report_template_sections_match_the_markdown_renderer():
    template = (SKILL_DIR / "references" / "report-template.md").read_text(encoding="utf-8")
    outside_fences = re.sub(r"^```.*?^```", "", template, flags=re.S | re.M)
    headings = re.findall(r"^## (\d+)\. (.+)$", outside_fences, re.M)
    assert headings == [("1", "Summary"), ("2", "Risk Assessment"), ("3", "Findings"),
                        ("4", "Assumptions"), ("5", "Recommendations")]


def test_claim_table_is_routed_to_process_notes_not_a_section():
    for path in (SKILL_MD, SKILL_DIR / "references" / "report-template.md",
                 LENSES / "adversarial.md"):
        text = path.read_text(encoding="utf-8")
        assert "Claim Verification section" not in text, path.name
        assert "process_notes" in text, path.name


def _documented_script_commands():
    texts = [SKILL_DIR / "references" / "deep.md"] + [LENSES / (name + ".md") for name in DEEP_PROMPTS]
    for path in texts:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'python3 "\$SCRIPTS/(\w+)\.py"([^`]*?)(?=python3 "\$SCRIPTS/|`|\Z)', text, re.S):
            command = match.group(2).split(" -- ")[0]
            yield path.name, match.group(1), command


def test_deep_commands_use_subcommands_and_flags_the_scripts_define():
    commands = list(_documented_script_commands())
    assert {script for _, script, _ in commands} >= {"deep_sandbox", "build_area_map", "merge_deep_findings"}
    for doc, script, command in commands:
        source = (SKILL_DIR / "scripts" / (script + ".py")).read_text(encoding="utf-8")
        for flag in re.findall(r"(?<!\S)--([a-z][a-z-]*)", command):
            assert '"--%s"' % flag in source or '"%s"' % flag in source, (doc, script, flag)
        if script == "deep_sandbox":
            subcommand = command.split()[0]
            assert 'add_parser("%s")' % subcommand in source, (doc, subcommand)


ZSH_GUIDANCE = "bash <file>"


def test_deep_runbook_documents_coverage_planning_and_hunk_tracking():
    runbook = (SKILL_DIR / "references" / "deep.md").read_text(encoding="utf-8")
    for term in ("examined", "capacity", "hunks", "--budget-minutes", "--concurrency",
                 "--elapsed-minutes", "hunkless_files", "priority", "id_prefix", "skip_globs"):
        assert term in runbook, term


def test_area_finder_prompt_takes_hunks_and_returns_examined_ids():
    text = (LENSES / "_area-finder.md").read_text(encoding="utf-8")
    for term in ("examined", "id_prefix", "hunks", "angle"):
        assert term in text, term
    assert '"hunk": "A1.h1"' in text


def test_skill_md_exposes_the_since_flag():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "[--since <ref>]" in _front_matter(text)["argument-hint"]
    assert "| `--since <ref>` |" in text
    assert "run.since" in text


def test_shell_guidance_reaches_every_agent_prompt():
    paths = [LENSES / (name + ".md") for name in DEEP_PROMPTS]
    paths.append(SKILL_DIR / "references" / "orchestration.md")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "zsh" in text, path.name
        assert ZSH_GUIDANCE in text, path.name


def _flat(path):
    # prose wraps at ~90 columns, so phrase checks must not depend on where lines break
    return " ".join(path.read_text(encoding="utf-8").split())


def test_test_adequacy_checks_values_handed_between_functions():
    text = _flat(LENSES / "test-adequacy.md")
    assert "through the caller" in text
    assert "supplied by hand" in text


def test_mutation_guidance_includes_the_call_site_mutant():
    for name in ("_mutation-probe", "_area-finder"):
        text = _flat(LENSES / (name + ".md"))
        assert "at the call site" in text, name
        assert "`None`" in text, name


def test_every_lens_is_told_to_work_through_its_whole_checklist():
    for path in (SKILL_DIR / "references" / "orchestration.md", SKILL_MD):
        assert "every item of its checklist" in _flat(path), path.name


def test_small_diffs_still_get_the_full_fan_out_and_report():
    # headless runs reviewed 2-9 line diffs inline and wrote no report.json
    skill = _flat(SKILL_MD)
    assert "Diff size never shortens the run" in skill
    assert "never review the diff inline" in skill
    assert "one `Agent` per lens" in skill
    # the lenses that skipped named diff size and headless mode as their reason
    assert "a headless run" in skill and "never a skip reason" in skill


def test_setup_keeps_a_caller_set_review_out_dir():
    skill = _flat(SKILL_MD)
    assert "Run this block verbatim" in skill
    assert "a caller that sets `REVIEW_OUT_DIR` reads the report there" in skill


def test_cross_repo_scan_keeps_the_caller_parent_as_a_sibling_root():
    skill = _flat(SKILL_MD)
    assert "parent directory of the caller's checkout" in skill
    assert "never replace it" in skill
    assert "extra roots" in _flat(LENSES / "cross-repo.md")


def test_degradation_table_covers_coverage_and_delta_paths():
    text = (SKILL_DIR / "references" / "degradation.md").read_text(encoding="utf-8")
    for term in ("over capacity", "unexamined", "time budget", "--since"):
        assert term in text, term


def test_report_docs_describe_delta_and_hunk_fields():
    refs = SKILL_DIR / "references"
    schema = (refs / "html-report.md").read_text(encoding="utf-8")
    for term in ("run.since", "hunks", "examined", "hunkless_files", "priority",
                 "unexamined", "hunk_coverage", "--since"):
        assert term in schema, term
    template = (refs / "report-template.md").read_text(encoding="utf-8")
    assert "since" in template and "unexamined" in template


def test_repo_review_md_excludes_the_answer_keys():
    path = REPO / "REVIEW.md"
    settings, body = resolve_policy.split_front_matter(path.read_text(encoding="utf-8"), "REVIEW.md")
    answer_key = next((REPO / "tests" / "fixtures" / "full-code-review" / "answer-keys").glob("*.json"))
    relative = answer_key.relative_to(REPO).as_posix()
    assert any(fnmatch.fnmatch(relative, pattern) for pattern in settings["skip_globs"])
    assert body.strip()
