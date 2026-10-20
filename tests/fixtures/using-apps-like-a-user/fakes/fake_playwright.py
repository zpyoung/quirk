"""Scenario-driven stand-in for playwright-cli, replaying shapes captured in the golden files.

`FAKE_PW_SCENARIO` names a JSON scenario:

    pages    {name: {url, title, yaml, png?, next_on_snapshot?}}   snapshot yaml per page
    start    name of the first page
    rules    [{on: [argv prefix], page?, console?, requests?, error?}]   first match wins
    visibility {ref: reason}   a ref listed here fails the visibility probe with that reason
               ("__garbage__" makes the probe answer something unparseable)
    console  [message]         error-level console messages so far
    requests [[method, url, status|null]]
    errors   [{on: [argv prefix], stdout, returncode}]   forced failures, checked first
    state_save  "replace" writes the file anew (default mode), "write_then_fail" writes then exits 1;
               the mode an existing target had is appended to `<scenario>.state_save_modes`
    golden_dir, version, stale_exit

State (current page and the growing console and request lists) lives next to the scenario so
each call, a separate process, sees what earlier calls did. Every call is appended to
`<scenario>.calls.jsonl`.
"""
import json
import os
import re
import struct
import sys
import zlib
from pathlib import Path

scenario_path = Path(os.environ["FAKE_PW_SCENARIO"])
state_path = Path(str(scenario_path) + ".state")
calls_path = Path(str(scenario_path) + ".calls.jsonl")
scenario = json.loads(scenario_path.read_text())
golden = Path(scenario["golden_dir"])

argv = sys.argv[1:]
session = None
if argv and argv[0].startswith("-s="):
    session = argv[0][3:]
    argv = argv[1:]

state = json.loads(state_path.read_text()) if state_path.exists() else {
    "page": scenario["start"], "console": list(scenario.get("console", [])),
    "requests": list(scenario.get("requests", [])), "snapshots": 0,
}


def save():
    state_path.write_text(json.dumps(state))


def log():
    with open(calls_path, "a") as handle:
        handle.write(json.dumps({"argv": argv, "session": session, "cwd": os.getcwd()}) + "\n")


def golden_stdout(name):
    return json.loads((golden / (name + ".json")).read_text())["stdout"]


def finish(stdout, code=0):
    save()
    sys.stdout.write(stdout)
    sys.exit(code)


def blank_png():
    def chunk(tag, body):
        crc = zlib.crc32(tag + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", crc)

    rows = b"".join(b"\x00" + b"\xff" * 24 for _ in range(8))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def page():
    return scenario["pages"][state["page"]]


def refs_of(yaml):
    return set(re.findall(r"\[ref=([^\]]+)\]", yaml))


def header(current):
    return "### Page\n- Page URL: %s\n- Page Title: %s\n" % (current["url"], current["title"])


def snapshot_block(current):
    return header(current) + "### Snapshot\n```yaml\n" + current["yaml"] + "\n```\n"


def linked_block(current):
    state["snapshots"] += 1
    rel = ".playwright-cli/page-%d.yml" % state["snapshots"]
    target = Path(os.getcwd()) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(current["yaml"])
    target.chmod(0o644)
    return header(current) + "### Snapshot\n- [Snapshot](%s)\n" % rel


def matches(prefix):
    return argv[:len(prefix)] == prefix


log()

for forced in scenario.get("errors", []):
    if matches(forced["on"]):
        finish(forced["stdout"], forced.get("returncode", 1))

if argv == ["--version"]:
    finish(scenario.get("version", "0.1.22") + "\n")

command = argv[0] if argv else ""

if command in ("open", "attach", "close", "detach", "goto", "state-load"):
    if command == "close":
        finish(golden_stdout("close"))
    if command in ("open", "goto"):
        finish("### Ran Playwright code\n" + linked_block(page()))
    finish("### Ran Playwright code\n")

if command == "state-save":
    target = Path(os.getcwd()) / argv[1]
    with open(str(scenario_path) + ".state_save_modes", "a") as handle:
        prior = oct(target.stat().st_mode & 0o777) if target.exists() else "absent"
        handle.write(prior + "\n")
    body = '{"cookies": [], "origins": []}'
    if scenario.get("state_save") == "replace":
        fresh = target.with_name(target.name + ".fresh")
        fresh.write_text(body)
        fresh.chmod(0o644)
        os.replace(str(fresh), str(target))
    else:
        target.write_text(body)
    if scenario.get("state_save") == "write_then_fail":
        finish("### Error\nstate-save failed\n", 1)
    finish(golden_stdout("state_save"))

if command == "snapshot":
    current = page()
    out = snapshot_block(current)
    if current.get("next_on_snapshot"):
        state["page"] = current["next_on_snapshot"]
    finish(out)

if command == "screenshot":
    filename = [a for a in argv if a.startswith("--filename=")][0].split("=", 1)[1]
    target = Path(os.getcwd()) / filename
    source = page().get("png")
    target.write_bytes(Path(source).read_bytes() if source else blank_png())
    target.chmod(0o644)
    finish(golden_stdout("screenshot"))

if command == "console":
    lines = ["### Result", "Total messages: %d (Errors: %d, Warnings: 0)" % (
        len(state["console"]), len(state["console"])), ""]
    lines += ["[ERROR] %s" % message for message in state["console"]]
    finish("\n".join(lines) + "\n")

if command == "requests":
    lines = ["### Result"]
    for number, (method, url, status) in enumerate(state["requests"], 1):
        suffix = "" if status is None else " => [%d] Status" % status
        lines.append("%d. [%s] %s%s" % (number, method, url, suffix))
    finish("\n".join(lines) + "\n")

if command == "eval":
    if "innerWidth" in argv[1] and len(argv) == 2:
        finish(golden_stdout("eval_viewport"))
    ref = argv[2] if len(argv) > 2 else ""
    reason = scenario.get("visibility", {}).get(ref, "")
    if reason == "__garbage__":
        finish('### Result\n"not json"\n')
    body = json.dumps(json.dumps({"visible": reason == "", "reason": reason}))
    finish("### Result\n%s\n### Ran Playwright code\n" % body)

ref_commands = ("click", "dblclick", "fill", "select", "hover", "drag")
if command in ref_commands and len(argv) > 1 and argv[1] not in refs_of(page()["yaml"]):
    finish(golden_stdout("click_stale_ref"), scenario.get("stale_exit", 1))

for rule in scenario.get("rules", []):
    if matches(rule["on"]):
        if rule.get("error"):
            finish("### Error\nError: %s\n" % rule["error"], rule.get("returncode", 1))
        if "page" in rule:
            state["page"] = rule["page"]
        state["console"] += rule.get("console", [])
        state["requests"] += rule.get("requests", [])
        break

finish("### Ran Playwright code\n" + linked_block(page()))
