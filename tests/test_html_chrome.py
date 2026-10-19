"""Behavior of theme/chrome.js run under node with a minimal fake DOM.

Covers the wa-dark class, the quirk-theme event, and quirkData's re-resolve on a new file pick.
Skipped when node is not installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHROME_JS = ROOT / "skills" / "writing-html-artifacts" / "theme" / "chrome.js"
NODE = shutil.which("node")

HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
function el(tag) {
  const classes = new Set();
  return {
    tag, attrs: {}, children: [], listeners: {}, textContent: "", className: "", files: null, id: "",
    classList: { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c) },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    appendChild(c) { this.children.push(c); return c; },
  };
}
function run(opts) {
  const root = el("html");
  const body = el("body");
  const store = Object.assign({}, opts.storage || {});
  const events = [];
  const doc = {
    documentElement: root, body, readyState: "complete", listeners: {},
    getElementById() { return null; },
    querySelector() { return null; },
    createElement: el,
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    dispatchEvent(e) { events.push({ type: e.type, detail: e.detail }); return true; },
  };
  const mql = { matches: !!opts.osDark, listeners: [], addEventListener(t, f) { this.listeners.push(f); } };
  const win = {
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
    matchMedia: opts.noMatchMedia ? undefined : () => mql,
  };
  new Function("window", "document", src)(win, doc);
  return { root, body, doc, win, mql, events };
}
function pick(t, name, text) {
  const input = el("input");
  input.id = "quirk-data-picker";
  input.files = [{ name, text: async () => text }];
  t.doc.listeners.change[0]({ target: input });
}
const tick = () => new Promise(r => setTimeout(r, 0));
const scenario = process.argv[3];
const out = {};
(async () => {
  if (scenario === "dark-class") {
    const t = run({});
    const btn = t.body.children[0];
    const seen = [];
    for (let i = 0; i < 3; i++) { btn.listeners.click[0](); seen.push(t.root.classList.contains("wa-dark")); }
    out.cycle = seen;
    out.events = t.events;
    out.restored = run({ storage: { "quirk-theme": "dark" } }).root.classList.contains("wa-dark");
    out.osDarkAtLoad = run({ osDark: true }).root.classList.contains("wa-dark");
  } else if (scenario === "os-follow") {
    const t = run({});
    out.before = t.root.classList.contains("wa-dark");
    t.mql.matches = true;
    t.mql.listeners.forEach(f => f());
    out.after = t.root.classList.contains("wa-dark");
    out.events = t.events;
    const pinned = run({ storage: { "quirk-theme": "light" }, osDark: true });
    pinned.mql.listeners.forEach(f => f());
    out.pinnedLight = pinned.root.classList.contains("wa-dark");
    const bare = run({ noMatchMedia: true });
    out.noMatchMedia = bare.root.classList.contains("wa-dark");
  } else if (scenario === "data-repick") {
    const t = run({});
    const calls = [];
    t.win.quirkData.onChange(v => calls.push(v));
    pick(t, "a.json", '{"n": 1}');
    await tick();
    out.first = await t.win.quirkData();
    pick(t, "b.json", '{"n": 2}');
    await tick();
    out.second = await t.win.quirkData();
    out.calls = calls;
    const early = run({});
    pick(early, "c.csv", "x\n9\n");
    await tick();
    out.pickedBeforeCall = await early.win.quirkData();
  }
  console.log(JSON.stringify(out));
})();
"""


def _node(tmp_path: Path, scenario: str) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(harness), str(CHROME_JS), scenario], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")


def test_toggle_sets_wa_dark_and_announces(tmp_path: Path) -> None:
    out = _node(tmp_path, "dark-class")
    assert out["cycle"] == [False, True, False]
    assert out["events"] == [
        {"type": "quirk-theme", "detail": {"mode": "light", "effective": "light"}},
        {"type": "quirk-theme", "detail": {"mode": "dark", "effective": "dark"}},
        {"type": "quirk-theme", "detail": {"mode": "auto", "effective": "light"}},
    ]
    assert out["restored"] is True
    assert out["osDarkAtLoad"] is True


def test_auto_mode_follows_os_scheme_live(tmp_path: Path) -> None:
    out = _node(tmp_path, "os-follow")
    assert out["before"] is False
    assert out["after"] is True
    assert out["events"] == [{"type": "quirk-theme", "detail": {"mode": "auto", "effective": "dark"}}]
    assert out["pinnedLight"] is False
    assert out["noMatchMedia"] is False


def test_quirk_data_re_resolves_on_new_pick(tmp_path: Path) -> None:
    out = _node(tmp_path, "data-repick")
    assert out["first"] == {"n": 1}
    assert out["second"] == {"n": 2}
    assert out["calls"] == [{"n": 1}, {"n": 2}]
    assert out["pickedBeforeCall"] == [{"x": "9"}]
