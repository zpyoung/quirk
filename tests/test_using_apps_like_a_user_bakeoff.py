from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "using-apps-like-a-user" / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bakeoff  # noqa: E402

SENTINEL = bakeoff.SENTINEL_BUNDLE_ID
FIXTURE = bakeoff.FIXTURE_BUNDLE_ID


def result(name, steals=0, clicks_landed=10, strings_landed=10, menu=False, dialog=False,
           cursor_moves=0, clicks=10, strings=10, samples=500, action_s=10.0, poller_errors=0):
    return {
        "name": name,
        "focus_steals": steals,
        "focus_steal_ms": steals * 100,
        "cursor_moves": cursor_moves,
        "clicks": clicks,
        "clicks_landed": clicks_landed,
        "strings": strings,
        "strings_landed": strings_landed,
        "menu": menu,
        "dialog": dialog,
        "samples": samples,
        "action_s": action_s,
        "poller_errors": poller_errors,
    }


def test_all_landed_zero_steals_wins():
    verdict = bakeoff.choose_winner([result("peekaboo")])
    assert verdict["winner"] == "peekaboo"
    assert verdict["background_capable"] is True
    assert verdict["qualified"] == ["peekaboo"]


def test_any_steal_disqualifies():
    verdict = bakeoff.choose_winner([result("peekaboo", steals=1), result("cua")])
    assert verdict["winner"] == "cua"
    assert verdict["qualified"] == ["cua"]


def test_partial_click_landing_disqualifies():
    verdict = bakeoff.choose_winner([result("peekaboo", clicks_landed=9), result("cua")])
    assert verdict["winner"] == "cua"


def test_partial_string_landing_disqualifies():
    verdict = bakeoff.choose_winner([result("cua", strings_landed=9), result("peekaboo")])
    assert verdict["winner"] == "peekaboo"


def test_zero_inputs_landed_never_qualifies_even_with_zero_steals():
    verdict = bakeoff.choose_winner([result("cua", clicks_landed=0, strings_landed=0)])
    assert verdict["winner"] == "orca"


def test_tie_goes_to_menu_and_dialog_support():
    verdict = bakeoff.choose_winner([
        result("cua", menu=True, dialog=False),
        result("peekaboo", menu=True, dialog=True),
    ])
    assert verdict["winner"] == "peekaboo"
    assert verdict["qualified"] == ["cua", "peekaboo"]


def test_tie_with_equal_support_goes_to_first_listed():
    verdict = bakeoff.choose_winner([result("cua", menu=True), result("peekaboo", menu=True)])
    assert verdict["winner"] == "cua"


def test_no_qualifier_falls_back_to_orca_foreground():
    verdict = bakeoff.choose_winner([
        result("peekaboo", steals=2),
        result("cua", clicks_landed=3),
        result("orca", steals=10),
    ])
    assert verdict["winner"] == "orca"
    assert verdict["background_capable"] is False
    assert verdict["qualified"] == []
    assert "foreground" in verdict["reason"]


def test_orca_is_never_background_capable_even_when_it_measures_clean():
    verdict = bakeoff.choose_winner([result("orca")])
    assert verdict["winner"] == "orca"
    assert verdict["background_capable"] is False


def test_empty_candidate_list_falls_back_to_orca():
    verdict = bakeoff.choose_winner([])
    assert verdict["winner"] == "orca"
    assert verdict["background_capable"] is False


def test_failed_candidate_with_error_never_qualifies():
    broken = result("peekaboo")
    broken["error"] = "launch failed"
    assert bakeoff.qualifies(broken) is False


def test_zero_samples_never_qualifies():
    assert bakeoff.qualifies(result("cua", samples=0)) is False
    assert bakeoff.choose_winner([result("cua", samples=0)])["winner"] == "orca"


def test_poller_errors_disqualify_even_with_samples():
    assert bakeoff.qualifies(result("cua", poller_errors=1)) is False


def test_sparse_sampling_disqualifies_by_action_interval():
    assert bakeoff.required_samples(10.0) == 100
    assert bakeoff.required_samples(0.0) == 1
    assert bakeoff.qualifies(result("cua", samples=99, action_s=10.0)) is False
    assert bakeoff.qualifies(result("cua", samples=100, action_s=10.0)) is True


def test_poller_records_errors_instead_of_discarding_them(monkeypatch):
    def boom():
        raise RuntimeError("lsappinfo gone")

    monkeypatch.setattr(bakeoff._desktop, "frontmost_bundle_id", boom)
    poller = bakeoff.Poller(interval_s=0.01)
    poller.start()
    bakeoff.wait_for(lambda: len(poller.errors) >= 2, 2.0)
    poller.stop()
    assert poller.samples == []
    assert poller.errors and "lsappinfo gone" in poller.errors[0]
    assert poller.duration_s > 0


def sample(t_ms, front, xy=(100.0, 100.0)):
    return (t_ms / 1000.0, front, xy)


def test_analyze_counts_a_steal_and_its_duration():
    samples = [
        sample(0, SENTINEL), sample(20, SENTINEL),
        sample(40, FIXTURE), sample(60, FIXTURE),
        sample(80, SENTINEL), sample(100, SENTINEL),
    ]
    out = bakeoff.analyze_samples(samples, SENTINEL)
    assert out["focus_steals"] == 1
    assert out["focus_steal_ms"] == pytest.approx(40.0)
    assert out["cursor_moves"] == 0


def test_analyze_counts_each_separate_steal():
    samples = [
        sample(0, SENTINEL), sample(20, FIXTURE), sample(40, SENTINEL),
        sample(60, "com.apple.finder"), sample(80, "com.apple.finder"), sample(100, SENTINEL),
    ]
    out = bakeoff.analyze_samples(samples, SENTINEL)
    assert out["focus_steals"] == 2
    assert out["focus_steal_ms"] == pytest.approx(20.0 + 40.0)


def test_analyze_open_ended_steal_runs_to_the_last_sample():
    samples = [sample(0, SENTINEL), sample(20, FIXTURE), sample(60, FIXTURE)]
    out = bakeoff.analyze_samples(samples, SENTINEL)
    assert out["focus_steals"] == 1
    assert out["focus_steal_ms"] == pytest.approx(40.0)


def test_analyze_a_sentinel_that_never_held_focus_counts_no_steal():
    samples = [sample(0, FIXTURE), sample(20, FIXTURE)]
    out = bakeoff.analyze_samples(samples, SENTINEL)
    assert out["focus_steals"] == 0


def test_analyze_ignores_an_empty_frontmost_reading():
    samples = [sample(0, SENTINEL), sample(20, ""), sample(40, SENTINEL)]
    out = bakeoff.analyze_samples(samples, SENTINEL)
    assert out["focus_steals"] == 0


def test_analyze_cursor_moves_beyond_tolerance_only():
    samples = [
        sample(0, SENTINEL, (100.0, 100.0)),
        sample(20, SENTINEL, (102.0, 101.0)),
        sample(40, SENTINEL, (110.0, 100.0)),
        sample(60, SENTINEL, (110.0, 100.0)),
        sample(80, SENTINEL, (110.0, 90.0)),
    ]
    out = bakeoff.analyze_samples(samples, SENTINEL)
    assert out["cursor_moves"] == 2


def test_analyze_cursor_move_at_exactly_the_tolerance_is_not_a_move():
    samples = [sample(0, SENTINEL, (0.0, 0.0)), sample(20, SENTINEL, (3.0, 0.0))]
    assert bakeoff.analyze_samples(samples, SENTINEL)["cursor_moves"] == 0


def test_analyze_empty_samples():
    out = bakeoff.analyze_samples([], SENTINEL)
    assert out == {"focus_steals": 0, "focus_steal_ms": 0.0, "cursor_moves": 0, "samples": 0}


def test_count_landed_strings():
    assert bakeoff.count_landed_strings("alpha-1 beta-2", ["alpha-1", "beta-2", "gamma-3"]) == 2
    assert bakeoff.count_landed_strings("", ["a"]) == 0
    assert bakeoff.count_landed_strings(None, ["a"]) == 0


def test_test_strings_are_distinct_and_none_contains_another():
    strings = bakeoff.make_strings(10)
    assert len(strings) == 10
    for i, a in enumerate(strings):
        for j, b in enumerate(strings):
            if i != j:
                assert a not in b


def test_parse_orca_index_picks_the_labelled_element():
    tree = (
        "0 standard window UALA Fixture\n"
        "\t1 text Status: idle\n"
        "\t2 button Working button\n"
        "\t3 button Dead button\n"
        "\t7 text field (settable) Notes\n"
    )
    assert bakeoff.parse_orca_index(tree, "Working button") == 2
    assert bakeoff.parse_orca_index(tree, "Notes") == 7
    assert bakeoff.parse_orca_index(tree, "Missing") is None


def test_parse_orca_index_ignores_value_and_action_suffixes():
    tree = (
        "\t7 text field (settable) Notes, Value: typed text\n"
        "\t10 full screen button, Secondary Actions: zoom the window\n"
    )
    assert bakeoff.parse_orca_index(tree, "Notes") == 7
    assert bakeoff.parse_orca_index(tree, "typed text") is None
    assert bakeoff.parse_orca_index(tree, "full screen button") == 10


def test_find_in_json_finds_nested_dict_by_label():
    doc = {"data": {"elements": [{"id": "e1", "label": "Dead button"},
                                 {"id": "e2", "label": "Working button"}]}}
    hit = bakeoff.find_in_json(doc, lambda d: d.get("label") == "Working button")
    assert hit == {"id": "e2", "label": "Working button"}
    assert bakeoff.find_in_json(doc, lambda d: d.get("label") == "x") is None


def test_find_key_walks_nested_structures():
    doc = {"a": [{"b": {"snapshotId": "S1"}}]}
    assert bakeoff.find_key(doc, ("snapshot_id", "snapshotId")) == "S1"
    assert bakeoff.find_key(doc, ("nope",)) is None


def test_parse_frame_and_window_local_center():
    assert bakeoff.parse_frame("512, 524, 280, 24") == (512.0, 524.0, 280.0, 24.0)
    assert bakeoff.parse_frame("512, 524") is None
    assert bakeoff.parse_frame("a, b, c, d") is None
    assert bakeoff.window_local_center((512, 524, 280, 24), (298, 273, 900, 450)) == (354, 263)


def test_find_element_prefers_the_role_hint_and_returns_the_driver_id():
    doc = {"elements": [
        {"label": "Notes", "role": "AXGroup", "element_token": "s1:2"},
        {"label": "Notes", "role": "AXTextField", "element_token": "s1:6"},
    ]}
    node = bakeoff.find_element(doc, "Notes", "field")
    assert bakeoff.element_id(node) == "s1:6"
    assert bakeoff.find_element(doc, "Absent", "field") is None
    assert bakeoff.find_element({"label": "Notes"}, "Notes", "field") is None


def test_hit_count_reads_the_state_file(tmp_path):
    state = tmp_path / "s.json"
    state.write_text(json.dumps({"hits": {"working": 4}, "text": "abc"}))
    assert bakeoff.read_state(state)["hits"]["working"] == 4
    assert bakeoff.read_state(tmp_path / "missing.json") == {}
    (tmp_path / "bad.json").write_text("{not json")
    assert bakeoff.read_state(tmp_path / "bad.json") == {}


def test_render_report_names_winner_and_each_candidate():
    results = [result("peekaboo", menu=True, dialog=True), result("cua", steals=3)]
    verdict = bakeoff.choose_winner(results)
    text = bakeoff.render_report(
        {"date": "2026-10-12", "machine": "macOS 26.0 Mac", "versions": {"peekaboo": "4.9.1", "cua": "0.34.1"}},
        [{"results": results, "verdict": verdict}],
    )
    assert "**Winner:** peekaboo" in text
    assert "background_capable" in text
    assert "| peekaboo |" in text and "| cua |" in text


def test_parse_args_defaults():
    ns = bakeoff.parse_args([])
    assert ns.clicks == 10 and ns.strings == 10
    assert ns.candidates == ["peekaboo", "cua", "orca"]


def test_parse_args_rejects_unknown_candidate():
    with pytest.raises(SystemExit):
        bakeoff.parse_args(["--candidates", "peekaboo,nope"])


def test_sentinel_source_is_a_plain_one_window_app():
    assert SENTINEL == "dev.quirk.uala.sentinel"
    assert "NSApplication" in bakeoff.SENTINEL_SWIFT
    assert "NSWindow" in bakeoff.SENTINEL_SWIFT


def fake_capture(outputs):
    def capture(argv):
        return outputs.get(" ".join(argv), "")
    return capture


def on_path(*names):
    return lambda binary: f"/usr/bin/{binary}" if binary in names else None


CUA_PERMS = "cua-driver permissions status --json"
PEEKABOO_PERMS = "peekaboo permissions --json"


def test_readiness_passes_when_cua_permissions_granted():
    capture = fake_capture({CUA_PERMS: json.dumps({"accessibility": True, "screen_recording": True})})
    assert bakeoff.check_readiness(["cua"], on_path("cua-driver"), capture) == []


def test_readiness_names_each_missing_cua_permission():
    capture = fake_capture({CUA_PERMS: json.dumps({"accessibility": True, "screen_recording": False})})
    missing = bakeoff.check_readiness(["cua"], on_path("cua-driver"), capture)
    assert missing == ["cua-driver lacks Screen Recording permission"]
    capture = fake_capture({CUA_PERMS: json.dumps({"accessibility": False})})
    assert len(bakeoff.check_readiness(["cua"], on_path("cua-driver"), capture)) == 2


def test_readiness_flags_unparseable_cua_permissions():
    missing = bakeoff.check_readiness(["cua"], on_path("cua-driver"), fake_capture({}))
    assert missing and "no JSON" in missing[0]


def test_readiness_checks_required_peekaboo_permissions_only():
    doc = {"data": {"permissions": [
        {"name": "Screen Recording", "isRequired": True, "isGranted": False},
        {"name": "Accessibility", "isRequired": True, "isGranted": True},
        {"name": "Event Synthesizing", "isRequired": False, "isGranted": False},
    ]}}
    capture = fake_capture({PEEKABOO_PERMS: json.dumps(doc)})
    assert bakeoff.check_readiness(["peekaboo"], on_path("peekaboo"), capture) == [
        "peekaboo lacks Screen Recording permission"]


def test_readiness_reports_missing_binaries_without_probing_permissions():
    def capture(argv):
        raise AssertionError("must not probe a missing binary")

    missing = bakeoff.check_readiness(["peekaboo", "cua", "orca"], on_path("orca"), capture)
    assert missing == ["peekaboo is not on PATH", "cua-driver is not on PATH"]


def test_main_exits_2_before_any_desktop_work_when_cua_lacks_permissions(monkeypatch, capsys):
    monkeypatch.setattr(bakeoff.sys, "platform", "darwin")
    monkeypatch.setattr(bakeoff, "check_readiness", lambda names: ["cua-driver lacks Accessibility permission"])

    def forbidden(*a, **k):
        raise AssertionError("desktop work before readiness")

    monkeypatch.setattr(bakeoff._desktop, "frontmost_bundle_id", forbidden)
    monkeypatch.setattr(bakeoff, "build_fixture", forbidden)
    assert bakeoff.main(["--candidates", "cua"]) == 2
    assert "Accessibility" in capsys.readouterr().err
