from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

import pm

from .conftest import TEMPLATES_DIR, run_pm


# --- fixtures: appending entries with arbitrary fields ----------------------


def _append(project: Path, filename: str, header: str, entry_id: int, title: str, fields: dict[str, str]) -> None:
    path = project / filename
    lines = [f"\n## {header}-{entry_id}: {title}"]
    for label, value in fields.items():
        lines.append(f"- **{label}**: {value}")
    path.write_text(path.read_text() + "\n".join(lines) + "\n")


def append_bug(project: Path, entry_id: int, title: str = "bug", **fields: str) -> None:
    _append(project, "BUGS.md", "BUG", entry_id, title, fields)


def append_defer(project: Path, entry_id: int, title: str = "defer", **fields: str) -> None:
    _append(project, "DEFERRED.md", "DEFER", entry_id, title, fields)


def append_test(project: Path, entry_id: int, title: str = "test", **fields: str) -> None:
    _append(project, "TEST_BACKLOG.md", "TEST", entry_id, title, fields)


def append_proposal(project: Path, entry_id: int, title: str = "proposal", **fields: str) -> None:
    _append(project, "proposals.md", "PROPOSAL", entry_id, title, fields)


SHA = "a" * 40
STATUS_IN_PROGRESS = "in_progress — 2026-08-05 — attempt 1"
STATUS_DELIVERED = f"delivered — 2026-08-05 — attempt 1 — commit: {SHA}"
STATUS_CLOSED = f"closed — 2026-08-06 — attempt 1 — integrated: {SHA}"
STATUS_WONTFIX = "wontfix — 2026-08-05 — attempt 1 — reason: not worth it"
STATUS_SUPERSEDED = "superseded — 2026-08-05 — attempt 1 — by: BUG-99 — reason: folded in"
STATUS_MALFORMED = "bogus_state — 2026-08-05"


# --- urgency: the full table ------------------------------------------------


@pytest.mark.parametrize("severity,expected", [
    ("critical", 0), ("high", 1), ("medium", 2), ("low", 3),
])
def test_urgency_severity_table(severity: str, expected: int) -> None:
    assert pm._urgency(pm.BACKLOG_FILES[0], {"Severity": severity}) == expected


@pytest.mark.parametrize("priority,expected", [
    ("P1", 0), ("P2", 1), ("P3", 2), ("P4", 3),
])
def test_urgency_priority_table(priority: str, expected: int) -> None:
    assert pm._urgency(pm.BACKLOG_FILES[1], {"Priority": priority}) == expected
    assert pm._urgency(pm.BACKLOG_FILES[2], {"Priority": priority}) == expected


def test_urgency_defaults_to_2_when_field_missing() -> None:
    assert pm._urgency(pm.BACKLOG_FILES[0], {}) == 2
    assert pm._urgency(pm.BACKLOG_FILES[1], {}) == 2


def test_urgency_defaults_to_2_when_value_unrecognized() -> None:
    assert pm._urgency(pm.BACKLOG_FILES[0], {"Severity": "urgent!!"}) == 2
    assert pm._urgency(pm.BACKLOG_FILES[1], {"Priority": "P9"}) == 2


def test_urgency_proposals_have_no_scale_and_default_to_2() -> None:
    assert pm._urgency(pm.PROPOSALS, {}) == 2
    assert pm._urgency(pm.PROPOSALS, {"Severity": "critical"}) == 2


# --- unplaced: ready / blocked / malformed breakdown ------------------------


def test_unplaced_breaks_out_ready_blocked_malformed(pm_project: Path) -> None:
    append_bug(pm_project, 1, "ready one", Severity="high", Observed="2026-08-01")
    append_bug(pm_project, 2, "blocked one", Severity="high", Observed="2026-08-01", **{"Blocked by": "BUG-3"})
    append_bug(pm_project, 3, "unrelated open bug", Severity="low", Observed="2026-01-01")
    bugs = pm_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-9:\n- **Severity**: high\n")

    result = run_pm("--next", cwd=pm_project)
    assert result.returncode == 0, result.stderr
    assert "4 unplaced (2 ready, 1 blocked, 1 malformed)" in result.stdout


def test_unplaced_excludes_entries_already_in_a_milestone(pm_project: Path) -> None:
    append_bug(pm_project, 1, "placed", Severity="high", Observed="2026-08-01")
    roadmap_path = pm_project / "ROADMAP.md"
    roadmap_path.write_text(roadmap_path.read_text() + "\n## Milestone: M1\n- BUG-1\n")

    result = run_pm("--next", cwd=pm_project)
    assert result.returncode == 0, result.stderr
    assert "0 unplaced (0 ready, 0 blocked, 0 malformed)" in result.stdout


# --- the -1 milestone-rank escape hatch --------------------------------------


def test_unroadmapped_entry_sorts_ahead_of_a_milestoned_entry(pm_project: Path) -> None:
    """BUG-1 is unroadmapped but eligible via urgency<=1; DEFER-1 is milestoned and *more*
    urgent. Rank must still dominate urgency in the sort key, or this fails."""
    append_bug(pm_project, 1, "unroadmapped high", Severity="high", Observed="2026-01-01")
    append_defer(pm_project, 1, "milestoned critical", Priority="P1", Deferred="2026-01-01")
    roadmap_path = pm_project / "ROADMAP.md"
    roadmap_path.write_text(roadmap_path.read_text() + "\n## Milestone: M1\n- DEFER-1\n")

    result = run_pm("--next", cwd=pm_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.index("BUG-1") < out.index("DEFER-1")


def test_eligible_requires_milestone_membership_or_low_urgency(pm_project: Path) -> None:
    append_bug(pm_project, 1, "urgent enough", Severity="high", Observed="2026-01-01")
    append_bug(pm_project, 2, "not urgent enough", Severity="low", Observed="2026-01-01")
    world = pm._load_ledger_world(pm_project)
    ranks = pm._milestone_ranks(pm._read_roadmap(pm_project))
    assert pm.eligible(world, ranks, "BUG-1") is True
    assert pm.eligible(world, ranks, "BUG-2") is False


# --- ties: ID ordinal, then type name ---------------------------------------


def test_ties_break_on_id_ordinal_then_type_name(pm_project: Path) -> None:
    append_bug(pm_project, 1, "b", Severity="critical", Observed="2026-01-01")
    append_defer(pm_project, 1, "d", Priority="P1", Deferred="2026-01-01")
    append_test(pm_project, 1, "t", Priority="P1", Logged="2026-01-01")

    result = run_pm("--next", cwd=pm_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.index("BUG-1") < out.index("DEFER-1") < out.index("TEST-1")


# --- Blocked by: lexical rules, in full -------------------------------------


def test_blocked_by_absent_field_means_no_blockers() -> None:
    field = pm.parse_blocked_by("")
    assert field.tokens == ()
    assert field.truncated is False


def test_blocked_by_valid_comma_separated_list() -> None:
    field = pm.parse_blocked_by("BUG-3, DEFER-7")
    assert [t.id for t in field.tokens] == ["BUG-3", "DEFER-7"]
    assert all(t.kind == "id" for t in field.tokens)


def test_blocked_by_strips_whitespace_only_at_token_boundaries() -> None:
    field = pm.parse_blocked_by("  BUG-3 ,  DEFER-7  ")
    assert [t.id for t in field.tokens] == ["BUG-3", "DEFER-7"]


def test_blocked_by_semicolon_joined_list_is_one_malformed_token() -> None:
    field = pm.parse_blocked_by("BUG-3;BUG-7")
    assert len(field.tokens) == 1
    assert field.tokens[0].kind == "malformed"


def test_blocked_by_internal_whitespace_is_malformed() -> None:
    field = pm.parse_blocked_by("BUG - 3")
    assert len(field.tokens) == 1
    assert field.tokens[0].kind == "malformed"


def test_blocked_by_lowercase_header_is_malformed() -> None:
    field = pm.parse_blocked_by("bug-3")
    assert field.tokens[0].kind == "malformed"


def test_blocked_by_leading_zero_is_malformed() -> None:
    field = pm.parse_blocked_by("BUG-007")
    assert field.tokens[0].kind == "malformed"


def test_blocked_by_non_ascii_digit_is_malformed() -> None:
    field = pm.parse_blocked_by("BUG-٣")  # Arabic-Indic three
    assert field.tokens[0].kind == "malformed"


def test_blocked_by_duplicate_ids_deduped_for_satisfaction_and_reported() -> None:
    field = pm.parse_blocked_by("BUG-3, BUG-3")
    assert [t.id for t in field.tokens] == ["BUG-3", "BUG-3"]
    assert field.duplicate_ids == ("BUG-3",)


def test_blocked_by_proposal_reference_is_its_own_kind() -> None:
    field = pm.parse_blocked_by("PROPOSAL-5")
    assert field.tokens[0].kind == "proposal"


def test_blocked_by_self_reference_never_reads_as_ready(pm_project: Path) -> None:
    append_bug(pm_project, 7, "self", **{"Blocked by": "BUG-7"})
    world = pm._load_ledger_world(pm_project)
    assert pm.ready(world, "BUG-7") is False


def test_blocked_by_duplicate_does_not_block_satisfaction_but_is_reported(pm_project: Path) -> None:
    append_bug(pm_project, 2, "blocker", Status=STATUS_CLOSED)
    append_bug(pm_project, 1, "dependent", **{"Blocked by": "BUG-2, BUG-2"})
    world = pm._load_ledger_world(pm_project)
    assert pm.ready(world, "BUG-1") is True

    result = run_pm("--doctor", cwd=pm_project)
    assert result.stdout.count("BLOCKED_BY_DUPLICATE") == 1


def test_blocked_by_proposal_never_satisfies_even_when_marked_superseded(pm_project: Path) -> None:
    """The `Status` label collides between the PM lifecycle and proposals.md's own vocabulary —
    `superseded` is legal in both. A naive satisfaction check that read any entry's Status field
    would wrongly satisfy this. It must not."""
    append_proposal(pm_project, 5, "some idea", Status="superseded")
    append_bug(pm_project, 1, "dependent", **{"Blocked by": "PROPOSAL-5"})
    world = pm._load_ledger_world(pm_project)
    assert pm.ready(world, "BUG-1") is False

    result = run_pm("--doctor", cwd=pm_project)
    assert "BLOCKED_BY_PROPOSAL" in result.stdout


def test_dangling_finding_for_unknown_blocker_id(pm_project: Path) -> None:
    append_bug(pm_project, 1, "dependent", **{"Blocked by": "BUG-999"})
    world = pm._load_ledger_world(pm_project)
    assert pm.ready(world, "BUG-1") is False
    result = run_pm("--doctor", cwd=pm_project)
    assert "DANGLING" in result.stdout
    assert "BUG-999" in result.stdout


def test_dangling_finding_for_malformed_token(pm_project: Path) -> None:
    append_bug(pm_project, 1, "dependent", **{"Blocked by": "BUG - 3"})
    result = run_pm("--doctor", cwd=pm_project)
    assert "DANGLING" in result.stdout


# --- a present-but-empty Blocked by field fails closed, not open ------------


def test_present_but_empty_blocked_by_stays_blocked(pm_project: Path) -> None:
    append_bug(pm_project, 1, "dependent", **{"Blocked by": ""})
    world = pm._load_ledger_world(pm_project)
    assert pm.ready(world, "BUG-1") is False

    result = run_pm("--doctor", cwd=pm_project)
    assert "DANGLING" in result.stdout
    assert "BUG-1" in result.stdout


def test_present_but_empty_blocked_by_with_nothing_at_all_after_the_colon_stays_blocked(
    pm_project: Path,
) -> None:
    bugs = pm_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: dependent\n- **Blocked by**:\n")
    world = pm._load_ledger_world(pm_project)
    assert pm.ready(world, "BUG-1") is False

    result = run_pm("--doctor", cwd=pm_project)
    assert "DANGLING" in result.stdout


def test_blocked_by_present_but_empty_field_is_recorded_distinct_from_absent(
    pm_project: Path,
) -> None:
    append_bug(pm_project, 1, "dependent", **{"Blocked by": ""})
    world = pm._load_ledger_world(pm_project)
    entry, _spec = world.entries["BUG-1"]
    blocked = pm._blocked_by(entry)
    assert blocked.empty is True
    assert blocked.tokens == ()


# --- regression row 10: wrapped blocker list --------------------------------


def test_wrapped_blocker_list_is_truncated_and_stays_blocked(pm_project: Path) -> None:
    append_bug(pm_project, 3, "blocker", Status=STATUS_CLOSED)
    bugs = pm_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: dependent\n- **Blocked by**: BUG-3,\n  BUG-7\n")

    world = pm._load_ledger_world(pm_project)
    entry, _spec = world.entries["BUG-1"]
    assert entry.fields["Blocked by"] == "BUG-3,"

    blocked = pm.parse_blocked_by(entry.fields["Blocked by"])
    assert blocked.truncated is True
    # BUG-3 (the only visible token) is closed, but the entry must stay blocked regardless —
    # the dropped continuation could have named anything.
    assert pm.ready(world, "BUG-1") is False

    result = run_pm("--doctor", cwd=pm_project)
    assert "BLOCKED_BY_TRUNCATED" in result.stdout
    assert "BUG-1" in result.stdout


# --- satisfaction: an allowlist, not "anything but open" -------------------


@pytest.mark.parametrize("status_value,expected_satisfied", [
    (STATUS_IN_PROGRESS, False),
    (STATUS_DELIVERED, False),
    (STATUS_CLOSED, True),
    (STATUS_WONTFIX, True),
    (STATUS_SUPERSEDED, True),
])
def test_satisfaction_is_an_allowlist(
    pm_project: Path, status_value: str, expected_satisfied: bool
) -> None:
    append_bug(pm_project, 2, "blocker", Status=status_value)
    append_bug(pm_project, 1, "dependent", **{"Blocked by": "BUG-2"})
    world = pm._load_ledger_world(pm_project)
    assert pm.satisfied(world, "BUG-2") is expected_satisfied
    assert pm.ready(world, "BUG-1") is expected_satisfied


def test_blocker_with_malformed_status_leaves_dependent_blocked(pm_project: Path) -> None:
    append_bug(pm_project, 2, "blocker", Status=STATUS_MALFORMED)
    append_bug(pm_project, 1, "dependent", **{"Blocked by": "BUG-2"})
    world = pm._load_ledger_world(pm_project)
    entry, _spec = world.entries["BUG-2"]
    assert isinstance(pm._entry_status(entry), pm.MalformedField)
    assert pm.ready(world, "BUG-1") is False


def test_duplicate_blocker_id_fails_closed_for_readiness(pm_project: Path) -> None:
    """Two headings claiming BUG-2 must not let readiness resolve to whichever parsed last —
    DUPLICATE_ID makes the collision visible, but an ambiguous id must never itself satisfy a
    blocker, even though one of the two BUG-2 entries here is closed."""
    append_bug(pm_project, 2, "blocker (open)")
    append_bug(pm_project, 2, "blocker (closed)", Status=STATUS_CLOSED)
    append_bug(pm_project, 1, "dependent", **{"Blocked by": "BUG-2"})

    world = pm._load_ledger_world(pm_project)
    assert pm.satisfied(world, "BUG-2") is False
    assert pm.ready(world, "BUG-1") is False

    result = run_pm("--doctor", cwd=pm_project)
    assert "DUPLICATE_ID" in result.stdout
    assert "BUG-2" in result.stdout


def test_ambiguous_entrys_own_id_is_not_ready(pm_project: Path) -> None:
    """Round 1 made a duplicate id fail closed for its *dependents* (`satisfied()` returns False
    for an ambiguous id). The ambiguous entry itself must fail closed the same way — not flow
    through readiness on whichever heading `_load_ledger_world` happened to keep last — so it
    can't be reported ready or recommended by `next`/`roadmap --show`.

    The heading that wins the dict-collapse (the second one, parsed last) is open with no
    blockers here specifically so that, absent the fix, `ready()` would return True for it.
    """
    append_bug(pm_project, 2, "first (closed)", Status=STATUS_CLOSED)
    append_bug(pm_project, 2, "second (open)")

    world = pm._load_ledger_world(pm_project)
    assert "BUG-2" in world.ambiguous_ids
    assert pm.ready(world, "BUG-2") is False

    result = run_pm("roadmap", "--show", cwd=pm_project)
    assert "0 ready" in result.stdout


# --- CYCLE detection ---------------------------------------------------------


def test_cycle_detection_two_entry(pm_project: Path) -> None:
    append_bug(pm_project, 1, "a", **{"Blocked by": "BUG-2"})
    append_bug(pm_project, 2, "b", **{"Blocked by": "BUG-1"})
    world = pm._load_ledger_world(pm_project)
    cycles = pm._find_cycles(pm._blocked_by_edges(world))
    assert len(cycles) == 1
    assert set(cycles[0]) == {"BUG-1", "BUG-2"}

    result = run_pm("--doctor", cwd=pm_project)
    assert result.stdout.count("CYCLE") == 1


def test_cycle_detection_three_entry(pm_project: Path) -> None:
    append_bug(pm_project, 1, "a", **{"Blocked by": "BUG-2"})
    append_bug(pm_project, 2, "b", **{"Blocked by": "BUG-3"})
    append_bug(pm_project, 3, "c", **{"Blocked by": "BUG-1"})
    world = pm._load_ledger_world(pm_project)
    cycles = pm._find_cycles(pm._blocked_by_edges(world))
    assert len(cycles) == 1
    assert set(cycles[0]) == {"BUG-1", "BUG-2", "BUG-3"}


def test_cycle_detection_deduped_by_rotation(pm_project: Path) -> None:
    append_bug(pm_project, 5, "a", **{"Blocked by": "BUG-6"})
    append_bug(pm_project, 6, "b", **{"Blocked by": "BUG-5"})
    world = pm._load_ledger_world(pm_project)
    cycles = pm._find_cycles(pm._blocked_by_edges(world))
    assert len(cycles) == 1


def test_cycle_detection_terminates_on_a_self_loop(pm_project: Path) -> None:
    append_bug(pm_project, 9, "loop", **{"Blocked by": "BUG-9"})
    world = pm._load_ledger_world(pm_project)
    cycles = pm._find_cycles(pm._blocked_by_edges(world))
    assert cycles == [("BUG-9",)]

    result = run_pm("--doctor", cwd=pm_project)
    assert result.stdout.count("CYCLE") == 1


def test_cycle_detection_is_not_quadratic_on_a_long_path_with_many_back_edges() -> None:
    """A back edge from node i to i-2, on every node of a long chain, is adversarial for a
    path.index() cycle-start lookup: by the time each back edge is processed the path has
    already grown to ~i, so an O(path length) scan per back edge is O(n^2) overall even though
    every individual cycle found is short. This would take many seconds under that quadratic
    form; the O(1) position index this guards must keep it well under a second."""
    n = 60000
    edges: dict[str, list[str]] = {}
    for i in range(1, n + 1):
        node = f"N{i}"
        neighbors = []
        if i < n:
            neighbors.append(f"N{i + 1}")
        if i >= 3:
            neighbors.append(f"N{i - 2}")
        edges[node] = neighbors

    start = time.monotonic()
    cycles = pm._find_cycles(edges)
    elapsed = time.monotonic() - start

    assert len(cycles) == n - 2
    assert all(len(c) == 3 for c in cycles)
    assert elapsed < 3.0, f"_find_cycles took {elapsed:.2f}s — path.index() quadratic regression?"


# --- lock acquisition: a symlinked lock path must be refused, not followed -


def test_acquire_ledger_lock_refuses_a_symlink_and_leaves_target_untouched(tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    target.write_bytes(b"do not touch\n")
    lock_path = tmp_path / "some.lock"
    lock_path.symlink_to(target)

    # a deliberate, named refusal — not the OSError O_NOFOLLOW raises reaching main()'s exit-1
    # catch-all, which would blame pm.py for the user's setup
    with pytest.raises(pm.SymlinkedLedgerError):
        pm._acquire_ledger_lock(lock_path, deadline=time.monotonic() + 1.0)

    assert target.read_bytes() == b"do not touch\n"


def test_roadmap_write_refuses_a_symlinked_lock_path_and_leaves_target_untouched(
    pm_project: Path,
) -> None:
    append_bug(pm_project, 1, "x")
    target = pm_project / "secret.txt"
    target.write_bytes(b"do not touch\n")
    lock_dir = pm.ensure_lock_dir(pm_project)
    (lock_dir / "ROADMAP.md.lock").symlink_to(target)

    before = (pm_project / "ROADMAP.md").read_text()
    proposed = pm_project / "proposed.md"
    proposed.write_text("# ROADMAP\n\n## Milestone: M1\n- BUG-1\n")
    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)

    # exit 2, not the exit-1 catch-all: the ledger case already gets this treatment, and the
    # lock file has the identical hazard
    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert "unexpected error" not in result.stderr
    assert "symlinked lock file" in result.stderr
    assert target.read_bytes() == b"do not touch\n"
    assert (pm_project / "ROADMAP.md").read_text() == before


# --- regression row 6: ROADMAP grammar rejecting its own example -----------


def test_literal_template_roadmap_passes_write_unchanged(pm_project: Path) -> None:
    template_path = TEMPLATES_DIR / "ROADMAP.md"
    result = run_pm("roadmap", "--write", str(template_path), cwd=pm_project)
    assert result.returncode == 0, result.stderr
    assert (pm_project / "ROADMAP.md").read_text() == template_path.read_text()


SPEC_ROADMAP_EXAMPLE = """<!-- schema-version: 2 -->
<!-- ROADMAP.md SCHEMA
Ordered milestones, each naming BUG/DEFER/TEST entry IDs. Milestones are ordered
top-to-bottom; earlier milestones rank higher for --next's sort key. An ID should
appear in at most one milestone (--doctor flags duplicates). PROPOSAL entries are
never valid roadmap members. This file is agent-proposed, human-ratified — see
/quirk:pm:roadmap. Manual edits are allowed; pm.py re-parses on every run.
-->

# ROADMAP

## Milestone: Auth hardening
- BUG-3
- DEFER-7
- TEST-12

## Milestone: Search v2
- BUG-9
"""


def test_spec_roadmap_example_passes_write_given_known_ids(pm_project: Path) -> None:
    append_bug(pm_project, 3, "auth bug")
    append_bug(pm_project, 9, "search bug")
    append_defer(pm_project, 7, "auth defer")
    append_test(pm_project, 12, "auth test")

    proposed = pm_project / "proposed.md"
    proposed.write_text(SPEC_ROADMAP_EXAMPLE)
    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)
    assert result.returncode == 0, result.stderr
    assert (pm_project / "ROADMAP.md").read_text() == SPEC_ROADMAP_EXAMPLE


def test_roadmap_write_reports_proposal_in_roadmap_not_malformed(pm_project: Path) -> None:
    content = "# ROADMAP\n\n## Milestone: M1\n- PROPOSAL-1\n"
    proposed = pm_project / "proposed.md"
    proposed.write_text(content)
    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)
    assert result.returncode == pm.EXIT_BAD_ARGUMENT
    assert "PROPOSAL_IN_ROADMAP" in result.stderr
    assert "ROADMAP_LINE_MALFORMED" not in result.stderr


def test_roadmap_write_refuses_unknown_id_and_writes_nothing(pm_project: Path) -> None:
    before = (pm_project / "ROADMAP.md").read_text()
    content = "# ROADMAP\n\n## Milestone: M1\n- BUG-999\n"
    proposed = pm_project / "proposed.md"
    proposed.write_text(content)
    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)
    assert result.returncode == pm.EXIT_BAD_ARGUMENT
    assert (pm_project / "ROADMAP.md").read_text() == before


def test_roadmap_write_does_not_refuse_on_a_reference_into_a_ledger_it_could_not_read(
    pm_project: Path,
) -> None:
    """A ledger `--write` cannot read is could-not-look, not looked-and-found-nothing —
    refusing the whole write on that false premise would mean a user with one oversized or
    corrupt ledger can never write a roadmap at all. The skip is surfaced instead of being
    silently treated as a clean pass."""
    deferred = pm_project / "DEFERRED.md"
    deferred.write_bytes(b"\xff\xfe\x00\x01not utf-8")

    content = "# ROADMAP\n\n## Milestone: M1\n- DEFER-1\n"
    proposed = pm_project / "proposed.md"
    proposed.write_text(content)

    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)

    assert result.returncode == pm.EXIT_OK, result.stderr
    assert (pm_project / "ROADMAP.md").read_text() == content
    assert "DEFERRED.md: parse error, skipping" in result.stdout


def test_roadmap_write_still_refuses_an_unknown_id_in_a_readable_ledger_alongside_a_skip(
    pm_project: Path,
) -> None:
    # proves the skip isn't a blanket pass: a genuinely unknown id in a ledger that *was* read
    # must still refuse the write, even while another ledger is unreadable
    deferred = pm_project / "DEFERRED.md"
    deferred.write_bytes(b"\xff\xfe\x00\x01not utf-8")
    before = (pm_project / "ROADMAP.md").read_text()

    content = "# ROADMAP\n\n## Milestone: M1\n- BUG-999\n"
    proposed = pm_project / "proposed.md"
    proposed.write_text(content)

    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)

    assert result.returncode == pm.EXIT_BAD_ARGUMENT, result.stdout
    assert "DANGLING_ROADMAP_REF: BUG-999" in result.stderr
    assert (pm_project / "ROADMAP.md").read_text() == before


def test_roadmap_write_exits_seven_when_project_dir_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    proposed = tmp_path / "proposed.md"
    proposed.write_text("# ROADMAP\n")
    result = run_pm("roadmap", "--write", str(proposed), "--project-dir", str(missing), cwd=tmp_path)
    assert result.returncode == pm.EXIT_PROJECT_DIR_NOT_FOUND


def test_roadmap_write_refuses_a_member_line_outside_every_milestone(pm_project: Path) -> None:
    """A member-shaped line above the first milestone heading writes cleanly today and then
    contributes no membership at all — the entry silently ranks -1 as though never placed."""
    append_bug(pm_project, 1, "x")
    before = (pm_project / "ROADMAP.md").read_text()
    content = "# ROADMAP\n- BUG-1\n\n## Milestone: M1\n"
    proposed = pm_project / "proposed.md"
    proposed.write_text(content)
    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)
    assert result.returncode == pm.EXIT_BAD_ARGUMENT
    assert "MEMBER_OUTSIDE_MILESTONE" in result.stderr
    assert "BUG-1" in result.stderr
    assert (pm_project / "ROADMAP.md").read_text() == before


def test_roadmap_write_refuses_a_member_line_when_no_milestone_exists_at_all(
    pm_project: Path,
) -> None:
    append_bug(pm_project, 1, "x")
    before = (pm_project / "ROADMAP.md").read_text()
    proposed = pm_project / "proposed.md"
    proposed.write_text("# ROADMAP\n- BUG-1\n")
    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)
    assert result.returncode == pm.EXIT_BAD_ARGUMENT
    assert "MEMBER_OUTSIDE_MILESTONE" in result.stderr
    assert (pm_project / "ROADMAP.md").read_text() == before


def test_doctor_reports_member_outside_milestone(pm_project: Path) -> None:
    """`MEMBER_OUTSIDE_MILESTONE` must be visible at read time too, matching the write-time
    refusal above — a hand-edited `ROADMAP.md` with a member line above every milestone
    contributes no membership at all and, until now, no diagnostic either."""
    append_bug(pm_project, 1, "x")
    (pm_project / "ROADMAP.md").write_text("# ROADMAP\n- BUG-1\n\n## Milestone: M1\n")

    result = run_pm("--doctor", cwd=pm_project)

    assert result.returncode == 0, result.stderr
    assert "MEMBER_OUTSIDE_MILESTONE" in result.stdout
    assert "BUG-1" in result.stdout


# --- a missing ROADMAP.md is an empty roadmap, not an error -----------------


def test_missing_roadmap_is_empty_not_an_error(initialized_project: Path) -> None:
    append_bug(initialized_project, 1, "no roadmap yet", Severity="critical", Observed="2026-08-01")
    assert not (initialized_project / "ROADMAP.md").exists()

    result = run_pm("--next", cwd=initialized_project)
    assert result.returncode == 0, result.stderr

    ranks = pm._milestone_ranks(pm._read_roadmap(initialized_project))
    assert ranks == {}


# --- an unreadable/undecodable ROADMAP.md is not silently "missing" --------


def test_unreadable_roadmap_is_not_silently_treated_as_missing(pm_project: Path) -> None:
    roadmap_path = pm_project / "ROADMAP.md"
    roadmap_path.chmod(0o000)
    try:
        if os.access(roadmap_path, os.R_OK):
            pytest.skip("running as a user that bypasses file permissions")

        roadmap = pm._read_roadmap(pm_project)
        assert roadmap.milestones == []
        assert any(code == "ROADMAP_UNREADABLE" for code, _detail in roadmap.findings)

        result = run_pm("--doctor", cwd=pm_project)
        assert "ROADMAP_UNREADABLE" in result.stdout
    finally:
        roadmap_path.chmod(0o644)


def test_undecodable_roadmap_is_not_silently_treated_as_missing(pm_project: Path) -> None:
    roadmap_path = pm_project / "ROADMAP.md"
    roadmap_path.write_bytes(b"\xff\xfe\x00\x01 not valid utf-8 or anything sane")

    roadmap = pm._read_roadmap(pm_project)
    assert roadmap.milestones == []
    assert any(code == "ROADMAP_UNREADABLE" for code, _detail in roadmap.findings)

    result = run_pm("--doctor", cwd=pm_project)
    assert "ROADMAP_UNREADABLE" in result.stdout


def test_roadmap_write_exits_two_on_an_undecodable_proposal_file(pm_project: Path) -> None:
    proposed = pm_project / "proposed.md"
    proposed.write_bytes(b"\xff\xfe\x00\x01 not valid utf-8")
    result = run_pm("roadmap", "--write", str(proposed), cwd=pm_project)
    assert result.returncode == pm.EXIT_BAD_ARGUMENT
    assert "proposed.md" in result.stderr


def test_roadmap_show_exits_zero_always(pm_project: Path) -> None:
    result = run_pm("roadmap", "--show", cwd=pm_project)
    assert result.returncode == 0, result.stderr


def test_roadmap_show_on_missing_project_dir_still_exits_zero(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    result = run_pm("roadmap", "--show", "--project-dir", str(missing), cwd=tmp_path)
    assert result.returncode == 0, result.stderr


# --- empty ready-set explanation --------------------------------------------


def test_empty_ready_set_explains_the_blockers_responsible(pm_project: Path) -> None:
    append_bug(pm_project, 2, "blocker", Severity="high", Observed="2026-08-01", Status=STATUS_IN_PROGRESS)
    append_bug(pm_project, 1, "dependent", Severity="critical", Observed="2026-08-01", **{"Blocked by": "BUG-2"})

    result = run_pm("--next", cwd=pm_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "no ready candidates" in out.lower()
    assert "BUG-2" in out


def test_empty_shortlist_because_ready_work_is_ineligible_does_not_claim_nothing_is_ready(
    pm_project: Path,
) -> None:
    """Medium urgency and no milestone: BUG-1 is ready (nothing blocks it) but not eligible for
    the shortlist. There are no blockers to name, so this is a different empty-shortlist cause
    than test_empty_ready_set_explains_the_blockers_responsible, and must say so rather than
    printing "no ready candidates" right above a line that counts it as ready."""
    append_bug(pm_project, 1, "ready but unplaced", Severity="medium", Observed="2026-08-01")

    result = run_pm("--next", cwd=pm_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "no ready candidates" not in out.lower()
    assert "ready but not eligible" in out.lower()
    assert "1 unplaced (1 ready, 0 blocked, 0 malformed)" in out


# --- hooks/load_artifact_tail.sh's grep must keep matching -----------------


def test_next_output_still_has_a_grep_matchable_unplaced_line(initialized_project: Path) -> None:
    result = run_pm("--next", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    assert any("unplaced (" in line for line in result.stdout.splitlines())
