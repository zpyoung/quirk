from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_filing_module, run_filing_script

BUG_FORM = """\
name: Bug Report
description: File a bug report
labels: ["bug", "needs-triage"]
body:
  - type: markdown
    attributes:
      value: Thanks for taking the time to file this!
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
    validations:
      required: true
  - type: textarea
    attributes:
      label: Steps To Reproduce
    validations:
      required: false
  - type: input
    id: version
    attributes:
      label: Version
    validations:
      required: true
"""

FEATURE_FORM = """\
name: Feature request
description: Suggest an idea
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem
    validations:
      required: false
  - type: textarea
    id: acceptance_criteria
    attributes:
      label: Acceptance criteria
    validations:
      required: false
"""

MARKDOWN_TEMPLATE = """\
---
name: Feature request
about: Suggest an idea
labels: enhancement
---

Some preamble prose.

## Problem

What are you trying to do?

## Expected behaviour

What should happen instead?
"""

BODILESS_FORM = """\
name: Just instructions
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: Please read the FAQ first.
"""

BODILESS_MARKDOWN = """\
---
name: Blank
---

No headings here, only prose.
"""

CONFIG_YML = """\
blank_issues_enabled: false
contact_links:
  - name: Community support
    url: https://example.invalid/chat
"""

# malformed under *both* tiers: an unterminated flow sequence. A fixture only the mini tier
# rejects would pass this test on any machine with PyYAML, which is where it least matters.
UNPARSABLE_FORM = """\
name: Broken
labels: ["bug"
body:
  - type: textarea
    id: what
    attributes:
      label: What
"""


@pytest.fixture(scope="module")
def template_resolve():
    return load_filing_module("template_resolve")


def _repo(tmp_path: Path, github: dict | None = None, gitlab: dict | None = None) -> Path:
    root = tmp_path / "repo"
    if github:
        target = root / ".github" / "ISSUE_TEMPLATE"
        target.mkdir(parents=True)
        for name, text in github.items():
            (target / name).write_text(text, encoding="utf-8")
    if gitlab:
        target = root / ".gitlab" / "issue_templates"
        target.mkdir(parents=True)
        for name, text in gitlab.items():
            (target / name).write_text(text, encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _paths(candidates: list) -> list:
    return [c["path"] for c in candidates]


# ---- discover: step 1 exclusions -------------------------------------------


def test_discover_returns_empty_for_a_repo_with_no_template_directories(
    template_resolve, tmp_path: Path,
) -> None:
    # a repo with no templates is not an error -- it is an empty candidate list
    root = _repo(tmp_path)
    candidates, warnings = template_resolve.discover(root)
    assert candidates == []
    assert warnings == []


def test_discover_never_treats_config_yml_as_a_candidate(template_resolve, tmp_path: Path) -> None:
    root = _repo(tmp_path, github={"config.yml": CONFIG_YML, "bug.yml": BUG_FORM})
    candidates, _ = template_resolve.discover(root)
    assert _paths(candidates) == [".github/ISSUE_TEMPLATE/bug.yml"]


def test_discover_excludes_a_yaml_form_with_no_non_markdown_body_element(
    template_resolve, tmp_path: Path,
) -> None:
    root = _repo(tmp_path, github={"instructions.yml": BODILESS_FORM, "bug.yml": BUG_FORM})
    candidates, _ = template_resolve.discover(root)
    assert _paths(candidates) == [".github/ISSUE_TEMPLATE/bug.yml"]


def test_discover_excludes_a_markdown_template_with_no_headings(
    template_resolve, tmp_path: Path,
) -> None:
    root = _repo(tmp_path, github={"blank.md": BODILESS_MARKDOWN, "feature.md": MARKDOWN_TEMPLATE})
    candidates, _ = template_resolve.discover(root)
    assert _paths(candidates) == [".github/ISSUE_TEMPLATE/feature.md"]


def test_discover_finds_gitlab_markdown_templates(template_resolve, tmp_path: Path) -> None:
    root = _repo(tmp_path, gitlab={"Feature.md": MARKDOWN_TEMPLATE})
    candidates, _ = template_resolve.discover(root)
    assert candidates[0]["kind"] == "gitlab-markdown"
    assert candidates[0]["path"] == ".gitlab/issue_templates/Feature.md"


def test_discover_records_declared_identity_for_classification(
    template_resolve, tmp_path: Path,
) -> None:
    root = _repo(tmp_path, github={"bug_report.yml": BUG_FORM})
    candidates, _ = template_resolve.discover(root)
    assert candidates[0] == {
        "path": ".github/ISSUE_TEMPLATE/bug_report.yml",
        "kind": "github-yaml",
        "name": "Bug Report",
        "labels": ["bug", "needs-triage"],
        "filename_stem": "bug_report",
    }


def test_discover_excludes_an_unparsable_file_without_aborting_the_sweep(
    template_resolve, tmp_path: Path,
) -> None:
    # the whole point of the per-file exclusion: one bad template must not cost the repo
    # every other template it has
    root = _repo(tmp_path, github={"broken.yml": UNPARSABLE_FORM, "bug.yml": BUG_FORM})
    candidates, warnings = template_resolve.discover(root)
    assert _paths(candidates) == [".github/ISSUE_TEMPLATE/bug.yml"]
    assert len(warnings) == 1
    assert "broken.yml" in warnings[0]


# ---- select: step 2/3 ------------------------------------------------------


def _candidate(name=None, labels=None, stem="template", path=None, kind="github-yaml") -> dict:
    return {
        "path": path or f".github/ISSUE_TEMPLATE/{stem}.yml",
        "kind": kind,
        "name": name,
        "labels": labels or [],
        "filename_stem": stem,
    }


@pytest.mark.parametrize(
    "request_type,name",
    [
        ("bug", "Bug Report"),
        ("bug", "Regression"),
        ("feature", "Feature request"),
        ("feature", "Enhancement proposal"),
        ("code-change", "Maintenance chore"),
        ("code-change", "Refactor"),
    ],
)
def test_select_matches_on_declared_name(template_resolve, request_type, name) -> None:
    result = template_resolve.select([_candidate(name=name)], request_type)
    assert result["resolution"] == "single"


def test_select_matches_on_labels(template_resolve) -> None:
    result = template_resolve.select([_candidate(name="Report a problem", labels=["defect"])], "bug")
    assert result["resolution"] == "single"


def test_select_matches_on_filename_stem_when_identity_is_silent(template_resolve) -> None:
    result = template_resolve.select([_candidate(name=None, stem="bug_report")], "bug")
    assert result["resolution"] == "single"
    assert result["template"]["filename_stem"] == "bug_report"


def test_select_prefers_declared_identity_over_a_filename_stem(template_resolve) -> None:
    # a stem-only match must never outvote a template that declares itself
    declared = _candidate(name="Bug Report", stem="one")
    stem_only = _candidate(name="Something else", stem="bug_two")
    result = template_resolve.select([declared, stem_only], "bug")
    assert result["resolution"] == "single"
    assert result["template"]["name"] == "Bug Report"


def test_select_returns_ambiguous_and_never_picks_silently(template_resolve) -> None:
    first = _candidate(name="Bug Report", stem="one")
    second = _candidate(name="Defect report", stem="two")
    result = template_resolve.select([first, second], "bug")
    assert result["resolution"] == "ambiguous"
    assert result["template"] is None
    assert result["ambiguous_candidates"] == [first, second]


def test_select_returns_none_when_nothing_matches(template_resolve) -> None:
    result = template_resolve.select([_candidate(name="Bug Report", stem="bug")], "feature")
    assert result == {"resolution": "none", "template": None, "ambiguous_candidates": []}


# ---- fields: the union-of-requiredness rule --------------------------------


def _fields_for(template_resolve, tmp_path: Path, filename: str, text: str, request_type: str):
    root = _repo(tmp_path, github={filename: text})
    candidates, _ = template_resolve.discover(root)
    candidate = candidates[0]
    parsed = template_resolve.parse_template(root / candidate["path"])
    return template_resolve.fields(request_type, parsed, candidate["kind"])


def _by_name(entries: list) -> dict:
    return {entry["name"]: entry for entry in entries}


def test_fields_no_template_returns_the_per_type_core_in_core_order(template_resolve) -> None:
    entries = template_resolve.fields("bug", None, None)
    assert entries == [
        {"name": "current_behavior", "required": True, "source": "core"},
        {"name": "expected_behavior", "required": True, "source": "core"},
        {"name": "steps_to_reproduce", "required": True, "source": "core"},
        {"name": "environment", "required": True, "source": "core"},
    ]


def test_fields_template_adds_a_field_the_core_does_not_have(
    template_resolve, tmp_path: Path,
) -> None:
    entries = _fields_for(template_resolve, tmp_path, "bug.yml", BUG_FORM, "bug")
    by_name = _by_name(entries)
    assert by_name["what_happened"] == {
        "name": "what_happened", "required": True, "source": "template",
    }
    assert by_name["version"]["source"] == "template"


def test_fields_core_field_the_template_omits_is_appended_after_its_sections(
    template_resolve, tmp_path: Path,
) -> None:
    entries = _fields_for(template_resolve, tmp_path, "bug.yml", BUG_FORM, "bug")
    names = [entry["name"] for entry in entries]
    # the template's own sections come first, in its order; the core is appended behind them
    assert names[:3] == ["what_happened", "steps_to_reproduce", "version"]
    assert set(names[3:]) == {"current_behavior", "expected_behavior", "environment"}
    for name in ("current_behavior", "expected_behavior", "environment"):
        assert _by_name(entries)[name] == {"name": name, "required": True, "source": "core"}


def test_fields_template_can_add_requirements_but_never_subtract_them(
    template_resolve, tmp_path: Path,
) -> None:
    # the form marks Steps To Reproduce `required: false`; it is a bug core field, so the
    # union forces it required anyway
    entries = _fields_for(template_resolve, tmp_path, "bug.yml", BUG_FORM, "bug")
    assert _by_name(entries)["steps_to_reproduce"]["required"] is True


def test_fields_non_waivable_override_fires_against_a_template_saying_otherwise(
    template_resolve, tmp_path: Path,
) -> None:
    entries = _fields_for(template_resolve, tmp_path, "feature.yml", FEATURE_FORM, "feature")
    by_name = _by_name(entries)
    assert by_name["problem"]["required"] is True
    assert by_name["acceptance_criteria"]["required"] is True


def test_fields_markdown_template_contributes_structure_but_no_requiredness(
    template_resolve, tmp_path: Path,
) -> None:
    entries = _fields_for(template_resolve, tmp_path, "feature.md", MARKDOWN_TEMPLATE, "feature")
    names = [entry["name"] for entry in entries]
    assert names[:2] == ["problem", "expected_behavior"]
    # `expected_behavior` is not in the feature core, so nothing forces it required, and a
    # markdown template has no mechanism to mark it
    assert _by_name(entries)["expected_behavior"] == {
        "name": "expected_behavior", "required": False, "source": "template",
    }


def test_fields_heading_synonyms_prevent_a_duplicate_of_a_core_field(
    template_resolve, tmp_path: Path,
) -> None:
    # "Expected behaviour" must not become a second field beside the core's
    # `expected_behavior`, asking the user the same question twice
    entries = _fields_for(template_resolve, tmp_path, "bug.md", MARKDOWN_TEMPLATE, "bug")
    names = [entry["name"] for entry in entries]
    assert "expected_behaviour" not in names
    assert names.count("expected_behavior") == 1


def test_fields_yaml_id_wins_over_the_label_for_the_canonical_name(
    template_resolve, tmp_path: Path,
) -> None:
    entries = _fields_for(template_resolve, tmp_path, "feature.yml", FEATURE_FORM, "feature")
    names = [entry["name"] for entry in entries]
    assert "acceptance_criteria" in names
    assert "acceptance_criteria_" not in names


def test_fields_static_markdown_elements_are_never_candidate_fields(
    template_resolve, tmp_path: Path,
) -> None:
    entries = _fields_for(template_resolve, tmp_path, "bug.yml", BUG_FORM, "bug")
    assert not any("thanks" in entry["name"] for entry in entries)


# ---- CLI contract ----------------------------------------------------------


def test_cli_discover_reports_candidates_and_the_active_yaml_tier(tmp_path: Path) -> None:
    root = _repo(tmp_path, github={"bug.yml": BUG_FORM, "config.yml": CONFIG_YML})
    result = run_filing_script(
        "template_resolve.py", "discover", "--repo-root", str(root), cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["yaml_tier"] in ("pyyaml", "mini")
    assert _paths(payload["candidates"]) == [".github/ISSUE_TEMPLATE/bug.yml"]


def test_cli_discover_on_a_missing_repo_root_exits_2(tmp_path: Path) -> None:
    result = run_filing_script(
        "template_resolve.py", "discover", "--repo-root", str(tmp_path / "nope"), cwd=tmp_path,
    )
    assert result.returncode == 2


def test_cli_discover_warns_on_stderr_for_an_excluded_unparsable_file(tmp_path: Path) -> None:
    root = _repo(tmp_path, github={"broken.yml": UNPARSABLE_FORM, "bug.yml": BUG_FORM})
    result = run_filing_script(
        "template_resolve.py", "discover", "--repo-root", str(root), cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "broken.yml" in result.stderr
    assert len(json.loads(result.stdout)["candidates"]) == 1


@pytest.mark.parametrize("resolution", ["single", "ambiguous", "none"])
def test_cli_select_exits_0_for_every_resolution(tmp_path: Path, resolution: str) -> None:
    # "ambiguous" and "none" are outcomes the caller must act on, not error states
    sets = {
        "single": [_candidate(name="Bug Report", stem="bug")],
        "ambiguous": [_candidate(name="Bug Report", stem="a"), _candidate(name="Defect", stem="b")],
        "none": [_candidate(name="Feature request", stem="feature")],
    }
    result = run_filing_script(
        "template_resolve.py", "select", "--candidates", "-", "--type", "bug",
        cwd=tmp_path, stdin=json.dumps(sets[resolution]),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["resolution"] == resolution


def test_cli_select_accepts_discover_output_verbatim(tmp_path: Path) -> None:
    root = _repo(tmp_path, github={"bug.yml": BUG_FORM})
    discovered = run_filing_script(
        "template_resolve.py", "discover", "--repo-root", str(root), cwd=tmp_path,
    )
    result = run_filing_script(
        "template_resolve.py", "select", "--candidates", "-", "--type", "bug",
        cwd=tmp_path, stdin=discovered.stdout,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["resolution"] == "single"


def test_cli_fields_no_template_returns_the_core(tmp_path: Path) -> None:
    result = run_filing_script(
        "template_resolve.py", "fields", "--type", "feature", "--no-template", cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    entries = json.loads(result.stdout)
    assert all(entry["source"] == "core" for entry in entries)
    assert [entry["name"] for entry in entries] == [
        "problem", "who_benefits", "current_behavior", "acceptance_criteria",
    ]


def test_cli_fields_from_a_selected_template(tmp_path: Path) -> None:
    root = _repo(tmp_path, github={"bug.yml": BUG_FORM})
    discovered = json.loads(run_filing_script(
        "template_resolve.py", "discover", "--repo-root", str(root), cwd=tmp_path,
    ).stdout)
    result = run_filing_script(
        "template_resolve.py", "fields", "--type", "bug", "--template", "-",
        "--repo-root", str(root), cwd=tmp_path,
        stdin=json.dumps(discovered["candidates"][0]),
    )
    assert result.returncode == 0, result.stderr
    names = [entry["name"] for entry in json.loads(result.stdout)]
    assert names[0] == "what_happened"


def test_cli_fields_requires_exactly_one_of_template_or_no_template(tmp_path: Path) -> None:
    result = run_filing_script("template_resolve.py", "fields", "--type", "bug", cwd=tmp_path)
    assert result.returncode == 2


# ---- the mini tier serves discovery identically ----------------------------


def test_discover_and_fields_agree_across_both_yaml_tiers(
    template_resolve, tmp_path: Path, monkeypatch,
) -> None:
    # the guarantee `yaml_tier` exists to make visible: a machine without PyYAML must
    # resolve the same templates into the same field set.
    root = _repo(tmp_path, github={"bug.yml": BUG_FORM, "feature.md": MARKDOWN_TEMPLATE})
    with_pyyaml = template_resolve.discover(root)

    import sys

    monkeypatch.setitem(sys.modules, "yaml", None)
    forced_mini = load_filing_module("_yaml_mini")
    assert forced_mini.YAML_TIER == "mini"
    monkeypatch.setattr(template_resolve, "_yaml_mini", forced_mini)
    without_pyyaml = template_resolve.discover(root)

    assert without_pyyaml == with_pyyaml


# ---- production-review round 2 -------------------------------------------


FENCED_MARKDOWN = """\
---
name: Bug report
labels: bug
---

## What happened

Describe it.

```
## Not a real section
  File "x.py", line 1
```

## Environment
"""

DUPLICATE_HEADINGS = """\
---
name: Bug report
labels: bug
---

## Client
### Version
## Server
### Version
"""

STRING_REQUIRED_FORM = """\
name: Bug Report
labels: ["bug"]
body:
  - type: textarea
    id: optional_notes
    attributes:
      label: Notes
    validations:
      required: "false"
"""


def test_headings_inside_a_fenced_block_are_not_sections(
    template_resolve, tmp_path: Path,
) -> None:
    # a template showing example output is displaying text, not declaring a section
    entries = _fields_for(template_resolve, tmp_path, "bug.md", FENCED_MARKDOWN, "bug")
    names = [entry["name"] for entry in entries]
    assert "not_a_real_section" not in names
    assert names[:2] == ["what_happened", "environment"]


def test_two_sections_that_slug_alike_both_survive(template_resolve, tmp_path: Path) -> None:
    # a template asking for a client version and a server version is asking twice; collapsing
    # them by name silently drops the maintainer's second question
    entries = _fields_for(template_resolve, tmp_path, "bug.md", DUPLICATE_HEADINGS, "bug")
    names = [entry["name"] for entry in entries]
    assert names[:4] == ["client", "version", "server", "version_2"]


def test_non_boolean_required_is_not_truthiness_coerced(
    template_resolve, tmp_path: Path,
) -> None:
    # `validations.required` is a YAML boolean; `"false"` is schema-invalid and coercing it
    # makes the template add a requirement it explicitly declined to add
    entries = _fields_for(template_resolve, tmp_path, "bug.yml", STRING_REQUIRED_FORM, "bug")
    assert _by_name(entries)["optional_notes"]["required"] is False


def test_filename_stem_narrows_two_identity_matches_rather_than_widening(
    template_resolve,
) -> None:
    # both declare themselves as bug templates; the stem is the tie-break the ordered rule
    # specifies, so this settles rather than asking the user
    candidates = [
        _candidate(name="Bug Report", stem="bug"),
        _candidate(name="Defect Report", stem="question"),
    ]
    result = template_resolve.select(candidates, "bug")
    assert result["resolution"] == "single"
    assert result["template"]["filename_stem"] == "bug"


def test_a_stem_only_candidate_never_outvotes_two_self_declaring_templates(
    template_resolve,
) -> None:
    # narrowing must stay inside the identity matches -- a candidate that declared nothing
    # cannot win over templates that did
    candidates = [
        _candidate(name="Bug Report", stem="one"),
        _candidate(name="Defect Report", stem="two"),
        _candidate(name="Support question", stem="bug_ish"),
    ]
    result = template_resolve.select(candidates, "bug")
    assert result["resolution"] == "ambiguous"
    assert [c["name"] for c in result["ambiguous_candidates"]] == ["Bug Report", "Defect Report"]
