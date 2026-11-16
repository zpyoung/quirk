"""Tests for the --quick parallel review pipeline (`scripts/quick_review.py`)."""

from __future__ import annotations

import json
from pathlib import Path

import quick_review


def test_annotate_diff_tracks_exact_new_file_lines():
    diff = (
        "diff --git a/app/svc.py b/app/svc.py\n"
        "--- a/app/svc.py\n"
        "+++ b/app/svc.py\n"
        "@@ -10,3 +10,4 @@ def run():\n"
        " context_line\n"
        "-old_line\n"
        "+new_line_1\n"
        "+new_line_2\n"
    )
    annotated, hunks = quick_review._annotate_diff(diff)
    assert hunks == {"app/svc.py": [(10, 13)]}
    assert "   10   context_line" in annotated
    assert "  OLD - old_line" in annotated
    assert "   11 + new_line_1" in annotated
    assert "   12 + new_line_2" in annotated


def test_deduplicate_findings_merges_true_duplicates_and_keeps_distinct_defects_apart():
    items = [
        {
            "severity": "Should fix",
            "dimension": "correctness",
            "dimensions": ["correctness"],
            "file": "app/svc.py",
            "line": "142",
            "title": "Redis cache write omits TTL expiration",
            "impact": "Cached count never expires in Redis.",
            "fix_md": "Pass ex=300 to redis.set.",
            "issue": "redis.set is called without ex= TTL so the key never expires.",
            "body_md": "redis.set is called without ex= TTL so the key never expires.",
            "recommendation": "Pass ex=300.",
            "recommendation_md": "Pass ex=300.",
            "verified": True,
            "verification_status": "confirmed",
            "assumptions": [],
        },
        {
            "severity": "Nit",
            "dimension": "safety",
            "dimensions": ["safety"],
            "file": "app/svc.py",
            "line": "141-143",
            "title": "Redis set call missing TTL expiration",
            "impact": "Stale cache key persists indefinitely in Redis.",
            "fix_md": "Add ex= TTL parameter to redis.set.",
            "issue": "Calling redis.set without TTL leaves stale keys in Redis.",
            "body_md": "Calling redis.set without TTL leaves stale keys in Redis.",
            "recommendation": "Add ex=60.",
            "recommendation_md": "Add ex=60.",
            "verified": True,
            "verification_status": "confirmed",
            "assumptions": [],
        },
        {
            "severity": "Must fix",
            "dimension": "safety",
            "dimensions": ["safety"],
            "file": "app/svc.py",
            "line": "142",
            "title": "Cache key omits store_id causing cross-tenant data leak",
            "impact": "One store's count is served to another store.",
            "fix_md": "Include store_id in the Redis cache key.",
            "issue": "The cache key is global and omits store_id.",
            "body_md": "The cache key is global and omits store_id.",
            "recommendation": "Include store_id in key.",
            "recommendation_md": "Include store_id in key.",
            "verified": True,
            "verification_status": "confirmed",
            "assumptions": [],
        },
    ]
    merged = quick_review._deduplicate_findings(items)
    assert len(merged) == 2
    assert merged[0]["severity"] == "Must fix"
    assert "store_id" in merged[0]["title"]
    assert merged[1]["severity"] == "Should fix"
    assert set(merged[1]["dimensions"]) == {"correctness", "safety"}


def test_prepare_and_finalize_quick_end_to_end(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def greet(name):\n    return f'hi {name}'\n", encoding="utf-8")

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ctx = {
        "target": "mr",
        "seat": "reviewer",
        "project": "engineering/demo",
        "mr": {
            "iid": 42,
            "title": "Demo MR",
            "description": "Adds greet helper.",
            "state": "opened",
            "source_branch": "feat/greet",
            "target_branch": "main",
            "web_url": "https://gitlab.example.com/engineering/demo/-/merge_requests/42",
        },
        "refs": {"base": "a" * 40, "head": "b" * 40, "start": "a" * 40},
        "changed_files": ["app.py"],
        "size": {"files": 1, "lines": 2, "additions": 2, "deletions": 0},
        "coverage": {},
        "diff": (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,0 +1,2 @@\n"
            "+def greet(name):\n"
            "+    return f'hi {name}'\n"
        ),
    }
    (run_dir / "review-context.json").write_text(json.dumps(ctx), encoding="utf-8")
    (run_dir / "review-source.json").write_text(
        json.dumps({"kind": "worktree", "path": str(repo), "borrowed": False, "mutation_consent": False}),
        encoding="utf-8",
    )

    rc = quick_review.main(["prepare", "--run-dir", str(run_dir), "--repo", str(repo), "--headless"])
    assert rc == 0
    manifest = json.loads((run_dir / "quick-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["packs"]) == 7

    for p in manifest["packs"]:
        assert Path(p["prompt_file"]).is_file()
        Path(p["raw_file"]).write_text("[]", encoding="utf-8")

    Path(manifest["packs"][0]["raw_file"]).write_text(
        json.dumps([
            {
                "severity": "Should fix",
                "dimension": "correctness",
                "file": "app.py",
                "line": "2",
                "title": "Missing None check on name",
                "impact": "Passes 'None' string into greeting.",
                "fix_md": "Guard against None.",
                "issue": "At app.py:2, name=None formats literal 'hi None'.",
                "recommendation": "```python\nif not name:\n    return 'hi'\n```",
                "verified": True,
                "assumptions": [],
            }
        ]),
        encoding="utf-8",
    )

    rc_fin = quick_review.main(["finalize", "--run-dir", str(run_dir), "--wait", "1", "--format", "md", "--headless"])
    assert rc_fin == 0
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert len(report["findings"]) == 1
    assert report["findings"][0]["title"] == "Missing None check on name"
    assert (run_dir / "review-42-findings.md").is_file()
