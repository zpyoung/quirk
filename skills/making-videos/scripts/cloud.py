#!/usr/bin/env python3
"""The only door to cloud APIs for the making-videos skill: one allowlisted, logged HTTPS call.

``cloud.py call --project DIR --provider P --method GET|POST --url URL [--json BODY] [--out FILE]``
prints one JSON object ``{"status", "out", "bytes"}`` (plus a ``preview`` of at most 2000 text
characters when ``--out`` is not given, and an ``error`` key on failure). ``--json`` is a file path
or inline JSON sent as application/json. Diagnostics go to stderr.

A response body larger than ``--max-bytes`` (default 2 GiB) or still arriving after ``--timeout``
seconds in total (default 300) aborts the call: the log record gains an ``aborted`` reason and the
bytes read so far, and the exit code is 1. The body streams into a temporary file beside ``--out``
that replaces it only after a complete 2xx download, so a failed call leaves an existing ``--out``
untouched. An HTTP error body is read only up to 64 KiB and within the same ``--timeout``.

Exit codes: 0 ok; 1 refused or failed (provider not in the brief's ``cloud_allow``, key env var
unset, URL scheme or host not allowed for the provider, redirect to a disallowed host, HTTP error
status, response over the size or time limit, network failure); 2 usage error (including an unknown provider or malformed ``--json``).

Credentials come only from the provider's env var (``PROVIDER_KEY_ENV``) and are sent only to the
provider's API hosts, never to its CDN hosts: ``xi-api-key`` for elevenlabs, ``Authorization:
Bearer`` for openai (speech and images), a bare ``Authorization`` value for pexels, a ``key``
query parameter for pixabay, ``Authorization: Token`` for freesound. A key never reaches stdout,
stderr or ``calls.jsonl``; an echo of it in a response preview is redacted.

Every attempted request, including HTTP errors, appends ``ts, provider, method, host, path, status,
bytes`` to ``<project>/calls.jsonl``; the path carries no query string. Refusals make no request
and log nothing. Only ``https`` is allowed. Setting ``QUIRK_CLOUD_LOOPBACK_OK=1`` additionally
allows ``http`` to 127.0.0.1 and localhost for any provider; it exists so tests can run a local
server and must not be set in real use.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NoReturn, Optional

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import (  # noqa: E402
    EXIT_FAILED,
    EXIT_USAGE,
    PROVIDER_KEY_ENV,
    emit,
    load_brief,
    log_call,
    ssl_context,
)

LOOPBACK_ENV = "QUIRK_CLOUD_LOOPBACK_OK"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost")
PREVIEW_CHARS = 2000
MIN_KEY_FRAGMENT = 4
CHUNK = 1 << 16
TIMEOUT_S = 120
DEFAULT_MAX_BYTES = 2 << 30
DEFAULT_TOTAL_TIMEOUT_S = 300.0
ERROR_BODY_CAP = 64 << 10
USER_AGENT = "quirk-making-videos/1"

PROVIDERS = {
    "elevenlabs": {
        "hosts": ("api.elevenlabs.io", "api.us.elevenlabs.io", "api.eu.residency.elevenlabs.io",
                  "api.in.residency.elevenlabs.io", "api.sg.residency.elevenlabs.io"),
        "credential_hosts": None,
    },
    "openai": {"hosts": ("api.openai.com",), "credential_hosts": None},
    "pexels": {
        "hosts": ("api.pexels.com", "videos.pexels.com", "images.pexels.com"),
        "credential_hosts": ("api.pexels.com",),
    },
    "pixabay": {
        "hosts": ("pixabay.com", "cdn.pixabay.com"),
        "credential_hosts": ("pixabay.com",),
    },
    "freesound": {
        "hosts": ("freesound.org", "cdn.freesound.org"),
        "credential_hosts": ("freesound.org",),
    },
}
assert set(PROVIDERS) == set(PROVIDER_KEY_ENV)


class _Refused(Exception):
    """A request that must not be made, or must not be followed."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class _Aborted(Exception):
    """A response that exceeded the size or time limit; ``nbytes`` is what was read before aborting."""

    def __init__(self, reason: str, status: int, nbytes: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.nbytes = nbytes


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def _positive_float(value: str) -> float:
    number = float(value)
    if not number > 0 or number == float("inf"):
        raise argparse.ArgumentTypeError("must be a finite number greater than 0")
    return number


def _loopback_ok() -> bool:
    return os.environ.get(LOOPBACK_ENV) == "1"


def check_url(provider: str, url: str) -> urllib.parse.SplitResult:
    """Return the parsed ``url`` or raise ``_Refused`` when it is not allowed for ``provider``."""
    parts = urllib.parse.urlsplit(url)
    try:
        host = (parts.hostname or "").lower()
        parts.port
    except ValueError:
        raise _Refused(f"not a valid URL: {parts.netloc!r}")
    if parts.username is not None or parts.password is not None:
        raise _Refused("URLs with embedded credentials are not allowed")
    if host in LOOPBACK_HOSTS and _loopback_ok():
        if parts.scheme not in ("http", "https"):
            raise _Refused(f"scheme {parts.scheme!r} is not allowed")
        return parts
    if parts.scheme != "https":
        raise _Refused(f"only https URLs are allowed, got {parts.scheme or 'no scheme'!r}")
    if host not in PROVIDERS[provider]["hosts"]:
        raise _Refused(f"host {host or '(none)'!r} is not an allowed {provider} host")
    return parts


def _gets_credential(provider: str, host: str) -> bool:
    if host in LOOPBACK_HOSTS and _loopback_ok():
        return True
    allowed = PROVIDERS[provider]["credential_hosts"]
    return allowed is None or host in allowed


def _credential_headers(provider: str, key: str) -> dict:
    if provider == "elevenlabs":
        return {"xi-api-key": key}
    if provider == "openai":
        return {"Authorization": f"Bearer {key}"}
    if provider == "pexels":
        return {"Authorization": key}
    if provider == "freesound":
        return {"Authorization": f"Token {key}"}
    return {}


def _with_pixabay_key(parts: urllib.parse.SplitResult, key: str) -> str:
    pairs = [kv for kv in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if kv[0] != "key"]
    pairs.append(("key", key))
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(pairs)))


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to a URL the provider allows, dropping credentials elsewhere."""

    def __init__(self, provider: str, credential_names: "tuple[str, ...]") -> None:
        self.provider = provider
        self.credential_names = {n.lower() for n in credential_names}

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            parts = check_url(self.provider, newurl)
        except _Refused as exc:
            host = urllib.parse.urlsplit(newurl).hostname or "(none)"
            raise _Refused(f"redirect to {host} refused: {exc}", status=code)
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and not _gets_credential(self.provider, (parts.hostname or "").lower()):
            for name in list(new.headers):
                if name.lower() in self.credential_names:
                    del new.headers[name]
        return new


def _read_body_arg(value: str) -> bytes:
    raw = value.encode("utf-8")
    if not value.lstrip().startswith(("{", "[", '"')):
        try:
            if Path(value).is_file():
                raw = Path(value).read_bytes()
        except OSError:
            pass
    try:
        json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        emit({"error": f"--json is neither a JSON file nor valid inline JSON: {exc}"}, EXIT_USAGE)
    return raw


def _redact(text: str, key: str) -> str:
    return text.replace(key, "[redacted]") if key else text


def _preview(data: bytes, key: str) -> str:
    """Capped text preview of a response with the API key removed, including a key cut by the cap."""
    text = _redact(data.decode("utf-8", errors="replace"), key)
    cut = text[:PREVIEW_CHARS]
    if key and len(text) > PREVIEW_CHARS:
        for size in range(min(len(key) - 1, len(cut)), MIN_KEY_FRAGMENT - 1, -1):
            if cut.endswith(key[:size]):
                return cut[:-size] + "[redacted]"
    return cut


def _fail(message: str, key: str = "", **extra: object) -> NoReturn:
    message = _redact(message, key)
    print(message, file=sys.stderr)
    emit({"error": message, **extra}, EXIT_FAILED)


def _read_error_body(exc: urllib.error.HTTPError, deadline: float) -> "tuple[bytes, bool]":
    """Read at most ``ERROR_BODY_CAP`` bytes of an HTTP error body, stopping at ``deadline``.

    Returns the bytes read and whether the deadline (or a socket timeout) cut the read short.
    """
    data = b""
    read = getattr(exc, "read1", exc.read)
    try:
        while len(data) < ERROR_BODY_CAP:
            if time.monotonic() > deadline:
                return data, True
            chunk = read(min(CHUNK, ERROR_BODY_CAP - len(data))) or b""
            if not chunk:
                break
            data += chunk
    except (socket.timeout, TimeoutError):
        return data, True
    except OSError:
        pass
    return data, False


def _cmd_call(args: argparse.Namespace) -> None:
    provider = args.provider
    project = Path(args.project)
    body = _read_body_arg(args.json) if args.json else None

    try:
        brief = load_brief(project)
    except (FileNotFoundError, ValueError) as exc:
        _fail(f"cannot read the project brief: {exc}")
    allowed = brief.get("cloud_allow") if isinstance(brief, dict) else None
    if not isinstance(allowed, list) or provider not in allowed:
        _fail(f"provider {provider!r} is not in the project brief's cloud_allow; ask the user first")

    key_var = PROVIDER_KEY_ENV[provider]
    key = os.environ.get(key_var, "")
    if not key:
        _fail(f"{key_var} is not set; the {provider} call was not made")

    try:
        parts = check_url(provider, args.url)
    except _Refused as exc:
        _fail(str(exc))

    host = (parts.hostname or "").lower()
    url = args.url
    headers = {"User-Agent": USER_AGENT}
    credential_names: "tuple[str, ...]" = ()
    if _gets_credential(provider, host):
        if provider == "pixabay":
            url = _with_pixabay_key(parts, key)
        else:
            cred = _credential_headers(provider, key)
            headers.update(cred)
            credential_names = tuple(cred)
    if body is not None:
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=args.method)
    opener = urllib.request.build_opener(
        _CheckedRedirects(provider, credential_names),
        urllib.request.HTTPSHandler(context=ssl_context()),
    )

    record = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "provider": provider,
        "method": args.method,
        "host": host,
        "path": parts.path,
        "status": 0,
        "bytes": 0,
    }

    def finish(status: int, nbytes: int, aborted: Optional[str] = None) -> None:
        record["status"], record["bytes"] = status, nbytes
        if aborted:
            record["aborted"] = aborted
        try:
            log_call(project, record)
        except OSError as exc:
            message = _redact(f"provider request was sent but calls.jsonl could not be written: {exc}", key)
            print(message, file=sys.stderr)
            emit({"error": message, "request_sent": True, "status": status, "bytes": nbytes}, EXIT_FAILED)

    out_path: Optional[Path] = Path(args.out) if args.out else None
    deadline = time.monotonic() + args.timeout
    try:
        with opener.open(request, timeout=min(TIMEOUT_S, args.timeout)) as resp:
            status = resp.status
            total = 0
            head = b""
            sink = None
            tmp_path: Optional[Path] = None
            try:
                declared = resp.headers.get("Content-Length", "")
                if declared.isdigit() and int(declared) > args.max_bytes:
                    raise _Aborted(f"response declares {declared} bytes, over --max-bytes {args.max_bytes}",
                                   status, 0)
                if out_path is not None:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    fd, tmp_name = tempfile.mkstemp(dir=str(out_path.parent), prefix=f".{out_path.name}.",
                                                    suffix=".part")
                    tmp_path = Path(tmp_name)
                    sink = os.fdopen(fd, "wb")
                while True:
                    try:
                        chunk = resp.read1(CHUNK)
                    except (socket.timeout, TimeoutError):
                        raise _Aborted("timed out waiting for the response body", status, total)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > args.max_bytes:
                        raise _Aborted(f"response body exceeded --max-bytes {args.max_bytes}", status, total)
                    if sink is not None:
                        sink.write(chunk)
                    elif len(head) < PREVIEW_CHARS * 4:
                        head += chunk
                    if time.monotonic() > deadline:
                        raise _Aborted(f"response body exceeded --timeout {args.timeout:g}s", status, total)
                if sink is not None:
                    sink.close()
                    sink = None
                    os.replace(tmp_path, out_path)
                    tmp_path = None
            finally:
                if sink is not None:
                    sink.close()
                if tmp_path is not None:
                    tmp_path.unlink(missing_ok=True)
    except _Aborted as exc:
        finish(exc.status, exc.nbytes, exc.reason)
        _fail(f"{provider} response aborted: {exc.reason}", key, status=exc.status, out=None,
              bytes=exc.nbytes, aborted=exc.reason)
    except urllib.error.HTTPError as exc:
        data, timed_out = _read_error_body(exc, deadline)
        reason = f"error body exceeded --timeout {args.timeout:g}s" if timed_out else None
        finish(exc.code, len(data), reason)
        extra = {"aborted": reason} if reason else {}
        _fail(f"HTTP {exc.code} from {provider}", key, status=exc.code, out=None,
              bytes=len(data), preview=_preview(data, key), **extra)
    except _Refused as exc:
        finish(exc.status, 0)
        _fail(str(exc), key)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        finish(0, 0)
        _fail(f"{provider} request failed: {getattr(exc, 'reason', exc)}", key)

    finish(status, total)
    if out_path is not None:
        emit({"status": status, "out": str(out_path), "bytes": total})
    emit({"status": status, "out": None, "bytes": total, "preview": _preview(head, key)})


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="cloud.py", description="Allowlisted, logged cloud API calls.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    call = sub.add_parser("call", help="make one request to a provider")
    call.add_argument("--project", required=True, help="project directory holding brief.json")
    call.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    call.add_argument("--method", required=True, choices=["GET", "POST"])
    call.add_argument("--url", required=True)
    call.add_argument("--json", help="request body: a JSON file path or inline JSON")
    call.add_argument("--out", help="write the response body here instead of previewing it")
    call.add_argument("--max-bytes", type=_positive_int, default=DEFAULT_MAX_BYTES,
                      help="abort when the response body exceeds this many bytes (default 2 GiB)")
    call.add_argument("--timeout", type=_positive_float, default=DEFAULT_TOTAL_TIMEOUT_S,
                      help="abort when the whole call takes longer than this many seconds (default 300)")
    call.set_defaults(func=_cmd_call)
    return parser


def main(argv: Optional["list[str]"] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
