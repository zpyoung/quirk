"""Tests for the making-videos review page builder.

They run the real script as a subprocess, and it runs the real sibling builder of the
``writing-html-artifacts`` skill, so every assertion is about the built page or its source.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / "skills"
SCRIPT = SKILLS / "making-videos" / "scripts" / "review_page.py"

INJECTION = '<script>alert("pwn")</script>'
ESCAPED_INJECTION = "&lt;script&gt;alert(&quot;pwn&quot;)&lt;/script&gt;"

STORYBOARD = f"""# Launch storyboard

## Script (narration)

1. First spoken line {INJECTION}
2. Second spoken line

## Scene list

| Scene | Time (s) | On screen |
|---|---|---|
| s1 Hook | 0.0-6.0 | a headline |
| s2 payoff | 6.0-12.5 | a result |
"""


def _check(name: str, status: str = "pass", measured: object = None, threshold: object = None,
           detail: str = "ok") -> dict:
    return {"name": name, "status": status, "measured": measured, "threshold": threshold, "detail": detail}


def _sync(offsets: "list[tuple[str, str, float]]", status: str = "pass") -> dict:
    beats = [{"id": i, "via": via, "offset_frames": off} for i, via, off in offsets]
    worst = max((abs(b["offset_frames"]) for b in beats), default=0.0)
    return _check("sync", status, {"worst_frames": worst, "beats": beats}, {"offset_frames_max": 1},
                  "%d beat(s) within one frame" % len(beats))


def _run(checks: "list[dict]", passed: bool = True, attempts: "list[bool]" = None, stop: bool = False) -> dict:
    flags = attempts if attempts is not None else [passed]
    return {
        "attempts": [{"n": n + 1, "ts": "2026-10-22T10:00:00+00:00", "passed": ok} for n, ok in enumerate(flags)],
        "attempt": len(flags),
        "failed_attempts": sum(1 for ok in flags if not ok),
        "passed": passed,
        "stop": stop,
        "checks": checks,
        "frames": {},
    }


GOOD_CHECKS = [
    _check("fonts", "pass", {"injected": 3, "required": 2, "unresolved": 0}, {"injected_min": 2, "unresolved": 0}),
    _check("loudness", "pass", {"lufs": -16.0, "true_peak_dbtp": -4.3},
           {"lufs": [-17.0, -15.0], "true_peak_dbtp_max": -1.0}),
    _sync([("b1", "onset", 0.3), ("b2", "expected", 0.0)]),
    _check("blender", "skip", None, None, "no guard.json under the project, so no 3D clip"),
    _check("outside_calls", "pass", {}, {"cloud_allow": ["elevenlabs"]}, "4 logged call(s), all to allowed providers"),
]


def write_verify(vdir: Path, runs: dict, version: str = None) -> None:
    doc = {"version": version or vdir.name, "passed": all(r["passed"] for r in runs.values()), "runs": runs}
    (vdir / "verify.json").write_text(json.dumps(doc))


def add_cut(vdir: Path, stem: str, stills: "list[str]" = (), sheet: bool = True) -> None:
    (vdir / (stem + ".mp4")).write_bytes(b"\x00mp4")
    folder = vdir / "frames" / stem
    folder.mkdir(parents=True, exist_ok=True)
    if sheet:
        (folder / "sheet.png").write_bytes(b"png")
    for name in stills:
        (folder / name).write_bytes(b"png")


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(tmp_path / "cache"),
    }


def build(project: Path, env: dict, script: Path = SCRIPT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), "--project", str(project)],
        capture_output=True, text=True, env=env, timeout=120,
    )


def build_ok(project: Path, env: dict) -> "tuple[str, str]":
    """Build, assert success, and return ``(source, page)`` text."""
    proc = build(project, env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return (
        (project / "review.src.html").read_text(encoding="utf-8"),
        (project / "review.html").read_text(encoding="utf-8"),
    )


def section(page: str, heading: str) -> str:
    """The top-level ``<section aria-labelledby=...>`` whose h2 text is ``heading``."""
    for chunk in page.split("<section aria-labelledby=")[1:]:
        if re.match(r'"[^"]*">\s*<h2[^>]*>\s*%s\s*</h2>' % re.escape(heading), chunk):
            return chunk
    raise AssertionError("no section %r in page" % heading)


def make_project(root: Path, name: str = "2026-10-22-demo") -> Path:
    proj = root / "studio" / "videos" / name
    proj.mkdir(parents=True)
    return proj


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """v1 with per-MP4 runs and two cuts, v2 (newest) with a flat verify.json, a note and flat frames."""
    proj = make_project(tmp_path)
    (proj / "brief.json").write_text(json.dumps({
        "slug": "demo", "product": "Acme <b>Pro</b>", "title": f"Demo {INJECTION}", "length_s": 42,
        "aspects": ["16:9", "9:16"], "narration": True, "cloud_allow": ["elevenlabs"],
        "music": {"source": "none", "path": None}, "created": "2026-10-22",
    }))
    (proj / "storyboard.md").write_text(STORYBOARD)
    (proj / "beats-16x9.json").write_text(json.dumps([
        {"id": "b1", "word": "alpha"}, {"id": "b2", "word": "beta"},
    ]))

    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "demo-16x9", ["still-01-3.70s.png", "still-02-9.00s.png"])
    add_cut(v1, "demo-9x16", [])
    (v1 / "demo-16x9.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
    write_verify(v1, {
        "demo-16x9.mp4": _run(GOOD_CHECKS, True, [False, True]),
        "demo-9x16.mp4": _run(
            [_check("title_safe", "fail", {"collisions": 1, "bands_checked": ["top"]}, {"collisions": 0},
                    f"text near the edge {INJECTION}")] + GOOD_CHECKS[:3],
            False, [False],
        ),
    })

    v2 = proj / "v2"
    (v2 / "frames").mkdir(parents=True)
    (v2 / "demo-16x9.mp4").write_bytes(b"\x00mp4")
    (v2 / "frames" / "sheet.png").write_bytes(b"png")
    (v2 / "frames" / "still-01-2.00s.png").write_bytes(b"png")
    (v2 / "verify.json").write_text(json.dumps({
        "version": "v2", "attempt": 1, "passed": True, "stop": False, "checks": GOOD_CHECKS,
    }))
    (v2 / "review-notes.md").write_text(
        "Looks right overall, with one caption to look at.\n\n"
        "- The caption in s2 sits close to the bottom edge\n"
        f"- Listen to the end for clipping {INJECTION}\n"
    )

    calls = [
        {"ts": "2026-10-22T10:00:00Z", "provider": "elevenlabs", "method": "POST",
         "host": "api.elevenlabs.io", "path": "/v1/tts", "status": 200, "bytes": 1234},
        {"ts": "2026-10-22T10:01:00Z", "provider": "hyperframes", "subcommand": "render",
         "args": ["render", "--output", "v1/demo.mp4"], "status": 0},
        {"ts": "2026-10-22T10:01:10Z", "provider": "hyperframes", "subcommand": "render",
         "args": ["render"], "status": 0},
        {"ts": "2026-10-22T10:01:30Z", "provider": "playwright", "method": "RECORD",
         "host": "localhost", "path": "/app", "status": 200, "bytes": 5},
        {"ts": "2026-10-22T10:02:00Z", "provider": "pexels", "method": "GET",
         "host": "api.pexels.com", "path": "/v1/search", "status": 200, "bytes": 99},
    ]
    (proj / "calls.jsonl").write_text("\n".join(json.dumps(c) for c in calls) + "\nnot json\n")
    return proj


@pytest.fixture()
def built(project: Path, env: dict) -> "tuple[str, str]":
    return build_ok(project, env)


# contract ---------------------------------------------------------------------------------------


def test_stdout_is_one_json_object(project: Path, env: dict) -> None:
    proc = build(project, env)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert out["page"] == str(project / "review.html")
    assert out["source"] == str(project / "review.src.html")
    assert out["checks"]["passed"] is True
    assert out["checks"]["failures"] == []
    assert (project / "review.src.html").is_file() and (project / "review.html").is_file()


def test_missing_project_exits_2(tmp_path: Path, env: dict) -> None:
    proc = build(tmp_path / "nope", env)
    assert proc.returncode == 2
    assert "error" in json.loads(proc.stdout.strip())


def test_missing_arguments_exit_2(env: dict) -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env)
    assert proc.returncode == 2
    assert "error" in json.loads(proc.stdout.strip())


def test_bare_project_still_builds(tmp_path: Path, env: dict) -> None:
    proj = tmp_path / "bare"
    proj.mkdir()
    src, page = build_ok(proj, env)
    assert '"title": "Video review, no versions yet"' in src.splitlines()[0]
    assert "brief.json" in page and "storyboard.md" in page
    assert "no versions" in page.lower()


def test_header_is_one_json_line(built: "tuple[str, str]") -> None:
    src, _ = built
    first = src.splitlines()[0]
    assert first.startswith("<!-- quirk-src ") and first.endswith(" -->")
    header = json.loads(first[len("<!-- quirk-src "):-len(" -->")])
    assert header["template"] == "report"
    assert header["layout"] == "explainer"
    assert header["mode"] == "offline"
    assert header["title"] == f"Demo {INJECTION}, v2 review"
    assert "<" not in first[len("<!--"):] and first.count("-->") == 1
    assert "<!-- slot: summary -->" in src and "<!-- slot: main -->" in src


def test_title_with_comment_close_and_markup(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "brief.json").write_text(json.dumps({"title": "a --> b <i>x</i> & c"}))
    (proj / "v1").mkdir()
    src, page = build_ok(proj, env)
    first = src.splitlines()[0]
    assert first.count("-->") == 1 and first.endswith(" -->")
    assert "<i>x</i>" not in page
    assert "a --&gt; b &lt;i&gt;x&lt;/i&gt; &amp; c" in page


def test_interactions_declared(built: "tuple[str, str]", tmp_path: Path, env: dict) -> None:
    header = json.loads(built[0].splitlines()[0][len("<!-- quirk-src "):-len(" -->")])
    text = " ".join(header["interactions"])
    assert "jump" in text and "play" in text and "compare" in text
    assert "choose which cut" not in text and "switch" not in text  # newest version has one cut

    proj = make_project(tmp_path, "two-cuts")
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9", ["still-01-1.00s.png"])
    add_cut(v1, "a-9x16", ["still-01-1.00s.png"])
    (proj / "storyboard.md").write_text(STORYBOARD)
    src, _ = build_ok(proj, env)
    header = json.loads(src.splitlines()[0][len("<!-- quirk-src "):-len(" -->")])
    text = " ".join(header["interactions"])
    assert "choose which cut" in text and "switch" in text and "compare" not in text


def test_every_project_value_is_escaped(built: "tuple[str, str]") -> None:
    src, page = built
    for text in (src, page):
        assert INJECTION not in text
        assert "<script>alert" not in text
    assert ESCAPED_INJECTION in src
    assert ESCAPED_INJECTION in page
    assert "Acme &lt;b&gt;Pro&lt;/b&gt;" in src


def test_no_network_references_in_source(built: "tuple[str, str]") -> None:
    src, _ = built
    assert not re.search(r"https?://", src)
    assert not re.search(r"\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource", src)
    assert not re.search(r"@import|<link\b|<script[^>]+src=", src)


def test_media_links_are_relative_and_percent_encoded(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "my cut 16x9", ["still-01-1.00s.png"])
    (v1 / "my cut 16x9.srt").write_text("x")
    src, page = build_ok(proj, env)
    assert 'src="v1/my%20cut%2016x9.mp4"' in src
    assert 'href="v1/my%20cut%2016x9.srt"' in src
    assert 'src="v1/frames/my%20cut%2016x9/still-01-1.00s.png"' in src
    assert 'src="v1/my%20cut%2016x9.mp4"' in page


# summary and the agent's notes ---------------------------------------------------------------


def test_newest_version_leads(built: "tuple[str, str]") -> None:
    _, page = built
    watch = section(page, "Watch")
    assert 'src="v2/demo-16x9.mp4"' in watch
    assert 'src="v1/' not in watch
    assert "Earlier versions" in page


def test_note_verdict_is_the_summary_and_list_follows(built: "tuple[str, str]") -> None:
    _, page = built
    lede = re.search(r'<p class="q-lede">(.*?)</p>', page, re.S).group(1)
    assert "Looks right overall, with one caption to look at." in lede
    check = section(page, "What I would check before signing off")
    assert re.search(r"<ul>\s*<li>The caption in s2 sits close to the bottom edge</li>", check)
    assert ESCAPED_INJECTION in check
    assert "Looks right overall" not in check


def test_no_notes_says_the_review_is_not_written(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9", ["still-01-1.00s.png"])
    write_verify(v1, {"a-16x9.mp4": _run(GOOD_CHECKS)})
    _, page = build_ok(proj, env)
    check = section(page, "What I would check before signing off")
    assert "The agent's frame review for v1 isn't written yet." in check.replace("&#x27;", "'")
    lede = re.search(r'<p class="q-lede">(.*?)</p>', page, re.S).group(1)
    assert "Verify passed" in lede


def test_note_without_a_list_says_nothing_beyond_the_checks(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    (v1 / "review-notes.md").write_text("Clean.\n")
    _, page = build_ok(proj, env)
    assert "Nothing beyond the checks." in section(page, "What I would check before signing off")


def test_stopped_run_opens_the_summary_and_names_failing_checks(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9", ["still-01-1.00s.png"])
    failing = [_check("contrast", "fail", {"failing": 3, "worst_ratio": 2.1}, {"failing": 0}, "3 text elements fail"),
               _check("title_safe", "fail", {"collisions": 2}, {"collisions": 0}, "text near the edge")]
    write_verify(v1, {"a-16x9.mp4": _run(failing, False, [False, False, False], stop=True)})
    (v1 / "review-notes.md").write_text("The render is not usable yet.\n\n- look at the contrast\n")
    _, page = build_ok(proj, env)
    ledes = re.findall(r'<p class="q-lede">(.*?)</p>', page, re.S)
    assert ledes[0].startswith("Stopped after 3 failed verify attempts")
    assert "contrast" in ledes[0] and "title safe" in ledes[0]
    assert "The render is not usable yet." in " ".join(ledes[1:])
    assert page.index("Stopped after 3 failed verify attempts") < page.index("The render is not usable yet.")


# findings, verify results and the sync chart --------------------------------------------------


def test_findings_are_generated_from_verify_json(built: "tuple[str, str]") -> None:
    _, page = built
    findings = section(page, "Findings")
    assert "-16.0 LUFS" in findings and "-4.3 dBTP" in findings
    assert "0.3 frames" in findings
    assert '"beta"' in findings.replace("&quot;", '"') and "no clear audio onset" in findings
    assert "5 logged calls" in findings or "5 calls" in findings
    assert "pexels" in findings
    assert "{" not in findings


def test_attempt_history_per_mp4(project: Path, env: dict) -> None:
    (project / "v2").rename(project / "v2-old")
    (project / "v2-old").rename(project / "v0")
    _, page = build_ok(project, env)
    findings = section(page, "Findings")
    assert "16:9" in findings and "attempt 1 failed, attempt 2 passed" in findings
    assert "9:16" in findings


def test_verify_results_table_in_plain_words(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9", ["still-01-1.00s.png"])
    add_cut(v1, "a-9x16", ["still-01-1.00s.png"])
    other = list(GOOD_CHECKS)
    other[0] = _check("fonts", "fail", {"injected": 1, "required": 2, "unresolved": 1},
                      {"injected_min": 2, "unresolved": 0}, f"missing {INJECTION}")
    write_verify(v1, {
        "a-16x9.mp4": _run(GOOD_CHECKS + [_check("mystery", "pass", {"depth": 3, "ok": True}, None, "fine")]),
        "a-9x16.mp4": _run(other, False),
    })
    _, page = build_ok(proj, env)
    results = section(page, "Verify results")
    head = re.search(r"<thead>(.*?)</thead>", results, re.S).group(1)
    assert "16:9" in head and "9:16" in head
    assert re.search(r"<th[^>]*>Fonts</th>\s*<td[^>]*>Pass</td>\s*<td[^>]*>Fail</td>", results)
    assert re.search(r"<th[^>]*>Blender</th>\s*<td[^>]*>Skipped</td>", results)
    assert "-16.0 LUFS, true peak -4.3 dBTP" in results
    assert "-17 to -15 LUFS" in results
    assert "3 font families" in results and "1 font family" in results  # the two cuts differ
    assert "Mystery" in results and "depth: 3" in results
    assert ESCAPED_INJECTION in results
    assert '"injected"' not in results and "&quot;injected&quot;" not in results and "worst_frames" not in results


def test_sync_chart_labels_come_from_beats_files(built: "tuple[str, str]") -> None:
    _, page = built
    results = section(page, "Verify results")
    assert "<q-chart" in results or "q-chart" in results
    rows = re.findall(r"<tr><td>([^<]*)</td><td>([^<]*)</td></tr>", results)
    assert ("alpha", "0.3") in rows
    assert ("beta (no onset)", "0") in rows


def test_sync_chart_one_series_when_cuts_agree_else_one_per_cut(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9")
    add_cut(v1, "a-9x16")
    same = [_sync([("b1", "onset", 0.3)])]
    write_verify(v1, {"a-16x9.mp4": _run(same), "a-9x16.mp4": _run(same)})
    _, page = build_ok(proj, env)
    results = section(page, "Verify results")
    assert "Every cut measured the same offsets." in results
    assert "<td>b1</td><td>0.3</td>" in results

    write_verify(v1, {"a-16x9.mp4": _run(same), "a-9x16.mp4": _run([_sync([("b1", "onset", -0.6)])])})
    _, page = build_ok(proj, env)
    results = section(page, "Verify results")
    assert "Every cut measured the same offsets." not in results
    assert re.search(r"<tr><td>b1</td><td>0\.3</td><td>-0\.6</td></tr>", results)


def test_no_onset_label_survives_a_cut_that_measured_one(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "beats.json").write_text(json.dumps([{"id": "b1", "word": "alpha"}]))
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9")
    add_cut(v1, "a-9x16")
    write_verify(v1, {
        "a-16x9.mp4": _run([_sync([("b1", "onset", 0.3)])]),
        "a-9x16.mp4": _run([_sync([("b1", "expected", 0.0)])]),
    })
    _, page = build_ok(proj, env)
    assert "<td>alpha (no onset)</td>" in section(page, "Verify results")


# scenes ---------------------------------------------------------------------------------------


def test_scene_table_gives_seek_buttons(built: "tuple[str, str]") -> None:
    _, page = built
    scenes = section(page, "Scenes")
    assert re.findall(r'<button type="button" class="seek" data-seek="([\d.]+)">(.*?)</button>', scenes) == [
        ("0.0", "Play s1 from 0.0 s"),
        ("6.0", "Play s2 from 6.0 s"),
    ]
    assert "s1 hook" in scenes and "s1 Hook" not in scenes
    assert "<table" in scenes and "<caption" in scenes
    assert "First spoken line" in scenes and ESCAPED_INJECTION in scenes
    assert 'type="radio"' not in scenes  # one cut in the newest version


def test_radio_group_picks_the_player_when_two_cuts(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "storyboard.md").write_text(STORYBOARD)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9")
    add_cut(v1, "a-9x16")
    _, page = build_ok(proj, env)
    scenes = section(page, "Scenes")
    radios = re.findall(r'<input type="radio" name="cut" value="(cut-\d)"', scenes)
    assert radios == ["cut-0", "cut-1"]
    watch = section(page, "Watch")
    assert re.search(r'<figure data-span="3"[^>]*>\s*<video id="cut-0"', watch)
    assert re.search(r'<figure data-span="1"[^>]*>\s*<video id="cut-1"', watch)
    assert "<q-grid>" in watch


def test_script_words_only_when_counts_match(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "v1").mkdir()
    (proj / "storyboard.md").write_text(
        "## Script\n\n1. only one line\n\n"
        "| Scene | Time | Narration | Notes |\n|---|---|---|---|\n"
        "| a | 0-2 | said in a | n |\n| b | 2-4 | said in b | n |\n| c | none | said in c | n |\n"
    )
    _, page = build_ok(proj, env)
    scenes = section(page, "Scenes")
    assert "only one line" not in scenes
    assert "said in a" in scenes and "said in c" in scenes
    assert scenes.count('class="seek"') == 2  # the row without a number gets no button
    assert 'data-seek="2"' in scenes


def test_text_column_is_the_last_resort_for_words(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "v1").mkdir()
    (proj / "storyboard.md").write_text(
        "| Scene | Time (s) | On-screen text |\n|---|---|---|\n| S1 **3D** | 0.0 to 15.0 (turn) | big title |\n"
    )
    _, page = build_ok(proj, env)
    scenes = section(page, "Scenes")
    assert "big title" in scenes
    assert "Play s1 from 0.0 s" in scenes
    assert "s1 3d" in scenes


def test_storyboard_without_a_scene_table_renders_as_text_with_tables(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "v1").mkdir()
    (proj / "storyboard.md").write_text(
        f"# Plan\n\nSome **intro** {INJECTION}\n\n## Costs\n\n| Item | Price |\n|---|---|\n| a | 1 |\n| b | 2 |\n\n- first\n- second\n"
    )
    src, page = build_ok(proj, env)
    scenes = section(page, "Scenes")
    assert '<table' in scenes and "<th scope=\"col\">Item</th>" in scenes and "<td>b</td>" in scenes
    assert "<strong>intro</strong>" in scenes and ESCAPED_INJECTION in scenes
    assert "<li>second</li>" in scenes
    assert 'class="seek"' not in scenes
    assert page.count("<h1") == 1  # the storyboard's own h1 is demoted


def test_scene_table_without_outer_pipes(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "v1").mkdir()
    (proj / "storyboard.md").write_text(
        "Scene | Time | Narration\n--- | --- | ---\ns1 | 0-5 | Hello\ns2 | 5-10 | Bye\n"
    )
    _, page = build_ok(proj, env)
    scenes = section(page, "Scenes")
    assert scenes.count('class="seek"') == 2
    assert "Hello" in scenes and "Bye" in scenes and 'data-seek="5"' in scenes

    mod = _load_module()
    assert [s.start for s in mod.parse_scenes("Scene | Time | Narration\n--- | --- | ---\ns1 | 0-5 | Hello\n")] == ["0"]
    html = mod.render_markdown("a | b\n--|--\n1 | 2\n3 | 4\n\nafter\n")
    assert html.count("<tr>") == 3 and "<td>3</td><td>4</td>" in html
    assert "<p>after</p>" in html


def test_heading_with_pipe_right_after_a_table_is_not_a_row() -> None:
    mod = _load_module()
    table = "Scene | Time | Narration\n--- | --- | ---\ns1 | 0-5 | Hello\n"
    scenes = mod.parse_scenes(table + "## Style | framing\nUse a wide shot.\n")
    assert [(s.scene_id, s.start, s.words) for s in scenes] == [("s1", "0", "Hello")]

    scenes = mod.parse_scenes(table.replace("Hello", "Fallback") + "## Script | Voiceover\n1. Spoken words\n")
    assert [(s.scene_id, s.start, s.words) for s in scenes] == [("s1", "0", "Spoken words")]

    html = mod.render_markdown(table + "## Style | framing\nUse a wide shot.\n")
    assert html.count("<tr>") == 2 and "<h2>Style | framing</h2>" in html
    assert "<td>## Style" not in html


def _load_module():
    spec = importlib.util.spec_from_file_location("review_page_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(mod)
    return mod


def test_render_markdown_table_unit() -> None:
    spec = importlib.util.spec_from_file_location("review_page_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(mod)
    html = mod.render_markdown("| a | b |\n|:--|--:|\n| 1 | `x\\|y` |\n| 2 |\n\n| lone | line |\n")
    assert html.count("<table") == 1
    assert "<th scope=\"col\">a</th>" in html and "<td>1</td>" in html
    assert "<code>x|y</code>" in html
    assert "<td>2</td><td></td>" in html  # short rows are padded
    assert "<p>| lone | line |</p>" in html  # no separator row, so it stays text


# stills ---------------------------------------------------------------------------------------


def test_stills_are_captioned_with_time_and_scene(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "storyboard.md").write_text(STORYBOARD)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9", ["still-01-3.70s.png", "still-02-6.00s.png", "still-03-12.00s.png", "odd name.png"])
    _, page = build_ok(proj, env)
    frames = section(page, "Frames")
    captions = re.findall(r"<figcaption>(.*?)</figcaption>", frames)
    assert "s1 hook, 3.7 s" in captions and "s2 payoff, 6 s" in captions and "s2 payoff, 12 s" in captions
    assert "odd name.png" in captions
    assert "sheet.png" not in frames


def test_frames_use_tabs_only_with_two_cuts(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9", ["still-01-1.00s.png"])
    _, page = build_ok(proj, env)
    assert "<q-tabs" not in section(page, "Frames")
    add_cut(v1, "a-9x16", [])
    _, page = build_ok(proj, env)
    frames = section(page, "Frames")
    assert frames.count("<q-tabs") == 1
    assert len(re.findall(r"<q-tabs[^>]*>\s*<section>", frames)) == 1
    assert frames.count("<h3>") == 2
    assert "no stills in frames/a-9x16/" in frames


# missing pieces -------------------------------------------------------------------------------


def test_missing_items_are_named(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "v1").mkdir()
    _, page = build_ok(proj, env)
    assert "no MP4" in section(page, "Watch")
    assert "no verify.json" in section(page, "Verify results")

    v1 = proj / "v1"
    add_cut(v1, "a-16x9")
    add_cut(v1, "a-9x16")
    write_verify(v1, {"a-16x9.mp4": _run(GOOD_CHECKS)})
    _, page = build_ok(proj, env)
    assert "no verify run for a-9x16.mp4" in section(page, "Verify results")
    frames = section(page, "Frames")
    assert "no stills in frames/a-16x9/" in frames and "no stills in frames/a-9x16/" in frames


def test_unreadable_verify_json_is_named(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    (v1 / "verify.json").write_text("{not json")
    _, page = build_ok(proj, env)
    assert "verify.json unreadable" in section(page, "Verify results")


def test_wrongly_typed_verify_fields_are_named_not_fatal(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9")
    add_cut(v1, "a-9x16")
    add_cut(v1, "a-1x1")
    sync_bad = _check("sync", "pass", {"worst_frames": 0, "beats": 5}, {"offset_frames_max": 1})
    (v1 / "verify.json").write_text(json.dumps({"runs": {
        "a-16x9.mp4": {"passed": True, "checks": 1},
        "a-9x16.mp4": 7,
        "a-1x1.mp4": _run([sync_bad]),
    }}))
    _, page = build_ok(proj, env)
    results = section(page, "Verify results")
    assert "verify.json checks unreadable for a-16x9.mp4" in results
    assert "verify.json run for a-9x16.mp4 unreadable" in results
    assert "verify.json sync beats unreadable for a-1x1.mp4" in results

    (v1 / "verify.json").write_text(json.dumps({"passed": True, "checks": "nope", "runs": None}))
    _, page = build_ok(proj, env)
    assert "verify.json runs unreadable" in section(page, "Verify results")

    (v1 / "verify.json").write_text(json.dumps({"passed": True, "checks": 1}))
    for stem in ("a-9x16", "a-1x1"):
        (v1 / (stem + ".mp4")).unlink()
    _, page = build_ok(proj, env)
    assert "verify.json checks unreadable" in section(page, "Verify results")


def test_flat_verify_and_flat_frames_still_render(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    (v1 / "frames").mkdir(parents=True)
    (v1 / "a-16x9.mp4").write_bytes(b"\x00mp4")
    (v1 / "frames" / "still-01-2.50s.png").write_bytes(b"png")
    (v1 / "verify.json").write_text(json.dumps({
        "version": "v1", "attempt": 2, "passed": False, "stop": False,
        "checks": [_check("contrast", "fail", 3.2, 4.5, "low contrast")],
    }))
    _, page = build_ok(proj, env)
    results = section(page, "Verify results")
    assert re.search(r"<th[^>]*>Contrast</th>\s*<td[^>]*>Fail</td>", results)
    assert "3.2" in results and "4.5" in results and "low contrast" in results
    assert 'src="v1/frames/still-01-2.50s.png"' in section(page, "Frames")
    assert "Verify failed" in re.search(r'<p class="q-lede">(.*?)</p>', page, re.S).group(1)


# outside calls --------------------------------------------------------------------------------


def test_outside_calls_grouped_and_cloud_calls_listed(built: "tuple[str, str]") -> None:
    _, page = built
    calls = section(page, "Outside calls")
    counts = re.search(r"<table>\s*<caption>[^<]*counted[^<]*</caption>.*?</table>", calls, re.S)
    assert counts, calls
    assert re.search(r"<td>hyperframes</td>\s*<td>render</td>\s*<td[^>]*>2</td>", counts.group(0))
    assert re.search(r"<td>elevenlabs</td>\s*<td>api\.elevenlabs\.io</td>\s*<td[^>]*>1</td>", counts.group(0))
    rows = re.findall(r"<tr>.*?</tr>", calls.split("Cloud and outside calls")[-1], re.S)
    by_provider = {p: r for r in rows for p in ("elevenlabs", "pexels", "hyperframes", "playwright") if f"<td>{p}</td>" in r}
    assert set(by_provider) == {"elevenlabs", "pexels"}
    assert "not allowed" in by_provider["pexels"] and "1234" in by_provider["elevenlabs"]
    assert "not allowed" not in by_provider["elevenlabs"]
    assert "/v1/tts" in by_provider["elevenlabs"] and "2026-10-22T10:00:00Z" in by_provider["elevenlabs"]
    assert "1 unreadable line" in calls


def test_outside_calls_what_ran_is_escaped(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "calls.jsonl").write_text(
        json.dumps({"provider": "<i>evil</i>", "method": "GET", "host": "<b>x</b>", "status": 200}) + "\n"
    )
    src, page = build_ok(proj, env)
    assert "&lt;b&gt;x&lt;/b&gt;" in src and "<b>x</b>" not in src
    assert "&lt;i&gt;evil&lt;/i&gt;" in page and "<i>evil</i>" not in page


def test_local_call_status_follows_each_providers_convention(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    (proj / "v1").mkdir()
    calls = [
        {"provider": "hyperframes", "subcommand": "render", "args": [], "status": 0},
        {"provider": "playwright", "method": "RECORD", "host": "localhost", "path": "/", "status": 200},
    ]
    (proj / "calls.jsonl").write_text("\n".join(json.dumps(c) for c in calls) + "\n")
    src, _ = build_ok(proj, env)
    assert "local call" not in src.split("every one to local tools")[-1].split("</li>")[0]

    calls += [
        {"provider": "hyperframes", "subcommand": "render", "args": [], "status": 1},
        {"provider": "playwright", "method": "RECORD", "host": "localhost", "path": "/", "status": 0},
    ]
    (proj / "calls.jsonl").write_text("\n".join(json.dumps(c) for c in calls) + "\n")
    src, _ = build_ok(proj, env)
    assert "2 local calls failed." in src


# earlier versions and compare -----------------------------------------------------------------


def test_earlier_versions_and_compare(built: "tuple[str, str]") -> None:
    _, page = built
    earlier = section(page, "Earlier versions")
    assert re.search(r"<h3[^>]*>v1</h3>", earlier)
    assert earlier.count("<video") >= 4  # v1's two players and the two compare players
    assert 'href="v1/verify.json"' in earlier
    assert "Verify failed" in earlier
    selects = re.findall(r"<select[^>]*>(.*?)</select>", earlier, re.S)
    assert len(selects) == 2
    for body in selects:
        options = re.findall(r"<option[^>]*>([^<]*)</option>", body)
        assert options == ["v2 / demo-16x9.mp4", "v1 / demo-16x9.mp4", "v1 / demo-9x16.mp4"]
    assert "<script>" in page and page.count("addEventListener(\"load\"") >= 2


def test_single_version_has_no_earlier_section_or_compare(tmp_path: Path, env: dict) -> None:
    proj = make_project(tmp_path)
    v1 = proj / "v1"
    v1.mkdir()
    add_cut(v1, "a-16x9", ["still-01-1.00s.png"])
    _, page = build_ok(proj, env)
    assert "Earlier versions" not in page and "<select" not in page


# builder failures -----------------------------------------------------------------------------


def _isolated_tree(tmp_path: Path) -> Path:
    scripts = tmp_path / "tree" / "skills" / "making-videos" / "scripts"
    scripts.mkdir(parents=True)
    for name in ("review_page.py", "_mv_common.py"):
        shutil.copy(SKILLS / "making-videos" / "scripts" / name, scripts / name)
    return scripts / "review_page.py"


def test_missing_html_builder_exits_1_naming_it(tmp_path: Path, env: dict) -> None:
    script = _isolated_tree(tmp_path)
    proj = make_project(tmp_path)
    proc = build(proj, env, script)
    assert proc.returncode == 1
    out = json.loads(proc.stdout.strip())
    assert "writing-html-artifacts" in out["error"] and "quirk_html.py" in out["error"]
    assert (proj / "review.src.html").is_file()
    assert not (proj / "review.html").exists()


def _stub_builder(script: Path, body: str) -> None:
    stub = script.parents[2] / "writing-html-artifacts" / "scripts"
    stub.mkdir(parents=True)
    (stub / "quirk_html.py").write_text(body)


@pytest.mark.parametrize(
    "body, code, needle",
    [
        ("import sys\nprint('not json')\nsys.exit(0)\n", 1, "JSON"),
        ("import sys, json\nprint(json.dumps({'error': 'bad template'}))\nsys.exit(2)\n", 1, "bad template"),
        ("import sys, json\nprint(json.dumps({'checks': {'passed': False, 'failures': "
         "[{'check': 'layout'}], 'warnings': []}}))\nsys.exit(1)\n", 1, "static checks"),
    ],
)
def test_builder_failures_exit_1(tmp_path: Path, env: dict, body: str, code: int, needle: str) -> None:
    script = _isolated_tree(tmp_path)
    _stub_builder(script, body)
    proj = make_project(tmp_path)
    proc = build(proj, env, script)
    assert proc.returncode == code
    out = json.loads(proc.stdout.strip())
    assert needle in out["error"]
    if "static checks" in needle:
        assert out["checks"]["passed"] is False
        assert out["source"] == str(proj / "review.src.html") and out["page"] == str(proj / "review.html")


def test_builder_is_called_with_the_project_dir(tmp_path: Path, env: dict) -> None:
    script = _isolated_tree(tmp_path)
    _stub_builder(script, (
        "import sys, json\n"
        "print(json.dumps({'checks': {'passed': True, 'failures': [], 'warnings': [' '.join(sys.argv[1:])]}}))\n"
    ))
    proj = make_project(tmp_path)
    proc = build(proj, env, script)
    assert proc.returncode == 0, proc.stdout
    argv = json.loads(proc.stdout)["checks"]["warnings"][0].split()
    assert argv[0] == "build" and argv[1] == str(proj / "review.src.html")
    assert argv[argv.index("--out") + 1] == str(proj / "review.html")
    assert argv[argv.index("--project-dir") + 1] == str(proj)
