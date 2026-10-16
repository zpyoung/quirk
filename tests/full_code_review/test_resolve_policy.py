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


def _context(tmp_path, changed, batched=False, seat=None):
    ctx = {"schema": 1, "changed_files": list(changed), "diff": _diff(*changed), "batched": batched,
           "size": {"files": len(changed), "lines": 2 * len(changed)}}
    if seat:
        ctx["seat"] = seat
    ctx["test_files"], ctx["source_files"] = [], list(changed)
    if batched:
        ctx["batches"] = [{"files": list(changed), "diff": ctx["diff"]}]
    path = tmp_path / "context.json"
    path.write_text(json.dumps(ctx))
    return path


def _resolve(tmp_path, repo, changed=("src/app.py",), pack=None, ref=None, apply=False,
             batched=False, user_config=None, monkeypatch=None, seat=None, diff_only=False):
    if monkeypatch is not None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(user_config or tmp_path / "no-config"))
    ctx = _context(tmp_path, changed, batched, seat)
    out = tmp_path / "out" / "policy.json"
    args = ["--context", str(ctx), "--lenses-dir", str(LENSES), "--out", str(out)]
    args += ["--diff-only"] if diff_only else ["--source-root", str(repo)]
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


@pytest.mark.parametrize("path, text, fragment", [
    ("REVIEW.md", "---\nseverity_floor: Must fix\n", "front matter is not closed"),
    (".quirk/review/lenses/bad.md", "---\nid: bad\nrun_when: sometimes\n---\n", "run_when must be one of"),
])
def test_malformed_policy_files_exit_2(tmp_path, monkeypatch, path, text, fragment):
    repo = _repo(tmp_path)
    _write(repo / path, text)
    rc, policy, _, out = _resolve(tmp_path, repo, monkeypatch=monkeypatch)
    assert rc == 2 and policy is None and fragment in json.loads(out)["error"]


def test_skip_and_models_naming_an_unknown_lens_warn(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".quirk" / "review" / "pack.yaml", "skip: [secutiry]\nmodels:\n  dbb: haiku\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, monkeypatch=monkeypatch)
    assert rc == 0
    assert any("skip: unknown lens secutiry" in w for w in policy["warnings"])
    assert any("models: unknown lens dbb" in w for w in policy["warnings"])


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


def test_reviewer_seat_reads_gitattributes_from_the_target_ref_only(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".gitattributes", "gen/** linguist-generated\n")
    target = _commit(repo, "target")
    _write(repo / ".gitattributes", "gen/** linguist-generated\nsrc/** linguist-generated\n")
    _commit(repo, "head hides src")
    if not m._supports_attr_source(repo):
        pytest.skip("git < 2.40 cannot read attributes from a ref")
    rc, policy, ctx, _ = _resolve(tmp_path, repo, changed=("src/app.py", "gen/client.py"), ref=target,
                                  apply=True, monkeypatch=monkeypatch)
    assert rc == 0
    # the target's attribute excludes gen/, so check-attr ran; the head's attribute on src/ is ignored
    assert ctx["changed_files"] == ["src/app.py"]
    assert ctx["excluded_generated"] == ["gen/client.py"]
    assert not [w for w in policy["warnings"] if "linguist-generated" in w]


def test_reviewer_seat_requires_a_policy_ref(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    target = _commit(repo, "target")
    rc, policy, _, out = _resolve(tmp_path, repo, seat="reviewer", monkeypatch=monkeypatch)
    assert rc == 2 and policy is None
    assert "--policy-ref" in json.loads(out)["error"]
    rc, policy, _, _ = _resolve(tmp_path, repo, seat="reviewer", ref=target, monkeypatch=monkeypatch)
    assert rc == 0 and policy is not None


def test_diff_only_reviewer_run_skips_project_policy_and_records_it(tmp_path, monkeypatch):
    user_pack = tmp_path / "user-pack"
    _write(user_pack / "pack.yaml", "skip_globs: [\"*.lock\"]\nseverity_floor: Nit\n")
    rc, policy, ctx, _ = _resolve(tmp_path, None, changed=("src/app.py", "deps.lock"), pack=user_pack,
                                  apply=True, seat="reviewer", diff_only=True, monkeypatch=monkeypatch)
    assert rc == 0
    assert policy["diff_only"] is True
    assert policy["severity_floor"] == "Nit"
    assert [src["kind"] for src in policy["sources"]] == ["builtin", "user-pack"]
    assert any("diff-only" in warning for warning in policy["warnings"])
    assert ctx["changed_files"] == ["src/app.py"] and ctx["excluded_generated"] == ["deps.lock"]


def test_diff_only_cannot_be_combined_with_a_policy_ref_or_a_source_root(tmp_path, monkeypatch):
    rc, policy, _, out = _resolve(tmp_path, None, ref="a" * 40, seat="reviewer", diff_only=True,
                                  monkeypatch=monkeypatch)
    assert rc == 2 and policy is None and "--policy-ref" in json.loads(out)["error"]
    with pytest.raises(SystemExit):
        m.main(["--context", "c.json", "--lenses-dir", str(LENSES), "--out", "o.json",
                "--diff-only", "--source-root", str(tmp_path)])


def test_author_seat_reads_the_working_tree_without_a_policy_ref(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / "REVIEW.md", "---\nseverity_floor: Nit\n---\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, seat="author", monkeypatch=monkeypatch)
    assert rc == 0 and policy["severity_floor"] == "Nit"


def test_unreadable_policy_ref_is_an_error_not_an_absent_policy(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _commit(repo, "target")
    rc, policy, _, out = _resolve(tmp_path, repo, ref="deadbeef" * 5, monkeypatch=monkeypatch)
    assert rc == 2 and policy is None
    assert "cannot read" in json.loads(out)["error"]


def test_a_path_missing_at_the_ref_is_simply_absent(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    target = _commit(repo, "target")
    source = m._RefSource(repo, target, tmp_path / "stash")
    assert source.read("REVIEW.md") is None
    assert source.read(".quirk/review/pack.yaml") is None


def test_git_timeout_surfaces_as_a_policy_error(tmp_path, monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(m.subprocess, "run", hang)
    with pytest.raises(m.PolicyError, match="timed out"):
        m._git(tmp_path, "status")


def test_applying_the_policy_twice_keeps_the_excluded_list(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / "REVIEW.md", "---\nskip_globs: [\"**/*.lock\"]\n---\n")
    _commit(repo)
    rc, policy, ctx, _ = _resolve(tmp_path, repo, changed=("src/app.py", "poetry.lock"), apply=True,
                                  monkeypatch=monkeypatch)
    assert rc == 0 and ctx["excluded_generated"] == ["poetry.lock"]
    second = tmp_path / "second"
    second.mkdir()
    out = second / "policy.json"
    rc = m.main(["--context", str(tmp_path / "context.json"), "--source-root", str(repo),
                 "--lenses-dir", str(LENSES), "--out", str(out), "--apply"])
    assert rc == 0
    again = json.loads((tmp_path / "context.json").read_text())
    assert again["excluded_generated"] == ["poetry.lock"]
    assert again["changed_files"] == ["src/app.py"]


def test_policy_yaml_matches_the_vendored_copy():
    scripts = Path(m.__file__).resolve().parent
    vendored = scripts.parents[1] / "filing-requests" / "scripts" / "_yaml_mini.py"
    assert (scripts / "policy_yaml.py").read_bytes() == vendored.read_bytes()


def test_reviewer_seat_reads_lenses_and_guidance_from_the_target_ref(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".quirk" / "review" / "lenses" / "extra.md",
           "---\nid: extra\nrun_when: always\n---\nTarget checklist.\n")
    _write(repo / ".quirk" / "review" / "guidance" / "team.md", "Target rule.\n")
    target = _commit(repo, "target")
    _write(repo / ".quirk" / "review" / "lenses" / "extra.md",
           "---\nid: extra\nrun_when: always\n---\nPR checklist.\n")
    _write(repo / ".quirk" / "review" / "guidance" / "team.md", "PR rule.\n")
    _commit(repo, "head")
    rc, policy, _, _ = _resolve(tmp_path, repo, ref=target, monkeypatch=monkeypatch)
    assert rc == 0
    assert _lens(policy, "extra")["run_when"] == "always"
    guidance = [Path(p) for p in policy["guidance_files"]]
    assert [p.read_text() for p in guidance] == ["Target rule.\n"]
    assert all("policy-files" in str(p) for p in guidance)
    assert [s["ref"] for s in policy["sources"] if s["kind"] == "project-pack"] == [target]


def test_cross_family_and_cross_repo_settings_come_from_a_pack(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    pack = tmp_path / "pack"
    _write(pack / "pack.yaml", "cross_family:\n  enabled: true\n  alias: codex\n"
                               "cross_repo:\n  search_agent: code-search-agent\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, pack=pack, monkeypatch=monkeypatch)
    assert rc == 0
    assert policy["cross_family"] == {"enabled": True, "alias": "codex"}
    assert policy["cross_repo"] == {"search_agent": "code-search-agent"}


def test_skip_globs_union_across_layers_and_exclude_files(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    pack = tmp_path / "pack"
    _write(pack / "pack.yaml", "skip_globs:\n- \"dist/**\"\n")
    _write(repo / "REVIEW.md", "---\nskip_globs: [\"**/*.lock\"]\n---\n")
    _commit(repo)
    rc, policy, ctx, _ = _resolve(tmp_path, repo, changed=("src/app.py", "dist/a.js", "uv.lock"),
                                  pack=pack, apply=True, monkeypatch=monkeypatch)
    assert rc == 0
    assert policy["skip_globs"] == ["dist/**", "**/*.lock"]
    assert ctx["changed_files"] == ["src/app.py"]


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


def test_critical_paths_union_across_layers(tmp_path, monkeypatch):
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


def test_old_git_skips_ref_attributes_with_a_warning(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".gitattributes", "gen/** linguist-generated\n")
    target = _commit(repo, "target")
    monkeypatch.setattr(m, "_supports_attr_source", lambda root: False)
    rc, policy, ctx, _ = _resolve(tmp_path, repo, changed=("gen/client.py",), ref=target, apply=True,
                                  monkeypatch=monkeypatch)
    assert rc == 0
    assert any("git < 2.40" in w for w in policy["warnings"])
    assert ctx["changed_files"] == ["gen/client.py"]


def test_failed_attribute_lookup_warns_and_keeps_the_files(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    real_git = m._git

    def failing_check_attr(root, *args, **kwargs):
        if args and args[0] == "check-attr":
            return subprocess.CompletedProcess(args, 128, stdout="", stderr="fatal: boom")
        return real_git(root, *args, **kwargs)

    monkeypatch.setattr(m, "_git", failing_check_attr)
    rc, policy, ctx, _ = _resolve(tmp_path, repo, changed=("gen/client.py",), apply=True,
                                  monkeypatch=monkeypatch)
    assert rc == 0
    assert any("could not read linguist-generated attributes: fatal: boom" in w for w in policy["warnings"])
    assert ctx["changed_files"] == ["gen/client.py"]


def test_generated_files_with_non_ascii_names_are_excluded(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".gitattributes", "*.gen linguist-generated\n")
    _commit(repo)
    rc, _, ctx, _ = _resolve(tmp_path, repo, changed=("src/app.py", "\u00e9.gen", "a b.gen"), apply=True,
                             monkeypatch=monkeypatch)
    assert rc == 0
    assert ctx["changed_files"] == ["src/app.py"]
    assert sorted(ctx["excluded_generated"]) == ["a b.gen", "\u00e9.gen"]


def test_attribute_lookup_does_not_depend_on_argv_size(tmp_path):
    repo = _repo(tmp_path)
    _write(repo / ".gitattributes", "*.gen linguist-generated\n")
    paths = ["dir/%s/file-%d.gen" % ("x" * 80, i) for i in range(20000)]
    assert m._generated_paths(repo, paths, None, []) == set(paths)


def test_pack_files_with_spaces_and_directories_named_like_files_at_a_ref(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".quirk" / "review" / "lenses" / "my lens.md",
           "---\nid: spaced\nrun_when: always\n---\nChecklist.\n")
    _write(repo / ".quirk" / "review" / "lenses" / "dir.md" / "inner.txt", "not a lens\n")
    target = _commit(repo, "target")
    rc, policy, _, _ = _resolve(tmp_path, repo, ref=target, monkeypatch=monkeypatch)
    assert rc == 0
    assert _lens(policy, "spaced")["run_when"] == "always"


def test_explicit_pack_that_is_not_a_directory_exits_2(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    rc, policy, _, out = _resolve(tmp_path, repo, pack=tmp_path / "no-such-org-pack",
                                  monkeypatch=monkeypatch)
    assert rc == 2 and policy is None
    assert "no-such-org-pack" in json.loads(out)["error"]


def test_explicit_empty_pack_warns_that_nothing_was_applied(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    empty = tmp_path / "empty-pack"
    empty.mkdir()
    rc, policy, _, _ = _resolve(tmp_path, repo, pack=empty, monkeypatch=monkeypatch)
    assert rc == 0
    assert any("empty-pack" in w and "no pack policy" in w for w in policy["warnings"])


def test_reviewer_seat_follows_a_symlinked_review_md_to_its_in_repo_target(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / "docs" / "policy.md", "---\nseverity_floor: Must fix\n---\n")
    (repo / "REVIEW.md").symlink_to("docs/policy.md")
    target = _commit(repo, "target")
    rc, policy, _, _ = _resolve(tmp_path, repo, ref=target, monkeypatch=monkeypatch)
    assert rc == 0
    assert policy["severity_floor"] == "Must fix"
    assert all("docs/policy.md" not in Path(p).read_text() for p in policy["guidance_files"])


def test_reviewer_seat_rejects_a_symlink_that_leaves_the_repo(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / "REVIEW.md").symlink_to("../outside.md")
    target = _commit(repo, "target")
    rc, policy, _, out = _resolve(tmp_path, repo, ref=target, monkeypatch=monkeypatch)
    assert rc == 2 and policy is None
    assert "REVIEW.md" in json.loads(out)["error"]


def test_front_matter_after_a_byte_order_mark_still_applies(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / "REVIEW.md", "﻿---\nseverity_floor: Must fix\n---\nBody.\n")
    rc, policy, _, _ = _resolve(tmp_path, repo, monkeypatch=monkeypatch)
    assert rc == 0 and policy["severity_floor"] == "Must fix"


def test_non_string_lens_id_exits_2_naming_the_file(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _write(repo / ".quirk" / "review" / "lenses" / "bad.md",
           "---\nid:\n- a\n- b\nrun_when: always\n---\nChecklist.\n")
    rc, policy, _, out = _resolve(tmp_path, repo, monkeypatch=monkeypatch)
    assert rc == 2 and policy is None
    assert "bad.md" in json.loads(out)["error"]


@pytest.mark.parametrize("path,pattern,expected", [
    ("src/a.py", "src/**/*.py", True),
    ("src/x/y/a.py", "src/**/*.py", True),
    ("a.lock", "**/*.lock", True),
    ("src/a/b/c.py", "src/**/b/**/c.py", True),
    ("src/b/c.py", "src/**/b/**/c.py", True),
    ("other/a.py", "src/**/*.py", False),
])
def test_matches_lets_double_star_segments_span_zero_directories(path, pattern, expected):
    assert m._matches(path, pattern) is expected
