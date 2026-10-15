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
from urllib.parse import quote

from forge import ForgeError, change_label as _change_label, default_run, positive_int
from forge import note_url as _note_url

NAME = "github"
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
_MAX_PAGES = 30
# the pulls/{n}/commits and compare endpoints stop listing at these counts without signalling truncation
_COMMITS_CAP = 250
_COMPARE_FILES_CAP = 300


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


def _get_pages_capped(api_call, host, endpoint):
    """GET up to _MAX_PAGES pages of a list endpoint (per_page=100); return (items, truncated)."""
    items = []
    separator = "&" if "?" in endpoint else "?"
    for page in range(1, _MAX_PAGES + 1):
        data = api_call(host, "GET", "%s%sper_page=100&page=%d" % (endpoint, separator, page))
        if not isinstance(data, list):
            raise ForgeError("GitHub page %d of %s is not a JSON list" % (page, endpoint.split("?", 1)[0]))
        items.extend(data)
        if len(data) < 100:
            return items, False
    return items, True


def get_pages(api_call, host, endpoint):
    """GET every page of a list endpoint (per_page=100), rejecting runaway pagination."""
    items, truncated = _get_pages_capped(api_call, host, endpoint)
    if truncated:
        raise ForgeError("GitHub pagination of %s exceeded %d pages" % (endpoint.split("?", 1)[0], _MAX_PAGES))
    return items


def _digest(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _header_path(text, prefix):
    """Return the path in a ---/+++ header line, or None for /dev/null."""
    text = text.split("\t", 1)[0]
    if text == "/dev/null":
        return None
    return text[len(prefix):] if text.startswith(prefix) else text


def hunk_lines(diff_text, path):
    """Return ({new-side lines}, {old-side lines}) a review comment may anchor on for `path`.

    `path` matches a file's new path, or its old path when the file was deleted. Hunk
    line counts decide where a hunk ends, so added or removed lines that look like
    `+++ ` or `--- ` headers are still read as content.
    """
    new_lines, old_lines = set(), set()
    old_path = new_path = None
    old_no = new_no = old_left = new_left = 0
    in_file = False
    for line in (diff_text or "").splitlines():
        if line.startswith("diff --git "):
            old_path = new_path = None
            old_left = new_left = 0
            in_file = False
            continue
        if old_left <= 0 and new_left <= 0:
            if line.startswith("--- "):
                old_path = _header_path(line[4:], "a/")
            elif line.startswith("+++ "):
                new_path = _header_path(line[4:], "b/")
            else:
                match = _HUNK_RE.match(line)
                if match:
                    old_no, new_no = int(match.group(1)), int(match.group(3))
                    old_left = int(match.group(2) if match.group(2) is not None else 1)
                    new_left = int(match.group(4) if match.group(4) is not None else 1)
                continue
            in_file = path == new_path or (new_path is None and path == old_path)
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("+"):
            if in_file:
                new_lines.add(new_no)
            new_no += 1
            new_left -= 1
        elif line.startswith("-"):
            if in_file:
                old_lines.add(old_no)
            old_no += 1
            old_left -= 1
        else:
            if in_file:
                new_lines.add(new_no)
                old_lines.add(old_no)
            old_no += 1
            new_no += 1
            old_left -= 1
            new_left -= 1
    return new_lines, old_lines


class GitHubForge:
    """GitHub bound to one host and owner/repo, with injectable transport.

    `change_details` and `current_user` return None on failure; `last_error` then holds the
    cause (None after a success) so callers can report why.
    """

    name = NAME

    def __init__(self, host, project, run=None, api_call=None):
        self.host = host
        self.project = project
        self.last_error = None
        self._run = run or default_run
        self._api_call = api_call or (lambda h, m, e, p=None, timeout=120: api(self._run, h, m, e, p, timeout))

    def change_label(self, number):
        return _change_label(NAME, number)

    def note_url(self, number, note_id):
        return _note_url(NAME, self.host, self.project, number, note_id)

    def _repo(self, suffix=""):
        return "repos/%s%s" % (self.project, suffix)

    def _pull(self, number, suffix=""):
        return self._repo("/pulls/%s%s" % (number, suffix))

    def current_user(self):
        self.last_error = None
        try:
            data = self._api_call(self.host, "GET", "user")
        except ForgeError as exc:
            self.last_error = str(exc)
            return None
        if not isinstance(data, dict) or not data.get("id") or not data.get("login"):
            self.last_error = "GitHub user response is missing an id or login"
            return None
        return {"id": data["id"], "username": data["login"],
                "emails": [data["email"]] if data.get("email") else []}

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
        items, truncated = _get_pages_capped(self._api_call, self.host, self._pull(number, "/files"))
        for item in items:
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
            "overflow": True if truncated else None,
        }

    def change_details(self, number):
        self.last_error = None
        try:
            data = self._pull_data(number)
            head = data.get("head") or {}
            base = data.get("base") or {}
            merge_base = self._merge_base(base.get("sha"), head.get("sha"))
        except ForgeError as exc:
            self.last_error = str(exc)
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
        """Return [{username, email}] per commit, or None when the list may be incomplete.

        GitHub stops listing a pull request's commits at 250 without saying so, so a
        list that reaches the cap is unknown rather than a complete author set.
        """
        try:
            commits = get_pages(self._api_call, self.host, self._pull(number, "/commits"))
        except ForgeError:
            return None
        if len(commits) >= _COMMITS_CAP:
            return None
        return [{"username": (c.get("author") or {}).get("login"),
                 "email": ((c.get("commit") or {}).get("author") or {}).get("email")}
                for c in commits if isinstance(c, dict)]

    def find_change_for_branch(self, branch):
        owner = self.project.split("/", 1)[0]
        head = "%s:%s" % (quote(owner, safe=""), quote(branch, safe=""))
        try:
            data = self._api_call(self.host, "GET", self._repo("/pulls?head=%s&state=open" % head))
        except ForgeError:
            return None
        return data[0].get("number") if isinstance(data, list) and data else None

    def changed_paths(self, old_head, new_head):
        """Return the paths changed between two heads; raise when GitHub may have truncated them."""
        data = self._api_call(self.host, "GET", self._repo("/compare/%s...%s" % (old_head, new_head)))
        files = data.get("files") if isinstance(data, dict) else None
        if not isinstance(files, list):
            raise ForgeError("GitHub compare response is missing files")
        if len(files) >= _COMPARE_FILES_CAP:
            raise ForgeError("GitHub compare lists at most %d files, so the changed-file set may be incomplete"
                             % _COMPARE_FILES_CAP)
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

    _THREADS_QUERY = (
        "query($owner:String!,$name:String!,$number:Int!,$after:String){repository(owner:$owner,name:$name)"
        "{pullRequest(number:$number){reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor}"
        "nodes{id isResolved path line comments(first:100){pageInfo{hasNextPage} "
        "nodes{databaseId body url author{login ... on User{databaseId}}}}}}}}}")

    def list_threads(self, number, api_call=None):
        """Return review threads as GitLab-style discussion dicts.

        Raises when a thread has more than 100 comments, because the remainder would be
        silently invisible to duplicate-post suppression.
        """
        call = api_call or self._api_call
        owner, name = self.project.split("/", 1)
        threads, after = [], None
        for _ in range(_MAX_PAGES):
            data = graphql(call, self.host, self._THREADS_QUERY,
                           {"owner": owner, "name": name, "number": int(number), "after": after})
            page = (((data.get("repository") or {}).get("pullRequest") or {}).get("reviewThreads") or {})
            for node in page.get("nodes") or []:
                if ((node.get("comments") or {}).get("pageInfo") or {}).get("hasNextPage"):
                    raise ForgeError("GitHub review thread %s has more than 100 comments" % node.get("id"))
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

        Only the overview and inline notes are created together. Replies are separate
        GraphQL mutations that need the review's node id, so a reply failure leaves a
        pending review without them, and `cleanup_commands` removes it. GitHub allows one
        pending review per user and cannot append comments to it over REST, so inline
        notes go in the single create call. A create that errors may still have committed;
        the overview digest identifies it so it is adopted, never duplicated.
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
