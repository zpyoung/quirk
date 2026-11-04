"""Tests for the mock registry: the ``mock`` and ``mock-export`` subcommands, ``step`` version checks
and the ``GET /_quirk/mock/<N>`` route.

The harness template is a stub in the test's tmp dir, selected with QUIRK_MOCK_HARNESS, so these
tests do not depend on the real harness files.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from tests.test_companion_app_server import MOCK_REVIEW, App, run, start_app, stop_app

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import mocks  # noqa: E402

BOOT = '<script id="quirk-mock-boot" type="application/json">null</script>'
CORE_MARK = "<!--quirk-harness-core-->"
TEMPLATE = f"<!doctype html><html><body><div id=h></div>{BOOT}{CORE_MARK}</body></html>"
CORE_JS = "window.__core = 1; var s = '</script><b>';"

SCREENS = {
    "ui_layer": True,
    "screens": [
        {
            "id": "home",
            "title": "Home",
            "purpose": "Landing page",
            "states": ["default", "empty"],
            "skipped_states": [{"state": "error", "reason": "static page"}],
            "elements": [
                {"pin": "cta", "label": "Start button", "component": "Button"},
                {"pin": "hero", "label": "Hero banner", "component": None},
            ],
        },
        {"id": "cart", "title": "Cart", "purpose": "Items", "states": ["default"]},
    ],
}
MOCK_HTML = "<!doctype html><html><head><title>m</title></head><body data-screen='home'><p>hi &lt; there</p></body></html>"

PIN_A = "mock:v1/home/default/cta/x10-y20"
PIN_B = "mock:v2/home/empty/hero/x0-y100"


def write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
    return path


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    template = write(tmp_path / "harness" / "mock-harness.html", TEMPLATE)
    write(tmp_path / "harness" / "harness-core.js", CORE_JS)
    monkeypatch.setenv("QUIRK_MOCK_HARNESS", str(template))
    return template


@pytest.fixture
def offline(tmp_path: Path) -> Path:
    """An app-mode session with no server running."""
    session = tmp_path / "offline"
    (session / "state").mkdir(parents=True)
    (session / "state" / "mode.json").write_text(json.dumps({"mode": "app"}))
    return session


@pytest.fixture
def app(tmp_path: Path, harness: Path):
    srv = start_app(tmp_path / "root", tmp_path / ".quirk" / "brainstorm" / "s1")
    try:
        yield srv
    finally:
        stop_app(srv)


def register(session: Path, tmp_path: Path, version: int = 1, html: str = MOCK_HTML, screens: object = SCREENS,
             changed: object = None, expect: int | None = 0, name: str = "mock.html"):
    args: list[object] = ["mock", session, write(tmp_path / "in" / name, html), "--version", version,
                          "--screens", write(tmp_path / "in" / "screens.json", screens)]
    if changed is not None:
        args += ["--changed", write(tmp_path / "in" / "changed.json", changed)]
    rc, out, err = run(*args)
    if expect is not None:
        assert rc == expect, (rc, out, err)
    return rc, out


def get(app: App, path: str, headers: dict | None = None):
    return app.request("GET", path, headers=headers)


def comment(app: App, block_id: str, text: str = "move this") -> str:
    status, _ = app.event("comment", {"block_id": block_id, "text": text})
    assert status == 204
    return app.snapshot()["threads"][-1]["id"]


def boot_of(page: str) -> dict:
    found = re.findall(r'<script id="quirk-mock-boot" type="application/json">(.*?)</script>', page, re.S)
    assert len(found) == 1
    return json.loads(found[0])


# ---- mock subcommand --------------------------------------------------------------------------


def test_mock_registers_a_version_without_a_server(offline: Path, tmp_path: Path) -> None:
    rc, out = register(offline, tmp_path)
    assert (rc, out) == (0, {"version": 1, "mock_url": "/_quirk/mock/1"})
    index = json.loads((offline / "state" / "mocks.json").read_text())
    entry = index["versions"]["1"]
    assert re.fullmatch(r"mocks/v1-[0-9a-f]+\.html", entry["file"])
    assert (offline / "state" / entry["file"]).read_text(encoding="utf-8") == MOCK_HTML
    assert entry["screens"] == SCREENS and entry["changed"] == []
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*", entry["registered_at"])


def test_mock_records_changed_pins(offline: Path, tmp_path: Path) -> None:
    register(offline, tmp_path)
    register(offline, tmp_path, 2, changed={"changed": ["cta", "hero"]})
    index = json.loads((offline / "state" / "mocks.json").read_text())
    assert index["versions"]["2"]["changed"] == ["cta", "hero"]


def test_mock_refuses_a_screen_session(tmp_path: Path) -> None:
    session = tmp_path / "screen"
    (session / "state").mkdir(parents=True)
    rc, out = register(session, tmp_path, expect=None)
    assert rc == 2 and out == {"error": "session is not in app mode"}


@pytest.mark.parametrize(
    ("version", "prior"),
    [(2, []), (0, []), (3, [1]), (1, [1, 2]), (4, [1, 2])],
)
def test_mock_sequencing(offline: Path, tmp_path: Path, version: int, prior: list[int]) -> None:
    for v in prior:
        register(offline, tmp_path, v)
    rc, out = register(offline, tmp_path, version, expect=None)
    assert rc == 2 and out["field"] == "version" and out["error"]
    index = json.loads((offline / "state" / "mocks.json").read_text()) if prior else {"versions": {}}
    assert sorted(map(int, index["versions"])) == prior


def test_mock_accepts_the_latest_again_and_latest_plus_one(offline: Path, tmp_path: Path) -> None:
    register(offline, tmp_path, 1)
    register(offline, tmp_path, 1, html="<html><body>replaced</body></html>")
    index = json.loads((offline / "state" / "mocks.json").read_text())
    assert "replaced" in (offline / "state" / index["versions"]["1"]["file"]).read_text()
    assert len(list((offline / "state" / "mocks").iterdir())) == 1
    register(offline, tmp_path, 2)
    register(offline, tmp_path, 2)
    register(offline, tmp_path, 3)
    assert register(offline, tmp_path, 3)[1]["version"] == 3


def test_mock_rejects_unreadable_non_utf8_and_oversize_html(offline: Path, tmp_path: Path) -> None:
    screens = write(tmp_path / "s.json", SCREENS)
    missing = run("mock", offline, tmp_path / "nope.html", "--version", 1, "--screens", screens)
    assert missing[0] == 2 and missing[1]["error"]
    bad = tmp_path / "bad.html"
    bad.write_bytes(b"<html>\xff\xfe</html>")
    assert run("mock", offline, bad, "--version", 1, "--screens", screens)[0] == 2
    big = tmp_path / "big.html"
    big.write_bytes(b"a" * (5 * 1024 * 1024 + 1))
    rc, out, _ = run("mock", offline, big, "--version", 1, "--screens", screens)
    assert rc == 2 and out["error"]
    assert not (offline / "state" / "mocks.json").exists()
    exact = tmp_path / "exact.html"
    exact.write_bytes(b"a" * (5 * 1024 * 1024))
    assert run("mock", offline, exact, "--version", 1, "--screens", screens)[0] == 0


def bad_screens() -> list[tuple[object, str]]:
    def screens(**over: object) -> dict:
        s = {"id": "home", "title": "Home", "purpose": "p", "states": ["default"]}
        s.update(over)
        return {"ui_layer": True, "screens": [s]}

    many = {"ui_layer": True, "screens": [
        {"id": f"s{i}", "title": "T", "purpose": "p", "states": ["default"]} for i in range(51)]}
    dup = {"ui_layer": True, "screens": [
        {"id": "a", "title": "T", "purpose": "p", "states": ["default"]},
        {"id": "a", "title": "T", "purpose": "p", "states": ["default"]}]}
    return [
        ([], ""),
        ({"screens": []}, "ui_layer"),
        ({"ui_layer": "yes", "screens": []}, "ui_layer"),
        ({"ui_layer": True}, "screens"),
        ({"ui_layer": True, "screens": []}, "screens"),
        ({"ui_layer": True, "screens": "x"}, "screens"),
        ({"ui_layer": True, "screens": [], "extra": 1}, "extra"),
        (many, "screens"),
        (dup, "screens[1].id"),
        (screens(id="Bad Id"), "screens[0].id"),
        (screens(id="a" * 41), "screens[0].id"),
        (screens(title=""), "screens[0].title"),
        (screens(title="t" * 81), "screens[0].title"),
        (screens(purpose=""), "screens[0].purpose"),
        (screens(purpose="p" * 201), "screens[0].purpose"),
        (screens(states=[]), "screens[0].states"),
        (screens(states=["a"] * 2), "screens[0].states[1]"),
        (screens(states=[f"s{i}" for i in range(9)]), "screens[0].states"),
        (screens(states=["Bad State"]), "screens[0].states[0]"),
        (screens(skipped_states=[{"state": "x"}]), "screens[0].skipped_states[0].reason"),
        (screens(skipped_states=[{"state": "X!", "reason": "r"}]), "screens[0].skipped_states[0].state"),
        (screens(skipped_states="x"), "screens[0].skipped_states"),
        (screens(elements=[{"pin": "Bad Pin", "label": "l", "component": None}]), "screens[0].elements[0].pin"),
        (screens(elements=[{"pin": "a", "label": "", "component": None}]), "screens[0].elements[0].label"),
        (screens(elements=[{"pin": "a", "label": "l", "component": 3}]), "screens[0].elements[0].component"),
        (screens(elements=[{"pin": "a", "label": "l", "component": None}] * 2), "screens[0].elements[1].pin"),
        (screens(surprise=1), "screens[0].surprise"),
    ]


@pytest.mark.parametrize(("screens", "field"), bad_screens())
def test_mock_rejects_a_bad_screens_file(offline: Path, tmp_path: Path, screens: object, field: str) -> None:
    rc, out = register(offline, tmp_path, screens=screens, expect=None)
    assert rc == 2 and out["error"] and out["field"] == field
    assert not (offline / "state" / "mocks.json").exists()


def test_mock_rejects_unparseable_screens_and_changed_files(offline: Path, tmp_path: Path) -> None:
    html = write(tmp_path / "m.html", MOCK_HTML)
    broken = write(tmp_path / "broken.json", "{nope")
    rc, out, _ = run("mock", offline, html, "--version", 1, "--screens", broken)
    assert rc == 2 and out["error"]
    rc, out, _ = run("mock", offline, html, "--version", 1, "--screens", tmp_path / "gone.json")
    assert rc == 2 and out["error"]


@pytest.mark.parametrize(
    ("changed", "field"),
    [
        ([], ""),
        ({}, "changed"),
        ({"changed": "cta"}, "changed"),
        ({"changed": ["Bad Pin"]}, "changed[0]"),
        ({"changed": [5]}, "changed[0]"),
        ({"changed": ["a"] * 501}, "changed"),
        ({"changed": [], "extra": 1}, "extra"),
    ],
)
def test_mock_rejects_a_bad_changed_file(offline: Path, tmp_path: Path, changed: object, field: str) -> None:
    rc, out = register(offline, tmp_path, changed=changed, expect=None)
    assert rc == 2 and out["error"] and out["field"] == field
    assert not (offline / "state" / "mocks.json").exists()


@pytest.mark.parametrize("surrogate", ["\ud800", "ok\udfff", "\ud83d"])
def test_mock_rejects_an_unpaired_surrogate_in_screens(offline: Path, tmp_path: Path, surrogate: str) -> None:
    screens = json.loads(json.dumps(SCREENS))
    screens["screens"][1]["title"] = surrogate
    rc, out = register(offline, tmp_path, screens=screens, expect=None)
    assert rc == 2 and out["error"] and out["field"] == "screens[1].title"
    assert not (offline / "state" / "mocks.json").exists()


def test_mock_rejects_an_unpaired_surrogate_in_any_screens_or_changed_string(offline: Path, tmp_path: Path) -> None:
    screens = json.loads(json.dumps(SCREENS))
    screens["screens"][0]["elements"][0]["component"] = "x\ud800"
    rc, out = register(offline, tmp_path, screens=screens, expect=None)
    assert rc == 2 and out["field"] == "screens[0].elements[0].component"
    rc, out = register(offline, tmp_path, changed={"changed": ["\ud800"]}, expect=None)
    assert rc == 2 and out["field"] == "changed[0]"
    rc, out = register(offline, tmp_path, screens={"ui_layer": True, "screens": SCREENS["screens"], "\ud800": 1},
                       expect=None)
    assert rc == 2 and out["field"] and "\ud800" not in out["field"]
    assert not (offline / "state" / "mocks.json").exists()


def test_a_registered_copy_is_immutable_to_later_source_edits(app: App, tmp_path: Path) -> None:
    source = write(tmp_path / "in" / "mock.html", MOCK_HTML)
    register(app.session, tmp_path)
    source.write_text("<html><body>CHANGED AFTER</body></html>", encoding="utf-8")
    status, body, _ = get(app, f"/_quirk/mock/1?t={app.token}")
    page = body.decode()
    assert status == 200
    assert "CHANGED AFTER" not in page and "hi &lt; there" in boot_of(page)["mock_html"]


# ---- step version check -----------------------------------------------------------------------


def test_step_rejects_an_unregistered_mock_version(offline: Path, tmp_path: Path) -> None:
    step = write(tmp_path / "step.json", {**MOCK_REVIEW, "version": 1})
    rc, out, _ = run("step", offline, step)
    assert rc == 2 and out["field"] == "version" and out["error"]
    assert not (offline / "state" / "current.json").exists()
    register(offline, tmp_path)
    rc, out, _ = run("step", offline, step)
    assert rc == 0 and out["step"].endswith("mock-review")
    rc, out, _ = run("step", offline, write(tmp_path / "step2.json", {**MOCK_REVIEW, "version": 2}))
    assert rc == 2 and out["field"] == "version"


# ---- route ------------------------------------------------------------------------------------


def test_route_serves_the_filled_harness(app: App, tmp_path: Path) -> None:
    register(app.session, tmp_path)
    register(app.session, tmp_path, 2, changed={"changed": ["cta"]})
    status, body, resp = get(app, f"/_quirk/mock/1?t={app.token}")
    page = body.decode()
    assert status == 200
    assert resp.getheader("Content-Type") == "text/html; charset=utf-8"
    assert resp.getheader("Cache-Control") == "no-store" and resp.getheader("X-Content-Type-Options") == "nosniff"
    boot = boot_of(page)
    assert boot == {
        "mode": "app", "version": 1, "latest": 2, "versions": [1, 2], "token": app.token,
        "screens": SCREENS, "changed": [], "mock_html": MOCK_HTML, "revision": boot["revision"],
    }
    assert boot["revision"] == app.snapshot()["mocks"]["revisions"]["1"]
    assert CORE_MARK not in page and "<script>" + CORE_JS.replace("</script", "<\\/script") + "</script>" in page
    boot2 = boot_of(get(app, f"/_quirk/mock/2?t={app.token}")[1].decode())
    assert boot2["version"] == 2 and boot2["changed"] == ["cta"]


def test_route_escapes_angle_brackets_in_the_boot_json(app: App, tmp_path: Path) -> None:
    html = f"<html><head></head><body>{BOOT}{CORE_MARK}</script><script>x</script></body></html>"
    register(app.session, tmp_path, html=html)
    page = get(app, f"/_quirk/mock/1?t={app.token}")[1].decode()
    boot_text = re.findall(r'<script id="quirk-mock-boot" type="application/json">(.*?)</script>', page, re.S)
    assert len(boot_text) == 1 and "<" not in boot_text[0] and "\\u003c" in boot_text[0]
    assert boot_of(page)["mock_html"] == html
    assert page.count('id="quirk-mock-boot"') == 1 and page.count(CORE_MARK) == 0


@pytest.mark.parametrize("query", ["", "?t=", "?t=wrong", "?x=1"])
def test_route_needs_the_session_token(app: App, tmp_path: Path, query: str) -> None:
    register(app.session, tmp_path)
    status, body, _ = get(app, f"/_quirk/mock/1{query}")
    assert status == 403 and json.loads(body) == {"error": "bad token"}
    # an unknown version with a bad token is also 403: the token comes first
    assert get(app, "/_quirk/mock/9")[0] == 403


def test_route_unknown_version_is_404(app: App, tmp_path: Path) -> None:
    register(app.session, tmp_path)
    for path in ("/_quirk/mock/2", "/_quirk/mock/0", "/_quirk/mock/x", "/_quirk/mock/01", "/_quirk/mock/"):
        assert get(app, f"{path}?t={app.token}")[0] == 404, path


def test_route_foreign_origin_or_host_is_403(app: App, tmp_path: Path) -> None:
    register(app.session, tmp_path)
    url = f"/_quirk/mock/1?t={app.token}"
    assert get(app, url, {"Origin": "http://evil.example"})[0] == 403
    assert get(app, url, {"Host": "evil.example"})[0] == 403


def test_route_500_when_the_template_is_missing_or_malformed(app: App, tmp_path: Path, harness: Path) -> None:
    register(app.session, tmp_path)
    url = f"/_quirk/mock/1?t={app.token}"
    for text in ("<html>no boot</html>", f"{BOOT}{BOOT}{CORE_MARK}", BOOT + "<html>no core</html>",
                 f"{BOOT}{CORE_MARK}{CORE_MARK}"):
        harness.write_text(text, encoding="utf-8")
        status, body, _ = get(app, url)
        assert status == 500 and json.loads(body) == {"error": "mock harness missing"}, text
    harness.write_text(TEMPLATE, encoding="utf-8")
    assert get(app, url)[0] == 200
    (harness.parent / "harness-core.js").unlink()
    assert get(app, url)[0] == 500
    (harness.parent / "harness-core.js").write_text(CORE_JS)
    harness.unlink()
    status, body, _ = get(app, url)
    assert status == 500 and json.loads(body) == {"error": "mock harness missing"}


def test_route_does_not_exist_in_screen_mode(tmp_path: Path, harness: Path) -> None:
    import http.client
    import os
    import signal
    import subprocess

    from tests.test_companion_app_server import CLI

    proc = subprocess.Popen(
        [sys.executable, str(CLI), "start", str(tmp_path / "scr"), "--foreground", "--port", "0"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy(),
    )
    try:
        info = json.loads(proc.stdout.readline())
        conn = http.client.HTTPConnection("127.0.0.1", info["port"], timeout=10)
        conn.request("GET", "/_quirk/mock/1?t=x")
        assert conn.getresponse().status == 404
        conn.close()
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
        proc.stdout.close()
        proc.stderr.close()


def test_snapshot_over_http_lists_mock_versions(app: App, tmp_path: Path) -> None:
    assert app.snapshot()["mocks"] == {"latest": None, "versions": [], "revisions": {}}
    register(app.session, tmp_path)
    register(app.session, tmp_path, 2)
    mocks = app.snapshot()["mocks"]
    assert (mocks["latest"], mocks["versions"]) == (2, [1, 2])
    assert set(mocks["revisions"]) == {"1", "2"} and mocks["revisions"]["1"] != mocks["revisions"]["2"]


def test_re_registering_a_version_changes_its_revision_in_boot_and_snapshot(app: App, tmp_path: Path) -> None:
    register(app.session, tmp_path)
    first = boot_of(get(app, f"/_quirk/mock/1?t={app.token}")[1].decode())["revision"]
    assert isinstance(first, str) and first == app.snapshot()["mocks"]["revisions"]["1"]
    register(app.session, tmp_path, html=MOCK_HTML.replace("hi", "bye"))
    second = boot_of(get(app, f"/_quirk/mock/1?t={app.token}")[1].decode())["revision"]
    assert second != first and second == app.snapshot()["mocks"]["revisions"]["1"]


# ---- mock-export ------------------------------------------------------------------------------


def export(session: Path, out_dir: Path, version: int = 1, expect: int | None = 0):
    rc, out, err = run("mock-export", session, "--version", version, "--out", out_dir)
    if expect is not None:
        assert rc == expect, (rc, out, err)
    return rc, out


def test_export_writes_three_files_with_an_offline_boot(offline: Path, tmp_path: Path, harness: Path) -> None:
    register(offline, tmp_path)
    out_dir = tmp_path / "out" / "mock"
    rc, out = export(offline, out_dir)
    assert out == {"files": [str(out_dir.resolve() / n) for n in ("mock.html", "screens.md", "review.json")]}
    assert sorted(p.name for p in out_dir.iterdir()) == ["mock.html", "review.json", "screens.md"]
    page = (out_dir / "mock.html").read_text(encoding="utf-8")
    boot = boot_of(page)
    assert boot["mode"] == "offline" and "token" not in boot and boot["version"] == 1
    assert boot["screens"] == SCREENS and boot["mock_html"] == MOCK_HTML and boot["changed"] == []
    assert isinstance(boot["revision"], str) and boot["revision"]
    assert CORE_MARK not in page


def test_export_with_a_running_server_never_leaks_the_token(app: App, tmp_path: Path) -> None:
    register(app.session, tmp_path)
    export(app.session, tmp_path / "exp")
    assert app.token not in (tmp_path / "exp" / "mock.html").read_text(encoding="utf-8")
    assert app.token not in (tmp_path / "exp" / "review.json").read_text(encoding="utf-8")


def test_export_screens_md_lists_screens_states_elements_and_gaps(offline: Path, tmp_path: Path, harness: Path) -> None:
    register(offline, tmp_path)
    export(offline, tmp_path / "o")
    md = (tmp_path / "o" / "screens.md").read_text(encoding="utf-8")
    assert "Home" in md and "Cart" in md and "Landing page" in md
    assert "default" in md and "empty" in md
    assert "error" in md and "static page" in md
    assert "Start button" in md and "Button" in md
    gaps = md.split("## Gaps", 1)[1]
    assert "Hero banner" in gaps and "Start button" not in gaps


def test_export_without_a_ui_layer_names_none_and_raises_no_gaps(offline: Path, tmp_path: Path, harness: Path) -> None:
    screens = {**SCREENS, "ui_layer": False}
    register(offline, tmp_path, screens=screens)
    export(offline, tmp_path / "o")
    md = (tmp_path / "o" / "screens.md").read_text(encoding="utf-8")
    assert "none (no UI layer)" in md
    assert "Hero banner" not in md.split("## Gaps", 1)[1]


def test_export_review_json_keeps_only_pin_threads_with_resolutions(app: App, tmp_path: Path) -> None:
    register(app.session, tmp_path)
    register(app.session, tmp_path, 2)
    t1 = comment(app, PIN_A, "move the button")
    comment(app, "design:s1", "not a pin")
    t3 = comment(app, PIN_B, "hero is wrong")
    comment(app, "mock:v1/home/default/cta/x101-y5", "x out of range")
    rc, _, _ = run("reply", app.session, t1, "--text", "done", "--resolve", "addressed")
    assert rc == 0
    export(app.session, tmp_path / "o", version=2)
    review = json.loads((tmp_path / "o" / "review.json").read_text(encoding="utf-8"))
    assert review["version"] == 2 and re.fullmatch(r"\d{4}-\d\d-\d\dT.*", review["exported_at"])
    assert [p["thread_id"] for p in review["pins"]] == [t1, t3]
    first, second = review["pins"]
    assert (first["version"], first["screen"], first["state"], first["pin"]) == (1, "home", "default", "cta")
    assert first["resolution"] == "addressed" and second["resolution"] is None
    assert [m["from"] for m in first["messages"]] == ["user", "agent"]
    assert first["messages"][0]["text"] == "move the button"
    assert all(isinstance(m["timestamp"], str) for m in first["messages"])
    assert (second["version"], second["state"], second["pin"]) == (2, "empty", "hero")


def test_export_unknown_version_or_unwritable_dir_exits_2(offline: Path, tmp_path: Path, harness: Path) -> None:
    register(offline, tmp_path)
    rc, out = export(offline, tmp_path / "o", version=7, expect=None)
    assert rc == 2 and out["field"] == "version" and not (tmp_path / "o").exists()
    blocker = write(tmp_path / "blocker", "a file")
    rc, out = export(offline, blocker / "sub", expect=None)
    assert rc == 2 and out["error"]


def test_export_without_the_template_exits_2(offline: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    register(offline, tmp_path)
    monkeypatch.setenv("QUIRK_MOCK_HARNESS", str(tmp_path / "missing.html"))
    rc, out = export(offline, tmp_path / "o", expect=None)
    assert rc == 2 and out["error"] == "mock harness missing"


# ---- pure helpers -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("block_id", "parsed"),
    [
        (PIN_A, {"version": 1, "screen": "home", "state": "default", "pin": "cta", "x": 10, "y": 20}),
        (PIN_B, {"version": 2, "screen": "home", "state": "empty", "pin": "hero", "x": 0, "y": 100}),
        ("mock:v9999/a/b/c.d_e-f/x100-y0", {"version": 9999, "screen": "a", "state": "b", "pin": "c.d_e-f", "x": 100, "y": 0}),
    ],
)
def test_parse_pin_accepts_pin_block_ids(block_id: str, parsed: dict) -> None:
    assert mocks.parse_pin(block_id) == parsed


@pytest.mark.parametrize(
    "block_id",
    [
        "design:s1", "mock:v0/a/b/c/x1-y1", "mock:v10000/a/b/c/x1-y1", "mock:v1/A/b/c/x1-y1",
        "mock:v1/a/b/_c/x1-y1", "mock:v1/a/b/c/x101-y1", "mock:v1/a/b/c/x1-y101", "mock:v1/a/b/c/x1-y1/extra",
        "mock:v1/a/b/c/x1000-y1", "mock:v1/a/b/c/x-1-y1", "mock:v1/a/b/c/x1-y", "", "mock:v1/a/b/c/x1-y1\n",
    ],
)
def test_parse_pin_rejects_everything_else(block_id: str) -> None:
    assert mocks.parse_pin(block_id) is None
