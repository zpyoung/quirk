"""Shared helpers for new_app.py, add_patterns.py and set_style.py: pattern discovery, step runner,
style and token wiring, dev check.

Kept in one module so the scripts install, style, build and verify an app identically.
"""
from __future__ import annotations

import json
import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import _styles

SKILL_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_DIR = SKILL_ROOT / "gallery" / "src" / "patterns"
REGISTRY_R = SKILL_ROOT / "registry" / "r"
STYLES_DIR = SKILL_ROOT / "styles"
TOKENS_REL = Path("src") / "styles" / "mini-tokens.css"
SHADCN = "shadcn@4.22.1"
DEV_TIMEOUT = 30
TAIL_LINES = 20
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PRESS_REL = Path("src") / "lib" / "mini" / "press.ts"
PRESS_SOURCE = SKILL_ROOT / "gallery" / PRESS_REL
PRESS_IMPORT = 'import "./lib/mini/press"'
PRESS_IMPORT_RE = re.compile(r"""^[ \t]*import[ \t]+["']\./lib/mini/press(?:\.ts|\.js)?["'];?[ \t]*$""", re.MULTILINE)
NON_CODE_RE = re.compile(
    r"""/\*.*?\*/|`(?:\\.|[^`\\])*`|//[^\n]*|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'""", re.DOTALL
)
TOKENS_IMPORT = '@import "./styles/mini-tokens.css";'
TOP_LEVEL_IMPORT_RE = re.compile(r"^@import\b")
THEME_INLINE_RE = re.compile(r"@theme\s+inline\s*\{")
FONT_WIRING = (("--font-sans", "var(--mini-font-sans)"), ("--font-heading", "var(--mini-font-heading)"))


def known_patterns() -> list[str]:
    """Pattern slugs that have both a gallery folder and a built registry item."""
    if not PATTERNS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in PATTERNS_DIR.iterdir()
        if p.is_dir() and (REGISTRY_R / f"{p.name}.json").is_file()
    )


def parse_patterns(raw: str | None) -> list[str]:
    """Split a comma list into ordered, de-duplicated slugs; None or empty gives no patterns."""
    slugs: list[str] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part and part not in slugs:
            slugs.append(part)
    return slugs


def unknown_patterns(slugs: list[str]) -> list[str]:
    known = set(known_patterns())
    return [s for s in slugs if s not in known]


def usage_error(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def tail(text: str) -> str:
    return "\n".join(text.rstrip().splitlines()[-TAIL_LINES:])


def step_failed(name: str, output: str) -> int:
    print(f"step {name} failed", file=sys.stderr)
    if output.strip():
        print(tail(output), file=sys.stderr)
    return 1


def run_step(name: str, cmd: list[str], cwd: Path) -> int:
    """Run one command with stdin closed; on failure report the step name and output tail."""
    print(f"+ [{name}] {' '.join(cmd)}  (cwd {cwd})", flush=True)
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
        )
    except OSError as exc:
        return step_failed(name, str(exc))
    if proc.returncode != 0:
        return step_failed(name, proc.stdout)
    return 0


def add_step(app: Path, patterns: list[str]) -> int:
    """`shadcn add` of the base plus `patterns` from the local registry; existing files are kept."""
    items = [str(REGISTRY_R / "base.json")] + [str(REGISTRY_R / f"{p}.json") for p in patterns]
    return run_step("add", ["pnpm", "dlx", SHADCN, "add", *items, "-y"], app)


def build_step(app: Path) -> int:
    return run_step("build", ["pnpm", "build"], app)


def style_step(app: Path, slug: str) -> int:
    """Write the style's tokens file into `app` and add any font packages it lacks; never removes any."""
    dist = STYLES_DIR / "dist" / f"{slug}.css"
    try:
        tokens = dist.read_bytes()
        packages = _styles.load_style(STYLES_DIR / f"{slug}.json")["font_packages"]
    except (OSError, _styles.StyleError) as exc:
        return step_failed("style", str(exc))
    target = app / TOKENS_REL
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(tokens)
    except OSError as exc:
        return step_failed("style", str(exc))
    print(f"+ [style] wrote {slug} tokens to {target}")
    try:
        manifest = json.loads((app / "package.json").read_text(encoding="utf-8"))
        installed = manifest.get("dependencies") or {}
    except FileNotFoundError:
        installed = {}
    except (OSError, ValueError, AttributeError) as exc:
        return step_failed("style", f"cannot read {app / 'package.json'}: {exc}")
    missing = [pkg for pkg in packages if pkg not in installed]
    if not missing:
        return 0
    return run_step("style", ["pnpm", "add", *missing], app)


def _skip_opaque(text: str, i: int) -> int:
    """Index just past the string literal or `/* */` comment starting at `i`; `i` when neither starts there.

    An unterminated string or comment runs to the end of `text`.
    """
    char = text[i]
    if char in "\"'":
        j = i + 1
        while j < len(text):
            if text[j] == "\\":
                j += 1
            elif text[j] == char:
                return j + 1
            j += 1
        return len(text)
    if text.startswith("/*", i):
        close = text.find("*/", i + 2)
        return len(text) if close < 0 else close + 2
    return i


def _theme_inline_span(text: str) -> tuple[int, int] | None:
    """Offsets of the body of the first `@theme inline { ... }` block, or None when absent or unclosed."""
    opener = THEME_INLINE_RE.search(text)
    if opener is None:
        return None
    depth = 1
    i = opener.end()
    while i < len(text):
        skipped = _skip_opaque(text, i)
        if skipped != i:
            i = skipped
            continue
        if text[i] == "\\":
            i += 1
        elif text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return opener.end(), i
        i += 1
    return None


def _declarations(block: str):
    """Yield `(property, value_start, value_end, terminated)` for each top-level declaration in `block`.

    Strings, `/* */` comments and parentheses or braces never split a declaration; only a top-level
    `;` does. The property is the text before the first top-level `:` with comments and surrounding
    whitespace dropped. The value span starts after the `:` and its whitespace and ends before
    trailing whitespace and the `;`, so it can include comments. `terminated` is whether a `;` ended it.
    """
    prop: list[str] = []
    colon = -1
    depth = 0
    i = 0

    def finish(end: int, terminated: bool):
        nonlocal prop, colon
        found = None
        if colon >= 0:
            start = colon + 1
            while start < end and block[start].isspace():
                start += 1
            found = ("".join(prop).strip(), start, max(len(block[:end].rstrip()), start), terminated)
        prop, colon = [], -1
        return found

    while i < len(block):
        skipped = _skip_opaque(block, i)
        if skipped != i:
            if colon < 0 and not block.startswith("/*", i):
                prop.append(block[i:skipped])
            i = skipped
            continue
        char = block[i]
        if char == "\\":
            if colon < 0:
                prop.append(block[i : i + 2])
            i += 2
            continue
        if char in "({":
            depth += 1
        elif char in ")}":
            depth = max(depth - 1, 0)
            if char == "}" and depth == 0:
                prop, colon = [], -1
                i += 1
                continue
        elif depth == 0 and char == ";":
            found = finish(i, True)
            if found:
                yield found
            i += 1
            continue
        elif depth == 0 and char == ":" and colon < 0:
            colon = i
        if colon < 0:
            prop.append(char)
        i += 1
    found = finish(len(block), False)
    if found:
        yield found


def _wire_fonts(block: str) -> str:
    """Point `--font-sans` and `--font-heading` at the mini tokens, adding a line when it is absent.

    Only the value span of the font declarations changes; every other byte of `block` is preserved.
    """
    for name, value in FONT_WIRING:
        match = next((d for d in _declarations(block) if d[0] == name), None)
        if match is not None:
            _, start, end, terminated = match
            block = f"{block[:start]}{value}{'' if terminated else ';'}{block[end:]}"
        else:
            body = block.rstrip(" \t")
            trail = block[len(body):]
            if not body.endswith("\n"):
                body += "\n"
            block = f"{body}  {name}: {value};\n{trail}"
    return block


def tokens_step(app: Path) -> int:
    """Wire `src/index.css` to the tokens file: import it once and point the font theme lines at it.

    Idempotent. The font lines live in the first `@theme inline` block; an app without one fails.
    """
    css = app / "src" / "index.css"
    try:
        text = css.read_text(encoding="utf-8")
    except OSError as exc:
        return step_failed("tokens", str(exc))
    span = _theme_inline_span(text)
    if span is None:
        return step_failed("tokens", f"no @theme inline block found in {css}")
    start, end = span
    updated = text[:start] + _wire_fonts(text[start:end]) + text[end:]
    if "styles/mini-tokens.css" not in updated:
        lines = updated.splitlines(keepends=True)
        last = max((i for i, line in enumerate(lines) if TOP_LEVEL_IMPORT_RE.match(line)), default=None)
        if last is None:
            return step_failed("tokens", f"no top-level @import found in {css}")
        if not lines[last].endswith("\n"):
            lines[last] += "\n"
        lines.insert(last + 1, TOKENS_IMPORT + "\n")
        updated = "".join(lines)
    if updated == text:
        return 0
    try:
        css.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return step_failed("tokens", str(exc))
    print(f"+ [tokens] wired {TOKENS_IMPORT} and the font lines into {css}")
    return 0


def blank_non_code(text: str) -> str:
    """Replace comments and template literals with spaces, keeping newlines so line anchors still work.

    Quoted strings are matched only so a comment marker inside one is not misread; they are kept.
    """
    def blank(match: re.Match[str]) -> str:
        chunk = match.group()
        return chunk if chunk[0] in "\"'" else re.sub(r"[^\n]", " ", chunk)

    return NON_CODE_RE.sub(blank, text)


def press_step(app: Path) -> int:
    """Install the press marker: copy `src/lib/mini/press.ts` when absent and import it from `src/main.tsx`.

    Idempotent. An existing module is never overwritten and a `main.tsx` that already has an active
    top-level `import "./lib/mini/press"` line (a comment, template literal, or string mentioning it does not count) is
    not rewritten. Otherwise the import goes on the first line of the file, which is never inside a comment or
    template literal.
    """
    main = app / "src" / "main.tsx"
    try:
        text = main.read_text(encoding="utf-8")
    except OSError as exc:
        return step_failed("press", str(exc))
    target = app / PRESS_REL
    try:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(PRESS_SOURCE.read_bytes())
        code = blank_non_code(text)
        if PRESS_IMPORT_RE.search(code) is None:
            updated = PRESS_IMPORT + "\n" + text
            main.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return step_failed("press", str(exc))
    print(f"+ [press] press marker in place: {target} imported from {main}")
    return 0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def dev_step(app: Path) -> int:
    """Start `pnpm dev`, wait for its `Local:` line, then stop the whole process group."""
    cmd = ["pnpm", "dev", "--port", str(free_port()), "--strictPort"]
    print(f"+ [dev] {' '.join(cmd)}  (cwd {app})", flush=True)
    env = {**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0"}
    try:
        proc = subprocess.Popen(
            cmd, cwd=app, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, start_new_session=True,
        )
    except OSError as exc:
        return step_failed("dev", str(exc))

    lines: queue.Queue[str | None] = queue.Queue()

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(ANSI_RE.sub("", line))
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    seen: list[str] = []
    ready = False
    deadline = time.monotonic() + DEV_TIMEOUT
    try:
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if line is None:
                break
            seen.append(line)
            if "Local:" in line:
                ready = True
                break
    finally:
        stop_group(proc)
    if not ready:
        return step_failed("dev", "".join(seen) or f"no `Local:` line within {DEV_TIMEOUT}s")
    return 0


def group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_group_gone(pgid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while group_alive(pgid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def stop_group(proc: subprocess.Popen, grace: float = 5.0) -> None:
    """Stop the whole process group led by `proc`, SIGKILLing any member that outlives SIGTERM.

    The leader exiting is not enough: a descendant (the vite/esbuild child) can ignore SIGTERM and
    keep running, so the group itself is polled until empty.
    """
    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        proc.wait()
        return
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    if proc.poll() is not None and wait_group_gone(pgid, grace):
        return
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()
    wait_group_gone(pgid, grace)
