"""Tests for the browser verify runner (`htmlkit.verify_runner`) and `verify.mjs`.

Staleness tests always run. Browser tests need `scripts/verify/node_modules` and a launchable
browser; they skip otherwise, and never touch the network.
"""

from __future__ import annotations

import hashlib
import json
import shutil
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
