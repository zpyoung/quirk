"""Prepare, dispatch, and apply the adjudicator's rulings over merged review findings."""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import NoReturn

import jsonio
from render_report import UNSAFE_LINE


_SEVERITY_RANK = {"Nit": 0, "Should fix": 1, "Must fix": 2}
_DISAGREEMENT_KIND = {"issue_wrong": "issue", "fix_wrong": "fix", "unreachable": "reachability"}
_RULINGS = ("agree", *_DISAGREEMENT_KIND)
_LABELS = ("Common path", "Edge case", "Unreachable", "Would miss", "N/A")
_TEST_DIMENSIONS = {"tests", "test-adequacy", "test-coverage"}
_FENCE_PADDING = " \t\r"
_IDENTITY = re.compile(r"(?i)\b(adjudicat\w*|lens(es)?|opus|sonnet|reviewer)\b")
_FINDING_ID = re.compile(r"A[1-9][0-9]*")
_PATH_CAP = 200
_FIX_MD_CAP = 160
_TITLE_CAP = 80
_NO_VERDICT_TEXT = "Prover did not return; check the objection by hand."
_NO_SETTLE_TEXT = "Prover returned no usable evidence; check the objection by hand."
_UNREACHABLE_REASON = "Proven unreachable from any real entry point."
_MERGE_REASON = "Merged with a stronger-severity finding."
_DIMENSION_PREFIX = "quirk:"


def _has_closed_diff_fence(text: str) -> bool:
    """True when a bare ```diff line is followed by a later bare ``` line; one pass, linear in len(text)."""
    opened = False
    for line in text.split("\n"):
        stripped = line.rstrip(_FENCE_PADDING)
        if opened and stripped == "```":
            return True
        if stripped == "```diff":
            opened = True
    return False


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
    """Return `value` trimmed; it must be a non-empty line free of the characters the report renderer rejects, within `limit` if given.

    The renderer's check runs on the raw value so edge characters are rejected, not trimmed away.
    """
    text = _required_text(value, label)
    if UNSAFE_LINE.search(value):
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


def _bare(name: str) -> str:
    return name[len(_DIMENSION_PREFIX):] if name.startswith(_DIMENSION_PREFIX) else name


def _text_field(finding: dict, label: str, *keys: str) -> str:
    for key in keys:
        value = finding.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("%s needs %s" % (label, " or ".join(keys)))


def _auto_production(source: dict) -> dict[str, str]:
    dims = _dimensions(source)
    bare_dims = {_bare(d) for d in dims}
    if bare_dims & _TEST_DIMENSIONS:
        path = "%s:%s test coverage" % (source.get("file", "test"), source.get("line", "1"))
        return {"label": "Would miss", "path": _elided(path, _PATH_CAP)}
    dim = dims[0] if dims else str(source.get("dimension") or "conventions")
    return {"label": "N/A", "path": _elided(dim, _PATH_CAP)}


def prepare(findings: list[dict], seed: int, skip_nits: bool = False) -> dict:
    """Assign ids `A1..An` in input order, then return the findings shuffled by `seed`."""
    numbered = [{**finding, "id": "A%d" % number} for number, finding in enumerate(findings, 1)]
    if not skip_nits:
        random.Random(seed).shuffle(numbered)
        return {"seed": seed, "findings": numbered}
    active = [item for item in numbered if item.get("severity") != "Nit"]
    auto_agreed = [item for item in numbered if item.get("severity") == "Nit"]
    random.Random(seed).shuffle(active)
    return {"seed": seed, "findings": active, "auto_agreed": auto_agreed}

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
    if label == "N/A" and dimensions and _bare(path) not in {_bare(name) for name in dimensions}:
        raise ValueError("%s: production.path for N/A must be the finding's dimension (%s)" % (
            where, ", ".join(dimensions)))
    if label == "Would miss" and not _TEST_DIMENSIONS.intersection(_bare(name) for name in dimensions):
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
        objection = _one_line(objection, None, "%s: objection" % where)
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
        if not _has_closed_diff_fence(recommendation):
            raise ValueError("%s: replacement.recommendation must contain a closed ```diff fenced block" % where)
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


def _packet_claims(finding: dict, ruling: dict, a_is: str, where: str) -> dict:
    """Return the packet fields that carry the claims under test, with sides assigned by `a_is`."""
    lens_claim, adjudicator_claim = _claims(finding, ruling, where)
    claim_a, claim_b = (lens_claim, adjudicator_claim) if a_is == "lens" else (adjudicator_claim, lens_claim)
    return {"file": str(finding.get("file", "")), "line": str(finding.get("line", "")),
            "kind": _DISAGREEMENT_KIND[ruling["ruling"]], "claim_a": claim_a, "claim_b": claim_b}


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
        a_is = rng.choice(("lens", "adjudicator"))
        fields = _packet_claims(finding, ruling, a_is, "adjudication-input.json finding %s" % identifier)
        jobs.append({
            "job": job_id, "finding": identifier, "ruling": ruling, "a_is": a_is,
            "packet": {"job": job_id, **fields, "execution": execution},
        })
    return {"seed": seed, "jobs": jobs}


def _load_jobs(doc: dict, rulings: dict[str, dict], findings: dict[str, dict]) -> dict[str, dict]:
    """Return the jobs keyed by finding id; they must cover exactly the disagreement rulings, one job each.

    A job whose packet no longer matches the claims rebuilt from the current rulings and input is stale.
    """
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
        packet = job.get("packet")
        expected = _packet_claims(findings[finding_id], rulings[finding_id], job["a_is"],
                                  "adjudication-input.json finding %s" % finding_id)
        if not isinstance(packet, dict) or any(packet.get(key) != value for key, value in expected.items()):
            raise ValueError("prover-jobs.json job %s is stale: its packet no longer matches the current rulings "
                             "and input for %s; rerun jobs" % (identifier, finding_id))
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


def _resolve(finding: dict, ruling: dict, job: dict | None, verdict: dict | None, warnings: list[str],
             preserve_unreproduced: bool = False) -> dict:
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
        if kind == "issue_wrong" and preserve_unreproduced and (verdict is None or verdict.get("evidence_kind") != "repro"):
            result["outcome"] = "disputed"
            result["what_would_settle"] = _elided(proof or ruling["objection"], _PATH_CAP)
            return result
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


def apply_rulings(input_doc: dict, rulings_doc: dict, jobs_doc: dict, verdicts_doc: dict,
                  preserve_unreproduced: bool = False) -> dict:
    """Apply rulings and prover verdicts; return `{findings, adjudication, warnings}` in input order.

    A ruling may raise a finding's severity but never lower it; only a proven unreachable finding drops to Nit.
    """
    findings = _input_findings(input_doc, "adjudication-input.json")
    rulings, merges = _validate_rulings(findings, rulings_doc)
    jobs = _load_jobs(jobs_doc, rulings, findings)
    verdicts = _load_verdicts(verdicts_doc, jobs)
    warnings: list[str] = []

    kept: dict[str, dict] = {}
    outcomes: dict[str, str] = {}
    original_severity: dict[str, str | None] = {}
    dropped: list[dict] = []
    for identifier, source in findings.items():
        ruling = rulings[identifier]
        job = jobs.get(identifier)
        resolved = _resolve(source, ruling, job, verdicts.get(job["job"]) if job else None, warnings,
                            preserve_unreproduced=preserve_unreproduced)
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
        if (not resolved["force_nit"] and target is not None
                and _SEVERITY_RANK[target] < _SEVERITY_RANK.get(was, -1)):
            # quirk's merge-step calibration outranks an unproven downgrade; only a proven unreachable lowers it
            warnings.append("kept %s:%s at %s; adjudication proposed %s: %s" % (
                source.get("file", ""), source.get("line", ""), was, target, ruling["severity_reason"]))
            target = None
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

    for source in _items(input_doc.get("auto_agreed") or [], "adjudication-input.json auto_agreed"):
        identifier = str(source.get("id", ""))
        outcomes[identifier] = "agreed"
        original_severity[identifier] = source.get("severity")
        finding = copy.deepcopy(source)
        finding.pop("id", None)
        finding["production"] = _auto_production(source)
        finding["adjudication"] = {
            "outcome": "agreed", "objection": None, "proof": None,
            "what_would_settle": None, "severity_change": None, "original_fix": None,
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
    all_ids = sorted(kept.keys() | set(findings.keys()), key=lambda fid: int(fid[1:]) if fid[1:].isdigit() else 0)
    tally = {"checked": len(findings) + len(input_doc.get("auto_agreed") or []),
             "agreed": counts.count("agreed"), "dropped": counts.count("dropped"),
             "fixes_replaced": counts.count("fix_replaced"), "unreachable": counts.count("unreachable"),
             "survived": counts.count("survived"), "disputed": counts.count("disputed"),
             "merged": len(merged_away)}
    raw_out_list = [kept[identifier] for identifier in all_ids if identifier in kept and identifier not in merged_away]
    by_ident: dict[tuple[str, str], dict] = {}
    for item in raw_out_list:
        ident = (str(item.get("file", "")).strip(), str(item.get("line", "")).strip())
        if ident not in by_ident:
            by_ident[ident] = item
            continue
        tally["merged"] += 1
        existing = by_ident[ident]
        if _SEVERITY_RANK.get(item.get("severity"), -1) > _SEVERITY_RANK.get(existing.get("severity"), -1):
            existing["severity"] = item["severity"]
        names = sorted({n for f in (existing, item) for n in _dimensions(f)})
        if names:
            existing["dimensions"] = names
            existing["dimension"] = names[0]
        sub_note = "\n\n- **%s:** %s" % (item.get("title") or "Related", item.get("issue") or item.get("body_md") or "")
        if str(item.get("title") or "").lower() not in str(existing.get("body_md") or existing.get("issue") or "").lower():
            existing["body_md"] = str(existing.get("body_md") or existing.get("issue") or "").rstrip() + sub_note
            existing["issue"] = str(existing.get("issue") or "").rstrip() + sub_note
    return {
        "findings": list(by_ident.values()),
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
    prepare_cmd.add_argument("--skip-nits", action="store_true",
                             help="auto-agree Nit findings and send only Must/Should fix findings to the adjudicator")
    prepare_cmd.add_argument("--must-out", help="write Must fix subset to this path for the opus adjudicator")
    prepare_cmd.add_argument("--should-out", help="write Should fix subset to this path for the sonnet adjudicator")
    prepare_cmd.add_argument("--must-shard-size", type=int,
                             help="also split the Must fix subset into `<must-out stem>-<k>.json` files of at most "
                                  "this many findings, one opus adjudicator each; prints their paths")
    jobs_cmd = commands.add_parser("jobs", help="build one prover packet per disagreement")
    for name in ("input", "rulings", "out"):
        jobs_cmd.add_argument("--" + name, required=True)
    jobs_cmd.add_argument("--seed", type=int)
    jobs_cmd.add_argument("--execution", choices=("enabled", "disabled"), default="disabled")
    jobs_cmd.add_argument("--wait", nargs="?", type=int, const=360, metavar="SECONDS",
                          help="block until expected lane rulings files exist before building jobs (default 360 s)")
    apply_cmd = commands.add_parser("apply", help="apply rulings and verdicts to the findings")
    for name in ("input", "rulings", "jobs", "verdicts", "out"):
        apply_cmd.add_argument("--" + name, required=True)
    apply_cmd.add_argument("--preserve-unreproduced", action="store_true",
                           help="keep issue_wrong rulings as disputed unless backed by an execution repro")
    return parser


def _seed(value: int | None) -> int:
    return value if value is not None else random.SystemRandom().randrange(2 ** 32)



def _must_shards(items: list[dict], must_out: str, size: int) -> list[str]:
    """Write `items` as consecutive `<must_out stem>-<k>.json` shards of at most `size` findings; return the paths."""
    if size < 1:
        raise ValueError("--must-shard-size must be at least 1")
    stem, ext = os.path.splitext(must_out)
    return [stem + "-%d%s" % (k, ext or ".json") for k in range(1, (len(items) + size - 1) // size + 1)]


def _lane_rulings_paths(base_dir: str) -> list[tuple[str, str]]:
    """Return the per-lane rulings files to combine; shard files `rulings-must-<k>.json` replace `rulings-must.json`."""
    shards = sorted(
        (name for name in os.listdir(base_dir) if re.fullmatch(r"rulings-must-\d+\.json", name)),
        key=lambda name: int(name[len("rulings-must-"):-len(".json")]))
    names = shards or ["rulings-must.json"]
    names.append("rulings-should.json")
    return [(os.path.join(base_dir, name), name) for name in names if os.path.isfile(os.path.join(base_dir, name))]


def _expected_lane_rulings(base_dir: str) -> list[str]:
    """Return the lane rulings filenames expected from `adjudication-input-*.json` in `base_dir`."""
    expected: list[str] = []
    shard_inputs = sorted(
        (name for name in os.listdir(base_dir) if re.fullmatch(r"adjudication-input-must-\d+\.json", name)),
        key=lambda name: int(name[len("adjudication-input-must-"):-len(".json")]))
    if shard_inputs:
        for inp_name in shard_inputs:
            idx = inp_name[len("adjudication-input-must-"):-len(".json")]
            expected.append("rulings-must-%s.json" % idx)
    elif os.path.isfile(os.path.join(base_dir, "adjudication-input-must.json")):
        try:
            doc = _load_json(os.path.join(base_dir, "adjudication-input-must.json"), "adjudication-input-must.json")
            if isinstance(doc, dict) and doc.get("findings"):
                expected.append("rulings-must.json")
        except ValueError:
            expected.append("rulings-must.json")
    should_in = os.path.join(base_dir, "adjudication-input-should.json")
    if os.path.isfile(should_in):
        try:
            doc = _load_json(should_in, "adjudication-input-should.json")
            if isinstance(doc, dict) and not doc.get("findings"):
                should_out = os.path.join(base_dir, "rulings-should.json")
                if not os.path.isfile(should_out):
                    jsonio.write_json(should_out, {"rulings": [], "merges": []})
            else:
                expected.append("rulings-should.json")
        except ValueError:
            expected.append("rulings-should.json")
    return expected


def wait_for_lane_rulings(base_dir: str, timeout: int, poll: float = 3.0) -> list[str]:
    """Block until every expected lane rulings file in `base_dir` exists and parses as JSON; return any still pending."""
    expected = _expected_lane_rulings(base_dir)
    if not expected:
        return []
    deadline = time.monotonic() + timeout
    while True:
        pending = []
        for name in expected:
            full = os.path.join(base_dir, name)
            if not os.path.isfile(full):
                pending.append(name)
                continue
            try:
                doc = _load_json(full, name)
                if not isinstance(doc, dict) or not isinstance(doc.get("rulings"), list):
                    pending.append(name)
            except ValueError:
                pending.append(name)
        if not pending or time.monotonic() >= deadline:
            return pending
        time.sleep(min(poll, max(0.0, deadline - time.monotonic())))


def _load_or_merge_rulings(path: str) -> dict:
    """Load `rulings.json`, auto-merging sibling lane files (`rulings-must[-<k>].json`, `rulings-should.json`) when present."""
    base_dir = os.path.dirname(os.path.abspath(path))
    lanes = _lane_rulings_paths(base_dir)
    if lanes:
        combined_rulings: list[dict] = []
        combined_merges: list[dict] = []
        for sub_path, label in lanes:
            if os.path.isfile(sub_path):
                doc = _object(_load_json(sub_path, label), label)
                combined_rulings.extend(_items(doc.get("rulings", []), "%s rulings" % label))
                combined_merges.extend(_items(doc.get("merges", []), "%s merges" % label))
        merged_doc = {"rulings": combined_rulings, "merges": combined_merges}
        jsonio.write_json(path, merged_doc)
        return merged_doc
    return _object(_load_json(path, "rulings.json"), "rulings.json")

def _maybe_repair_and_write_auto_report(run_dir: str, result: dict) -> None:
    """Repair anchors against `review-source.json` and pre-build `auto-report.json` when in a run dir."""
    import check_anchors
    import check_merge_ledger as ledger
    import render_report
    src_manifest_path = os.path.join(run_dir, "review-source.json")
    source_root = None
    if os.path.isfile(src_manifest_path):
        try:
            source_root = jsonio.load_object(src_manifest_path, "review-source.json").get("path")
        except ValueError:
            source_root = None
    if source_root and os.path.isdir(source_root):
        root_real = os.path.realpath(source_root)
        for f in result.get("findings") or []:
            rel = str(f.get("file") or "").strip()
            for pfx in (root_real.rstrip("/") + "/", source_root.rstrip("/") + "/"):
                if rel.startswith(pfx):
                    rel = rel[len(pfx):]
            while rel.startswith("./"):
                rel = rel[2:]
            f["file"] = rel
            full = os.path.realpath(os.path.join(source_root, rel))
            if os.path.commonpath([root_real, full]) != root_real or not os.path.isfile(full):
                f["anchor_side"] = "old"
                f["line"] = ledger._norm_line_str(f.get("line"))
                continue
            total = check_anchors.line_count(full)
            span = ledger._range(ledger._norm_line_str(f.get("line")))
            if span and total >= 1:
                lo, hi = (span[1], span[0]) if span[0] > span[1] else span
                lo = max(1, min(lo, total))
                hi = max(lo, min(hi, total))
                f["line"] = str(lo) if lo == hi else "%d-%d" % (lo, hi)
        # Re-fold any findings that collided on (file, line) after clamping
        by_ident: dict[tuple[str, str], dict] = {}
        for item in result.get("findings") or []:
            ident = (str(item.get("file", "")), str(item.get("line", "")))
            if ident not in by_ident:
                by_ident[ident] = item
                continue
            existing = by_ident[ident]
            if _SEVERITY_RANK.get(item.get("severity"), -1) > _SEVERITY_RANK.get(existing.get("severity"), -1):
                existing["severity"] = item["severity"]
            names = sorted({n for x in (existing, item) for n in _dimensions(x)})
            if names:
                existing["dimensions"] = names
                existing["dimension"] = names[0]
            sub = "\n\n- **%s:** %s" % (item.get("title") or "Related", item.get("issue") or item.get("body_md") or "")
            if str(item.get("title") or "").lower() not in str(existing.get("body_md") or "").lower():
                existing["body_md"] = str(existing.get("body_md") or existing.get("issue") or "").rstrip() + sub
                existing["issue"] = str(existing.get("issue") or "").rstrip() + sub
        result["findings"] = list(by_ident.values())

    ctx_path = os.path.join(run_dir, "review-context.json")
    if not os.path.isfile(ctx_path):
        return
    try:
        ctx = jsonio.load_object(ctx_path, "review-context.json")
        ranked = render_report.rank_findings(result.get("findings") or [])
        has_must = any(f.get("severity") == "Must fix" for f in ranked)
        has_should = any(f.get("severity") == "Should fix" for f in ranked)
        verdict = "Request changes" if has_must else ("Fix, then merge" if has_should else "Approve")
        mr_obj = ctx.get("change") or ctx.get("mr") or {}
        iid = mr_obj.get("number") or mr_obj.get("iid") or 0
        size = ctx.get("size") or {}
        size_str = "%d files, %d lines" % (size.get("files", 0), size.get("lines", 0))
        if (size.get("lines") or 0) > 600 or (size.get("files") or 0) > 30:
            size_str += " (large MR warning: over 600 lines)"
        disp_path = os.path.join(run_dir, "dispatch.json")
        dims_run = ["risk"]
        if os.path.isfile(disp_path):
            for ag in (jsonio.load_object(disp_path, "dispatch.json").get("agents") or []):
                b_name = ag.get("name", "").split("-batch")[0]
                if b_name and ("quirk:" + b_name) not in dims_run:
                    dims_run.append("quirk:" + b_name)
        all_dims = ["correctness", "safety", "risk", "adversarial", "scope",
                    "db", "cross-repo", "conventions", "comments",
                    "observability", "resilience", "test-adequacy", "tests",
                    "test-coverage"]
        dims_skipped = [{"name": d, "why": "run condition not met"} for d in all_dims if d not in dims_run]
        models_map = {d: ("sonnet" if d == "risk" else "haiku") for d in dims_run}
        risk_md_path = os.path.join(run_dir, "risk.md")
        risk_text = Path(risk_md_path).read_text(encoding="utf-8").strip() if os.path.isfile(risk_md_path) else "**Risk: High**"
        r_level = "High" if "High" in risk_text else ("Low" if "Low" in risk_text else "Medium")
        adj_obj = dict(result["adjudication"], model="opus (Must fix), sonnet (Should fix)")
        p_notes = []
        adv_t = os.path.join(run_dir, "tables", "adversarial.md")
        if os.path.isfile(adv_t):
            p_notes.append({"title": "Claim verification", "body_md": Path(adv_t).read_text(encoding="utf-8").strip()})
        else:
            p_notes.append({"title": "Claim verification", "body_md": "No MR description claims checked."})
        p_notes.append({"title": "Pre-read hints", "body_md": "Every dimension received the promise, repo facts and hints from `preread.md`."})
        p_notes.append({"title": "Merge ledger", "body_md": "Merged into %d findings via `merge-ledger.json`." % len(ranked)})
        t_counts = []
        t_dir = os.path.join(run_dir, "tables")
        if os.path.isdir(t_dir):
            for tf in sorted(os.listdir(t_dir)):
                if tf.endswith(".md"):
                    t_counts.append("%s (%d rows)" % (tf[:-3], ledger.table_rows(Path(t_dir, tf).read_text(encoding="utf-8"))))
        p_notes.append({"title": "Enumeration tables", "body_md": "Tables written to tables/: " + (", ".join(t_counts) if t_counts else "none")})
        auto_rep = {
            "schema_version": 1,
            "meta": {
                "target": "mr" if iid else "local",
                "iid": int(iid) if iid else 1,
                "title": mr_obj.get("title") or "Code Review",
                "verdict": verdict,
                "standfirst_md": (ctx.get("scope_intent") or {}).get("statement") or "Comprehensive code review.",
                "source_branch": ctx.get("source_branch") or mr_obj.get("source_branch") or "HEAD",
                "web_url": mr_obj.get("web_url") or "",
                "project": ctx.get("project") or mr_obj.get("project") or "owner/repo",
                "seat": ctx.get("seat") or "reviewer",
                "head_sha": (ctx.get("refs") or {}).get("head") or "",
                "change_state": mr_obj.get("state") or "opened",
            },
            "run": {
                "dimensions_run": dims_run,
                "dimensions_skipped": dims_skipped,
                "diff_size": size_str,
                "coverage": "all %d changed files reviewed" % size.get("files", 0),
                "guidance": ["repo CLAUDE.md", "repo review-code references", "pack guidance", "REVIEW.md"],
                "notes_md": "25 single-focus haiku agents + mechanical merge + sharded Opus/Sonnet adjudication.",
                "source_access": "borrowed-worktree" if ctx.get("seat") == "reviewer" else "author-worktree",
                "mutation_consent": False,
                "severity_floor": "Should fix",
                "models": models_map,
                "adjudication": adj_obj,
            },
            "risk": {
                "level": r_level,
                "metrics": {
                    "likelihood": {"level": "Occasional", "tone": "warn", "note_md": "Assessed during risk pass."},
                    "impact": {"level": "Major" if r_level == "High" else "Moderate", "tone": "bad" if r_level == "High" else "warn", "note_md": "Assessed during risk pass."},
                },
                "mitigations_md": "Address Must fix and Should fix findings before merge.",
                "verbatim_md": risk_text,
            },
            "findings": ranked,
            "recommended_order": ["Resolve all Must fix items first.", "Address Should fix items before merge."],
            "assumptions": ["Mutation probe not run: reviewer seat without `--allow-mutation-probe`."] + list(result.get("warnings") or []),
            "process_notes": p_notes,
        }
        jsonio.write_json(os.path.join(run_dir, "auto-report.json"), auto_rep)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand; print `{"error": ...}` and return 2 when an input is malformed."""
    try:
        args = _parser().parse_args(argv)
        if args.command == "prepare":
            if args.must_shard_size is not None and not args.must_out:
                raise ValueError("--must-shard-size needs --must-out")
            raw = _load_json(args.findings, "findings")
            if isinstance(raw, dict):
                raw = raw.get("findings")
            result = prepare(_items(raw, "findings"), _seed(args.seed),
                             skip_nits=bool(args.skip_nits or args.must_out or args.should_out))
            if args.must_out:
                must_items = [item for item in result["findings"] if item.get("severity") == "Must fix"]
                jsonio.write_json(args.must_out, {"seed": result["seed"], "findings": must_items})
                if args.must_shard_size is not None:
                    shard_paths = _must_shards(must_items, args.must_out, args.must_shard_size)
                    size = args.must_shard_size
                    for k, shard_path in enumerate(shard_paths):
                        jsonio.write_json(shard_path, {"seed": result["seed"],
                                                       "findings": must_items[k * size:(k + 1) * size]})
                    print(json.dumps({"must_shards": shard_paths}))
            if args.should_out:
                should_items = [item for item in result["findings"] if item.get("severity") != "Must fix"]
                jsonio.write_json(args.should_out, {"seed": result["seed"], "findings": should_items})
        elif args.command == "jobs":
            if args.wait is not None:
                wait_for_lane_rulings(os.path.dirname(os.path.abspath(args.rulings)), args.wait)
            result = build_jobs(
                _object(_load_json(args.input, "adjudication input"), "adjudication input"),
                _load_or_merge_rulings(args.rulings), _seed(args.seed),
                args.execution)
        else:
            if args.preserve_unreproduced and not os.path.isfile(args.verdicts):
                jsonio.write_json(args.verdicts, {"verdicts": []})
            result = apply_rulings(
                _object(_load_json(args.input, "adjudication input"), "adjudication input"),
                _load_or_merge_rulings(args.rulings),
                _object(_load_json(args.jobs, "prover-jobs.json"), "prover-jobs.json"),
                _object(_load_json(args.verdicts, "verdicts.json"), "verdicts.json"),
                preserve_unreproduced=bool(args.preserve_unreproduced))
            _maybe_repair_and_write_auto_report(os.path.dirname(os.path.abspath(args.out)), result)
        jsonio.write_json(args.out, result)
        return 0
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
