"""Tests for the making-videos cloud gateway: auth headers, host allowlists, logging, secrecy."""
from __future__ import annotations

import http.server
import json
import shutil
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
CLOUD_PY = SCRIPTS / "cloud.py"
KEY = "sk-test-SECRET-key-123"
ALL_PROVIDERS = ["elevenlabs", "openai", "pexels", "pixabay", "freesound"]
KEY_VARS = {
    "elevenlabs": "ELEVENLABS_API_KEY",
    "openai": "OPENAI_API_KEY",
    "pexels": "PEXELS_API_KEY",
    "pixabay": "PIXABAY_API_KEY",
    "freesound": "FREESOUND_API_KEY",
}
BINARY = bytes(range(256)) * 4


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _serve(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.server.seen.append(
            {"method": self.command, "path": self.path, "headers": dict(self.headers), "body": body}
        )
        route = self.path.split("?")[0]
        if route == "/boom":
            self._reply(500, b'{"detail": "server exploded"}', "application/json")
        elif route == "/bin":
            self._reply(200, BINARY, "application/octet-stream")
        elif route == "/long":
            self._reply(200, b"x" * 5000, "text/plain")
        elif route == "/huge-error":
            self._reply(500, b"e" * 200_000, "text/plain")
        elif route == "/stream":
            self._stream(b"z" * 8192, 40, declare=False)
        elif route == "/declared":
            self._stream(b"z" * 8192, 40, declare=True)
        elif route == "/drip":
            self._stream(b"d" * 10, 40, delay=0.3, declare=True)
        elif route == "/drip-error":
            self._stream(b"e" * 10, 40, delay=0.3, declare=True, status=500)
        elif route == "/redir":
            self.send_response(302)
            self.send_header("Location", "https://evil.example.com/steal")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._reply(200, json.dumps({"ok": True}).encode(), "application/json")

    def _reply(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self, piece: bytes, count: int, declare: bool, delay: float = 0.0, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        if declare:
            self.send_header("Content-Length", str(len(piece) * count))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for _ in range(count):
                self.wfile.write(piece)
                self.wfile.flush()
                if delay:
                    time.sleep(delay)
        except OSError:
            pass
        self.close_connection = True

    do_GET = do_POST = _serve


@pytest.fixture()
def server():
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    httpd.seen = []
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "studio" / "videos" / "2026-10-22-demo"
    proj.mkdir(parents=True)
    write_brief(proj, ALL_PROVIDERS)
    return proj


def write_brief(proj: Path, allow: list) -> None:
    (proj / "brief.json").write_text(json.dumps({"slug": "demo", "cloud_allow": allow}))


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    out = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(tmp_path / "cache"),
        "QUIRK_CLOUD_LOOPBACK_OK": "1",
    }
    for var in KEY_VARS.values():
        out[var] = KEY
    return out


def base_url(httpd) -> str:
    return f"http://127.0.0.1:{httpd.server_address[1]}"


def call(project: Path, provider: str, url: str, env: dict, *extra: object, method: str = "GET"):
    proc = subprocess.run(
        [
            sys.executable,
            str(CLOUD_PY),
            "call",
            "--project",
            str(project),
            "--provider",
            provider,
            "--method",
            method,
            "--url",
            url,
            *map(str, extra),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    assert len(out.splitlines()) == 1
    return proc, json.loads(out)


def calls(project: Path) -> list:
    path = project / "calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def assert_key_absent(proc, project: Path) -> None:
    assert KEY not in proc.stdout
    assert KEY not in proc.stderr
    log = project / "calls.jsonl"
    if log.exists():
        assert KEY not in log.read_text()


@pytest.mark.parametrize(
    "provider,header,expected",
    [
        ("elevenlabs", "Xi-Api-Key", KEY),
        ("openai", "Authorization", f"Bearer {KEY}"),
        ("pexels", "Authorization", KEY),
        ("freesound", "Authorization", f"Token {KEY}"),
    ],
)
def test_provider_sends_documented_auth_header(server, project, env, provider, header, expected):
    proc, out = call(project, provider, base_url(server) + "/v1/thing", env)
    assert proc.returncode == 0, proc.stderr
    assert out["status"] == 200
    assert len(server.seen) == 1
    headers = {k.lower(): v for k, v in server.seen[0]["headers"].items()}
    assert headers[header.lower()] == expected
    assert "key=" not in server.seen[0]["path"]
    assert_key_absent(proc, project)


def test_pixabay_sends_key_as_query_parameter_only(server, project, env):
    proc, out = call(project, "pixabay", base_url(server) + "/api/?q=cats", env)
    assert proc.returncode == 0, proc.stderr
    seen = server.seen[0]
    assert seen["path"] == f"/api/?q=cats&key={KEY}"
    assert "authorization" not in {k.lower() for k in seen["headers"]}
    assert_key_absent(proc, project)
    record = calls(project)[0]
    assert record["path"] == "/api/"


def test_pixabay_replaces_a_key_the_caller_supplied(server, project, env):
    proc, _ = call(project, "pixabay", base_url(server) + "/api/?key=attacker&q=x", env)
    assert proc.returncode == 0
    assert server.seen[0]["path"].count("key=") == 1
    assert f"key={KEY}" in server.seen[0]["path"]


def test_calls_jsonl_record_has_no_query_and_no_key(server, project, env):
    proc, out = call(project, "pexels", base_url(server) + "/v1/search?query=beach&per_page=3", env)
    assert proc.returncode == 0
    (record,) = calls(project)
    assert set(record) == {"ts", "provider", "method", "host", "path", "status", "bytes"}
    assert record["provider"] == "pexels"
    assert record["method"] == "GET"
    assert record["host"] == "127.0.0.1"
    assert record["path"] == "/v1/search"
    assert record["status"] == 200
    assert record["bytes"] == out["bytes"] > 0
    assert "beach" not in json.dumps(record)
    assert_key_absent(proc, project)


def test_post_json_inline_and_from_file(server, project, env, tmp_path):
    proc, out = call(
        project, "openai", base_url(server) + "/v1/audio/speech", env,
        "--json", '{"input": "hi"}', method="POST",
    )
    assert proc.returncode == 0, proc.stderr
    seen = server.seen[0]
    assert seen["method"] == "POST"
    assert json.loads(seen["body"]) == {"input": "hi"}
    assert seen["headers"]["Content-Type"] == "application/json"

    body_file = tmp_path / "body.json"
    body_file.write_text('{"text": "from file"}')
    proc, _ = call(
        project, "elevenlabs", base_url(server) + "/v1/text-to-speech/abc", env,
        "--json", body_file, method="POST",
    )
    assert proc.returncode == 0
    assert json.loads(server.seen[1]["body"]) == {"text": "from file"}


def test_invalid_inline_json_is_a_usage_error_and_sends_nothing(server, project, env):
    proc, out = call(project, "openai", base_url(server) + "/x", env, "--json", "{nope", method="POST")
    assert proc.returncode == 2
    assert "error" in out
    assert server.seen == []


def test_out_file_is_binary_safe(server, project, env, tmp_path):
    dest = tmp_path / "assets" / "clip.bin"
    proc, out = call(project, "pexels", base_url(server) + "/bin", env, "--out", dest)
    assert proc.returncode == 0, proc.stderr
    assert dest.read_bytes() == BINARY
    assert out == {"status": 200, "out": str(dest), "bytes": len(BINARY)}


def test_without_out_json_has_a_capped_text_preview(server, project, env):
    proc, out = call(project, "pexels", base_url(server) + "/long", env)
    assert proc.returncode == 0
    assert out["out"] is None
    assert out["bytes"] == 5000
    assert out["preview"] == "x" * 2000


def test_preview_redacts_a_key_echoed_by_the_server(server, project, env):
    class Echo(_Handler):
        def _serve(self) -> None:
            self._reply(200, f"your key is {KEY}".encode(), "text/plain")

        do_GET = do_POST = _serve

    server.RequestHandlerClass = Echo
    proc, out = call(project, "pexels", base_url(server) + "/anything", env)
    assert proc.returncode == 0
    assert KEY not in proc.stdout
    assert "[redacted]" in out["preview"]


def test_preview_redacts_a_key_straddling_the_cutoff(server, project, env):
    class Straddle(_Handler):
        def _serve(self) -> None:
            self._reply(200, b"x" * 1990 + KEY.encode() + b"y" * 50, "text/plain")

        do_GET = do_POST = _serve

    server.RequestHandlerClass = Straddle
    proc, out = call(project, "pexels", base_url(server) + "/anything", env)
    assert proc.returncode == 0
    assert out["preview"].endswith("x" * 1990 + "[redacted]")
    assert KEY[:6] not in proc.stdout
    assert_key_absent(proc, project)


def test_log_write_failure_exits_1_and_says_the_request_was_sent(server, project, env):
    (project / "calls.jsonl").mkdir()
    proc, out = call(project, "pexels", base_url(server) + "/anything", env)
    assert proc.returncode == 1
    assert out["request_sent"] is True
    assert out["status"] == 200
    assert "calls.jsonl" in out["error"]
    assert len(server.seen) == 1
    assert KEY not in proc.stdout and KEY not in proc.stderr


def test_http_error_returns_status_exit_1_and_is_logged(server, project, env, tmp_path):
    dest = tmp_path / "never.bin"
    proc, out = call(project, "openai", base_url(server) + "/boom", env, "--out", dest)
    assert proc.returncode == 1
    assert out["status"] == 500
    assert "server exploded" in out["preview"]
    assert not dest.exists()
    (record,) = calls(project)
    assert record["status"] == 500
    assert_key_absent(proc, project)


@pytest.mark.parametrize("route", ["/stream", "/declared"])
def test_body_over_max_bytes_aborts_and_deletes_the_partial_file(server, project, env, tmp_path, route):
    dest = tmp_path / "big.bin"
    proc, out = call(project, "pexels", base_url(server) + route, env, "--out", dest, "--max-bytes", 100_000)
    assert proc.returncode == 1
    assert "--max-bytes" in out["error"]
    assert out["aborted"] == out["error"].split("aborted: ", 1)[1]
    assert not dest.exists()
    (record,) = calls(project)
    assert "--max-bytes" in record["aborted"]
    assert record["bytes"] == out["bytes"]
    if route == "/stream":
        assert 100_000 < record["bytes"] < 8192 * 40
    assert_key_absent(proc, project)


def _leftovers(directory: Path, keep: Path) -> list:
    return [p.name for p in directory.iterdir() if p != keep]


@pytest.mark.parametrize(
    "route,extra",
    [
        ("/long", ["--max-bytes", 100]),
        ("/declared", ["--max-bytes", 100_000]),
        ("/stream", ["--max-bytes", 100_000]),
        ("/drip", ["--timeout", 1]),
        ("/boom", []),
    ],
)
def test_failed_download_leaves_an_existing_out_file_untouched(server, project, env, tmp_path, route, extra):
    outdir = tmp_path / "assets"
    outdir.mkdir()
    dest = outdir / "existing.bin"
    dest.write_bytes(b"original bytes")
    proc, _ = call(project, "pexels", base_url(server) + route, env, "--out", dest, *extra)
    assert proc.returncode == 1
    assert dest.read_bytes() == b"original bytes"
    assert _leftovers(outdir, dest) == []


def test_successful_download_replaces_an_existing_out_file_without_leftovers(server, project, env, tmp_path):
    outdir = tmp_path / "assets"
    outdir.mkdir()
    dest = outdir / "existing.bin"
    dest.write_bytes(b"original bytes")
    proc, out = call(project, "openai", base_url(server) + "/bin", env, "--out", dest)
    assert proc.returncode == 0
    assert dest.read_bytes() == BINARY
    assert out["bytes"] == len(BINARY)
    assert _leftovers(outdir, dest) == []


def test_body_under_max_bytes_is_unaffected(server, project, env, tmp_path):
    dest = tmp_path / "ok.bin"
    proc, out = call(project, "openai", base_url(server) + "/bin", env, "--out", dest, "--max-bytes", len(BINARY))
    assert proc.returncode == 0
    assert dest.read_bytes() == BINARY
    assert "aborted" not in calls(project)[0]


def test_slow_body_past_timeout_aborts_and_deletes_the_partial_file(server, project, env, tmp_path):
    dest = tmp_path / "slow.bin"
    started = time.monotonic()
    proc, out = call(project, "pexels", base_url(server) + "/drip", env, "--out", dest, "--timeout", 1)
    assert time.monotonic() - started < 10
    assert proc.returncode == 1
    assert "--timeout" in out["aborted"]
    assert not dest.exists()
    (record,) = calls(project)
    assert "--timeout" in record["aborted"]
    assert 0 < record["bytes"] < 400


def test_http_error_body_is_read_only_up_to_64_kib(server, project, env):
    proc, out = call(project, "openai", base_url(server) + "/huge-error", env)
    assert proc.returncode == 1
    assert out["status"] == 500
    assert out["bytes"] == 64 * 1024
    assert len(out["preview"]) == 2000
    (record,) = calls(project)
    assert record["bytes"] == 64 * 1024


def test_trickling_http_error_body_is_cut_off_at_the_timeout(server, project, env):
    started = time.monotonic()
    proc, out = call(project, "openai", base_url(server) + "/drip-error", env, "--timeout", 1)
    assert time.monotonic() - started < 8
    assert proc.returncode == 1
    assert out["status"] == 500
    assert "--timeout" in out["aborted"]
    assert 0 < out["bytes"] < 400
    (record,) = calls(project)
    assert record["status"] == 500
    assert "--timeout" in record["aborted"]


@pytest.mark.parametrize("flag,value", [("--max-bytes", "0"), ("--max-bytes", "x"), ("--timeout", "0"), ("--timeout", "-1")])
def test_nonpositive_limits_are_usage_errors(server, project, env, flag, value):
    proc, out = call(project, "openai", base_url(server) + "/bin", env, flag, value)
    assert proc.returncode == 2
    assert calls(project) == []


def test_connection_failure_is_logged_with_status_zero(project, env):
    proc, out = call(project, "pexels", "http://127.0.0.1:1/x", env)
    assert proc.returncode == 1
    assert "error" in out
    assert calls(project)[0]["status"] == 0
    assert_key_absent(proc, project)


def test_provider_not_in_cloud_allow_is_refused_without_a_request(server, project, env):
    write_brief(project, ["pexels"])
    proc, out = call(project, "openai", base_url(server) + "/x", env)
    assert proc.returncode == 1
    assert "cloud_allow" in out["error"]
    assert server.seen == []
    assert calls(project) == []


def test_missing_brief_is_refused(server, tmp_path, env):
    empty = tmp_path / "bare"
    empty.mkdir()
    proc, out = call(empty, "pexels", base_url(server) + "/x", env)
    assert proc.returncode == 1
    assert server.seen == []


def test_unknown_provider_is_a_usage_error(server, project, env):
    proc, out = call(project, "midjourney", base_url(server) + "/x", env)
    assert proc.returncode == 2
    assert "error" in out
    assert server.seen == []


def test_missing_key_names_the_variable_not_its_value(server, project, env):
    del env["PEXELS_API_KEY"]
    proc, out = call(project, "pexels", base_url(server) + "/x", env)
    assert proc.returncode == 1
    assert "PEXELS_API_KEY" in out["error"]
    assert server.seen == []


def test_loopback_is_refused_unless_the_test_switch_is_set(server, project, env):
    del env["QUIRK_CLOUD_LOOPBACK_OK"]
    proc, out = call(project, "pexels", base_url(server) + "/x", env)
    assert proc.returncode == 1
    assert server.seen == []
    assert calls(project) == []


@pytest.mark.parametrize(
    "provider,url",
    [
        ("elevenlabs", "https://api.openai.com/v1/audio/speech"),
        ("openai", "https://evil.example.com/v1/audio/speech"),
        ("pexels", "https://pixabay.com/api/"),
        ("pixabay", "https://api.pexels.com/v1/search"),
        ("freesound", "https://freesound.org.evil.example/apiv2/search"),
        ("pexels", "http://api.pexels.com/v1/search"),
        ("elevenlabs", "ftp://api.elevenlabs.io/x"),
        ("pexels", "https://user:pw@api.pexels.com@evil.example.com/x"),
    ],
)
def test_disallowed_host_or_scheme_is_refused_without_a_request(project, env, provider, url):
    proc, out = call(project, provider, url, env)
    assert proc.returncode == 1
    assert "error" in out
    assert calls(project) == []
    assert_key_absent(proc, project)


def test_redirect_to_a_disallowed_host_is_not_followed(server, project, env):
    proc, out = call(project, "pexels", base_url(server) + "/redir", env)
    assert proc.returncode == 1
    assert "evil.example.com" in out["error"]
    assert len(server.seen) == 1
    assert calls(project)[0]["status"] == 302
    assert_key_absent(proc, project)


@pytest.fixture()
def tls_server(tmp_path: Path):
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl CLI not available")
    cert, key = tmp_path / "server.pem", tmp_path / "server.key"
    subprocess.run(
        [
            openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-subj", "/CN=127.0.0.1", "-keyout", str(key), "-out", str(cert),
            "-addext", "subjectAltName=IP:127.0.0.1",
            "-addext", "basicConstraints=critical,CA:TRUE",
        ],
        check=True,
        capture_output=True,
    )
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    httpd.seen = []
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(str(cert), str(key))
    httpd.socket = server_ctx.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, cert
    httpd.shutdown()
    httpd.server_close()


def test_https_call_trusts_the_ssl_cert_file(project, env, tls_server):
    httpd, cert = tls_server
    env["SSL_CERT_FILE"] = str(cert)
    proc, out = call(project, "pexels", f"https://127.0.0.1:{httpd.server_address[1]}/x", env)
    assert proc.returncode == 0, proc.stderr
    assert out["status"] == 200
    assert len(httpd.seen) == 1


def test_https_call_refuses_an_untrusted_certificate(project, env, tls_server, tmp_path):
    httpd, _ = tls_server
    env["QUIRK_CA_FALLBACKS"] = str(tmp_path / "missing.pem")
    proc, out = call(project, "pexels", f"https://127.0.0.1:{httpd.server_address[1]}/x", env)
    assert proc.returncode == 1
    assert "CERTIFICATE_VERIFY_FAILED" in out["error"]
    assert httpd.seen == []
