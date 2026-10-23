"""Prepare, dispatch, and apply the adjudicator's rulings over merged review findings."""

from __future__ import annotations

import argparse
import copy
import json
import random
import re
import sys
from pathlib import Path
from typing import NoReturn

import jsonio
from render_report import UNSAFE_LINE


_SEVERITY_RANK = {"Nit": 0, "Should fix": 1, "Must fix": 2}
_DISAGREEMENT_KIND = {"issue_wrong": "issue", "fix_wrong": "fix", "unreachable": "reachability"}
_RULINGS = ("agree", *_DISAGREEMENT_KIND)
_LABELS = ("Common path", "Edge case", "Unreachable", "Would miss", "N/A")
_TEST_DIMENSIONS = {"tests", "test-adequacy", "test-coverage"}
_IDENTITY = re.compile(r"(?i)\b(adjudicat\w*|lens(es)?|opus|sonnet|reviewer)\b")
_FINDING_ID = re.compile(r"A[1-9][0-9]*")
_PATH_CAP = 200
_FIX_MD_CAP = 160
_TITLE_CAP = 80
_NO_VERDICT_TEXT = "Prover did not return; check the objection by hand."
_NO_SETTLE_TEXT = "Prover returned no usable evidence; check the objection by hand."
_UNREACHABLE_REASON = "Proven unreachable from any real entry point."
_MERGE_REASON = "Merged with a stronger-severity finding."


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value


def _items(value: object, label: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("%s must be an array of JSON objects" % label)
    return value


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a non-empty string" % label)
    return value.strip()


def _one_line(value: object, limit: int | None, label: str) -> str:
    """Return `value` trimmed; it must be a non-empty line free of the characters the report renderer rejects, within `limit` if given."""
    text = _required_text(value, label)
    if UNSAFE_LINE.search(text):
        raise ValueError("%s must be a single line" % label)
    if limit is not None and len(text) > limit:
        raise ValueError("%s exceeds %d characters" % (label, limit))
    return text


def _elided(value: str, limit: int) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _load_json(path: str, label: str) -> object:
    try:
        with Path(path).open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError("could not read %s: %s" % (label, exc)) from exc


def _dimensions(finding: dict) -> list[str]:
    names = {finding["dimension"].strip()} if isinstance(finding.get("dimension"), str) else set()
    raw = finding.get("dimensions")
    if isinstance(raw, list):
        names.update(item.strip() for item in raw if isinstance(item, str))
    names.discard("")
    return sorted(names)


def _text_field(finding: dict, label: str, *keys: str) -> str:
    for key in keys:
        value = finding.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("%s needs %s" % (label, " or ".join(keys)))


def prepare(findings: list[dict], seed: int) -> dict:
    """Assign ids `A1..An` in input order, then return the findings shuffled by `seed`."""
    numbered = [{**finding, "id": "A%d" % number} for number, finding in enumerate(findings, 1)]
    random.Random(seed).shuffle(numbered)
    return {"seed": seed, "findings": numbered}


def _input_findings(doc: dict, label: str) -> dict[str, dict]:
    """Return the prepared findings keyed by id, in original (id) order."""
    findings = _items(doc.get("findings"), "%s findings" % label)
    keyed: dict[str, dict] = {}
    for finding in findings:
        identifier = finding.get("id")
        if not isinstance(identifier, str) or not _FINDING_ID.fullmatch(identifier):
            raise ValueError("%s finding id must look like A1, got %r" % (label, identifier))
        if identifier in keyed:
            raise ValueError("%s repeats finding id %s" % (label, identifier))
        keyed[identifier] = finding
    return dict(sorted(keyed.items(), key=lambda pair: int(pair[0][1:])))


def _optional_absent(value: object, label: str, ruling_kind: str, needed_for: str) -> None:
    if value is not None:
        raise ValueError("%s must be null unless the ruling is %s (ruling is %s)" % (label, needed_for, ruling_kind))


def _reject_identity(text: str, label: str) -> None:
    found = _IDENTITY.search(text)
    if found:
        raise ValueError("%s must state claims about the code only; it names %r" % (label, found[0]))


def _validate_ruling(raw: dict, finding: dict) -> dict:
    identifier = raw["id"]
    where = "rulings.json ruling %s" % identifier
    kind = raw.get("ruling")
    if kind not in _RULINGS:
        raise ValueError("%s: ruling must be one of %s" % (where, ", ".join(_RULINGS)))

    production = raw.get("production")
    if not isinstance(production, dict):
        raise ValueError("%s: production must be an object with label and path" % where)
    label = production.get("label")
    if label not in _LABELS:
        raise ValueError("%s: production.label must be one of %s" % (where, ", ".join(_LABELS)))
    path = _one_line(production.get("path"), _PATH_CAP, "%s: production.path" % where)
    dimensions = _dimensions(finding)
    if label == "N/A" and dimensions and path not in dimensions:
        raise ValueError("%s: production.path for N/A must be the finding's dimension (%s)" % (
            where, ", ".join(dimensions)))
    if label == "Would miss" and not _TEST_DIMENSIONS.intersection(dimensions):
        raise ValueError("%s: production.label Would miss needs a tests, test-adequacy, or test-coverage finding" % where)
    if (label == "Unreachable") != (kind == "unreachable"):
        raise ValueError("%s: production.label must be Unreachable exactly when the ruling is unreachable" % where)

    severity = raw.get("severity")
    reason = raw.get("severity_reason")
    if severity is None:
        if reason is not None:
            raise ValueError("%s: severity_reason must be null when severity is null" % where)
    else:
        if severity not in _SEVERITY_RANK:
            raise ValueError("%s: severity must be null, Must fix, Should fix, or Nit" % where)
        reason = _one_line(reason, 1000, "%s: severity_reason" % where)

    objection = raw.get("objection")
    trigger = raw.get("lens_trigger_path")
    replacement = raw.get("replacement")
    if kind == "agree":
        _optional_absent(objection, "%s: objection" % where, kind, "a disagreement")
    else:
        objection = _required_text(objection, "%s: objection" % where)
        _reject_identity(objection, "%s: objection" % where)
    if kind == "unreachable":
        trigger = _one_line(trigger, None, "%s: lens_trigger_path" % where)
        _reject_identity(trigger, "%s: lens_trigger_path" % where)
    else:
        _optional_absent(trigger, "%s: lens_trigger_path" % where, kind, "unreachable")
    if kind == "fix_wrong":
        replacement = _object(replacement, "%s: replacement" % where)
        fix_md = _one_line(replacement.get("fix_md"), _FIX_MD_CAP, "%s: replacement.fix_md" % where)
        recommendation = _required_text(replacement.get("recommendation"), "%s: replacement.recommendation" % where)
        _reject_identity(fix_md, "%s: replacement.fix_md" % where)
        _reject_identity(recommendation, "%s: replacement.recommendation" % where)
        replacement = {"fix_md": fix_md, "recommendation": recommendation}
    else:
        _optional_absent(replacement, "%s: replacement" % where, kind, "fix_wrong")

    return {"id": identifier, "ruling": kind, "production": {"label": label, "path": path},
            "severity": severity, "severity_reason": reason, "objection": objection,
            "lens_trigger_path": trigger, "replacement": replacement}


def _validate_rulings(findings: dict[str, dict], doc: dict) -> tuple[dict[str, dict], list[dict]]:
    """Check `rulings.json` against the prepared findings; return rulings by id and the proposed merges."""
    raw_rulings = _items(doc.get("rulings"), "rulings.json rulings")
    rulings: dict[str, dict] = {}
    for raw in raw_rulings:
        identifier = raw.get("id")
        if not isinstance(identifier, str) or identifier not in findings:
            raise ValueError("rulings.json rulings names unknown finding id %r" % (identifier,))
        if identifier in rulings:
            raise ValueError("rulings.json rulings repeats finding id %s" % identifier)
        rulings[identifier] = _validate_ruling(raw, findings[identifier])
    missing = [identifier for identifier in findings if identifier not in rulings]
    if missing:
        raise ValueError("rulings.json rulings has no ruling for %s" % ", ".join(missing))

    merges = _items(doc.get("merges", []), "rulings.json merges")
    for number, merge in enumerate(merges, 1):
        ids = merge.get("ids")
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            raise ValueError("rulings.json merges[%d].ids must be an array of strings" % number)
        _one_line(merge.get("anchor"), None, "rulings.json merges[%d].anchor" % number)
        _one_line(merge.get("reason"), None, "rulings.json merges[%d].reason" % number)
    return {identifier: rulings[identifier] for identifier in findings}, merges


def _claims(finding: dict, ruling: dict, where: str) -> tuple[str, str]:
    """Return the (lens claim, adjudicator claim) texts for one disagreement."""
    kind = ruling["ruling"]
    if kind == "fix_wrong":
        return (_text_field(finding, where, "recommendation", "recommendation_md"),
                ruling["replacement"]["recommendation"])
    issue = _text_field(finding, where, "issue", "body_md")
    if kind == "unreachable":
        issue = "%s\n\nTrigger path: %s" % (issue, ruling["lens_trigger_path"])
    return issue, ruling["objection"]


def build_jobs(input_doc: dict, rulings_doc: dict, seed: int, execution: str = "disabled") -> dict:
    """Return the prover jobs, one per disagreement, with the A/B side drawn per job from `seed`.

    `execution` is stamped on every packet and says whether provers may run repros.
    """
    findings = _input_findings(input_doc, "adjudication-input.json")
    rulings, _ = _validate_rulings(findings, rulings_doc)
    rng = random.Random(seed)
    jobs = []
    for identifier, ruling in rulings.items():
        if ruling["ruling"] == "agree":
            continue
        finding = findings[identifier]
        job_id = "J%d" % (len(jobs) + 1)
        lens_claim, adjudicator_claim = _claims(finding, ruling, "adjudication-input.json finding %s" % identifier)
        a_is = rng.choice(("lens", "adjudicator"))
        claim_a, claim_b = (lens_claim, adjudicator_claim) if a_is == "lens" else (adjudicator_claim, lens_claim)
        jobs.append({
            "job": job_id, "finding": identifier, "ruling": ruling, "a_is": a_is,
            "packet": {"job": job_id, "file": str(finding.get("file", "")), "line": str(finding.get("line", "")),
                       "kind": _DISAGREEMENT_KIND[ruling["ruling"]], "claim_a": claim_a, "claim_b": claim_b,
                       "execution": execution},
        })
    return {"seed": seed, "jobs": jobs}


def _load_jobs(doc: dict, rulings: dict[str, dict]) -> dict[str, dict]:
    """Return the jobs keyed by finding id; they must cover exactly the disagreement rulings, one job each."""
    jobs = _items(doc.get("jobs"), "prover-jobs.json jobs")
    by_finding: dict[str, dict] = {}
    seen: set[str] = set()
    for job in jobs:
        identifier = _required_text(job.get("job"), "prover-jobs.json job id")
        if identifier in seen:
            raise ValueError("prover-jobs.json repeats job id %s" % identifier)
        seen.add(identifier)
        finding_id = job.get("finding")
        if job.get("a_is") not in ("lens", "adjudicator"):
            raise ValueError("prover-jobs.json job %s a_is must be lens or adjudicator" % identifier)
        if not isinstance(finding_id, str) or finding_id not in rulings:
            raise ValueError("prover-jobs.json job %s names unknown finding %r" % (identifier, finding_id))
        kind = rulings[finding_id]["ruling"]
        if kind == "agree":
            raise ValueError("prover-jobs.json job %s is for %s, which the rulings agree with" % (identifier, finding_id))
        job_ruling = job.get("ruling")
        if not isinstance(job_ruling, dict) or job_ruling.get("ruling") != kind:
            raise ValueError("prover-jobs.json job %s ruling does not match the %s ruling for %s" % (identifier, kind, finding_id))
        if finding_id in by_finding:
            raise ValueError("prover-jobs.json job %s is a second job for %s" % (identifier, finding_id))
        by_finding[finding_id] = job
    for identifier, ruling in rulings.items():
        if ruling["ruling"] != "agree" and identifier not in by_finding:
            raise ValueError("prover-jobs.json has no job for disagreement %s" % identifier)
    return by_finding


def _load_verdicts(doc: dict, jobs: dict[str, dict]) -> dict[str, dict]:
    """Return verdicts keyed by job id; an unknown or repeated job id is an error."""
    known = {job["job"] for job in jobs.values()}
    verdicts: dict[str, dict] = {}
    for verdict in _items(doc.get("verdicts"), "verdicts.json verdicts"):
        identifier = verdict.get("job")
        if not isinstance(identifier, str) or identifier not in known:
            raise ValueError("verdicts.json verdicts names unknown job %r" % (identifier,))
        if identifier in verdicts:
            raise ValueError("verdicts.json verdicts repeats job %s" % identifier)
        verdicts[identifier] = verdict
    return verdicts


def _text_or_none(value: object) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) and value.strip() else None


def _settle(job: dict, verdict: dict | None, warnings: list[str]) -> tuple[str, str | None, dict | None]:
    """Reduce a prover verdict to (state, proof, verdict); state is lens, adjudicator, inconclusive, or missing.

    A verdict that is unparseable or says A/B without evidence is never a win for either side.
    """
    if verdict is None:
        return "missing", None, None
    choice, kind = verdict.get("verdict"), verdict.get("evidence_kind")
    if choice not in ("A", "B", "inconclusive") or kind not in ("repro", "quote", "none"):
        warnings.append("verdict for %s is unusable and was treated as missing" % job["job"])
        return "missing", None, None
    evidence = verdict.get("evidence")
    proof = evidence.strip() if isinstance(evidence, str) and evidence.strip() else None
    if choice == "inconclusive" or kind == "none" or proof is None:
        return "inconclusive", proof, verdict
    winner = job["a_is"] if choice == "A" else ("adjudicator" if job["a_is"] == "lens" else "lens")
    return winner, proof, verdict


def _resolve(finding: dict, ruling: dict, job: dict | None, verdict: dict | None, warnings: list[str]) -> dict:
    """Apply one row of the outcome table; return the outcome and the pieces the caller records."""
    kind = ruling["ruling"]
    result = {"outcome": "agreed", "production": ruling["production"], "proof": None,
              "what_would_settle": None, "force_nit": False, "replace_fix": False, "drop": False}
    if kind == "agree":
        return result
    state, proof, verdict = _settle(job, verdict, warnings)
    result["proof"] = proof
    if kind == "unreachable":
        result["production"] = {"label": "Edge case", "path": _elided(ruling["lens_trigger_path"], _PATH_CAP)}

    if state == "adjudicator":
        result["outcome"] = {"issue_wrong": "dropped", "fix_wrong": "fix_replaced", "unreachable": "unreachable"}[kind]
        result["production"] = ruling["production"]
        result["drop"] = kind == "issue_wrong"
        result["replace_fix"] = kind == "fix_wrong"
        result["force_nit"] = kind == "unreachable"
    elif state == "lens" or (state == "inconclusive" and kind == "fix_wrong"):
        result["outcome"] = "survived"
        proven = _text_or_none(verdict.get("production_path")) if state == "lens" and verdict else None
        if kind == "unreachable" and proven:
            result["production"] = {"label": "Edge case", "path": _elided(proven, _PATH_CAP)}
    else:
        result["outcome"] = "disputed"
        settle = _text_or_none(verdict.get("what_would_settle")) if verdict else None
        result["what_would_settle"] = settle or (_NO_VERDICT_TEXT if state == "missing" else _NO_SETTLE_TEXT)
    return result


def _merge_groups(merges: list[dict], outcomes: dict[str, str], warnings: list[str]) -> list[tuple[str, list[str]]]:
    """Return the usable merges as (anchor, members); unusable ones become warnings."""
    groups: list[tuple[str, list[str]]] = []
    consumed: set[str] = set()
    for number, merge in enumerate(merges, 1):
        ids = list(dict.fromkeys(merge["ids"]))
        anchor = merge["anchor"].strip()
        problem = None
        if len(ids) < 2 or anchor not in ids:
            problem = "needs two or more ids that include its anchor"
        else:
            unknown = [item for item in ids if item not in outcomes]
            disagreed = [item for item in ids if item in outcomes and outcomes[item] != "agreed"]
            reused = [item for item in ids if item in consumed]
            if unknown:
                problem = "names unknown finding %s" % ", ".join(unknown)
            elif disagreed:
                problem = "includes %s, which was not agreed" % ", ".join(disagreed)
            elif reused:
                problem = "includes %s, already merged" % ", ".join(reused)
        if problem:
            warnings.append("merge %d skipped: %s" % (number, problem))
            continue
        consumed.update(ids)
        groups.append((anchor, [item for item in ids if item != anchor]))
    return groups


def apply_rulings(input_doc: dict, rulings_doc: dict, jobs_doc: dict, verdicts_doc: dict) -> dict:
    """Apply rulings and prover verdicts; return `{findings, adjudication, warnings}` in input order."""
    findings = _input_findings(input_doc, "adjudication-input.json")
    rulings, merges = _validate_rulings(findings, rulings_doc)
    jobs = _load_jobs(jobs_doc, rulings)
    verdicts = _load_verdicts(verdicts_doc, jobs)
    warnings: list[str] = []

    kept: dict[str, dict] = {}
    outcomes: dict[str, str] = {}
    original_severity: dict[str, str | None] = {}
    dropped: list[dict] = []
    for identifier, source in findings.items():
        ruling = rulings[identifier]
        job = jobs.get(identifier)
        resolved = _resolve(source, ruling, job, verdicts.get(job["job"]) if job else None, warnings)
        outcomes[identifier] = resolved["outcome"]
        if resolved["drop"]:
            title = source.get("title") if isinstance(source.get("title"), str) and source["title"].strip() else None
            dropped.append({
                "file": str(source.get("file", "")), "line": str(source.get("line", "")),
                "title": title.strip() if title else _elided(str(source.get("issue", "")), _TITLE_CAP),
                "reason": ruling["objection"], "proof": resolved["proof"]})
            continue

        finding = copy.deepcopy(source)
        del finding["id"]
        was = finding.get("severity")
        original_severity[identifier] = was
        change = None
        target = "Nit" if resolved["force_nit"] else ruling["severity"]
        if target is not None and target != was:
            reason = _UNREACHABLE_REASON if resolved["force_nit"] else ruling["severity_reason"]
            change = {"from": was, "to": target, "reason": reason}
            finding["severity"] = target
        original_fix = None
        if resolved["replace_fix"]:
            original_fix = {"fix_md": finding.get("fix_md") if isinstance(finding.get("fix_md"), str) else None,
                            "recommendation": finding.get("recommendation")}
            replacement = ruling["replacement"]
            finding["recommendation"] = replacement["recommendation"]
            if "recommendation_md" in finding:
                finding["recommendation_md"] = replacement["recommendation"]
            finding["fix_md"] = replacement["fix_md"]
        finding["production"] = copy.deepcopy(resolved["production"])
        finding["adjudication"] = {
            "outcome": resolved["outcome"],
            "objection": ruling["objection"],
            "proof": resolved["proof"],
            "what_would_settle": resolved["what_would_settle"],
            "severity_change": change,
            "original_fix": original_fix,
        }
        kept[identifier] = finding

    merged_away: set[str] = set()
    for anchor, members in _merge_groups(merges, outcomes, warnings):
        target = kept[anchor]
        group = [target, *(kept[member] for member in members)]
        names = sorted({name for item in group for name in _dimensions(item)})
        target["dimensions"] = names
        target["dimension"] = names[0] if names else target.get("dimension")
        strongest = max((item.get("severity") for item in group), key=lambda value: _SEVERITY_RANK.get(value, -1))
        if strongest in _SEVERITY_RANK and strongest != target.get("severity"):
            existing = target["adjudication"]["severity_change"]
            target["severity"] = strongest
            target["adjudication"]["severity_change"] = {
                "from": original_severity[anchor], "to": strongest,
                "reason": existing["reason"] if existing else _MERGE_REASON}
        target["adjudication"]["merged_from"] = [
            {"file": kept[member].get("file"), "line": kept[member].get("line"),
             "dimension": (_dimensions(kept[member]) or [None])[0]} for member in members]
        merged_away.update(members)

    counts = list(outcomes.values())
    tally = {"checked": len(findings), "agreed": counts.count("agreed"), "dropped": counts.count("dropped"),
             "fixes_replaced": counts.count("fix_replaced"), "unreachable": counts.count("unreachable"),
             "survived": counts.count("survived"), "disputed": counts.count("disputed"),
             "merged": len(merged_away)}
    return {
        "findings": [kept[identifier] for identifier in findings if identifier in kept and identifier not in merged_away],
        "adjudication": {"status": "complete", "model": None, "reason": None, "tally": tally,
                         "checked_and_dropped": dropped},
        "warnings": warnings,
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_cmd = commands.add_parser("prepare", help="assign ids and shuffle merged findings")
    prepare_cmd.add_argument("--findings", required=True)
    prepare_cmd.add_argument("--out", required=True)
    prepare_cmd.add_argument("--seed", type=int)
    jobs_cmd = commands.add_parser("jobs", help="build one prover packet per disagreement")
    for name in ("input", "rulings", "out"):
        jobs_cmd.add_argument("--" + name, required=True)
    jobs_cmd.add_argument("--seed", type=int)
    jobs_cmd.add_argument("--execution", choices=("enabled", "disabled"), default="disabled")
    apply_cmd = commands.add_parser("apply", help="apply rulings and verdicts to the findings")
    for name in ("input", "rulings", "jobs", "verdicts", "out"):
        apply_cmd.add_argument("--" + name, required=True)
    return parser


def _seed(value: int | None) -> int:
    return value if value is not None else random.SystemRandom().randrange(2 ** 32)


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand; print `{"error": ...}` and return 2 when an input is malformed."""
    try:
        args = _parser().parse_args(argv)
        if args.command == "prepare":
            raw = _load_json(args.findings, "findings")
            if isinstance(raw, dict):
                raw = raw.get("findings")
            result = prepare(_items(raw, "findings"), _seed(args.seed))
        elif args.command == "jobs":
            result = build_jobs(
                _object(_load_json(args.input, "adjudication input"), "adjudication input"),
                _object(_load_json(args.rulings, "rulings.json"), "rulings.json"), _seed(args.seed),
                args.execution)
        else:
            result = apply_rulings(
                _object(_load_json(args.input, "adjudication input"), "adjudication input"),
                _object(_load_json(args.rulings, "rulings.json"), "rulings.json"),
                _object(_load_json(args.jobs, "prover-jobs.json"), "prover-jobs.json"),
                _object(_load_json(args.verdicts, "verdicts.json"), "verdicts.json"))
        jsonio.write_json(args.out, result)
        return 0
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
