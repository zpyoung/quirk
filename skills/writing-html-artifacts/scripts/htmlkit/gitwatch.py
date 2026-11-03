"""Read-only git facts for an SDD run: a hardened runner, one-poll observation, diffs, a poller.

Task worktrees hold code written by unsandboxed workers, so nothing here trusts them. Every git
call goes through ``git()``, which disables hooks, fsmonitor and external diff drivers and never
uses a shell. A worktree is read only when the repo itself lists it. This module takes plain
dicts (RUN.json, report lines, previous git.json) and callbacks; it knows nothing of the run store.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
import threading
import time
from typing import Callable

_PREFIX = [
    "git",
    "--no-optional-locks",
    "-c", "core.fsmonitor=false",
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.untrackedCache=false",
    "-c", "diff.external=",
    "-c", "core.pager=cat",
]
_ENV_SET = {
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
}
_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_EXTERNAL_DIFF", "GIT_PAGER", "GIT_CONFIG_PARAMETERS")
_DIFF_LIKE = {"diff", "log"}

UNTRACKED_FILE_CAP = 256 * 1024
_BINARY_SNIFF = 8 * 1024
_STATUS = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed", "T": "modified", "C": "added"}


class GitError(RuntimeError):
    """A git call failed, timed out or git is missing. ``returncode`` is None unless git exited."""

    def __init__(self, message: str, returncode: int | None = None):
        super().__init__(message)
        self.returncode = returncode


def git(cwd: os.PathLike | str, *args: str, timeout: float = 5.0) -> str:
    """Run one hardened, read-only git command in ``cwd`` and return its stdout as text.

    ``diff`` and ``log`` get ``--no-ext-diff --no-textconv`` inserted after the subcommand, so
    callers cannot forget them. Raises GitError on a non-zero exit, a timeout or a missing git.
    """
    args = tuple(args)
    if args and args[0] in _DIFF_LIKE:
        args = (args[0], "--no-ext-diff", "--no-textconv", *args[1:])
    env = {k: v for k, v in os.environ.items() if k not in _ENV_DROP}
    env.update(_ENV_SET)
    argv = [*_PREFIX, "-C", os.fspath(cwd), *args]
    try:
        proc = subprocess.run(
            argv, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, shell=False
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {' '.join(args[:2])} timed out after {timeout}s") from exc
    except OSError as exc:
        raise GitError(f"git could not run: {exc}") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args[:2])} exited {proc.returncode}: {err}", proc.returncode)
    return proc.stdout.decode("utf-8", "replace")


def listed_worktrees(repo: os.PathLike | str) -> set[str]:
    """Realpaths of every worktree ``repo`` lists, including the main one."""
    out = git(repo, "worktree", "list", "--porcelain")
    return {os.path.realpath(line[len("worktree "):]) for line in out.splitlines() if line.startswith("worktree ")}


def _safe_ref(value: object) -> str:
    if not isinstance(value, str) or not value or value.startswith("-"):
        raise GitError(f"unusable ref {value!r}")
    return value


def _branch_ref(branch: str) -> str:
    return "refs/heads/" + _safe_ref(branch)


def _all_tasks(run: dict, reports: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for t in run.get("tasks") or []:
        seen.setdefault(t["id"], t)
    for r in reports:
        if r.get("kind") == "task-add" and isinstance(r.get("task"), dict):
            seen.setdefault(r["task"]["id"], r["task"])
    return list(seen.values())


def _latest(reports: list[dict], kind: str, task_id: str) -> tuple[int, dict] | None:
    found = None
    for i, r in enumerate(reports):
        if r.get("kind") == kind and r.get("task") == task_id:
            found = (i, r)
    return found


def _task_branch(run: dict, reports: list[dict], task_id: str) -> str:
    disp = _latest(reports, "dispatch", task_id)
    if disp and disp[1].get("branch"):
        return disp[1]["branch"]
    pattern = run.get("branch_pattern") or "sdd/{run}/{task}"
    return pattern.replace("{run}", str(run.get("run_id", ""))).replace("{task}", task_id)


def _listed_worktree(repo: str, reports: list[dict], task_id: str, listed: set[str] | None) -> str | None:
    """The dispatch worktree's realpath when the repo lists it, else None. Runs no command in it."""
    disp = _latest(reports, "dispatch", task_id)
    wt = disp[1].get("worktree") if disp else None
    if not isinstance(wt, str) or not os.path.isabs(wt):
        return None
    if listed is None:
        try:
            listed = listed_worktrees(repo)
        except GitError:
            return None
    real = os.path.realpath(wt)
    return real if real in listed else None


def _is_running(reports: list[dict], task_id: str) -> bool:
    """True while the latest dispatch has no later commit report."""
    disp = _latest(reports, "dispatch", task_id)
    commit = _latest(reports, "commit", task_id)
    return disp is not None and not (commit is not None and commit[0] > disp[0])


def _branch_head(repo: str, branch: str) -> str | None:
    """The branch's sha, or None when the branch does not exist."""
    try:
        return git(repo, "rev-parse", "--verify", "--quiet", _branch_ref(branch) + "^{commit}").strip()
    except GitError as exc:
        if exc.returncode == 1:
            return None
        raise


def _status_entries(worktree: str) -> list[tuple[str, str]]:
    """(XY, path) pairs from ``status --porcelain=v1 -z --untracked-files=all`` in a listed worktree."""
    out = git(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    tokens = out.split("\0")
    entries: list[tuple[str, str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if len(tok) < 4:
            continue
        xy, path = tok[:2], tok[3:]
        if "R" in xy or "C" in xy:
            i += 1  # the original path follows as its own token
        entries.append((xy, path))
    return entries


def _merge_second_parents(repo: str, run: dict) -> set[str]:
    out = git(repo, "log", "--merges", "--format=%H %P", f"{_safe_ref(run['base'])}..{_branch_ref(run['branch'])}")
    heads: set[str] = set()
    for line in out.splitlines():
        parts = line.split()
        heads.update(parts[2:])
    return heads


def _task_facts(run, reports, task, head, listed, merged_heads):
    tid = task["id"]
    repo = run["repo"]
    disp = _latest(reports, "dispatch", tid)
    feature = _branch_ref(run["branch"])
    base = _safe_ref(disp[1]["base"]) if disp and disp[1].get("base") else feature
    commits = int(git(repo, "rev-list", "--count", f"{base}..{head}").strip())
    files: set[str] = set()
    if commits:
        out = git(repo, "diff", "--name-only", "-z", f"{base}..{head}")
        files.update(p for p in out.split("\0") if p)
    worktree = _listed_worktree(repo, reports, tid, listed)
    if worktree and _is_running(reports, tid):
        files.update(path for _xy, path in _status_entries(worktree))
    return {
        "branch_head": head,
        "commits": commits,
        "merged": head in merged_heads,
        "files": sorted(files),
        "worktree_present": worktree is not None,
    }


def observe(run: dict, reports: list[dict], previous: dict | None, now: float) -> dict:
    """Collect one poll of git facts for every task of a run, as the ``git.json`` object.

    A task whose branch does not exist has no entry. A failing call records ``error`` on that
    task and keeps its previous facts. ``changed_at`` stays at the previous value while every
    task's facts are unchanged, so a caller can skip the write and the revision bump.
    """
    repo = run["repo"]
    try:
        listed: set[str] | None = listed_worktrees(repo)
    except GitError:
        listed = set()
    merged_heads: set[str] | None
    merge_error: GitError | None = None
    try:
        merged_heads = _merge_second_parents(repo, run)
    except GitError as exc:
        merged_heads, merge_error = None, exc

    prev_tasks = (previous or {}).get("tasks") or {}
    tasks: dict[str, dict] = {}
    for task in _all_tasks(run, reports):
        tid = task["id"]
        try:
            head = _branch_head(repo, _task_branch(run, reports, tid))
            if head is None:
                continue
            if merged_heads is None:
                raise merge_error  # type: ignore[misc]
            tasks[tid] = _task_facts(run, reports, task, head, listed, merged_heads)
        except (GitError, ValueError, KeyError) as exc:
            kept = dict(prev_tasks.get(tid) or {
                "commits": 0, "merged": False, "files": [], "worktree_present": False,
            })
            kept["error"] = str(exc)
            tasks[tid] = kept

    unchanged = previous is not None and tasks == prev_tasks
    return {
        "observed_at": now,
        "changed_at": previous["changed_at"] if unchanged else now,
        "tasks": tasks,
    }


_DIFF_HEADER = re.compile(r"(?m)^(?=diff --git )")


def _name_status(out: str) -> list[tuple[str, str]]:
    tokens = out.split("\0")
    result: list[tuple[str, str]] = []
    i = 0
    while i < len(tokens) and tokens[i]:
        code = tokens[i][0]
        if code in "RC":
            result.append((code, tokens[i + 2] if i + 2 < len(tokens) else ""))
            i += 3
        else:
            result.append((code, tokens[i + 1] if i + 1 < len(tokens) else ""))
            i += 2
    return result


def _tracked_files(cwd: str, *range_args: str) -> list[dict]:
    names = _name_status(git(cwd, "diff", "-M", "--name-status", "-z", *range_args))
    chunks = [c for c in _DIFF_HEADER.split(git(cwd, "diff", "-M", *range_args)) if c]
    if len(names) != len(chunks):
        raise GitError("diff listing and patch disagree")
    files = []
    for (code, path), chunk in zip(names, chunks):
        binary = bool(re.search(r"(?m)^(Binary files |GIT binary patch)", chunk))
        files.append({
            "path": path,
            "status": _STATUS.get(code, "modified"),
            "patch": "" if binary else chunk,
            "binary": binary,
        })
    return files


def _read_untracked(root: str, rel: str) -> dict | None:
    """An untracked file as an added-file entry, or None when it is not a plain file inside ``root``."""
    full = os.path.join(root, rel)
    if os.path.realpath(os.path.dirname(full)) != os.path.dirname(os.path.join(os.path.realpath(root), rel)):
        return None
    try:
        fd = os.open(full, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        with os.fdopen(fd, "rb", closefd=False) as fh:
            data = fh.read(UNTRACKED_FILE_CAP)
    except OSError:
        return None
    finally:
        os.close(fd)
    if b"\0" in data[:_BINARY_SNIFF]:
        return {"path": rel, "status": "added", "patch": "", "binary": True}
    text = data.decode("utf-8", "replace")
    lines = text.split("\n")
    trailing_newline = text.endswith("\n")
    if trailing_newline:
        lines.pop()
    body = "".join("+" + ln + "\n" for ln in lines)
    if not trailing_newline and lines:
        body += "\\ No newline at end of file\n"
    patch = (
        f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n--- /dev/null\n+++ b/{rel}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n{body}"
    )
    return {"path": rel, "status": "added", "patch": patch, "binary": False}


def task_diff(run: dict, reports: list[dict], task_id: str, max_bytes: int = 1 << 20) -> dict | None:
    """The Diff object for one task, or None for an unknown task or one with no branch.

    A running task (listed worktree, no later commit report) is diffed in its worktree against
    the task base, plus untracked files read directly. Any other task diffs ``base..head`` in the
    repo. Raises GitError when git itself fails. Once the patch text passes ``max_bytes`` no
    further files are added and ``truncated`` is set.
    """
    if task_id not in {t["id"] for t in _all_tasks(run, reports)}:
        return None
    repo = run["repo"]
    branch = _task_branch(run, reports, task_id)
    head = _branch_head(repo, branch)
    if head is None:
        return None
    disp = _latest(reports, "dispatch", task_id)
    if disp and disp[1].get("base"):
        base = git(repo, "rev-parse", "--verify", _safe_ref(disp[1]["base"]) + "^{commit}").strip()
    else:
        base = git(repo, "merge-base", head, _branch_ref(run["branch"])).strip()

    worktree = _listed_worktree(repo, reports, task_id, None)
    if worktree and _is_running(reports, task_id):
        source, out_head = "worktree", None
        files = _tracked_files(worktree, base)
        have = {f["path"] for f in files}
        for xy, path in _status_entries(worktree):
            if xy == "??" and not path.endswith("/") and path not in have:
                entry = _read_untracked(worktree, path)
                if entry:
                    files.append(entry)
    else:
        source, out_head = "commit", head
        files = _tracked_files(repo, f"{base}..{head}")

    kept: list[dict] = []
    total = 0
    truncated = False
    for f in files:
        kept.append(f)
        total += len(f["patch"].encode("utf-8"))
        if total > max_bytes:
            truncated = True
            break
    return {"task": task_id, "base": base, "head": out_head, "source": source, "files": kept, "truncated": truncated}


class Watcher(threading.Thread):
    """Polls git facts while a run is live and hands changed facts to ``save``.

    ``load()`` returns ``(run, reports, previous facts)``. The watcher polls every ``interval``
    while the run has no run-end, makes one final poll after it, then idles and keeps checking
    ``load()`` so a new run restarts polling. A failing poll is retried next interval.
    """

    def __init__(
        self,
        load: Callable[[], tuple[dict | None, list[dict], dict | None]],
        save: Callable[[dict], None],
        interval: float = 3.0,
    ):
        super().__init__(daemon=True, name="gitwatch")
        self._load = load
        self._save = save
        self._interval = interval
        self._halt = threading.Event()
        self._finalized: str | None = None
        self._last: tuple[str, dict] | None = None

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        while not self._halt.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._halt.wait(self._interval)

    def _tick(self) -> None:
        run, reports, previous = self._load()
        if run is None:
            self._finalized = None
            return
        run_id = str(run.get("run_id"))
        if any(r.get("kind") == "run-end" for r in reports):
            if self._finalized == run_id:
                return
            self._finalized = run_id
        else:
            self._finalized = None
        if previous is None and self._last and self._last[0] == run_id:
            previous = self._last[1]
        facts = observe(run, reports, previous, time.time())
        self._last = (run_id, facts)
        if previous is None or facts["changed_at"] != previous.get("changed_at"):
            self._save(facts)
