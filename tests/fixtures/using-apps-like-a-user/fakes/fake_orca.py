"""Scenario-driven stand-in for `orca computer`, replaying envelopes captured in the golden files.

`FAKE_ORCA_SCENARIO` names a JSON scenario:

    pages     {name: {tree, focused, title, truncated?}}   tree is orca treeText
    start     name of the first page
    rules     [{cmd, opts?, page?, verification?, error?}]   first match wins
    bundle, window_id, scale, running (bool), golden_dir
    screenshot_dir   where get-app-state with a screenshot writes its PNG
    open_log         the fake `open` command's log; a line from `open` marks the app running

State (current page) lives next to the scenario. Every call, with any stdin text, is appended
to `<scenario>.calls.jsonl`.
"""
import copy
import json
import os
import struct
import sys
import zlib
from pathlib import Path

scenario_path = Path(os.environ["FAKE_ORCA_SCENARIO"])
state_path = Path(str(scenario_path) + ".state")
calls_path = Path(str(scenario_path) + ".calls.jsonl")
scenario = json.loads(scenario_path.read_text())
golden = Path(scenario["golden_dir"])
state = json.loads(state_path.read_text()) if state_path.exists() else {
    "page": scenario["start"], "shots": 0}
argv = sys.argv[1:]
stdin = "" if sys.stdin.isatty() else sys.stdin.read()

with open(calls_path, "a") as handle:
    handle.write(json.dumps({"argv": argv, "stdin": stdin}) + "\n")


def envelope(name):
    return json.loads(json.loads((golden / (name + ".json")).read_text())["stdout"])


def finish(body, code=0):
    state_path.write_text(json.dumps(state))
    sys.stdout.write(json.dumps(body, indent=2) + "\n")
    sys.exit(code)


def fail(code, message):
    finish({"id": "x", "ok": False, "error": {"code": code, "message": message, "data": {}}}, 1)


def png():
    def chunk(tag, body):
        crc = zlib.crc32(tag + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", crc)

    rows = b"".join(b"\x00" + b"\x80" * 24 for _ in range(8))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def options(args):
    found = {}
    index = 0
    while index < len(args):
        if args[index].startswith("--"):
            if index + 1 < len(args) and not args[index + 1].startswith("--"):
                found[args[index]] = args[index + 1]
                index += 2
                continue
            found[args[index]] = True
        index += 1
    return found


def snapshot(result_template):
    page = scenario["pages"][state["page"]]
    snap = copy.deepcopy(result_template["snapshot"])
    snap["treeText"] = page["tree"]
    snap["focusedElementId"] = page.get("focused", 0)
    snap["window"]["title"] = page.get("title", "Fake")
    snap["window"]["id"] = scenario["window_id"]
    snap["app"]["bundleId"] = scenario["bundle"]
    snap["elementCount"] = page["tree"].count("\n")
    snap["truncation"]["truncated"] = bool(page.get("truncated"))
    return snap


if argv[:1] == ["--version"]:
    sys.stdout.write("1.4.216-rc.0.fake\n")
    sys.exit(0)

sub = argv[1] if len(argv) > 1 else ""
opts = options(argv[2:])


def was_launched():
    log = scenario.get("open_log")
    if not log or not Path(log).exists():
        return False
    return any(json.loads(line)["tool"] == "open" for line in Path(log).read_text().splitlines())


running = scenario.get("running", True) or was_launched()

if sub == "capabilities":
    finish(envelope("capabilities"))

if sub == "list-windows":
    if not running:
        fail("app_not_found", "app not running")
    body = envelope("list-windows")
    body["result"]["windows"][0]["id"] = scenario["window_id"]
    finish(body)

if not running:
    fail("app_not_found", "app not running")

if sub == "get-app-state":
    with_shot = "--no-screenshot" not in argv
    body = envelope("get-app-state" if with_shot else "get-app-state-no-screenshot")
    body["result"]["snapshot"] = snapshot(body["result"])
    if with_shot:
        state["shots"] += 1
        target = Path(scenario["screenshot_dir"]) / ("orca-%d.png" % state["shots"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(png())
        body["result"]["screenshot"]["path"] = str(target)
        body["result"]["screenshot"]["scale"] = scenario.get("scale", 2)
    finish(body)

for rule in scenario.get("rules", []):
    if rule["cmd"] != sub:
        continue
    if all(opts.get(key) == value for key, value in rule.get("opts", {}).items()):
        if rule.get("error"):
            fail(rule["error"], rule.get("message", rule["error"]))
        if "page" in rule:
            state["page"] = rule["page"]
        body = envelope("click-element")
        body["result"]["snapshot"] = snapshot(body["result"])
        body["result"]["action"]["verification"] = {"state": rule.get("verification", "unverified")}
        finish(body)

body = envelope("click-element")
body["result"]["snapshot"] = snapshot(body["result"])
finish(body)
