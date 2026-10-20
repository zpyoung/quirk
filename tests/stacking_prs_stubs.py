"""Fake `gh` / `glab` executables for the stacking-prs script tests.

Shared by the stack.sh and restack.sh suites so neither one reaches a real forge. Import it the
way the other test helpers are imported: `from .stacking_prs_stubs import write_forge_stubs`.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Dict, List, Sequence

_STUB_TEMPLATE = """#!{python}
import json, os, sys

tool = {tool!r}
argv = sys.argv[1:]
with open(os.environ["FAKE_FORGE_LOG"], "a") as log:
    log.write(json.dumps([tool] + argv) + "\\n")
with open(os.environ["FAKE_FORGE_FIXTURE"]) as handle:
    fixture = json.load(handle)
best = None
for entry in fixture.get(tool, []):
    prefix = entry["argv"]
    if argv[:len(prefix)] == prefix and (best is None or len(prefix) > len(best["argv"])):
        best = entry
if best is None:
    sys.stderr.write("unmatched " + tool + " argv: " + " ".join(argv) + "\\n")
    sys.exit(99)
sys.stdout.write(best.get("stdout", ""))
sys.stderr.write(best.get("stderr", ""))
sys.exit(best.get("exit", 0))
"""


def write_forge_stubs(
    bin_dir: Path,
    fixture: Dict[str, List[dict]],
    log_path: Path,
    tools: Sequence[str] = ("gh", "glab"),
) -> Dict[str, str]:
    """Write the named forge stubs into `bin_dir` and return the env vars a child process needs.

    `fixture` maps a tool to entries `{"argv": [...], "stdout": str, "stderr": str, "exit": int}`.
    A call is answered by the entry with the longest argv prefix matching the arguments after the
    tool name; an unmatched call exits 99. Every call is logged before matching. `tools` selects
    which stubs exist, so a test can simulate a forge CLI that is not installed.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("")
    fixture_path = bin_dir / "forge_fixture.json"
    fixture_path.write_text(json.dumps(fixture))
    for tool in tools:
        stub = bin_dir / tool
        stub.write_text(_STUB_TEMPLATE.format(python=sys.executable, tool=tool))
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
        "FAKE_FORGE_FIXTURE": str(fixture_path),
        "FAKE_FORGE_LOG": str(log_path),
    }


def read_forge_log(log_path: Path) -> List[List[str]]:
    """Return one argv list per stub invocation, in call order, with the tool name first."""
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
