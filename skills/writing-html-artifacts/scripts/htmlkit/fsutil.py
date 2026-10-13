"""Filesystem helpers: atomic writes and self-ignoring output directories."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_DEFAULT_MODE = 0o644


def atomic_write(path: Path, data: str | bytes) -> None:
    """Write ``data`` to ``path`` so readers see the old file or the new one, never a partial write.

    The temp file lives in the target's directory so ``os.replace`` stays on one filesystem.
    Text is written as UTF-8 with no newline translation. The parent directory must exist.
    """
    payload = data.encode("utf-8") if isinstance(data, str) else data
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError(f"atomic_write needs str or bytes, got {type(data).__name__}")
    path = Path(path)
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        mode = _DEFAULT_MODE
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def ensure_self_ignoring(dir: Path) -> None:
    """Create ``dir`` (and parents) and give it a ``.gitignore`` of ``*`` unless one exists.

    Output directories such as ``.quirk/html/`` call this before every write so generated
    files never show up in ``git status``. An existing ``.gitignore`` is left untouched.
    """
    dir = Path(dir)
    dir.mkdir(parents=True, exist_ok=True)
    ignore = dir / ".gitignore"
    if not ignore.exists():
        atomic_write(ignore, "*\n")
