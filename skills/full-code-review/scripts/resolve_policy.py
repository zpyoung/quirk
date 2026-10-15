#!/usr/bin/env python3
"""Resolve the effective review policy and optionally filter the review context.

Layers, lowest to highest: the built-in lens roster, the user pack (or --pack), the
project pack at <source-root>/.quirk/review/, then REVIEW.md files (the root one plus any
in an ancestor directory of a changed file; deeper overrides shallower key by key).

With --policy-ref (reviewer seat: the target branch SHA) the project pack and REVIEW.md
are read from that ref, never the working tree, so a change cannot weaken its own review.
Files read from a ref are written under <out-dir>/policy-files/ so lenses can read them.

Exit 0 on success; exit 2 with {"error": ...} naming the file and line on a bad pack.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import policy_yaml
from prepare_diff import count_changed_lines, split_diff_by_file

FLOORS = ("Must fix", "Should fix", "Nit")
MODELS = ("sonnet", "opus", "haiku")
RUN_WHEN = ("always", "has_description", "code_changed", "source_or_config_changed",
            "tests_changed", "source_without_tests", "not_diff_only")
KNOWN_KEYS = ("severity_floor", "escalation", "models", "skip", "cross_family",
              "critical_paths", "skip_globs", "cross_repo")
PROJECT_PACK = ".quirk/review"


class PolicyError(Exception):
    pass


def _git(root, *args, timeout=30):
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True,
                          text=True, timeout=timeout)


class _FsSource:
    """Reads files from a directory on disk."""

    def __init__(self, root):
        self.root = Path(root)
        self.ref = None

    def read(self, rel):
        path = self.root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def listdir(self, rel, suffix=".md"):
        base = self.root / rel
        if not base.is_dir():
            return []
        return sorted("%s/%s" % (rel, p.name) for p in base.iterdir()
                      if p.is_file() and p.name.endswith(suffix))

    def readable_path(self, rel, text):
        return str(self.root / rel)


class _RefSource:
    """Reads files from a git ref; materializes them under `stash` for lenses to read."""

    def __init__(self, root, ref, stash):
        self.root = Path(root)
        self.ref = ref
        self.stash = Path(stash)

    def read(self, rel):
        result = _git(self.root, "show", "%s:%s" % (self.ref, rel))
        return result.stdout if result.returncode == 0 else None

    def listdir(self, rel, suffix=".md"):
        result = _git(self.root, "ls-tree", "--name-only", "%s:%s" % (self.ref, rel))
        if result.returncode != 0:
            return []
        return sorted("%s/%s" % (rel, name) for name in result.stdout.split() if name.endswith(suffix))

    def readable_path(self, rel, text):
        target = self.stash / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return str(target)


def _parse_yaml(text, label, line_offset=0):
    try:
        value = policy_yaml.parse(text, label)
    except policy_yaml.TemplateParseError as exc:
        raise PolicyError("%s:%d: %s" % (label, exc.line + line_offset, exc.message))
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PolicyError("%s: expected a mapping of settings" % label)
    return value


def split_front_matter(text, label):
    """Return (settings, body) for a Markdown file with optional `---` front matter."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        raise PolicyError("%s:1: front matter is not closed with ---" % label)
    block = text[4:end + 1]
    body = text[end + 4:].lstrip("\n")
    return _parse_yaml(block, label, line_offset=1), body


def _list_of_strings(value, label, key):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PolicyError("%s: %s must be a list of strings" % (label, key))
    return value


class Policy:
    def __init__(self):
        self.lenses = {}
        self.order = []
        self.settings = {"severity_floor": "Should fix", "escalation": True, "models": {},
                         "cross_family": {"enabled": False, "alias": None},
                         "critical_paths": [], "skip_globs": [],
                         "cross_repo": {"search_agent": None}}
        self.skipped = {}
        self.sources = []
        self.guidance = []
        self.warnings = []

    def apply_settings(self, values, label):
        for key in values:
            if key not in KNOWN_KEYS:
                self.warnings.append("%s: unknown key ignored: %s" % (label, key))
        if "severity_floor" in values:
            if values["severity_floor"] not in FLOORS:
                raise PolicyError("%s: severity_floor must be one of %s" % (label, ", ".join(FLOORS)))
            self.settings["severity_floor"] = values["severity_floor"]
        if "escalation" in values:
            if not isinstance(values["escalation"], bool):
                raise PolicyError("%s: escalation must be true or false" % label)
            self.settings["escalation"] = values["escalation"]
        if "models" in values:
            models = values["models"]
            if not isinstance(models, dict):
                raise PolicyError("%s: models must be a mapping of lens id to model" % label)
            for lens_id, model in models.items():
                if model not in MODELS:
                    raise PolicyError("%s: models.%s must be one of %s" % (label, lens_id, ", ".join(MODELS)))
                self.settings["models"][lens_id] = model
        if "skip" in values:
            for lens_id in _list_of_strings(values["skip"], label, "skip"):
                self.skipped.setdefault(lens_id, label)
        for key in ("critical_paths", "skip_globs"):
            if key in values:
                for item in _list_of_strings(values[key], label, key):
                    if item not in self.settings[key]:
                        self.settings[key].append(item)
        if "cross_family" in values:
            value = values["cross_family"]
            if (not isinstance(value, dict) or not isinstance(value.get("enabled", False), bool)
                    or not isinstance(value.get("alias"), (str, type(None)))):
                raise PolicyError("%s: cross_family needs enabled (true/false) and an alias string" % label)
            self.settings["cross_family"].update({k: value[k] for k in ("enabled", "alias") if k in value})
        if "cross_repo" in values:
            value = values["cross_repo"]
            if not isinstance(value, dict) or not isinstance(value.get("search_agent"), (str, type(None))):
                raise PolicyError("%s: cross_repo.search_agent must be a subagent type or null" % label)
            self.settings["cross_repo"]["search_agent"] = value.get("search_agent")

    def add_lens(self, meta, checklist, source, label, builtin=False):
        lens_id = meta.get("id") or Path(label).stem
        if lens_id in self.lenses:
            lens = self.lenses[lens_id]
            lens.update({"checklist": checklist, "source": source})
        else:
            if builtin is False and meta.get("run_when") is None:
                raise PolicyError("%s: an added lens must declare run_when" % label)
            lens = {"id": lens_id, "checklist": checklist, "model": "sonnet", "escalate": False,
                    "run_when": None, "batched": True, "source": source}
            self.lenses[lens_id] = lens
            self.order.append(lens_id)
        for key in ("model", "escalate", "run_when", "batched"):
            if key in meta:
                lens[key] = meta[key]
        if lens["run_when"] not in RUN_WHEN:
            raise PolicyError("%s: run_when must be one of %s" % (label, ", ".join(RUN_WHEN)))
        if lens["model"] not in MODELS:
            raise PolicyError("%s: model must be one of %s" % (label, ", ".join(MODELS)))
        for key in ("escalate", "batched"):
            if not isinstance(lens[key], bool):
                raise PolicyError("%s: %s must be true or false" % (label, key))

    def load_pack(self, source, base, kind):
        """Apply one pack (pack.yaml, lenses/*.md, guidance/*.md) rooted at `base`."""
        prefix = "%s/" % base if base else ""
        found = False
        text = source.read(prefix + "pack.yaml")
        label_root = str(source.root / base) if base else str(source.root)
        if text is not None:
            found = True
            self.apply_settings(_parse_yaml(text, "%s/pack.yaml" % label_root), "%s/pack.yaml" % label_root)
        for rel in source.listdir(prefix + "lenses"):
            found = True
            lens_text = source.read(rel)
            label = str(source.root / rel)
            meta, _ = split_front_matter(lens_text, label)
            self.add_lens(meta, source.readable_path(rel, lens_text), kind, label)
        for rel in source.listdir(prefix + "guidance"):
            found = True
            self.guidance.append(source.readable_path(rel, source.read(rel)))
        if found:
            self.sources.append({"kind": kind, "path": label_root, "ref": source.ref})

    def finish(self):
        for lens_id, model in self.settings["models"].items():
            if lens_id in self.lenses:
                self.lenses[lens_id]["model"] = model
            else:
                self.warnings.append("models: unknown lens %s ignored" % lens_id)
        for lens_id in self.skipped:
            if lens_id not in self.lenses:
                self.warnings.append("skip: unknown lens %s ignored" % lens_id)
        return {
            "schema": 1,
            "lenses": [self.lenses[i] for i in self.order if i not in self.skipped],
            "skipped": [{"id": i, "by": self.skipped[i]} for i in self.order if i in self.skipped],
            "severity_floor": self.settings["severity_floor"],
            "escalation": self.settings["escalation"],
            "cross_family": self.settings["cross_family"],
            "critical_paths": self.settings["critical_paths"],
            "skip_globs": self.settings["skip_globs"],
            "cross_repo": self.settings["cross_repo"],
            "sources": self.sources,
            "guidance_files": self.guidance,
            "warnings": self.warnings,
        }


def _review_md_dirs(changed_files):
    dirs = {""}
    for path in changed_files:
        parts = path.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:depth]))
    return sorted(dirs, key=lambda d: (d.count("/") + (1 if d else 0), d))


def _user_pack_dir(pack_flag):
    if pack_flag:
        return Path(pack_flag)
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(config) / "quirk" / "review"


def resolve_policy(context, source_root, lenses_dir, out_dir, policy_ref=None, pack=None):
    """Return the merged policy dict; raises PolicyError on a malformed pack or REVIEW.md."""
    policy = Policy()
    lenses_dir = Path(lenses_dir)
    for path in sorted(lenses_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        meta, _ = split_front_matter(path.read_text(encoding="utf-8"), str(path))
        if meta.get("id") != path.stem:
            raise PolicyError("%s: front matter id must equal the file name" % path)
        policy.add_lens(meta, str(path), "builtin", str(path), builtin=True)
    policy.sources.append({"kind": "builtin", "path": str(lenses_dir), "ref": None})

    user_dir = _user_pack_dir(pack)
    if user_dir.is_dir():
        policy.load_pack(_FsSource(user_dir), "", "user-pack")

    repo = (_RefSource(source_root, policy_ref, Path(out_dir) / "policy-files") if policy_ref
            else _FsSource(source_root))
    policy.load_pack(repo, PROJECT_PACK, "project-pack")
    for directory in _review_md_dirs(context.get("changed_files") or []):
        rel = "%s/REVIEW.md" % directory if directory else "REVIEW.md"
        text = repo.read(rel)
        if text is None:
            continue
        label = str(Path(source_root) / rel)
        settings, _ = split_front_matter(text, label)
        policy.apply_settings(settings, label)
        policy.sources.append({"kind": "review-md", "path": label, "ref": policy_ref})
        policy.guidance.append(repo.readable_path(rel, text))
    return policy.finish()


def _matches(path, pattern):
    if fnmatch.fnmatchcase(path, pattern):
        return True
    return pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:])


def _supports_attr_source(root):
    result = _git(root, "version")
    match = re.search(r"(\d+)\.(\d+)", result.stdout or "")
    return bool(match) and (int(match.group(1)), int(match.group(2))) >= (2, 40)


def _generated_paths(root, paths, policy_ref, warnings):
    if not paths:
        return set()
    args = ["check-attr"]
    if policy_ref:
        if not _supports_attr_source(root):
            warnings.append("git < 2.40 cannot read .gitattributes from the target ref; "
                            "linguist-generated exclusion skipped, skip_globs still applied")
            return set()
        args += ["--source", policy_ref]
    result = _git(root, *(args + ["linguist-generated", "--"] + list(paths)))
    if result.returncode != 0:
        warnings.append("could not read linguist-generated attributes: %s" % result.stderr.strip()[:200])
        return set()
    generated = set()
    for line in result.stdout.splitlines():
        path, _, rest = line.rpartition(": linguist-generated: ")
        if path and rest.strip() in ("set", "true"):
            generated.add(path)
    return generated


def apply_policy(context, policy, source_root, policy_ref=None):
    """Drop generated and skip-glob files from `context` in place; return the excluded list."""
    changed = list(context.get("changed_files") or [])
    warnings = policy.setdefault("warnings", [])
    generated = _generated_paths(source_root, changed, policy_ref, warnings)
    excluded = [p for p in changed
                if p in generated or any(_matches(p, g) for g in policy.get("skip_globs") or [])]
    drop = set(excluded)
    for key in ("changed_files", "test_files", "source_files", "diff_unavailable", "not_text_reviewable"):
        if isinstance(context.get(key), list):
            context[key] = [p for p in context[key] if p not in drop]
    sections = split_diff_by_file(context.get("diff") or "")
    kept = [text for path, text in sections.items() if path not in drop]
    context["diff"] = ("\n".join(kept) + "\n") if kept else ""
    if context.get("batches"):
        batches = []
        for batch in context["batches"]:
            files = [f for f in batch.get("files", []) if f not in drop]
            if files:
                batch_sections = split_diff_by_file(batch.get("diff") or "")
                batches.append({"files": files,
                                "diff": "\n".join(batch_sections[f] for f in files if f in batch_sections)})
        context["batches"] = batches
    context["size"] = {"files": len(context.get("changed_files") or []),
                       "lines": count_changed_lines(context["diff"])}
    context["excluded_generated"] = excluded
    return excluded


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(str(temp), str(path))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Resolve review policy from lenses, packs, and REVIEW.md.")
    ap.add_argument("--context", required=True)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--policy-ref")
    ap.add_argument("--pack")
    ap.add_argument("--lenses-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    try:
        with open(args.context, encoding="utf-8") as fh:
            context = json.load(fh)
        policy = resolve_policy(context, args.source_root, args.lenses_dir,
                                os.path.dirname(os.path.abspath(args.out)),
                                policy_ref=args.policy_ref, pack=args.pack)
        if args.apply:
            apply_policy(context, policy, args.source_root, args.policy_ref)
            _write_json(args.context, context)
        _write_json(args.out, policy)
    except (PolicyError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps({"out": os.path.abspath(args.out), "lenses": len(policy["lenses"]),
                      "excluded_generated": context.get("excluded_generated", []),
                      "warnings": policy["warnings"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
