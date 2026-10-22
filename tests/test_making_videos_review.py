"""Tests for the making-videos review page builder."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "making-videos"
    / "scripts"
    / "review_page.py"
)

INJECTION = '<script>alert("pwn")</script>'

STORYBOARD = f"""# Launch storyboard

Opening paragraph with **bold words** and `inline code` here.

## Scenes

- first bullet
- second bullet

1. numbered one
2. numbered two

```
fenced <b>code</b> line
```

Injection attempt: {INJECTION}

| unknown | table |
"""


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(tmp_path / "cache"),
    }


def build(project: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(project)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "studio" / "videos" / "2026-10-22-demo"
    proj.mkdir(parents=True)
    brief = {
        "slug": "demo",
        "product": "Acme <b>Pro</b>",
        "title": f"Demo {INJECTION}",
        "length_s": 42,
        "aspects": ["16:9", "9:16"],
        "narration": True,
        "cloud_allow": ["elevenlabs"],
        "music": {"source": "none", "path": None},
        "created": "2026-10-22",
    }
    (proj / "brief.json").write_text(json.dumps(brief))
    (proj / "storyboard.md").write_text(STORYBOARD)

    v1 = proj / "v1"
    (v1 / "frames").mkdir(parents=True)
    (v1 / "demo-16x9.mp4").write_bytes(b"\x00mp4")
    (v1 / "demo-9x16.mp4").write_bytes(b"\x00mp4")
    (v1 / "demo-16x9.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
    (v1 / "frames" / "sheet.png").write_bytes(b"png")
    (v1 / "frames" / "still-01.png").write_bytes(b"png")
    (v1 / "verify.json").write_text(
        json.dumps(
            {
                "version": "v1",
                "attempt": 2,
                "passed": False,
                "checks": [
                    {
                        "name": "contrast",
                        "status": "fail",
                        "measured": 3.2,
                        "threshold": 4.5,
                        "detail": f"low contrast {INJECTION}",
                    },
                    {
                        "name": "loudness",
                        "status": "pass",
                        "measured": -16.1,
                        "threshold": "-17..-15 LUFS",
                        "detail": "ok",
                    },
                ],
            }
        )
    )

    v2 = proj / "v2"
    (v2 / "frames").mkdir(parents=True)
    (v2 / "demo-16x9.mp4").write_bytes(b"\x00mp4")
    (v2 / "frames" / "sheet.png").write_bytes(b"png")
    (v2 / "verify.json").write_text(
        json.dumps(
            {
                "version": "v2",
                "attempt": 1,
                "passed": True,
                "checks": [
                    {
                        "name": "fonts",
                        "status": "pass",
                        "measured": 3,
                        "threshold": 3,
                        "detail": "all families injected",
                    }
                ],
            }
        )
    )

    (proj / "v3").mkdir()

    calls = [
        {"ts": "2026-10-22T10:00:00Z", "provider": "elevenlabs", "method": "POST",
         "host": "api.elevenlabs.io", "path": "/v1/tts", "status": 200, "bytes": 1234},
        {"ts": "2026-10-22T10:01:00Z", "provider": "hyperframes", "subcommand": "render",
         "args": ["render", "--output", "v1/demo.mp4"], "status": 0},
        {"ts": "2026-10-22T10:01:30Z", "provider": "playwright", "method": "RECORD",
         "host": "localhost", "path": "/app", "status": 200, "bytes": 5},
        {"ts": "2026-10-22T10:02:00Z", "provider": "pexels", "method": "GET",
         "host": "api.pexels.com", "path": "/v1/search", "status": 200, "bytes": 99},
    ]
    (proj / "calls.jsonl").write_text("\n".join(json.dumps(c) for c in calls) + "\n")
    return proj


@pytest.fixture()
def page(project: Path, env: dict) -> str:
    proc = build(project, env)
    assert proc.returncode == 0, proc.stderr
    return (project / "review.html").read_text(encoding="utf-8")


def test_stdout_is_one_json_object(project: Path, env: dict) -> None:
    proc = build(project, env)
    assert proc.returncode == 0
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"page": str(project / "review.html")}


def test_missing_project_exits_2(tmp_path: Path, env: dict) -> None:
    proc = build(tmp_path / "nope", env)
    assert proc.returncode == 2
    assert "error" in json.loads(proc.stdout.strip())


def test_header_shows_brief(page: str) -> None:
    assert "42" in page
    assert "16:9" in page and "9:16" in page
    assert "2026-10-22" in page
    assert "Acme &lt;b&gt;Pro&lt;/b&gt;" in page
    assert "<dt>Narration</dt><dd>on</dd>" in page


def test_relative_video_srcs_per_version(page: str) -> None:
    for rel in ("v1/demo-16x9.mp4", "v1/demo-9x16.mp4", "v2/demo-16x9.mp4"):
        assert re.search(r'<video[^>]*\ssrc="%s"' % re.escape(rel), page), rel
    assert 'controls' in page and 'preload="metadata"' in page and "playsinline" in page


def test_versions_newest_first(page: str) -> None:
    ids = re.findall(r'<section class="version" id="(v\d+)"', page)
    assert ids == ["v3", "v2", "v1"]


def test_srt_and_frames_linked(page: str) -> None:
    assert 'href="v1/demo-16x9.srt"' in page
    assert 'src="v1/frames/sheet.png"' in page
    assert 'src="v1/frames/still-01.png"' in page


def test_missing_pieces_named_for_empty_version(page: str) -> None:
    v3 = page[page.index('id="v3"'): page.index('id="v2"')]
    assert "no MP4" in v3
    assert "no verify.json" in v3
    assert "no frames/sheet.png" in v3
    assert "<video" not in v3


def test_complete_version_reports_no_missing(page: str) -> None:
    v2 = page[page.index('id="v2"'): page.index('id="v1"')]
    assert "no verify.json" not in v2
    assert "no MP4" not in v2
    assert "no stills" in v2


def test_check_rows_with_measured_values(page: str) -> None:
    v1 = page[page.index('id="v1"'):]
    assert re.search(r"<td[^>]*>contrast</td>\s*<td[^>]*>fail</td>\s*<td[^>]*>3\.2</td>\s*<td[^>]*>4\.5</td>", v1)
    assert re.search(r"<td[^>]*>loudness</td>\s*<td[^>]*>pass</td>\s*<td[^>]*>-16\.1</td>", v1)
    assert "attempt" in v1.lower()
    assert re.search(r"fail", v1, re.I)
    v2 = page[page.index('id="v2"'): page.index('id="v1"')]
    assert re.search(r"<td[^>]*>fonts</td>", v2)


def test_injection_is_escaped(page: str) -> None:
    assert INJECTION not in page
    assert "<script>alert" not in page
    assert "&lt;script&gt;alert(&quot;pwn&quot;)&lt;/script&gt;" in page
    assert "fenced &lt;b&gt;code&lt;/b&gt; line" in page


def test_markdown_subset_rendered(page: str) -> None:
    assert re.search(r"<h1[^>]*>Launch storyboard</h1>", page)
    assert re.search(r"<h2[^>]*>Scenes</h2>", page)
    assert "<strong>bold words</strong>" in page
    assert "<code>inline code</code>" in page
    assert re.search(r"<ul>\s*<li>first bullet</li>\s*<li>second bullet</li>\s*</ul>", page)
    assert re.search(r"<ol>\s*<li>numbered one</li>\s*<li>numbered two</li>\s*</ol>", page)
    assert re.search(r"<pre><code>fenced", page)
    assert "| unknown | table |" in page


def test_compare_selects_list_all_versions(page: str) -> None:
    selects = re.findall(r"<select[^>]*>(.*?)</select>", page, re.S)
    assert len(selects) == 2
    for body in selects:
        for v in ("v1", "v2", "v3"):
            assert re.search(r"<option[^>]*>[^<]*\b%s\b" % v, body), v
    assert page.count("<script>") == 1


def test_compare_players_present(page: str) -> None:
    assert page.count('class="compare-player"') == 2


def test_outside_calls_table_highlights_disallowed(page: str) -> None:
    assert "api.elevenlabs.io" in page and "/v1/tts" in page and "1234" in page
    rows = re.findall(r"<tr[^>]*>.*?</tr>", page, re.S)
    by_provider = {}
    for row in rows:
        for p in ("elevenlabs", "hyperframes", "pexels"):
            if re.search(r"<td[^>]*>%s</td>" % p, row):
                by_provider[p] = row
    assert set(by_provider) == {"elevenlabs", "hyperframes", "pexels"}
    assert "not-allowed" in by_provider["pexels"]
    assert "not-allowed" not in by_provider["elevenlabs"]
    assert "not-allowed" not in by_provider["hyperframes"]
    assert "render --output v1/demo.mp4" in by_provider["hyperframes"]
    assert "RECORD localhost" in page


def test_outside_calls_what_ran_is_escaped(tmp_path: Path, env: dict) -> None:
    proj = tmp_path / "esc"
    proj.mkdir()
    (proj / "calls.jsonl").write_text(
        json.dumps({"provider": "hyperframes", "subcommand": "<b>x</b>", "args": ["<i>"], "status": 0}) + "\n"
    )
    proc = build(proj, env)
    assert proc.returncode == 0, proc.stderr
    html = (proj / "review.html").read_text(encoding="utf-8")
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "<b>x</b>" not in html


def test_self_contained(page: str) -> None:
    assert not re.search(r'(?:src|href|action)\s*=\s*["\']?https?://', page)
    assert not re.search(r"url\(\s*[\"']?https?://", page)
    assert not re.search(r"@import|<link\b", page)
    assert "<script src" not in page


def test_theme_and_layout(page: str) -> None:
    assert ":root" in page
    assert "@media (prefers-color-scheme: dark)" in page
    assert re.search(r"body\s*{[^}]*background", page)
    assert 'name="viewport"' in page


def test_missing_optional_files_still_builds(tmp_path: Path, env: dict) -> None:
    proj = tmp_path / "bare"
    proj.mkdir()
    proc = build(proj, env)
    assert proc.returncode == 0
    html = (proj / "review.html").read_text(encoding="utf-8")
    assert "brief.json" in html and "storyboard.md" in html


def _check(name: str, status: str, measured: object, detail: str = "ok") -> dict:
    return {"name": name, "status": status, "measured": measured, "threshold": None, "detail": detail}


def _runs_project(tmp_path: Path, runs: dict) -> Path:
    proj = tmp_path / "studio" / "videos" / "2026-10-22-runs"
    v1 = proj / "v1"
    v1.mkdir(parents=True)
    (proj / "brief.json").write_text(json.dumps({"title": "Runs", "aspects": ["16:9", "9:16"]}))
    for name in ("demo-16x9.mp4", "demo-9x16.mp4"):
        (v1 / name).write_bytes(b"\x00mp4")
        stem = name[:-4]
        (v1 / "frames" / stem).mkdir(parents=True)
        (v1 / "frames" / stem / "sheet.png").write_bytes(b"png")
        (v1 / "frames" / stem / ("still-01-%s.png" % stem)).write_bytes(b"png")
    (v1 / "verify.json").write_text(json.dumps({
        "version": "v1", "passed": all(r["passed"] for r in runs.values()), "runs": runs,
    }))
    return proj


def _run(passed: bool, attempt: int, checks: list, failed: int = None) -> dict:
    run = {"attempts": [], "attempt": attempt, "passed": passed, "stop": False, "checks": checks, "frames": {}}
    if failed is not None:
        run["failed_attempts"] = failed
    return run


def test_each_mp4_run_shows_its_checks_and_frames(tmp_path: Path, env: dict) -> None:
    proj = _runs_project(tmp_path, {
        "demo-16x9.mp4": _run(True, 1, [_check("fonts", "pass", 2)]),
        "demo-9x16.mp4": _run(False, 3, [_check("title_safe", "fail", {"collisions": 1}, "text near the edge")], failed=2),
    })
    proc = build(proj, env)
    assert proc.returncode == 0, proc.stderr
    page = (proj / "review.html").read_text(encoding="utf-8")
    wide = page[page.index('id="run-demo-16x9.mp4"'): page.index('id="run-demo-9x16.mp4"')]
    tall = page[page.index('id="run-demo-9x16.mp4"'):]
    assert re.search(r"<td[^>]*>fonts</td>\s*<td[^>]*>pass</td>", wide)
    assert "title_safe" not in wide
    assert re.search(r"<td[^>]*>title_safe</td>\s*<td[^>]*>fail</td>", tall)
    assert "attempt 3 (2 failed)" in tall and "attempt 1" in wide and "failed)" not in wide
    frames = page[page.index("<h3>Frames</h3>"):]
    wide_frames = frames[frames.index("<h4>demo-16x9.mp4</h4>"): frames.index("<h4>demo-9x16.mp4</h4>")]
    tall_frames = frames[frames.index("<h4>demo-9x16.mp4</h4>"):]
    assert 'src="v1/frames/demo-16x9/sheet.png"' in wide_frames
    assert 'src="v1/frames/demo-9x16/sheet.png"' not in wide_frames
    assert 'src="v1/frames/demo-9x16/sheet.png"' in tall_frames
    assert 'src="v1/frames/demo-9x16/still-01-demo-9x16.png"' in tall_frames
    assert "Missing" not in page
    assert re.search(r'class="verdict fail"[^>]*>\s*<strong>Verify failed', page)


def test_all_runs_passing_reads_as_a_pass(tmp_path: Path, env: dict) -> None:
    proj = _runs_project(tmp_path, {
        "demo-16x9.mp4": _run(True, 1, [_check("fonts", "pass", 2)]),
        "demo-9x16.mp4": _run(True, 2, [_check("fonts", "pass", 2)]),
    })
    assert build(proj, env).returncode == 0
    page = (proj / "review.html").read_text(encoding="utf-8")
    assert "Verify failed" not in page
    assert page.count("Verify passed") >= 1


def test_an_mp4_without_a_verify_run_is_named_missing(tmp_path: Path, env: dict) -> None:
    proj = _runs_project(tmp_path, {"demo-16x9.mp4": _run(True, 1, [_check("fonts", "pass", 2)])})
    assert build(proj, env).returncode == 0
    page = (proj / "review.html").read_text(encoding="utf-8")
    assert "no verify run for demo-9x16.mp4" in page


def test_run_names_and_check_text_are_escaped(tmp_path: Path, env: dict) -> None:
    proj = _runs_project(tmp_path, {
        "demo-16x9.mp4": _run(False, 1, [_check("fonts", "fail", 1, INJECTION)]),
        INJECTION: _run(True, 1, []),
    })
    assert build(proj, env).returncode == 0
    page = (proj / "review.html").read_text(encoding="utf-8")
    assert INJECTION not in page and "<script>alert" not in page
