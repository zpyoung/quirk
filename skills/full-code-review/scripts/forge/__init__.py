"""Forge-neutral types for the review scripts.

Only the adapters in this package know whether a change lives on GitHub or GitLab.
Everything else works on these shapes and on the `Forge` protocol.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Protocol

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ForgeError(RuntimeError):
    """A forge call or a forge response failed.

    `code` is one of: auth, not_found, conflict, validation, transient, unknown.
    It subclasses RuntimeError so callers that historically caught RuntimeError keep working.
    """

    def __init__(self, message: str, code: str = "unknown"):
        super().__init__(message)
        self.code = code


def positive_int(value, label):
    """Return `value` as a positive int, or raise ForgeError naming `label`."""
    if isinstance(value, bool):
        raise ForgeError("%s must be a positive integer" % label, "validation")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ForgeError("%s must be a positive integer" % label, "validation")
    if number <= 0:
        raise ForgeError("%s must be a positive integer" % label, "validation")
    return number


def valid_sha(value, label):
    """Return `value` if it is a full lowercase SHA, else raise ForgeError naming `label`."""
    if not isinstance(value, str) or not SHA_RE.match(value):
        raise ForgeError("%s must be a full lowercase SHA" % label, "validation")
    return value


@dataclass
class User:
    id: str
    username: str
    emails: List[str] = field(default_factory=list)


@dataclass
class ChangedFile:
    old_path: str
    new_path: str
    status: str
    diff: Optional[str] = None
    too_large: bool = False
    binary: bool = False


@dataclass
class Change:
    number: int
    title: str
    description: str
    web_url: str
    state: str
    author: User
    source_branch: str
    target_branch: str
    refs: Dict[str, Optional[str]]
    files: List[ChangedFile] = field(default_factory=list)
    file_list_complete: bool = True
    is_fork: bool = False
    author_trusted: Optional[bool] = None


@dataclass
class Anchor:
    path: str
    line: int
    side: str = "new"
    old_path: Optional[str] = None
    start_line: Optional[int] = None


@dataclass
class Note:
    id: str
    author: User
    body: str
    url: str


@dataclass
class Thread:
    id: str
    resolved: bool
    path: Optional[str] = None
    line: Optional[int] = None
    notes: List[Note] = field(default_factory=list)


@dataclass
class Receipt:
    thread_id: str
    note_id: str
    url: str
    inline: bool
    head_sha: str


@dataclass
class StagedInline:
    finding_id: str
    fingerprint: Optional[str]
    body: str
    anchor: Anchor


@dataclass
class StagedReply:
    finding_id: str
    fingerprint: Optional[str]
    body: str
    thread_id: str


@dataclass
class PendingItem:
    id: str
    body: str


@dataclass
class StageResult:
    review_id: Optional[str]
    created: List[dict] = field(default_factory=list)
    moved_to_overview: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class Forge(Protocol):
    """What the review scripts need from a code forge."""

    name: Literal["github", "gitlab"]
    host: str
    project: str

    def change_label(self, number: int) -> str: ...
    def current_user(self) -> User: ...
    def get_change(self, number: int) -> Change: ...
    def find_change_for_branch(self, branch: str) -> Optional[int]: ...
    def commit_authors(self, number: int) -> Optional[List[str]]: ...
    def changed_paths_between(self, base: str, head: str) -> List[str]: ...
    def head_refspec(self, number: int) -> str: ...
    def clone(self, dest: str, shallow: bool) -> None: ...
    def list_threads(self, number: int) -> List[Thread]: ...
    def post_inline(self, number: int, body: str, anchor: Anchor, head_sha: str) -> Receipt: ...
    def post_overview(self, number: int, body: str) -> Receipt: ...
    def pending_items(self, number: int) -> List[PendingItem]: ...
    def stage(self, number: int, overview: str, inline: List[StagedInline],
              replies: List[StagedReply], head_sha: str) -> StageResult: ...
    def publish(self, number: int, staged: StageResult) -> None: ...
    def complete(self, number: int, action: str, head_sha: str, body: str) -> None: ...
    def cleanup_commands(self, number: int, staged: StageResult) -> List[str]: ...
