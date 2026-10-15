import contextlib
import io
import json
import subprocess
from pathlib import Path

import pytest

import resolve_policy as m

SKILL = Path(__file__).resolve().parents[2] / "skills" / "full-code-review"
LENSES = SKILL / "references" / "lenses"
EXAMPLE_PACK = SKILL / "references" / "example-pack"


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + list(args), check=True,
                          capture_output=True, text=True).stdout.strip()


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo, message="c"):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message, "--allow-empty")
    return _git(repo, "rev-parse", "HEAD")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _diff(*paths):
    return "".join("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -1 +1 @@\n-x\n+y\n" % (p, p, p, p)
                   for p in paths)


def _context(tmp_path, changed, batched=False):
    ctx = {"schema": 1, "changed_files": list(changed), "diff": _diff(*changed), "batched": batched,
           "size": {"files": len(changed), "lines": 2 * len(changed)}}
    ctx["test_files"], ctx["source_files"] = [], list(changed)
    if batched:
        ctx["batches"] = [{"files": list(changed), "diff": ctx["diff"]}]
    path = tmp_path / "context.json"
    path.write_text(json.dumps(ctx))
    return path


def _resolve(tmp_path, repo, changed=("src/app.py",), pack=None, ref=None, apply=False,
             batched=False, user_config=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(user_config or tmp_path / "no-config"))
    ctx = _context(tmp_path, changed, batched)
    out = tmp_path / "out" / "policy.json"
    args = ["--context", str(ctx), "--source-root", str(repo), "--lenses-dir", str(LENSES),
            "--out", str(out)]
    if pack:
        args += ["--pack", str(pack)]
    if ref:
        args += ["--policy-ref", ref]
    if apply:
        args.append("--apply")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = m.main(args)
    policy = json.loads(out.read_text()) if out.exists() else None
    return rc, policy, json.loads(ctx.read_text()), buf.getvalue()


def _lens(policy, lens_id):
    return next((lens for lens in policy["lenses"] if lens["id"] == lens_id), None)


def test_builtin_roster_is_the_default_policy(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    rc, policy, _, _ = _resolve(tmp_path, repo, monkeypatch=monkeypatch)
    assert rc == 0
    assert len(policy["lenses"]) == 14
    assert policy["severity_floor"] == "Should fix"
    assert policy["escalation"] is True
    assert policy["cross_family"] == {"enabled": False, "alias": None}
    assert _lens(policy, "risk")["batched"] is False
    assert _lens(policy, "risk")["source"] == "builtin"
    assert policy["sources"] == [{"kind": "builtin", "path": str(LENSES), "ref": None}]


def test_layers_apply_in_order_user_then_project_then_review_md(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    user = tmp_path / "config" / "quirk" / "review"
    _write(user / "pack.yaml", "severity_floor: Nit\nescalation: false\nmodels:\n  db: haiku\n  safety: opus\n")
    _write(repo / ".quirk" / "review" / "pack.yaml", "severity_floor: Must fix\nmodels:\n  db: sonnet\n")
    _write(repo / "REVIEW.md", "---\nescalation: true\n---\n\nPrefer small diffs.\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, user_config=tmp_path / "config", monkeypatch=monkeypatch)
    assert rc == 0
    assert policy["severity_floor"] == "Must fix"
    assert policy["escalation"] is True
    assert _lens(policy, "db")["model"] == "sonnet"
    assert _lens(policy, "safety")["model"] == "opus"
    assert [s["kind"] for s in policy["sources"]] == ["builtin", "user-pack", "project-pack", "review-md"]


def test_pack_flag_stands_in_for_the_user_pack(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    user = tmp_path / "config" / "quirk" / "review"
    _write(user / "pack.yaml", "severity_floor: Nit\n")
    flag_pack = tmp_path / "org-pack"
    _write(flag_pack / "pack.yaml", "severity_floor: Must fix\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, pack=flag_pack, user_config=tmp_path / "config",
                                monkeypatch=monkeypatch)
    assert rc == 0 and policy["severity_floor"] == "Must fix"
    assert [s["path"] for s in policy["sources"] if s["kind"] == "user-pack"] == [str(flag_pack)]


def test_reviewer_seat_reads_project_policy_from_the_target_ref(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / "REVIEW.md", "---\nseverity_floor: Must fix\n---\n")
    _write(repo / ".quirk" / "review" / "pack.yaml", "skip: [observability]\n")
    target = _commit(repo, "target")
    # the PR head weakens both files; the review must not see that
    _write(repo / "REVIEW.md", "---\nseverity_floor: Nit\n---\n")
    _write(repo / ".quirk" / "review" / "pack.yaml", "skip: [correctness, safety]\n")
    _commit(repo, "head")
    rc, policy, _, _ = _resolve(tmp_path, repo, ref=target, monkeypatch=monkeypatch)
    assert rc == 0
    assert policy["severity_floor"] == "Must fix"
    assert [s["id"] for s in policy["skipped"]] == ["observability"]
    assert _lens(policy, "correctness") is not None
    review_md = [s for s in policy["sources"] if s["kind"] == "review-md"][0]
    assert review_md["ref"] == target
    # lenses read guidance from disk, so ref-read files are materialized beside policy.json
    materialized = [Path(p) for p in policy["guidance_files"]]
    assert all(p.is_file() for p in materialized)
    assert any("Must fix" in p.read_text() for p in materialized)


def test_nearest_review_md_overrides_the_root_key_by_key(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / "REVIEW.md", "---\nseverity_floor: Must fix\nescalation: false\n---\n")
    _write(repo / "services" / "billing" / "REVIEW.md", "---\nseverity_floor: Nit\n---\n")
    _write(repo / "services" / "other" / "REVIEW.md", "---\nseverity_floor: Should fix\n---\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, changed=("services/billing/pay.py",),
                                monkeypatch=monkeypatch)
    assert rc == 0
    assert policy["severity_floor"] == "Nit"
    assert policy["escalation"] is False
    assert [Path(s["path"]).parent.name for s in policy["sources"] if s["kind"] == "review-md"] == ["repo", "billing"]


def test_pack_lens_replaces_a_builtin_and_unknown_id_adds_a_lens(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    pack = tmp_path / "pack"
    _write(pack / "lenses" / "risk.md", "---\nid: risk\nrun_when: always\nmodel: sonnet\nescalate: false\nbatched: false\n---\n\n# Org risk\n")
    _write(pack / "lenses" / "license-headers.md", "---\nid: license-headers\nrun_when: code_changed\n---\n\n# Headers\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, pack=pack, monkeypatch=monkeypatch)
    assert rc == 0
    assert _lens(policy, "risk")["checklist"] == str(pack / "lenses" / "risk.md")
    assert _lens(policy, "risk")["source"] == "user-pack"
    added = _lens(policy, "license-headers")
    assert added["run_when"] == "code_changed" and added["model"] == "sonnet"
    assert added["batched"] is True and added["escalate"] is False
    assert len(policy["lenses"]) == 15


def test_added_lens_without_run_when_is_rejected(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    pack = tmp_path / "pack"
    _write(pack / "lenses" / "mystery.md", "---\nid: mystery\n---\n")
    rc, policy, _, out = _resolve(tmp_path, repo, pack=pack, monkeypatch=monkeypatch)
    assert rc == 2 and policy is None
    assert "mystery.md" in json.loads(out)["error"] and "run_when" in json.loads(out)["error"]


def test_skip_is_a_union_across_layers(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    pack = tmp_path / "pack"
    _write(pack / "pack.yaml", "skip: [observability]\n")
    _write(repo / "REVIEW.md", "---\nskip: [comments]\n---\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, pack=pack, monkeypatch=monkeypatch)
    assert rc == 0
    assert sorted(s["id"] for s in policy["skipped"]) == ["comments", "observability"]
    assert _lens(policy, "comments") is None and _lens(policy, "observability") is None


def test_flow_mapping_is_rejected_with_file_and_line(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".quirk" / "review" / "pack.yaml", "severity_floor: Nit\nmodels: {db: haiku}\n")
    rc, policy, _, out = _resolve(tmp_path, repo, monkeypatch=monkeypatch)
    assert rc == 2 and policy is None
    error = json.loads(out)["error"]
    assert "pack.yaml:2" in error


@pytest.mark.parametrize("text, fragment", [
    ("severity_floor: Blocker\n", "severity_floor"),
    ("models:\n  db: gpt\n", "models.db"),
    ("escalation: maybe\n", "escalation"),
])
def test_invalid_values_exit_2(tmp_path, monkeypatch, text, fragment):
    repo = _repo(tmp_path)
    _write(repo / ".quirk" / "review" / "pack.yaml", text)
    rc, _, _, out = _resolve(tmp_path, repo, monkeypatch=monkeypatch)
    assert rc == 2 and fragment in json.loads(out)["error"]


def test_unknown_keys_warn(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / "REVIEW.md", "---\nfuture_toggle: on\n---\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, monkeypatch=monkeypatch)
    assert rc == 0
    assert any("future_toggle" in w for w in policy["warnings"])


def test_apply_excludes_generated_and_skip_glob_files_and_recomputes_size(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".gitattributes", "gen/** linguist-generated\n")
    _write(repo / "REVIEW.md", "---\nskip_globs: [\"**/*.lock\"]\n---\n")
    _commit(repo)
    changed = ("src/app.py", "gen/client.py", "poetry.lock")
    rc, policy, ctx, _ = _resolve(tmp_path, repo, changed=changed, apply=True, batched=True,
                                  monkeypatch=monkeypatch)
    assert rc == 0
    assert ctx["changed_files"] == ["src/app.py"]
    assert ctx["source_files"] == ["src/app.py"]
    assert ctx["excluded_generated"] == ["gen/client.py", "poetry.lock"]
    assert "gen/client.py" not in ctx["diff"] and "poetry.lock" not in ctx["diff"]
    assert ctx["size"] == {"files": 1, "lines": 2}
    assert ctx["batches"] == [{"files": ["src/app.py"], "diff": ctx["diff"].rstrip("\n")}]


def test_reviewer_seat_ignores_gitattributes_added_at_the_pr_head(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    target = _commit(repo, "target")
    _write(repo / ".gitattributes", "src/** linguist-generated\n")
    _commit(repo, "head hides src")
    rc, _, ctx, _ = _resolve(tmp_path, repo, changed=("src/app.py",), ref=target, apply=True,
                             monkeypatch=monkeypatch)
    assert rc == 0
    assert ctx["changed_files"] == ["src/app.py"] and ctx["excluded_generated"] == []


def test_guidance_files_list_pack_guidance_and_review_md(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    pack = tmp_path / "pack"
    _write(pack / "guidance" / "org.md", "Org rule.\n")
    _write(repo / ".quirk" / "review" / "guidance" / "team.md", "Team rule.\n")
    _write(repo / "REVIEW.md", "---\n---\nRepo rule.\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, pack=pack, monkeypatch=monkeypatch)
    assert rc == 0
    names = sorted(Path(p).name for p in policy["guidance_files"])
    assert names == ["REVIEW.md", "org.md", "team.md"]


def test_critical_paths_and_skip_globs_union_across_layers(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    pack = tmp_path / "pack"
    _write(pack / "pack.yaml", "critical_paths: [\"src/billing/**\"]\n")
    _write(repo / "REVIEW.md", "---\ncritical_paths: [\"src/auth/**\"]\n---\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, pack=pack, monkeypatch=monkeypatch)
    assert rc == 0
    assert policy["critical_paths"] == ["src/billing/**", "src/auth/**"]


def test_example_pack_overrides_risk_and_adds_a_lens(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    rc, policy, _, _ = _resolve(tmp_path, repo, pack=EXAMPLE_PACK, monkeypatch=monkeypatch)
    assert rc == 0
    assert _lens(policy, "risk")["checklist"] == str(EXAMPLE_PACK / "lenses" / "risk.md")
    assert _lens(policy, "license-headers")["source"] == "user-pack"
    assert policy["critical_paths"]
