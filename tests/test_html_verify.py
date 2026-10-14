"""Tests for the browser verify runner (`htmlkit.verify_runner`) and `verify.mjs`.

Staleness tests always run. Browser tests need `scripts/verify/node_modules` and a launchable
browser; they skip otherwise, and never touch the network.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "writing-html-artifacts"
SCRIPTS = SKILL / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "html-verify"
sys.path.insert(0, str(SCRIPTS))

from htmlkit import verify_runner  # noqa: E402

SCREENSHOTS = ["375-light.png", "375-dark.png", "1280-light.png", "1280-dark.png"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_report_is_stale_when_report_missing(tmp_path: Path) -> None:
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    assert verify_runner.report_is_stale(page, tmp_path / "report.json") is True


def test_report_is_fresh_when_hash_matches(tmp_path: Path) -> None:
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"file_sha256": _sha(page)}))
    assert verify_runner.report_is_stale(page, report) is False


def test_report_is_stale_after_file_changes(tmp_path: Path) -> None:
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"file_sha256": _sha(page)}))
    page.write_text("<p>y</p>")
    assert verify_runner.report_is_stale(page, report) is True


def test_report_is_stale_when_report_unreadable(tmp_path: Path) -> None:
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    report = tmp_path / "report.json"
    report.write_text("not json")
    assert verify_runner.report_is_stale(page, report) is True


def test_no_node_gives_not_browser_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    monkeypatch.setattr(verify_runner.shutil, "which", lambda name: None)
    result = verify_runner.run_verify(page, tmp_path / "out")
    assert result["status"] == "not-browser-verified"
    assert result["reason"] == "no-node"
    assert result["file_sha256"] == _sha(page)


@pytest.mark.parametrize("node", [None, "/usr/bin/node"])
def test_missing_file_gives_missing_file_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, node: str | None) -> None:
    monkeypatch.setattr(verify_runner.shutil, "which", lambda name: node)
    result = verify_runner.run_verify(tmp_path / "gone.html", tmp_path / "out")
    assert result["status"] == "not-browser-verified"
    assert result["reason"] == "missing-file"
    assert result["file_sha256"] is None
    assert verify_runner.report_is_stale(tmp_path / "gone.html", tmp_path / "out" / "report.json") is True


def test_missing_file_with_unwritable_out_dir_still_returns(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    result = verify_runner.run_verify(tmp_path / "gone.html", blocker / "out")
    assert result["reason"] == "missing-file"


def _fake_verifier_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify_runner.shutil, "which", lambda name: "/usr/bin/node")
    monkeypatch.setattr(verify_runner, "_ensure_installed", lambda: None)


def test_a_verifier_crash_is_a_failed_result_not_a_missing_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_verifier_environment(monkeypatch)
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    done = subprocess.CompletedProcess([], 4, stdout="", stderr="net::ERR_FAILED boom")
    monkeypatch.setattr(verify_runner.subprocess, "run", lambda *a, **kw: done)
    result = verify_runner.run_verify(page, tmp_path / "out")
    assert result["status"] == "failed"
    assert result["reason"] == "verify-crashed" and "boom" in result["detail"]
    assert json.loads((tmp_path / "out" / "report.json").read_text())["status"] == "failed"


def test_a_verifier_timeout_is_a_failed_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_verifier_environment(monkeypatch)
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")

    def hang(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("node", 1)

    monkeypatch.setattr(verify_runner.subprocess, "run", hang)
    result = verify_runner.run_verify(page, tmp_path / "out")
    assert result["status"] == "failed" and result["reason"] == "verify-timeout"


def test_the_cli_exits_1_when_the_verifier_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import quirk_html

    _fake_verifier_environment(monkeypatch)
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    done = subprocess.CompletedProcess([], 4, stdout="", stderr="boom")
    monkeypatch.setattr(verify_runner.subprocess, "run", lambda *a, **kw: done)
    assert quirk_html.main(["verify", str(page)]) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "verify-crashed"


def test_default_out_dir_is_beside_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = tmp_path / "report.html"
    page.write_text("<p>x</p>")
    monkeypatch.setattr(verify_runner.shutil, "which", lambda name: None)
    verify_runner.run_verify(page)
    assert (tmp_path / "report.verify" / "report.json").is_file()


@pytest.fixture(scope="module")
def browser_ready(tmp_path_factory: pytest.TempPathFactory) -> None:
    if not (SCRIPTS / "verify" / "node_modules").is_dir():
        pytest.skip("scripts/verify/node_modules is absent; run pnpm install there")
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    probe = verify_runner.run_verify(FIXTURES / "ok.html", tmp_path_factory.mktemp("probe"))
    if probe["status"] == "not-browser-verified":
        pytest.skip(f"no browser could be launched ({probe.get('reason')})")


def _run(name: str, tmp_path: Path, mode: str = "offline") -> dict:
    return verify_runner.run_verify(FIXTURES / name, tmp_path / "out", mode=mode)


@pytest.mark.usefixtures("browser_ready")
def test_ok_fixture_passes_with_four_screenshots(tmp_path: Path) -> None:
    result = _run("ok.html", tmp_path)
    assert result["status"] == "passed", result
    assert result["file_sha256"] == _sha(FIXTURES / "ok.html")
    assert all(result["checks"][k]["passed"] for k in ("console", "viewports", "themes", "network"))
    assert sorted(Path(p).name for p in result["screenshots"]) == sorted(SCREENSHOTS)
    for name in SCREENSHOTS:
        assert (tmp_path / "out" / name).stat().st_size > 0
    assert result["requests"] == []
    assert verify_runner.report_is_stale(FIXTURES / "ok.html", tmp_path / "out" / "report.json") is False


@pytest.mark.usefixtures("browser_ready")
def test_fetching_fixture_fails_network_and_records_url(tmp_path: Path) -> None:
    result = _run("fetches.html", tmp_path)
    assert result["status"] == "failed"
    assert result["checks"]["network"]["passed"] is False
    assert any("https://example.com/x" in url for url in result["requests"])


@pytest.mark.usefixtures("browser_ready")
def test_overflow_fixture_fails_viewports(tmp_path: Path) -> None:
    result = _run("overflow.html", tmp_path)
    assert result["status"] == "failed"
    assert result["checks"]["viewports"]["passed"] is False
    assert result["checks"]["themes"]["passed"] is True


@pytest.mark.usefixtures("browser_ready")
def test_low_contrast_dark_fixture_fails_themes(tmp_path: Path) -> None:
    result = _run("lowcontrast-dark.html", tmp_path)
    assert result["status"] == "failed"
    assert result["checks"]["themes"]["passed"] is False
    assert any("dark" in d for d in result["checks"]["themes"]["details"])


class _Recorder:
    def __init__(self, url: str, paths: list[str]) -> None:
        self.url = url
        self.paths = paths


@pytest.fixture
def local_server() -> Iterator[_Recorder]:
    paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            paths.append(self.path)
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _Recorder(f"http://127.0.0.1:{server.server_address[1]}/data.json", paths)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _connected_page(tmp_path: Path, target: str) -> Path:
    page = tmp_path / "connected.html"
    page.write_text((FIXTURES / "connected.html").read_text().replace("__TARGET__", target))
    return page


@pytest.mark.usefixtures("browser_ready")
def test_connected_mode_lets_requests_through_and_reports_them(tmp_path: Path, local_server: _Recorder) -> None:
    page = _connected_page(tmp_path, local_server.url)
    result = verify_runner.run_verify(page, tmp_path / "out", mode="connected")
    assert result["checks"]["network"]["passed"] is True
    assert local_server.url in result["requests"]
    assert "/data.json" in local_server.paths
    assert result["status"] == "passed", result


@pytest.mark.usefixtures("browser_ready")
def test_offline_mode_blocks_the_same_page(tmp_path: Path, local_server: _Recorder) -> None:
    page = _connected_page(tmp_path, local_server.url)
    result = verify_runner.run_verify(page, tmp_path / "out", mode="offline")
    assert result["checks"]["network"]["passed"] is False
    assert local_server.url in result["requests"]
    assert local_server.paths == []


@pytest.mark.usefixtures("browser_ready")
def test_connected_mode_counts_console_errors_from_passed_through_requests(tmp_path: Path) -> None:
    page = tmp_path / "broken.html"
    page.write_text((FIXTURES / "connected.html").read_text().replace("__TARGET__", "http://127.0.0.1:1/refused"))
    result = verify_runner.run_verify(page, tmp_path / "out", mode="connected")
    assert result["checks"]["network"]["passed"] is True
    assert result["checks"]["console"]["passed"] is False


@pytest.fixture
def hanging_server() -> Iterator[str]:
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            release.wait(10)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/hang.js"
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.usefixtures("browser_ready")
def test_connected_navigation_timeout_is_a_network_failure_with_a_report(
    tmp_path: Path, hanging_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUIRK_VERIFY_NAV_TIMEOUT_MS", "1500")
    page = tmp_path / "hangs.html"
    page.write_text(f'<!doctype html><html><head><title>t</title><script src="{hanging_server}"></script></head><body><p>x</p></body></html>')
    result = verify_runner.run_verify(page, tmp_path / "out", mode="connected")
    assert result["status"] == "failed", result
    network = result["checks"]["network"]
    assert network["passed"] is False
    assert any("navigation to" in d and page.as_uri() in d for d in network["details"])
    assert (tmp_path / "out" / "report.json").is_file()
    assert verify_runner.report_is_stale(page, tmp_path / "out" / "report.json") is False


NOJS_SCREENSHOTS = ["375-light-nojs.png", "375-dark-nojs.png", "1280-light-nojs.png", "1280-dark-nojs.png"]
FOUR_CHECKS = {"console", "viewports", "themes", "network"}


@pytest.mark.usefixtures("browser_ready")
def test_no_js_passes_when_kit_elements_hold_plain_html(tmp_path: Path) -> None:
    result = _run_nojs("kit-fallback-ok.html", tmp_path)
    assert result["status"] == "passed", result
    assert result["no_js"] is True
    assert set(result["checks"]) == FOUR_CHECKS | {"fallback"}
    assert result["checks"]["fallback"]["passed"] is True
    assert sorted(Path(p).name for p in result["screenshots"]) == sorted(NOJS_SCREENSHOTS)


def _run_nojs(name: str, tmp_path: Path) -> dict:
    return verify_runner.run_verify(FIXTURES / name, tmp_path / "out", no_js=True)


@pytest.mark.usefixtures("browser_ready")
def test_no_js_fails_when_css_hides_an_unupgraded_element(tmp_path: Path) -> None:
    result = _run_nojs("kit-fallback-hidden.html", tmp_path)
    assert result["status"] == "failed"
    fallback = result["checks"]["fallback"]
    assert fallback["passed"] is False
    assert any("q-stat" in d for d in fallback["details"])
    assert all(result["checks"][k]["passed"] for k in FOUR_CHECKS)


@pytest.mark.usefixtures("browser_ready")
def test_no_js_exempts_empty_elements_with_data_from(tmp_path: Path) -> None:
    result = _run_nojs("kit-fallback-datafrom.html", tmp_path)
    assert result["checks"]["fallback"]["passed"] is True, result
    assert result["status"] == "passed"


@pytest.mark.usefixtures("browser_ready")
def test_no_js_fails_an_empty_element_without_data_from(tmp_path: Path) -> None:
    page = tmp_path / "empty.html"
    page.write_text((FIXTURES / "kit-fallback-datafrom.html").read_text().replace(' data-from="#t"', ""))
    result = verify_runner.run_verify(page, tmp_path / "out", no_js=True)
    assert result["checks"]["fallback"]["passed"] is False
    assert any("q-chart" in d for d in result["checks"]["fallback"]["details"])


@pytest.mark.usefixtures("browser_ready")
def test_no_js_disables_page_scripts(tmp_path: Path) -> None:
    page = tmp_path / "scripted.html"
    page.write_text(
        (FIXTURES / "ok.html").read_text().replace("</body>", "<script>throw new Error('ran')</script></body>")
    )
    assert verify_runner.run_verify(page, tmp_path / "js")["checks"]["console"]["passed"] is False
    assert verify_runner.run_verify(page, tmp_path / "nojs", no_js=True)["checks"]["console"]["passed"] is True


@pytest.mark.usefixtures("browser_ready")
def test_a_normal_run_reports_exactly_the_four_original_checks(tmp_path: Path) -> None:
    result = _run("kit-fallback-ok.html", tmp_path)
    assert set(result["checks"]) == FOUR_CHECKS
    assert result["no_js"] is False
    assert sorted(Path(p).name for p in result["screenshots"]) == sorted(SCREENSHOTS)
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert set(report) == {"status", "file_sha256", "browser", "checks", "screenshots", "requests"}


@pytest.mark.parametrize(("argv_extra", "expected"), [([], False), (["--no-js"], True)])
def test_the_cli_no_js_flag_reaches_run_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv_extra: list[str], expected: bool
) -> None:
    import quirk_html

    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    calls: list[tuple[tuple, dict]] = []

    def fake(*args: object, **kwargs: object) -> dict:
        calls.append((args, kwargs))
        return {"status": "passed", "no_js": kwargs.get("no_js", False)}

    monkeypatch.setattr(verify_runner, "run_verify", fake)
    assert quirk_html.main(["verify", str(page), "--out-dir", str(tmp_path / "o"), *argv_extra]) == 0
    (args, kwargs), = calls
    assert kwargs.get("no_js", args[3] if len(args) > 3 else False) is expected


def test_run_verify_passes_the_flag_to_node_and_records_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_verifier_environment(monkeypatch)
    page = tmp_path / "a.html"
    page.write_text("<p>x</p>")
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        seen.append(cmd)
        (tmp_path / "out").mkdir(exist_ok=True)
        (tmp_path / "out" / "report.json").write_text(json.dumps({"status": "passed", "checks": {}}))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(verify_runner.subprocess, "run", fake_run)
    assert verify_runner.run_verify(page, tmp_path / "out", no_js=True)["no_js"] is True
    assert seen[-1][-1] == "--no-js"
    assert verify_runner.run_verify(page, tmp_path / "out")["no_js"] is False
    assert "--no-js" not in seen[-1]
