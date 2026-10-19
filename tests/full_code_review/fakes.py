"""Fakes and constants shared by the GitHub adapter and the posting-script tests."""
import json
import re

from forge import ForgeError
from forge.github import GitHubForge

HOST, PROJECT, NUMBER = "github.com", "o/r", 7
BASE_TIP, MERGE_BASE, HEAD = "b" * 40, "c" * 40, "a" * 40
DIFF = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,4 @@\n one\n+two\n three\n four\n"
        "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -6,2 +6,3 @@\n six\n+seven\n eight\n")


class FakeGitHub:
    """Answers the GitHub REST/GraphQL calls the adapter makes, recording each one."""

    def __init__(self):
        self.calls = []
        self.user = {"id": 2, "login": "reviewer"}
        self.pr = {"number": NUMBER, "state": "open", "merged": False, "title": "Fix pagination",
                   "body": "Fixes the page size.", "html_url": "https://github.com/o/r/pull/7",
                   "user": {"id": 1, "login": "author"}, "author_association": "MEMBER",
                   "changed_files": 3,
                   "head": {"sha": HEAD, "ref": "feature", "repo": {"full_name": "o/r"}},
                   "base": {"sha": BASE_TIP, "ref": "main", "repo": {"full_name": "o/r"}}}
        self.files = [
            {"filename": "a.py", "status": "modified", "patch": "@@ -1,3 +1,4 @@\n one\n+two\n three\n four",
             "changes": 1},
            {"filename": "img.png", "status": "added", "changes": 0},
            {"filename": "new.py", "previous_filename": "old.py", "status": "renamed",
             "patch": "@@ -1 +1 @@\n-x\n+y", "changes": 2},
        ]
        self.commits = [{"author": {"login": "author"}, "commit": {"author": {"email": "a@x.io"}}}]
        self.compare_files = [{"filename": "a.py"}]
        self.reviews = []
        self.review_comments = {}
        self.threads = []
        self.next_id = 500
        self.fail_create_after_commit = False

    def _id(self):
        self.next_id += 1
        return self.next_id

    def _page(self, items, endpoint):
        page = int(re.search(r"[?&]page=(\d+)", endpoint).group(1))
        return items[(page - 1) * 100:page * 100]

    def __call__(self, host, method, endpoint, payload=None, timeout=120):
        self.calls.append((method, endpoint, payload))
        pull = "repos/o/r/pulls/7"
        if method == "GET" and endpoint == "user":
            return dict(self.user)
        if method == "GET" and endpoint == pull:
            return json.loads(json.dumps(self.pr))
        if method == "GET" and endpoint.startswith("repos/o/r/compare/"):
            return {"merge_base_commit": {"sha": MERGE_BASE}, "files": self.compare_files}
        if method == "GET" and endpoint.startswith(pull + "/files?"):
            return self._page(self.files, endpoint)
        if method == "GET" and endpoint.startswith(pull + "/commits?"):
            return self._page(self.commits, endpoint)
        if method == "GET" and endpoint.startswith("repos/o/r/pulls?head="):
            return [{"number": NUMBER}] if "o:feature" in endpoint else []
        if method == "GET" and re.match(pull + r"/reviews/\d+/comments\?", endpoint):
            return self._page(self.review_comments.get(int(endpoint.split("/")[6]), []), endpoint)
        if method == "GET" and endpoint.startswith(pull + "/reviews?"):
            return self._page(self.reviews, endpoint)
        if method == "POST" and endpoint == pull + "/reviews":
            review = {"id": self._id(), "node_id": "PRR_%d" % self.next_id, "body": payload.get("body", ""),
                      "user": {"login": self.user["login"]},
                      "state": "PENDING" if "event" not in payload else payload["event"]}
            self.reviews.append(review)
            self.review_comments[review["id"]] = [
                {"id": self._id(), "path": c["path"], "line": c["line"], "body": c["body"]}
                for c in payload.get("comments", [])]
            if self.fail_create_after_commit:
                self.fail_create_after_commit = False
                raise ForgeError("GitHub POST failed: HTTP 422", "validation")
            return {"id": review["id"], "node_id": review["node_id"], "state": review["state"]}
        if method == "POST" and re.match(pull + r"/reviews/\d+/events$", endpoint):
            review = next(r for r in self.reviews if r["id"] == int(endpoint.split("/")[6]))
            review["state"] = "COMMENTED"
            return {"id": review["id"], "state": "COMMENTED"}
        if method == "POST" and endpoint == pull + "/comments":
            return {"id": self._id(), "html_url": "https://github.com/o/r/pull/7#discussion_r%d" % self.next_id}
        if method == "POST" and endpoint == "repos/o/r/issues/7/comments":
            return {"id": self._id(), "html_url": "https://github.com/o/r/pull/7#issuecomment-%d" % self.next_id}
        if method == "POST" and endpoint == "graphql":
            return self._graphql(payload)
        raise AssertionError((method, endpoint, payload))

    def _graphql(self, payload):
        query, variables = payload["query"], payload["variables"]
        if "reviewThreads" in query:
            return {"data": {"repository": {"pullRequest": {"reviewThreads": {
                "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": self.threads}}}}}
        if "addPullRequestReviewThreadReply" in query:
            review = next(r for r in self.reviews if r["node_id"] == variables["p"])
            comment = {"id": self._id(), "path": None, "line": None, "body": variables["b"]}
            self.review_comments[review["id"]].append(comment)
            return {"data": {"addPullRequestReviewThreadReply": {"comment": {
                "databaseId": comment["id"], "pullRequestReview": {"databaseId": review["id"],
                                                                  "state": review["state"]}}}}}
        raise AssertionError(query)


def forge(fake):
    return GitHubForge(HOST, PROJECT, api_call=fake)
