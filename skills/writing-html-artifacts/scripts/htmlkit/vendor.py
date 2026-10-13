"""Vendored library lookup, checksum verification and inline-block production.

A ``VendorStore`` is built from an ordered list of ``libraries.json`` paths (a template's own
first, then the skill's). The first file that knows a library name owns it entirely, so a
template entry shadows the built-in one for that template only. Files live beside their
registry at ``<registry dir>/<name>/<version>/``.

Inlined blocks are exactly ``<script data-quirk-lib="name@ver">TEXT</script>`` or the
``<style ...>`` equivalent, where TEXT is the file escaped by ``escape_inline``. The static
checks hash that TEXT, so no padding or newlines may be added around it.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .manifest import ManifestError, load_libraries

_ESCAPES = {
    "js": (re.compile(r"</script", re.IGNORECASE), r"<\/script"),
    "css": (re.compile(r"</style", re.IGNORECASE), r"<\/style"),
}
_TAGS = {"js": "script", "css": "style"}


class VendorError(Exception):
    """A library or version is missing, or a vendored file fails its checksum."""


@dataclass(frozen=True)
class LibraryFile:
    path: str
    kind: str
    sha256: str
    inline_sha256: str
    position: str
    inline: bool


@dataclass(frozen=True)
class LibraryVersion:
    name: str
    version: str
    package: str
    license: str
    license_file: str
    source: str
    files: tuple[LibraryFile, ...]
    root: Path


@dataclass(frozen=True)
class InlineBlock:
    """One ready-to-paste block: ``text`` is the full wrapped element."""

    kind: str
    position: str
    text: str
    label: str


def escape_inline(text: str, kind: str) -> str:
    """Make ``text`` safe to sit inside a ``<script>`` (kind ``js``) or ``<style>`` (``css``).

    Every ``</script`` (or ``</style``), in any letter case, becomes ``<\\/script`` (or
    ``<\\/style``) so the element cannot close early. The vendoring task hashes the result
    as ``inline_sha256``, so this rule must not drift.
    """
    try:
        pattern, replacement = _ESCAPES[kind]
    except KeyError:
        raise ValueError(f"kind must be 'js' or 'css', got {kind!r}") from None
    return pattern.sub(lambda _m: replacement, text)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wrap_block(kind: str, label: str, attribute: str, escaped: str) -> str:
    tag = _TAGS[kind]
    return f'<{tag} {attribute}="{label}">{escaped}</{tag}>'


def shell_block(name: str, path: Path) -> InlineBlock:
    """Wrap a shipped shell file (``chrome.js``, ``companion.js``) as a checkable script block."""
    escaped = escape_inline(Path(path).read_text(encoding="utf-8"), "js")
    return InlineBlock("js", "body-end", wrap_block("js", name, "data-quirk-shell", escaped), name)


class VendorStore:
    """Resolves library names to versions across an ordered list of registries."""

    def __init__(self, paths: Iterable[Path]) -> None:
        self._paths = [Path(p) for p in paths]
        self._loaded: dict[Path, Optional[dict]] = {}

    def _registry(self, path: Path) -> Optional[dict]:
        if path not in self._loaded:
            if not path.is_file():
                self._loaded[path] = None
            else:
                try:
                    self._loaded[path] = load_libraries(path)
                except ManifestError as exc:
                    raise VendorError(str(exc)) from exc
        return self._loaded[path]

    def resolve(self, name: str, version: Optional[str]) -> LibraryVersion:
        """Find ``name`` at ``version`` (None means the registry's ``current``).

        Raises VendorError when the library is unknown, or when the requested version is not
        vendored; the latter message names ``--upgrade`` because that is the only way forward.
        """
        for path in self._paths:
            registry = self._registry(path)
            if registry is None or name not in registry["libraries"]:
                continue
            entry = registry["libraries"][name]
            wanted = version if version is not None else entry["current"]
            vinfo = entry["versions"].get(wanted)
            if vinfo is None:
                raise VendorError(
                    f"{name}@{wanted} is not vendored (available: {', '.join(sorted(entry['versions']))}); "
                    f"rebuild with --upgrade to use {entry['current']}"
                )
            files = tuple(
                LibraryFile(
                    path=f["path"],
                    kind=f["kind"],
                    sha256=f["sha256"],
                    inline_sha256=f.get("inline_sha256", ""),
                    position=f["position"],
                    inline=f["inline"],
                )
                for f in vinfo["files"]
            )
            return LibraryVersion(
                name=name,
                version=wanted,
                package=vinfo["package"],
                license=vinfo["license"],
                license_file=vinfo["license_file"],
                source=vinfo.get("source", ""),
                files=files,
                root=path.parent / name / wanted,
            )
        raise VendorError(f"library {name!r} is not in any libraries.json ({', '.join(str(p) for p in self._paths)})")

    def _file_path(self, lv: LibraryVersion, rel: str) -> Path:
        base = lv.root.resolve()
        path = (lv.root / rel).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            raise VendorError(f"{lv.name}@{lv.version}: {rel!r} escapes the library directory") from None
        return path

    def inline_blocks(self, lv: LibraryVersion) -> list[InlineBlock]:
        """Blocks for every ``inline: true`` file, in registry order, verified before use.

        Raises VendorError when a file is missing, its raw ``sha256`` differs from the
        registry, or the escaped text differs from the recorded ``inline_sha256``.
        """
        label = f"{lv.name}@{lv.version}"
        blocks = []
        for f in lv.files:
            if not f.inline:
                continue
            path = self._file_path(lv, f.path)
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise VendorError(f"{label}/{f.path}: cannot read vendored file: {exc}") from exc
            if hashlib.sha256(raw).hexdigest() != f.sha256:
                raise VendorError(f"{label}/{f.path}: sha256 does not match libraries.json")
            escaped = escape_inline(raw.decode("utf-8"), f.kind)
            if f.inline_sha256 and sha256_text(escaped) != f.inline_sha256:
                raise VendorError(f"{label}/{f.path}: inline_sha256 does not match the escaped file")
            blocks.append(InlineBlock(f.kind, f.position, wrap_block(f.kind, label, "data-quirk-lib", escaped), label))
        return blocks

    def license_comment(self, lv: LibraryVersion) -> str:
        return license_comment(lv)


def license_comment(lv: LibraryVersion) -> str:
    """The ``<!-- license: ... -->`` line that must precede an inlined library.

    Reads the first line mentioning "copyright" from the license file; any ``--`` in it is
    broken up so the comment cannot close early.
    """
    path = lv.root / lv.license_file
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise VendorError(f"{lv.name}@{lv.version}: cannot read license file {lv.license_file}: {exc}") from exc
    copyright_line = next((ln.strip() for ln in lines if "copyright" in ln.lower()), "")
    if not copyright_line:
        copyright_line = next((ln.strip() for ln in lines if ln.strip()), "no copyright line")
    while "--" in copyright_line:
        copyright_line = copyright_line.replace("--", "- -")
    return f"<!-- license: {lv.name} {lv.version} {lv.license} | {copyright_line} -->"
