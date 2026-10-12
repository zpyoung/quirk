#!/usr/bin/env python3
"""Effect detection for the using-apps-like-a-user guard: PNG hashing, tree normalization,
signal diffing, effect classification, and the settle loop.

Stdlib only. SCREEN_HASH_THRESHOLD is provisional; fixture calibration sets the final value.
"""
from __future__ import annotations

import re
import struct
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

SCREEN_HASH_THRESHOLD = 6
SETTLE_POLL_S = 0.25
SETTLE_CAP_S = 2.0
SIGNALS = ("url", "title", "tree", "focus", "value", "screen")

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(raw: bytes, height: int, stride: int, bpp: int) -> List[bytearray]:
    rows: List[bytearray] = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        ftype = raw[pos]
        cur = bytearray(raw[pos + 1:pos + 1 + stride])
        if len(cur) != stride:
            raise ValueError("truncated PNG image data")
        pos += 1 + stride
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(bpp, stride):
                cur[i] = (cur[i] + cur[i - bpp]) & 255
        elif ftype == 2:
            for i in range(stride):
                cur[i] = (cur[i] + prev[i]) & 255
        elif ftype == 3:
            for i in range(stride):
                left = cur[i - bpp] if i >= bpp else 0
                cur[i] = (cur[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(stride):
                left = cur[i - bpp] if i >= bpp else 0
                upleft = prev[i - bpp] if i >= bpp else 0
                cur[i] = (cur[i] + _paeth(left, prev[i], upleft)) & 255
        else:
            raise ValueError("unknown PNG filter type %d" % ftype)
        rows.append(cur)
        prev = cur
    return rows


def decode_png(data: bytes) -> Tuple[int, int, List[bytes]]:
    """Decode an 8-bit, non-interlaced PNG into (width, height, RGB rows).

    Each row is `width * 3` bytes. Gray, gray+alpha, RGB, RGBA, and palette images are
    accepted; alpha is dropped. Raises ValueError for interlaced, 16-bit, sub-byte-depth, or
    malformed input.
    """
    if data[:8] != _PNG_MAGIC:
        raise ValueError("not a PNG file")
    pos = 8
    header = None
    palette: List[Tuple[int, int, int]] = []
    idat = []
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body) - 2, 3)]
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if header is None:
        raise ValueError("PNG has no IHDR chunk")
    width, height, depth, ctype, _, _, interlace = header
    if interlace:
        raise ValueError("interlaced PNG is not supported")
    if depth == 16:
        raise ValueError("16-bit PNG is not supported")
    if depth != 8:
        raise ValueError("only 8-bit PNG is supported, got %d-bit" % depth)
    if ctype not in _CHANNELS:
        raise ValueError("unknown PNG color type %d" % ctype)
    if ctype == 3 and not palette:
        raise ValueError("palette PNG has no PLTE chunk")
    bpp = _CHANNELS[ctype]
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        raise ValueError("corrupt PNG image data: %s" % exc)
    rows = _unfilter(raw, height, width * bpp, bpp)
    out: List[bytes] = []
    for row in rows:
        rgb = bytearray()
        for x in range(width):
            px = row[x * bpp:(x + 1) * bpp]
            if ctype in (0, 4):
                rgb += bytes((px[0], px[0], px[0]))
            elif ctype in (2, 6):
                rgb += bytes(px[:3])
            else:
                if px[0] >= len(palette):
                    raise ValueError("palette index out of range")
                rgb += bytes(palette[px[0]])
        out.append(bytes(rgb))
    return width, height, out


def average_hash(path: Path) -> int:
    """64-bit average hash of the PNG at `path`.

    The image is box-downsampled to an 8x8 luma grid; each cell above the grid mean sets one
    bit, first cell in the most significant bit. Images under 8 pixels wide or tall reuse the
    nearest source pixel for the cells they cannot fill.
    """
    width, height, rows = decode_png(Path(path).read_bytes())
    if width == 0 or height == 0:
        raise ValueError("empty image")
    luma = [
        [0.299 * r[x * 3] + 0.587 * r[x * 3 + 1] + 0.114 * r[x * 3 + 2] for x in range(width)]
        for r in rows
    ]
    cells: List[float] = []
    for gy in range(8):
        y0 = gy * height // 8
        y1 = max((gy + 1) * height // 8, y0 + 1)
        for gx in range(8):
            x0 = gx * width // 8
            x1 = max((gx + 1) * width // 8, x0 + 1)
            total = 0.0
            for y in range(y0, y1):
                total += sum(luma[y][x0:x1])
            cells.append(total / ((y1 - y0) * (x1 - x0)))
    mean = sum(cells) / 64.0
    bits = 0
    for value in cells:
        bits = (bits << 1) | (1 if value > mean else 0)
    return bits


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two integers."""
    return bin(a ^ b).count("1")


_REF_RE = re.compile(r"\s*\[ref=[^\]]*\]")
_ACTIVE_RE = re.compile(r"\s*\[active\]")
_INDEX_RE = re.compile(r"^(\s*(?:-\s+)?)(?:\[\d+\]|#\d+)(?:\s+|$)")
_LEAD_RE = re.compile(r"^\s*")


def normalize_tree(text: str) -> str:
    """Strip volatile tokens from an accessibility tree so two reads compare by content.

    Removes `[ref=...]`, `[active]`, and a leading element-index token (`[12]` or `#12`),
    collapses whitespace runs inside each line, and drops blank lines. Indentation, roles,
    labels, and values are kept.
    """
    lines = []
    for line in text.splitlines():
        line = _REF_RE.sub("", line)
        line = _ACTIVE_RE.sub("", line)
        line = _INDEX_RE.sub(r"\1", line)
        indent = _LEAD_RE.match(line).group(0).replace("\t", "  ")
        body = " ".join(line.split())
        if body:
            lines.append(indent + body)
    return "\n".join(lines)


@dataclass
class Signals:
    """One snapshot of the observable signals; `tree` holds normalized tree text."""

    url: Optional[str] = None
    title: Optional[str] = None
    tree: Optional[str] = None
    focus: Optional[str] = None
    value: Optional[str] = None
    screen_hash: Optional[int] = None


def diff(before: Signals, after: Signals, threshold: int = SCREEN_HASH_THRESHOLD) -> List[str]:
    """Names of the signals that differ, in SIGNALS order.

    `screen` counts only when both hashes exist and their Hamming distance exceeds `threshold`.
    """
    changed = [
        name
        for name in ("url", "title", "tree", "focus", "value")
        if getattr(before, name) != getattr(after, name)
    ]
    if (
        before.screen_hash is not None
        and after.screen_hash is not None
        and hamming(before.screen_hash, after.screen_hash) > threshold
    ):
        changed.append("screen")
    return changed


def classify(
    before: Signals, after: Signals, expect: str, settled: bool
) -> Tuple[str, List[str], List[str]]:
    """Classify an action's effect as (status, signals, other_changes).

    `signals` is every changed signal. `UNSETTLED` when the observation never settled;
    otherwise `OBSERVED` when `expect` ("any" or a SIGNALS name) changed, else `NO_EFFECT`.
    `other_changes` is the changed signals other than `expect` (always empty for "any").
    Raises ValueError for an unknown `expect`.
    """
    if expect != "any" and expect not in SIGNALS:
        raise ValueError("unknown expect signal: %r" % (expect,))
    changed = diff(before, after)
    other = [] if expect == "any" else [s for s in changed if s != expect]
    if not settled:
        return "UNSETTLED", changed, other
    hit = bool(changed) if expect == "any" else expect in changed
    return ("OBSERVED" if hit else "NO_EFFECT"), changed, other


def _stable(a: Signals, b: Signals) -> bool:
    return a.url == b.url and a.tree == b.tree and a.focus == b.focus


def settle(
    read: Callable[[], Signals],
    poll_s: float = SETTLE_POLL_S,
    cap_s: float = SETTLE_CAP_S,
    sleep=time.sleep,
    clock=time.monotonic,
) -> Tuple[bool, Signals]:
    """Poll `read` until two consecutive reads agree on url, tree, and focus.

    Returns (True, last) once stable, or (False, last) when `cap_s` elapses first. A single
    read cannot tell a finished change from one in progress, so settling needs a pair.
    """
    start = clock()
    prev = read()
    while clock() - start < cap_s:
        sleep(poll_s)
        cur = read()
        if _stable(prev, cur):
            return True, cur
        prev = cur
    return False, prev
