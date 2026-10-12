"""Shared value types and exceptions for the using-apps-like-a-user guard script.

Every driver adapter and the CLI exchange these. The modules that use them are built and
tested separately, so the field names here are a contract between them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


class DriverError(Exception):
    """A driver reported failure. `code` is a stable, machine-readable identifier."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


class UsageError(Exception):
    """A usage or contract violation the CLI reports with exit 2."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


class RunStateError(Exception):
    """A run-state problem the CLI reports with exit 3, such as an unknown or ended run."""

    def __init__(self, code: str, message: str = "", detail: Optional[dict] = None) -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message
        self.detail = detail or {}


class MissingError(Exception):
    """Missing tools, versions, permissions, or credentials; the CLI reports exit 5."""

    def __init__(self, missing: List[str]) -> None:
        super().__init__(", ".join(missing))
        self.missing = list(missing)


@dataclass
class Action:
    """One UI action. Coordinates are driver points, already divided by the screenshot scale."""

    kind: str
    ref: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    to_ref: Optional[str] = None
    to_x: Optional[float] = None
    to_y: Optional[float] = None
    text: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    direction: Optional[str] = None
    amount: Optional[float] = None


@dataclass
class Observation:
    """What a driver saw: the tree, its references, and the surface metadata around them.

    `names` maps each ref to its accessible name, which is the gate subject. `values` maps a ref
    to its current value where the driver exposes one. `sheet_open` is the driver's own verdict
    that a sheet or dialog is open in the window, so callers never parse a driver's tree format.
    """

    tree_text: str
    refs: List[str] = field(default_factory=list)
    names: Dict[str, str] = field(default_factory=dict)
    values: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None
    title: Optional[str] = None
    focus: Optional[str] = None
    screenshot_path: Optional[Path] = None
    scale: Optional[float] = None
    tree_truncated: bool = False
    tree_sparse: bool = False
    window_id: Optional[int] = None
    bundle_id: Optional[str] = None
    raw: str = ""
    sheet_open: bool = False


@dataclass
class DriverResult:
    """What a driver reported for one action; `observation` is its own post-action view, if any."""

    delivered: bool
    driver_verified: Optional[bool] = None
    observation: Optional[Observation] = None
    raw: str = ""
