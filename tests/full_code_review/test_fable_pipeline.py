from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "full-code-review"
SCRIPT = SKILL_DIR / "scripts" / "fable_pipeline.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import fable_pipeline as fp


def test_normalize_external_and_function_anchors_maps_sibling_consumer_to_changed_producer(tmp_path):
    src = tmp_path / "repo"
    src.mkdir()
    prod_file = src / "customcheckout" / "schemas" / "settings_schema.py"
    prod_file.parent.mkdir(parents=True)
    prod_file.write_text(
        "class SettingsSchema:\n"
        "    # line 2\n"
        "    beta_flags = Dict(keys=String(), values=String())\n",
        encoding="utf-8",
    )
    diff = (
        "diff --git a/customcheckout/schemas/settings_schema.py b/customcheckout/schemas/settings_schema.py\n"
        "--- a/customcheckout/schemas/settings_schema.py\n"
        "+++ b/customcheckout/schemas/settings_schema.py\n"
        "@@ -1,3 +1,3 @@\n"
        " class SettingsSchema:\n"
        "     # line 2\n"
        "+    beta_flags = Dict(keys=String(), values=String())\n"
    )
    ctx = {
        "changed_files": ["customcheckout/schemas/settings_schema.py"],
        "source_files": ["customcheckout/schemas/settings_schema.py"],
        "test_files": [],
        "diff": diff,
    }
    hunk_index = fp._build_changed_hunk_index(diff)
    finding = {
        "file": "/Users/test/selling-plan-sync/app/shop_internal_settings.py",
        "line": "56",
        "title": "selling-plan-sync parses beta_flags as list[str]",
        "issue": "External consumer breaks when beta_flags changes to a dict.",
    }
    fp._normalize_external_and_function_anchors(finding, ctx, str(src), hunk_index)
    assert finding["file"] == "customcheckout/schemas/settings_schema.py"
    assert finding["line"] == "3"
    assert "[External consumer `/Users/test/selling-plan-sync/app/shop_internal_settings.py:56`]" in finding["issue"]


def test_prepare_wait_and_finalize_sharded_and_deep_modes(tmp_path):
    run_dir = tmp_path / "run"
    src = tmp_path / "repo"
    (src / "app").mkdir(parents=True)
    (src / "tests").mkdir(parents=True)
    (src / "app" / "service.py").write_text(
        "def release_attempt(attempt_id):\n"
        "    return attempt_id\n" + "x = 1\n" * 30,
        encoding="utf-8",
    )
    (src / "tests" / "test_service.py").write_text(
        "def test_release():\n    assert True\n",
        encoding="utf-8",
    )
    (run_dir / "briefs").mkdir(parents=True)
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "tables").mkdir(parents=True)

    diff = (
        "diff --git a/app/service.py b/app/service.py\n"
        "--- a/app/service.py\n"
        "+++ b/app/service.py\n"
        "@@ -1,5 +1,5 @@\n"
        "+def release_attempt(attempt_id):\n"
        "+    return attempt_id\n"
    )
    ctx = {
        "schema": 1,
        "forge": "gitlab",
        "seat": "reviewer",
        "source": "gitlab",
        "mode": "mr",
        "host": "gitlab.example.net",
        "project": "group/proj",
        "refs": {"base": "a" * 40, "start": "a" * 40, "head": "b" * 40},
        "mr": {"iid": 42, "title": "Test MR", "description": "Claims idempotent release.", "author_username": "dev", "current_username": "rev", "web_url": "https://gitlab.example.net/group/proj/-/merge_requests/42", "state": "opened"},
        "size": {"files": 2, "lines": 10},
        "changed_files": ["app/service.py", "tests/test_service.py"],
        "source_files": ["app/service.py"],
        "test_files": ["tests/test_service.py"],
        "diff": diff,
        "scope_intent": {"statement": "Release attempts", "source": "description"},
    }
    (run_dir / "review-context.json").write_text(json.dumps(ctx), encoding="utf-8")
    (run_dir / "context-meta.json").write_text(json.dumps({k: v for k, v in ctx.items() if k != "diff"}), encoding="utf-8")
    (run_dir / "diff.patch").write_text(fp._annotate_diff(diff), encoding="utf-8")
    (run_dir / "review-source.json").write_text(json.dumps({"path": str(src), "acquisition": "reused-cwd", "mutation_consent": True}), encoding="utf-8")
    (run_dir / "guidance.json").write_text(json.dumps({"quirk_guidance": {}, "target_repo_guidance": {}}), encoding="utf-8")
    (run_dir / "dimensions-plan.json").write_text(json.dumps({"dimensions_run": fp.ALL_DIMENSIONS[:-1], "dimensions_skipped": [{"dimension": "test-coverage", "reason": "test files present"}]}), encoding="utf-8")
    (run_dir / "dispatch.json").write_text(json.dumps({"agents": [{"name": "correctness"}, {"name": "adversarial", "exempt": "test"}]}), encoding="utf-8")
    (run_dir / "prepass.json").write_text(
        json.dumps({
            "scope_intent": {"statement": "Release attempts", "source": "description"},
            "standfirst_md": "Summary",
            "risk": {"level": "High", "likelihood": {"level": "Frequent", "tone": "bad", "note_md": "High"}, "impact": {"level": "Major", "tone": "bad", "note_md": "High"}, "mitigations_md": "Fix"},
            "promise": "Release attempt",
            "structural_read": "Read",
            "repo_facts": ["app/service.py:1"],
            "changed_symbols": ["release_attempt"],
            "hints": {"correctness": ["Check app/service.py:1"]},
        }),
        encoding="utf-8",
    )
    (run_dir / "area-map.json").write_text(
        json.dumps({"areas": [{"id": "A1", "files": ["app/service.py"], "test_files": ["tests/test_service.py"], "coupled_edges": [], "questions": ["Q1"], "hunks": [{"id": "A1.h1", "file": "app/service.py", "header": "@@ -1,5 +1,5 @@"}], "hunkless_files": [], "priority": 1, "status": "pending", "degraded_reason": None}]}),
        encoding="utf-8",
    )
    (run_dir / "deep-config.json").write_text(json.dumps({"deep": True, "budget_minutes": 60.0, "started_epoch": 1000.0, "consent": False}), encoding="utf-8")
    (run_dir / "deep-trust.json").write_text(json.dumps({"allowed": False, "consent": False, "prompt_required": False, "reason": "test"}), encoding="utf-8")

    r_prep = subprocess.run([sys.executable, str(SCRIPT), "prepare-focuses", "--run-dir", str(run_dir), "--deep"], capture_output=True, text=True, check=True)
    prep_out = json.loads(r_prep.stdout)
    assert prep_out["count"] >= 4

    for p_file in prep_out["prompts"]:
        stem = p_file["name"]
        (run_dir / "raw" / f"{stem}.json").write_text(
            json.dumps([{
                "severity": "Must fix",
                "dimension": "correctness",
                "file": "app/service.py",
                "line": "1-2",
                "title": f"Bug from {stem}",
                "impact": "Breaks release",
                "fix_md": "Check store_id",
                "issue": "Body",
                "recommendation": "Fix it",
                "verified": True,
                "assumptions": [],
            }]),
            encoding="utf-8",
        )
        (run_dir / "tables" / f"{stem}.md").write_text("| Col1 | Col2 |\n|---|---|\n| a | b [#0] |\n", encoding="utf-8")
        (run_dir / "focus" / "checked").mkdir(parents=True, exist_ok=True)
        (run_dir / "focus" / "checked" / stem).write_text("ok\n", encoding="utf-8")

    r_wait = subprocess.run([sys.executable, str(SCRIPT), "wait-and-prepare-fable", "--run-dir", str(run_dir), "--timeout", "1", "--shards", "1", "--verifier-model", "fable", "--deep"], capture_output=True, text=True, check=True)
    wait_out = json.loads(r_wait.stdout)
    assert wait_out["ok"] is True

    (run_dir / "fable-ledger.json").write_text(
        json.dumps({
            "groups": [{"primary": "correctness#0", "duplicates": ["correctness#1"], "severity": "Must fix", "production": {"label": "Common path", "path": "release_attempt -> line 1"}}],
            "drops": [],
            "recommended_order": ["Fix release_attempt"],
        }),
        encoding="utf-8",
    )
    r_fin = subprocess.run([sys.executable, str(SCRIPT), "finalize", "--run-dir", str(run_dir), "--prepass-model", "fable", "--verifier-model", "fable", "--deep"], capture_output=True, text=True, check=True)
    fin_out = json.loads(r_fin.stdout)
    assert fin_out["ok"] is True
    assert fin_out["must_fix"] == 1
    assert (run_dir / "review-42-findings.md").is_file()


def test_resolve_vendor_models_supports_all_vendors():
    assert fp.resolve_vendor_models("anthropic", "standard") == {
        "vendor": "anthropic", "prepass": "opus", "swarm": "haiku", "verifier": "sonnet", "shards": 4
    }
    assert fp.resolve_vendor_models("anthropic", "deep") == {
        "vendor": "anthropic", "prepass": "fable", "swarm": "haiku", "verifier": "fable", "shards": 1
    }
    assert fp.resolve_vendor_models("openai", "standard") == {
        "vendor": "openai", "prepass": "codex", "swarm": "codex-mini", "verifier": "codex", "shards": 4
    }
    assert fp.resolve_vendor_models("openai", "deep") == {
        "vendor": "openai", "prepass": "codex-max", "swarm": "codex-mini", "verifier": "codex-max", "shards": 1
    }
    assert fp.resolve_vendor_models("google", "standard") == {
        "vendor": "google", "prepass": "gemini", "swarm": "flash", "verifier": "gemini", "shards": 4
    }
    assert fp.resolve_vendor_models("xai", "deep") == {
        "vendor": "xai", "prepass": "grok", "swarm": "grok", "verifier": "grok", "shards": 1
    }
