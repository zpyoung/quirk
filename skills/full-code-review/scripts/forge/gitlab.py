"""GitLab adapter: every `glab` invocation and GitLab endpoint shape lives here.

Functions take the caller's command runner (`run`) or JSON API callable (`api_call`)
as their first argument, so a script can pass a late-bound reference to its own
module-level runner and tests that replace that runner keep intercepting every call.

The reviewer-delivery functions (identity through bulk_publish) raise ForgeError on any
failure. fetch_changes never raises: it returns an error message. mr_details, current_user,
commit_authors and find_mr_for_branch raise, and the GitLabForge wrappers map that to None
with the cause in `last_error` for prepare_diff.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from urllib.parse import quote, urlencode

from forge import ForgeError, StrayComment, context_lines, default_run, hunk_lines, positive_int, valid_sha
from forge import change_label as _change_label
from forge import note_url as _note_url

NAME = "gitlab"


def change_label(number):
    return _change_label(NAME, number)


def mr_path(project, iid):
    return "projects/%s/merge_requests/%s" % (quote(project, safe=""), iid)


def api(run, host, method, endpoint, payload=None, timeout=120):
    """Call the GitLab REST API through `glab api`; return parsed JSON or {}."""
    cmd = ["glab", "api", "--hostname", host, "--method", method, endpoint]
    input_text = None
    if payload is not None:
        cmd += ["-H", "Content-Type: application/json", "--input", "-"]
        input_text = json.dumps(payload, separators=(",", ":"))
    result = run(cmd, input_text=input_text, timeout=timeout)
    if result.returncode != 0:
        raise ForgeError("GitLab %s %s failed: %s" %
                         (method, endpoint.split("?", 1)[0],
                          (result.stderr or result.stdout).strip()[:400]))
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ForgeError("GitLab %s %s returned invalid JSON" % (method, endpoint.split("?", 1)[0]))


def get_json(host, endpoint):
    """GET-only JSON read used by review memory; raises RuntimeError-compatible ForgeError."""
    command = ["glab", "api", "--hostname", host, endpoint]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ForgeError("GitLab discussion request failed: %s" % str(exc)[:400]) from exc
    if result.returncode:
        raise ForgeError(result.stderr.strip() or "GitLab discussion request failed")
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise ForgeError("GitLab discussion response was not JSON") from exc


def _failure_detail(result):
    return (result.stderr or result.stdout or "").strip()[:400]


def fetch_changes(run, host, project, iid):
    """Return (changes_payload, None) or (None, error_message); never raises.

    The message ends with a stderr snippet so an auth, host or 404 failure is distinguishable.
    """
    try:
        r = run(["glab", "api", "--hostname", host,
                 "projects/%s/merge_requests/%s/changes" % (quote(project, safe=""), iid)])
        if r.returncode != 0 or not r.stdout.strip():
            return None, "GitLab changes request failed: %s" % (_failure_detail(r) or "empty response")
        return json.loads(r.stdout), None
    except Exception as exc:
        return None, "GitLab changes response was unavailable or invalid: %s" % str(exc)[:400]


def mr_details(run, host, project, iid):
    """Return the MR identity needed for seat detection and reviewer delivery.

    Returns None when `iid` or `project` is missing. Raises ForgeError, carrying a stderr
    snippet, when the request fails or the response is not JSON.
    """
    if not iid or not project:
        return None
    try:
        r = run(["glab", "api", "--hostname", host,
                 "projects/%s/merge_requests/%s" % (quote(project, safe=""), iid)])
    except Exception as exc:
        raise ForgeError("GitLab MR request failed: %s" % str(exc)[:400])
    if r.returncode != 0 or not r.stdout.strip():
        raise ForgeError("GitLab MR request failed: %s" % (_failure_detail(r) or "empty response"))
    try:
        data = json.loads(r.stdout)
    except ValueError:
        raise ForgeError("GitLab MR response was not JSON")
    if not isinstance(data, dict):
        raise ForgeError("GitLab MR response had an unexpected shape")
    author = data.get("author") if isinstance(data.get("author"), dict) else {}
    refs = data.get("diff_refs") if isinstance(data.get("diff_refs"), dict) else {}
    return {
        "iid": data.get("iid") or iid,
        "state": data.get("state"),
        "author_id": author.get("id"),
        "author_username": author.get("username"),
        "source_branch": data.get("source_branch"),
        "target_branch": data.get("target_branch"),
        "sha": data.get("sha") or refs.get("head_sha"),
        "base_sha": refs.get("base_sha"),
        "start_sha": refs.get("start_sha"),
        "web_url": data.get("web_url"),
        "is_fork": (data.get("source_project_id") is None or data.get("target_project_id") is None
                    or data.get("source_project_id") != data.get("target_project_id")),
        "author_trusted": None,
    }


def current_user(run, host):
    """Return the authenticated identity as {id, username, emails}.

    Raises ForgeError, carrying a stderr snippet, when the request fails or the response
    lacks an id or username.
    """
    try:
        r = run(["glab", "api", "--hostname", host, "user"], timeout=30)
    except Exception as exc:
        raise ForgeError("GitLab user request failed: %s" % str(exc)[:400])
    if r.returncode != 0 or not r.stdout.strip():
        raise ForgeError("GitLab user request failed: %s" % (_failure_detail(r) or "empty response"))
    try:
        data = json.loads(r.stdout)
    except ValueError:
        raise ForgeError("GitLab user response was not JSON")
    if not isinstance(data, dict) or not data.get("id") or not data.get("username"):
        raise ForgeError("GitLab user response is missing an id or username")
    emails = [data.get(k) for k in ("email", "commit_email", "public_email") if data.get(k)]
    return {"id": data["id"], "username": data["username"], "emails": emails}


def commit_authors(run, host, project, iid):
    """Return [{username: None, email}] for every commit on the MR.

    GitLab commit records carry author emails, not usernames, so callers match them
    against the viewer's own emails. Raises ForgeError when a page cannot be read or the
    list is longer than 20 pages.
    """
    authors = []
    for page in range(1, 21):
        endpoint = "projects/%s/merge_requests/%s/commits?per_page=100&page=%d" % (
            quote(project, safe=""), iid, page)
        try:
            r = run(["glab", "api", "--hostname", host, endpoint], timeout=60)
        except Exception as exc:
            raise ForgeError("GitLab commit list request failed: %s" % str(exc)[:400])
        if r.returncode != 0:
            raise ForgeError("GitLab commit list request failed: %s" % (_failure_detail(r) or "no output"))
        try:
            data = json.loads(r.stdout or "[]")
        except ValueError:
            raise ForgeError("GitLab commit list response was not JSON")
        if not isinstance(data, list):
            raise ForgeError("GitLab commit list response had an unexpected shape")
        authors.extend({"username": None, "email": c.get("author_email")} for c in data if isinstance(c, dict))
        if len(data) < 100:
            return authors
    raise ForgeError("GitLab commit list exceeded 20 pages, so the author set may be incomplete")


def find_mr_for_branch(run, branch, project, host=None):
    """Return the iid of the MR whose source branch is `branch`, or None when there is none.

    Raises ForgeError when the lookup itself fails, so a failure is not read as "no MR".
    `glab mr list` has no --hostname flag, so a full-URL -R is what pins a self-managed host.
    """
    cmd = ["glab", "mr", "list", "--source-branch", branch, "-F", "json"]
    if project:
        repository = "https://%s/%s" % (host, project) if host else project
        cmd += ["-R", repository]
    try:
        r = run(cmd, timeout=60)
    except Exception as exc:
        raise ForgeError("GitLab MR lookup failed: %s" % str(exc)[:400])
    if r.returncode != 0:
        raise ForgeError("GitLab MR lookup failed: %s" % (_failure_detail(r) or "no output"))
    if not r.stdout.strip():
        return None
    try:
        arr = json.loads(r.stdout)
    except ValueError:
        raise ForgeError("GitLab MR lookup response was not JSON")
    return arr[0].get("iid") if isinstance(arr, list) and arr and isinstance(arr[0], dict) else None


def clone_command(host, project, repo):
    """Return (argv, env) for a shallow, blob-less, no-checkout clone of `project`."""
    env = os.environ.copy()
    env["GITLAB_HOST"] = host
    cmd = ["glab", "repo", "clone", project, repo, "--", "--no-checkout",
           "--depth=1", "--filter=blob:none"]
    return cmd, env


def head_refspec(iid):
    return "refs/merge-requests/%s/head" % iid


def identity(api_call, host):
    data = api_call(host, "GET", "user")
    if not isinstance(data, dict) or not data.get("id") or not data.get("username"):
        raise ForgeError("authenticated GitLab identity has an unexpected shape")
    return {"id": data["id"], "username": data["username"]}


def merge_request(api_call, host, project, iid):
    """Return (raw, refs{base_sha,start_sha,head_sha}, author) for an open MR."""
    data = api_call(host, "GET", mr_path(project, iid))
    if not isinstance(data, dict) or data.get("iid") != iid:
        raise ForgeError("MR metadata has an unexpected shape or iid")
    if data.get("state") != "opened":
        raise ForgeError("MR !%s is not open" % iid)
    refs = data.get("diff_refs")
    if not isinstance(refs, dict):
        raise ForgeError("MR metadata is missing diff_refs")
    normalized = {}
    for key in ("base_sha", "start_sha", "head_sha"):
        normalized[key] = valid_sha(refs.get(key), "diff_refs.%s" % key)
    if data.get("sha") != normalized["head_sha"]:
        raise ForgeError("MR sha does not match diff_refs.head_sha")
    author = data.get("author") if isinstance(data.get("author"), dict) else {}
    return data, normalized, author


def list_drafts(api_call, host, project, iid):
    """Return every draft note of the authenticated user on the MR; raise ForgeError on malformed or incomplete pagination."""
    drafts = []
    seen = set()
    for page in range(1, 101):
        endpoint = "%s/draft_notes?%s" % (mr_path(project, iid), urlencode({"per_page": 100, "page": page}))
        data = api_call(host, "GET", endpoint)
        if not isinstance(data, list):
            raise ForgeError("draft-note page %d is not a JSON list" % page)
        for item in data:
            if not isinstance(item, dict):
                raise ForgeError("draft-note page %d contains a malformed item" % page)
            draft_id = positive_int(item.get("id"), "draft id")
            if draft_id in seen:
                raise ForgeError("draft-note pagination returned duplicate id %s" % draft_id)
            seen.add(draft_id)
            drafts.append(item)
        if len(data) < 100:
            return drafts
    raise ForgeError("draft-note pagination exceeded 100 pages")


def changed_paths(api_call, host, project, old_head, new_head):
    """Return the paths that differ between two heads; raise ForgeError when GitLab's compare may be truncated."""
    endpoint = "projects/%s/repository/compare?%s" % (
        quote(project, safe=""), urlencode({"from": old_head, "to": new_head, "straight": "true"}))
    data = api_call(host, "GET", endpoint)
    diffs = data.get("diffs") if isinstance(data, dict) else None
    if not isinstance(diffs, list):
        raise ForgeError("GitLab compare response is missing diffs")
    if data.get("compare_timeout"):
        raise ForgeError("GitLab compare timed out, so the changed-file set may be incomplete")
    paths = set()
    for item in diffs:
        if not isinstance(item, dict):
            raise ForgeError("GitLab compare response contains a malformed diff")
        for key in ("old_path", "new_path"):
            if isinstance(item.get(key), str) and item[key]:
                paths.add(item[key])
    return paths


def inline_position(refs, old_path, new_path, line, side="new", old_line=None):
    """Build a diff position; side "old" anchors on the removed line via old_line.

    An unchanged line needs both numbers, so pass its `old_line` alongside the new-side `line`.
    """
    position = {"position_type": "text", "base_sha": refs["base_sha"],
                "start_sha": refs["start_sha"], "head_sha": refs["head_sha"],
                "old_path": old_path, "new_path": new_path}
    position["old_line" if side == "old" else "new_line"] = line
    if side != "old" and old_line is not None:
        position["old_line"] = old_line
    return position


def draft_payload(note):
    """Build a draft-note payload from a planned note (overview, inline, or reply)."""
    payload = {"note": note["body"]}
    if note["kind"] == "inline":
        payload["position"] = note["position"]
    elif note["kind"] == "reply":
        payload["in_reply_to_discussion_id"] = note["discussion_id"]
    return payload


def create_draft(api_call, host, project, iid, payload):
    return api_call(host, "POST", "%s/draft_notes" % mr_path(project, iid), payload)


def bulk_publish(api_call, host, project, iid):
    return api_call(host, "POST", "%s/draft_notes/bulk_publish" % mr_path(project, iid), {})


def approve(api_call, host, project, iid, sha):
    return api_call(host, "POST", "%s/approve" % mr_path(project, iid), {"sha": sha})


def request_changes(run, host, project, iid):
    query = ("mutation($projectPath: ID!, $iid: String!) { "
             "mergeRequestRequestChanges(input: {projectPath: $projectPath, iid: $iid}) "
             "{ errors mergeRequest { iid } } }")
    cmd = ["glab", "api", "graphql", "--hostname", host, "-f", "query=" + query,
           "-f", "projectPath=" + project, "-f", "iid=" + str(iid)]
    result = run(cmd, timeout=120)
    if result.returncode != 0:
        raise ForgeError("request-changes mutation failed: %s" % (result.stderr or result.stdout).strip()[:400])
    try:
        data = json.loads(result.stdout)
        payload = (data.get("data") or {}).get("mergeRequestRequestChanges")
    except (json.JSONDecodeError, AttributeError):
        raise ForgeError("request-changes mutation returned an invalid response")
    if not isinstance(payload, dict):
        reasons = [str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in data.get("errors") or []]
        raise ForgeError("request-changes mutation failed: %s" % ("; ".join(reasons) or "empty mutation result"))
    if payload.get("errors"):
        raise ForgeError("request-changes mutation failed: %s" % "; ".join(payload["errors"]))
    return payload


def cleanup_commands(state):
    """User-run DELETE commands for this run's drafts; never executed by the agent."""
    commands = []
    for item in state.get("created", []) + state.get("reconciled", []):
        endpoint = "%s/draft_notes/%s" % (mr_path(state["project"], state["number"]), item["draft_id"])
        commands.append("glab api --hostname %s --method DELETE %s" %
                        (shlex.quote(state["host"]), shlex.quote(endpoint)))
    return commands


def note_url(host, project, iid, note_id):
    return _note_url(NAME, host, project, iid, note_id)


def fetch_discussions(api_call, host, project, iid):
    """Fetch every discussion page using GET, rejecting incomplete pagination.

    `project` must already be normalized; the returned dicts are GitLab discussion
    objects ({id, resolved?, notes: [{id, body, author, position?, ...}]}).
    """
    encoded = quote(project, safe="")
    page, discussions, seen_ids = 1, [], set()
    while page <= 100:
        endpoint = "projects/%s/merge_requests/%s/discussions?per_page=100&page=%d" % (encoded, iid, page)
        body = api_call(host, "GET", endpoint, None)
        if not isinstance(body, list):
            raise ForgeError("discussion page %d was not a JSON list" % page)
        for item in body:
            if not isinstance(item, dict):
                raise ForgeError("discussion page %d contained a non-object" % page)
            identifier = item.get("id")
            if not isinstance(identifier, (str, int)) or isinstance(identifier, bool):
                raise ForgeError("discussion page %d contained an invalid id" % page)
            if (not isinstance(item.get("notes"), list)
                    or any(not isinstance(note, dict) or not isinstance(note.get("body"), str)
                           for note in item["notes"])):
                raise ForgeError("discussion page %d contained invalid notes" % page)
            if identifier in seen_ids:
                raise ForgeError("duplicate discussion id while fetching discussions")
            seen_ids.add(identifier)
        discussions.extend(body)
        # A full page may have a successor; only a short page proves completion.
        if len(body) == 100:
            page += 1
            continue
        break
    if page > 100:
        raise ForgeError("discussion pagination exceeded 100 pages")
    return discussions


class GitLabForge:
    """GitLab bound to one host/project, with an injectable command runner.

    `change_details`, `current_user`, `commit_authors` and `find_change_for_branch` return
    None on failure; `last_error` then holds the cause, and is None after a successful call.
    """

    name = NAME

    def __init__(self, host, project, run=None, api_call=None):
        self.host = host
        self.project = project
        self._run = run or default_run
        self._injected_api = api_call
        self.last_error = None

    def _api_call(self, host, method, endpoint, payload=None, timeout=120):
        if self._injected_api is not None:
            return self._injected_api(host, method, endpoint, payload, timeout)
        return api(self._run, host, method, endpoint, payload, timeout)

    def change_label(self, number):
        return change_label(number)

    def note_url(self, number, note_id):
        return note_url(self.host, self.project, number, note_id)

    def change_records(self, number):
        if not number or not self.project:
            raise ForgeError("MR iid and project are required", "validation")
        data, error = fetch_changes(self._run, self.host, self.project, number)
        if data is None:
            raise ForgeError(error, "unknown")
        if not isinstance(data.get("changes"), list):
            raise ForgeError("GitLab changes response omitted the changes list", "unknown")
        raw_refs = data.get("diff_refs") or {}
        return {
            "number": data.get("iid") or number,
            "title": data.get("title") or "",
            "description": data.get("description") or "",
            "web_url": data.get("web_url") or "",
            "author": (data.get("author") or {}).get("username") or "",
            "source_branch": data.get("source_branch") or "",
            "refs": {"base": raw_refs.get("base_sha"), "start": raw_refs.get("start_sha"),
                     "head": raw_refs.get("head_sha")},
            "records": data["changes"],
            "reported_count": data.get("changes_count"),
            "overflow": data.get("overflow"),
        }

    def change_details(self, number):
        self.last_error = None
        try:
            details = mr_details(self._run, self.host, self.project, number)
        except ForgeError as exc:
            self.last_error = str(exc)
            return None
        if details is None:
            self.last_error = "GitLab MR iid and project are required"
            return None
        details["number"] = details.pop("iid")
        details["open"] = details.get("state") == "opened"
        return details

    def current_user(self):
        self.last_error = None
        try:
            return current_user(self._run, self.host)
        except ForgeError as exc:
            self.last_error = str(exc)
            return None

    def commit_authors(self, number):
        self.last_error = None
        try:
            return commit_authors(self._run, self.host, self.project, number)
        except ForgeError as exc:
            self.last_error = str(exc)
            return None

    def find_change_for_branch(self, branch):
        self.last_error = None
        try:
            return find_mr_for_branch(self._run, branch, self.project, self.host)
        except ForgeError as exc:
            self.last_error = str(exc)
            return None

    def head_refspec(self, number):
        return head_refspec(number)

    def clone_command(self, dest):
        return clone_command(self.host, self.project, dest)

    def list_threads(self, number, api_call=None):
        return fetch_discussions(api_call or self._api_call, self.host, self.project, number)

    def inline_target(self, refs, old_path, new_path, line, diff_text, side="new"):
        """Return a diff position, or None when `line` is not on a diff line of `new_path`."""
        new_lines, old_lines = hunk_lines(diff_text, new_path)
        if line not in (old_lines if side == "old" else new_lines):
            return None
        old_line = context_lines(diff_text, new_path).get(line) if side != "old" else None
        return inline_position(refs, old_path, new_path, line, side, old_line)

    def post_inline(self, number, body, position, head_sha):
        data = self._api_call(self.host, "POST", "%s/discussions" % mr_path(self.project, number),
                              {"body": body, "position": position})
        notes = data.get("notes") if isinstance(data, dict) else None
        note = notes[0] if isinstance(notes, list) and notes else {}
        if note.get("type") != "DiffNote":
            # a stale position silently degrades to a plain comment, so a missing DiffNote is a failure
            raise StrayComment(data.get("id") if isinstance(data, dict) else None, note.get("id"),
                               note_url(self.host, self.project, number, note.get("id")))
        return {"published": True, "discussion_id": data.get("id"), "note_id": note.get("id"),
                "url": note_url(self.host, self.project, number, note.get("id")), "head_sha": head_sha}

    def post_overview(self, number, body):
        data = self._api_call(self.host, "POST", "%s/notes" % mr_path(self.project, number), {"body": body})
        return {"published": True, "note_id": data.get("id"),
                "url": note_url(self.host, self.project, number, data.get("id"))}

    def identity(self):
        return identity(self._api_call, self.host)

    def live_change(self, number):
        return merge_request(self._api_call, self.host, self.project, number)

    def changed_paths(self, old_head, new_head):
        return changed_paths(self._api_call, self.host, self.project, old_head, new_head)

    def pending(self, number, username):
        return list_drafts(self._api_call, self.host, self.project, number)

    def stage_notes(self, number, notes, head_sha, record, username):
        for note in notes:
            data = create_draft(self._api_call, self.host, self.project, number, draft_payload(note))
            record(note, positive_int(data.get("id") if isinstance(data, dict) else None, "created draft id"))

    def live_staged_ids(self, number, username):
        return {positive_int(item.get("id"), "draft id") for item in self.pending(number, username)}

    def publish(self, number, state):
        bulk_publish(self._api_call, self.host, self.project, number)

    def complete(self, number, action, head_sha, body):
        """Record the reviewer's verdict after publication; `body` is unused on GitLab."""
        if action == "approve":
            return approve(self._api_call, self.host, self.project, number, head_sha)
        if action == "request-changes":
            return request_changes(self._run, self.host, self.project, number)
        return {"comment_only": True}

    def cleanup_commands(self, state):
        return cleanup_commands(state)

