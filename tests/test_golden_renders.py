"""Golden masters pinning the interactive renderer's logic.md and review payload output.

Set QUIRK_BLESS_GOLDENS=1 to rewrite the goldens from the current renderer
instead of comparing; never hand-edit them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INT = REPO_ROOT / "skills" / "writing-specs" / "interactive"
SCRIPT = INT / "render_spec.py"
TEMPLATE = INT / "review-template.html"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "interactive"
GOLDEN = FIXTURES / "golden"

sys.path.insert(0, str(SCRIPT.parent))
import render_spec  # noqa: E402

BLESS = os.environ.get("QUIRK_BLESS_GOLDENS") == "1"

# case -> (fixture dir holding logic.json, signed export to fold first, has payload)
CASES = {
    "sample": (FIXTURES / "sample", None, False),
    "stage1": (FIXTURES / "v2" / "stage1", None, True),
    "stage2": (FIXTURES / "v2" / "stage2", None, True),
    "stage2-signed": (
        FIXTURES / "v2" / "stage2",
        FIXTURES / "v2" / "stage2" / "exports" / "signed.json",
        True,
    ),
}
HTML_CASES = ["stage1", "stage2", "stage2-signed"]


def run_script(
    script: Path, *args: str, cwd: Optional[Path] = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def run_cli(*args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    return run_script(SCRIPT, *args, cwd=cwd)


def render_case(tmp_path: Path, case: str) -> Path:
    """Render a case into a dir named for its slug (the payload embeds the dir name)."""
    source, export, _ = CASES[case]
    slug = "sample" if case == "sample" else source.name
    spec_dir = tmp_path / slug
    spec_dir.mkdir(parents=True)
    shutil.copy(source / "logic.json", spec_dir / "logic.json")
    if export is not None:
        folded = run_cli("fold", str(spec_dir), str(export))
        assert folded.returncode == 0, folded.stderr
    rendered = run_cli("render", str(spec_dir))
    assert rendered.returncode == 0, rendered.stderr
    return spec_dir


def extract_payload(html: str) -> str:
    start = html.index(render_spec.PAYLOAD_OPEN) + len(render_spec.PAYLOAD_OPEN)
    end = html.index(render_spec.PAYLOAD_CLOSE, start)
    return html[start:end]


@pytest.mark.parametrize("case", list(CASES))
def test_golden_logic_md_and_payload(tmp_path: Path, case: str) -> None:
    spec_dir = render_case(tmp_path, case)
    actual = {"logic.md": (spec_dir / "logic.md").read_bytes()}
    if CASES[case][2]:
        payload = extract_payload((spec_dir / "review.html").read_text(encoding="utf-8"))
        actual["payload.json"] = payload.encode("utf-8")

    golden_dir = GOLDEN / case
    if BLESS:
        golden_dir.mkdir(parents=True, exist_ok=True)
        for name, data in actual.items():
            (golden_dir / name).write_bytes(data)
        return
    for name, data in actual.items():
        assert (golden_dir / name).read_bytes() == data, f"{case}/{name} drifted from golden"


@pytest.mark.parametrize("case", HTML_CASES)
def test_review_html_is_template_plus_payload(tmp_path: Path, case: str) -> None:
    spec_dir = render_case(tmp_path, case)
    html = (spec_dir / "review.html").read_text(encoding="utf-8")
    payload = extract_payload(html)
    template_text = TEMPLATE.read_text(encoding="utf-8")
    expected = template_text.replace(
        render_spec.PAYLOAD_PLACEHOLDER,
        render_spec.PAYLOAD_OPEN + payload + render_spec.PAYLOAD_CLOSE,
    )
    assert html == expected
