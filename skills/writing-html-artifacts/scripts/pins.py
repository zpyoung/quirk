"""Integrity and freshness checks for the vendored front-end libraries.

`verify` is offline: it proves every version listed in `vendor/libraries.json` is
present on disk and byte-identical to the recorded hashes, so a build can trust what it
inlines. `check` is for maintainers: it asks npm and OSV whether the pinned `current`
versions are outdated or carry advisories, and never runs in tests or CI.

`escape_inline` is the single definition of the escaping applied to inlined blocks;
`inline_sha256` in the manifest is the hash of its output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
MANIFEST_NAME = "libraries.json"
REGISTRY_URL = "https://registry.npmjs.org/{package}/latest"
OSV_URL = "https://api.osv.dev/v1/query"

_CLOSERS = {
    "js": (re.compile(r"</script", re.IGNORECASE), "<\\/script"),
    "css": (re.compile(r"</style", re.IGNORECASE), "<\\/style"),
}


def escape_inline(text: str, kind: str) -> str:
    """Return `text` safe to embed in a `<script>` (kind "js") or `<style>` (kind "css") block.

    Every case variant of the matching closing-tag opener becomes its lowercase
    escaped form; the rest of the text is byte-identical. Raises ValueError for any
    other kind.
    """
    try:
        pattern, replacement = _CLOSERS[kind]
    except KeyError:
        raise ValueError("kind must be 'js' or 'css', got %r" % (kind,)) from None
    return pattern.sub(lambda _m: replacement, text)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(vendor_dir: Path) -> Dict[str, Any]:
    return json.loads((vendor_dir / MANIFEST_NAME).read_text(encoding="utf-8"))


def verify(vendor_dir: Path) -> List[str]:
    """Return one message per integrity problem in `vendor_dir`; empty means healthy.

    Every version of every library must have each listed file with matching raw and
    inlined hashes, a license file, and `current` must name a listed version whose
    directory exists. Messages start with the path relative to `vendor_dir`.
    """
    errors: List[str] = []
    try:
        manifest = load_manifest(vendor_dir)
    except (OSError, ValueError) as exc:
        return ["%s: cannot read manifest: %s" % (MANIFEST_NAME, exc)]

    for name, lib in sorted(manifest.get("libraries", {}).items()):
        versions = lib.get("versions", {})
        current = lib.get("current")
        if current not in versions:
            errors.append("%s: current version %r is not a listed version" % (name, current))
        for version, entry in sorted(versions.items()):
            base = vendor_dir / name / version
            if not base.is_dir():
                errors.append("%s/%s: version directory is missing" % (name, version))
                continue
            license_file = entry.get("license_file")
            if not license_file or not (base / license_file).is_file():
                errors.append("%s/%s/%s: license file is missing" % (name, version, license_file))
            for spec in entry.get("files", []):
                errors.extend(_verify_file(name, version, base, spec))
    return errors


def _verify_file(name: str, version: str, base: Path, spec: Dict[str, Any]) -> List[str]:
    label = "%s/%s/%s" % (name, version, spec["path"])
    path = base / spec["path"]
    if not path.is_file():
        return ["%s: file is missing" % label]
    raw = path.read_bytes()
    problems: List[str] = []
    if _sha256(raw) != spec.get("sha256"):
        problems.append("%s: sha256 does not match the manifest" % label)
    escaped = escape_inline(raw.decode("utf-8", errors="replace"), spec["kind"])
    if _sha256(escaped.encode("utf-8")) != spec.get("inline_sha256"):
        problems.append("%s: inline_sha256 does not match the manifest" % label)
    return problems


def _get_json(url: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"} if data else {}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def check(vendor_dir: Path) -> Dict[str, Any]:
    """Compare each library's `current` pin with npm's latest and OSV's advisories.

    Needs network. A library that cannot be queried is reported with an `error` and
    counts against `ok`.
    """
    results: List[Dict[str, Any]] = []
    for name, lib in sorted(load_manifest(vendor_dir)["libraries"].items()):
        current = lib["current"]
        package = lib["versions"][current]["package"]
        row: Dict[str, Any] = {"name": name, "current": current}
        try:
            latest = _get_json(REGISTRY_URL.format(package=package))["version"]
            osv = _get_json(
                OSV_URL,
                {"version": current, "package": {"name": package, "ecosystem": "npm"}},
            )
        except (OSError, ValueError, KeyError) as exc:
            row.update(latest=None, outdated=False, advisories=[], error=str(exc))
        else:
            row.update(
                latest=latest,
                outdated=latest != current,
                advisories=[v["id"] for v in osv.get("vulns", [])],
            )
        results.append(row)
    ok = all(not r["outdated"] and not r["advisories"] and "error" not in r for r in results)
    return {"ok": ok, "libraries": results}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("verify", "check"):
        p = sub.add_parser(command)
        p.add_argument("--vendor-dir", type=Path, default=DEFAULT_VENDOR_DIR)
    args = parser.parse_args(argv)

    if args.command == "verify":
        errors = verify(args.vendor_dir)
        print(json.dumps({"ok": not errors, "errors": errors}))
        return 0 if not errors else 1

    report = check(args.vendor_dir)
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
