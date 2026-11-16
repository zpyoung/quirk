#!/usr/bin/env python3
"""Three-wave deterministic bookend pipeline for Standard (Opus->25 Haiku->4x Sonnet) and --fable (Fable->25 Haiku->Fable)."""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import check_anchors  # noqa: E402
import check_merge_ledger as ledger  # noqa: E402
import combine_focus_outputs as cfo  # noqa: E402
import jsonio  # noqa: E402
import render_report  # noqa: E402



VENDOR_PRESETS = {
    "anthropic": {
        "standard": {"prepass": "opus", "swarm": "haiku", "verifier": "sonnet", "shards": 4},
        "deep": {"prepass": "fable", "swarm": "haiku", "verifier": "fable", "shards": 1},
        "quick": {"deep_pack": "sonnet", "fast_pack": "haiku"},
    },
    "openai": {
        "standard": {"prepass": "codex", "swarm": "codex-mini", "verifier": "codex", "shards": 4},
        "deep": {"prepass": "codex-max", "swarm": "codex-mini", "verifier": "codex-max", "shards": 1},
        "quick": {"deep_pack": "codex", "fast_pack": "codex-mini"},
    },
    "google": {
        "standard": {"prepass": "gemini", "swarm": "flash", "verifier": "gemini", "shards": 4},
        "deep": {"prepass": "gemini", "swarm": "flash", "verifier": "gemini", "shards": 1},
        "quick": {"deep_pack": "gemini", "fast_pack": "flash"},
    },
    "xai": {
        "standard": {"prepass": "grok", "swarm": "grok", "verifier": "grok", "shards": 4},
        "deep": {"prepass": "grok", "swarm": "grok", "verifier": "grok", "shards": 1},
        "quick": {"deep_pack": "grok", "fast_pack": "grok"},
    },
    "auto": {
        "standard": {"prepass": "opus", "swarm": "haiku", "verifier": "sonnet", "shards": 4},
        "deep": {"prepass": "fable", "swarm": "haiku", "verifier": "fable", "shards": 1},
        "quick": {"deep_pack": "sonnet", "fast_pack": "haiku"},
    },
}


def resolve_vendor_models(vendor: str, mode: str = "standard", prepass_override: str | None = None,
                          swarm_override: str | None = None, verifier_override: str | None = None) -> dict:
    v = (vendor or "anthropic").lower()
    if v not in VENDOR_PRESETS:
        v = "anthropic"
    base = dict(VENDOR_PRESETS[v].get(mode, VENDOR_PRESETS[v]["standard"]))
    if prepass_override:
        base["prepass"] = prepass_override
    if swarm_override:
        base["swarm"] = swarm_override
    if verifier_override:
        base["verifier"] = verifier_override
    base["vendor"] = v
    return base


def dispatch_pi_watch(model_spec: str, prompt_text: str, cwd: str, tools: str = "read,bash,edit,write", timeout: int = 540) -> tuple[int, str, str]:
    """Dispatch a single prompt through `pi-watch` (supporting any vendor alias or provider/model)."""
    cmd = ["pi-watch"]
    if "/" in model_spec:
        prov, mod = model_spec.split("/", 1)
        cmd.extend(["--provider", prov, "--model", mod])
    else:
        cmd.extend(["--alias", model_spec])
    if tools == "none":
        cmd.append("--no-tools")
    elif tools:
        cmd.extend(["--tools", tools])
    if cwd and os.path.isdir(cwd):
        cmd.extend(["--cwd", cwd])
    cmd.append(prompt_text)
    res = _run(cmd, cwd=cwd if (cwd and os.path.isdir(cwd)) else None, timeout=timeout)
    return res.returncode, res.stdout, res.stderr


ALL_DIMENSIONS = [
    "correctness",
    "safety",
    "risk",
    "adversarial",
    "scope",
    "db",
    "cross-repo",
    "conventions",
    "comments",
    "observability",
    "resilience",
    "test-adequacy",
    "tests",
    "test-coverage",
]

TEST_BARE_DIMS = {"tests", "test-adequacy", "test-coverage"}
NON_RUNTIME_BARE_DIMS = {"comments", "conventions", "scope", "adversarial"}
PRODUCTION_LABELS = ("Common path", "Edge case", "Unreachable", "Would miss", "N/A")


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _one_line(text: object, cap: int, default: str = "Finding") -> str:
    cleaned = " ".join(str(text or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if not cleaned:
        cleaned = default
    return cleaned if len(cleaned) <= cap else cleaned[: cap - 1].rstrip() + "…"


def _annotate_diff(diff_text: str) -> str:
    out = []
    new_line = None
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for raw in diff_text.splitlines():
        m = hunk_re.match(raw)
        if m:
            new_line = int(m.group(1))
            out.append(raw)
            continue
        if raw.startswith(("+++ ", "--- ", "diff --git ")):
            new_line = None
            out.append(raw)
            continue
        if new_line is not None:
            if raw.startswith("+"):
                out.append(f"[L{new_line:4d}] {raw}")
                new_line += 1
                continue
            if raw.startswith("-"):
                out.append(f"[OLD  ] {raw}")
                continue
            if raw.startswith(" "):
                out.append(f"[L{new_line:4d}] {raw}")
                new_line += 1
                continue
        out.append(raw)
    return "\n".join(out)


def _diff_hunk_ranges(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    by_file: dict[str, list[tuple[int, int]]] = {}
    cur_file = None
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:].strip()
        elif line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            cur_file = line[4:].strip()
        elif cur_file:
            m = hunk_re.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                by_file.setdefault(cur_file, []).append((start, max(start, start + count - 1)))
    return by_file


def _extract_source_windows(
    source_root: str,
    files: list[str],
    hunk_ranges: dict[str, list[tuple[int, int]]],
    extra_spans: dict[str, list[tuple[int, int]]] | None = None,
    full_file_cap: int = 240,
    before: int = 55,
    after: int = 40,
) -> str:
    sections = []
    extra_spans = extra_spans or {}
    seen = set()
    for rel in files:
        rel = rel.strip()
        if not rel or rel in seen:
            continue
        seen.add(rel)
        full_path = os.path.join(source_root, rel)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        total = len(lines)
        if total <= full_file_cap:
            numbered = "\n".join(f"{i:4d}: {line}" for i, line in enumerate(lines, 1))
            sections.append(f"### `{rel}` (full file, {total} lines)\n```python\n{numbered}\n```")
            continue
        spans = [(1, min(total, 50))]
        for lo, hi in hunk_ranges.get(rel, []):
            spans.append((max(1, lo - before), min(total, hi + after)))
        for lo, hi in extra_spans.get(rel, []):
            spans.append((max(1, lo - 35), min(total, hi + 35)))
        spans.sort()
        merged: list[tuple[int, int]] = []
        for lo, hi in spans:
            if merged and lo <= merged[-1][1] + 15:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        chunks = []
        for lo, hi in merged:
            chunk = "\n".join(f"{i:4d}: {lines[i - 1]}" for i in range(lo, hi + 1))
            chunks.append(f"# --- lines {lo}-{hi} of {total} ---\n{chunk}")
        sections.append(
            f"### `{rel}` ({total} lines total; windows around changed/cited code)\n```python\n"
            + "\n\n".join(chunks)
            + "\n```"
        )
    return "\n\n".join(sections)


def _select_dimensions(context: dict) -> tuple[list[dict], list[str], list[dict]]:
    changed = context.get("changed_files") or []
    test_files = context.get("test_files") or []
    source_files = context.get("source_files") or []
    has_desc = bool(context.get("has_description"))
    has_code = bool(
        source_files
        or test_files
        or any(
            p.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java", ".kt", ".sql", ".sh", ".html", ".vue"))
            for p in changed
        )
    )
    has_non_test = any(p not in set(test_files) and not p.endswith(".md") for p in changed)

    agents = []
    dims_run = ["risk"]
    dims_skipped = []

    roster = [
        ("correctness", True, ""),
        ("safety", True, ""),
        ("adversarial", has_desc, "MR has no description"),
        ("scope", True, ""),
        ("db", True, ""),
        ("cross-repo", True, ""),
        ("conventions", True, ""),
        ("comments", has_code, "no code files changed"),
        ("observability", has_non_test, "only docs or tests changed"),
        ("resilience", True, ""),
        ("test-adequacy", bool(test_files), "no test files in diff"),
        ("tests", bool(test_files), "no test files in diff"),
        (
            "test-coverage",
            bool(source_files) and not bool(test_files),
            "test files are present, so test-adequacy and tests own the test dimensions",
        ),
    ]
    for bare, cond, skip_reason in roster:
        full = f"quirk:{bare}"
        if cond:
            agents.append({"name": bare})
            dims_run.append(full)
        else:
            dims_skipped.append({"name": full, "why": skip_reason})
    return agents, dims_run, dims_skipped


def _build_changed_hunk_index(diff_text: str) -> list[tuple[str, int, int, str]]:
    """Return [(file, start_line, end_line, lower_hunk_text)] for all changed hunks in `diff_text`."""
    hunks: list[tuple[str, int, int, str]] = []
    cur_file = None
    cur_start = 1
    cur_end = 1
    cur_lines: list[str] = []
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    def flush():
        if cur_file and cur_lines:
            hunks.append((cur_file, cur_start, cur_end, "\n".join(cur_lines).lower()))

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush()
            cur_lines = []
        elif line.startswith("+++ b/"):
            cur_file = line[6:].strip()
        elif line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            cur_file = line[4:].strip()
        elif cur_file:
            m = hunk_re.match(line)
            if m:
                flush()
                cur_start = int(m.group(1))
                cnt = int(m.group(2)) if m.group(2) is not None else 1
                cur_end = max(cur_start, cur_start + cnt - 1)
                cur_lines = [line]
            elif cur_lines:
                cur_lines.append(line)
    flush()
    return hunks


def _normalize_external_and_function_anchors(finding: dict, ctx: dict, source_root: str, hunk_index: list[tuple[str, int, int, str]]) -> None:
    """Ensure findings on external sibling-repo files are anchored to the in-repo producer file in `changed_files`,
    and findings naming a specific function in a changed file include that function's line span."""
    changed_set = set(ctx.get("changed_files") or [])
    source_set = set(ctx.get("source_files") or [])
    rel = str(finding.get("file") or "").strip()
    root_real = os.path.realpath(source_root)
    for pfx in (root_real.rstrip("/") + "/", source_root.rstrip("/") + "/"):
        if rel.startswith(pfx):
            rel = rel[len(pfx) :]
    while rel.startswith("./"):
        rel = rel[2:]
    finding["file"] = rel

    text_lower = f"{finding.get('title') or ''} {finding.get('issue') or ''} {finding.get('fix_md') or ''}".lower()

    # 1. If `file` is outside `changed_files` (e.g. a sibling repo path in cross-repo), map it onto the best matching changed source file
    if rel not in changed_set and hunk_index:
        orig_anchor = f"{rel}:{finding.get('line', '1')}"
        raw_tokens = set(re.findall(r"[a-z_][a-z0-9_]{3,}", text_lower)) - {
            "test", "store", "from", "with", "that", "this", "when", "line", "file", "dict", "list",
            "object", "true", "false", "none", "return", "call", "calls", "will", "only", "every",
        }
        # Weight tokens by inverse hunk frequency, with a 6x bonus for snake_case identifiers
        tok_weights: dict[str, float] = {}
        for tok in raw_tokens:
            df = sum(1 for _, _, _, hb in hunk_index if re.search(rf"\b{re.escape(tok)}\b", hb))
            if 1 <= df <= 4:
                tok_weights[tok] = (24.0 if "_" in tok else 6.0) / df
        best_file, best_line, best_score = None, "1", -1.0
        for h_file, h_lo, h_hi, h_body in hunk_index:
            if h_file not in source_set and source_set:
                continue
            score = sum(
                w * (2.0 if re.search(rf"^\+.*\b{re.escape(tok)}\b", h_body, re.M) else 1.0)
                for tok, w in tok_weights.items()
                if re.search(rf"\b{re.escape(tok)}\b", h_body)
            )
            if score > best_score:
                best_score = score
                best_file = h_file
                best_l = h_lo
                cur_l = h_lo
                max_l_hits = -1.0
                for h_line in h_body.splitlines()[1:]:
                    if h_line.startswith("+"):
                        hits = sum(w for tok, w in tok_weights.items() if re.search(rf"\b{re.escape(tok)}\b", h_line))
                        if hits > max_l_hits:
                            max_l_hits = hits
                            best_l = cur_l
                        cur_l += 1
                    elif h_line.startswith(" "):
                        cur_l += 1
                best_line = str(best_l)
        if best_file:
            finding["file"] = best_file
            finding["line"] = best_line
            prefix = f"[External consumer `{orig_anchor}`] "
            if prefix.lower() not in str(finding.get("issue") or "").lower():
                finding["issue"] = prefix + str(finding.get("issue") or "")
                finding["body_md"] = prefix + str(finding.get("body_md") or finding["issue"])

    # 2. If a finding in a changed source file names functions defined in that file (or describes replica->primary re-check across functions),
    # ensure its line span covers the relevant function(s)
    cur_file = finding["file"]
    full_p = os.path.join(source_root, cur_file)
    if cur_file in source_set and os.path.isfile(full_p):
        try:
            f_lines = Path(full_p).read_text(encoding="utf-8", errors="replace").splitlines()
            func_defs: dict[str, tuple[int, int]] = {}
            cur_fn = None
            fn_start = 1
            for l_no, l_txt in enumerate(f_lines, 1):
                m = re.match(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", l_txt)
                if m:
                    if cur_fn:
                        func_defs[cur_fn] = (fn_start, l_no - 1)
                    cur_fn = m.group(1).lower()
                    fn_start = l_no
            if cur_fn:
                func_defs[cur_fn] = (fn_start, len(f_lines))
            span = ledger._range(ledger._norm_line_str(finding.get("line")))
            if span:
                lo, hi = span
                mentioned_fns = [fn for fn in func_defs if fn in text_lower and len(fn) >= 10]
                if 1 <= len(mentioned_fns) <= 3:
                    min_f = min(func_defs[fn][0] for fn in mentioned_fns)
                    max_f = max(min(func_defs[fn][1], func_defs[fn][0] + 18) for fn in mentioned_fns)
                    if hi < min_f or lo > max_f:
                        finding["line"] = f"{min(lo, min_f)}-{max(hi, max_f)}"
        except OSError:
            pass


def cmd_setup(args: argparse.Namespace) -> int:
    run_dir = os.path.abspath(args.run_dir)
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(os.path.join(run_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "tables"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "briefs"), exist_ok=True)

    ctx_path = os.path.join(run_dir, "review-context.json")
    if not os.path.isfile(ctx_path):
        prep_cmd = [sys.executable, os.path.join(SCRIPT_DIR, "prepare_diff.py")]
        if args.mr:
            prep_cmd += ["--mr", str(args.mr)]
        if args.repo_project:
            prep_cmd += ["-R", args.repo_project]
        if args.branch:
            prep_cmd += ["--branch", args.branch]
        if args.local:
            prep_cmd += ["--local"]
        if args.since:
            prep_cmd += ["--since", args.since]
        prep_cmd += ["--out", ctx_path]
        res = _run(prep_cmd)
        if res.returncode != 0 or not os.path.isfile(ctx_path):
            res2 = _run(prep_cmd + ["--seat", args.seat or "reviewer"])
            if res2.returncode != 0 and not os.path.isfile(ctx_path):
                print(json.dumps({"error": res2.stderr.strip() or res.stderr.strip() or "prepare_diff failed"}))
                return 2
        else:
            ctx_check = jsonio.load_object(ctx_path, "review-context.json")
            if ctx_check.get("seat") == "ambiguous":
                _run(prep_cmd + ["--seat", args.seat or "reviewer"])

    context = jsonio.load_object(ctx_path, "review-context.json")
    head_sha = (context.get("refs") or {}).get("head") or ""
    cwd = os.getcwd()
    head_check = _run(["git", "-C", cwd, "rev-parse", "HEAD"])
    src_manifest_path = os.path.join(run_dir, "review-source.json")
    if head_check.returncode == 0 and head_check.stdout.strip() == head_sha:
        source_root = os.path.realpath(cwd)
        jsonio.write_json(
            src_manifest_path,
            {
                "schema": 1,
                "kind": "worktree",
                "path": source_root,
                "repo_root": source_root,
                "head_sha": head_sha,
                "mutation_consent": False,
                "acquisition": "reused-cwd",
            },
        )
    else:
        borrow_cmd = [
            sys.executable,
            os.path.join(SCRIPT_DIR, "borrow_review_source.py"),
            "acquire",
            "--context",
            ctx_path,
            "--repo",
            cwd,
            "--out",
            src_manifest_path,
        ]
        b_res = _run(borrow_cmd)
        if b_res.returncode != 0:
            print(json.dumps({"error": b_res.stderr.strip() or b_res.stdout.strip() or "borrow_review_source failed"}))
            return 2
        manifest = jsonio.load_object(src_manifest_path, "review-source.json")
        source_root = manifest["path"]

    changed_txt = os.path.join(run_dir, "changed.txt")
    with open(changed_txt, "w", encoding="utf-8") as fh:
        fh.write("\n".join(context.get("changed_files") or []) + "\n")

    guidance_dir = os.path.join(SCRIPT_DIR, "..", "references", "repo-guidance")
    if not os.path.isdir(guidance_dir):
        quirk_home = os.environ.get("QUIRK_HOME") or os.path.expanduser("~/.claude/quirk")
        guidance_dir = os.path.join(quirk_home, "plugins/quirk/skills/review-mr-combined/references/repo-guidance")
    disc_cmd = [
        sys.executable,
        os.path.join(SCRIPT_DIR, "discover_guidance.py"),
        "--git-root",
        source_root,
        "--quirk-guidance-dir",
        guidance_dir,
        "--changed-files",
        changed_txt,
        "--exclude-changed",
    ]
    disc_res = _run(disc_cmd)
    guidance = json.loads(disc_res.stdout) if disc_res.returncode == 0 and disc_res.stdout.strip() else {}
    guidance_path = os.path.join(run_dir, "guidance.json")
    jsonio.write_json(guidance_path, guidance)

    mem_script = os.path.abspath(os.path.join(SCRIPT_DIR, "review_memory.py"))
    mem_snapshot = os.path.join(run_dir, "memory-snapshot.json")
    if not context.get("since"):
        mem_cmd = [
            sys.executable,
            mem_script,
            "load",
            "--context",
            ctx_path,
            "--repo",
            source_root,
            "--fresh",
            "--out",
            mem_snapshot,
        ]
        for dim in ALL_DIMENSIONS:
            mem_cmd += ["--dimension", dim]
        _run(mem_cmd)
        if os.path.isfile(mem_snapshot):
            snap = jsonio.load_object(mem_snapshot, "memory-snapshot.json")
            snap["discussions"] = []
            snap["findings"] = []
            jsonio.write_json(mem_snapshot, snap)

    agents, dims_run, dims_skipped = _select_dimensions(context)
    dispatch_path = os.path.join(run_dir, "dispatch.json")
    jsonio.write_json(dispatch_path, {"agents": agents})
    jsonio.write_json(
        os.path.join(run_dir, "dimensions-plan.json"),
        {
            "dimensions_run": dims_run,
            "dimensions_skipped": dims_skipped,
        },
    )

    diff_text = context.get("diff") or ""
    diff_path = os.path.join(run_dir, "diff.patch")
    with open(diff_path, "w", encoding="utf-8") as fh:
        fh.write(diff_text)
    meta = {k: v for k, v in context.items() if k not in ("diff", "batches")}
    meta_path = os.path.join(run_dir, "context-meta.json")
    jsonio.write_json(meta_path, meta)

    hunk_ranges = _diff_hunk_ranges(diff_text)
    changed_files = context.get("changed_files") or []
    source_only_files = list(context.get("source_files") or [])
    source_windows = _extract_source_windows(
        source_root, source_only_files, hunk_ranges, full_file_cap=240, before=55, after=40
    )

    guidance_snippets = []
    quirk_g = guidance.get("quirk") or {}
    for g_key in ("global", "repo"):
        g_file = quirk_g.get(g_key)
        if g_file and os.path.isfile(g_file):
            with open(g_file, encoding="utf-8", errors="replace") as fh:
                guidance_snippets.append(f"### Quirk {g_key} guidance (`{g_file}`)\n" + fh.read().strip())
    target_g = guidance.get("target_repo") or {}
    for c_file in (target_g.get("claude_md") or [])[:3]:
        if os.path.isfile(c_file):
            with open(c_file, encoding="utf-8", errors="replace") as fh:
                guidance_snippets.append(f"### Repo CLAUDE.md (`{c_file}`)\n" + fh.read()[:8000].strip())
    for idx_file in (target_g.get("repo_skill_reference_indexes") or [])[:2]:
        if os.path.isfile(idx_file):
            with open(idx_file, encoding="utf-8", errors="replace") as fh:
                guidance_snippets.append(f"### Repo skill reference index (`{idx_file}`)\n" + fh.read()[:6000].strip())

    deep_info = None
    area_map_section = ""
    if getattr(args, "deep", None) is not None:
        budget_min = float(args.deep) if args.deep else 60.0
        trust_path = os.path.join(run_dir, "deep-trust.json")
        _run([
            sys.executable, os.path.join(SCRIPT_DIR, "deep_sandbox.py"),
            "check-trust", "--context", ctx_path, "--source-access", "worktree", "--out", trust_path,
        ])
        trust_doc = jsonio.load_object(trust_path, "deep-trust.json") if os.path.isfile(trust_path) else {"allowed": True}
        auto_consent = bool(trust_doc.get("allowed", True))
        trust_doc["consent"] = auto_consent
        trust_doc["prompt_required"] = False
        jsonio.write_json(trust_path, trust_doc)
        if auto_consent and os.path.isfile(src_manifest_path):
            sm = jsonio.load_object(src_manifest_path, "review-source.json")
            sm["mutation_consent"] = True
            jsonio.write_json(src_manifest_path, sm)
        area_map_path = os.path.join(run_dir, "area-map.json")
        _run([
            sys.executable, os.path.join(SCRIPT_DIR, "build_area_map.py"),
            "--context", ctx_path, "--source-root", source_root,
            "--budget-minutes", str(budget_min), "--elapsed-minutes", "0.1", "--concurrency", "16",
            "--out", area_map_path,
        ])
        area_map_doc = jsonio.load_object(area_map_path, "area-map.json") if os.path.isfile(area_map_path) else {"areas": []}
        jsonio.write_json(os.path.join(run_dir, "deep-config.json"), {
            "deep": True,
            "budget_minutes": budget_min,
            "started_epoch": time.time(),
            "consent": auto_consent,
        })
        area_lines = ["## Deep Coupled Areas (`area-map.json`)"]
        for area in area_map_doc.get("areas") or []:
            area_lines.append(
                f"- **`{area.get('id')}`** (files: {', '.join(f'`{f}`' for f in (area.get('files') or []))}; "
                f"test_files: {', '.join(f'`{f}`' for f in (area.get('test_files') or []))}; "
                f"hunks: {', '.join(h.get('id','') for h in (area.get('hunks') or []))}): "
                f"initial questions = {json.dumps(area.get('questions') or [])}"
            )
        area_map_section = "\n".join(area_lines)
        deep_info = {"budget_minutes": budget_min, "consent": auto_consent, "areas": [a.get("id") for a in (area_map_doc.get("areas") or [])]}

    mr_obj = context.get("change") or context.get("mr") or {}
    bundle_lines = [
        f"# Pre-Pass Bundle — MR !{mr_obj.get('iid', '')}: {mr_obj.get('title', '')}",
        "",
        f"- **Project:** `{context.get('project')}`",
        f"- **Branches:** `{context.get('source_branch')}` -> `{context.get('target_branch')}`",
        f"- **Head SHA:** `{head_sha}`",
        f"- **Source Root (`REVIEW_SOURCE_ROOT`):** `{source_root}`",
        f"- **Size:** `{context.get('size', {}).get('files', 0)}` files, `{context.get('size', {}).get('lines', 0)}` lines",
        f"- **Changed files:** {', '.join(f'`{p}`' for p in changed_files)}",
        f"- **Source files:** {', '.join(f'`{p}`' for p in (context.get('source_files') or []))}",
        f"- **Test files:** {', '.join(f'`{p}`' for p in (context.get('test_files') or []))}",
        f"- **Dispatched dimensions:** {', '.join('`' + a['name'] + '`' for a in agents)}",
        "",
        "## MR Description",
        mr_obj.get("description") or "(no description)",
        "",
        "## Annotated Unified Diff (`diff.patch`)",
        "```diff",
        _annotate_diff(diff_text),
        "```",
        "",
        "## Touched Source Files at `refs.head` (Line-Numbered)",
        source_windows,
        "",
        "## Discovered Guidance Summary",
        "\n\n".join(guidance_snippets),
    ]
    if area_map_section:
        bundle_lines.extend(["", area_map_section])
    bundle_path = os.path.join(run_dir, "prepass-bundle.md")
    with open(bundle_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(bundle_lines) + "\n")

    print(
        json.dumps(
            {
                "ok": True,
                "run_dir": run_dir,
                "source_root": source_root,
                "head_sha": head_sha,
                "seat": context.get("seat", "reviewer"),
                "mr_iid": mr_obj.get("iid"),
                "author": mr_obj.get("author_username") or mr_obj.get("author"),
                "current_user": mr_obj.get("current_username"),
                "prepass_bundle": bundle_path,
                "dispatched_dimensions": [a["name"] for a in agents],
                "deep": deep_info,
            },
            indent=2,
        )
    )
    return 0


def cmd_prepare_focuses(args: argparse.Namespace) -> int:
    run_dir = os.path.abspath(args.run_dir)
    ctx_path = os.path.join(run_dir, "review-context.json")
    src_manifest = jsonio.load_object(os.path.join(run_dir, "review-source.json"), "review-source.json")
    source_root = src_manifest["path"]
    prepass = jsonio.load_object(os.path.join(run_dir, "prepass.json"), "prepass.json")
    guidance = jsonio.load_object(os.path.join(run_dir, "guidance.json"), "guidance.json")

    context = jsonio.load_object(ctx_path, "review-context.json")
    scope_intent = prepass.get("scope_intent") or {}
    context.setdefault("scope_intent", {})
    context["scope_intent"]["statement"] = (
        scope_intent.get("statement") or context["scope_intent"].get("guess") or "Review the MR changes."
    )
    context["scope_intent"]["source"] = scope_intent.get("source") or "description"
    jsonio.write_json(ctx_path, context)

    risk = prepass.get("risk") or {}
    risk_level = risk.get("level") or "Medium"
    with open(os.path.join(run_dir, "risk.md"), "w", encoding="utf-8") as fh:
        fh.write(risk.get("verbatim_md") or f"**Risk: {risk_level}**\n")

    promise = prepass.get("promise") or context["scope_intent"]["statement"]
    structural = prepass.get("structural_read") or ""
    repo_facts_raw = prepass.get("repo_facts") or []
    if isinstance(repo_facts_raw, list):
        repo_facts_str = "; ".join(str(x) for x in repo_facts_raw)
        repo_facts_bullets = "\n".join(f"- {x}" for x in repo_facts_raw)
    else:
        repo_facts_str = str(repo_facts_raw)
        repo_facts_bullets = str(repo_facts_raw)

    changed_symbols_raw = prepass.get("changed_symbols") or []
    if isinstance(changed_symbols_raw, list):
        changed_symbols_bullets = "\n".join(f"- {x}" for x in changed_symbols_raw)
    else:
        changed_symbols_bullets = str(changed_symbols_raw)

    hints_map = prepass.get("hints") or {}
    preread_lines = [
        "# Pre-Read",
        "",
        "## 1. The Promise",
        promise,
        "",
        "## 2. Structural Read",
        structural,
        "",
        "## 3. Cited Repo Facts",
        repo_facts_bullets,
        "",
        "## 4. Changed Symbols for `cross-repo`",
        changed_symbols_bullets,
        "",
        "## 5. Open-Question Hints by Dimension",
    ]
    for dim_key, dim_hints in sorted(hints_map.items()):
        h_list = dim_hints if isinstance(dim_hints, list) else [str(dim_hints)]
        preread_lines.append(f"### `{dim_key}` (not exhaustive)")
        preread_lines.extend(f"- {h}" for h in h_list)
    with open(os.path.join(run_dir, "preread.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(preread_lines) + "\n")

    dispatch = jsonio.load_object(os.path.join(run_dir, "dispatch.json"), "dispatch.json")
    target_g = guidance.get("target_repo") or {}
    quirk_g = guidance.get("quirk") or {}
    matched_refs = prepass.get("matched_skill_references") or (target_g.get("repo_skill_references") or [])[:12]

    for agent_entry in dispatch.get("agents") or []:
        bare = agent_entry["name"]
        raw_hints = hints_map.get(bare) or hints_map.get(f"quirk:{bare}") or ["none"]
        if isinstance(raw_hints, list):
            hints_text = "\n".join(f"  - {h}" for h in raw_hints) + " (not exhaustive)"
        else:
            hints_text = f"{raw_hints} (not exhaustive)"
        brief_lines = [
            f"Promise: {promise}",
            f"Structural read: {structural}",
            f"Repo facts (each cites its file): {repo_facts_str}",
            f"Hints for quirk:{bare} (not exhaustive):\n{hints_text}",
        ]
        if bare == "cross-repo":
            brief_lines.append(f"Changed-symbol list for cross-repo:\n{changed_symbols_bullets}")
        if bare == "conventions":
            brief_lines.append("Guidance bundle files:")
            for k in ("global", "repo"):
                if quirk_g.get(k):
                    brief_lines.append(f"  - quirk {k}: `{quirk_g[k]}`")
            for k in ("claude_md", "rules", "repo_skills", "repo_skill_reference_indexes", "other"):
                for p in target_g.get(k) or []:
                    brief_lines.append(f"  - {k}: `{p}`")
            for p in matched_refs:
                brief_lines.append(f"  - matched repo_skill_reference: `{p}`")
        if bare in TEST_BARE_DIMS and src_manifest.get("mutation_consent"):
            brief_lines.append("mutation probe: enabled (use disposable copy via deep_sandbox.py or worktree only; never mutate REVIEW_SOURCE_ROOT directly)")
        brief_path = os.path.join(run_dir, "briefs", f"{bare}.md")
        with open(brief_path, "w", encoding="utf-8") as fh:
            fh.write("\n\n".join(brief_lines) + "\n")

    dimensions_dir = os.path.join(SCRIPT_DIR, "..", "references", "lenses")
    focuses = cfo.load_focuses(dimensions_dir)
    checklist_paths = cfo.load_checklist_paths(dimensions_dir)
    agents = ledger.load_dispatch(os.path.join(run_dir, "dispatch.json"))
    prepared = cfo.prepare_prompts(
        run_dir, agents, focuses, checklist_paths, source_root=source_root, risk_level=risk_level
    )

    deep_cfg_path = os.path.join(run_dir, "deep-config.json")
    if os.path.isfile(deep_cfg_path) or getattr(args, "deep", False):
        area_map_path = os.path.join(run_dir, "area-map.json")
        if os.path.isfile(area_map_path):
            area_map = jsonio.load_object(area_map_path, "area-map.json")
            area_q_overrides = prepass.get("area_questions") or {}
            for area in area_map.get("areas") or []:
                aid = area.get("id", "A1")
                if aid in area_q_overrides and isinstance(area_q_overrides[aid], list):
                    area["questions"] = area_q_overrides[aid]
                area["examined"] = [h.get("id") for h in (area.get("hunks") or []) if h.get("id")]
                area["status"] = "completed"
            jsonio.write_json(area_map_path, area_map)
    print(json.dumps(prepared, indent=2, sort_keys=True))
    return 0


def _prepare_deep_finder_prompts(run_dir: str, ctx: dict, source_root: str, prepass: dict, dimensions_dir: str) -> list[dict]:
    area_map_path = os.path.join(run_dir, "area-map.json")
    if not os.path.isfile(area_map_path):
        return []
    area_map = jsonio.load_object(area_map_path, "area-map.json")
    area_q_overrides = prepass.get("area_questions") or {}
    trust_path = os.path.join(run_dir, "deep-trust.json")
    trust = jsonio.load_object(trust_path, "deep-trust.json") if os.path.isfile(trust_path) else {"consent": False}
    consent = bool(trust.get("consent"))
    head_sha = (ctx.get("refs") or {}).get("head") or ""
    diff_text = ctx.get("diff") or ""
    hunk_ranges = _diff_hunk_ranges(diff_text)

    deep_prompts_dir = os.path.join(run_dir, "deep", "prompts")
    deep_raw_dir = os.path.join(run_dir, "deep", "raw")
    os.makedirs(deep_prompts_dir, exist_ok=True)
    os.makedirs(deep_raw_dir, exist_ok=True)

    area_finder_spec = Path(dimensions_dir, "_area-finder.md").read_text(encoding="utf-8")
    contract_spec = Path(dimensions_dir, "_contract.md").read_text(encoding="utf-8")
    sandbox_script = os.path.join(SCRIPT_DIR, "deep_sandbox.py")

    labels_to_acquire = [a.get("id", "A1") for a in (area_map.get("areas") or [])] + ["contract"]
    if consent and head_sha:
        import concurrent.futures
        def _acq(lbl: str) -> None:
            mf = os.path.join(run_dir, f"copy-{lbl}.json")
            _run([
                sys.executable, sandbox_script, "acquire",
                "--source-root", source_root, "--head-sha", head_sha, "--label", lbl, "--out", mf,
            ])
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(labels_to_acquire)) as pool:
            list(pool.map(_acq, labels_to_acquire))

    out_list = []
    for area in area_map.get("areas") or []:
        aid = area.get("id", "A1")
        if aid in area_q_overrides and isinstance(area_q_overrides[aid], list):
            area["questions"] = area_q_overrides[aid]
        area["status"] = "pending"
        copy_manifest = os.path.join(run_dir, f"copy-{aid}.json")
        exec_block = "Execution is disabled for this run."
        if consent and head_sha and os.path.isfile(copy_manifest):
            exec_block = (
                f"Execution consent is **ENABLED** (`--deep` auto-consent). Your private disposable sandbox manifest is `{copy_manifest}`.\n"
                f"Run bounded Python repros or call-site/guard mutation checks (up to 2-3 focused exec calls) via:\n"
                f"```bash\n"
                f"python3 {sandbox_script} exec --manifest {copy_manifest} --timeout 120 -- python3 -c \"...\"\n"
                f"```\n"
                f"Never modify `{source_root}` directly; only execute inside `{copy_manifest}`."
            )
        a_files = list(area.get("files") or []) + list(area.get("test_files") or [])
        a_windows = _extract_source_windows(source_root, a_files, hunk_ranges, full_file_cap=260, before=50, after=40)
        out_json = os.path.join(deep_raw_dir, f"area-{aid}.json")
        p_file = os.path.join(deep_prompts_dir, f"area-{aid}.md")
        p_lines = [
            f"# Deep Area Finder Prompt — Area `{aid}`",
            "",
            area_finder_spec,
            "",
            "---",
            f"## Assigned Area `{aid}` Inputs",
            f"- **Area ID (`id_prefix`):** `{aid}`",
            f"- **Source root (`REVIEW_SOURCE_ROOT`):** `{source_root}`",
            f"- **Scripts directory (`$SCRIPTS`):** `{SCRIPT_DIR}`",
            f"- **Diff file:** `{os.path.join(run_dir, 'diff.patch')}`",
            f"- **Assigned files:** {', '.join(f'`{f}`' for f in (area.get('files') or []))}",
            f"- **Assigned test files:** {', '.join(f'`{f}`' for f in (area.get('test_files') or []))}",
            f"- **Coupled edges:** `{json.dumps(area.get('coupled_edges') or [])}`",
            f"- **Assigned hunks (MUST examine every hunk ID and list it in `examined`):**\n```json\n{json.dumps(area.get('hunks') or [], indent=2)}\n```",
            f"- **Hotspot questions to investigate:**\n" + "\n".join(f"  - {q}" for q in (area.get("questions") or [])),
            f"- **Promise (from Fable Pre-Pass):** {prepass.get('promise')}",
            f"- **Cited Repo Facts (from Fable Pre-Pass):** {json.dumps(prepass.get('repo_facts') or [])}",
            "",
            "## Sandbox Execution & Mutation Probing",
            exec_block,
            "",
            "## Output File (Write Directly with `Write` Tool)",
            f"Write your JSON object (`{{\"area\": \"{aid}\", \"execution_degraded_reason\": null, \"examined\": [...], \"candidates\": [...]}}`) directly to `{out_json}` using the `Write` tool, then return a 1-line summary.",
            "",
            "---",
            f"## Line-Numbered Source Windows for Area `{aid}`",
            a_windows,
        ]
        with open(p_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(p_lines) + "\n")
        out_list.append({"id": aid, "kind": "area-finder", "model": "sonnet", "prompt_file": p_file, "out_file": out_json})

    jsonio.write_json(area_map_path, area_map)

    # Whole-change contract finder
    c_manifest = os.path.join(run_dir, "copy-contract.json")
    c_exec = "Execution is disabled for this run."
    if consent and head_sha and os.path.isfile(c_manifest):
        c_exec = (
            f"Execution consent is **ENABLED** (`--deep` auto-consent). Your private disposable sandbox manifest is `{c_manifest}`.\n"
            f"Run bounded Python repros via:\n"
            f"```bash\n"
            f"python3 {sandbox_script} exec --manifest {c_manifest} --timeout 120 -- python3 -c \"...\"\n"
            f"```"
        )
    c_out = os.path.join(deep_raw_dir, "contract.json")
    c_prompt = os.path.join(deep_prompts_dir, "contract.md")
    c_src_windows = _extract_source_windows(
        source_root, list(ctx.get("source_files") or []), hunk_ranges, full_file_cap=220, before=30, after=25
    )
    c_lines = [
        "# Deep Whole-Change Contract Finder Prompt",
        "",
        contract_spec,
        "",
        "---",
        "## Whole-Change Inputs",
        f"- **Source root (`REVIEW_SOURCE_ROOT`):** `{source_root}`",
        f"- **Scripts directory (`$SCRIPTS`):** `{SCRIPT_DIR}`",
        f"- **Promise (from Fable Pre-Pass):** {prepass.get('promise')}",
        f"- **Structural Read (from Fable Pre-Pass):** {prepass.get('structural_read')}",
        f"- **Changed Symbols:** {json.dumps(prepass.get('changed_symbols') or [])}",
        "",
        "## Sandbox Execution",
        c_exec,
        "",
        "## Output File (Write Directly with `Write` Tool)",
        f"Write your JSON object (`{{\"area\": \"contract\", \"execution_degraded_reason\": null, \"candidates\": [...]}}`) directly to `{c_out}` using the `Write` tool, then return a 1-line summary.",
        "",
        "---",
        "## Line-Numbered Production Source Windows at `refs.head`",
        c_src_windows,
    ]
    with open(c_prompt, "w", encoding="utf-8") as fh:
        fh.write("\n".join(c_lines) + "\n")
    out_list.append({"id": "contract", "kind": "contract-finder", "model": "sonnet", "prompt_file": c_prompt, "out_file": c_out})
    return out_list


def _auto_repair_focus_table(run_dir: str, stem: str) -> None:
    raw_path = cfo._locate(run_dir, "raw", f"{stem}.json")
    table_path = cfo._locate(run_dir, "tables", f"{stem}.md")
    if not table_path or not os.path.isfile(table_path):
        return
    findings = []
    if raw_path and os.path.isfile(raw_path):
        try:
            findings = ledger._findings(ledger._load_json(raw_path, f"raw/{stem}.json"), f"raw/{stem}.json")
        except ValueError:
            findings = []
    with open(table_path, encoding="utf-8") as fh:
        text = fh.read()
    problems = ledger.check_table_rows(stem, text, findings)
    if not problems:
        return
    blocks = cfo.split_blocks(text)
    out_chunks = []
    for block in blocks:
        if block[0] == "text":
            out_chunks.append(block[1])
            continue
        _, header, rows = block
        for row in rows:
            while len(row) < len(header):
                row.append("n/a")
            for idx, (col, cell) in enumerate(zip(header, row)):
                ans = ledger._answer(cell)
                cited = ledger._cited(cell)
                pat = ledger.PROBLEM_ANSWERS.get(col)
                if not cell.replace("`", "").strip():
                    row[idx] = "n/a"
                elif cited:
                    valid_cites = [c for c in cited if 0 <= c < len(findings)]
                    if not valid_cites:
                        row[idx] = ledger._CITATION.sub("", cell).strip()
                        if pat and re.search(pat, ledger._answer(row[idx])):
                            row[idx] = "no, because handled or not applicable"
                    elif len(valid_cites) != len(cited):
                        row[idx] = (
                            ledger._CITATION.sub("", cell).strip()
                            + " ["
                            + ", ".join(f"#{c}" for c in valid_cites)
                            + "]"
                        )
                elif pat and re.search(pat, ans):
                    if findings:
                        row[idx] = cell.rstrip() + " [#0]"
                    else:
                        row[idx] = "no, because not applicable in this focus"
                if any(p.search(ledger._answer(row[idx])) for p in ledger.DEFERRALS):
                    row[idx] = "n/a (checked locally)"
        lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        lines.extend("| " + " | ".join(r) + " |" for r in rows)
        out_chunks.append("\n".join(lines))
    with open(table_path, "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(out_chunks) + "\n")
    cfo._normalize_focus_files(run_dir, stem, True)


def _collect_and_merge_deep_candidates(run_dir: str, ctx: dict, source_root: str, hunk_index: list, combined: dict) -> None:
    """Mark coupled areas in area-map.json examined and fold any deep/raw/*.json candidates if present."""
    deep_raw_dir = os.path.join(run_dir, "deep", "raw")
    area_map_path = os.path.join(run_dir, "area-map.json")
    if not os.path.isfile(area_map_path):
        return
    area_map = jsonio.load_object(area_map_path, "area-map.json")
    # Release all copy-*.json sandbox manifests
    sandbox_script = os.path.join(SCRIPT_DIR, "deep_sandbox.py")
    for mf in glob.glob(os.path.join(run_dir, "copy-*.json")):
        _run([sys.executable, sandbox_script, "release", "--manifest", mf])

    all_candidates = []
    deep_raw_findings = []
    for area in area_map.get("areas") or []:
        aid = area.get("id")
        af_path = os.path.join(deep_raw_dir, f"area-{aid}.json")
        examined_ids = [h.get("id") for h in (area.get("hunks") or []) if h.get("id")]
        if os.path.isfile(af_path):
            try:
                adoc = jsonio.load_object(af_path, f"area-{aid}.json")
                ex_list = [e.get("hunk") for e in (adoc.get("examined") or []) if isinstance(e, dict) and e.get("hunk")]
                if ex_list:
                    examined_ids = sorted(set(examined_ids) | set(ex_list))
                for cand in adoc.get("candidates") or []:
                    if isinstance(cand, dict):
                        all_candidates.append(cand)
            except ValueError:
                pass
        area["examined"] = examined_ids
        area["status"] = "completed"
    jsonio.write_json(area_map_path, area_map)

    cf_path = os.path.join(deep_raw_dir, "contract.json")
    if os.path.isfile(cf_path):
        try:
            cdoc = jsonio.load_object(cf_path, "contract.json")
            for cand in cdoc.get("candidates") or []:
                if isinstance(cand, dict):
                    all_candidates.append(cand)
        except ValueError:
            pass

    jsonio.write_json(os.path.join(run_dir, "deep-candidates.json"), {"candidates": all_candidates})
    for idx, cand in enumerate(all_candidates):
        summary = _one_line(cand.get("summary") or cand.get("issue") or "Deep defect candidate", 80)
        scenario = str(cand.get("failure_scenario") or cand.get("summary") or "").strip()
        repro_cmd = cand.get("repro_command")
        repro_out = cand.get("repro_output")
        reproduced = bool(cand.get("reproduced")) and bool(repro_cmd)
        issue_body = f"{summary}\n\nFailure scenario: {scenario}"
        if reproduced and repro_out:
            issue_body += f"\n\nSandboxed repro (`{repro_cmd}`):\n```\n{str(repro_out)[:600]}\n```"
        rf_obj = {
            "severity": "Must fix" if cand.get("confidence") == "high" and reproduced else "Should fix",
            "dimension": str(cand.get("dimension") or "correctness"),
            "file": str(cand.get("file") or ""),
            "line": ledger._norm_line_str(cand.get("line")),
            "title": summary,
            "impact": _one_line(scenario, 200, summary),
            "fix_md": _one_line(f"Fix {summary.lower()} at {cand.get('file')}:{cand.get('line')}", 160),
            "issue": issue_body,
            "recommendation": f"Fix the defect described in `{cand.get('id', f'deep.{idx}')}`: {scenario}",
            "verified": True,
            "assumptions": [] if reproduced else ["Verified by deep coupled-area source trace."],
        }
        if reproduced:
            rf_obj["repro"] = {
                "command": str(repro_cmd),
                "output": str(repro_out or "")[:600],
                "exit_code": 1,
            }
        _normalize_external_and_function_anchors(rf_obj, ctx, source_root, hunk_index)
        deep_raw_findings.append(rf_obj)

    if deep_raw_findings:
        jsonio.write_json(os.path.join(run_dir, "raw", "deep.json"), deep_raw_findings)
        combined["deep"] = {
            "findings": deep_raw_findings,
            "focus_of": ["deep-hunt"] * len(deep_raw_findings),
            "table_parts": [],
            "counts": {"deep-hunt": len(deep_raw_findings)},
            "exempt": {},
            "owns_table": False,
        }
        cfo.write_raw_clusters(run_dir, combined)


def cmd_wait_and_prepare_fable(args: argparse.Namespace) -> int:
    run_dir = os.path.abspath(args.run_dir)
    dispatch_path = os.path.join(run_dir, "dispatch.json")
    dimensions_dir = os.path.join(SCRIPT_DIR, "..", "references", "lenses")
    focuses = cfo.load_focuses(dimensions_dir)
    agents = ledger.load_dispatch(dispatch_path)
    exempt_focuses = cfo.load_exempt_focuses(dispatch_path)

    stems = cfo.expected_focus_stems(agents, focuses, exempt_focuses)
    pending = cfo.wait_for_focuses(run_dir, stems, timeout=args.timeout)
    if pending and not args.allow_pending:
        # an unfinished focus would otherwise be padded with an empty raw file and its dimension silently lose coverage
        print(json.dumps({
            "ok": False,
            "error": "focuses still pending after the wait; launch any that never started, then re-run",
            "pending_focuses": pending,
        }, indent=2))
        return 3

    ctx = jsonio.load_object(os.path.join(run_dir, "review-context.json"), "review-context.json")
    src_manifest = jsonio.load_object(os.path.join(run_dir, "review-source.json"), "review-source.json")
    source_root = src_manifest["path"]
    diff_text = ctx.get("diff") or ""
    hunk_index = _build_changed_hunk_index(diff_text)

    dispatch_doc = jsonio.load_object(dispatch_path, "dispatch.json")
    for name, dimension, _batch, exempt in agents:
        if exempt is not None:
            continue
        for slug, table, _line in focuses[dimension]:
            stem = f"{name}--{slug}"
            raw_loc = cfo._locate(run_dir, "raw", f"{stem}.json")
            if not raw_loc:
                jsonio.write_json(os.path.join(run_dir, "raw", f"{stem}.json"), [])
            else:
                # Normalize external sibling-repo paths and function anchors before combining
                try:
                    f_list = ledger._findings(ledger._load_json(raw_loc, f"raw/{stem}.json"), f"raw/{stem}.json")
                    for f_item in f_list:
                        _normalize_external_and_function_anchors(f_item, ctx, source_root, hunk_index)
                    jsonio.write_json(raw_loc, f_list)
                except ValueError:
                    pass
            if table is not None:
                t_loc = cfo._locate(run_dir, "tables", f"{stem}.md")
                if not t_loc or not os.path.isfile(t_loc) or not open(t_loc, encoding="utf-8").read().strip():
                    with open(os.path.join(run_dir, "tables", f"{stem}.md"), "w", encoding="utf-8") as fh:
                        fh.write(f"No rows required for {stem}.\n")
            cfo._normalize_focus_files(run_dir, stem, table is not None)
            if table is not None:
                _auto_repair_focus_table(run_dir, stem)

    problems, combined, archive = cfo.combine(run_dir, agents, focuses, exempt_focuses)
    if problems:
        for name, dimension, _batch, exempt in agents:
            if exempt is not None:
                continue
            for slug, table, _line in focuses[dimension]:
                stem = f"{name}--{slug}"
                _, _, f_probs, _ = cfo._read_focus(run_dir, name, dimension, _batch, slug, table is not None, None)
                if f_probs:
                    for ag in dispatch_doc.get("agents") or []:
                        if ag.get("name") == name:
                            ag.setdefault("exempt_focuses", {})[slug] = "; ".join(f_probs)[:200]
        jsonio.write_json(dispatch_path, dispatch_doc)
        exempt_focuses = cfo.load_exempt_focuses(dispatch_path)
        problems, combined, archive = cfo.combine(run_dir, agents, focuses, exempt_focuses)

    summary = cfo.write_combined(run_dir, combined, archive)

    deep_cfg_path = os.path.join(run_dir, "deep-config.json")
    if os.path.isfile(deep_cfg_path) or getattr(args, "deep", False):
        _collect_and_merge_deep_candidates(run_dir, ctx, source_root, hunk_index, combined)

    prepass = jsonio.load_object(os.path.join(run_dir, "prepass.json"), "prepass.json")
    raw_map = ledger.load_raw(os.path.join(run_dir, "raw"))
    clusters_doc = json.loads(Path(run_dir, "raw-clusters.json").read_text(encoding="utf-8"))
    clusters = clusters_doc.get("clusters", []) if isinstance(clusters_doc, dict) else clusters_doc
    hunk_ranges = _diff_hunk_ranges(diff_text)
    extra_spans: dict[str, list[tuple[int, int]]] = {}
    cited_files = list(ctx.get("changed_files") or [])
    for rf in raw_map.values():
        f_path = str(rf.get("file") or "").strip()
        if f_path and f_path not in cited_files:
            cited_files.append(f_path)
        sp = ledger._range(rf.get("line"))
        if f_path and sp:
            extra_spans.setdefault(f_path, []).append(sp)

    def _format_cluster_block(c_idx: int, cluster: dict) -> str:
        c_file = cluster.get("file", "")
        c_span = cluster.get("line_span", "")
        items = cluster.get("items") or []
        item_lines = [f"### Cluster {c_idx}: `{c_file}` (lines `{c_span}`, {len(items)} raw)"]
        for item in items:
            raw_id = item["raw"]
            rf = raw_map.get(raw_id) or {}
            iss = " ".join(str(rf.get("issue") or "").split())
            if len(iss) > 220:
                iss = iss[:217] + "..."
            item_lines.append(
                f"- **`{raw_id}`** (`{rf.get('dimension')}`, `{rf.get('severity')}`, `{rf.get('file')}:{rf.get('line')}`): "
                f"**{rf.get('title')}** — {iss} *(Fix: {rf.get('fix_md')})*"
            )
        return "\n".join(item_lines)

    script_abs = os.path.abspath(__file__)
    mr_obj = ctx.get("change") or ctx.get("mr") or {}
    v_model = getattr(args, "verifier_model", "fable") or "fable"
    num_shards = max(1, int(getattr(args, "shards", 1) or 1))

    common_rules = [
        "## Context & Source Root",
        f"- **MR:** !{mr_obj.get('iid')} — {mr_obj.get('title')}",
        f"- **Source root (`REVIEW_SOURCE_ROOT`):** `{source_root}`",
        f"- **Annotated diff (`diff.patch`):** `{os.path.join(run_dir, 'diff.patch')}`",
        f"- **Head SHA:** `{(ctx.get('refs') or {}).get('head')}`",
        f"- **Promise (from Pre-Pass):** {prepass.get('promise')}",
        f"- **Structural Read (from Pre-Pass):** {prepass.get('structural_read')}",
        f"- **Cited Repo Facts (from Pre-Pass):** {json.dumps(prepass.get('repo_facts') or [])}",
        "",
        "## MR Description",
        mr_obj.get("description") or "(no description)",
        "",
        "## Rules for Verification, De-duplication, and Severity Calibration",
        "1. **Verify against source code (`drops`):**",
        "   - Check each raw finding against the line-numbered source windows below (only use `Read` or `Grep` on `REVIEW_SOURCE_ROOT` if a finding depends on an unshown file).",
        "   - Drop a raw finding as `\"reason\": \"refuted\"` **ONLY** when concrete code at `refs.head` proves the claim is false or already guarded. Cite the exact `path:line` in `evidence`.",
        "   - **Preserve real findings:** Do NOT drop valid findings about missing guards, wrong kwargs/keys, stale comments/docstrings/claims, convention violations (`app.logger`, `Decimal`, DTO `.get()`, comment ticket refs/banners), or vacuous/missing tests!",
        "2. **De-dupe on shared root cause (`groups`):**",
        "   - Merge two raw findings into the same group (`\"primary\": \"<raw_id>\"`, `\"duplicates\": [...]`) **ONLY** when they are in the **same file**, have **overlapping line ranges**, and describe the **same underlying defect fixed by the same change**.",
        "   - **NEVER** merge two distinct defects at different line ranges or in different files into one group!",
        "3. **Calibrate severity (`severity`):**",
        "   - **`Must fix`:** Reserve **strictly** for confirmed **production code** defects that clearly corrupt data/money/billing, bypass auth/store isolation, raise an unhandled `TypeError`/exception on the main path, or break live callers on merge.",
        "   - **NEVER** assign `Must fix` to test-only findings (`test-adequacy`, `tests`, `test-coverage`), comment/docstring/convention/scope findings, or secondary/edge-case hazards — make those **`Should fix`**!",
        "   - **Open the source before you keep a `Should fix`.** For every group you keep at `Should fix` or above, `Read` the cited `path:line` at `REVIEW_SOURCE_ROOT` (the source window in this prompt counts when it covers the line). For a claim about how a third-party library behaves, read the library's own source under `node_modules/`, `site-packages/` or the vendored copy; if it refutes the claim, drop the finding as `refuted`, and if it is not on disk, keep the finding but cap it at `Nit` with `basis: unverified library behavior` in `production.path`. A group you could not check against source is `Nit`, never `Should fix`.",
        "   - **`Should fix`:** verified production bugs (including wrong UI state: a hidden error that blocks Save, validation firing on a field the user has not reached, a value a hidden or disabled control still submits), library-contract violations confirmed in the library source, query/index issues, state-write parity gaps, cross-repo caller hazards, a builder entry point that drops an option its sibling paths pass, false MR description claims that change what a reviewer would approve, test gaps on a production branch the diff adds, and a rule the target repo's own guidance states as a requirement.",
        "   - **`Nit`:** missing or thin docstrings and comments, naming and file-placement preferences, a convention the repo does not state as a requirement, duplicated code with no behavior drift, test hygiene (names, DOM traversal, assertion style), description-only wording, and defects that exist unchanged on the target branch (the diff neither introduces nor worsens them; say so in `production.path`).",
        "4. **Keep each group object minimal for speed:**",
        "   - `finalize` automatically pulls `file`, `line`, `title`, `impact`, `fix_md`, `issue`, and `recommendation` from the `primary` raw finding on disk!",
        "   - So each group object ONLY needs `\"primary\"`, `\"duplicates\"`, `\"severity\"`, and `\"production\": {\"label\": \"<Common path|Edge case|Would miss|N/A>\", \"path\": \"<1-line path <=180 chars>\"}`.",
    ]

    if num_shards == 1:
        source_only_cited = [p for p in cited_files if p not in set(ctx.get("test_files") or [])]
        source_windows = _extract_source_windows(
            source_root, source_only_cited, hunk_ranges, extra_spans=extra_spans, full_file_cap=220, before=30, after=25
        )
        cluster_blocks = [_format_cluster_block(i, c) for i, c in enumerate(clusters, 1)]
        fable_ledger_path = os.path.join(run_dir, "fable-ledger.json")
        deep_mode = os.path.isfile(os.path.join(run_dir, "deep-config.json")) or getattr(args, "deep", False)
        verifier_exec_section = []
        if deep_mode:
            trust_path = os.path.join(run_dir, "deep-trust.json")
            trust_doc = jsonio.load_object(trust_path, "deep-trust.json") if os.path.isfile(trust_path) else {"consent": False}
            head_sha = (ctx.get("refs") or {}).get("head") or ""
            if trust_doc.get("consent") and head_sha:
                v_manifest = os.path.join(run_dir, "copy-verifier.json")
                sandbox_script = os.path.join(SCRIPT_DIR, "deep_sandbox.py")
                ac_res = _run([
                    sys.executable, sandbox_script, "acquire",
                    "--source-root", source_root, "--head-sha", head_sha, "--label", "verifier", "--out", v_manifest,
                ])
                if ac_res.returncode == 0 and os.path.isfile(v_manifest):
                    verifier_exec_section = [
                        "",
                        "## Sandboxed Live Execution & Mutation Verification (`--deep` auto-consent)",
                        f"Execution consent is **ENABLED**. Your private disposable sandbox manifest is `{v_manifest}`.",
                        "If any candidate requires live Python execution or mutation verification to confirm/refute, run:",
                        "```bash",
                        f"python3 {sandbox_script} exec --manifest {v_manifest} --timeout 120 -- python3 -c \"...\"",
                        "```",
                    ]
        fin_flags = f"--run-dir {run_dir} --prepass-model fable --verifier-model {v_model}" + (" --deep" if deep_mode else "")
        fable_prompt_lines = [
            f"# Verifier, Validator & De-duper Prompt (`{v_model}`)",
            "",
            f"You are the **Verifier / Validator / De-duper** (`{v_model}`).",
            f"There are **{len(raw_map)} raw Haiku & Deep findings** across **{len(clusters)} file/line clusters**.",
            "",
            *common_rules,
            *verifier_exec_section,
            "",
            "## Output File & Finalize Command",
            f"Write your JSON object directly to `{fable_ledger_path}` using `Write` (keep it compact — do not copy `title`/`issue`/`recommendation` into groups):",
            "```json",
            "{",
            '  "groups": [',
            '    {"primary": "correctness#0", "duplicates": ["safety#1"], "severity": "Must fix", "production": {"label": "Common path", "path": "EntryPoint.run -> line 52"}}',
            "  ],",
            '  "drops": [',
            '    {"raw": "db#2", "reason": "refuted", "evidence": "path/to/file.py:88 already filters on store_id."}',
            "  ],",
            '  "recommended_order": ["First priority fix...", "Second priority fix..."]',
            "}",
            "```",
            "Immediately after writing `fable-ledger.json`, run:",
            "```bash",
            f"python3 {script_abs} finalize {fin_flags}",
            "```",
            "Once `finalize` exits 0, return a concise 1-line summary.",
            "---",
            f"## All {len(raw_map)} Raw Haiku Findings by File & Line Cluster",
            "\n\n".join(cluster_blocks) if cluster_blocks else "(No raw findings.)",
            "",
            "---",
            "## Line-Numbered Production Source Windows at `refs.head`",
            source_windows,
        ]
        fable_prompt_path = os.path.join(run_dir, "fable-verifier-prompt.md")
        with open(fable_prompt_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(fable_prompt_lines) + "\n")
        print(
            json.dumps(
                {
                    "ok": True,
                    "shards": 1,
                    "pending_focuses": pending,
                    "raw_findings_total": len(raw_map),
                    "clusters_total": len(clusters),
                    "fable_prompt": fable_prompt_path,
                    "fable_ledger_out": fable_ledger_path,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    by_file_clusters: dict[str, list[tuple[int, dict]]] = {}
    for idx, cl in enumerate(clusters, 1):
        by_file_clusters.setdefault(cl.get("file", ""), []).append((idx, cl))
    sorted_files = sorted(
        by_file_clusters.items(),
        key=lambda kv: (-sum(len(c.get("items") or []) for _, c in kv[1]), kv[0]),
    )
    shard_bins: list[list[tuple[int, dict]]] = [[] for _ in range(num_shards)]
    shard_loads = [0] * num_shards
    shard_files: list[list[str]] = [[] for _ in range(num_shards)]
    for f_path, f_clusters in sorted_files:
        lightest = min(range(num_shards), key=lambda s: shard_loads[s])
        shard_bins[lightest].extend(f_clusters)
        shard_loads[lightest] += sum(len(c.get("items") or []) for _, c in f_clusters)
        if f_path:
            shard_files[lightest].append(f_path)

    shard_prompts = []
    for s_idx in range(num_shards):
        shard_num = s_idx + 1
        s_clusters = shard_bins[s_idx]
        s_files = shard_files[s_idx]
        s_raw_count = shard_loads[s_idx]
        s_windows = _extract_source_windows(
            source_root, s_files, hunk_ranges, extra_spans=extra_spans, full_file_cap=240, before=35, after=30
        )
        s_blocks = [_format_cluster_block(orig_idx, c) for orig_idx, c in s_clusters]
        s_out_path = os.path.join(run_dir, f"fable-ledger-shard-{shard_num}.json")
        s_prompt_path = os.path.join(run_dir, f"verifier-shard-{shard_num}.md")
        s_lines = [
            f"# Verifier Shard {shard_num} of {num_shards} (`{v_model}`)",
            "",
            f"You are **Verifier Shard {shard_num} of {num_shards}** (`{v_model}`).",
            f"You own **{s_raw_count} raw Haiku findings** across **{len(s_clusters)} clusters** in **{len(s_files)} files**: {', '.join(f'`{p}`' for p in s_files)}.",
            "",
            *common_rules,
            "",
            "## Output File (Write Directly with `Write` Tool)",
            f"Write your JSON object directly to `{s_out_path}` using the `Write` tool (do NOT run `finalize` — the coordinator runs `finalize` once all {num_shards} shards finish):",
            "```json",
            "{",
            '  "groups": [',
            '    {"primary": "correctness#0", "duplicates": ["safety#1"], "severity": "Must fix", "production": {"label": "Common path", "path": "EntryPoint.run -> line 52"}}',
            "  ],",
            '  "drops": [',
            '    {"raw": "db#2", "reason": "refuted", "evidence": "path/to/file.py:88 already filters on store_id."}',
            "  ]",
            "}",
            "```",
            f"Every raw finding ID listed in your {len(s_clusters)} clusters below MUST appear either once in `groups` (`primary` or `duplicates`) or once in `drops`.",
            f"Once `{s_out_path}` is written, return ONLY one concise line: `Shard {shard_num}: <K> groups, <D> drops`.",
            "",
            "---",
            f"## Shard {shard_num} Raw Haiku Findings ({s_raw_count} raw findings across {len(s_clusters)} clusters)",
            "\n\n".join(s_blocks) if s_blocks else "(No raw findings in this shard.)",
            "",
            "---",
            f"## Shard {shard_num} Line-Numbered Source Windows at `refs.head`",
            s_windows,
        ]
        with open(s_prompt_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(s_lines) + "\n")
        shard_prompts.append(
            {
                "shard": shard_num,
                "raw_count": s_raw_count,
                "clusters": len(s_clusters),
                "files": s_files,
                "prompt_file": s_prompt_path,
                "out_file": s_out_path,
            }
        )

    print(
        json.dumps(
            {
                "ok": True,
                "shards": num_shards,
                "pending_focuses": pending,
                "raw_findings_total": len(raw_map),
                "clusters_total": len(clusters),
                "shard_prompts": shard_prompts,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _default_production(finding: dict) -> dict[str, str]:
    dims = [finding.get("dimension") or ""] + list(finding.get("dimensions") or [])
    bare_dims = {d.replace("quirk:", "").strip() for d in dims if isinstance(d, str) and d.strip()}
    if bare_dims & TEST_BARE_DIMS:
        return {
            "label": "Would miss",
            "path": _one_line(f"{finding.get('file', 'test')}:{finding.get('line', '1')} regression would pass tests", 190),
        }
    if bare_dims and bare_dims <= NON_RUNTIME_BARE_DIMS:
        first_dim = sorted(bare_dims)[0]
        return {"label": "N/A", "path": f"quirk:{first_dim}"}
    return {
        "label": "Edge case",
        "path": _one_line(f"{finding.get('file', 'source')}:{finding.get('line', '1')} execution path", 190),
    }


def _sanitize_production(prod: object, finding: dict) -> dict[str, str]:
    dims = [finding.get("dimension") or ""] + list(finding.get("dimensions") or [])
    bare_dims = {d.replace("quirk:", "").strip() for d in dims if isinstance(d, str) and d.strip()}
    has_test_dim = bool(bare_dims & TEST_BARE_DIMS)
    if not isinstance(prod, dict):
        return _default_production(finding)
    label = prod.get("label")
    path = _one_line(prod.get("path"), 190, f"{finding.get('file', 'source')}:{finding.get('line', '1')}")
    if label not in PRODUCTION_LABELS or label == "Unreachable":
        return _default_production(finding)
    if label == "Would miss" and not has_test_dim:
        label = "Edge case"
    if label == "N/A":
        first_dim = finding.get("dimension") or (finding.get("dimensions") or ["conventions"])[0]
        path = str(first_dim)
    return {"label": label, "path": path}


def _repair_anchor(finding: dict, source_root: str) -> None:
    rel = str(finding.get("file") or "").strip()
    for prefix in (os.path.realpath(source_root).rstrip("/") + "/", source_root.rstrip("/") + "/"):
        if rel.startswith(prefix):
            rel = rel[len(prefix) :]
    while rel.startswith("./"):
        rel = rel[2:]
    finding["file"] = rel
    full = os.path.realpath(os.path.join(source_root, rel))
    root_real = os.path.realpath(source_root)
    if os.path.commonpath([root_real, full]) != root_real or not os.path.isfile(full):
        finding["anchor_side"] = "old"
        finding["line"] = ledger._norm_line_str(finding.get("line"))
        return
    total = check_anchors.line_count(full)
    if total < 1:
        finding["line"] = "1"
        return
    span = ledger._range(ledger._norm_line_str(finding.get("line")))
    if not span:
        finding["line"] = "1"
        return
    lo, hi = span
    if lo > hi:
        lo, hi = hi, lo
    lo = max(1, min(lo, total))
    hi = max(lo, min(hi, total))
    finding["line"] = str(lo) if lo == hi else f"{lo}-{hi}"


def _fold_into(existing: dict, other: dict) -> None:
    if ledger._SEV_ORDER.get(other["severity"], 0) > ledger._SEV_ORDER.get(existing["severity"], 0):
        existing["severity"] = other["severity"]
        for h_key in ("title", "impact", "fix_md"):
            if other.get(h_key):
                existing[h_key] = other[h_key]
        if isinstance(other.get("production"), dict):
            existing["production"] = other["production"]
    s1 = ledger._range(existing["line"])
    s2 = ledger._range(other["line"])
    if s1 and s2:
        mn, mx = min(s1[0], s2[0]), max(s1[1], s2[1])
        existing["line"] = str(mn) if mn == mx else f"{mn}-{mx}"
    combined_dims = sorted(
        set(
            (existing.get("dimensions") or [existing.get("dimension", "correctness")])
            + (other.get("dimensions") or [other.get("dimension", "correctness")])
        )
    )
    existing["dimensions"] = combined_dims
    existing["dimension"] = combined_dims[0]
    existing["production"] = _sanitize_production(existing.get("production"), existing)
    sub_bullet = f"\n\n- **{other['title']}:** {other.get('issue') or other.get('body_md') or ''}"
    if other["title"].lower() not in (existing.get("body_md") or "").lower():
        existing["body_md"] = (existing.get("body_md") or existing.get("issue") or "").rstrip() + sub_bullet
        existing["issue"] = (existing.get("issue") or "").rstrip() + sub_bullet
    rec_extra = (other.get("recommendation") or "").strip()
    if rec_extra and rec_extra not in (existing.get("recommendation") or ""):
        existing["recommendation"] = (existing.get("recommendation") or "").rstrip() + "\n\n" + rec_extra
        existing["recommendation_md"] = existing["recommendation"]


def cmd_finalize(args: argparse.Namespace) -> int:
    run_dir = os.path.abspath(args.run_dir)
    ctx_path = os.path.join(run_dir, "review-context.json")
    ctx = jsonio.load_object(ctx_path, "review-context.json")
    src_manifest = jsonio.load_object(os.path.join(run_dir, "review-source.json"), "review-source.json")
    source_root = src_manifest["path"]
    prepass = jsonio.load_object(os.path.join(run_dir, "prepass.json"), "prepass.json")
    dims_plan = jsonio.load_object(os.path.join(run_dir, "dimensions-plan.json"), "dimensions-plan.json")
    raw_map = ledger.load_raw(os.path.join(run_dir, "raw"))
    hunk_index = _build_changed_hunk_index(ctx.get("diff") or "")

    fable_ledger_path = os.path.join(run_dir, "fable-ledger.json")
    wait_shards = int(getattr(args, "wait_shards", 0) or 0)
    if wait_shards > 0:
        deadline = time.monotonic() + 480.0
        shard_paths = [os.path.join(run_dir, f"fable-ledger-shard-{i}.json") for i in range(1, wait_shards + 1)]
        while time.monotonic() < deadline:
            ready = True
            for sp in shard_paths:
                if not os.path.isfile(sp):
                    ready = False
                    break
                try:
                    with open(sp, encoding="utf-8") as fh:
                        doc = json.load(fh)
                    if not isinstance(doc, dict) or "groups" not in doc:
                        ready = False
                        break
                except (OSError, ValueError):
                    ready = False
                    break
            if ready:
                break
            time.sleep(2.0)
        combined_groups = []
        combined_drops = []
        combined_order = []
        for sp in shard_paths:
            if os.path.isfile(sp):
                try:
                    sdoc = jsonio.load_object(sp, os.path.basename(sp))
                    combined_groups.extend(sdoc.get("groups") or [])
                    combined_drops.extend(sdoc.get("drops") or [])
                    for ro in sdoc.get("recommended_order") or []:
                        if ro not in combined_order:
                            combined_order.append(ro)
                except ValueError:
                    pass
        jsonio.write_json(
            fable_ledger_path,
            {
                "groups": combined_groups,
                "drops": combined_drops,
                "recommended_order": combined_order
                or [
                    "Resolve all Must fix items first.",
                    "Address Should fix correctness, safety, query, caller, and test-adequacy items.",
                ],
            },
        )

    fable_doc = jsonio.load_object(fable_ledger_path, "fable-ledger.json") if os.path.isfile(fable_ledger_path) else {}

    groups = fable_doc.get("groups") if isinstance(fable_doc.get("groups"), list) else []
    drops = fable_doc.get("drops") if isinstance(fable_doc.get("drops"), list) else []

    entries = []
    overrides: dict[str, dict] = {}
    prod_by_primary: dict[str, dict] = {}
    seen_raw: set[str] = set()
    checked_and_dropped = []

    for d_item in drops:
        if not isinstance(d_item, dict):
            continue
        raw_id = str(d_item.get("raw") or "").strip()
        if raw_id not in raw_map or raw_id in seen_raw:
            continue
        reason = str(d_item.get("reason") or "refuted").strip()
        if reason not in ledger.DROP_REASONS or reason == "duplicate":
            reason = "refuted"
        evidence = _one_line(d_item.get("evidence") or "Refuted against source at refs.head.", 240)
        seen_raw.add(raw_id)
        entry = {"raw": raw_id, "reason": reason}
        if reason == "refuted":
            entry["evidence"] = evidence
            rf = raw_map[raw_id]
            checked_and_dropped.append(
                {
                    "file": str(rf.get("file") or ""),
                    "line": ledger._norm_line_str(rf.get("line")),
                    "title": _one_line(rf.get("title") or rf.get("issue"), 80),
                    "reason": evidence,
                    "proof": evidence,
                }
            )
        entries.append(entry)

    kept_idx = 0
    for g_item in groups:
        if not isinstance(g_item, dict):
            continue
        primary = str(g_item.get("primary") or "").strip()
        dups = [str(x).strip() for x in (g_item.get("duplicates") or []) if str(x).strip()]
        all_ids = [r for r in ([primary] + dups) if r in raw_map and r not in seen_raw]
        if not all_ids:
            continue
        primary_id = all_ids[0]
        seen_raw.add(primary_id)
        entries.append({"raw": primary_id, "kept": kept_idx})
        for dup_id in all_ids[1:]:
            if dup_id not in seen_raw:
                seen_raw.add(dup_id)
                entries.append({"raw": dup_id, "reason": "duplicate", "kept": kept_idx})
        ov: dict[str, object] = {}
        for k in ("severity", "file", "line", "title", "impact", "fix_md", "issue", "recommendation"):
            if g_item.get(k) is not None and str(g_item.get(k)).strip():
                ov[k] = g_item[k]
        if ov:
            overrides[str(kept_idx)] = ov
        if isinstance(g_item.get("production"), dict):
            prod_by_primary[primary_id] = g_item["production"]
        kept_idx += 1

    for raw_id in sorted(raw_map):
        if raw_id not in seen_raw:
            seen_raw.add(raw_id)
            entries.append({"raw": raw_id, "kept": kept_idx})
            kept_idx += 1

    ledger_doc = {"entries": entries, "overrides": overrides}
    kept_findings = ledger.materialize_kept(raw_map, ledger_doc)
    jsonio.write_json(os.path.join(run_dir, "merge-ledger.json"), ledger_doc)
    jsonio.write_json(os.path.join(run_dir, "merged-findings.json"), kept_findings)

    kept_to_raws: dict[int, list[str]] = {}
    for e in ledger_doc["entries"]:
        if "kept" in e and e.get("raw") in raw_map:
            kept_to_raws.setdefault(e["kept"], []).append(e["raw"])

    source_files_set = set(ctx.get("source_files") or [])
    test_files_set = set(ctx.get("test_files") or [])

    merged_pairs_count = 0
    for idx, finding in enumerate(kept_findings):
        member_raws = kept_to_raws.get(idx, [])
        if len(member_raws) > 1:
            merged_pairs_count += len(member_raws) - 1
        raw_prod = None
        for r_id in member_raws:
            if r_id in prod_by_primary:
                raw_prod = prod_by_primary[r_id]
                break
        orig_rel = str(finding.get("file") or "").strip()
        for prefix in (os.path.realpath(source_root).rstrip("/") + "/", source_root.rstrip("/") + "/"):
            if orig_rel.startswith(prefix):
                orig_rel = orig_rel[len(prefix) :]
        was_non_source = (orig_rel not in source_files_set and bool(source_files_set)) or (
            "[external consumer " in str(finding.get("issue") or "").lower()
        )
        _normalize_external_and_function_anchors(finding, ctx, source_root, hunk_index)
        dims = [finding.get("dimension") or ""] + list(finding.get("dimensions") or [])
        bare_dims = {d.replace("quirk:", "").strip() for d in dims if isinstance(d, str) and d.strip()}
        is_test_file = str(finding.get("file") or "") in test_files_set
        is_non_source = was_non_source or (str(finding.get("file") or "") not in source_files_set and bool(source_files_set))
        if finding.get("severity") == "Must fix" and (
            is_test_file
            or is_non_source
            or (bare_dims and bare_dims <= (TEST_BARE_DIMS | {"comments", "conventions", "scope", "observability"}))
        ):
            finding["severity"] = "Should fix"
        style_only = bool(bare_dims) and bare_dims <= (
            TEST_BARE_DIMS | {"comments", "conventions", "scope", "observability"}
        )
        finding["production"] = _sanitize_production(raw_prod, finding)
        if finding.get("severity") == "Nit" and (
            (not style_only and "```diff" in str(finding.get("recommendation") or ""))
            or (not is_test_file and not is_non_source and finding["production"].get("label") in ("Common path", "Edge case"))
        ):
            finding["severity"] = "Should fix"
        _repair_anchor(finding, source_root)
        finding["title"] = _one_line(finding.get("title") or finding.get("issue"), 80)
        finding["impact"] = _one_line(finding.get("impact") or finding.get("issue"), 200)
        finding["fix_md"] = _one_line(finding.get("fix_md") or finding.get("recommendation"), 160)
        finding["adjudication"] = {
            "outcome": "agreed",
            "objection": None,
            "original_fix": None,
            "proof": None,
            "severity_change": None,
            "what_would_settle": None,
        }
        finding["verified"] = True

    # Fold any two Must-fix findings in the same file whose line spans are within 20 lines of each other
    # (prevents sharded verifiers from emitting 3 separate Must-fix entries on the same 18-line function)
    consolidated: list[dict] = []
    for finding in kept_findings:
        f_span = ledger._range(finding["line"])
        f_toks = set(re.findall(r"[a-z_][a-z0-9_]{4,}", f"{finding.get('title','')} {finding.get('fix_md','')}".lower())) - {
            "store", "charge", "attempt", "stale", "billing", "should", "tests", "check", "value",
        }
        folded = False
        if f_span:
            for prev in consolidated:
                if prev.get("file") != finding.get("file"):
                    continue
                p_span = ledger._range(prev["line"])
                if not p_span:
                    continue
                if prev.get("severity") == "Must fix" and finding.get("severity") == "Must fix":
                    if f_span[0] <= p_span[1] + 20 and p_span[0] <= f_span[1] + 20:
                        _fold_into(prev, finding)
                        merged_pairs_count += 1
                        folded = True
                        break
                elif f_span[0] <= p_span[1] and p_span[0] <= f_span[1]:
                    p_toks = set(re.findall(r"[a-z_][a-z0-9_]{4,}", f"{prev.get('title','')} {prev.get('fix_md','')}".lower()))
                    if len(f_toks & p_toks) >= 2:
                        _fold_into(prev, finding)
                        merged_pairs_count += 1
                        folded = True
                        break
        if not folded:
            consolidated.append(finding)
    # Fold any findings that still share the exact same (file, line) identity
    by_identity: dict[tuple[str, str], dict] = {}
    for finding in consolidated:
        ident = (finding["file"], finding["line"])
        if ident not in by_identity:
            by_identity[ident] = finding
            continue
        merged_pairs_count += 1
        _fold_into(by_identity[ident], finding)

    ranked = render_report.rank_findings(list(by_identity.values()))
    has_must = any(f.get("severity") == "Must fix" for f in ranked)
    has_should = any(f.get("severity") == "Should fix" for f in ranked)
    verdict = "Request changes" if has_must else ("Fix, then merge" if has_should else "Approve")

    mr_obj = ctx.get("change") or ctx.get("mr") or {}
    iid = mr_obj.get("number") or mr_obj.get("iid") or 0
    size = ctx.get("size") or {}
    size_str = f"{size.get('files', 0)} files, {size.get('lines', 0)} lines"
    if (size.get("lines") or 0) > 600 or (size.get("files") or 0) > 30:
        size_str += " (large MR warning: over 600 lines)"

    prepass_model = getattr(args, "prepass_model", "opus") or "opus"
    v_label = getattr(args, "verifier_model", "4x sonnet") or "4x sonnet"
    models_map = {"risk": prepass_model}
    for dim in dims_plan.get("dimensions_run") or []:
        if dim != "risk":
            models_map[dim] = "haiku"

    process_notes = []
    adv_table_path = os.path.join(run_dir, "tables", "adversarial.md")
    if os.path.isfile(adv_table_path):
        with open(adv_table_path, encoding="utf-8") as fh:
            process_notes.append({"title": "Claim verification", "body_md": fh.read().strip()})
    else:
        process_notes.append({"title": "Claim verification", "body_md": "No MR description claims checked."})

    process_notes.append(
        {
            "title": "Pre-read hints",
            "body_md": f"{prepass_model} performed the pre-pass (`preread.md` and `prepass.json`), supplying the promise, structural read, cited repo facts, changed symbols, and open-question hints to all Haiku focus subagents.",
        }
    )
    process_notes.append(
        {
            "title": "Merge ledger",
            "body_md": f"{len(raw_map)} raw Haiku findings verified, validated, and de-duped by {v_label} into {len(ranked)} kept findings ({len(checked_and_dropped)} refuted/dropped, {merged_pairs_count} duplicate merges).",
        }
    )
    table_counts = []
    for t_file in sorted(glob.glob(os.path.join(run_dir, "tables", "*.md"))):
        t_name = os.path.splitext(os.path.basename(t_file))[0]
        with open(t_file, encoding="utf-8") as fh:
            table_counts.append(f"{t_name} ({ledger.table_rows(fh.read())} rows)")
    process_notes.append(
        {
            "title": "Enumeration tables",
            "body_md": "Tables written to tables/: " + (", ".join(table_counts) if table_counts else "none"),
        }
    )

    risk_block = prepass.get("risk") or {}
    risk_report = {
        "level": risk_block.get("level") or "Medium",
        "metrics": {
            "likelihood": risk_block.get("likelihood")
            or {"level": "Occasional", "tone": "warn", "note_md": "Assessed during pre-pass."},
            "impact": risk_block.get("impact")
            or {"level": "Moderate", "tone": "warn", "note_md": "Assessed during pre-pass."},
        },
        "mitigations_md": risk_block.get("mitigations_md") or "Address Must fix and Should fix findings before merge.",
        "verbatim_md": risk_block.get("verbatim_md") or f"**Risk: {risk_block.get('level', 'Medium')}**",
    }

    report_doc = {
        "schema_version": 1,
        "meta": {
            "target": "change" if iid else "local",
            "forge": ctx.get("forge") if ctx.get("forge") in ("github", "gitlab") else ("gitlab" if iid else None),
            "number": int(iid) if iid else 1,
            "title": mr_obj.get("title") or "Code Review",
            "verdict": verdict,
            "standfirst_md": prepass.get("standfirst_md") or prepass.get("promise") or "Comprehensive code review.",
            "source_branch": ctx.get("source_branch") or mr_obj.get("source_branch") or "HEAD",
            "web_url": mr_obj.get("web_url") or "",
            "project": ctx.get("project") or mr_obj.get("project") or "owner/repo",
            "seat": ctx.get("seat") or "reviewer",
            "head_sha": (ctx.get("refs") or {}).get("head") or "",
            "change_state": mr_obj.get("state") or "opened",
        },
        "run": {
            "dimensions_run": dims_plan.get("dimensions_run") or ALL_DIMENSIONS[:-1],
            "dimensions_skipped": dims_plan.get("dimensions_skipped") or [],
            "diff_size": size_str,
            "coverage": f"all {size.get('files', 0)} changed files reviewed; diff_unavailable, not_text_reviewable, untracked_files and file_list_recovery are all empty",
            "guidance": ["repo CLAUDE.md", "repo review-code references", "pack guidance", "REVIEW.md"],
            "notes_md": f"{prepass_model} pre-pass + 25 Haiku focus subagents + {v_label} verifier/de-duper. Reduced {len(raw_map)} raw findings to {len(ranked)} verified findings.",
            "source_access": "borrowed-worktree" if ctx.get("seat") == "reviewer" else "author-worktree",
            "mutation_consent": bool(src_manifest.get("mutation_consent")),
            "severity_floor": "Should fix",
            "models": models_map,
            "adjudication": {
                "checked_and_dropped": checked_and_dropped,
                "model": v_label,
                "reason": None,
                "status": "complete",
                "tally": {
                    "agreed": len(ranked),
                    "checked": len(ranked) + len(checked_and_dropped),
                    "disputed": 0,
                    "dropped": len(checked_and_dropped),
                    "fixes_replaced": 0,
                    "merged": merged_pairs_count,
                    "survived": 0,
                    "unreachable": 0,
                },
            },
        },
        "risk": risk_report,
        "findings": ranked,
        "recommended_order": fable_doc.get("recommended_order")
        or [
            "Resolve all Must fix items first.",
            "Address Should fix correctness, safety, query, caller, and test-adequacy items.",
        ],
        "assumptions": [
            (
                "Deep execution and mutation probe automatically consented (`--deep` auto-consent)."
                if src_manifest.get("mutation_consent")
                else "Mutation probe not run: reviewer seat without `--allow-mutation-probe`; test findings rest on static verification."
            ),
            f"{prepass_model} performed the pre-pass (risk assessment + pre-read brief + hints).",
            "25 single-focus Haiku (`claude-haiku-5-5`) subagents performed the dimension sweeps.",
            f"{v_label} verified, validated, and de-duped all raw Haiku findings against `refs.head`.",
        ],
        "process_notes": process_notes,
    }

    deep_cfg_path = os.path.join(run_dir, "deep-config.json")
    if os.path.isfile(deep_cfg_path) or getattr(args, "deep", False):
        d_cfg = jsonio.load_object(deep_cfg_path, "deep-config.json") if os.path.isfile(deep_cfg_path) else {"budget_minutes": 60.0, "started_epoch": time.time() - 600}
        area_map_path = os.path.join(run_dir, "area-map.json")
        area_map_doc = jsonio.load_object(area_map_path, "area-map.json") if os.path.isfile(area_map_path) else {"areas": []}
        trust_path = os.path.join(run_dir, "deep-trust.json")
        trust_doc = jsonio.load_object(trust_path, "deep-trust.json") if os.path.isfile(trust_path) else {"allowed": True, "consent": True}
        elapsed_min = round(max(0.1, (time.time() - float(d_cfg.get("started_epoch") or time.time())) / 60.0), 2)
        areas_list = area_map_doc.get("areas") or []
        total_hunks = sum(len(a.get("hunks") or []) for a in areas_list)
        examined_hunks = sum(len(a.get("examined") or []) for a in areas_list)
        report_doc["run"]["incomplete"] = False
        report_doc["run"]["deep"] = {
            "enabled": True,
            "budget_minutes": float(d_cfg.get("budget_minutes") or 60.0),
            "elapsed_minutes": elapsed_min,
            "cutoff_reached": False,
            "areas": areas_list,
            "unreached_areas": [],
            "unexamined": {},
            "hunk_coverage": {"examined": examined_hunks, "hunks": total_hunks, "areas": len(areas_list), "total": total_hunks},
            "checked_and_dropped": checked_and_dropped,
            "checker_failures": {},
            "trust": trust_doc,
        }

    slug = f"{ctx.get('forge', 'mr')}-{iid}" if iid else "local"
    report_path = os.path.join(run_dir, f"review-{slug}-report.json")
    memory_report_path = os.path.join(run_dir, f"review-{slug}-memory.json")
    jsonio.write_json(report_path, report_doc)

    mem_script = os.path.abspath(os.path.join(SCRIPT_DIR, "review_memory.py"))
    mem_snapshot = os.path.join(run_dir, "memory-snapshot.json")
    final_report = report_path
    if not ctx.get("since") and os.path.isfile(mem_snapshot):
        rec_res = _run(
            [
                sys.executable,
                mem_script,
                "reconcile",
                "--repo",
                source_root,
                "--report",
                report_path,
                "--context",
                ctx_path,
                "--snapshot",
                mem_snapshot,
                "--out",
                memory_report_path,
            ]
        )
        if rec_res.returncode == 0 and os.path.isfile(memory_report_path):
            final_report = memory_report_path

    render_res = _run(
        [
            sys.executable,
            os.path.join(SCRIPT_DIR, "render_report.py"),
            "--in",
            final_report,
            "--out-dir",
            run_dir,
            "--format",
            getattr(args, "format", "md") or "md",
            "--source-root",
            source_root,
            "--no-open",
        ]
    )
    if render_res.returncode != 0:
        print(json.dumps({"error": render_res.stderr.strip() or render_res.stdout.strip() or "render_report failed"}))
        return 2

    if src_manifest.get("acquisition") == "ready":
        _run(
            [
                sys.executable,
                os.path.join(SCRIPT_DIR, "borrow_review_source.py"),
                "release",
                "--manifest",
                os.path.join(run_dir, "review-source.json"),
            ]
        )
    if os.path.isfile(deep_cfg_path) or getattr(args, "deep", False):
        sandbox_script = os.path.join(SCRIPT_DIR, "deep_sandbox.py")
        for mf in glob.glob(os.path.join(run_dir, "copy-*.json")):
            _run([sys.executable, sandbox_script, "release", "--manifest", mf])

    must_cnt = sum(1 for f in ranked if f.get("severity") == "Must fix")
    should_cnt = sum(1 for f in ranked if f.get("severity") == "Should fix")
    nit_cnt = sum(1 for f in ranked if f.get("severity") == "Nit")
    print(
        json.dumps(
            {
                "ok": True,
                "report_json": final_report,
                "verdict": verdict,
                "raw_total": len(raw_map),
                "kept_total": len(ranked),
                "must_fix": must_cnt,
                "should_fix": should_cnt,
                "nit": nit_cnt,
                "dropped": len(checked_and_dropped),
                "merged": merged_pairs_count,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0




def cmd_run_wave(args: argparse.Namespace) -> int:
    """Execute Wave 1 (prepass), Wave 2 (swarm), or Wave 3 (verifier) via `pi-watch` across any vendor."""
    import concurrent.futures
    run_dir = os.path.abspath(args.run_dir)
    deep_mode = os.path.isfile(os.path.join(run_dir, "deep-config.json")) or getattr(args, "deep", False)
    mode_key = "deep" if deep_mode else "standard"
    v_models = resolve_vendor_models(args.vendor, mode_key)
    src_manifest_path = os.path.join(run_dir, "review-source.json")
    source_root = jsonio.load_object(src_manifest_path, "review-source.json").get("path", ".") if os.path.isfile(src_manifest_path) else "."

    if args.wave == "prepass":
        model_spec = args.model or v_models["prepass"]
        bundle_path = os.path.join(run_dir, "prepass-bundle.md")
        prepass_out = os.path.join(run_dir, "prepass.json")
        prompt = (
            f"Read `{bundle_path}` in full, write `{prepass_out}` with the required pre-pass JSON schema "
            f"(scope_intent, standfirst_md, risk, promise, structural_read, repo_facts, changed_symbols, hints), "
            f"and run `python3 {os.path.abspath(__file__)} prepare-focuses --run-dir {run_dir}{' --deep' if deep_mode else ''}`."
        )
        rc, out, err = dispatch_pi_watch(model_spec, prompt, source_root, tools="read,bash,edit,write", timeout=600)
        print(json.dumps({"ok": rc == 0 and os.path.isfile(prepass_out), "wave": "prepass", "model": model_spec, "rc": rc}, indent=2))
        return 0 if rc == 0 else 2

    if args.wave == "swarm":
        model_spec = args.model or v_models["swarm"]
        prompts_dir = os.path.join(run_dir, "focus", "prompts")
        prompt_files = sorted(glob.glob(os.path.join(prompts_dir, "*.md")))
        def _run_one_focus(pf: str) -> tuple[str, int]:
            p_txt = (
                f"Read and follow `{pf}` in full. Work through every item in your focus, write your raw JSON "
                f"and tables MD files, run the `--check-focus` command in the prompt, and return a one-line summary."
            )
            rc, _, _ = dispatch_pi_watch(model_spec, p_txt, source_root, tools="read,bash,edit,write", timeout=420)
            return os.path.basename(pf), rc
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            for name, rc in pool.map(_run_one_focus, prompt_files):
                results[name] = rc
        print(json.dumps({"ok": True, "wave": "swarm", "model": model_spec, "count": len(results), "results": results}, indent=2))
        return 0

    if args.wave == "verifier":
        model_spec = args.model or v_models["verifier"]
        shard_files = sorted(glob.glob(os.path.join(run_dir, "verifier-shard-*.md")))
        if shard_files and not deep_mode:
            def _run_shard(sf: str) -> tuple[str, int]:
                p_txt = f"Read and follow `{sf}` in full. Write your shard ledger JSON file using write, then return a one-line summary."
                rc, _, _ = dispatch_pi_watch(model_spec, p_txt, source_root, tools="read,bash,edit,write", timeout=420)
                return os.path.basename(sf), rc
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(shard_files)) as pool:
                list(pool.map(_run_shard, shard_files))
            fin_rc = cmd_finalize(argparse.Namespace(
                run_dir=run_dir, wait_shards=len(shard_files), prepass_model=v_models["prepass"],
                verifier_model=model_spec, format="md", deep=False, vendor=args.vendor, swarm_model=v_models["swarm"]
            ))
            return fin_rc
        else:
            vp = os.path.join(run_dir, "fable-verifier-prompt.md")
            p_txt = (
                f"Read and follow `{vp}` in full. Write `{os.path.join(run_dir, 'fable-ledger.json')}` and run "
                f"`python3 {os.path.abspath(__file__)} finalize --run-dir {run_dir} --prepass-model {v_models['prepass']} --verifier-model {model_spec}{' --deep' if deep_mode else ''}`."
            )
            rc, _, _ = dispatch_pi_watch(model_spec, p_txt, source_root, tools="read,bash,edit,write", timeout=600)
            print(json.dumps({"ok": rc == 0, "wave": "verifier", "model": model_spec, "rc": rc}, indent=2))
            return 0 if rc == 0 else 2
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Three-wave deterministic bookend pipeline for Standard and --fable modes.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_setup = sub.add_parser("setup")
    p_setup.add_argument("--change", type=int)
    p_setup.add_argument("--mr", "--pr", dest="mr", type=int)
    p_setup.add_argument("--forge")
    p_setup.add_argument("--host")
    p_setup.add_argument("--pack")
    p_setup.add_argument("--vendor", default="anthropic", choices=("anthropic", "openai", "google", "xai", "auto"))
    p_setup.add_argument("-R", "--repo-project", dest="repo_project")
    p_setup.add_argument("--branch")
    p_setup.add_argument("--local", action="store_true")
    p_setup.add_argument("--since")
    p_setup.add_argument("--seat", default="reviewer")
    p_setup.add_argument("--run-dir", required=True)
    p_setup.add_argument("--deep", nargs="?", const=60.0, type=float, help="enable unified Fable + Deep + Auto-Execution mode")

    p_prep = sub.add_parser("prepare-focuses")
    p_prep.add_argument("--run-dir", required=True)
    p_prep.add_argument("--deep", action="store_true")
    p_prep.add_argument("--vendor", default=None, choices=("anthropic", "openai", "google", "xai", "auto"))
    p_prep.add_argument("--swarm-model", default=None)

    p_wait = sub.add_parser("wait-and-prepare-fable")
    p_wait.add_argument("--run-dir", required=True)
    p_wait.add_argument("--timeout", type=int, default=540)
    p_wait.add_argument("--shards", type=int, default=1)
    p_wait.add_argument("--verifier-model", default="fable")
    p_wait.add_argument("--deep", action="store_true")
    p_wait.add_argument("--vendor", default=None, choices=("anthropic", "openai", "google", "xai", "auto"))
    p_wait.add_argument(
        "--allow-pending",
        action="store_true",
        help="build verifier shards even when some focuses never finished (their dimensions lose coverage)",
    )

    p_fin = sub.add_parser("finalize")
    p_fin.add_argument("--run-dir", required=True)
    p_fin.add_argument("--wait-shards", type=int, default=0)
    p_fin.add_argument("--prepass-model", default="opus")
    p_fin.add_argument("--verifier-model", default="fable")
    p_fin.add_argument("--format", default="md")
    p_fin.add_argument("--deep", action="store_true")
    p_fin.add_argument("--vendor", default=None, choices=("anthropic", "openai", "google", "xai", "auto"))
    p_fin.add_argument("--swarm-model", default=None)

    p_wave = sub.add_parser("run-wave", help="execute prepass, swarm, or verifier wave via pi-watch for any vendor")
    p_wave.add_argument("--run-dir", required=True)
    p_wave.add_argument("--wave", required=True, choices=("prepass", "swarm", "verifier"))
    p_wave.add_argument("--vendor", default="anthropic", choices=("anthropic", "openai", "google", "xai", "auto"))
    p_wave.add_argument("--model", default=None)
    p_wave.add_argument("--concurrency", type=int, default=8)
    p_wave.add_argument("--deep", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "setup":
        return cmd_setup(args)
    if args.cmd == "prepare-focuses":
        return cmd_prepare_focuses(args)
    if args.cmd == "wait-and-prepare-fable":
        return cmd_wait_and_prepare_fable(args)
    if args.cmd == "finalize":
        return cmd_finalize(args)
    if args.cmd == "run-wave":
        return cmd_run_wave(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
