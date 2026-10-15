"""GitLab adapter: every `glab` invocation and GitLab endpoint shape lives here.

Functions take the caller's command runner (`run`) or JSON API callable (`api_call`)
as their first argument, so a script can pass a late-bound reference to its own
module-level runner and tests that replace that runner keep intercepting every call.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from urllib.parse import quote, urlencode

from forge import ForgeError, positive_int, valid_sha
from forge import change_label as _change_label

NAME = "gitlab"


def default_run(cmd, input_text=None, timeout=120, env=None):
    """Run a command, mapping launch failures to a non-zero CompletedProcess."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, input=input_text,
                              timeout=timeout, shell=False, env=env)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def change_label(number):
    return _change_label(NAME, number)


def mr_path(project, iid):
    return "projects/%s/merge_requests/%s" % (quote(project, safe=""), iid)


def api(run, host, method, endpoint, payload=None, timeout=120):
    """Call the GitLab REST API through `glab api`; return parsed JSON or {}."""
    cmd = ["glab", "api", "--hostname", host, "--method", method, endpoint]
    input_text = None
    if payload is not None:
        cmd += ["--input", "-"]
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
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=120)
    if result.returncode:
        raise ForgeError(result.stderr.strip() or "GitLab discussion request failed")
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise ForgeError("GitLab discussion response was not JSON") from exc


# --------------------------------------------------------------------------- #
# Change reads used by prepare_diff (return None on failure, never raise)
# --------------------------------------------------------------------------- #

def fetch_changes(run, host, project, iid):
    """Return (changes_payload, None) or (None, error_message)."""
    try:
        r = run(["glab", "api", "--hostname", host,
                 "projects/%s/merge_requests/%s/changes" % (quote(project, safe=""), iid)])
        if r.returncode != 0 or not r.stdout.strip():
            return None, "GitLab changes request failed"
        return json.loads(r.stdout), None
    except Exception:
        return None, "GitLab changes response was unavailable or invalid"


def mr_details(run, host, project, iid):
    """Return the MR identity needed for seat detection and reviewer delivery."""
    if not iid or not project:
        return None
    try:
        r = run(["glab", "api", "--hostname", host,
                 "projects/%s/merge_requests/%s" % (quote(project, safe=""), iid)])
        if r.returncode != 0 or not r.stdout.strip():
            return None
        data = json.loads(r.stdout)
    except Exception:
        return None
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
    }


def current_user(run, host):
    """Return the authenticated identity as {id, username}, or None."""
    try:
        r = run(["glab", "api", "--hostname", host, "user"], timeout=30)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        data = json.loads(r.stdout)
        if not isinstance(data, dict) or not data.get("id") or not data.get("username"):
            return None
        return {"id": data["id"], "username": data["username"]}
    except Exception:
        return None


def find_mr_for_branch(run, branch, project, host=None):
    cmd = ["glab", "mr", "list"]
    if host:
        cmd += ["--hostname", host]
    cmd += ["--source-branch", branch, "-F", "json"]
    if project:
        repository = "https://%s/%s" % (host, project) if host else project
        cmd += ["-R", repository]  # full URL pins self-managed host outside a checkout
    try:
        r = run(cmd, timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        arr = json.loads(r.stdout)
        if isinstance(arr, list) and arr:
            return arr[0].get("iid")
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- #
# Source borrowing
# --------------------------------------------------------------------------- #

def clone_command(host, project, repo):
    """Return (argv, env) for a shallow, blob-less, no-checkout clone of `project`."""
    env = os.environ.copy()
    env["GITLAB_HOST"] = host
    cmd = ["glab", "repo", "clone", project, repo, "--", "--no-checkout",
           "--depth=1", "--filter=blob:none"]
    return cmd, env


def head_refspec(iid):
    return "refs/merge-requests/%s/head" % iid


# --------------------------------------------------------------------------- #
# Reviewer delivery (raise ForgeError on any failure)
# --------------------------------------------------------------------------- #

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


def draft_summary(item):
    position = item.get("position") if isinstance(item.get("position"), dict) else {}
    path = position.get("new_path") or position.get("old_path")
    line = position.get("new_line") or position.get("old_line")
    note = item.get("note") if isinstance(item.get("note"), str) else ""
    return {"id": item.get("id"), "anchor": "%s:%s" % (path, line) if path else None,
            "note": note.replace("\n", " ")[:120]}


def changed_paths(api_call, host, project, old_head, new_head):
    endpoint = "projects/%s/repository/compare?%s" % (
        quote(project, safe=""), urlencode({"from": old_head, "to": new_head, "straight": "true"}))
    data = api_call(host, "GET", endpoint)
    diffs = data.get("diffs") if isinstance(data, dict) else None
    if not isinstance(diffs, list):
        raise ForgeError("GitLab compare response is missing diffs")
    paths = set()
    for item in diffs:
        if not isinstance(item, dict):
            raise ForgeError("GitLab compare response contains a malformed diff")
        for key in ("old_path", "new_path"):
            if isinstance(item.get(key), str) and item[key]:
                paths.add(item[key])
    return paths


def inline_position(refs, old_path, new_path, line):
    return {"position_type": "text", "base_sha": refs["base_sha"],
            "start_sha": refs["start_sha"], "head_sha": refs["head_sha"],
            "old_path": old_path, "new_path": new_path, "new_line": line}


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
        payload = data["data"]["mergeRequestRequestChanges"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise ForgeError("request-changes mutation returned an invalid response")
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


def discussion_resolved(discussion):
    notes = discussion.get("notes") if isinstance(discussion.get("notes"), list) else []
    root = notes[0] if notes and isinstance(notes[0], dict) else {}
    return bool(discussion.get("resolved") or root.get("resolved"))


def note_url(host, project, iid, note_id):
    return "https://%s/%s/-/merge_requests/%s#note_%s" % (host, project, iid, note_id)


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
    """GitLab bound to one host/project, with an injectable command runner."""

    name = NAME

    def __init__(self, host, project, run=None):
        self.host = host
        self.project = project
        self._run = run or default_run

    def _api_call(self, host, method, endpoint, payload=None, timeout=120):
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
        details = mr_details(self._run, self.host, self.project, number)
        if details is None:
            return None
        details["number"] = details.pop("iid")
        details["open"] = details.get("state") == "opened"
        return details

    def current_user(self):
        return current_user(self._run, self.host)

    def find_change_for_branch(self, branch):
        return find_mr_for_branch(self._run, branch, self.project, self.host)

    def head_refspec(self, number):
        return head_refspec(number)

    def clone_command(self, dest):
        return clone_command(self.host, self.project, dest)

    def list_threads(self, number, api_call=None):
        return fetch_discussions(api_call or self._api_call, self.host, self.project, number)
