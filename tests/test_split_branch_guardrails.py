from __future__ import annotations

import re
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parents[1] / "skills/split-branch/scripts"


def scripts() -> list[Path]:
    found = sorted(SCRIPTS_DIR.glob("*.sh"))
    assert found, f"no scripts found under {SCRIPTS_DIR}"
    return found


def lines(path: Path) -> list[str]:
    return path.read_text().splitlines()


def location(path: Path, line_number: int, line: str) -> str:
    return f"{path.relative_to(SCRIPTS_DIR.parents[2])}:{line_number}: {line.strip()}"


def commands(path: Path) -> list[tuple[int, str]]:
    """Return shell commands, joining explicit backslash continuations."""
    result: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 1
    for number, line in enumerate(lines(path), 1):
        if not pending:
            start = number
        pending.append(line.rstrip().removesuffix("\\"))
        if not line.rstrip().endswith("\\"):
            result.append((start, " ".join(pending)))
            pending = []
    if pending:
        result.append((start, " ".join(pending)))
    return result


def assert_no_violations(violations: list[str]) -> None:
    assert not violations, "guardrail violation(s):\n" + "\n".join(violations)


def test_git_apply_never_uses_recount() -> None:
    violations = [
        location(path, number, line)
        for path in scripts()
        for number, line in enumerate(lines(path), 1)
        if "--recount" in line
    ]
    assert_no_violations(violations)


def test_unidiff_zero_is_marked_as_undrifted_base_only() -> None:
    violations: list[str] = []
    marker = "GUARDRAIL-OK: undrifted-base"
    for path in scripts():
        source_lines = lines(path)
        for index, line in enumerate(source_lines):
            if "--unidiff-zero" in line and (
                index == 0 or marker not in source_lines[index - 1]
            ):
                violations.append(location(path, index + 1, line))
    assert_no_violations(violations)


def test_git_apply_never_uses_check() -> None:
    pattern = re.compile(r"\bgit\s+apply\b.*(?:^|\s)--check(?:\s|$)")
    violations = [
        location(path, number, line)
        for path in scripts()
        for number, line in commands(path)
        if not line.lstrip().startswith("#") and pattern.search(line)
    ]
    assert_no_violations(violations)


def test_verify_never_checks_out_inside_a_loop() -> None:
    path = SCRIPTS_DIR / "verify.sh"
    violations: list[str] = []
    loop_depth = 0
    for number, line in enumerate(lines(path), 1):
        code = line.split("#", 1)[0]
        if re.match(r"^\s*(?:for|while)\b", code):
            loop_depth += 1
        if loop_depth and re.search(r"\bgit\s+checkout\b", code):
            violations.append(location(path, number, line))
        if re.match(r"^\s*done(?:\s|;|$)", code):
            loop_depth = max(0, loop_depth - 1)
    assert_no_violations(violations)


def test_force_push_always_uses_force_with_lease() -> None:
    bare_force = re.compile(r"\bgit\s+push\b[^#\n]*--force(?!-with-lease)(?:[=\s]|$)")
    violations = [
        location(path, number, line)
        for path in scripts()
        for number, line in commands(path)
        if not line.lstrip().startswith("#") and bare_force.search(line)
    ]
    assert_no_violations(violations)


def test_origin_only_appears_in_documented_default_resolution() -> None:
    origin = re.compile(r"\borigin\b")
    violations = [
        location(path, number, line)
        for path in scripts()
        for number, line in enumerate(lines(path), 1)
        if origin.search(line)
        and not line.lstrip().startswith("#")
        and "pushDefault" not in line
    ]
    assert_no_violations(violations)


def test_every_script_enables_strict_mode() -> None:
    violations: list[str] = []
    for path in scripts():
        source_lines = lines(path)
        if not source_lines or not source_lines[0].startswith("#!"):
            violations.append(location(path, 1, source_lines[0] if source_lines else "<empty>"))
            continue
        first_command = next(
            (
                (number, line)
                for number, line in enumerate(source_lines[1:], 2)
                if line.strip() and not line.lstrip().startswith("#")
            ),
            None,
        )
        if first_command is None or first_command[1].strip() != "set -euo pipefail":
            number, line = first_command or (1, "<missing set -euo pipefail>")
            violations.append(location(path, number, line))
    assert_no_violations(violations)


def test_slice_patch_diffs_enable_rename_detection() -> None:
    # Patch-producing diffs request context or binary output. Status, conflict,
    # and conservation diffs do not materialize slice patches.
    patch_diff = re.compile(r"\bgit\s+diff\b.*(?:-U\d+|--binary)\b")
    rename_detection = re.compile(r"(?:^|\s)-M(?:\s|$)")
    violations = [
        location(path, number, line)
        for path in scripts()
        for number, line in commands(path)
        if not line.lstrip().startswith("#")
        and patch_diff.search(line)
        and not rename_detection.search(line)
    ]
    assert_no_violations(violations)


def test_scripts_remain_bash_3_2_compatible() -> None:
    incompatible = re.compile(r"\b(?:mapfile|readarray)\b|\bdeclare\s+-A\b")
    violations = [
        location(path, number, line)
        for path in scripts()
        for number, line in enumerate(lines(path), 1)
        if not line.lstrip().startswith("#") and incompatible.search(line)
    ]
    assert_no_violations(violations)
