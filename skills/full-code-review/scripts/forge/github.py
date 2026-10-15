"""GitHub adapter: every `gh` invocation and GitHub endpoint shape lives here.

Like the GitLab adapter, functions and methods take an injectable JSON API callable
(`api_call(host, method, endpoint, payload=None, timeout=120)`) so tests can replace the
transport. Threads are normalized to the GitLab-style discussion dicts the rest of the
skill already reads.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess

from forge import ForgeError, change_label as _change_label, positive_int
from forge import note_url as _note_url

NAME = "github"
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
_MAX_PAGES = 30


def default_run(cmd, input_text=None, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, input=input_text,
                              timeout=timeout, shell=False)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def _error_code(text):
    match = re.search(r"HTTP (\d{3})", text or "")
    status = int(match.group(1)) if match else 0
    return {401: "auth", 403: "auth", 404: "not_found", 409: "conflict",
            422: "validation"}.get(status, "transient" if status >= 500 else "unknown")


def api(run, host, method, endpoint, payload=None, timeout=120):
    """Call the GitHub REST or GraphQL API through `gh api`; return parsed JSON or {}."""
    cmd = ["gh", "api", "--hostname", host, "-X", method, endpoint]
    input_text = None
    if payload is not None:
        cmd += ["--input", "-"]
        input_text = json.dumps(payload, separators=(",", ":"))
    result = run(cmd, input_text=input_text, timeout=timeout)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[:400]
        raise ForgeError("GitHub %s %s failed: %s" % (method, endpoint.split("?", 1)[0], detail),
                         _error_code(detail))
    if not (result.stdout or "").strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ForgeError("GitHub %s %s returned invalid JSON" % (method, endpoint.split("?", 1)[0]))


def graphql(api_call, host, query, variables):
    data = api_call(host, "POST", "graphql", {"query": query, "variables": variables})
    if not isinstance(data, dict) or data.get("errors"):
        messages = "; ".join(str(e.get("message", e)) for e in (data or {}).get("errors") or []) or "no data"
        raise ForgeError("GitHub GraphQL request failed: %s" % messages)
    return data.get("data") or {}


def get_pages(api_call, host, endpoint):
    """GET every page of a list endpoint (per_page=100), rejecting runaway pagination."""
    items = []
    separator = "&" if "?" in endpoint else "?"
    for page in range(1, _MAX_PAGES + 1):
        data = api_call(host, "GET", "%s%sper_page=100&page=%d" % (endpoint, separator, page))
        if not isinstance(data, list):
            raise ForgeError("GitHub page %d of %s is not a JSON list" % (page, endpoint.split("?", 1)[0]))
        items.extend(data)
        if len(data) < 100:
            return items
    raise ForgeError("GitHub pagination of %s exceeded %d pages" % (endpoint.split("?", 1)[0], _MAX_PAGES))


def _digest(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def hunk_lines(diff_text, path):
    """Return ({new-side lines}, {old-side lines}) a review comment may anchor on for `path`."""
    new_lines, old_lines = set(), set()
    current, old_no, new_no, in_file = None, 0, 0, False
    for line in (diff_text or "").splitlines():
        if line.startswith("diff --git "):
            in_file = False
            current = None
            continue
        if line.startswith("+++ "):
            current = line[4:][2:] if line[4:].startswith("b/") else line[4:]
            in_file = current == path
            continue
        if not in_file:
            continue
        match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if match:
            old_no, new_no = int(match.group(1)), int(match.group(2))
            continue
        if not old_no and not new_no:
            continue
        if line.startswith("+"):
            new_lines.add(new_no)
            new_no += 1
        elif line.startswith("-"):
            old_lines.add(old_no)
            old_no += 1
        elif line.startswith(" ") or line == "":
            new_lines.add(new_no)
            old_lines.add(old_no)
            new_no += 1
            old_no += 1
    return new_lines, old_lines


class GitHubForge:
    """GitHub bound to one host and owner/repo, with injectable transport."""

    name = NAME

    def __init__(self, host, project, run=None, api_call=None):
        self.host = host
        self.project = project
        self._run = run or default_run
        self._api_call = api_call or (lambda h, m, e, p=None, timeout=120: api(self._run, h, m, e, p, timeout))

    # -- identity and labels -------------------------------------------------
    def change_label(self, number):
        return _change_label(NAME, number)

    def note_url(self, number, note_id):
        return _note_url(NAME, self.host, self.project, number, note_id)

    def _repo(self, suffix=""):
        return "repos/%s%s" % (self.project, suffix)

    def _pull(self, number, suffix=""):
        return self._repo("/pulls/%s%s" % (number, suffix))

    def current_user(self):
        try:
            data = self._api_call(self.host, "GET", "user")
        except ForgeError:
            return None
        if not isinstance(data, dict) or not data.get("id") or not data.get("login"):
            return None
        return {"id": data["id"], "username": data["login"],
                "emails": [data["email"]] if data.get("email") else []}

    # -- read path -------------------------------------------------------------
    def _merge_base(self, base_sha, head_sha):
        data = self._api_call(self.host, "GET", self._repo("/compare/%s...%s" % (base_sha, head_sha)))
        merge_base = (data.get("merge_base_commit") or {}).get("sha") if isinstance(data, dict) else None
        if not merge_base:
            raise ForgeError("GitHub compare response is missing merge_base_commit")
        return merge_base

    def _pull_data(self, number):
        data = self._api_call(self.host, "GET", self._pull(number))
        if not isinstance(data, dict) or data.get("number") != int(number):
            raise ForgeError("GitHub pull request metadata has an unexpected shape")
        return data

    def change_records(self, number):
        data = self._pull_data(number)
        head_sha = (data.get("head") or {}).get("sha")
        base_sha = self._merge_base((data.get("base") or {}).get("sha"), head_sha)
        records = []
        for item in get_pages(self._api_call, self.host, self._pull(number, "/files")):
            status = item.get("status")
            patch = item.get("patch")
            path = item.get("filename")
            records.append({
                "old_path": item.get("previous_filename") or path,
                "new_path": path,
                "diff": patch or "",
                "new_file": status == "added",
                "deleted_file": status == "removed",
                "renamed_file": status == "renamed",
                "a_mode": None, "b_mode": None,
                # GitHub drops `patch` for large and binary files; local git recovers them
                "too_large": patch is None and status not in ("removed",) and item.get("changes", 1) > 0,
            })
        return {
            "number": data["number"], "title": data.get("title") or "",
            "description": data.get("body") or "", "web_url": data.get("html_url") or "",
            "author": (data.get("user") or {}).get("login") or "",
            "source_branch": (data.get("head") or {}).get("ref") or "",
            "refs": {"base": base_sha, "start": base_sha, "head": head_sha},
            "records": records,
            "reported_count": data.get("changed_files"),
            "overflow": None,
        }

    def change_details(self, number):
        try:
            data = self._pull_data(number)
            head = data.get("head") or {}
            base = data.get("base") or {}
            merge_base = self._merge_base(base.get("sha"), head.get("sha"))
        except ForgeError:
            return None
        head_repo = (head.get("repo") or {}).get("full_name")
        base_repo = (base.get("repo") or {}).get("full_name")
        user = data.get("user") or {}
        return {
            "number": data["number"], "state": data.get("state"),
            "open": data.get("state") == "open" and not data.get("merged"),
            "author_id": user.get("id"), "author_username": user.get("login"),
            "source_branch": head.get("ref"), "target_branch": base.get("ref"),
            "sha": head.get("sha"), "base_sha": merge_base, "start_sha": merge_base,
            "web_url": data.get("html_url"),
            "is_fork": head_repo is None or head_repo != base_repo,
            "author_trusted": data.get("author_association") in TRUSTED_ASSOCIATIONS,
        }

    def commit_authors(self, number):
        try:
            commits = get_pages(self._api_call, self.host, self._pull(number, "/commits"))
        except ForgeError:
            return None
        return [{"username": (c.get("author") or {}).get("login"),
                 "email": ((c.get("commit") or {}).get("author") or {}).get("email")}
                for c in commits if isinstance(c, dict)]

    def find_change_for_branch(self, branch):
        owner = self.project.split("/", 1)[0]
        try:
            data = self._api_call(self.host, "GET", self._repo("/pulls?head=%s:%s&state=open" % (owner, branch)))
        except ForgeError:
            return None
        return data[0].get("number") if isinstance(data, list) and data else None

    def changed_paths(self, old_head, new_head):
        data = self._api_call(self.host, "GET", self._repo("/compare/%s...%s" % (old_head, new_head)))
        files = data.get("files") if isinstance(data, dict) else None
        if not isinstance(files, list):
            raise ForgeError("GitHub compare response is missing files")
        paths = set()
        for item in files:
            for key in ("filename", "previous_filename"):
                if isinstance(item.get(key), str) and item[key]:
                    paths.add(item[key])
        return paths

    def head_refspec(self, number):
        return "refs/pull/%s/head" % number

    def clone_command(self, dest):
        env = os.environ.copy()
        env["GH_HOST"] = self.host
        repo = self.project if self.host == "github.com" else "%s/%s" % (self.host, self.project)
        return ["gh", "repo", "clone", repo, dest, "--", "--no-checkout", "--depth=1",
                "--filter=blob:none"], env

    # -- threads (normalized to discussion dicts) --------------------------------
    _THREADS_QUERY = (
        "query($owner:String!,$name:String!,$number:Int!,$after:String){repository(owner:$owner,name:$name)"
        "{pullRequest(number:$number){reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor}"
        "nodes{id isResolved path line comments(first:100){nodes{databaseId body url "
        "author{login ... on User{databaseId}}}}}}}}}")

    def list_threads(self, number, api_call=None):
        call = api_call or self._api_call
        owner, name = self.project.split("/", 1)
        threads, after = [], None
        for _ in range(_MAX_PAGES):
            data = graphql(call, self.host, self._THREADS_QUERY,
                           {"owner": owner, "name": name, "number": int(number), "after": after})
            page = (((data.get("repository") or {}).get("pullRequest") or {}).get("reviewThreads") or {})
            for node in page.get("nodes") or []:
                position = {"new_path": node.get("path"), "new_line": node.get("line")}
                notes = [{"id": c.get("databaseId"), "body": c.get("body") or "",
                          "author": {"id": (c.get("author") or {}).get("databaseId"),
                                     "username": (c.get("author") or {}).get("login")},
                          "web_url": c.get("url"), "position": position, "resolved": node.get("isResolved")}
                         for c in ((node.get("comments") or {}).get("nodes") or [])]
                threads.append({"id": node.get("id"), "resolved": bool(node.get("isResolved")),
                                "position": position, "notes": notes})
            info = page.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                return threads
            after = info.get("endCursor")
        raise ForgeError("GitHub review-thread pagination exceeded %d pages" % _MAX_PAGES)

    # -- author seat -------------------------------------------------------------
    def inline_target(self, refs, old_path, new_path, line, diff_text, side="new"):
        """Return a review-comment position, or None when GitHub would reject the line."""
        new_lines, old_lines = hunk_lines(diff_text, new_path)
        if side == "old":
            return {"path": new_path, "line": line, "side": "LEFT"} if line in old_lines else None
        return {"path": new_path, "line": line, "side": "RIGHT"} if line in new_lines else None

    def post_inline(self, number, body, position, head_sha):
        payload = dict(position, body=body, commit_id=head_sha)
        data = self._api_call(self.host, "POST", self._pull(number, "/comments"), payload)
        return {"published": True, "discussion_id": str(data.get("id")), "note_id": data.get("id"),
                "url": data.get("html_url"), "head_sha": head_sha}

    def post_overview(self, number, body):
        data = self._api_call(self.host, "POST", self._repo("/issues/%s/comments" % number), {"body": body})
        return {"published": True, "note_id": data.get("id"), "url": data.get("html_url")}

    # -- reviewer seat -----------------------------------------------------------
    def identity(self):
        user = self.current_user()
        if not user:
            raise ForgeError("authenticated GitHub identity has an unexpected shape")
        return {"id": user["id"], "username": user["username"]}

    def live_change(self, number):
        """Return (raw, refs{base_sha,start_sha,head_sha}, author) for an open pull request."""
        data = self._pull_data(number)
        if data.get("state") != "open" or data.get("merged"):
            raise ForgeError("%s is not open" % self.change_label(number))
        head_sha = (data.get("head") or {}).get("sha")
        merge_base = self._merge_base((data.get("base") or {}).get("sha"), head_sha)
        refs = {"base_sha": merge_base, "start_sha": merge_base, "head_sha": head_sha}
        return data, refs, data.get("user") or {}

    def _pending_reviews(self, number, username):
        reviews = get_pages(self._api_call, self.host, self._pull(number, "/reviews"))
        return [r for r in reviews if r.get("state") == "PENDING"
                and str((r.get("user") or {}).get("login") or "").casefold() == str(username).casefold()]

    def pending(self, number, username):
        """This user's unsubmitted review content, as draft-like items."""
        items = []
        for review in self._pending_reviews(number, username):
            items.append({"id": review["id"], "note": review.get("body") or "", "position": None})
            for comment in get_pages(self._api_call, self.host, self._pull(number, "/reviews/%s/comments" % review["id"])):
                items.append({"id": comment["id"], "note": comment.get("body") or "",
                              "position": {"new_path": comment.get("path"), "new_line": comment.get("line")}})
        return items

    def stage_notes(self, number, notes, head_sha, record, username):
        """Create one pending review holding the overview and inline notes, then add replies.

        GitHub allows one pending review per user and cannot append comments to it over
        REST, so inline notes go in the single create call. A create that errors may still
        have committed; the overview digest identifies it so it is adopted, never duplicated.
        """
        overview = next(n for n in notes if n["kind"] == "overview")
        inline = [n for n in notes if n["kind"] == "inline"]
        payload = {"commit_id": head_sha, "body": overview["body"],
                   "comments": [dict(n["position"], body=n["body"]) for n in inline]}
        try:
            review = self._api_call(self.host, "POST", self._pull(number, "/reviews"), payload)
        except ForgeError:
            review = self._adopt(number, username, overview["body"])
            if review is None:
                raise
        review_id = positive_int(review.get("id"), "created review id")
        record(overview, review_id, review_id=review_id, review_node_id=review.get("node_id"))
        created = get_pages(self._api_call, self.host, self._pull(number, "/reviews/%s/comments" % review_id))
        by_key = {}
        for comment in created:
            by_key.setdefault((comment.get("path"), comment.get("line"), _digest(comment.get("body"))), []).append(comment["id"])
        for note in inline:
            key = (note["position"]["path"], note["position"]["line"], _digest(note["body"]))
            ids = by_key.get(key) or []
            if not ids:
                raise ForgeError("GitHub did not return the staged comment for %s" % note.get("finding_id"))
            record(note, ids.pop(0))
        node_id = review.get("node_id")
        for note in (n for n in notes if n["kind"] == "reply"):
            data = graphql(self._api_call, self.host,
                           "mutation($t:ID!,$p:ID!,$b:String!){addPullRequestReviewThreadReply(input:"
                           "{pullRequestReviewThreadId:$t,pullRequestReviewId:$p,body:$b})"
                           "{comment{databaseId pullRequestReview{databaseId state}}}}",
                           {"t": note["discussion_id"], "p": node_id, "b": note["body"]})
            comment = ((data.get("addPullRequestReviewThreadReply") or {}).get("comment") or {})
            if (comment.get("pullRequestReview") or {}).get("state") != "PENDING":
                raise ForgeError("GitHub did not attach the support reply to the pending review")
            record(note, positive_int(comment.get("databaseId"), "created reply id"))

    def _adopt(self, number, username, overview_body):
        try:
            pending = self._pending_reviews(number, username)
        except ForgeError:
            return None
        matches = [r for r in pending if _digest(r.get("body")) == _digest(overview_body)]
        return matches[0] if len(matches) == 1 else None

    def live_staged_ids(self, number, username):
        return {item["id"] for item in self.pending(number, username)}

    def publish(self, number, state):
        self._api_call(self.host, "POST", self._pull(number, "/reviews/%s/events" % state["review_id"]),
                       {"event": "COMMENT"})

    def complete(self, number, action, head_sha, body):
        if action == "comment-only":
            return {"comment_only": True}
        event = {"approve": "APPROVE", "request-changes": "REQUEST_CHANGES"}[action]
        payload = {"commit_id": head_sha, "event": event}
        if event == "REQUEST_CHANGES":
            payload["body"] = body
        data = self._api_call(self.host, "POST", self._pull(number, "/reviews"), payload)
        return {"review_id": data.get("id"), "state": data.get("state")}

    def cleanup_commands(self, state):
        review_id = state.get("review_id")
        if not review_id:
            return []
        endpoint = "repos/%s/pulls/%s/reviews/%s" % (state["project"], state["number"], review_id)
        return ["gh api --hostname %s -X DELETE %s" % (shlex.quote(state["host"]), shlex.quote(endpoint))]
