"""Tests for the optional code-walkthrough template (code_walkthrough.py), run through subprocess on a tmp project."""
from __future__ import annotations

import html
import importlib.util
import json
import re
import signal
import subprocess
import sys
import wave
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
CW_PY = SCRIPTS / "code_walkthrough.py"

sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("code_walkthrough_for_tests", CW_PY)
assert _spec is not None and _spec.loader is not None
cw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cw)

SOURCE = "\n".join([
    "def short(value):",
    '    """A docstring line."""',
    "    return value",
    "def long_one():",
    "    result = compute_something(alpha_parameter, beta_parameter, gamma_parameter, delta_parameter_value)",
    "    return result",
    "# trailing comment",
]) + "\n"


def write_wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(b"\x00\x00" * int(24000 * seconds))


def within(seconds: float, fn, *args):
    """``fn(*args)``, failing the test instead of hanging when it has not returned after ``seconds``."""
    def stop(*_):
        raise TimeoutError(f"{fn.__name__} did not return within {seconds} s")
    old = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn(*args)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


class Walkthrough:
    """A tmp studio and project with two narration lines, word timings, a source file and a spec."""

    def __init__(self, tmp_path: Path, spec: "dict | None" = None, brand_colors: "dict | None" = None):
        self.studio = tmp_path / "studio"
        self.project = tmp_path / "studio" / "videos" / "2026-11-02-demo"
        brand_dir = self.studio / "brands" / "acme"
        (brand_dir / "fonts").mkdir(parents=True)
        (brand_dir / "fonts" / "Display-Medium.ttf").write_bytes(b"not a real font")
        (brand_dir / "brand.json").write_text(json.dumps({
            "product": "acme", "confirmed": True,
            "colors": brand_colors or {"bg-subtle": "#fcfaf9", "fg": "#000000", "fg-secondary": "#666666",
                                       "border": "#d8d4d1", "primary": "#0129f1", "accent": "#dcec5a"},
            "fonts": {"display": {"family": "Display", "files": ["fonts/Display-Medium.ttf"]},
                      "body": {"family": "Inter", "files": []}},
            "logo": None, "voice": {"engine": "kokoro", "id": "af_heart"},
        }))
        (self.project / "assets" / "src").mkdir(parents=True)
        (self.project / "scenes").mkdir()
        (self.project / "scenes" / "index.html").write_text("<!doctype html>")
        (self.project / "brief.json").write_text(json.dumps({"product": "acme", "narration": True}))
        (self.project / "assets" / "src" / "demo.py").write_text(SOURCE)
        lines = [{"id": "a", "text": "Here is the short function.", "start_s": 0},
                 {"id": "b", "text": "Then the long one returns.", "start_s": 0}]
        (self.project / "assets" / "lines.json").write_text(json.dumps(lines))
        write_wav(self.project / "assets" / "voice" / "a.wav", 2.0)
        write_wav(self.project / "assets" / "voice" / "b.wav", 1.5)
        # "short" lands after the cards' entrance settles, so its ring gets a sync beat
        words = {"a": [("Here", 0.0), ("is", 0.3), ("the", 0.5), ("short", 1.5), ("function.", 1.8)],
                 "b": [("Then", 0.0), ("the", 0.3), ("long", 0.5), ("one", 0.8), ("returns.", 1.0)]}
        for lid, items in words.items():
            (self.project / "assets" / "voice" / f"{lid}.words.json").write_text(
                json.dumps([{"text": t, "start": s, "end": s + 0.2} for t, s in items]))
        self.spec = spec or {
            "sources": {"demo": "assets/src/demo.py"},
            "sync_shift": {"b:long": 0.05},
            "scenes": [
                {"id": "s1", "type": "cards", "lines": ["a"], "heading": "Demo",
                 "cards": [{"eye": "1", "title": "Short", "ring": "a:short"}]},
                {"id": "s2", "type": "code", "lines": ["b"], "eyebrow": "demo.py", "heading": "Long",
                 "source": "demo", "excerpt": [[1, 3], "...", [4, 6]], "visible": 3,
                 "bands": [{"at": "b:then", "lines": [1, 3]}, {"at": "b:long", "lines": [4, 6]}],
                 "chips": [{"at": "b:long", "text": "the long one"}]},
            ],
        }
        (self.project / "kit").mkdir()
        (self.project / "kit" / "walkthrough.json").write_text(json.dumps(self.spec))

    def run(self, command: str, *extra: str) -> "tuple[int, dict]":
        proc = subprocess.run(
            [sys.executable, str(CW_PY), command, "--project", str(self.project), *extra],
            capture_output=True, text=True, timeout=60,
            env={"PATH": "/usr/bin:/bin", "HOME": str(self.studio.parent), "QUIRK_STUDIO": str(self.studio)},
        )
        try:
            return proc.returncode, json.loads(proc.stdout)
        except ValueError:
            pytest.fail(f"{command} printed no JSON object (exit {proc.returncode}); stderr:\n{proc.stderr}")

    def lines(self) -> dict:
        return {l["id"]: l for l in json.loads((self.project / "assets" / "lines.json").read_text())}

    def page(self, sid: str) -> str:
        return (self.project / "scenes" / "compositions" / f"{sid}.html").read_text()


@pytest.fixture()
def walk(tmp_path: Path) -> Walkthrough:
    return Walkthrough(tmp_path)


def test_timeline_places_lines_from_measured_clip_lengths(walk):
    code, out = walk.run("timeline")
    assert code == 0, out
    lines = walk.lines()
    # scene 1 starts at 0 with a 0.3 s lead; scene 2 starts after line a (2.0 s) and the 0.6 s scene gap
    assert lines["a"]["start_s"] == 0.3
    assert out["scenes"][1]["start"] == 2.9 and lines["b"]["start_s"] == 3.2
    assert out["total"] == round(3.2 + 1.5 + 3.0, 2)
    assert json.loads((walk.project / "kit" / "timeline.json").read_text()) == out


def test_timeline_refuses_a_line_no_scene_places(tmp_path):
    w = Walkthrough(tmp_path)
    w.spec["scenes"][1]["lines"] = []
    (w.project / "kit" / "walkthrough.json").write_text(json.dumps(w.spec))
    code, out = w.run("timeline")
    assert code == 1 and "b" in out["error"] and "not placed" in out["error"]


def test_build_writes_registered_scenes_root_page_and_assets(walk):
    walk.run("timeline")
    code, out = walk.run("build")
    assert code == 0, out
    assert out["scenes"] == ["s1", "s2"]
    for sid in ("s1", "s2"):
        page = walk.page(sid)
        assert page.startswith("<template>") and f'window.__timelines["{sid}"] = tl;' in page
        assert '--font-display: "Display", sans-serif;' in page
    index = (walk.project / "scenes" / "index.html").read_text()
    assert 'data-composition-src="compositions/s2.html" data-start="2.9"' in index
    assert '<audio id="vo-b" class="clip" src="assets/voice/b.wav" data-start="3.2"' in index
    assert "@font-face" in index and "font-weight: 500" in index
    assert (walk.project / "scenes" / "assets" / "fonts" / "Display-Medium.ttf").is_file()
    assert (walk.project / "scenes" / "assets" / "voice" / "a.wav").is_file()


def test_cues_land_one_frame_before_the_word_plus_the_measured_shift(walk):
    walk.run("timeline")
    walk.run("build")
    page = walk.page("s2")
    # "long" is 0.5 s into line b, which starts 0.3 s into scene 2; one frame early, then +0.05 shift
    expected = round(0.3 + 0.5 - 1 / 30 + 0.05, 3)
    assert f"ease: \"expo.out\", immediateRender: false }}, {expected});" in page
    beats = json.loads((walk.project / "beats.json").read_text())
    ring = next(b for b in beats if b["id"] == "s1-ring0")
    assert ring["expected_s"] == 1.8 and ring["clip"] == "assets/voice/a.wav"


def test_an_unknown_cue_word_names_the_words_that_were_heard(tmp_path):
    w = Walkthrough(tmp_path)
    w.spec["scenes"][1]["bands"][0]["at"] = "b:missing"
    (w.project / "kit" / "walkthrough.json").write_text(json.dumps(w.spec))
    w.run("timeline")
    code, out = w.run("build")
    assert code == 1 and "b:missing" in out["error"] and "heard: Then the long one returns." in out["error"]


def test_rows_outside_the_window_are_hidden_and_shown_as_the_panel_scrolls(walk):
    walk.run("timeline")
    walk.run("build")
    page = walk.page("s2")
    # row 4 starts line 4, below the three-row window until the band scrolls to it
    assert re.search(r'gsap\.set\("[^"]*#s2-row4[^"]*", \{ visibility: "hidden" \}\);', page)
    assert re.search(r'tl\.set\("[^"]*#s2-row4[^"]*", \{ visibility: "visible" \}', page)
    assert 'tl.fromTo("#s2-scroll"' in page


def test_long_lines_soft_wrap_without_a_line_number_on_the_continuation():
    rows, where, starts = cw.code_rows(SOURCE.split("\n"), [5], "demo")
    assert len(rows) == 2 and where[5] == (0, 1) and starts == {0}
    assert '<span class="k-no">5</span>' in rows[0]
    assert '<span class="k-no"> </span>' in rows[1]


DEEP_LINE = " " * 76 + "x" * 60


def test_a_line_indented_past_the_wrap_width_still_wraps():
    rows, indent = within(0.5, cw.wrap_points, DEEP_LINE)
    assert indent == 76
    assert rows[0][0] == 0 and rows[-1][1] == len(DEEP_LINE)
    assert all(b > a for a, b in rows)


def test_continuation_rows_of_a_deeply_indented_line_fit_the_wrap_width():
    rows, _, _ = within(0.5, cw.code_rows, [DEEP_LINE], [1], "deep")
    assert len(rows) > 1
    for row in rows[1:]:
        shown = html.unescape(re.sub(r"<[^>]+>", "", row.split('<span class="k-tx">', 1)[1]))
        assert len(shown) <= cw.WRAP, shown


def test_scrolling_never_opens_the_window_on_a_wrapped_tail_row():
    starts = {0, 1, 3, 4}
    # row 2 is the tail of the line starting at row 1; the band (rows 3-4) still fits from row 1
    assert cw.snap_scroll(2, 3, 4, 4, starts) == 1
    # when it does not fit from above, snap down to the next line start instead
    assert cw.snap_scroll(2, 3, 5, 3, starts) == 3


def test_docstring_lines_can_be_coloured_as_strings():
    rows, _, _ = cw.code_rows(SOURCE.split("\n"), [{"line": 2, "as": "str"}], "demo")
    assert 'class="t-str"' in rows[0] and 't-kw' not in rows[0]


def test_custom_scenes_get_the_kit_and_their_cues_filled(tmp_path):
    w = Walkthrough(tmp_path)
    (w.project / "kit" / "s3.html").write_text(
        '<template><style>{{kit_css}}</style><div id="root" data-composition-id="s3"></div>'
        "<script>const tl = gsap.timeline({ paused: true }); tl.set('#x', {}, {{cue:b:returns}});"
        ' window.__timelines["s3"] = tl;</script></template>')
    w.spec["scenes"][1]["lines"] = []
    w.spec["scenes"].append({"id": "s3", "type": "custom", "lines": ["b"], "file": "kit/s3.html"})
    (w.project / "kit" / "walkthrough.json").write_text(json.dumps(w.spec))
    w.run("timeline")
    code, out = w.run("build")
    assert code == 0, out
    page = w.page("s3")
    assert ".k-chip {" in page and "{{" not in page
    assert f"{{}}, {round(0.3 + 1.0 - 1 / 30, 3)});" in page


def test_a_role_with_no_matching_brand_token_asks_for_spec_colors(tmp_path):
    w = Walkthrough(tmp_path, brand_colors={"paper": "#ffffff", "fg": "#000000"})
    w.run("timeline")
    code, out = w.run("build")
    assert code == 1 and "spec.colors.ground" in out["error"] and "paper" in out["error"]


def _with_scene(w: Walkthrough, k: int, scene: dict) -> None:
    w.spec["scenes"][k] = scene
    (w.project / "kit" / "walkthrough.json").write_text(json.dumps(w.spec))


def test_files_scene_lists_rows_and_highlights_one_on_its_cue(tmp_path):
    w = Walkthrough(tmp_path)
    _with_scene(w, 0, {"id": "s1", "type": "files", "lines": ["a"], "heading": "Files", "files": [
        {"path": "src/app.py", "add": "+12", "remove": "-3", "tag": "new"},
        {"path": "src/short.py", "add": "+1", "highlight": "a:short"}]})
    w.run("timeline")
    code, out = w.run("build")
    assert code == 0, out
    page = w.page("s1")
    assert "src/app.py" in page and ">+12<" in page and ">-3<" in page and ">new<" in page
    # "short" is 1.5 s into line a, which starts 0.3 s into scene 1; the tween lands one frame early
    t = round(0.3 + 1.5 - 1 / 30, 3)
    assert f'tl.fromTo("#s1-hl1", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, ease: "expo.out" }}, {t});' in page
    assert 'tl.fromTo("#s1-hl0"' not in page
    beats = json.loads((w.project / "beats.json").read_text())
    assert [b["id"] for b in beats] == ["s1-row1"] and beats[0]["region"][1] == 240 + 112 + 10


def test_files_scene_takes_at_most_six_rows(tmp_path):
    w = Walkthrough(tmp_path)
    _with_scene(w, 0, {"id": "s1", "type": "files", "lines": ["a"], "files": [{"path": f"f{k}"} for k in range(7)]})
    w.run("timeline")
    code, out = w.run("build")
    assert code == 1 and "files needs 1 to 6 rows" in out["error"]


def test_panels_scene_places_two_columns_and_moves_the_band_between_steps(tmp_path):
    w = Walkthrough(tmp_path)
    _with_scene(w, 1, {"id": "s2", "type": "panels", "lines": ["b"], "footer": "fine print", "panels": [
        {"eye": "before", "rows": ["one", "two"]},
        {"eye": "after", "rows": ["a", ["label", "value"], "c", "d"],
         "steps": [{"at": "b:then", "row": 1}, {"at": "b:long", "row": 3}]}]})
    w.run("timeline")
    code, out = w.run("build")
    assert code == 0, out
    page = w.page("s2")
    assert 'id="s2-p0" style="left:120px;' in page and 'id="s2-p1" style="left:980px;' in page
    assert "width:820px" in page and ">label<" in page and ">value<" in page and "fine print" in page
    # mono rows are 64 px apart, so moving from row 1 to row 3 is 128 px; "long" carries a 0.05 s sync shift
    first = round(0.3 + 0.0 - 1 / 30, 3)
    second = round(0.3 + 0.5 - 1 / 30 + 0.05, 3)
    assert f'tl.fromTo("#s2-p1-band", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, ease: "expo.out" }}, {first});' in page
    assert (f'tl.fromTo("#s2-p1-band", {{ y: 0 }}, {{ y: 128, duration: 0.35, ease: "expo.out", '
            f'immediateRender: false }}, {second});') in page
    assert "s2-p0-band" not in page


def test_panels_scene_takes_at_most_two_panels(tmp_path):
    w = Walkthrough(tmp_path)
    _with_scene(w, 1, {"id": "s2", "type": "panels", "lines": ["b"], "panels": [{}, {}, {}]})
    w.run("timeline")
    code, out = w.run("build")
    assert code == 1 and "panels needs 1 or 2 panels" in out["error"]


def _bad_brief(w):
    (w.project / "brief.json").write_text("{not json")


def _line_without_id(w):
    (w.project / "assets" / "lines.json").write_text(json.dumps([{"text": "no id"}]))


def _clip_that_is_not_a_wav(w):
    (w.project / "assets" / "voice" / "a.wav").write_bytes(b"not a wav")


def _brand_colour_that_is_not_hex(w):
    brand = w.studio / "brands" / "acme" / "brand.json"
    doc = json.loads(brand.read_text())
    doc["colors"]["accent"] = "yellow"
    brand.write_text(json.dumps(doc))


def _chip_without_text(w):
    w.spec["scenes"][1]["chips"] = [{"at": "b:long"}]
    (w.project / "kit" / "walkthrough.json").write_text(json.dumps(w.spec))


@pytest.mark.parametrize("command,break_input", [
    ("timeline", _bad_brief),
    ("timeline", _line_without_id),
    ("timeline", _clip_that_is_not_a_wav),
    ("build", _brand_colour_that_is_not_hex),
    ("build", _chip_without_text),
])
def test_malformed_inputs_exit_1_with_a_json_error_instead_of_a_traceback(tmp_path, command, break_input):
    w = Walkthrough(tmp_path)
    if command == "build":
        assert w.run("timeline")[0] == 0
    break_input(w)
    code, out = w.run(command)
    assert code == 1 and out["error"]
