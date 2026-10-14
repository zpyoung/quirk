"""Template manifests (``template.json``), library registries (``libraries.json``) and
``verified.json`` validation.

``validate_template`` returns every problem as a string so an author sees them all at once;
``load_template`` raises them together as one ``ManifestError``. Custom templates (project and
user level) must also pass the ``verified.json`` hash check, reported with the word
``unverified`` so callers can tell a stale template from a broken one.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import SKILL_DIR
from .tokens import validate_tokens

NAME_RE = re.compile(r"^[a-z0-9-]{1,40}\Z")
SLOT_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
REQUIRED_PLACEHOLDERS = ("{{header}}", "{{title}}", "{{head}}", "{{chrome}}", "{{body_end}}")
_SLOT_PLACEHOLDER = re.compile(r"\{\{slot:([^{}]*)\}\}")
_LIB_KINDS = ("js", "css")
_LIB_POSITIONS = ("head", "body-end")
_TIER2_UNHASHED = ("node_modules", "dist")
_SOURCE_HEADER = re.compile(r"^<!-- quirk-src (\{.*\}) -->[ \t]*$")


class ManifestError(Exception):
    """A manifest is invalid; ``errors`` holds every problem found."""

    def __init__(self, message: str, errors: Optional[list[str]] = None) -> None:
        super().__init__(message)
        self.errors = errors if errors is not None else [message]


@dataclass
class Template:
    """A parsed ``template.json`` plus the directory it came from.

    ``level`` is filled in by ``resolve`` (project, user or builtin) and is empty otherwise.
    """

    schema: int
    name: str
    description: str
    tier: int
    dir: Path
    libraries: list[str] = field(default_factory=list)
    optional_libraries: list[str] = field(default_factory=list)
    slots: dict[str, dict] = field(default_factory=dict)
    skeleton: Optional[str] = None
    tokens: Optional[str] = None
    rules: Optional[str] = None
    example: Optional[str] = None
    project: Optional[str] = None
    level: str = ""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_path(base: Path, rel: str) -> Optional[Path]:
    """Resolve ``rel`` under ``base``, or None when it is absolute or climbs out of it."""
    if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")):
        return None
    candidate = (base / rel).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def _read_json(path: Path) -> tuple[Optional[Any], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path.name} is missing"
    except (OSError, ValueError) as exc:
        return None, f"{path.name} is not valid JSON: {exc}"


def load_libraries(path: Path) -> dict:
    """Read and validate a ``libraries.json``; raises ManifestError listing every problem."""
    path = Path(path)
    data, err = _read_json(path)
    if err:
        raise ManifestError(f"{path}: {err}")
    errors = _library_problems(data)
    if errors:
        raise ManifestError(f"{path}: " + "; ".join(errors), errors)
    return data


def _library_problems(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["libraries.json must be a JSON object"]
    errors: list[str] = []
    if data.get("schema") != 1 or isinstance(data.get("schema"), bool):
        errors.append(f"schema must be 1, got {data.get('schema')!r}")
    libs = data.get("libraries")
    if not isinstance(libs, dict):
        return errors + ["libraries must be an object"]
    for name, entry in libs.items():
        if not isinstance(entry, dict):
            errors.append(f"library {name!r} must be an object")
            continue
        versions = entry.get("versions")
        if not isinstance(versions, dict) or not versions:
            errors.append(f"library {name!r} needs a non-empty versions object")
            versions = {}
        current = entry.get("current")
        if not isinstance(current, str) or current not in versions:
            errors.append(f"library {name!r} current {current!r} is not one of its versions")
        for ver, vinfo in versions.items():
            tag = f"{name}@{ver}"
            if not isinstance(vinfo, dict):
                errors.append(f"{tag} must be an object")
                continue
            for key in ("package", "license", "license_file"):
                if not isinstance(vinfo.get(key), str) or not vinfo.get(key):
                    errors.append(f"{tag} needs a string {key}")
            if "first_party" in vinfo and not isinstance(vinfo["first_party"], bool):
                errors.append(f"{tag} first_party must be true or false")
            files = vinfo.get("files")
            if not isinstance(files, list) or not files:
                errors.append(f"{tag} needs a non-empty files list")
                continue
            for i, f in enumerate(files):
                if not isinstance(f, dict):
                    errors.append(f"{tag} files[{i}] must be an object")
                    continue
                if not isinstance(f.get("path"), str) or not f.get("path"):
                    errors.append(f"{tag} files[{i}] needs a path")
                if f.get("kind") not in _LIB_KINDS:
                    errors.append(f"{tag} files[{i}] kind must be js or css")
                if f.get("position") not in _LIB_POSITIONS:
                    errors.append(f"{tag} files[{i}] position must be head or body-end")
                if not isinstance(f.get("inline"), bool):
                    errors.append(f"{tag} files[{i}] inline must be true or false")
                if not re.fullmatch(r"[0-9a-f]{64}", str(f.get("sha256", ""))):
                    errors.append(f"{tag} files[{i}] needs a hex sha256")
                if f.get("inline") is True and not re.fullmatch(r"[0-9a-f]{64}", str(f.get("inline_sha256", ""))):
                    errors.append(f"{tag} files[{i}] is inline and needs a hex inline_sha256")
    return errors


def _str_list(meta: dict, key: str, errors: list[str]) -> list[str]:
    value = meta.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f"{key} must be a list of library names")
        return []
    return value


def _manifest_problems(tdir: Path, meta: Any, skill_dir: Path) -> list[str]:
    if not isinstance(meta, dict):
        return ["template.json must be a JSON object"]
    errors: list[str] = []
    if meta.get("schema") != 1 or isinstance(meta.get("schema"), bool):
        errors.append(f"schema must be 1, got {meta.get('schema')!r}")
    name = meta.get("name")
    if name != tdir.name:
        errors.append(f"name {name!r} must equal the template directory name {tdir.name!r}")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append(f"name {name!r} must match [a-z0-9-]{{1,40}}")
    desc = meta.get("description")
    if not isinstance(desc, str) or not 30 <= len(desc) <= 400:
        errors.append("description must be a string of 30 to 400 characters")
    elif not desc.startswith("Use when"):
        errors.append('description must start with "Use when"')
    tier = meta.get("tier")
    if tier not in (1, 2) or isinstance(tier, bool):
        errors.append(f"tier must be 1 or 2, got {tier!r}")

    libraries = _str_list(meta, "libraries", errors)
    optional = _str_list(meta, "optional_libraries", errors)

    for key in ("tokens", "rules"):
        if key in meta:
            rel = meta[key]
            path = _safe_path(tdir, rel) if isinstance(rel, str) else None
            if path is None:
                errors.append(f"{key} must be a relative path inside the template")
            elif not path.is_file():
                errors.append(f"{key} file {rel!r} does not exist")
            elif key == "tokens":
                data, err = _read_json(path)
                if err:
                    errors.append(f"tokens {err}")
                else:
                    errors.extend(f"tokens: {e}" for e in validate_tokens(data))

    if tier == 1:
        errors.extend(_tier1_problems(tdir, meta))
    elif tier == 2:
        errors.extend(_tier2_problems(tdir, meta))

    errors.extend(_library_resolution_problems(tdir, skill_dir, libraries + optional))
    return errors


def _symlink_problems(tdir: Path, rel: str, *, skip: tuple[str, ...] = ()) -> list[str]:
    """One error per symlink at or under the template-relative directory ``rel``.

    Stamp hashing does not follow links but the app build copies their targets, so a link
    would let built content change without invalidating ``verified.json``.
    """
    root = tdir / rel
    found = [rel.rstrip("/")] if root.is_symlink() else []
    if root.is_dir() and not root.is_symlink():
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for name in (*dirnames, *filenames):
                path = Path(dirpath) / name
                if path.is_symlink():
                    found.append(path.relative_to(tdir).as_posix())
    return [f"{path} is a symlink; templates must not contain symlinks" for path in sorted(found)]


def _tier1_problems(tdir: Path, meta: dict) -> list[str]:
    errors: list[str] = _symlink_problems(tdir, "vendor")
    slots = meta.get("slots")
    declared: list[str] = []
    if not isinstance(slots, dict) or not 1 <= len(slots) <= 3:
        errors.append("slots must be an object with 1 to 3 entries")
    else:
        for slot, info in slots.items():
            if not SLOT_NAME_RE.match(slot):
                errors.append(f"slot name {slot!r} must match [a-z][a-z0-9-]{{0,30}}")
            if not isinstance(info, dict):
                errors.append(f"slot {slot!r} must be an object")
            else:
                if "required" in info and not isinstance(info["required"], bool):
                    errors.append(f"slot {slot!r} required must be true or false")
                if "description" in info and not isinstance(info["description"], str):
                    errors.append(f"slot {slot!r} description must be a string")
            declared.append(slot)

    for key in ("skeleton", "example"):
        rel = meta.get(key)
        if not isinstance(rel, str) or not rel:
            errors.append(f"tier 1 needs {key}")
            continue
        path = _safe_path(tdir, rel)
        if path is None:
            errors.append(f"{key} must be a relative path inside the template")
        elif not path.is_file():
            errors.append(f"{key} file {rel!r} does not exist")
        elif key == "skeleton":
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"skeleton file {rel!r} cannot be read: {exc}")
                continue
            for placeholder in REQUIRED_PLACEHOLDERS:
                if placeholder not in text:
                    errors.append(f"skeleton is missing {placeholder}")
            for slot in declared:
                if "{{slot:%s}}" % slot not in text:
                    errors.append("skeleton is missing {{slot:%s}}" % slot)
            for used in _SLOT_PLACEHOLDER.findall(text):
                if used not in declared:
                    errors.append("skeleton uses {{slot:%s}} which is not a declared slot" % used)
    return errors


def _tier2_problems(tdir: Path, meta: dict) -> list[str]:
    errors: list[str] = []
    rel = meta.get("project", "project/")
    base = _safe_path(tdir, rel) if isinstance(rel, str) else None
    if base is None:
        return ["project must be a relative directory inside the template"]
    errors.extend(_symlink_problems(tdir, rel.rstrip("/"), skip=_TIER2_UNHASHED))
    example = meta.get("example")
    if isinstance(example, str) and example and _safe_path(tdir, example) is not None:
        errors.extend(_symlink_problems(tdir, example.rstrip("/"), skip=_TIER2_UNHASHED))
    for fname in ("package.json", "pnpm-lock.yaml"):
        if not (base / fname).is_file():
            errors.append(f"tier 2 needs {rel.rstrip('/')}/{fname}")
    return errors


def _library_resolution_problems(tdir: Path, skill_dir: Path, names: list[str]) -> list[str]:
    if not names:
        return []
    from .vendor import VendorError, VendorStore

    store = VendorStore([tdir / "vendor" / "libraries.json", skill_dir / "vendor" / "libraries.json"])
    errors = []
    for name in dict.fromkeys(names):
        try:
            store.resolve(name, None)
        except VendorError as exc:
            errors.append(f"library {name!r} cannot be resolved: {exc}")
    return errors


def _tree_paths(tdir: Path, rel: str) -> set[str]:
    """Every file under the template-relative directory ``rel``, minus ``node_modules`` and ``dist``."""
    root = _safe_path(tdir, rel)
    found: set[str] = set()
    if root is None or not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _TIER2_UNHASHED]
        for fname in filenames:
            if fname != ".DS_Store":
                found.add(f"{rel}/{(Path(dirpath) / fname).relative_to(root).as_posix()}")
    return found


def _example_data_path(tdir: Path, example: Any) -> Optional[str]:
    """Template-relative path of the tier-1 example's ``data`` file, or None when it names none."""
    if not isinstance(example, str):
        return None
    path = _safe_path(tdir, example)
    if path is None or not path.is_file():
        return None
    try:
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
    except (OSError, UnicodeDecodeError):
        return None
    match = _SOURCE_HEADER.match(first)
    if not match:
        return None
    try:
        data = json.loads(match.group(1)).get("data")
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, str) or not data:
        return None
    target = _safe_path(tdir, (Path(example).parent / data).as_posix())
    if target is None:
        return None
    return target.relative_to(tdir.resolve()).as_posix()


def verification_paths(tdir: Path, meta: Optional[dict] = None) -> list[str]:
    """Relative paths that ``verified.json`` must hash for this template, sorted.

    Tier 1 covers the manifest, skeleton, tokens, rules, example, the example's ``data`` file
    when its header names one, and every file under ``vendor/``. Tier 2 covers the manifest,
    every file under ``project/`` and every file under ``example/`` (``node_modules`` and ``dist``
    excluded from both), so a ``.pnpmfile.cjs``, ``vite.config.ts`` or an example overlay that
    replaces either cannot ride along under a stamp.
    """
    tdir = Path(tdir)
    if meta is None:
        loaded, _ = _read_json(tdir / "template.json")
        meta = loaded if isinstance(loaded, dict) else {}
    paths = {"template.json"}
    if meta.get("tier") == 2:
        base = str(meta.get("project", "project/")).rstrip("/")
        paths.update({f"{base}/package.json", f"{base}/pnpm-lock.yaml"})
        paths.update(_tree_paths(tdir, base))
        example = meta.get("example")
        if isinstance(example, str) and example:
            paths.update(_tree_paths(tdir, example.rstrip("/")))
    else:
        for key in ("skeleton", "tokens", "rules", "example"):
            if isinstance(meta.get(key), str):
                paths.add(meta[key])
        data = _example_data_path(tdir, meta.get("example"))
        if data:
            paths.add(data)
        vdir = tdir / "vendor"
        if vdir.is_dir():
            paths.update(p.relative_to(tdir).as_posix() for p in vdir.rglob("*") if p.is_file())
    return sorted(paths)


def compute_hashes(tdir: Path) -> dict[str, str]:
    """SHA-256 of every verification path that exists, keyed by relative POSIX path."""
    tdir = Path(tdir)
    out = {}
    for rel in verification_paths(tdir):
        path = _safe_path(tdir, rel)
        if path is not None and path.is_file():
            out[rel] = _sha256_file(path)
    return out


def _verified_problems(tdir: Path, meta: Optional[dict]) -> list[str]:
    data, err = _read_json(tdir / "verified.json")
    if err:
        return [f"unverified: {err}"]
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("hashes"), dict):
        return ["unverified: verified.json needs schema 1 and a hashes object"]
    hashes = data["hashes"]
    errors = []
    for rel in verification_paths(tdir, meta):
        path = _safe_path(tdir, rel)
        if rel not in hashes:
            errors.append(f"unverified: {rel} is not covered by verified.json")
        elif path is None or not path.is_file():
            errors.append(f"unverified: {rel} is missing")
        else:
            try:
                changed = _sha256_file(path) != hashes[rel]
            except OSError as exc:
                errors.append(f"unverified: {rel} cannot be read: {exc}")
                continue
            if changed:
                errors.append(f"unverified: {rel} changed since it was verified")
    return errors


def validate_template(tdir: Path, *, require_verified: bool, skill_dir: Optional[Path] = None) -> list[str]:
    """Return every problem with the template at ``tdir``; an empty list means valid.

    ``skill_dir`` locates the built-in ``vendor/libraries.json`` that library names fall back
    to; it defaults to the skill this module ships in. With ``require_verified`` the
    ``verified.json`` hashes must also match, and those errors contain ``unverified``.
    """
    tdir = Path(tdir)
    skill = Path(skill_dir) if skill_dir is not None else SKILL_DIR
    meta, err = _read_json(tdir / "template.json")
    if err:
        return [err]
    errors = _manifest_problems(tdir, meta, skill)
    if require_verified:
        errors.extend(_verified_problems(tdir, meta if isinstance(meta, dict) else None))
    return errors


def load_template(tdir: Path, *, skill_dir: Optional[Path] = None) -> Template:
    """Parse ``template.json`` into a Template; raises ManifestError listing every problem."""
    tdir = Path(tdir)
    errors = validate_template(tdir, require_verified=False, skill_dir=skill_dir)
    if errors:
        raise ManifestError(f"{tdir}: " + "; ".join(errors), errors)
    meta = json.loads((tdir / "template.json").read_text(encoding="utf-8"))
    return Template(
        schema=meta["schema"],
        name=meta["name"],
        description=meta["description"],
        tier=meta["tier"],
        dir=tdir,
        libraries=list(meta.get("libraries", [])),
        optional_libraries=list(meta.get("optional_libraries", [])),
        slots=dict(meta.get("slots", {})),
        skeleton=meta.get("skeleton"),
        tokens=meta.get("tokens"),
        rules=meta.get("rules"),
        example=meta.get("example"),
        project=meta.get("project"),
    )
