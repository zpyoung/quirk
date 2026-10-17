"""Browser tests for the component kit's elements (`kit.js` and `kit.css`).

Each page under test is built with the real CLI from a report-template source, so the kit is
auto-included, then driven through `tests/fixtures/html-kit/harness.mjs`. The tests skip only when
node, `scripts/verify/node_modules` or a launchable browser is missing; they never touch the network.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "writing-html-artifacts"
CLI = SKILL / "scripts" / "quirk_html.py"
KIT_JS = SKILL / "vendor" / "kit" / "1.0.0" / "kit.js"
HARNESS = Path(__file__).resolve().parent / "fixtures" / "html-kit" / "harness.mjs"

SCHEMES = ["light", "dark"]
HEADER = '<!-- quirk-src {"template": "report", "title": "Kit elements", "mode": "offline"} -->\n<!-- slot: summary -->\n<p>Kit elements.</p>\n<!-- slot: main -->\n'

LONG_UNBROKEN = "x" * 220

ELEMENTS_SRC = (
    HEADER
    + f"""<q-tabs id="tabs" label="Release review">
  <section>
    <h3>Summary</h3>
    <p>The 2.4 release shipped on schedule. Checkout latency improved, and one rollback was needed for the address form.</p>
  </section>
  <section>
    <h3>Timeline and rollout details</h3>
    <p>Rollout started Tuesday at 09:00 UTC and reached every region by Wednesday at noon.</p>
  </section>
  <section>
    <h3>Follow-ups</h3>
    <ul><li>Add a canary stage for the address form.</li><li>Alert on checkout p95 above 800 ms.</li></ul>
  </section>
  <section>
    <h3>Raw data export</h3>
    <p>The raw export lives next to the dashboard.</p>
  </section>
  <section>
    <h3>Appendix: glossary of terms used</h3>
    <p>Canary: a small first slice of traffic.</p>
  </section>
</q-tabs>

<q-timeline id="timeline">
  <ol>
    <li data-tone="warning"><time datetime="2026-09-14T09:02Z">09:02</time> Error rate on checkout crosses 2%.</li>
    <li data-tone="danger"><time datetime="2026-09-14T09:10Z">09:10</time> Pager fires; incident declared.</li>
    <li data-tone="neutral"><time datetime="2026-09-14T09:31Z">09:31</time> Bad config identified in the 2.4 rollout.</li>
    <li data-tone="success"><time datetime="2026-09-14T09:44Z">09:44</time> Rollback complete; error rate back to baseline.</li>
    <li><time datetime="2026-09-14T10:15Z">10:15</time> Review scheduled.</li>
  </ol>
</q-timeline>

<q-code id="code" filename="deploy.sh">
  <pre><code>#!/usr/bin/env bash
set -euo pipefail
./build.sh --release
./push.sh --env staging
echo {LONG_UNBROKEN}</code></pre>
</q-code>

<q-code id="bare">
  <pre><code>npm test</code></pre>
</q-code>
"""
)

KIT_SCRIPT = re.compile(r'<script data-quirk-lib="kit@1\.0\.0">.*?</script>', re.S)
TABS = "document.querySelector('#tabs')"


def _node_ready() -> str | None:
    if not (SKILL / "scripts" / "verify" / "node_modules").is_dir():
        return "scripts/verify/node_modules is absent; run pnpm install there"
    if shutil.which("node") is None:
        return "node is not installed"
    return None


def _run_harness(spec: dict) -> dict:
    proc = subprocess.run(
        ["node", str(HARNESS), json.dumps(spec)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode == 3:
        pytest.skip("no browser could be launched")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _build(src: Path, out: Path) -> Path:
    proc = subprocess.run(
        [sys.executable, str(CLI), "build", str(src), "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return out


@pytest.fixture(scope="module")
def elements_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-elements")
    src = work / "elements.src.html"
    src.write_text(ELEMENTS_SRC, encoding="utf-8")
    page = _build(src, work / "elements.html")
    _run_harness({"file": str(page)})
    return page


@pytest.fixture(scope="module")
def nojs_page(elements_page: Path) -> Path:
    html = elements_page.read_text(encoding="utf-8")
    stripped, count = KIT_SCRIPT.subn("", html)
    assert count == 1, "the built page should carry exactly one kit script block"
    page = elements_page.with_name("elements-nojs.html")
    page.write_text(stripped, encoding="utf-8")
    return page


def run(page: Path, *steps: dict, **spec: object) -> dict:
    return _run_harness({"file": str(page), "steps": list(steps), **spec})


def ev(expr: str, name: str = "v") -> dict:
    return {"eval": expr, "as": name}


def assert_clean(out: dict) -> None:
    assert out["failedSteps"] == []
    assert out["consoleErrors"] == []
    assert out["pageErrors"] == []


# --- q-tabs -----------------------------------------------------------------------------------


def test_tabs_roles_and_aria_wiring(elements_page: Path) -> None:
    out = run(
        elements_page,
        ev(
            f"""(() => {{
              const root = {TABS};
              const list = root.querySelector('[role=tablist]');
              const tabs = [...root.querySelectorAll('[role=tab]')];
              const panels = [...root.querySelectorAll(':scope > section')];
              return {{
                listLabel: list && list.getAttribute('aria-label'),
                listIsKit: list && list.hasAttribute('data-q-kit'),
                listBeforeFirstSection: list && list.nextElementSibling === panels[0],
                tabCount: tabs.length,
                tabsAreButtons: tabs.every((t) => t.tagName === 'BUTTON' && t.type === 'button'),
                selected: tabs.map((t) => t.getAttribute('aria-selected')),
                tabindex: tabs.map((t) => t.getAttribute('tabindex')),
                controls: tabs.map((t, i) => t.getAttribute('aria-controls') === panels[i].id && panels[i].id !== ''),
                panelRoles: panels.map((p) => p.getAttribute('role')),
                panelTabindex: panels.map((p) => p.getAttribute('tabindex')),
                labelledby: panels.map((p, i) => p.getAttribute('aria-labelledby') === tabs[i].id && tabs[i].id !== ''),
                uniqueIds: new Set([...tabs, ...panels].map((n) => n.id)).size === tabs.length * 2,
              }};
            }})()""",
            "aria",
        ),
    )
    assert_clean(out)
    aria = out["results"]["aria"]
    assert aria["listLabel"] == "Release review"
    assert aria["listIsKit"] and aria["listBeforeFirstSection"]
    assert aria["tabCount"] == 5 and aria["tabsAreButtons"]
    assert aria["selected"] == ["true", "false", "false", "false", "false"]
    assert aria["tabindex"] == ["0", "-1", "-1", "-1", "-1"]
    assert all(aria["controls"]) and all(aria["labelledby"]) and aria["uniqueIds"]
    assert aria["panelRoles"] == ["tabpanel"] * 5
    assert aria["panelTabindex"] == ["0"] * 5


def _active(expr_tabs: str = TABS) -> str:
    return f"""(() => {{
      const root = {expr_tabs};
      const tabs = [...root.querySelectorAll('[role=tab]')];
      return {{
        selected: tabs.findIndex((t) => t.getAttribute('aria-selected') === 'true'),
        focused: tabs.indexOf(document.activeElement),
      }};
    }})()"""


def test_tabs_arrow_keys_wrap_and_activate(elements_page: Path) -> None:
    out = run(
        elements_page,
        {"focus": "#tabs [role=tab]"},
        {"press": "ArrowLeft"},
        ev(_active(), "left_from_first"),
        {"press": "ArrowRight"},
        ev(_active(), "right_from_last"),
        {"press": "ArrowRight"},
        ev(_active(), "right"),
    )
    assert_clean(out)
    assert out["results"]["left_from_first"] == {"selected": 4, "focused": 4}
    assert out["results"]["right_from_last"] == {"selected": 0, "focused": 0}
    assert out["results"]["right"] == {"selected": 1, "focused": 1}


def test_tabs_home_and_end(elements_page: Path) -> None:
    out = run(
        elements_page,
        {"focus": "#tabs [role=tab]:nth-child(3)"},
        {"press": "End"},
        ev(_active(), "end"),
        {"press": "Home"},
        ev(_active(), "home"),
    )
    assert_clean(out)
    assert out["results"]["end"] == {"selected": 4, "focused": 4}
    assert out["results"]["home"] == {"selected": 0, "focused": 0}


def test_tabs_click_selects_and_only_active_panel_is_visible(elements_page: Path) -> None:
    visible = f"""(() => [...{TABS}.querySelectorAll(':scope > section')].map((p) => ({{
      shown: p.offsetHeight > 0,
      inactiveAttr: p.hasAttribute('data-q-inactive'),
      hiddenAttr: p.hasAttribute('hidden'),
    }})))()"""
    out = run(
        elements_page,
        ev(visible, "initial"),
        {"click": "#tabs [role=tab]:nth-child(3)"},
        ev(visible, "after_click"),
        ev(_active(), "active"),
    )
    assert_clean(out)
    for key, index in (("initial", 0), ("after_click", 2)):
        panels = out["results"][key]
        assert [p["shown"] for p in panels] == [i == index for i in range(5)]
        assert [p["inactiveAttr"] for p in panels] == [i != index for i in range(5)]
        assert not any(p["hiddenAttr"] for p in panels)
    assert out["results"]["active"]["selected"] == 2


def test_tabs_print_shows_every_panel_and_hides_the_tablist(elements_page: Path) -> None:
    out = run(
        elements_page,
        {"emulate": {"media": "print"}},
        ev(
            f"""(() => ({{
              shown: [...{TABS}.querySelectorAll(':scope > section')].map((p) => p.offsetHeight > 0),
              headingVisible: [...{TABS}.querySelectorAll(':scope > section > h3')].every((h) => h.offsetWidth > 1 && h.offsetHeight > 1),
              tablist: getComputedStyle({TABS}.querySelector('[role=tablist]')).display,
            }}))()""",
            "print",
        ),
    )
    assert_clean(out)
    assert out["results"]["print"]["shown"] == [True] * 5
    assert out["results"]["print"]["headingVisible"] is True
    assert out["results"]["print"]["tablist"] == "none"


def test_tabs_heading_text_equals_tab_label_and_is_visually_hidden(elements_page: Path) -> None:
    out = run(
        elements_page,
        ev(
            f"""(() => {{
              const tabs = [...{TABS}.querySelectorAll('[role=tab]')];
              const headings = [...{TABS}.querySelectorAll(':scope > section > h3')];
              return {{
                labels: tabs.map((t) => t.textContent.trim()),
                headings: headings.map((h) => h.textContent.trim()),
                hiddenBox: headings.map((h) => {{ const r = h.getBoundingClientRect(); return r.width <= 1 && r.height <= 1; }}),
              }};
            }})()""",
            "labels",
        ),
    )
    assert_clean(out)
    labels = out["results"]["labels"]
    assert labels["labels"] == labels["headings"]
    assert labels["labels"][0] == "Summary"
    assert all(labels["hiddenBox"])


def test_tabs_upgrade_is_idempotent_when_kit_runs_again(elements_page: Path) -> None:
    source = json.dumps(KIT_JS.read_text(encoding="utf-8"))
    out = run(
        elements_page,
        ev(
            f"""(() => {{
              const before = customElements.get('q-tabs');
              const s = document.createElement('script');
              s.textContent = {source};
              document.head.appendChild(s);
              const root = {TABS};
              root.parentNode.appendChild(root);
              return {{
                same: customElements.get('q-tabs') === before,
                tablists: root.querySelectorAll('[role=tablist]').length,
                tabs: root.querySelectorAll('[role=tab]').length,
                inserted: root.querySelectorAll('[data-q-kit]').length,
              }};
            }})()""",
            "again",
        ),
    )
    assert_clean(out)
    again = out["results"]["again"]
    assert again["same"] is True
    assert again["tablists"] == 1 and again["tabs"] == 5
    assert again["inserted"] == 1


def test_tabs_rebuild_when_sections_change(elements_page: Path) -> None:
    out = run(
        elements_page,
        ev(
            f"""(async () => {{
              const root = {TABS};
              const s = document.createElement('section');
              s.innerHTML = '<h3>Added later</h3><p>New.</p>';
              root.appendChild(s);
              await new Promise((r) => setTimeout(r, 100));
              return [...root.querySelectorAll('[role=tab]')].map((t) => t.textContent.trim());
            }})()""",
            "labels",
        ),
    )
    assert_clean(out)
    assert out["results"]["labels"][-1] == "Added later"
    assert len(out["results"]["labels"]) == 6


# --- q-timeline -------------------------------------------------------------------------------

TONES = {"neutral": "color-text-muted", "success": "color-good", "warning": "color-warn", "danger": "color-critical"}


@pytest.mark.parametrize("scheme", SCHEMES)
def test_timeline_tone_word_and_marker_colour_come_from_tokens(elements_page: Path, scheme: str) -> None:
    out = run(
        elements_page,
        ev(
            f"""(() => {{
              const resolve = (name) => {{
                const probe = document.createElement('span');
                probe.style.color = 'var(--q-' + name + ')';
                document.body.appendChild(probe);
                const colour = getComputedStyle(probe).color;
                probe.remove();
                return colour;
              }};
              const tones = {json.dumps(TONES)};
              const items = [...document.querySelectorAll('#timeline ol > li')];
              return items.map((li) => {{
                const tone = li.getAttribute('data-tone');
                const word = li.querySelector('.q-visually-hidden');
                const rect = word && word.getBoundingClientRect();
                const marker = getComputedStyle(li, '::before');
                return {{
                  tone,
                  word: word && word.textContent.trim(),
                  wordHidden: !!rect && rect.width <= 1 && rect.height <= 1,
                  innerText: li.innerText,
                  marker: marker.backgroundColor,
                  markerBorder: marker.borderTopColor,
                  expected: tone ? resolve(tones[tone]) : resolve('color-text-muted'),
                }};
              }});
            }})()""",
            "items",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    items = out["results"]["items"]
    assert [i["tone"] for i in items] == ["warning", "danger", "neutral", "success", None]
    for item in items[:4]:
        assert item["word"].lower().rstrip(":") == item["tone"], item
        assert item["wordHidden"] is True
        assert item["innerText"].strip() != ""
        assert item["marker"] == item["expected"] or item["markerBorder"] == item["expected"], item
    assert items[4]["word"] is None


def test_timeline_tone_colours_differ_between_tones(elements_page: Path) -> None:
    out = run(
        elements_page,
        ev(
            """[...document.querySelectorAll('#timeline ol > li')].map((li) => {
              const m = getComputedStyle(li, '::before');
              return m.backgroundColor + '|' + m.borderTopColor;
            })""",
            "markers",
        ),
    )
    assert_clean(out)
    assert len(set(out["results"]["markers"][:4])) == 4


def test_timeline_upgrade_is_idempotent(elements_page: Path) -> None:
    out = run(
        elements_page,
        ev(
            """(async () => {
              const root = document.querySelector('#timeline');
              root.parentNode.appendChild(root);
              await new Promise((r) => setTimeout(r, 100));
              return [...root.querySelectorAll('ol > li')].map((li) => li.querySelectorAll('[data-q-kit]').length);
            })()""",
            "counts",
        ),
    )
    assert_clean(out)
    assert out["results"]["counts"] == [1, 1, 1, 1, 0]


# --- q-code -----------------------------------------------------------------------------------

CODE_TEXT = "#!/usr/bin/env bash\nset -euo pipefail\n./build.sh --release\n./push.sh --env staging\necho " + LONG_UNBROKEN
NOTICE = "Press Ctrl+C (⌘C on Mac) to copy"
STUB_CLIPBOARD = """
Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
  writeText(text) { window.__copied = text; return Promise.resolve(); },
} });
"""
DENIED_CLIPBOARD = """
Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
  writeText() { return Promise.reject(new DOMException('Write permission denied.', 'NotAllowedError')); },
} });
"""


def test_code_has_copy_button_and_filename_label(elements_page: Path) -> None:
    out = run(
        elements_page,
        ev(
            """(() => {
              const info = (id) => {
                const root = document.querySelector(id);
                const button = root.querySelector('button');
                const bar = root.querySelector('[data-q-kit]');
                return {
                  button: button && button.textContent.trim(),
                  buttonType: button && button.type,
                  barText: bar && bar.textContent,
                  barBeforePre: !!bar && bar.compareDocumentPosition(root.querySelector('pre')) & Node.DOCUMENT_POSITION_FOLLOWING,
                  preText: root.querySelector('pre code').textContent,
                  live: !!root.querySelector('[aria-live=polite]'),
                };
              };
              return { named: info('#code'), bare: info('#bare') };
            })()""",
            "info",
        ),
    )
    assert_clean(out)
    named, bare = out["results"]["info"]["named"], out["results"]["info"]["bare"]
    assert named["button"] == "Copy" and named["buttonType"] == "button"
    assert "deploy.sh" in named["barText"] and named["barBeforePre"]
    assert named["preText"] == CODE_TEXT
    assert named["live"] is True
    assert bare["button"] == "Copy"
    assert "deploy.sh" not in (bare["barText"] or "")


def test_code_copy_success_writes_the_code_and_says_copied(elements_page: Path) -> None:
    out = run(
        elements_page,
        {"click": "#code button"},
        {"waitFor": "document.querySelector('#code button').textContent.trim() === 'Copied'"},
        ev("window.__copied", "copied"),
        ev("document.querySelector('#code button').textContent.trim()", "label"),
        {"wait": 2300},
        ev("document.querySelector('#code button').textContent.trim()", "label_later"),
        initScripts=[STUB_CLIPBOARD],
    )
    assert_clean(out)
    assert out["results"]["copied"] == CODE_TEXT
    assert out["results"]["label"] == "Copied"
    assert out["results"]["label_later"] == "Copy"


@pytest.mark.parametrize("script", [None, DENIED_CLIPBOARD], ids=["permission-denied", "write-rejects"])
def test_code_blocked_clipboard_selects_the_text_and_tells_the_reader(elements_page: Path, script: str | None) -> None:
    spec: dict = {"permissions": []}
    if script:
        spec["initScripts"] = [script]
    out = run(
        elements_page,
        {"click": "#code button"},
        {"waitFor": "document.querySelector('#code [aria-live=polite]').textContent.trim() !== ''"},
        ev("getSelection().toString().replace(/\\r/g, '')", "selection"),
        ev("document.querySelector('#code [aria-live=polite]').textContent.trim()", "notice"),
        ev("document.querySelector('#code button').textContent.trim()", "label"),
        **spec,
    )
    assert_clean(out)
    assert out["results"]["selection"].strip() == CODE_TEXT
    assert out["results"]["notice"] == NOTICE
    assert out["results"]["label"] == "Copy"


def test_code_without_a_clipboard_api_still_falls_back(elements_page: Path) -> None:
    out = run(
        elements_page,
        {"click": "#bare button"},
        {"waitFor": "document.querySelector('#bare [aria-live=polite]').textContent.trim() !== ''"},
        ev("getSelection().toString().trim()", "selection"),
        ev("document.querySelector('#bare [aria-live=polite]').textContent.trim()", "notice"),
        initScripts=["Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });"],
    )
    assert_clean(out)
    assert out["results"]["selection"] == "npm test"
    assert out["results"]["notice"] == NOTICE


def test_code_print_hides_the_copy_button_but_keeps_the_filename(elements_page: Path) -> None:
    out = run(
        elements_page,
        {"emulate": {"media": "print"}},
        ev(
            """({
              button: getComputedStyle(document.querySelector('#code button')).display,
              filename: document.querySelector('#code').innerText.includes('deploy.sh'),
            })""",
            "print",
        ),
    )
    assert_clean(out)
    assert out["results"]["print"] == {"button": "none", "filename": True}


# --- q-stat and q-table -----------------------------------------------------------------------


def _stat(idx: str, direction: str | None, delta: str | None, points: str | None = None, *, label: str = "Metric") -> str:
    attrs = ""
    if direction:
        attrs += f' direction="{direction}"'
    if points:
        attrs += f' points="{points}"'
    delta_html = f'\n    <span slot="delta">{delta}</span>' if delta is not None else ""
    return (
        f'  <q-stat id="{idx}"{attrs}>\n    <span slot="label">{label} {idx}</span>\n    <span slot="value">42</span>{delta_html}\n'
        f'    <span slot="definition">Distinct events per day, last 7 days, versus the prior 7 days.</span>\n  </q-stat>\n'
    )


TREND_CASES = [
    ("up_good_pos", "up-good", "+4.2%", "good"),
    ("down_good_pos", "down-good", "+4.2%", "bad"),
    ("down_good_neg", "down-good", "-0.3 pts", "good"),
    ("up_good_neg", "up-good", "−0.3 pts", "bad"),
    ("default_pos", None, "+1", "good"),
    ("digit_lead", "up-good", "12 pts", "good"),
    ("zero", "up-good", "0%", "flat"),
    ("zero_signed", "down-good", "+0.0", "flat"),
]


def _numeric_rows(n: int) -> str:
    return "".join(f"<tr><td>Row {i:02d}</td><td>{i * 7 % 10}</td><td>{'abc'[i % 3]}</td></tr>" for i in range(1, n + 1))


WIDE_COLS = 12
SUITES = [
    {"suite": "integration", "median_s": 342, "runs": 1288, "owner": "Platform"},
    {"suite": "unit", "median_s": 118, "runs": 4120, "owner": "Core"},
    {"suite": "e2e", "median_s": 287, "runs": 640, "owner": "Checkout"},
]

STAT_TABLE_SRC = (
    HEADER.replace('"mode": "offline"', '"mode": "offline", "data": "rows.json"')
    + '<section id="stat-row">\n'
    + _stat("s1", "up-good", "+11.5%", "41,43,42,47,52,58", label="Weekly users")
    + _stat("s2", "down-good", "-0.3 pts", "4.1,3.9,3.6,3.4,3.1", label="Error rate")
    + _stat("s3", "down-good", "+12s", None, label="Support wait")
    + "</section>\n<section id=\"trend-cases\">\n"
    + "".join(_stat(i, d, t) for i, d, t, _ in TREND_CASES)
    + _stat("no_delta", "up-good", None, "5,5,5")
    + _stat("flat_points", "up-good", "+1", "3,3,3,3")
    + "</section>\n"
    + '<section id="tables">\n'
    + '<q-table id="basic"><table><thead><tr><th>Name</th><th class="num">Count</th><th>Group</th></tr></thead><tbody>'
    + "<tr><td>delta</td><td>1,200</td><td>b</td></tr><tr><td>alpha</td><td>9</td><td>c</td></tr>"
    + "<tr><td>charlie</td><td>10</td><td>a</td></tr><tr><td>bravo</td><td>$2.5 / mo</td><td>b</td></tr></tbody></table></q-table>\n"
    + f'<q-table id="rows12"><table><thead><tr><th>Name</th><th class="num">Count</th><th>Group</th></tr></thead><tbody>{_numeric_rows(12)}</tbody></table></q-table>\n'
    + f'<q-table id="rows13"><table><thead><tr><th>Name</th><th class="num">Count</th><th>Group</th></tr></thead><tbody>{_numeric_rows(13)}</tbody></table></q-table>\n'
    + '<q-table id="wide"><table><thead><tr>'
    + "".join(f'<th class="num">Quarterly column {c}</th>' for c in range(WIDE_COLS))
    + "</tr></thead><tbody>"
    + "".join("<tr>" + "".join(f"<td>{r * 1000 + c}</td>" for c in range(WIDE_COLS)) + "</tr>" for r in range(3))
    + "</tbody></table></q-table>\n"
    + '<q-table id="bound" data-from="suites"><table><thead><tr><th>suite</th><th class="num" data-key="median_s">Median (s)</th><th class="num" data-key="runs">Runs</th><th>owner</th><th>absent</th></tr></thead><tbody></tbody></table></q-table>\n'
    + '<q-table id="missing" data-from="nope"><table><thead><tr><th>suite</th></tr></thead><tbody></tbody></table></q-table>\n'
    + "</section>\n"
)

STAT = "document.querySelector('#%s')"


@pytest.fixture(scope="module")
def stat_table_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-stat-table")
    (work / "rows.json").write_text(json.dumps({"suites": SUITES}), encoding="utf-8")
    src = work / "stat-table.src.html"
    src.write_text(STAT_TABLE_SRC, encoding="utf-8")
    page = _build(src, work / "stat-table.html")
    _run_harness({"file": str(page)})
    return page


@pytest.fixture(scope="module")
def stat_table_nojs(stat_table_page: Path) -> Path:
    html = stat_table_page.read_text(encoding="utf-8")
    stripped, count = KIT_SCRIPT.subn("", html)
    assert count == 1
    page = stat_table_page.with_name("stat-table-nojs.html")
    page.write_text(stripped, encoding="utf-8")
    return page


RESOLVE = """const resolve = (name) => {
  const probe = document.createElement('span');
  probe.style.color = 'var(--q-' + name + ')';
  document.body.appendChild(probe);
  const colour = getComputedStyle(probe).color;
  probe.remove();
  return colour;
};"""


def test_stat_trend_follows_sign_and_direction(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """Object.fromEntries([...document.querySelectorAll('#trend-cases q-stat')].map((s) => {
              const d = s.querySelector('[slot=delta]');
              return [s.id, d ? d.getAttribute('data-q-trend') : null];
            }))""",
            "trends",
        ),
    )
    assert_clean(out)
    trends = out["results"]["trends"]
    for idx, _direction, _delta, expected in TREND_CASES:
        assert trends[idx] == expected, (idx, trends[idx])
    assert trends["no_delta"] is None


def test_stat_without_a_delta_inserts_nothing_for_it(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev("document.querySelector('#no_delta').querySelectorAll('[data-q-trend]').length", "n"),
        ev("document.querySelector('#no_delta').innerText.includes('Metric no_delta')", "label"),
    )
    assert_clean(out)
    assert out["results"]["n"] == 0 and out["results"]["label"] is True


def test_stat_trend_updates_when_direction_or_delta_changes(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """(async () => {
              const s = document.querySelector('#up_good_pos');
              const d = s.querySelector('[slot=delta]');
              const trend = () => d.getAttribute('data-q-trend');
              const before = trend();
              s.setAttribute('direction', 'down-good');
              await new Promise((r) => setTimeout(r, 60));
              const flipped = trend();
              d.textContent = '-2%';
              await new Promise((r) => setTimeout(r, 60));
              return { before, flipped, after_text: trend() };
            })()""",
            "changes",
        ),
    )
    assert_clean(out)
    assert out["results"]["changes"] == {"before": "good", "flipped": "bad", "after_text": "good"}


@pytest.mark.parametrize("scheme", SCHEMES)
def test_stat_trend_colours_come_from_tokens(stat_table_page: Path, scheme: str) -> None:
    out = run(
        stat_table_page,
        ev(
            "(() => {"
            + RESOLVE
            + """
            const colour = (id) => getComputedStyle(document.querySelector('#' + id + ' [slot=delta]')).color;
            return {
              good: colour('up_good_pos'), bad: colour('down_good_pos'), flat: colour('zero'),
              tokens: { good: resolve('color-good'), bad: resolve('color-critical'), flat: resolve('color-text-muted') },
            };
            })()""",
            "colours",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    colours = out["results"]["colours"]
    tokens = colours["tokens"]
    assert (colours["good"], colours["bad"], colours["flat"]) == (tokens["good"], tokens["bad"], tokens["flat"])
    assert len({colours["good"], colours["bad"], colours["flat"]}) == 3


def test_stat_sparkline_is_hidden_from_assistive_tech(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """(() => {
              const info = (id) => {
                const root = document.querySelector('#' + id);
                const svgs = root.querySelectorAll('svg');
                const svg = svgs[0];
                const line = svg && svg.querySelector('polyline');
                return {
                  svgs: svgs.length,
                  ariaHidden: svg && svg.getAttribute('aria-hidden'),
                  focusable: svg && svg.getAttribute('focusable'),
                  kit: svg && svg.hasAttribute('data-q-kit'),
                  points: line ? line.getAttribute('points').trim().split(/\\s+/).length : 0,
                  polylines: svg ? svg.querySelectorAll('polyline').length : 0,
                  labelled: svg ? (svg.hasAttribute('aria-label') || !!svg.querySelector('title')) : null,
                  stroke: line && getComputedStyle(line).stroke,
                  ys: line ? line.getAttribute('points').trim().split(/\\s+/).map((p) => Number(p.split(',')[1])) : [],
                };
              };
              return { s1: info('s1'), s2: info('s2'), s3: info('s3'), flat: info('flat_points'), noDelta: info('no_delta') };
            })()""",
            "spark",
        ),
    )
    assert_clean(out)
    spark = out["results"]["spark"]
    assert spark["s1"]["svgs"] == 1 and spark["s1"]["ariaHidden"] == "true" and spark["s1"]["focusable"] == "false"
    assert spark["s1"]["kit"] is True and spark["s1"]["labelled"] is False
    assert spark["s1"]["polylines"] == 1 and spark["s1"]["points"] == 6
    assert spark["s2"]["points"] == 5
    assert spark["s1"]["ys"][0] > spark["s1"]["ys"][-1], "a rising series ends higher on screen (smaller y)"
    assert spark["s3"]["svgs"] == 0, "no points attribute, no sparkline"
    assert spark["noDelta"]["points"] == 3 and spark["flat"]["points"] == 4
    assert len(set(spark["flat"]["ys"])) == 1, "a constant series draws a level line"


@pytest.mark.parametrize("scheme", SCHEMES)
def test_stat_sparkline_stroke_is_the_accent_token(stat_table_page: Path, scheme: str) -> None:
    out = run(
        stat_table_page,
        ev(
            "(() => {" + RESOLVE + " return { stroke: getComputedStyle(document.querySelector('#s1 svg polyline')).stroke, accent: resolve('color-accent') }; })()",
            "stroke",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["stroke"]["stroke"] == out["results"]["stroke"]["accent"]


def test_stat_sparkline_follows_points_attribute_without_duplicating(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """(async () => {
              const s = document.querySelector('#s1');
              const count = () => ({ svgs: s.querySelectorAll('svg').length, points: s.querySelector('svg polyline')?.getAttribute('points').trim().split(/\\s+/).length ?? 0 });
              s.setAttribute('points', '1,2,3');
              await new Promise((r) => setTimeout(r, 60));
              const three = count();
              s.parentNode.appendChild(s);
              await new Promise((r) => setTimeout(r, 60));
              const moved = count();
              s.setAttribute('points', '7');
              await new Promise((r) => setTimeout(r, 60));
              const one = count();
              s.removeAttribute('points');
              await new Promise((r) => setTimeout(r, 60));
              return { three, moved, one, removed: count() };
            })()""",
            "points",
        ),
    )
    assert_clean(out)
    assert out["results"]["points"] == {"three": {"svgs": 1, "points": 3}, "moved": {"svgs": 1, "points": 3}, "one": {"svgs": 0, "points": 0}, "removed": {"svgs": 0, "points": 0}}


def test_adjacent_stats_sit_on_one_row_wide_and_wrap_narrow(stat_table_page: Path) -> None:
    tops = "[...document.querySelectorAll('#stat-row q-stat')].map((s) => Math.round(s.getBoundingClientRect().top))"
    fits = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    out = run(
        stat_table_page,
        ev(tops, "wide_tops"),
        ev("[...document.querySelectorAll('#stat-row q-stat')].map((s) => Math.round(s.getBoundingClientRect().height))", "wide_heights"),
        ev(fits, "wide_fits"),
        {"viewport": {"width": 360, "height": 800}},
        ev(tops, "narrow_tops"),
        ev(fits, "narrow_fits"),
        ev("[...document.querySelectorAll('#stat-row q-stat')].map((s) => s.getBoundingClientRect().right <= document.documentElement.clientWidth)", "narrow_inside"),
        viewport={"width": 1280, "height": 900},
    )
    assert_clean(out)
    assert len(set(out["results"]["wide_tops"])) == 1, out["results"]["wide_tops"]
    assert out["results"]["wide_fits"] is True
    narrow = out["results"]["narrow_tops"]
    assert len(set(narrow)) == 3, narrow
    assert out["results"]["narrow_fits"] is True and all(out["results"]["narrow_inside"])


def test_stat_rows_insert_no_wrapper(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev("[...document.querySelectorAll('#stat-row > *')].map((n) => n.tagName.toLowerCase())", "kids"),
        ev("getComputedStyle(document.querySelector('#s1')).display", "display"),
        ev("getComputedStyle(document.querySelector('#s1')).verticalAlign", "valign"),
    )
    assert_clean(out)
    assert out["results"]["kids"] == ["q-stat"] * 3
    assert out["results"]["display"] == "inline-grid" and out["results"]["valign"] == "top"


def test_stat_reads_label_value_delta_definition(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev("document.querySelector('#s1').innerText", "text"),
        ev("document.querySelector('#s1 [slot=definition]').getBoundingClientRect().height > 0", "definition"),
    )
    assert_clean(out)
    text = out["results"]["text"]
    for part in ("Weekly users s1", "42", "+11.5%", "Distinct events per day"):
        assert part in text
    assert out["results"]["definition"] is True


def _col(table_id: str, index: int, selector: str = "tbody tr:not([hidden])") -> str:
    return f"[...document.querySelectorAll('#{table_id} {selector}')].map((tr) => tr.cells[{index}].innerText.trim())"


def _sorts(table_id: str) -> str:
    return f"[...document.querySelectorAll('#{table_id} thead th')].map((th) => th.getAttribute('aria-sort'))"


def test_table_sort_buttons_cycle_asc_desc_with_one_aria_sort(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """[...document.querySelectorAll('#basic thead th')].map((th) => ({
              buttons: th.querySelectorAll('button').length,
              type: th.querySelector('button')?.type,
              text: th.querySelector('button')?.innerText.trim(),
              kit: th.querySelector('button')?.hasAttribute('data-q-kit'),
            }))""",
            "buttons",
        ),
        ev(_sorts("basic"), "initial_sorts"),
        {"click": "#basic thead th:nth-child(1) button"},
        ev(_col("basic", 0), "asc"),
        ev(_sorts("basic"), "asc_sorts"),
        {"click": "#basic thead th:nth-child(1) button"},
        ev(_col("basic", 0), "desc"),
        ev(_sorts("basic"), "desc_sorts"),
        {"click": "#basic thead th:nth-child(3) button"},
        ev(_sorts("basic"), "other_sorts"),
        ev(_col("basic", 2), "other_col"),
        ev("document.activeElement === document.querySelector('#basic thead th:nth-child(3) button')", "kept_focus"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["buttons"] == [
        {"buttons": 1, "type": "button", "text": "Name", "kit": True},
        {"buttons": 1, "type": "button", "text": "Count", "kit": True},
        {"buttons": 1, "type": "button", "text": "Group", "kit": True},
    ]
    assert results["initial_sorts"] == [None, None, None]
    assert results["asc"] == ["alpha", "bravo", "charlie", "delta"]
    assert results["asc_sorts"] == ["ascending", None, None]
    assert results["desc"] == ["delta", "charlie", "bravo", "alpha"]
    assert results["desc_sorts"] == ["descending", None, None]
    assert results["other_sorts"] == [None, None, "ascending"]
    assert results["other_col"] == sorted(results["other_col"])
    assert results["kept_focus"] is True


def test_table_third_click_restores_the_authored_order(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(_col("basic", 0), "authored"),
        {"click": "#basic thead th:nth-child(1) button"},
        {"click": "#basic thead th:nth-child(1) button"},
        {"click": "#basic thead th:nth-child(1) button"},
        ev(_col("basic", 0), "restored"),
        ev(_sorts("basic"), "sorts"),
        {"click": "#basic thead th:nth-child(1) button"},
        ev(_sorts("basic"), "again"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["restored"] == results["authored"]
    assert results["sorts"] == [None, None, None]
    assert results["again"] == ["ascending", None, None]


def test_table_num_column_sorts_by_value_not_text(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        {"click": "#basic thead th:nth-child(2) button"},
        ev(_col("basic", 1), "asc"),
        {"click": "#basic thead th:nth-child(2) button"},
        ev(_col("basic", 1), "desc"),
    )
    assert_clean(out)
    assert out["results"]["asc"] == ["$2.5 / mo", "9", "10", "1,200"]
    assert out["results"]["desc"] == ["1,200", "10", "9", "$2.5 / mo"]


def test_table_num_sort_puts_cells_without_a_number_last(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev("document.querySelector('#basic tbody tr:nth-child(4) td:nth-child(2)').textContent = 'n/a'", "edit"),
        {"wait": 60},
        {"click": "#basic thead th:nth-child(2) button"},
        ev(_col("basic", 1), "asc"),
        {"click": "#basic thead th:nth-child(2) button"},
        ev(_col("basic", 1), "desc"),
    )
    assert_clean(out)
    assert out["results"]["asc"] == ["9", "10", "1,200", "n/a"]
    assert out["results"]["desc"][-1] == "n/a"


def test_table_sort_is_stable_for_equal_keys(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        {"click": "#basic thead th:nth-child(3) button"},
        ev(_col("basic", 0), "asc_by_group"),
    )
    assert_clean(out)
    assert out["results"]["asc_by_group"] == ["charlie", "delta", "bravo", "alpha"]


def test_table_filter_appears_only_past_twelve_rows(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """Object.fromEntries(['basic', 'rows12', 'rows13'].map((id) => {
              const q = document.querySelector('#' + id);
              return [id, { search: q.querySelectorAll('input[type=search]').length, live: q.querySelectorAll('[aria-live=polite]').length, rows: q.querySelectorAll('tbody tr').length }];
            }))""",
            "filters",
        ),
        ev(
            """(() => {
              const q = document.querySelector('#rows13');
              const input = q.querySelector('input[type=search]');
              const live = q.querySelector('[aria-live=polite]');
              return {
                name: input.getAttribute('aria-label') || input.labels?.[0]?.textContent.trim(),
                kit: input.closest('[data-q-kit]') !== null,
                readout: live.textContent.trim(),
                beforeTable: !!(input.compareDocumentPosition(q.querySelector('table')) & Node.DOCUMENT_POSITION_FOLLOWING),
              };
            })()""",
            "box",
        ),
    )
    assert_clean(out)
    filters = out["results"]["filters"]
    assert filters["basic"]["search"] == 0 and filters["rows12"] == {"search": 0, "live": 0, "rows": 12}
    assert filters["rows13"] == {"search": 1, "live": 1, "rows": 13}
    assert out["results"]["box"] == {"name": "Filter rows", "kit": True, "readout": "13 of 13 rows", "beforeTable": True}


def test_table_filter_narrows_rows_and_updates_readout(stat_table_page: Path) -> None:
    visible = "[...document.querySelectorAll('#rows13 tbody tr')].filter((tr) => tr.getBoundingClientRect().height > 0).map((tr) => tr.cells[0].innerText.trim())"
    readout = "document.querySelector('#rows13 [aria-live=polite]').textContent.trim()"
    out = run(
        stat_table_page,
        {"focus": "#rows13 input[type=search]"},
        {"type": "ROW 1"},
        ev(visible, "narrowed"),
        ev(readout, "readout"),
        {"type": "2"},
        ev(visible, "one"),
        ev(readout, "readout_one"),
        {"type": "9"},
        ev(visible, "none"),
        ev(readout, "readout_none"),
        {"press": "Backspace"},
        {"press": "Backspace"},
        {"press": "Backspace"},
        {"press": "Backspace"},
        {"press": "Backspace"},
        {"press": "Backspace"},
        ev(readout, "readout_back"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["narrowed"] == ["Row 10", "Row 11", "Row 12", "Row 13"]
    assert results["readout"] == "4 of 13 rows"
    assert results["one"] == ["Row 12"] and results["readout_one"] == "1 of 13 rows"
    assert results["none"] == [] and results["readout_none"] == "0 of 13 rows"
    assert results["readout_back"] == "13 of 13 rows"


def test_table_filter_and_sort_work_together(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        {"focus": "#rows13 input[type=search]"},
        {"type": "row 0"},
        {"click": "#rows13 thead th:nth-child(2) button"},
        ev(_col("rows13", 1), "asc"),
        {"click": "#rows13 thead th:nth-child(2) button"},
        ev(_col("rows13", 1), "desc"),
        ev("document.querySelector('#rows13 [aria-live=polite]').textContent.trim()", "readout"),
    )
    assert_clean(out)
    asc = [int(v) for v in out["results"]["asc"]]
    assert len(asc) == 9 and asc == sorted(asc)
    assert [int(v) for v in out["results"]["desc"]] == sorted(asc, reverse=True)
    assert out["results"]["readout"] == "9 of 13 rows"


def test_table_header_row_is_sticky_and_the_element_scrolls(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """(() => {
              const q = document.querySelector('#rows13');
              const qs = getComputedStyle(q);
              const th = getComputedStyle(q.querySelector('thead th'));
              return { display: qs.display, overflowX: qs.overflowX, overflowY: qs.overflowY, maxHeight: qs.maxHeight, sticky: th.position, top: th.top, bg: th.backgroundColor, clear: th.backgroundColor === 'rgba(0, 0, 0, 0)' };
            })()""",
            "long",
        ),
        ev(
            """(() => {
              const q = document.querySelector('#rows12');
              const qs = getComputedStyle(q);
              return { overflowX: qs.overflowX, maxHeight: qs.maxHeight, sticky: getComputedStyle(q.querySelector('thead th')).position };
            })()""",
            "short",
        ),
        ev(
            """(() => {
              const q = document.querySelector('#rows13');
              q.scrollTop = 120;
              const th = q.querySelector('thead th').getBoundingClientRect().top;
              return { stuck: Math.abs(th - q.getBoundingClientRect().top) <= 1, scrolled: q.scrollTop > 0 };
            })()""",
            "stuck",
        ),
    )
    assert_clean(out)
    long = out["results"]["long"]
    assert long["display"] == "block" and long["overflowX"] == "auto" and long["overflowY"] == "auto"
    assert long["maxHeight"] != "none" and long["sticky"] == "sticky" and long["clear"] is False
    short = out["results"]["short"]
    assert short["overflowX"] == "auto" and short["maxHeight"] == "none" and short["sticky"] == "sticky"
    assert out["results"]["stuck"] == {"stuck": True, "scrolled": True}


@pytest.mark.parametrize("scheme", SCHEMES)
def test_table_header_uses_theme_tokens(stat_table_page: Path, scheme: str) -> None:
    out = run(
        stat_table_page,
        ev(
            "(() => {" + RESOLVE + " return { bg: getComputedStyle(document.querySelector('#rows13 thead th')).backgroundColor, surface: resolve('color-surface') }; })()",
            "colours",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["colours"]["bg"] == out["results"]["colours"]["surface"]


@pytest.mark.parametrize("scheme", SCHEMES)
def test_wide_table_scrolls_inside_q_table_not_the_page(stat_table_page: Path, scheme: str) -> None:
    out = run(
        stat_table_page,
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "page_fits"),
        ev(
            """(() => {
              const q = document.querySelector('#wide');
              return { scrolls: q.scrollWidth > q.clientWidth + 20, inside: q.getBoundingClientRect().right <= document.documentElement.clientWidth, overflowX: getComputedStyle(q).overflowX };
            })()""",
            "wide",
        ),
        ev(
            """(() => {
              const q = document.querySelector('#wide');
              q.scrollLeft = 200;
              return { moved: q.scrollLeft > 0, pageMoved: document.documentElement.scrollLeft };
            })()""",
            "scrolled",
        ),
        viewport={"width": 360, "height": 800},
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["page_fits"] is True
    assert out["results"]["wide"] == {"scrolls": True, "inside": True, "overflowX": "auto"}
    assert out["results"]["scrolled"] == {"moved": True, "pageMoved": 0}


def test_table_at_narrow_width_keeps_every_table_inside(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev("[...document.querySelectorAll('q-table')].map((q) => q.getBoundingClientRect().right <= document.documentElement.clientWidth)", "inside"),
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        viewport={"width": 360, "height": 800},
    )
    assert_clean(out)
    assert all(out["results"]["inside"]) and out["results"]["fits"] is True


def test_table_data_from_builds_rows_by_data_key_else_header_text(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """(() => {
              const q = document.querySelector('#bound');
              const rows = [...q.querySelectorAll('tbody tr')];
              return {
                rows: rows.map((tr) => [...tr.cells].map((td) => td.textContent)),
                kitBody: q.querySelectorAll('tbody[data-q-kit]').length,
                numCells: rows.map((tr) => [...tr.cells].map((td) => td.hasAttribute('data-q-num') || td.classList.contains('num'))),
                message: q.querySelector('[data-q-message]')?.textContent ?? null,
                filter: q.querySelectorAll('input[type=search]').length,
              };
            })()""",
            "bound",
        ),
    )
    assert_clean(out)
    bound = out["results"]["bound"]
    assert bound["rows"] == [
        ["integration", "342", "1288", "Platform", ""],
        ["unit", "118", "4120", "Core", ""],
        ["e2e", "287", "640", "Checkout", ""],
    ]
    assert bound["kitBody"] == 1 and bound["message"] is None and bound["filter"] == 0
    assert bound["numCells"][0] == [False, True, True, False, False]


def test_table_data_from_rows_sort_and_rebind_on_data_change(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        {"click": "#bound thead th:nth-child(2) button"},
        ev(_col("bound", 0), "asc"),
        ev(
            """(async () => {
              const q = document.querySelector('#bound');
              q.setAttribute('data-from', 'nope');
              await new Promise((r) => setTimeout(r, 120));
              const missing = q.querySelector('[data-q-message]')?.textContent ?? null;
              q.setAttribute('data-from', 'suites');
              await new Promise((r) => setTimeout(r, 120));
              return { missing, back: q.querySelector('[data-q-message]')?.textContent ?? null, rows: q.querySelectorAll('tbody tr').length };
            })()""",
            "rebind",
        ),
    )
    assert_clean(out)
    assert out["results"]["asc"] == ["unit", "e2e", "integration"]
    assert out["results"]["rebind"] == {"missing": 'No data found for "nope".', "back": None, "rows": 3}


def test_table_data_from_missing_key_shows_the_bind_message(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev("document.querySelector('#missing [data-q-message]')?.textContent ?? null", "message"),
        ev("document.querySelector('#missing').querySelectorAll('tbody tr').length", "rows"),
    )
    assert_clean(out)
    assert out["results"]["message"] == 'No data found for "nope".'
    assert out["results"]["rows"] == 0


def test_table_upgrade_is_idempotent_when_moved(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """(async () => {
              const q = document.querySelector('#rows13');
              const before = q.querySelectorAll('[data-q-kit]').length;
              q.parentNode.appendChild(q);
              await new Promise((r) => setTimeout(r, 120));
              return {
                before,
                buttons: q.querySelectorAll('thead button').length,
                searches: q.querySelectorAll('input[type=search]').length,
                live: q.querySelectorAll('[aria-live=polite]').length,
                kit: q.querySelectorAll('[data-q-kit]').length,
              };
            })()""",
            "moved",
        ),
    )
    assert_clean(out)
    assert out["results"]["moved"]["buttons"] == 3 and out["results"]["moved"]["searches"] == 1 and out["results"]["moved"]["live"] == 1
    assert out["results"]["moved"]["kit"] == out["results"]["moved"]["before"], out["results"]["moved"]


def test_table_filter_disappears_when_rows_drop_to_twelve(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        ev(
            """(async () => {
              const q = document.querySelector('#rows13');
              q.querySelector('tbody tr:last-child').remove();
              await new Promise((r) => setTimeout(r, 120));
              return { searches: q.querySelectorAll('input[type=search]').length, hidden: q.querySelectorAll('tbody tr[hidden]').length };
            })()""",
            "after",
        ),
    )
    assert_clean(out)
    assert out["results"]["after"] == {"searches": 0, "hidden": 0}


def test_table_print_hides_the_filter_and_shows_every_row(stat_table_page: Path) -> None:
    out = run(
        stat_table_page,
        {"focus": "#rows13 input[type=search]"},
        {"emulate": {"media": "print"}},
        ev(
            """(() => {
              const q = document.querySelector('#rows13');
              return { filter: getComputedStyle(q.querySelector('input[type=search]').closest('[data-q-kit]')).display, overflow: getComputedStyle(q).overflowY, maxHeight: getComputedStyle(q).maxHeight };
            })()""",
            "print",
        ),
    )
    assert_clean(out)
    assert out["results"]["print"] == {"filter": "none", "overflow": "visible", "maxHeight": "none"}


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("width", [360, 1280])
def test_stat_and_table_page_has_no_errors_or_page_scroll(stat_table_page: Path, scheme: str, width: int) -> None:
    out = run(
        stat_table_page,
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        ev("[...document.querySelectorAll('q-stat')].every((s) => s.getBoundingClientRect().right <= document.documentElement.clientWidth)", "stats_inside"),
        viewport={"width": width, "height": 800},
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["fits"] is True and out["results"]["stats_inside"] is True


def test_stat_and_table_read_without_the_script(stat_table_nojs: Path) -> None:
    html = stat_table_nojs.read_text(encoding="utf-8")
    assert '<script data-quirk-lib="kit@1.0.0">' not in html
    out = run(
        stat_table_nojs,
        ev(
            """[...document.querySelectorAll('#stat-row q-stat, #basic, #rows13, #wide')].map((el) => ({
              id: el.id, text: el.innerText.trim().length, height: el.getBoundingClientRect().height,
              upgraded: !!el.querySelector('[data-q-kit]'),
            }))""",
            "shown",
        ),
        ev("[...document.querySelectorAll('#stat-row q-stat')].map((s) => ['label', 'value', 'delta', 'definition'].map((n) => { const e = s.querySelector('[slot=' + n + ']'); return !!e && e.innerText.trim().length > 0 && e.getBoundingClientRect().height > 0; }))", "slots"),
        ev("[...document.querySelectorAll('#rows13 tbody tr')].every((tr) => tr.getBoundingClientRect().height > 0)", "rows"),
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        viewport={"width": 360, "height": 800},
    )
    assert_clean(out)
    assert len(out["results"]["shown"]) == 6
    for item in out["results"]["shown"]:
        assert item["text"] > 0 and item["height"] > 0 and item["upgraded"] is False, item
    assert all(all(row) for row in out["results"]["slots"])
    assert out["results"]["rows"] is True and out["results"]["fits"] is True


@pytest.mark.parametrize("scheme", SCHEMES)
def test_stat_and_table_read_without_the_script_in_both_schemes(stat_table_nojs: Path, scheme: str) -> None:
    out = run(
        stat_table_nojs,
        ev("[...document.querySelectorAll('q-stat')].every((s) => s.innerText.trim().length > 0 && s.getBoundingClientRect().height > 0)", "stats"),
        ev("[...document.querySelectorAll('q-table')].every((t) => t.innerText.trim().length > 0 && t.getBoundingClientRect().height > 0)", "tables"),
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["stats"] is True and out["results"]["tables"] is True


# --- q-chart ----------------------------------------------------------------------------------

LONG_CATEGORY = "Payments reconciliation and settlement"
MONTHS = [("June", 14, 3), ("July", 12, 2), ("August", 10, 4), (LONG_CATEGORY, 9, 1)]
CHART_BUILDS = [
    {"suite": "integration", "median_s": 342, "p95_s": 611, "runs": 1288},
    {"suite": "unit", "median_s": 118, "p95_s": 205, "runs": 4120},
    {"suite": "e2e", "median_s": 287, "p95_s": 455, "runs": 640},
]
NINE_SERIES = [{"label": name, **{f"s{n}": n * (i + 1) for n in range(1, 10)}} for i, name in enumerate(["alpha", "bravo", "charlie"])]


def _month_table(series: int = 2) -> str:
    heads = "<th>Month</th><th>Builds</th>" + ("<th>Failures</th>" if series == 2 else "")
    body = "".join(
        f"<tr><td>{m}</td><td>{b}</td>" + (f"<td>{f}</td>" if series == 2 else "") + "</tr>" for m, b, f in MONTHS
    )
    return f"<table><thead><tr>{heads}</tr></thead><tbody>{body}</tbody></table>"


def _chart(chart_id: str, attrs: str, series: int = 2, extra: str = "") -> str:
    summary = f"Summary of {chart_id}: builds fell as the quarter went on."
    return f'<q-chart id="{chart_id}" summary="{summary}" {attrs}>{_month_table(series)}{extra}</q-chart>\n'


RAW_OPTIONS = (
    '<script type="application/json">{"animation": true, "scales": {"x": {"grid": {"color": "#ff0000"}}, '
    '"y": {"grid": {"color": "#ff0000"}}}, "plugins": {"legend": {"display": false}}}</script>'
)
CHART_SRC = (
    HEADER.replace('"mode": "offline"', '"mode": "offline", "data": "rows.json"')
    + _chart("bar", "")
    + _chart("line", 'type="line"', 1)
    + _chart("area", 'type="area"', 1)
    + _chart("donut", 'type="donut"', 1)
    + _chart("stacked", "stacked")
    + _chart("horiz", "horizontal")
    + _chart("linehoriz", 'type="line" horizontal', 1)
    + _chart("stackedline", 'type="area" stacked')
    + _chart("raw", "", 2, RAW_OPTIONS)
    + _chart("badjson", "", 2, '<script type="application/json">{ not json</script>')
    + '<q-chart id="bound" type="bar" horizontal data-from="suites" summary="Integration is the slowest suite, at 342 s median.">'
    + '<table><thead><tr><th data-key="suite">Suite</th><th class="num" data-key="median_s">Median (s)</th><th class="num" data-key="p95_s">p95 (s)</th></tr></thead><tbody></tbody></table></q-chart>\n'
    + '<q-chart id="keyed" data-from="suites" y="runs" x="suite" summary="Unit runs the most often, at 4,120 runs."></q-chart>\n'
    + '<q-chart id="many" data-from="wide" summary="Nine series are too many to read as one chart."></q-chart>\n'
    + '<q-chart id="missing" data-from="nope" summary="This data does not exist."></q-chart>\n'
)
CHART_IDS = ["bar", "line", "area", "donut", "stacked", "horiz", "linehoriz", "stackedline", "raw", "badjson", "bound", "keyed"]
BOUND_IDS = ["bound", "keyed", "many"]
CHART_SCRIPT = re.compile(r'<script data-quirk-lib="chartjs@[^"]*">.*?</script>', re.S)

GET_CHART = "const chartOf = (id) => window.Chart.getChart(document.querySelector('#' + id + ' canvas'));"
CHARTS_DRAWN = "[" + ",".join(f"'{i}'" for i in CHART_IDS) + "].every((id) => { const c = document.querySelector('#' + id + ' canvas'); return c && window.Chart.getChart(c); })"


@pytest.fixture(scope="module")
def chart_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-chart")
    (work / "rows.json").write_text(json.dumps({"suites": CHART_BUILDS, "wide": NINE_SERIES}), encoding="utf-8")
    src = work / "chart.src.html"
    src.write_text(CHART_SRC, encoding="utf-8")
    page = _build(src, work / "chart.html")
    _run_harness({"file": str(page)})
    return page


def _stripped(page: Path, pattern: re.Pattern[str], name: str) -> Path:
    stripped, count = pattern.subn("", page.read_text(encoding="utf-8"))
    assert count == 1, f"the built page should carry exactly one {name} block"
    out = page.with_name(f"{page.stem}-{name}.html")
    out.write_text(stripped, encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def chart_nojs(chart_page: Path) -> Path:
    return _stripped(chart_page, KIT_SCRIPT, "nojs")


@pytest.fixture(scope="module")
def chart_nochartjs(chart_page: Path) -> Path:
    return _stripped(chart_page, CHART_SCRIPT, "nochartjs")


def _drawn() -> dict:
    return {"waitFor": CHARTS_DRAWN}


def test_chart_page_includes_chartjs_and_the_kit_automatically(chart_page: Path) -> None:
    html = chart_page.read_text(encoding="utf-8")
    assert '<script data-quirk-lib="chartjs@' in html and '<script data-quirk-lib="kit@1.0.0">' in html
    assert html.index('<script data-quirk-lib="chartjs@') < html.index('<script data-quirk-lib="kit@1.0.0">')


def test_chart_canvas_is_an_image_labelled_with_the_summary(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""[...document.querySelectorAll('q-chart')].filter((q) => q.querySelector('canvas')).map((q) => {{
              const canvases = q.querySelectorAll('canvas');
              const c = canvases[0];
              return {{ id: q.id, n: canvases.length, role: c.getAttribute('role'), label: c.getAttribute('aria-label'),
                summary: q.getAttribute('summary'), inBox: c.parentElement.hasAttribute('data-q-kit') && c.parentElement.parentElement === q }};
            }})""",
            "canvases",
        ),
    )
    assert_clean(out)
    canvases = out["results"]["canvases"]
    assert {c["id"] for c in canvases} == set(CHART_IDS)
    for c in canvases:
        assert c["n"] == 1 and c["role"] == "img" and c["inBox"], c
        assert c["label"] == c["summary"] and c["label"], c


def test_chart_summary_change_updates_the_label(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev("document.querySelector('#bar').setAttribute('summary', 'A new finding.')", "set"),
        {"waitFor": "document.querySelector('#bar canvas').getAttribute('aria-label') === 'A new finding.'"},
        ev("document.querySelector('#bar canvas').getAttribute('aria-label')", "label"),
    )
    assert_clean(out)
    assert out["results"]["label"] == "A new finding."


def test_chart_source_table_moves_into_a_table_view_details(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            """[...document.querySelectorAll('q-chart')].filter((q) => q.querySelector('canvas') && !q.hasAttribute('data-from')).map((q) => {
              const table = q.querySelector('table');
              const details = table.closest('details');
              return { id: q.id, direct: !!q.querySelector(':scope > table'), kit: details.hasAttribute('data-q-kit'),
                inside: details.parentElement === q, summary: details.querySelector(':scope > summary').textContent,
                open: details.open, rows: table.tBodies[0].rows.length, heads: table.tHead.rows[0].cells.length };
            })""",
            "views",
        ),
    )
    assert_clean(out)
    views = out["results"]["views"]
    assert len(views) == 10
    for view in views:
        assert view["direct"] is False and view["kit"] is True and view["inside"] is True, view
        assert view["summary"] == "Table view" and view["open"] is False, view
        assert view["rows"] == len(MONTHS) and view["heads"] in (2, 3), view


@pytest.mark.parametrize(
    ("chart_id", "config_type", "fill"),
    [("bar", "bar", None), ("line", "line", False), ("area", "line", True), ("donut", "doughnut", None)],
)
def test_chart_type_draws_the_matching_chartjs_chart(chart_page: Path, chart_id: str, config_type: str, fill: bool | None) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(() => {{ {GET_CHART}
              const c = chartOf('{chart_id}');
              return {{ type: c.config.type, fill: c.config.data.datasets[0].fill, n: c.config.data.datasets.length,
                labels: c.config.data.labels.length, data: c.config.data.datasets[0].data }};
            }})()""",
            "chart",
        ),
    )
    assert_clean(out)
    chart = out["results"]["chart"]
    assert chart["type"] == config_type
    assert chart["labels"] == len(MONTHS) and chart["data"] == [m[1] for m in MONTHS]
    if fill is not None:
        assert chart["fill"] is fill
    assert chart["n"] == (2 if chart_id in ("bar",) else 1)


def test_chart_stacked_and_horizontal_reach_the_chartjs_options(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(() => {{ {GET_CHART}
              const o = (id) => {{ const c = chartOf(id); return {{ axis: c.options.indexAxis, sx: c.options.scales.x.stacked, sy: c.options.scales.y.stacked }}; }};
              return {{ bar: o('bar'), stacked: o('stacked'), horiz: o('horiz'), linehoriz: o('linehoriz'), stackedline: o('stackedline') }};
            }})()""",
            "opts",
        ),
    )
    assert_clean(out)
    opts = out["results"]["opts"]
    assert opts["bar"] == {"axis": "x", "sx": False, "sy": False}
    assert opts["stacked"] == {"axis": "x", "sx": True, "sy": True}
    assert opts["horiz"] == {"axis": "y", "sx": False, "sy": False}
    assert opts["linehoriz"]["axis"] == "x", "horizontal applies to bars only"
    assert opts["stackedline"]["sy"] is True


COLOURS = (
    "const token = (n) => getComputedStyle(document.documentElement).getPropertyValue('--q-' + n).trim();"
    "const chartColours = () => [1, 2, 3, 4, 5, 6, 7, 8].map((n) => token('color-chart-' + n));"
)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_chart_dataset_colours_equal_the_chart_tokens(chart_page: Path, scheme: str) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(() => {{ {GET_CHART} {COLOURS}
              const sets = (id) => chartOf(id).config.data.datasets;
              return {{
                tokens: chartColours(),
                bar: sets('bar').map((d) => d.backgroundColor),
                barEdge: sets('bar').map((d) => d.borderColor),
                line: sets('line').map((d) => d.borderColor),
                area: sets('area').map((d) => d.borderColor),
                donut: sets('donut')[0].backgroundColor,
              }};
            }})()""",
            "colours",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    colours = out["results"]["colours"]
    tokens = colours["tokens"]
    assert all(tokens) and len(set(tokens)) == 8
    assert colours["bar"] == tokens[:2] and colours["barEdge"] == tokens[:2]
    assert colours["line"] == [tokens[0]] and colours["area"] == [tokens[0]]
    assert colours["donut"] == tokens[:4]


def test_chart_tokens_differ_between_schemes(chart_page: Path) -> None:
    results = {}
    for scheme in SCHEMES:
        out = run(chart_page, _drawn(), ev(f"(() => {{ {GET_CHART} return chartOf('bar').config.data.datasets[0].backgroundColor; }})()", "c"), colorScheme=scheme)
        assert_clean(out)
        results[scheme] = out["results"]["c"]
    assert results["light"] != results["dark"]


def test_chart_redraws_when_data_theme_changes_without_a_theme_event(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(() => {{ {GET_CHART} {COLOURS}
              window.__before = chartOf('bar'); window.__lightColour = chartColours()[0];
              return {{ light: window.__lightColour, matches: window.__before.config.data.datasets[0].backgroundColor === window.__lightColour }};
            }})()""",
            "before",
        ),
        ev("document.documentElement.setAttribute('data-theme', 'dark')", "toggle"),
        {"waitFor": f"(() => {{ {GET_CHART} return chartOf('bar') !== window.__before; }})()"},
        ev(
            f"""(() => {{ {GET_CHART} {COLOURS}
              const c = chartOf('bar');
              return {{ dark: chartColours()[0], colour: c.config.data.datasets[0].backgroundColor, tick: c.options.scales.y.ticks.color,
                muted: token('color-text-muted'), oldDestroyed: window.__before.ctx === null,
                donut: chartOf('donut').config.data.datasets[0].backgroundColor[0] }};
            }})()""",
            "after",
        ),
        colorScheme="light",
    )
    assert_clean(out)
    before, after = out["results"]["before"], out["results"]["after"]
    assert before["matches"] is True
    assert after["dark"] != before["light"]
    assert after["colour"] == after["dark"] and after["donut"] == after["dark"]
    assert after["tick"] == after["muted"]
    assert after["oldDestroyed"] is True


def test_chart_raw_options_are_merged_but_the_guarantees_win(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(() => {{ {GET_CHART} {COLOURS}
              const o = chartOf('raw').options;
              const plain = chartOf('bar').options;
              return {{
                animation: o.animation, responsive: o.responsive, aspect: o.maintainAspectRatio,
                gridX: o.scales.x.grid.color, gridY: o.scales.y.grid.color, border: token('color-border'),
                legendDisplay: o.plugins.legend.display, plainLegend: plain.plugins.legend.display,
                legendColour: o.plugins.legend.labels.color, text: token('color-text'), muted: token('color-text-muted'),
                tickX: o.scales.x.ticks.color, tickY: o.scales.y.ticks.color,
                tipTitle: o.plugins.tooltip.titleColor, tipBody: o.plugins.tooltip.bodyColor, tipBorder: o.plugins.tooltip.borderColor,
                plainAnimation: plain.animation,
              }};
            }})()""",
            "raw",
        ),
    )
    assert_clean(out)
    raw = out["results"]["raw"]
    assert raw["animation"] is False and raw["plainAnimation"] is False
    assert raw["responsive"] is True and raw["aspect"] is False
    assert raw["gridX"] == raw["border"] and raw["gridY"] == raw["border"] and raw["border"] != "#ff0000"
    assert raw["legendDisplay"] is False and raw["plainLegend"] is True, "raw options outside the guarantees are kept"
    assert raw["legendColour"] == raw["text"]
    assert raw["tickX"] == raw["muted"] == raw["tickY"]
    assert raw["tipTitle"] == raw["text"] and raw["tipBody"] == raw["text"] and raw["tipBorder"] == raw["border"]


def test_chart_invalid_raw_json_is_ignored_without_a_console_error(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(f"(() => {{ {GET_CHART} const c = chartOf('badjson'); return {{ type: c.config.type, animation: c.options.animation }}; }})()", "bad"),
    )
    assert_clean(out)
    assert out["results"]["bad"] == {"type": "bar", "animation": False}


def test_chart_long_category_labels_are_truncated_and_the_tooltip_has_the_full_text(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(() => {{ {GET_CHART}
              const c = chartOf('bar');
              const title = c.options.plugins.tooltip.callbacks.title;
              return {{ labels: c.config.data.labels, titles: c.config.data.labels.map((_, i) => title([{{ dataIndex: i }}])) }};
            }})()""",
            "labels",
        ),
    )
    assert_clean(out)
    labels = out["results"]["labels"]
    assert labels["labels"][:3] == ["June", "July", "August"]
    assert labels["labels"][3] == LONG_CATEGORY[:23] + "…" and len(labels["labels"][3]) == 24
    assert labels["titles"][3] == LONG_CATEGORY and labels["titles"][0] == "June"


def test_chart_bound_data_draws_with_columns_from_the_table_headers(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(() => {{ {GET_CHART}
              const c = chartOf('bound');
              const q = document.querySelector('#bound');
              const table = q.querySelector('details > table');
              return {{ type: c.config.type, axis: c.options.indexAxis, labels: c.config.data.labels,
                series: c.config.data.datasets.map((d) => d.label), values: c.config.data.datasets.map((d) => d.data),
                rows: [...table.tBodies].flatMap((b) => [...b.rows]).filter((r) => !r.hidden).map((r) => [...r.cells].map((x) => x.textContent)),
                open: table.closest('details').open, note: q.querySelector('[data-q-note]') }};
            }})()""",
            "bound",
        ),
    )
    assert_clean(out)
    bound = out["results"]["bound"]
    assert bound["type"] == "bar" and bound["axis"] == "y"
    assert bound["labels"] == ["integration", "unit", "e2e"]
    assert bound["series"] == ["Median (s)", "p95 (s)"]
    assert bound["values"] == [[342, 118, 287], [611, 205, 455]]
    assert bound["rows"] == [["integration", "342", "611"], ["unit", "118", "205"], ["e2e", "287", "455"]]
    assert bound["open"] is False and bound["note"] is None


def test_chart_bound_data_without_a_table_generates_one_and_honours_x_and_y(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(() => {{ {GET_CHART}
              const c = chartOf('keyed');
              const table = document.querySelector('#keyed details[data-q-kit] > table');
              return {{ labels: c.config.data.labels, series: c.config.data.datasets.map((d) => d.label), values: c.config.data.datasets[0].data,
                heads: [...table.tHead.rows[0].cells].map((x) => x.textContent), rows: table.tBodies[0].rows.length, summary: table.closest('details').querySelector('summary').textContent }};
            }})()""",
            "keyed",
        ),
    )
    assert_clean(out)
    keyed = out["results"]["keyed"]
    assert keyed["labels"] == ["integration", "unit", "e2e"] and keyed["series"] == ["runs"] and keyed["values"] == [1288, 4120, 640]
    assert keyed["heads"] == ["suite", "median_s", "p95_s", "runs"] and keyed["rows"] == 3 and keyed["summary"] == "Table view"


def test_chart_bound_data_with_more_than_eight_series_shows_the_table_with_a_note(chart_page: Path) -> None:
    out = run(
        chart_page,
        {"waitFor": "document.querySelector('#many details table')"},
        ev(
            """(() => {
              const q = document.querySelector('#many');
              const details = q.querySelector('details[data-q-kit]');
              const table = details.querySelector('table');
              const note = q.querySelector('[data-q-note]');
              return { canvas: !!q.querySelector('canvas'), open: details.open, noteText: note && note.textContent.trim(),
                visible: table.getBoundingClientRect().height > 0, heads: table.tHead.rows[0].cells.length, rows: table.tBodies[0].rows.length };
            })()""",
            "many",
        ),
    )
    assert_clean(out)
    many = out["results"]["many"]
    assert many["canvas"] is False and many["open"] is True and many["visible"] is True
    assert many["noteText"] == "Too many series to chart clearly (9); showing the table."
    assert many["heads"] == 10 and many["rows"] == 3


def test_chart_bound_data_that_is_missing_says_so_without_throwing(chart_page: Path) -> None:
    out = run(chart_page, _drawn(), ev("document.querySelector('#missing [data-q-message]').textContent", "msg"))
    assert_clean(out)
    assert "nope" in out["results"]["msg"]


def test_chart_rebinds_and_redraws_when_data_from_changes(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(async () => {{ {GET_CHART}
              const q = document.querySelector('#keyed');
              const wait = () => new Promise((r) => setTimeout(r, 150));
              q.setAttribute('x', 'label'); q.setAttribute('y', 's1,s2'); q.setAttribute('data-from', 'wide');
              await wait();
              const wide = {{ labels: chartOf('keyed').config.data.labels, series: chartOf('keyed').config.data.datasets.map((d) => d.label) }};
              q.setAttribute('x', 'suite'); q.setAttribute('y', 'runs'); q.setAttribute('data-from', 'suites');
              await wait();
              const back = {{ labels: chartOf('keyed').config.data.labels, rows: q.querySelectorAll('details table tbody tr').length, canvases: q.querySelectorAll('canvas').length }};
              return {{ wide, back }};
            }})()""",
            "rebind",
        ),
    )
    assert_clean(out)
    rebind = out["results"]["rebind"]
    assert rebind["wide"] == {"labels": ["alpha", "bravo", "charlie"], "series": ["s1", "s2"]}
    assert rebind["back"] == {"labels": ["integration", "unit", "e2e"], "rows": 3, "canvases": 1}


def test_chart_stays_a_single_canvas_and_table_view_when_moved(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev(
            f"""(async () => {{ {GET_CHART}
              const q = document.querySelector('#bar');
              const parent = q.parentElement;
              const next = q.nextSibling;
              q.remove();
              parent.insertBefore(q, next);
              await new Promise((r) => setTimeout(r, 200));
              return {{ canvases: q.querySelectorAll('canvas').length, details: q.querySelectorAll(':scope > details').length,
                tables: q.querySelectorAll('table').length, boxes: q.querySelectorAll(':scope > [data-q-kit]').length,
                drawn: !!chartOf('bar') }};
            }})()""",
            "moved",
        ),
    )
    assert_clean(out)
    assert out["results"]["moved"] == {"canvases": 1, "details": 1, "tables": 1, "boxes": 2, "drawn": True}


def test_chart_table_view_shows_when_chartjs_is_missing(chart_nochartjs: Path) -> None:
    html = chart_nochartjs.read_text(encoding="utf-8")
    assert '<script data-quirk-lib="chartjs@' not in html and '<script data-quirk-lib="kit@1.0.0">' in html
    out = run(
        chart_nochartjs,
        {"waitFor": "document.querySelector('#bound details table')"},
        ev(
            """['bar', 'donut', 'bound', 'many'].map((id) => {
              const q = document.querySelector('#' + id);
              const details = q.querySelector('details');
              const table = details && details.querySelector('table');
              return { id, hasChartjs: typeof window.Chart, canvas: !!q.querySelector('canvas'), open: !!details && details.open,
                visible: !!table && table.getBoundingClientRect().height > 0 && table.innerText.trim().length > 0 };
            })""",
            "views",
        ),
    )
    assert_clean(out)
    for view in out["results"]["views"]:
        assert view["hasChartjs"] == "undefined" and view["canvas"] is False, view
        assert view["open"] is True and view["visible"] is True, view


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("width", [360, 1024])
def test_chart_page_has_no_errors_or_page_scroll(chart_page: Path, scheme: str, width: int) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        ev("[...document.querySelectorAll('q-chart')].every((q) => q.getBoundingClientRect().right <= document.documentElement.clientWidth)", "inside"),
        ev("[...document.querySelectorAll('q-chart canvas')].every((c) => c.getBoundingClientRect().width > 0 && c.getBoundingClientRect().height > 0)", "sized"),
        {"eval": "document.querySelectorAll('q-chart details').forEach((d) => { d.open = true; })", "as": "open"},
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fitsOpen"),
        viewport={"width": width, "height": 800},
        colorScheme=scheme,
    )
    assert_clean(out)
    results = out["results"]
    assert results["fits"] is True and results["inside"] is True and results["sized"] is True and results["fitsOpen"] is True


def test_chart_box_uses_the_height_token(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        ev("document.querySelector('#bar canvas').parentElement.getBoundingClientRect().height", "default"),
        ev("document.querySelector('#bar').style.setProperty('--q-chart-height', '200px'); document.querySelector('#bar canvas').parentElement.getBoundingClientRect().height", "custom"),
    )
    assert_clean(out)
    assert out["results"]["default"] == 320 and out["results"]["custom"] == 200


def test_chart_print_keeps_the_table_view_open_and_hides_its_toggle(chart_page: Path) -> None:
    out = run(
        chart_page,
        _drawn(),
        {"emulate": {"media": "print"}},
        ev(
            """(() => {
              const details = document.querySelector('#bar details');
              return { open: details.open, toggle: getComputedStyle(details.querySelector('summary')).display,
                table: details.querySelector('table').getBoundingClientRect().height > 0 };
            })()""",
            "print",
        ),
    )
    assert_clean(out)
    assert out["results"]["print"]["toggle"] == "none" and out["results"]["print"]["table"] is True


def test_chart_reads_without_the_script(chart_nojs: Path) -> None:
    html = chart_nojs.read_text(encoding="utf-8")
    assert '<script data-quirk-lib="kit@1.0.0">' not in html and '<style data-quirk-lib="kit@1.0.0">' in html
    out = run(
        chart_nojs,
        ev(
            """[...document.querySelectorAll('q-chart')].map((q) => ({
              id: q.id, text: q.innerText.trim().length, height: q.getBoundingClientRect().height,
              hasTable: !!q.querySelector('table'),
              tables: [...q.querySelectorAll('table')].every((t) => t.getBoundingClientRect().height > 0),
              upgraded: !!q.querySelector('[data-q-kit]'),
              finding: getComputedStyle(q, '::before').content.includes(q.getAttribute('summary').slice(0, 12)),
            }))""",
            "charts",
        ),
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        viewport={"width": 360, "height": 800},
    )
    assert_clean(out)
    charts = out["results"]["charts"]
    assert len(charts) == 14
    for chart in charts:
        assert chart["height"] > 0 and chart["tables"] is True and chart["upgraded"] is False, chart
        assert chart["finding"] is True, "the summary shows as text when the script is absent"
        if chart["hasTable"]:
            assert chart["text"] > 0, chart
    assert out["results"]["fits"] is True


@pytest.mark.parametrize("scheme", SCHEMES)
def test_chart_reads_without_the_script_in_both_schemes(chart_nojs: Path, scheme: str) -> None:
    out = run(
        chart_nojs,
        ev("[...document.querySelectorAll('q-chart')].every((q) => q.getBoundingClientRect().height > 0 && (!q.querySelector('table') || q.innerText.trim().length > 0))", "all"),
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["all"] is True


def test_report_example_renders_stats_chart_and_table_from_the_data(tmp_path: Path) -> None:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    example = SKILL / "templates" / "report"
    src = tmp_path / "example.src.html"
    shutil.copy(example / "example.src.html", src)
    shutil.copy(example / "timings.json", tmp_path / "timings.json")
    page = _build(src, tmp_path / "example.html")
    source = src.read_text(encoding="utf-8")
    assert '"libraries"' not in source and "<script>" not in source, "the kit and Chart.js come in automatically"
    html = page.read_text(encoding="utf-8")
    assert "chartjs@" in html and "x-data" not in html and "drawChart" not in html
    out = run(
        page,
        {"waitFor": "document.querySelector('q-chart canvas') && document.querySelectorAll('q-table tbody tr').length > 0"},
        ev(
            """(() => {
              const chart = window.Chart.getChart(document.querySelector('q-chart canvas'));
              const rows = [...document.querySelectorAll('q-table tbody:not([hidden]) tr')];
              return { stats: document.querySelectorAll('q-stat').length, labels: chart.config.data.labels,
                series: chart.config.data.datasets.length, rows: rows.length,
                label: document.querySelector('q-chart canvas').getAttribute('aria-label'),
                sortable: document.querySelectorAll('q-table th > button[data-q-sort]').length };
            })()""",
            "example",
        ),
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        viewport={"width": 360, "height": 800},
    )
    assert_clean(out)
    example_out = out["results"]["example"]
    assert example_out["stats"] == 3 and example_out["series"] == 2 and example_out["rows"] == 6
    assert example_out["labels"][0] == "integration" and len(example_out["labels"]) == 6
    assert example_out["sortable"] == 6 and example_out["label"]
    assert out["results"]["fits"] is True


# --- q-diff and q-diff-note -------------------------------------------------------------------

DIFF_TEXT = (
    "diff --git a/src/app.py b/src/app.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/src/app.py\n"
    "+++ b/src/app.py\n"
    "@@ -1,4 +1,5 @@\n"
    " import os\n"
    "-import sys\n"
    "+import json\n"
    "+import logging\n"
    " \n"
    " def main():\n"
    "@@ -20,3 +21,3 @@ def run():\n"
    "     value = 1\n"
    "-    return value\n"
    "+    return value + 1\n"
    "     # end\n"
    "--- a/web/index.html\n"
    "+++ b/web/index.html\n"
    "@@ -5,3 +5,5 @@\n"
    " &lt;p&gt;keep&lt;/p&gt;\n"
    "-&lt;b&gt;old&lt;/b&gt;\n"
    "+&lt;b&gt;x&lt;/b&gt;\n"
    "+&lt;i&gt;new&lt;/i&gt;\n"
    f"+{LONG_UNBROKEN}\n"
    " &lt;p&gt;tail&lt;/p&gt;\n"
)

DIFF_SRC = (
    HEADER
    + f"""<q-diff id="diff">
  <pre>{DIFF_TEXT}</pre>
  <q-diff-note id="note-a" file="src/app.py" line="22">Adds one to the value.</q-diff-note>
  <q-diff-note id="note-b" file="web/index.html" line="6">Escape this before it reaches the page.</q-diff-note>
  <q-diff-note id="note-c" file="web/index.html" line="6">A second note on the same line.</q-diff-note>
  <q-diff-note id="note-d" file="src/app.py" line="2">The json import is new.</q-diff-note>
</q-diff>
"""
)

DIFF_VIEW = "document.querySelector('#diff > [data-q-diff]')"
DIFF_ROWS = (
    "[..."
    + DIFF_VIEW
    + ".querySelectorAll('tr')].map((tr) => ({"
    " cls: tr.className,"
    " old: (tr.querySelector('[data-q-old]') || {}).textContent ?? null,"
    " new: (tr.querySelector('[data-q-new]') || {}).textContent ?? null,"
    " text: (tr.querySelector('[data-q-code]') || tr.cells[0] || {}).textContent ?? ''"
    "}))"
)
FITS_PAGE = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
DIFF_ROW_COUNT = 16

HIDE_PROBE = """
(() => {
  window.__hides = [];
  const original = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function (name, value) {
    if (name === 'data-q-replaced') {
      window.__hides.push({
        tag: this.localName,
        clones: document.querySelectorAll('#diff > [data-q-diff] .q-diff-note-row').length,
        view: !!document.querySelector('#diff > [data-q-diff]'),
      });
    }
    return original.call(this, name, value);
  };
})();
"""


@pytest.fixture(scope="module")
def diff_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-diff")
    src = work / "diff.src.html"
    src.write_text(DIFF_SRC, encoding="utf-8")
    page = _build(src, work / "diff.html")
    _run_harness({"file": str(page)})
    return page


@pytest.fixture(scope="module")
def diff_nojs(diff_page: Path) -> Path:
    html = diff_page.read_text(encoding="utf-8")
    stripped, count = KIT_SCRIPT.subn("", html)
    assert count == 1
    page = diff_page.with_name("diff-nojs.html")
    page.write_text(stripped, encoding="utf-8")
    return page


def _row(rows: list[dict], cls: str, text: str) -> dict:
    matches = [r for r in rows if cls in r["cls"].split() and r["text"][1:] == text]
    assert len(matches) == 1, (cls, text, rows)
    return matches[0]


def _numbers(rows: list[dict], cls: str, text: str) -> tuple[str, str]:
    row = _row(rows, cls, text)
    return row["old"], row["new"]


def test_diff_renders_both_file_headers_and_every_hunk(diff_page: Path) -> None:
    out = run(diff_page, ev(DIFF_ROWS, "rows"))
    assert_clean(out)
    rows = out["results"]["rows"]
    assert [r["text"].strip() for r in rows if "q-diff-file" in r["cls"].split()] == ["src/app.py", "web/index.html"]
    assert [r["text"] for r in rows if "q-diff-hunk" in r["cls"].split()] == [
        "@@ -1,4 +1,5 @@",
        "@@ -20,3 +21,3 @@ def run():",
        "@@ -5,3 +5,5 @@",
    ]
    assert [r["text"] for r in rows if "q-diff-meta" in r["cls"].split()] == [
        "diff --git a/src/app.py b/src/app.py",
        "index 1111111..2222222 100644",
    ]


def test_diff_added_and_removed_rows_have_distinct_classes_and_a_text_marker(diff_page: Path) -> None:
    rows = run(diff_page, ev(DIFF_ROWS, "rows"))["results"]["rows"]
    added = _row(rows, "q-diff-add", "import json")
    removed = _row(rows, "q-diff-del", "import sys")
    context = _row(rows, "q-diff-ctx", "import os")
    assert (added["text"][0], removed["text"][0], context["text"][0]) == ("+", "-", " ")
    assert len({added["cls"], removed["cls"], context["cls"]}) == 3
    assert not {"q-diff-add", "q-diff-del"} & set(context["cls"].split())


def test_diff_line_numbers_follow_the_hunk_headers(diff_page: Path) -> None:
    rows = run(diff_page, ev(DIFF_ROWS, "rows"))["results"]["rows"]
    assert _numbers(rows, "q-diff-del", "import sys") == ("2", "")
    assert _numbers(rows, "q-diff-add", "import json") == ("", "2")
    assert _numbers(rows, "q-diff-add", "import logging") == ("", "3")
    assert _numbers(rows, "q-diff-ctx", "def main():") == ("4", "5")
    assert _numbers(rows, "q-diff-ctx", "    value = 1") == ("20", "21")
    assert _numbers(rows, "q-diff-del", "    return value") == ("21", "")
    assert _numbers(rows, "q-diff-add", "    return value + 1") == ("", "22")
    assert _numbers(rows, "q-diff-ctx", "    # end") == ("22", "23")
    assert _numbers(rows, "q-diff-add", "<b>x</b>") == ("", "6")
    assert _numbers(rows, "q-diff-ctx", "<p>tail</p>") == ("7", "9")


def test_diff_new_side_numbers_match_the_static_check(diff_page: Path) -> None:
    import html as html_lib

    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        from htmlkit.kitcheck import parse_diff
    finally:
        sys.path.remove(str(SKILL / "scripts"))
    expected = parse_diff(html_lib.unescape(DIFF_TEXT))
    out = run(
        diff_page,
        ev(
            """(() => {
              const byFile = {};
              let file = null;
              for (const tr of document.querySelectorAll('#diff > [data-q-diff] tr')) {
                if (tr.classList.contains('q-diff-file')) { file = tr.textContent.trim(); byFile[file] = []; }
                const n = tr.querySelector('[data-q-new]');
                if (file && n && n.textContent) byFile[file].push(Number(n.textContent));
              }
              return byFile;
            })()""",
            "numbers",
        ),
    )
    assert {f: sorted(n) for f, n in out["results"]["numbers"].items()} == {f: sorted(n) for f, n in expected.items()}


def test_diff_notes_render_directly_under_their_line(diff_page: Path) -> None:
    rows = run(diff_page, ev(DIFF_ROWS, "rows"))["results"]["rows"]

    def under(code: str) -> list[str]:
        at = next(i for i, r in enumerate(rows) if r["text"] == code)
        notes = []
        for row in rows[at + 1 :]:
            if "q-diff-note-row" not in row["cls"].split():
                break
            notes.append(row["text"].strip())
        return notes

    assert [n.endswith(t) for n, t in zip(under("+    return value + 1"), ["Adds one to the value."])] == [True]
    assert [n.endswith(t) for n, t in zip(under("+import json"), ["The json import is new."])] == [True]
    second_file = under("+<b>x</b>")
    assert len(second_file) == 2
    assert second_file[0].endswith("Escape this before it reaches the page.") and second_file[1].endswith("A second note on the same line.")
    assert len([r for r in rows if "q-diff-note-row" in r["cls"].split()]) == 4


def test_diff_original_notes_are_hidden_only_after_their_clones_exist(diff_page: Path) -> None:
    out = run(
        diff_page,
        ev("window.__hides", "hides"),
        ev(
            "[...document.querySelectorAll('#diff > q-diff-note')].map((n) => ({ display: getComputedStyle(n).display, hidden: n.hasAttribute('data-q-replaced') }))",
            "notes",
        ),
        initScripts=[HIDE_PROBE],
    )
    assert_clean(out)
    hides = out["results"]["hides"]
    assert sorted(h["tag"] for h in hides) == ["pre", "q-diff-note", "q-diff-note", "q-diff-note", "q-diff-note"]
    assert all(h["view"] for h in hides)
    assert all(h["clones"] == 4 for h in hides if h["tag"] == "q-diff-note")
    assert out["results"]["notes"] == [{"display": "none", "hidden": True}] * 4


def test_diff_note_that_matches_no_row_stays_visible(diff_page: Path) -> None:
    out = run(
        diff_page,
        ev(
            """(async () => {
              const note = document.createElement('q-diff-note');
              note.setAttribute('file', 'src/app.py');
              note.setAttribute('line', '999');
              note.textContent = 'Nowhere to go.';
              document.querySelector('#diff').appendChild(note);
              await new Promise((r) => setTimeout(r, 50));
              return {
                display: getComputedStyle(note).display,
                hidden: note.hasAttribute('data-q-replaced'),
                clones: document.querySelectorAll('#diff .q-diff-note-row').length,
                height: note.getBoundingClientRect().height,
              };
            })()""",
            "orphan",
        ),
    )
    assert_clean(out)
    orphan = out["results"]["orphan"]
    assert (orphan["display"], orphan["hidden"], orphan["clones"]) == ("list-item", False, 4)
    assert orphan["height"] > 0


@pytest.mark.parametrize("media", ["screen", "print"])
def test_diff_raw_pre_is_hidden_after_upgrade_in_every_medium(diff_page: Path, media: str) -> None:
    out = run(
        diff_page,
        ev(
            """(() => {
              const pre = document.querySelector('#diff > pre');
              const view = document.querySelector('#diff > [data-q-diff]');
              return {
                pre: getComputedStyle(pre).display,
                marked: pre.hasAttribute('data-q-replaced'),
                view: getComputedStyle(view).display,
                viewHeight: view.getBoundingClientRect().height,
                notes: [...document.querySelectorAll('#diff > q-diff-note')].map((n) => getComputedStyle(n).display),
              };
            })()""",
            "state",
        ),
        media=media,
    )
    assert_clean(out)
    state = out["results"]["state"]
    assert state["pre"] == "none" and state["marked"] is True
    assert state["view"] != "none" and state["viewHeight"] > 0
    assert state["notes"] == ["none"] * 4


def test_diff_text_is_rendered_literally_not_as_markup(diff_page: Path) -> None:
    out = run(
        diff_page,
        ev(
            """(() => {
              const view = document.querySelector('#diff > [data-q-diff]');
              return {
                elements: view.querySelectorAll('b, i').length,
                text: view.textContent.includes('+<b>x</b>'),
                shown: view.innerText.includes('<i>new</i>'),
              };
            })()""",
            "literal",
        ),
    )
    assert_clean(out)
    assert out["results"]["literal"] == {"elements": 0, "text": True, "shown": True}


def test_diff_upgrade_is_idempotent_when_moved_and_follows_edits(diff_page: Path) -> None:
    out = run(
        diff_page,
        ev(
            """(async () => {
              const diff = document.querySelector('#diff');
              const settle = () => new Promise((r) => setTimeout(r, 50));
              const count = () => ({
                views: diff.querySelectorAll(':scope > [data-q-diff]').length,
                notes: diff.querySelectorAll('.q-diff-note-row').length,
                rows: diff.querySelectorAll('.q-diff-add, .q-diff-del, .q-diff-ctx').length,
              });
              const before = count();
              document.body.appendChild(diff);
              await settle();
              const moved = count();
              diff.querySelector('q-diff-note').remove();
              await settle();
              const removed = count();
              diff.querySelector('pre').textContent = '--- a/f\\n+++ b/f\\n@@ -1 +1 @@\\n-a\\n+b\\n';
              await settle();
              return { before, moved, removed, after: count(), pre: getComputedStyle(diff.querySelector('pre')).display };
            })()""",
            "counts",
        ),
    )
    assert_clean(out)
    counts = out["results"]["counts"]
    assert counts["before"] == counts["moved"] == {"views": 1, "notes": 4, "rows": DIFF_ROW_COUNT}
    assert counts["removed"] == {"views": 1, "notes": 3, "rows": DIFF_ROW_COUNT}
    assert counts["after"] == {"views": 1, "notes": 0, "rows": 2}
    assert counts["pre"] == "none"


@pytest.mark.parametrize("scheme", SCHEMES)
def test_diff_rows_use_theme_tokens_and_differ_by_kind(diff_page: Path, scheme: str) -> None:
    out = run(
        diff_page,
        ev(
            "(() => {"
            + RESOLVE
            + """
              const style = (sel) => getComputedStyle(document.querySelector(sel));
              return {
                add: style('#diff tr.q-diff-add [data-q-code]').backgroundColor,
                del: style('#diff tr.q-diff-del [data-q-code]').backgroundColor,
                ctx: style('#diff tr.q-diff-ctx [data-q-code]').backgroundColor,
                addMarker: style('#diff tr.q-diff-add .q-diff-marker').color,
                delMarker: style('#diff tr.q-diff-del .q-diff-marker').color,
                text: style('#diff tr.q-diff-add [data-q-code]').color,
                good: resolve('color-good'),
                critical: resolve('color-critical'),
                expectedText: resolve('color-text'),
              };
            })()""",
            "colours",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    c = out["results"]["colours"]
    assert len({c["add"], c["del"], c["ctx"]}) == 3
    assert c["addMarker"] == c["good"] and c["delMarker"] == c["critical"]
    assert c["text"] == c["expectedText"]


def test_diff_row_colours_follow_the_scheme(diff_page: Path) -> None:
    probe = ev(
        "[...['add', 'del'].map((k) => getComputedStyle(document.querySelector('#diff tr.q-diff-' + k + ' [data-q-code]')).backgroundColor)]",
        "bg",
    )
    light = run(diff_page, probe, colorScheme="light")["results"]["bg"]
    dark = run(diff_page, probe, colorScheme="dark")["results"]["bg"]
    assert light[0] != dark[0] and light[1] != dark[1]


@pytest.mark.parametrize("scheme", SCHEMES)
def test_diff_at_360px_scrolls_inside_the_element_not_the_page(diff_page: Path, scheme: str) -> None:
    out = run(
        diff_page,
        ev(FITS_PAGE, "fits"),
        ev(
            f"""(() => {{
              const view = {DIFF_VIEW};
              return {{
                overflowX: getComputedStyle(view).overflowX,
                scrolls: view.scrollWidth > view.clientWidth,
                inside: view.getBoundingClientRect().right <= document.documentElement.clientWidth,
              }};
            }})()""",
            "view",
        ),
        ev(
            f"""(() => {{
              const view = {DIFF_VIEW};
              const note = view.querySelector('.q-diff-note-row [data-q-note]');
              view.scrollLeft = view.scrollWidth;
              const n = note.getBoundingClientRect();
              const v = view.getBoundingClientRect();
              return {{ left: n.left >= v.left - 1, right: n.right <= v.right + 1 }};
            }})()""",
            "note",
        ),
        viewport={"width": 360, "height": 800},
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["fits"] is True
    assert out["results"]["view"] == {"overflowX": "auto", "scrolls": True, "inside": True}
    assert out["results"]["note"] == {"left": True, "right": True}


def test_diff_view_is_a_named_keyboard_reachable_region(diff_page: Path) -> None:
    out = run(
        diff_page,
        ev(
            f"(() => {{ const v = {DIFF_VIEW}; return {{ tabindex: v.getAttribute('tabindex'), role: v.getAttribute('role'), label: v.getAttribute('aria-label') }}; }})()",
            "view",
        ),
    )
    assert out["results"]["view"] == {"tabindex": "0", "role": "region", "label": "Diff"}


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("width", [360, 1024])
def test_diff_page_has_no_errors_or_page_scroll(diff_page: Path, scheme: str, width: int) -> None:
    out = run(diff_page, ev(FITS_PAGE, "fits"), viewport={"width": width, "height": 800}, colorScheme=scheme)
    assert_clean(out)
    assert out["results"]["fits"] is True


def test_diff_print_wraps_long_lines_instead_of_scrolling(diff_page: Path) -> None:
    out = run(
        diff_page,
        ev(
            f"(() => {{ const v = {DIFF_VIEW}; return {{ overflow: getComputedStyle(v).overflowX, fits: v.scrollWidth <= v.clientWidth + 1 }}; }})()",
            "view",
        ),
        media="print",
        viewport={"width": 700, "height": 800},
    )
    assert_clean(out)
    assert out["results"]["view"] == {"overflow": "visible", "fits": True}


@pytest.mark.parametrize("scheme", SCHEMES)
def test_diff_reads_without_the_script_as_raw_text_then_a_notes_list(diff_nojs: Path, scheme: str) -> None:
    out = run(
        diff_nojs,
        ev(
            """(() => {
              const diff = document.querySelector('#diff');
              const pre = diff.querySelector('pre');
              const notes = [...diff.querySelectorAll('q-diff-note')];
              const p = pre.getBoundingClientRect();
              return {
                view: !!diff.querySelector('[data-q-diff]'),
                preText: pre.innerText.includes('+++ b/web/index.html') && pre.innerText.includes('+<b>x</b>'),
                preHeight: p.height,
                preDisplay: getComputedStyle(pre).display,
                displays: notes.map((n) => getComputedStyle(n).display),
                texts: notes.map((n) => n.innerText.trim().length > 0),
                heights: notes.map((n) => n.getBoundingClientRect().height > 0),
                below: notes.every((n) => n.getBoundingClientRect().top >= p.bottom - 1),
              };
            })()""",
            "plain",
        ),
        ev(FITS_PAGE, "fits"),
        viewport={"width": 360, "height": 800},
        colorScheme=scheme,
    )
    assert_clean(out)
    plain = out["results"]["plain"]
    assert plain["view"] is False and plain["preText"] is True and plain["preHeight"] > 0
    assert plain["preDisplay"] != "none"
    assert plain["displays"] == ["list-item"] * 4 and all(plain["texts"]) and all(plain["heights"])
    assert plain["below"] is True
    assert out["results"]["fits"] is True


# --- every element: themes, narrow viewport, no console errors, no-JS reading ------------------


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("width", [360, 1024])
def test_no_page_level_horizontal_scroll_and_no_errors(elements_page: Path, scheme: str, width: int) -> None:
    out = run(
        elements_page,
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        {"click": "#tabs [role=tab]:nth-child(5)"},
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits_after_tab"),
        ev(
            "['q-tabs', 'q-timeline', 'q-code'].map((t) => document.querySelector(t).getBoundingClientRect().width <= document.documentElement.clientWidth)",
            "inside",
        ),
        viewport={"width": width, "height": 800},
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["fits"] is True
    assert out["results"]["fits_after_tab"] is True
    assert out["results"]["inside"] == [True, True, True]


@pytest.mark.parametrize("scheme", SCHEMES)
def test_tabs_and_copy_button_use_theme_colours(elements_page: Path, scheme: str) -> None:
    out = run(
        elements_page,
        ev(
            """(() => {
              const resolve = (name) => {
                const probe = document.createElement('span');
                probe.style.color = 'var(--q-' + name + ')';
                document.body.appendChild(probe);
                const colour = getComputedStyle(probe).color;
                probe.remove();
                return colour;
              };
              const tab = document.querySelector('#tabs [role=tab][aria-selected=true]');
              const style = getComputedStyle(tab);
              return {
                tabColour: style.color,
                tabBorder: style.borderBottomColor,
                text: resolve('color-text'),
                accent: resolve('color-accent'),
                bg: getComputedStyle(document.body).backgroundColor,
              };
            })()""",
            "colours",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    colours = out["results"]["colours"]
    assert colours["tabColour"] in (colours["text"], colours["accent"])
    assert colours["tabBorder"] == colours["accent"]


def test_no_js_reading_shows_all_content(nojs_page: Path) -> None:
    html = nojs_page.read_text(encoding="utf-8")
    assert '<style data-quirk-lib="kit@1.0.0">' in html and '<script data-quirk-lib="kit@1.0.0">' not in html
    out = run(
        nojs_page,
        ev(
            """['q-tabs', 'q-timeline', 'q-code'].map((tag) => {
              const el = document.querySelector(tag);
              return { tag, text: el.innerText.trim().length, height: el.getBoundingClientRect().height, upgraded: !!el.querySelector('[data-q-kit]') };
            })""",
            "elements",
        ),
        ev(
            """[...document.querySelectorAll('#tabs > section')].map((s) => s.getBoundingClientRect().height > 0 && s.innerText.trim().length > 0)""",
            "sections",
        ),
        ev("document.querySelector('#code pre').innerText.includes('push.sh --env staging')", "code"),
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        viewport={"width": 360, "height": 800},
    )
    assert_clean(out)
    for element in out["results"]["elements"]:
        assert element["text"] > 0 and element["height"] > 0, element
        assert element["upgraded"] is False, element
    assert out["results"]["sections"] == [True] * 5
    assert out["results"]["code"] is True
    assert out["results"]["fits"] is True


@pytest.mark.parametrize("scheme", SCHEMES)
def test_no_js_reading_in_both_schemes(nojs_page: Path, scheme: str) -> None:
    out = run(
        nojs_page,
        ev("[...document.querySelectorAll('#timeline li')].every((li) => li.innerText.trim().length > 0 && li.getBoundingClientRect().height > 0)", "items"),
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["items"] is True


# --- q-board ----------------------------------------------------------------------------------


def board_source(*, extra: bool = False) -> str:
    extra_card = '\n      <li data-id="new-card">A brand new card</li>' if extra else ""
    return (
        HEADER
        + f"""<q-board id="triage">
  <section>
    <h3>Now</h3>
    <ul>
      <li data-id="login-bug">Fix login redirect loop</li>
      <li data-id="slow-search">Profile slow search queries</li>{extra_card}
    </ul>
  </section>
  <section>
    <h3>Next</h3>
    <ul>
      <li data-id="csv-export">Add CSV export to reports</li>
    </ul>
  </section>
  <section>
    <h3>Later</h3>
    <ul>
      <li data-id="dark-mode-icons">Redraw icons for dark mode</li>
      <li>{LONG_UNBROKEN}</li>
    </ul>
  </section>
  <section>
    <h3>Done</h3>
    <ul></ul>
  </section>
</q-board>
"""
    )


AUTHORED_BOARD = [
    ["Now", ["login-bug", "slow-search"]],
    ["Next", ["csv-export"]],
    ["Later", ["dark-mode-icons", LONG_UNBROKEN]],
    ["Done", []],
]
BOARD_KEY = "quirk-board:board:triage"
CARD = "#triage li[data-id=login-bug]"
LAYOUT = """(() => [...document.querySelectorAll('#triage > section')].map((s) => [
  s.querySelector(':scope > h3').textContent.trim(),
  [...s.querySelectorAll(':scope > ul > li:not([data-q-kit])')].map((li) => li.getAttribute('data-id') || li.childNodes[0].textContent.trim()),
]))()"""
ACTIVE_CARD = "(() => { const a = document.activeElement; return a && (a.closest('li[data-id]') || a).getAttribute('data-id'); })()"
ANNOUNCED = "document.querySelector('#triage [data-q-announce]').textContent.replace(/\\u00a0/g, ' ').trim()"
STORED = f"localStorage.getItem({json.dumps(BOARD_KEY)})"
NOTE = "document.querySelector('#triage [data-q-note]').textContent.trim()"
LOGIN_BUG_TEXT = "Fix login redirect loop"
AUTHORED_MARKDOWN = (
    "## Now\n- Fix login redirect loop\n- Profile slow search queries\n\n"
    "## Next\n- Add CSV export to reports\n\n"
    f"## Later\n- Redraw icons for dark mode\n- {LONG_UNBROKEN}\n\n"
    "## Done"
)


def _moved(layout: list, card: str, column: int, index: int) -> list:
    """The authored layout with `card` moved to `index` of `column`."""
    result = [[name, [c for c in ids if c != card]] for name, ids in layout]
    result[column][1].insert(index, card)
    return result


@pytest.fixture(scope="module")
def board_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-board")
    src = work / "board.src.html"
    src.write_text(board_source(), encoding="utf-8")
    page = _build(src, work / "board.html")
    _run_harness({"file": str(page)})
    return page


@pytest.fixture(scope="module")
def board_nojs(board_page: Path) -> Path:
    html = board_page.read_text(encoding="utf-8")
    stripped, count = KIT_SCRIPT.subn("", html)
    assert count == 1
    page = board_page.with_name("board-nojs.html")
    page.write_text(stripped, encoding="utf-8")
    return page


def test_board_toolbar_and_card_controls_are_inserted(board_page: Path) -> None:
    out = run(
        board_page,
        ev(
            """(() => {
              const board = document.querySelector('#triage');
              const bar = board.querySelector(':scope > [data-q-kit]');
              const buttons = bar ? [...bar.querySelectorAll('button')] : [];
              const cards = [...board.querySelectorAll('li[data-id], li:not([data-id])')].filter((li) => !li.hasAttribute('data-q-kit'));
              const lists = [...board.querySelectorAll(':scope > section > ul')];
              const note = board.querySelector('[data-q-note]');
              return {
                barFirst: board.firstElementChild === bar,
                buttons: buttons.map((b) => [b.textContent.trim(), b.type]),
                note: note && note.textContent.trim(),
                noteVisible: !!note && note.getBoundingClientRect().height > 0,
                cards: cards.length,
                tabindex: cards.map((c) => c.getAttribute('tabindex')),
                selects: board.querySelectorAll('select').length,
                kitMarked: [...board.querySelectorAll('button, [data-q-handle], [data-q-announce]')].every((n) => n.hasAttribute('data-q-kit')),
                liveRegions: [...board.querySelectorAll('[aria-live=polite]')].length,
                listNames: lists.map((ul) => ul.getAttribute('aria-labelledby') && document.getElementById(ul.getAttribute('aria-labelledby')).textContent.trim()),
                keys: cards[0].getAttribute('aria-keyshortcuts'),
              };
            })()""",
            "info",
        ),
    )
    assert_clean(out)
    info = out["results"]["info"]
    assert info["barFirst"] is True
    assert info["buttons"] == [["Reset", "button"], ["Copy as Markdown", "button"]]
    assert info["note"] == "Saved in this browser only." and info["noteVisible"] is True
    assert info["cards"] == 5 and info["tabindex"] == ["0"] * 5 and info["selects"] == 0
    assert info["kitMarked"] is True and info["liveRegions"] >= 2
    assert info["listNames"] == ["Now", "Next", "Later", "Done"]
    assert "Alt+ArrowRight" in info["keys"]


def test_board_authored_layout_is_unchanged_on_load(board_page: Path) -> None:
    out = run(board_page, ev(LAYOUT, "layout"), ev(STORED, "stored"))
    assert_clean(out)
    assert out["results"]["layout"] == AUTHORED_BOARD
    assert out["results"]["stored"] is None


def test_board_alt_right_moves_the_card_to_the_next_column_and_keeps_focus(board_page: Path) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        ev(LAYOUT, "layout"),
        ev(ACTIVE_CARD, "active"),
        ev("document.activeElement === document.querySelector('#triage li[data-id=login-bug]')", "on_card"),
        ev(ANNOUNCED, "say"),
        ev("document.querySelector('#triage [data-q-announce]').getAttribute('aria-live')", "live"),
        {"press": "Alt+ArrowRight"},
        ev(LAYOUT, "layout2"),
        ev(ANNOUNCED, "say2"),
        {"press": "Alt+ArrowLeft"},
        ev(LAYOUT, "layout3"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["layout"] == _moved(AUTHORED_BOARD, "login-bug", 1, 0)
    assert results["active"] == "login-bug" and results["on_card"] is True
    assert results["say"] == f'Moved "{LOGIN_BUG_TEXT}" to Next, position 1 of 2.'
    assert results["live"] == "polite"
    assert results["layout2"] == _moved(AUTHORED_BOARD, "login-bug", 2, 0)
    assert results["say2"] == f'Moved "{LOGIN_BUG_TEXT}" to Later, position 1 of 3.'
    assert results["layout3"] == _moved(AUTHORED_BOARD, "login-bug", 1, 0)


def test_board_alt_left_and_right_stop_at_the_edges_with_an_announcement(board_page: Path) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowLeft"},
        ev(LAYOUT, "layout"),
        ev(ANNOUNCED, "first"),
        {"focus": "#triage li[data-id=dark-mode-icons]"},
        {"press": "Alt+ArrowRight"},
        {"press": "Alt+ArrowRight"},
        ev(ANNOUNCED, "last"),
        ev(LAYOUT, "layout2"),
    )
    assert_clean(out)
    assert out["results"]["layout"] == AUTHORED_BOARD
    assert out["results"]["first"] == f'"{LOGIN_BUG_TEXT}" is already in the first column.'
    assert out["results"]["layout2"] == _moved(AUTHORED_BOARD, "dark-mode-icons", 3, 0)
    assert out["results"]["last"] == '"Redraw icons for dark mode" is already in the last column.'


def test_board_alt_down_and_up_reorder_within_the_column(board_page: Path) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowDown"},
        ev(LAYOUT, "down"),
        ev(ACTIVE_CARD, "active"),
        ev(ANNOUNCED, "say"),
        {"press": "Alt+ArrowDown"},
        ev(LAYOUT, "bottom"),
        ev(ANNOUNCED, "say_bottom"),
        {"press": "Alt+ArrowUp"},
        ev(LAYOUT, "up"),
        {"press": "Alt+ArrowUp"},
        ev(ANNOUNCED, "say_top"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["down"] == _moved(AUTHORED_BOARD, "login-bug", 0, 1)
    assert results["active"] == "login-bug"
    assert results["say"] == f'Moved "{LOGIN_BUG_TEXT}" to position 2 of 2 in Now.'
    assert results["bottom"] == results["down"]
    assert results["say_bottom"] == f'"{LOGIN_BUG_TEXT}" is already last in Now.'
    assert results["up"] == AUTHORED_BOARD
    assert results["say_top"] == f'"{LOGIN_BUG_TEXT}" is already first in Now.'


def test_board_plain_arrows_and_modified_alt_arrows_do_not_move_cards(board_page: Path) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "ArrowRight"},
        {"press": "Shift+Alt+ArrowRight"},
        {"press": "Control+Alt+ArrowRight"},
        ev(LAYOUT, "layout"),
    )
    assert_clean(out)
    assert out["results"]["layout"] == AUTHORED_BOARD


def test_board_alt_arrows_reach_an_empty_column(board_page: Path) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        {"press": "Alt+ArrowRight"},
        {"press": "Alt+ArrowRight"},
        ev(LAYOUT, "layout"),
    )
    assert_clean(out)
    assert out["results"]["layout"] == _moved(AUTHORED_BOARD, "login-bug", 3, 0)


def test_board_mouse_drag_moves_a_card_between_columns(board_page: Path) -> None:
    out = run(
        board_page,
        {"drag": {"from": CARD, "to": "#triage li[data-id=csv-export]", "at": "bottom"}},
        ev(LAYOUT, "layout"),
        ev(STORED, "stored"),
        ev("[...document.querySelectorAll('#triage [data-q-dragging], #triage [data-q-drop]')].length", "leftover"),
        ev(ANNOUNCED, "say"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["layout"] == _moved(AUTHORED_BOARD, "login-bug", 1, 1)
    assert json.loads(results["stored"])["columns"] == [ids for _, ids in results["layout"]]
    assert results["leftover"] == 0
    assert results["say"] == f'Moved "{LOGIN_BUG_TEXT}" to Next, position 2 of 2.'


def test_board_mouse_drag_to_the_top_of_a_column_and_into_an_empty_one(board_page: Path) -> None:
    out = run(
        board_page,
        {"drag": {"from": "#triage li[data-id=slow-search]", "to": "#triage li[data-id=dark-mode-icons]", "at": "top"}},
        ev(LAYOUT, "above"),
        {"drag": {"from": CARD, "to": "#triage > section:nth-of-type(4) > ul"}},
        ev(LAYOUT, "empty"),
    )
    assert_clean(out)
    above = _moved(AUTHORED_BOARD, "slow-search", 2, 0)
    assert out["results"]["above"] == above
    assert out["results"]["empty"] == _moved(above, "login-bug", 3, 0)


def test_board_mouse_drag_reorders_within_a_column(board_page: Path) -> None:
    out = run(
        board_page,
        {"drag": {"from": CARD, "to": "#triage li[data-id=slow-search]", "at": "bottom"}},
        ev(LAYOUT, "layout"),
    )
    assert_clean(out)
    assert out["results"]["layout"] == _moved(AUTHORED_BOARD, "login-bug", 0, 1)


def test_board_drag_shows_a_drop_indicator_and_marks_the_card(board_page: Path) -> None:
    out = run(
        board_page,
        {"dragHold": {"from": CARD, "to": "#triage li[data-id=csv-export]", "at": "top"}},
        ev(
            """(() => {
              const drop = document.querySelector('#triage [data-q-drop]');
              const card = document.querySelector('#triage li[data-id=login-bug]');
              const target = document.querySelector('#triage li[data-id=csv-export]').getBoundingClientRect();
              const rect = drop && drop.getBoundingClientRect();
              return {
                drop: !!drop,
                hidden: drop && drop.getAttribute('aria-hidden'),
                visible: !!rect && rect.width > 0,
                near: !!rect && Math.abs(rect.top - target.top) < 24,
                dragging: card.hasAttribute('data-q-dragging'),
                unmoved: [...document.querySelectorAll('#triage > section:first-of-type > ul > li')].map((li) => li.getAttribute('data-id')),
              };
            })()""",
            "held",
        ),
        {"mouseUp": True},
        ev("!!document.querySelector('#triage [data-q-drop]')", "drop_after"),
        ev(LAYOUT, "layout"),
    )
    assert_clean(out)
    held = out["results"]["held"]
    assert held["drop"] is True and held["hidden"] == "true" and held["visible"] is True and held["near"] is True
    assert held["dragging"] is True and held["unmoved"] == ["login-bug", "slow-search"]
    assert out["results"]["drop_after"] is False
    assert out["results"]["layout"] == _moved(AUTHORED_BOARD, "login-bug", 1, 0)


def test_board_escape_cancels_a_drag(board_page: Path) -> None:
    out = run(
        board_page,
        {"dragHold": {"from": CARD, "to": "#triage li[data-id=csv-export]", "at": "top"}},
        {"press": "Escape"},
        {"mouseUp": True},
        ev(LAYOUT, "layout"),
        ev("[...document.querySelectorAll('#triage [data-q-dragging], #triage [data-q-drop]')].length", "leftover"),
    )
    assert_clean(out)
    assert out["results"]["layout"] == AUTHORED_BOARD and out["results"]["leftover"] == 0


def test_board_a_plain_click_does_not_move_or_save(board_page: Path) -> None:
    out = run(
        board_page,
        {"click": f"{CARD}"},
        ev(LAYOUT, "layout"),
        ev(STORED, "stored"),
    )
    assert_clean(out)
    assert out["results"]["layout"] == AUTHORED_BOARD and out["results"]["stored"] is None


def test_board_touch_drag_from_the_handle_moves_a_card(board_page: Path) -> None:
    out = run(
        board_page,
        ev("getComputedStyle(document.querySelector('#triage li[data-id=login-bug] [data-q-handle]')).touchAction", "touch_action"),
        {"touchDrag": {"from": f"{CARD} [data-q-handle]", "to": "#triage li[data-id=csv-export]", "at": "bottom"}},
        ev(LAYOUT, "layout"),
        hasTouch=True,
    )
    assert_clean(out)
    assert out["results"]["touch_action"] == "none"
    assert out["results"]["layout"] == _moved(AUTHORED_BOARD, "login-bug", 1, 1)


def test_board_reload_restores_the_moved_layout(board_page: Path) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        ev(f"JSON.parse({STORED})", "stored"),
        {"reload": True},
        ev(LAYOUT, "after_reload"),
        ev(NOTE, "note"),
        ev("[...document.querySelectorAll('#triage [data-q-kit]')].length", "kit_nodes"),
        {"reload": True},
        ev("[...document.querySelectorAll('#triage [data-q-kit]')].length", "kit_nodes_again"),
    )
    assert_clean(out)
    results = out["results"]
    moved = _moved(AUTHORED_BOARD, "login-bug", 1, 0)
    assert results["after_reload"] == moved
    assert results["stored"]["v"] == 1 and results["stored"]["columns"] == [ids for _, ids in moved]
    assert isinstance(results["stored"]["authored"], str) and results["stored"]["authored"]
    assert results["note"] == "Saved in this browser only."
    assert results["kit_nodes"] == results["kit_nodes_again"]


def test_board_reset_restores_the_authored_layout_and_clears_storage(board_page: Path) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        {"press": "Alt+ArrowDown"},
        ev(f"{STORED} !== null", "saved"),
        {"click": "#triage button:text-is('Reset')"},
        ev(LAYOUT, "layout"),
        ev(STORED, "stored"),
        ev(ANNOUNCED, "say"),
        {"reload": True},
        ev(LAYOUT, "after_reload"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["saved"] is True
    assert results["layout"] == AUTHORED_BOARD and results["stored"] is None
    assert results["say"] == "Layout reset to the authored order."
    assert results["after_reload"] == AUTHORED_BOARD


def test_board_copy_as_markdown_exports_the_authored_and_the_current_layout(board_page: Path) -> None:
    out = run(
        board_page,
        {"click": "#triage button:text-is('Copy as Markdown')"},
        {"waitFor": "document.querySelector('#triage [data-q-status]').textContent.trim() === 'Copied'"},
        ev("navigator.clipboard.readText()", "authored"),
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        {"click": "#triage button:text-is('Copy as Markdown')"},
        {"waitFor": "document.querySelector('#triage [data-q-status]').textContent.trim() === 'Copied'"},
        ev("navigator.clipboard.readText()", "moved"),
        ev("!!document.querySelector('#triage [data-q-export]')", "textarea"),
        permissions=["clipboard-read", "clipboard-write"],
    )
    assert_clean(out)
    assert out["results"]["authored"] == AUTHORED_MARKDOWN
    moved = AUTHORED_MARKDOWN.replace("## Now\n- Fix login redirect loop\n", "## Now\n").replace(
        "## Next\n", "## Next\n- Fix login redirect loop\n"
    )
    assert out["results"]["moved"] == moved
    assert out["results"]["textarea"] is False


@pytest.mark.parametrize("script", [None, DENIED_CLIPBOARD], ids=["permission-denied", "write-rejects"])
def test_board_blocked_clipboard_selects_the_markdown_and_tells_the_reader(board_page: Path, script: str | None) -> None:
    spec: dict = {}
    if script:
        spec["initScripts"] = [script]
    out = run(
        board_page,
        {"click": "#triage button:text-is('Copy as Markdown')"},
        {"waitFor": "document.querySelector('#triage [data-q-status]').textContent.trim() !== ''"},
        ev("document.querySelector('#triage [data-q-status]').textContent.trim()", "notice"),
        ev(
            """(() => {
              const box = document.querySelector('#triage [data-q-export]');
              return box && {
                value: box.value,
                selected: box.value.slice(box.selectionStart, box.selectionEnd),
                focused: document.activeElement === box,
                readOnly: box.readOnly,
                label: box.getAttribute('aria-label'),
                height: box.getBoundingClientRect().height,
              };
            })()""",
            "box",
        ),
        ev(LAYOUT, "layout"),
        **spec,
    )
    assert_clean(out)
    assert out["results"]["notice"] == NOTICE
    box = out["results"]["box"]
    assert box["value"] == AUTHORED_MARKDOWN and box["selected"] == AUTHORED_MARKDOWN
    assert box["focused"] is True and box["readOnly"] is True and box["label"] and box["height"] > 0
    assert out["results"]["layout"] == AUTHORED_BOARD


def test_board_without_a_clipboard_api_still_falls_back(board_page: Path) -> None:
    out = run(
        board_page,
        {"click": "#triage button:text-is('Copy as Markdown')"},
        {"waitFor": "document.querySelector('#triage [data-q-status]').textContent.trim() !== ''"},
        ev("document.querySelector('#triage [data-q-status]').textContent.trim()", "notice"),
        ev("document.querySelector('#triage [data-q-export]').value", "value"),
        initScripts=["Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });"],
    )
    assert_clean(out)
    assert out["results"]["notice"] == NOTICE and out["results"]["value"] == AUTHORED_MARKDOWN


def test_board_changed_authored_cards_discard_the_stale_saved_layout(tmp_path: Path) -> None:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    first = tmp_path / "first.src.html"
    first.write_text(board_source(), encoding="utf-8")
    page = _build(first, tmp_path / "board.html")
    second = tmp_path / "second.src.html"
    second.write_text(board_source(extra=True), encoding="utf-8")
    (tmp_path / "rebuilt").mkdir()
    rebuilt = _build(second, tmp_path / "rebuilt" / "board.html")
    out = run(
        page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        ev(f"{STORED} !== null", "saved"),
        {"copyFile": {"from": str(rebuilt), "to": str(page)}},
        {"reload": True},
        ev(LAYOUT, "layout"),
        ev(STORED, "stored"),
        ev(NOTE, "note"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["saved"] is True
    expected = [["Now", ["login-bug", "slow-search", "new-card"]]] + AUTHORED_BOARD[1:]
    assert results["layout"] == expected
    assert results["stored"] is None
    assert results["note"] == "Saved in this browser only."


@pytest.mark.parametrize(
    "tamper",
    [
        "stored.v = 2",
        "stored.authored = 'stale'",
        "stored.columns[1].push('ghost')",
        "stored.columns[0].pop()",
        "stored.columns.pop()",
        "stored.columns[0].push(stored.columns[0][0])",
        "stored.columns = 'nope'",
    ],
)
def test_board_a_stored_layout_that_does_not_match_is_discarded(board_page: Path, tamper: str) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        ev(f"(() => {{ const stored = JSON.parse({STORED}); {tamper}; localStorage.setItem({json.dumps(BOARD_KEY)}, JSON.stringify(stored)); return true; }})()", "tampered"),
        {"reload": True},
        ev(LAYOUT, "layout"),
        ev(STORED, "stored"),
    )
    assert_clean(out)
    assert out["results"]["layout"] == AUTHORED_BOARD and out["results"]["stored"] is None


@pytest.mark.parametrize("value", ["{nope", "null", '"text"', "[]", "42", '{"v":1}', ""], ids=["syntax", "null", "string", "array", "number", "no-columns", "empty"])
def test_board_malformed_stored_json_is_discarded(board_page: Path, value: str) -> None:
    out = run(
        board_page,
        ev(LAYOUT, "layout"),
        ev(STORED, "stored"),
        initScripts=[f"localStorage.setItem({json.dumps(BOARD_KEY)}, {json.dumps(value)});"],
    )
    assert_clean(out)
    assert out["results"]["layout"] == AUTHORED_BOARD and out["results"]["stored"] is None


def test_board_storage_is_keyed_by_page_slug_and_board_id(tmp_path: Path) -> None:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    src = tmp_path / "src.html"
    src.write_text(board_source(), encoding="utf-8")
    page = _build(src, tmp_path / "weekly.review.html")
    out = run(
        page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        ev("Object.keys(localStorage).filter((k) => k.startsWith('quirk-board:'))", "keys"),
    )
    assert_clean(out)
    assert out["results"]["keys"] == ["quirk-board:weekly.review:triage"]


BLOCKED_SET_ITEM = """
Storage.prototype.setItem = function () { throw new DOMException('The quota has been exceeded.', 'QuotaExceededError'); };
"""
BLOCKED_STORAGE = """
Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new DOMException('The operation is insecure.', 'SecurityError'); } });
"""


@pytest.mark.parametrize("script", [BLOCKED_SET_ITEM, BLOCKED_STORAGE], ids=["set-item-throws", "storage-blocked"])
def test_board_blocked_storage_says_so_and_moves_still_work(board_page: Path, script: str) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        ev(LAYOUT, "layout"),
        ev(NOTE, "note"),
        {"focus": "#triage li[data-id=slow-search]"},
        {"press": "Alt+ArrowRight"},
        {"press": "Alt+ArrowRight"},
        {"press": "Alt+ArrowRight"},
        ev(LAYOUT, "layout2"),
        {"drag": {"from": "#triage li[data-id=csv-export]", "to": "#triage li[data-id=dark-mode-icons]", "at": "top"}},
        ev(LAYOUT, "layout3"),
        {"click": "#triage button:text-is('Reset')"},
        ev(LAYOUT, "reset"),
        ev(NOTE, "note_after_reset"),
        initScripts=[script],
    )
    assert_clean(out)
    results = out["results"]
    assert results["layout"] == _moved(AUTHORED_BOARD, "login-bug", 1, 0)
    assert results["note"] == "Not saved: this browser blocks storage."
    assert results["layout2"] == _moved(results["layout"], "slow-search", 3, 0)
    assert results["layout3"] == _moved(results["layout2"], "csv-export", 2, 0)
    assert results["reset"] == AUTHORED_BOARD
    assert results["note_after_reset"] == "Not saved: this browser blocks storage."


def test_board_upgrade_is_idempotent_when_the_element_is_moved(board_page: Path) -> None:
    out = run(
        board_page,
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        ev(
            """(() => {
              const board = document.querySelector('#triage');
              const count = () => ({
                bars: board.querySelectorAll(':scope > [data-q-kit]').length,
                buttons: board.querySelectorAll('button').length,
                handles: board.querySelectorAll('[data-q-handle]').length,
                notes: board.querySelectorAll('[data-q-note]').length,
              });
              const before = count();
              const holder = document.createElement('div');
              document.querySelector('main').appendChild(holder);
              holder.appendChild(board);
              return { before, after: count() };
            })()""",
            "counts",
        ),
        ev(LAYOUT, "layout"),
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        ev(LAYOUT, "layout2"),
        {"click": "#triage button:text-is('Reset')"},
        ev(LAYOUT, "reset"),
    )
    assert_clean(out)
    counts = out["results"]["counts"]
    assert counts["before"] == counts["after"]
    assert counts["after"]["bars"] == 1 and counts["after"]["handles"] == 5 and counts["after"]["notes"] == 1
    assert out["results"]["layout"] == _moved(AUTHORED_BOARD, "login-bug", 1, 0)
    assert out["results"]["layout2"] == _moved(AUTHORED_BOARD, "login-bug", 2, 0)
    assert out["results"]["reset"] == AUTHORED_BOARD


def test_board_card_text_for_identity_and_markdown_ignores_inserted_controls(board_page: Path) -> None:
    out = run(
        board_page,
        ev("document.querySelector('#triage li[data-id=login-bug]').childNodes[0].textContent.trim()", "own_text"),
        {"focus": "#triage > section:nth-of-type(3) > ul > li:nth-of-type(2)"},
        {"press": "Alt+ArrowLeft"},
        ev(LAYOUT, "layout"),
        {"reload": True},
        ev(LAYOUT, "after_reload"),
    )
    assert_clean(out)
    assert out["results"]["layout"] == _moved(AUTHORED_BOARD, LONG_UNBROKEN, 1, 1)
    assert out["results"]["after_reload"] == out["results"]["layout"]


@pytest.mark.parametrize("scheme", SCHEMES)
def test_board_uses_theme_tokens(board_page: Path, scheme: str) -> None:
    out = run(
        board_page,
        ev(
            """(() => {
              const resolve = (name, prop) => {
                const probe = document.createElement('span');
                probe.style[prop] = 'var(--q-' + name + ')';
                document.body.appendChild(probe);
                const colour = getComputedStyle(probe)[prop];
                probe.remove();
                return colour;
              };
              const card = getComputedStyle(document.querySelector('#triage li[data-id=login-bug]'));
              const note = getComputedStyle(document.querySelector('#triage [data-q-note]'));
              return {
                cardBorder: card.borderTopColor, border: resolve('color-border', 'color'),
                cardBg: card.backgroundColor, surface: resolve('color-surface', 'backgroundColor'),
                cardText: card.color, text: resolve('color-text', 'color'),
                noteColour: note.color, muted: resolve('color-text-muted', 'color'),
                bodyBg: getComputedStyle(document.body).backgroundColor,
              };
            })()""",
            "colours",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    colours = out["results"]["colours"]
    assert colours["cardBorder"] == colours["border"]
    assert colours["cardBg"] == colours["surface"] and colours["cardBg"] != colours["bodyBg"]
    assert colours["cardText"] == colours["text"] and colours["noteColour"] == colours["muted"]


@pytest.mark.parametrize("scheme", SCHEMES)
def test_board_drop_indicator_uses_the_accent_token(board_page: Path, scheme: str) -> None:
    out = run(
        board_page,
        {"dragHold": {"from": CARD, "to": "#triage li[data-id=csv-export]", "at": "top"}},
        ev(
            """(() => {
              const probe = document.createElement('span');
              probe.style.backgroundColor = 'var(--q-color-accent)';
              document.body.appendChild(probe);
              const accent = getComputedStyle(probe).backgroundColor;
              probe.remove();
              return { accent, drop: getComputedStyle(document.querySelector('#triage [data-q-drop]')).backgroundColor };
            })()""",
            "colours",
        ),
        {"mouseUp": True},
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["colours"]["drop"] == out["results"]["colours"]["accent"]


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("width", [360, 1024])
def test_board_page_has_no_errors_or_page_scroll(board_page: Path, scheme: str, width: int) -> None:
    out = run(
        board_page,
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        ev(
            """(() => {
              const limit = document.documentElement.clientWidth;
              const board = document.querySelector('#triage').getBoundingClientRect();
              const cards = [...document.querySelectorAll('#triage li')].map((li) => li.getBoundingClientRect());
              return { board: board.right <= limit + 1, cards: cards.every((r) => r.left >= 0 && r.right <= limit + 1) };
            })()""",
            "inside",
        ),
        {"focus": CARD},
        {"press": "Alt+ArrowRight"},
        {"press": "Alt+ArrowRight"},
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits_after_move"),
        viewport={"width": width, "height": 800},
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["fits"] is True and out["results"]["fits_after_move"] is True
    assert out["results"]["inside"] == {"board": True, "cards": True}


def test_board_columns_sit_side_by_side_wide_and_stack_narrow(board_page: Path) -> None:
    probe = "[...document.querySelectorAll('#triage > section')].map((s) => Math.round(s.getBoundingClientRect().top))"
    wide = run(board_page, ev(probe, "tops"), viewport={"width": 1280, "height": 800})
    narrow = run(board_page, ev(probe, "tops"), viewport={"width": 360, "height": 800})
    assert_clean(wide)
    assert_clean(narrow)
    assert len(set(wide["results"]["tops"][:3])) == 1
    assert narrow["results"]["tops"] == sorted(narrow["results"]["tops"]) and len(set(narrow["results"]["tops"])) == 4


@pytest.mark.parametrize("width", [1280, 2000])
def test_board_columns_together_fill_the_board_width(board_page: Path, width: int) -> None:
    out = run(
        board_page,
        ev(
            """(() => {
              const board = document.querySelector('#triage').getBoundingClientRect();
              const cols = [...document.querySelectorAll('#triage > section')].map((s) => s.getBoundingClientRect());
              return {
                left: Math.round(cols[0].left - board.left),
                right: Math.round(board.right - cols[cols.length - 1].right),
                oneRow: new Set(cols.map((r) => Math.round(r.top))).size === 1,
              };
            })()""",
            "fill",
        ),
        viewport={"width": width, "height": 800},
    )
    assert_clean(out)
    assert out["results"]["fill"] == {"left": 0, "right": 0, "oneRow": True}


def test_board_empty_column_is_a_usable_drop_target(board_page: Path) -> None:
    out = run(board_page, ev("document.querySelector('#triage > section:nth-of-type(4) > ul').getBoundingClientRect().height", "height"))
    assert_clean(out)
    assert out["results"]["height"] >= 40


def test_board_print_hides_the_controls_but_keeps_every_card(board_page: Path) -> None:
    out = run(
        board_page,
        ev(
            """(() => {
              const shown = (sel) => [...document.querySelectorAll(sel)].some((n) => getComputedStyle(n).display !== 'none');
              return {
                bar: shown('#triage > [data-q-kit]:not([data-q-announce])'),
                handles: shown('#triage [data-q-handle]'),
                cards: [...document.querySelectorAll('#triage li')].every((li) => li.innerText.trim().length > 0 && li.getBoundingClientRect().height > 0),
                headings: [...document.querySelectorAll('#triage h3')].every((h) => h.getBoundingClientRect().height > 0),
              };
            })()""",
            "print",
        ),
        media="print",
    )
    assert_clean(out)
    assert out["results"]["print"] == {"bar": False, "handles": False, "cards": True, "headings": True}


def test_board_print_hides_the_export_box_too(board_page: Path) -> None:
    out = run(
        board_page,
        {"click": "#triage button:text-is('Copy as Markdown')"},
        {"waitFor": "!!document.querySelector('#triage [data-q-export]')"},
        {"emulate": {"media": "print"}},
        ev("getComputedStyle(document.querySelector('#triage [data-q-export]')).display", "display"),
    )
    assert_clean(out)
    assert out["results"]["display"] == "none"


def test_board_reads_without_the_script(board_nojs: Path) -> None:
    html = board_nojs.read_text(encoding="utf-8")
    assert '<script data-quirk-lib="kit@1.0.0">' not in html
    out = run(
        board_nojs,
        ev(
            """(() => {
              const board = document.querySelector('#triage');
              return {
                text: board.innerText.trim().length,
                height: board.getBoundingClientRect().height,
                upgraded: !!board.querySelector('[data-q-kit]'),
                headings: [...board.querySelectorAll('h3')].map((h) => h.innerText.trim()),
                cards: [...board.querySelectorAll('li')].map((li) => li.innerText.trim().length > 0 && li.getBoundingClientRect().height > 0),
              };
            })()""",
            "shown",
        ),
        ev("document.documentElement.scrollWidth <= document.documentElement.clientWidth", "fits"),
        viewport={"width": 360, "height": 800},
    )
    assert_clean(out)
    shown = out["results"]["shown"]
    assert shown["text"] > 0 and shown["height"] > 0 and shown["upgraded"] is False
    assert shown["headings"] == ["Now", "Next", "Later", "Done"]
    assert shown["cards"] == [True] * 5
    assert out["results"]["fits"] is True


@pytest.mark.parametrize("scheme", SCHEMES)
def test_board_reads_without_the_script_in_both_schemes(board_nojs: Path, scheme: str) -> None:
    out = run(
        board_nojs,
        ev("[...document.querySelectorAll('#triage li')].every((li) => li.innerText.trim().length > 0 && li.getBoundingClientRect().height > 0)", "cards"),
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["cards"] is True


# --- review fixes: page CSS wins, header columns, chart cleanup and the no-numbers note -----------


def _mini_page(tmp_path: Path, body: str, name: str = "mini") -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    src = tmp_path / f"{name}.src.html"
    src.write_text(HEADER + body, encoding="utf-8")
    return _build(src, tmp_path / f"{name}.html")


def test_page_rules_with_one_class_beat_the_kit_on_slotted_and_inserted_nodes(tmp_path: Path) -> None:
    page = _mini_page(
        tmp_path,
        """<style>
.big { font-size: 9px; }
.tight { padding: 3px; }
.snug { margin-top: 11px; }
.tab-mine { padding: 0; }
</style>
<q-stat id="stat"><span slot="label">Label</span><span slot="value" class="big">42</span>
<span slot="definition">Distinct events per day.</span></q-stat>
<q-table id="table"><table><thead><tr><th class="tight">Name</th></tr></thead><tbody><tr><td>a</td></tr></tbody></table></q-table>
<q-code id="code" filename="a.sh"><pre class="snug"><code>echo hi</code></pre></q-code>
""",
    )
    out = run(
        page,
        ev("getComputedStyle(document.querySelector('#stat [slot=value]')).fontSize", "value"),
        ev("getComputedStyle(document.querySelector('#table th')).paddingTop", "th"),
        ev("getComputedStyle(document.querySelector('#code pre')).marginTop", "pre"),
        ev("getComputedStyle(document.querySelector('#stat [slot=label]')).fontSize", "label"),
    )
    assert_clean(out)
    assert out["results"]["value"] == "9px"
    assert out["results"]["th"] == "3px"
    assert out["results"]["pre"] == "11px"
    assert out["results"]["label"] != "9px"


def test_kit_css_rules_stay_at_or_below_one_class_except_the_named_lifts() -> None:
    css = re.sub(r"/\*.*?\*/", "", (KIT_JS.parent / "kit.css").read_text(encoding="utf-8"), flags=re.S)

    def strip_where(selector: str) -> str:
        while ":where(" in selector:
            start = selector.index(":where(")
            depth, end = 1, start + 7
            while depth:
                depth += (selector[end] == "(") - (selector[end] == ")")
                end += 1
            selector = selector[:start] + selector[end:]
        return selector

    lifted = {
        'q-tabs > [role="tablist"] > [role="tab"]:enabled:hover',
        'q-tabs > [role="tablist"] > [role="tab"][aria-selected="true"]:enabled:hover',
        'q-tabs > section[role="tabpanel"]',
        "q-table th > [data-q-sort]:enabled:hover",
        "q-board > section:not([hidden])",
        "q-board > section > :is(h2, h3, h4, h5, h6):first-child",
        ":is(q-flow, q-sequence) aside button:enabled:hover",
        ':is(q-flow, q-sequence) aside button[aria-current="step"]:enabled:hover',
        ":is(q-flow, q-sequence) aside [data-q-flow-tree] details[open] > summary",
        "q-sequence [data-q-sequence-pinned-row] > button:enabled:hover",
    }
    offenders: list[str] = []
    stack: list[str] = []
    for match in re.finditer(r"([^{}]*)([{}])", css):
        text, brace = match.group(1).strip(), match.group(2)
        if brace == "}":
            stack.pop()
        elif text.startswith("@"):
            stack.append(text)
        else:
            stack.append("rule")
            if any("print" in item for item in stack[:-1]):
                continue
            for selector in re.split(r",\s*(?![^(]*\))", text):
                bare = re.sub(r":is\([^)]*\)", "", strip_where(selector)).replace("::", " ")
                if re.search(r"[\[.#]|:[a-z]", bare) and " ".join(selector.split()) not in lifted:
                    offenders.append(" ".join(selector.split()))
    assert offenders == []


def _sortable(table_id: str, head: str, rows: list[str]) -> str:
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row.split("|")) + "</tr>" for row in rows)
    return f'<q-table id="{table_id}"><table><thead>{head}</thead><tbody>{body}</tbody></table></q-table>\n'


COLUMN_TABLES = _sortable(
    "corner",
    '<tr><td></td><th>Q1</th><th class="num">Q2</th></tr>',
    ["alpha|30|5", "beta|10|50", "gamma|20|7"],
) + _sortable(
    "span",
    '<tr><th colspan="2">Name and id</th><th class="num">Score</th></tr>',
    ["b|x|3", "a|y|9", "c|z|1"],
)


def _first_cells(table_id: str) -> str:
    return f"[...document.querySelectorAll('#{table_id} tbody tr')].map((tr) => tr.cells[0].textContent)"


def _aria_sorts(table_id: str) -> str:
    return f"[...document.querySelectorAll('#{table_id} th')].map((th) => th.getAttribute('aria-sort'))"


def test_table_sorts_the_right_column_when_the_header_row_has_a_non_th_cell(tmp_path: Path) -> None:
    page = _mini_page(tmp_path, COLUMN_TABLES)
    out = run(
        page,
        {"click": "#corner th:nth-child(2) button"},
        ev(_first_cells("corner"), "q1_asc"),
        ev(_aria_sorts("corner"), "q1_aria"),
        {"click": "#corner th:nth-child(3) button"},
        ev(_first_cells("corner"), "q2_asc"),
        ev(_aria_sorts("corner"), "q2_aria"),
        {"click": "#corner th:nth-child(3) button"},
        ev(_first_cells("corner"), "q2_desc"),
        ev("[...document.querySelectorAll('#corner tbody tr')].map((tr) => [...tr.cells].map((c) => c.hasAttribute('data-q-num')))", "num"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["q1_asc"] == ["beta", "gamma", "alpha"]
    assert results["q1_aria"] == ["ascending", None]
    assert results["q2_asc"] == ["alpha", "gamma", "beta"]
    assert results["q2_aria"] == [None, "ascending"]
    assert results["q2_desc"] == ["beta", "gamma", "alpha"]
    assert results["num"] == [[False, False, True]] * 3


def test_table_header_with_a_colspan_sorts_by_its_first_spanned_column(tmp_path: Path) -> None:
    page = _mini_page(tmp_path, COLUMN_TABLES)
    out = run(
        page,
        {"click": "#span th:nth-child(1) button"},
        ev(_first_cells("span"), "name_asc"),
        ev(_aria_sorts("span"), "name_aria"),
        {"click": "#span th:nth-child(2) button"},
        ev(_first_cells("span"), "score_asc"),
        ev(_aria_sorts("span"), "score_aria"),
        ev("[...document.querySelectorAll('#span tbody tr')].map((tr) => tr.cells[2].hasAttribute('data-q-num'))", "num"),
    )
    assert_clean(out)
    results = out["results"]
    assert results["name_asc"] == ["a", "b", "c"]
    assert results["name_aria"] == ["ascending", None]
    assert results["score_asc"] == ["c", "b", "a"]
    assert results["score_aria"] == [None, "ascending"]
    assert results["num"] == [True] * 3


def test_table_data_from_rows_line_up_under_a_header_row_with_a_corner_cell(tmp_path: Path) -> None:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    (tmp_path / "rows.json").write_text(json.dumps({"rows": [{"Q1": 30, "Q2": 5}, {"Q1": 10, "Q2": 50}]}), encoding="utf-8")
    src = tmp_path / "bound.src.html"
    src.write_text(
        HEADER.replace('"mode": "offline"', '"mode": "offline", "data": "rows.json"')
        + '<q-table id="bound" data-from="rows"><table><thead><tr><td></td><th class="num">Q1</th><th class="num">Q2</th></tr></thead><tbody></tbody></table></q-table>\n',
        encoding="utf-8",
    )
    page = _build(src, tmp_path / "bound.html")
    out = run(
        page,
        {"waitFor": "document.querySelectorAll('#bound tbody tr').length === 2"},
        {"click": "#bound th:nth-child(2) button"},
        ev("[...document.querySelectorAll('#bound tbody tr')].map((tr) => [...tr.cells].map((c) => c.textContent))", "rows"),
    )
    assert_clean(out)
    assert out["results"]["rows"] == [["", "10", "50"], ["", "30", "5"]]


THEME_PROBE = """(() => {
  window.__themeListeners = new Set();
  window.__themeObservers = new Set();
  const add = document.addEventListener.bind(document);
  const remove = document.removeEventListener.bind(document);
  document.addEventListener = function (type, fn, options) {
    if (type === 'quirk-theme') window.__themeListeners.add(fn);
    return add(type, fn, options);
  };
  document.removeEventListener = function (type, fn, options) {
    if (type === 'quirk-theme') window.__themeListeners.delete(fn);
    return remove(type, fn, options);
  };
  const Native = window.MutationObserver;
  window.MutationObserver = class extends Native {
    observe(target, options) {
      if (target === document.documentElement) window.__themeObservers.add(this);
      return super.observe(target, options);
    }
    disconnect() {
      window.__themeObservers.delete(this);
      return super.disconnect();
    }
  };
})();"""


def test_chart_removed_from_the_page_stops_watching_the_theme(chart_page: Path) -> None:
    live = "({ listeners: window.__themeListeners.size, observers: window.__themeObservers.size })"
    out = run(
        chart_page,
        _drawn(),
        ev(live, "before"),
        ev("document.querySelectorAll('q-chart').length", "charts"),
        ev("document.querySelectorAll('q-chart').forEach((chart) => chart.remove())", "removed"),
        ev(live, "after"),
        ev("(document.documentElement.setAttribute('data-theme', 'dark'), new Promise((r) => setTimeout(() => r(window.__themeListeners.size), 100)))", "later"),
        initScripts=[THEME_PROBE],
    )
    assert_clean(out)
    results = out["results"]
    assert results["before"]["listeners"] >= results["charts"] and results["before"]["observers"] >= results["charts"]
    assert results["after"]["listeners"] == results["before"]["listeners"] - results["charts"]
    assert results["after"]["observers"] == results["before"]["observers"] - results["charts"]
    assert results["later"] == results["after"]["listeners"]


NO_NUMBERS_NOTE = "No numeric columns to chart; showing the table."


def _no_series_chart(chart_id: str, attrs: str, cells: list[str], label: str = "V") -> str:
    rows = "".join(f"<tr><td>M{i}</td><td>{cell}</td></tr>" for i, cell in enumerate(cells, 1))
    return (
        f'<q-chart id="{chart_id}" type="area" summary="A chart of {chart_id}." {attrs}>'
        f"<table><thead><tr><th>Month</th><th>{label}</th></tr></thead><tbody>{rows}</tbody></table></q-chart>\n"
    )


def test_chart_with_no_numeric_series_shows_the_table_with_a_note(tmp_path: Path) -> None:
    page = _mini_page(
        tmp_path,
        _no_series_chart("placeholder", "", ["-5", "n/a", "7"])
        + _no_series_chart("unknown-y", 'y="Nope"', ["1", "2", "3"])
        + _no_series_chart("text-y", 'y="V"', ["low", "mid", "high"])
        + _no_series_chart("fine", "", ["1", "2", "3"]),
    )
    view = """['placeholder', 'unknown-y', 'text-y', 'fine'].map((id) => {
      const q = document.querySelector('#' + id);
      const note = q.querySelector(':scope > [data-q-note]');
      const details = q.querySelector(':scope > details');
      return { id, note: note ? note.textContent : null, open: !!details && details.open, canvas: !!q.querySelector('canvas') };
    })"""
    out = run(
        page,
        {"waitFor": "document.querySelector('#fine canvas') && document.querySelector('#text-y details')"},
        ev(view, "views"),
    )
    assert_clean(out)
    views = {v["id"]: v for v in out["results"]["views"]}
    assert views["placeholder"] == {
        "id": "placeholder",
        "note": NO_NUMBERS_NOTE + " Not charted (non-numeric values): V.",
        "open": True,
        "canvas": False,
    }
    for chart_id in ("unknown-y", "text-y"):
        assert views[chart_id] == {"id": chart_id, "note": NO_NUMBERS_NOTE, "open": True, "canvas": False}
    assert views["fine"]["note"] is None and views["fine"]["canvas"] is True and views["fine"]["open"] is False


def _two_column_chart(chart_id: str, columns: dict[str, list[str]], attrs: str = "") -> str:
    labels = list(columns)
    head = "".join(f"<th>{label}</th>" for label in ["Month", *labels])
    size = len(next(iter(columns.values())))
    rows = "".join(
        f"<tr><td>M{i + 1}</td>" + "".join(f"<td>{columns[label][i]}</td>" for label in labels) + "</tr>"
        for i in range(size)
    )
    return (
        f'<q-chart id="{chart_id}" type="line" summary="A chart of {chart_id}." {attrs}>'
        f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></q-chart>\n"
    )


def test_chart_names_the_columns_it_skipped_when_choosing_series(tmp_path: Path) -> None:
    page = _mini_page(
        tmp_path,
        _two_column_chart("partial", {"A": ["1", "2", "3"], "B": ["4", "n/a", "6"]})
        + _two_column_chart("text", {"A": ["1", "2", "3"], "Owner": ["x", "y", "z"], "Notes": ["p", "q", "r"]})
        + _two_column_chart("only", {"B": ["4", "n/a", "6"]})
        + _two_column_chart("clean", {"A": ["1", "2", "3"], "B": ["4", "5", "6"]})
        + _two_column_chart("named", {"A": ["1", "2", "3"], "B": ["4", "n/a", "6"]}, 'y="A"'),
    )
    view = """['partial', 'text', 'only', 'clean', 'named'].map((id) => {
      const q = document.querySelector('#' + id);
      const note = q.querySelector(':scope > [data-q-note]');
      const chart = window.Chart.getChart(q.querySelector('canvas'));
      return { id, note: note ? note.textContent : null, labels: chart ? chart.data.datasets.map((d) => d.label) : null };
    })"""
    out = run(
        page,
        {"waitFor": "document.querySelector('#clean canvas') && document.querySelector('#only details')"},
        ev(view, "views"),
    )
    assert_clean(out)
    views = {v["id"]: v for v in out["results"]["views"]}
    assert views["partial"] == {"id": "partial", "note": "Not charted (non-numeric values): B.", "labels": ["A"]}
    assert views["text"]["note"] == "Not charted (non-numeric values): Owner, Notes."
    assert views["text"]["labels"] == ["A"]
    assert views["only"] == {
        "id": "only",
        "note": NO_NUMBERS_NOTE + " Not charted (non-numeric values): B.",
        "labels": None,
    }
    assert views["clean"] == {"id": "clean", "note": None, "labels": ["A", "B"]}
    assert views["named"]["note"] is None and views["named"]["labels"] == ["A"]


# --- highlighting -------------------------------------------------------------------------------

HIGHLIGHT_SRC = (
    HEADER
    + """<q-code id="by-ext" filename="retry.py">
  <pre><code>def fetch(url):
    # three attempts
    return get(url, retries=3)</code></pre>
</q-code>

<q-code id="by-attr" filename="notes.txt" language="json">
  <pre><code>{"max_attempts": 3}</code></pre>
</q-code>

<q-code id="plain" language="not-a-language">
  <pre><code>make test</code></pre>
</q-code>

<q-diff id="hdiff">
  <pre>--- a/config/payments.yaml
+++ b/config/payments.yaml
@@ -1,2 +1,2 @@
 provider: adyen
-max_attempts: 3
+max_attempts: 0</pre>
</q-diff>
"""
)

HIGHLIGHT_LIB = 'data-quirk-lib="highlightjs@'


@pytest.fixture(scope="module")
def highlight_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-highlight")
    src = work / "highlight.src.html"
    src.write_text(HIGHLIGHT_SRC, encoding="utf-8")
    page = _build(src, work / "highlight.html")
    _run_harness({"file": str(page)})
    return page


def test_highlight_js_is_inlined_only_for_code_and_diff(highlight_page: Path, board_page: Path) -> None:
    assert HIGHLIGHT_LIB in highlight_page.read_text(encoding="utf-8")
    assert HIGHLIGHT_LIB not in board_page.read_text(encoding="utf-8")


def test_code_highlights_by_extension_or_language_and_keeps_the_authored_text(highlight_page: Path) -> None:
    out = run(
        highlight_page,
        ev(
            """['by-ext', 'by-attr', 'plain'].map((id) => {
              const host = document.getElementById(id);
              const view = host.querySelector(':scope > pre[data-q-kit]');
              const authored = host.querySelector(':scope > pre:not([data-q-kit])');
              return {
                language: view && view.getAttribute('data-q-highlight'),
                tokens: view ? view.querySelectorAll('[class^="hljs-"]').length > 0 : false,
                same: view ? view.textContent === authored.textContent : null,
                authoredShown: getComputedStyle(authored).display !== 'none',
              };
            })""",
            "codes",
        ),
    )
    assert_clean(out)
    by_ext, by_attr, plain = out["results"]["codes"]
    assert by_ext == {"language": "py", "tokens": True, "same": True, "authoredShown": False}
    assert by_attr == {"language": "json", "tokens": True, "same": True, "authoredShown": False}
    assert plain == {"language": None, "tokens": False, "same": None, "authoredShown": True}


def test_code_copy_copies_the_authored_text_when_highlighted(highlight_page: Path) -> None:
    out = run(
        highlight_page,
        {"click": "#by-ext button"},
        {"waitFor": "document.querySelector('#by-ext button').textContent.trim() === 'Copied'"},
        ev("window.__copied", "copied"),
        initScripts=[STUB_CLIPBOARD],
    )
    assert_clean(out)
    assert out["results"]["copied"] == "def fetch(url):\n    # three attempts\n    return get(url, retries=3)"


def test_diff_highlights_each_line_by_the_file_extension(highlight_page: Path) -> None:
    out = run(
        highlight_page,
        ev(
            """[...document.querySelectorAll('#hdiff [data-q-code]')].map((td) => ({
              text: td.textContent,
              tokens: td.querySelectorAll('[class^="hljs-"]').length > 0,
            }))""",
            "rows",
        ),
    )
    assert_clean(out)
    assert out["results"]["rows"] == [
        {"text": " provider: adyen", "tokens": True},
        {"text": "-max_attempts: 3", "tokens": True},
        {"text": "+max_attempts: 0", "tokens": True},
    ]


@pytest.mark.parametrize("scheme", SCHEMES)
def test_highlight_token_colours_beat_the_page_stylesheet(highlight_page: Path, scheme: str) -> None:
    out = run(
        highlight_page,
        ev(
            """(() => {
              const probe = document.createElement('span');
              probe.style.color = 'var(--q-color-syntax-name)';
              document.body.appendChild(probe);
              const want = getComputedStyle(probe).color;
              probe.remove();
              const code = document.querySelector('#by-attr pre[data-q-kit] .hljs-attr');
              const diff = document.querySelector('#hdiff .hljs-attr');
              return { code: getComputedStyle(code).color === want, diff: getComputedStyle(diff).color === want };
            })()""",
            "colours",
        ),
        colorScheme=scheme,
    )
    assert_clean(out)
    assert out["results"]["colours"] == {"code": True, "diff": True}


def test_diff_without_long_lines_does_not_scroll_sideways(highlight_page: Path) -> None:
    out = run(
        highlight_page,
        ev(
            """(() => {
              const view = document.querySelector('#hdiff > [data-q-diff]');
              return view.scrollWidth <= view.clientWidth;
            })()""",
            "fits",
        ),
        viewport={"width": 1600, "height": 800},
    )
    assert_clean(out)
    assert out["results"]["fits"] is True


# --- default page shape ---------------------------------------------------------------------------------


def test_the_default_shape_uses_wide_screens_and_its_prose_fills_the_column(tmp_path: Path) -> None:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    filler = "\n".join(f"<p>Paragraph {i} of the page body, long enough to wrap at the prose measure.</p>" for i in range(60))
    src = tmp_path / "wide.src.html"
    src.write_text(HEADER + filler + "\n", encoding="utf-8")
    page = _build(src, tmp_path / "wide.html")
    out = run(
        page,
        ev("(window.scrollTo({ top: 2000, behavior: 'instant' }), window.scrollY > 1000)", "scrolled"),
        ev(
            """(() => {
              const main = document.querySelector('main').getBoundingClientRect();
              const p = document.querySelector('main p').getBoundingClientRect();
              return {
                wideMain: main.width > 960,
                proseFills: Math.abs(p.width - main.width) <= 1,
                fits: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
              };
            })()""",
            "layout",
        ),
        viewport={"width": 2000, "height": 900},
    )
    assert_clean(out)
    assert out["results"]["scrolled"] is True
    assert out["results"]["layout"] == {"wideMain": True, "proseFills": True, "fits": True}


# --- q-flow -----------------------------------------------------------------------------------

FLOW_ORDERS = """
<q-flow id="flow-orders" summary="Orders flow from checkout through billing to the ledger." direction="right" groups="panels">
  <script type="application/json">
  {
    "kinds": {"ui": 1, "worker": 2, "database": 3, "queue": 4},
    "groups": [
      {"id": "billing", "label": "Billing"}
    ],
    "nodes": [
      {"id": "checkout", "label": "Checkout", "kind": "ui"},
      {"id": "charge", "label": "Charge worker", "kind": "worker", "group": "billing",
       "detail": "<p>Retries 3x with backoff, then dead-letters.</p><ul><li>Max wait: 32s</li></ul>"},
      {"id": "ledger", "label": "Ledger", "kind": "database", "group": "billing",
       "detail": "<p>Append-only journal.</p>"},
      {"id": "retries", "label": "Retry queue", "kind": "queue", "group": "billing"},
      {"id": "refund", "label": "Refund worker", "kind": "worker", "group": "billing"}
    ],
    "edges": [
      {"from": "checkout", "to": "charge", "label": "order.created", "async": true},
      {"from": "charge", "to": "ledger", "label": "charge.settled"},
      {"from": "charge", "to": "retries", "label": "charge.failed", "async": true},
      {"from": "refund", "to": "ledger", "label": "refund.issued"}
    ]
  }
  </script>
</q-flow>

<q-flow id="flow-lanes" summary="Pipeline stages from intake through billing to settlement." direction="right" groups="lanes">
  <script type="application/json">
  {
    "kinds": {"ui": 1, "worker": 2, "database": 3, "queue": 4},
    "groups": [
      {"id": "intake", "label": "Intake"},
      {"id": "billing", "label": "Billing"},
      {"id": "retries", "label": "Retries", "parent": "billing"},
      {"id": "settlement", "label": "Settlement"}
    ],
    "nodes": [
      {"id": "checkout", "label": "Checkout", "kind": "ui", "group": "intake"},
      {"id": "charge", "label": "Charge worker", "kind": "worker", "group": "billing"},
      {"id": "retry_q", "label": "Retry queue", "kind": "queue", "group": "retries"},
      {"id": "ledger", "label": "Ledger", "kind": "database", "group": "settlement"}
    ],
    "edges": [
      {"from": "checkout", "to": "charge", "label": "order.created", "async": true},
      {"from": "charge", "to": "retry_q", "label": "charge.failed", "async": true},
      {"from": "charge", "to": "ledger", "label": "charge.settled"}
    ]
  }
  </script>
</q-flow>

<q-flow id="flow-lanes-down" summary="Top-to-bottom stages." direction="down" groups="lanes">
  <script type="application/json">
  {
    "groups": [
      {"id": "intake", "label": "Intake"},
      {"id": "billing", "label": "Billing"},
      {"id": "settlement", "label": "Settlement"}
    ],
    "nodes": [
      {"id": "checkout", "label": "Checkout", "group": "intake"},
      {"id": "charge", "label": "Charge worker", "group": "billing"},
      {"id": "ledger", "label": "Ledger", "group": "settlement"}
    ],
    "edges": [
      {"from": "checkout", "to": "charge"},
      {"from": "charge", "to": "ledger"}
    ]
  }
  </script>
</q-flow>
"""


@pytest.fixture(scope="module")
def flow_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-flow")
    src = work / "flow.src.html"
    src.write_text(HEADER + FLOW_ORDERS, encoding="utf-8")
    return _build(src, work / "flow.html")


def test_flow_renders_at_rest_with_controls_closed_list_and_sync_async_edges(flow_page: Path) -> None:
    out = run(
        flow_page,
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              const svg = f.querySelector('[data-q-flow-svg]');
              const checkout = f.querySelector('[data-q-flow-node="checkout"] > [data-q-flow-box]').getBoundingClientRect();
              const charge = f.querySelector('[data-q-flow-node="charge"] > [data-q-flow-box]').getBoundingClientRect();
              const billing = f.querySelector('[data-q-flow-group="billing"] > [data-q-flow-group-box]').getBoundingClientRect();
              const edges = [...f.querySelectorAll('[data-q-flow-edge]')].map((e) => ({
                from: e.getAttribute('data-q-flow-from'),
                to: e.getAttribute('data-q-flow-to'),
                dash: e.querySelector('[data-q-flow-edge-line]').getAttribute('stroke-dasharray'),
                marker: e.querySelector('[data-q-flow-edge-line]').getAttribute('marker-end'),
              }));
              const actions = [...f.querySelectorAll('[data-q-flow-controls] button')].map((b) => b.getAttribute('data-q-flow-action'));
              const details = f.querySelector('details[data-q-flow-list]');
              return {
                ready: f.getAttribute('data-q-flow-ready'),
                ariaLabel: svg.getAttribute('aria-label'),
                pulsing: f.hasAttribute('data-q-flow-pulsing'),
                drawerHidden: f.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
                checkoutLeftOfBilling: checkout.right <= billing.left + 4,
                chargeInsideBilling: charge.left >= billing.left && charge.right <= billing.right,
                actions,
                edges,
                detailsOpen: details.open,
                listNodes: details.querySelectorAll('[data-q-flow-list-node]').length,
              };
            })()""",
            "state",
        ),
    )
    assert_clean(out)
    st = out["results"]["state"]
    assert st["ready"] == "true"
    assert st["ariaLabel"] == "Orders flow from checkout through billing to the ledger."
    assert st["pulsing"] is False
    assert st["drawerHidden"] is True
    assert st["checkoutLeftOfBilling"] is True
    assert st["chargeInsideBilling"] is True
    assert st["actions"] == ["zoom-in", "zoom-out", "fit", "expand"]
    assert st["detailsOpen"] is False
    assert st["listNodes"] == 5
    by_pair = {(e["from"], e["to"]): e for e in st["edges"]}
    assert by_pair[("checkout", "charge")]["dash"] == "6 4"
    assert by_pair[("charge", "retries")]["dash"] == "6 4"
    assert by_pair[("charge", "ledger")]["dash"] is None
    assert all(e["marker"].startswith("url(#q-flow-arrow-") for e in st["edges"])


def test_flow_focusing_a_node_lights_path_dims_unconnected_pulses_hop_by_hop_and_opens_drawer(flow_page: Path) -> None:
    out = run(
        flow_page,
        {"click": '#flow-orders [data-q-flow-node="charge"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              const litNodes = [...f.querySelectorAll('[data-q-flow-node][data-q-flow-lit]')].map((n) => n.getAttribute('data-q-flow-node')).sort();
              const dimNodes = [...f.querySelectorAll('[data-q-flow-node][data-q-flow-dim]')].map((n) => n.getAttribute('data-q-flow-node')).sort();
              const hops = {};
              for (const e of f.querySelectorAll('[data-q-flow-edge][data-q-flow-lit]')) {
                hops[e.getAttribute('data-q-flow-from') + '->' + e.getAttribute('data-q-flow-to')] = Number(e.getAttribute('data-q-flow-hop'));
              }
              const dimEdges = [...f.querySelectorAll('[data-q-flow-edge][data-q-flow-dim]')].map(
                (e) => e.getAttribute('data-q-flow-from') + '->' + e.getAttribute('data-q-flow-to')
              );
              const drawer = f.querySelector('[data-q-flow-drawer]');
              const chargeBox = f.querySelector('[data-q-flow-node="charge"] > [data-q-flow-box]').getBoundingClientRect();
              const drawerBox = drawer.getBoundingClientRect();
              return {
                pulsing: f.hasAttribute('data-q-flow-pulsing'),
                litNodes,
                dimNodes,
                hops,
                dimEdges,
                drawerOpen: !drawer.hasAttribute('data-q-inactive'),
                drawerTitle: drawer.querySelector('h3').textContent,
                drawerKind: drawer.querySelector('[data-q-flow-drawer-kind]').textContent,
                drawerDetail: drawer.querySelector('[data-q-flow-drawer-detail]').textContent,
                notCovered: chargeBox.right <= drawerBox.left + 2,
              };
            })()""",
            "focused",
        ),
        {"click": '#flow-orders [data-q-flow-drawer] [data-q-flow-target="ledger"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              return {
                title: f.querySelector('[data-q-flow-drawer] h3').textContent,
                litNodes: [...f.querySelectorAll('[data-q-flow-node][data-q-flow-lit]')].map((n) => n.getAttribute('data-q-flow-node')).sort(),
              };
            })()""",
            "moved",
        ),
        {"press": "Escape"},
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              return {
                pulsing: f.hasAttribute('data-q-flow-pulsing'),
                drawerHidden: f.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
                dimCount: f.querySelectorAll('[data-q-flow-dim]').length,
              };
            })()""",
            "cleared",
        ),
    )
    assert_clean(out)
    foc = out["results"]["focused"]
    assert foc["pulsing"] is True
    assert foc["litNodes"] == ["charge", "checkout", "ledger", "retries"]
    assert foc["dimNodes"] == ["refund"]
    assert foc["hops"] == {"checkout->charge": 0, "charge->ledger": 1, "charge->retries": 1}
    assert foc["dimEdges"] == ["refund->ledger"]
    assert foc["drawerOpen"] is True
    assert foc["drawerTitle"] == "Charge worker"
    assert foc["drawerKind"] == "worker"
    assert "Retries 3x with backoff" in foc["drawerDetail"]
    assert foc["notCovered"] is True

    moved = out["results"]["moved"]
    assert moved["title"] == "Ledger"
    assert moved["litNodes"] == ["charge", "checkout", "ledger", "refund"]

    cleared = out["results"]["cleared"]
    assert cleared == {"pulsing": False, "drawerHidden": True, "dimCount": 0}


# a fake clock drives the pulse frame by frame, so dot positions are read at exact times
FLOW_FAKE_CLOCK = """(() => {
  window.__now = 1000;
  window.__frames = [];
  performance.now = () => window.__now;
  window.requestAnimationFrame = (fn) => { window.__frames.push(fn); return window.__frames.length; };
  window.cancelAnimationFrame = () => {};
  window.__tick = (t) => {
    window.__now = t;
    const frames = window.__frames;
    window.__frames = [];
    frames.forEach((fn) => fn(t));
  };
  window.__arcs = (f, from, to) => {
    const g = f.querySelector(`[data-q-flow-edge][data-q-flow-from="${from}"][data-q-flow-to="${to}"]`);
    const line = g.querySelector('[data-q-flow-edge-line]');
    const maskId = g.querySelector('[data-q-flow-edge-pulse]').getAttribute('mask').slice(5, -1);
    const len = line.getTotalLength();
    const arcs = [...f.querySelector('#' + CSS.escape(maskId)).querySelectorAll('circle')]
      .filter((c) => !c.hasAttribute('data-q-inactive'))
      .map((c) => {
        const cx = Number(c.getAttribute('cx'));
        const cy = Number(c.getAttribute('cy'));
        let best = 0;
        let bestD = Infinity;
        for (let s = 0; s <= len; s += 0.5) {
          const p = line.getPointAtLength(s);
          const d = Math.hypot(p.x - cx, p.y - cy);
          if (d < bestD) { bestD = d; best = s; }
        }
        return best;
      })
      .sort((a, b) => a - b);
    return { len, arcs };
  };
  return true;
})()"""


def test_flow_pulse_travels_at_one_speed_and_streams_before_the_last_one_lands(flow_page: Path) -> None:
    out = run(
        flow_page,
        ev(FLOW_FAKE_CLOCK, "clock"),
        {"click": '#flow-orders [data-q-flow-node="charge"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              window.__tick(1150);
              const first = window.__arcs(f, 'checkout', 'charge');
              const speed = first.arcs[0] / 0.15;
              window.__tick(1000 + (1000 * (first.len + 20)) / speed);
              const ledger = window.__arcs(f, 'charge', 'ledger');
              const retries = window.__arcs(f, 'charge', 'retries');
              const longer = ledger.len > retries.len ? ['charge', 'ledger'] : ['charge', 'retries'];
              const lifetime = (1000 * (first.len + Math.max(ledger.len, retries.len))) / speed;
              window.__tick(1000 + lifetime - 30);
              const laterOnFirst = window.__arcs(f, 'checkout', 'charge').arcs.length;
              const onLonger = window.__arcs(f, longer[0], longer[1]).arcs.length;
              return {
                lens: [first.len, ledger.len, retries.len],
                firstArcs: first.arcs,
                ledgerArc: ledger.arcs[ledger.arcs.length - 1],
                retriesArc: retries.arcs[retries.arcs.length - 1],
                laterWaves: laterOnFirst + (onLonger - 1),
              };
            })()""",
            "pulse",
        ),
    )
    assert_clean(out)
    p = out["results"]["pulse"]
    first_len, ledger_len, retries_len = p["lens"]
    # the speed check only discriminates when the edges differ in length
    assert abs(ledger_len - first_len) > 10 or abs(retries_len - first_len) > 10, p
    assert p["firstArcs"], p
    assert abs(p["ledgerArc"] - 20) < 3, p
    assert abs(p["retriesArc"] - 20) < 3, p
    assert p["laterWaves"] >= 1, p


def test_flow_group_focus_zooms_and_dims_without_pulsing_or_opening_drawer(flow_page: Path) -> None:
    out = run(
        flow_page,
        ev("document.querySelector('#flow-orders [data-q-flow-viewport]').getAttribute('transform')", "before"),
        {"click": '#flow-orders [data-q-flow-group-header="billing"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              return {
                after: f.querySelector('[data-q-flow-viewport]').getAttribute('transform'),
                pulsing: f.hasAttribute('data-q-flow-pulsing'),
                drawerHidden: f.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
                dimNodes: [...f.querySelectorAll('[data-q-flow-node][data-q-flow-dim]')].map((n) => n.getAttribute('data-q-flow-node')),
              };
            })()""",
            "group",
        ),
    )
    assert_clean(out)
    grp = out["results"]["group"]
    assert grp["after"] != out["results"]["before"]
    assert grp["pulsing"] is False
    assert grp["drawerHidden"] is True
    assert grp["dimNodes"] == ["checkout"]


def test_flow_two_graphs_and_lanes_in_both_directions_with_nested_panel(flow_page: Path) -> None:
    out = run(
        flow_page,
        {"click": '#flow-orders [data-q-flow-node="charge"]'},
        ev(
            """(() => {
              const f2 = document.querySelector('#flow-lanes');
              const r = (sel) => f2.querySelector(sel).getBoundingClientRect();
              const intake = r('[data-q-flow-group="intake"] > [data-q-flow-group-box]');
              const billing = r('[data-q-flow-group="billing"] > [data-q-flow-group-box]');
              const settlement = r('[data-q-flow-group="settlement"] > [data-q-flow-group-box]');
              const retries = r('[data-q-flow-group="retries"] > [data-q-flow-group-box]');
              const f3 = document.querySelector('#flow-lanes-down');
              const r3 = (sel) => f3.querySelector(sel).getBoundingClientRect();
              const dIntake = r3('[data-q-flow-group="intake"] > [data-q-flow-group-box]');
              const dBilling = r3('[data-q-flow-group="billing"] > [data-q-flow-group-box]');
              const dSettlement = r3('[data-q-flow-group="settlement"] > [data-q-flow-group-box]');
              return {
                f2Isolated: !f2.hasAttribute('data-q-flow-pulsing') && f2.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
                lanesOrderRight: intake.left < billing.left && billing.left < settlement.left,
                lanesSameHeight: Math.abs(intake.height - billing.height) <= 1 && Math.abs(billing.height - settlement.height) <= 1,
                retriesIsPanelInsideBilling:
                  f2.querySelector('[data-q-flow-group="retries"]').getAttribute('data-q-flow-lane') === 'false' &&
                  retries.left >= billing.left && retries.right <= billing.right,
                lanesOrderDown: dIntake.top < dBilling.top && dBilling.top < dSettlement.top,
                lanesSameWidthDown: Math.abs(dIntake.width - dBilling.width) <= 1 && Math.abs(dBilling.width - dSettlement.width) <= 1,
              };
            })()""",
            "lanes",
        ),
    )
    assert_clean(out)
    assert out["results"]["lanes"] == {
        "f2Isolated": True,
        "lanesOrderRight": True,
        "lanesSameHeight": True,
        "retriesIsPanelInsideBilling": True,
        "lanesOrderDown": True,
        "lanesSameWidthDown": True,
    }


def test_flow_keyboard_roving_tabindex_arrows_enter_live_region_zoom_keys_and_expand(flow_page: Path) -> None:
    out = run(
        flow_page,
        {"focus": '#flow-orders [data-q-flow-node][tabindex="0"]'},
        ev("document.querySelectorAll('#flow-orders [data-q-flow-node][tabindex=\"0\"]').length", "rovingCount"),
        {"press": "ArrowRight"},
        ev("document.activeElement.getAttribute('data-q-flow-node')", "movedFocus"),
        {"focus": '#flow-orders [data-q-flow-node="charge"]'},
        {"press": "Enter"},
        ev("document.querySelector('#flow-orders [data-q-flow-live]').textContent", "live"),
        ev("document.querySelector('#flow-orders [data-q-flow-viewport]').getAttribute('transform')", "t0"),
        {"press": "+"},
        ev("document.querySelector('#flow-orders [data-q-flow-viewport]').getAttribute('transform')", "tPlus"),
        {"press": "0"},
        ev("document.querySelector('#flow-orders [data-q-flow-viewport]').getAttribute('transform')", "tFit"),
        {"click": '#flow-orders [data-q-flow-action="expand"]'},
        ev("document.querySelector('#flow-orders').hasAttribute('data-q-flow-expanded')", "expanded"),
        {"press": "Escape"},
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              return {
                expanded: f.hasAttribute('data-q-flow-expanded'),
                stillFocused: !f.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
              };
            })()""",
            "afterEscapeExpand",
        ),
    )
    assert_clean(out)
    res = out["results"]
    assert res["rovingCount"] == 1
    assert res["movedFocus"] != "checkout"
    assert res["live"] == "Charge worker, worker, 1 upstream, 2 downstream"
    assert res["tPlus"] != res["t0"]
    assert res["tFit"] == res["t0"]
    assert res["expanded"] is True
    assert res["afterEscapeExpand"] == {"expanded": False, "stillFocused": True}


def test_flow_plain_wheel_does_not_zoom_while_ctrl_wheel_zooms_and_phone_uses_bottom_sheet(flow_page: Path) -> None:
    out = run(
        flow_page,
        ev(
            """(() => {
              const svg = document.querySelector('#flow-orders [data-q-flow-svg]');
              const vp = document.querySelector('#flow-orders [data-q-flow-viewport]');
              const before = vp.getAttribute('transform');
              svg.dispatchEvent(new WheelEvent('wheel', { deltaY: -120, bubbles: true, cancelable: true }));
              const afterPlain = vp.getAttribute('transform');
              svg.dispatchEvent(new WheelEvent('wheel', { deltaY: -120, ctrlKey: true, bubbles: true, cancelable: true }));
              const afterCtrl = vp.getAttribute('transform');
              return { unchangedOnPlain: afterPlain === before, changedOnCtrl: afterCtrl !== before };
            })()""",
            "wheel",
        ),
        {"viewport": {"width": 375, "height": 800}},
        {"click": '#flow-orders [data-q-flow-node="charge"]'},
        ev(
            """(() => {
              const stage = document.querySelector('#flow-orders [data-q-flow-stage]').getBoundingClientRect();
              const drawer = document.querySelector('#flow-orders [data-q-flow-drawer]').getBoundingClientRect();
              return {
                fullWidth: Math.abs(drawer.width - stage.width) <= 2,
                atBottom: Math.abs(drawer.bottom - stage.bottom) <= 2,
                lowerHalf: drawer.top > stage.top + 40,
              };
            })()""",
            "sheet",
        ),
    )
    assert_clean(out)
    assert out["results"]["wheel"] == {"unchangedOnPlain": True, "changedOnCtrl": True}
    assert out["results"]["sheet"] == {"fullWidth": True, "atBottom": True, "lowerHalf": True}


def test_flow_reduced_motion_and_no_js_and_layout_failure_fallbacks(flow_page: Path, tmp_path: Path) -> None:
    reduced = run(
        flow_page,
        {"click": '#flow-orders [data-q-flow-node="charge"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              const line = f.querySelector('[data-q-flow-edge][data-q-flow-lit] [data-q-flow-edge-line]');
              return {
                pulsing: f.hasAttribute('data-q-flow-pulsing'),
                width: line.getAttribute('stroke-width'),
                marker: line.getAttribute('marker-end').includes('arrow-lit'),
              };
            })()""",
            "reduced",
        ),
        initScripts=[
            """
            const orig = window.matchMedia;
            window.matchMedia = (q) => q.includes('prefers-reduced-motion: reduce')
              ? { matches: true, media: q, addEventListener() {}, removeEventListener() {} }
              : orig(q);
            """
        ],
    )
    assert_clean(reduced)
    assert reduced["results"]["reduced"] == {"pulsing": False, "width": "3.5", "marker": True}

    nojs = run(
        flow_page,
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              const details = f.querySelector('details[data-q-flow-list]');
              return {
                noticeVisible: f.querySelector('[data-q-flow-notice]').getBoundingClientRect().height > 0,
                detailsOpen: details.open,
                nodeItems: details.querySelectorAll('[data-q-flow-list-node]').length,
              };
            })()""",
            "nojs",
        ),
        javaScript=False,
    )
    assert_clean(nojs)
    assert nojs["results"]["nojs"] == {"noticeVisible": True, "detailsOpen": True, "nodeItems": 5}

    failed = run(
        flow_page,
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              const details = f.querySelector('details[data-q-flow-list]');
              return {
                ready: f.getAttribute('data-q-flow-ready'),
                notice: f.querySelector('[data-q-flow-notice]').textContent,
                detailsOpen: details.open,
              };
            })()""",
            "failed",
        ),
        initScripts=[
            """
            Object.defineProperty(window, 'quirkFlow', {
              configurable: true,
              get() { return { ELK: function () { return { layout() { return Promise.reject(new Error('boom')); } }; } }; },
              set() {}
            });
            """
        ],
    )
    assert_clean(failed)
    assert failed["results"]["failed"]["ready"] == "error"
    assert "could not be drawn" in failed["results"]["failed"]["notice"]
    assert failed["results"]["failed"]["detailsOpen"] is True


def test_flow_theme_toggle_recolors_without_relayout_and_touch_allows_only_two_fingers(flow_page: Path) -> None:
    out = run(
        flow_page,
        ev(
            """(() => {
              const f = document.querySelector('#flow-orders');
              const svg = f.querySelector('[data-q-flow-svg]');
              const stripe = f.querySelector('[data-q-flow-node="checkout"] [data-q-flow-stripe]');
              const box = f.querySelector('[data-q-flow-node="checkout"] [data-q-flow-box]');
              document.documentElement.setAttribute('data-theme', 'light');
              const lightFill = getComputedStyle(box).fill;
              const lightStripe = getComputedStyle(stripe).fill;
              document.documentElement.setAttribute('data-theme', 'dark');
              const darkFill = getComputedStyle(box).fill;
              const darkStripe = getComputedStyle(stripe).fill;
              const sameSvg = f.querySelector('[data-q-flow-svg]') === svg;
              const touchAction = getComputedStyle(svg).touchAction;
              return {
                recoloredBox: lightFill !== darkFill,
                recoloredStripe: lightStripe !== darkStripe,
                sameSvg,
                touchAction,
              };
            })()""",
            "themeAndTouch",
        ),
    )
    assert_clean(out)
    res = out["results"]["themeAndTouch"]
    assert res["recoloredBox"] is True
    assert res["recoloredStripe"] is True
    assert res["sameSvg"] is True
    assert res["touchAction"] in ("manipulation", "pan-x pan-y pinch-zoom") and res["touchAction"] != "none"


FLOW_SHAPES = """
<q-flow id="flow-checkout" summary="Checkout with a payment decision, a retry loop and a refund subprocess.">
  <script type="application/json">
  {
    "kinds": {"ui": 1, "worker": 2, "queue": 4},
    "nodes": [
      {"id": "checkout", "label": "Checkout", "kind": "ui"},
      {"id": "charge", "label": "Charge worker", "kind": "worker"},
      {"id": "paid", "label": "Paid?", "kind": "worker", "shape": "decision"},
      {"id": "ship", "label": "Ship", "kind": "worker"},
      {"id": "retry_q", "label": "Retry queue", "kind": "queue"},
      {"id": "refund", "label": "Issue refund", "kind": "worker", "shape": "subprocess", "flow": "refund-flow"}
    ],
    "edges": [
      {"from": "checkout", "to": "charge", "label": "order.created", "async": true},
      {"from": "charge", "to": "paid"},
      {"from": "paid", "to": "ship", "label": "Yes"},
      {"from": "paid", "to": "retry_q", "label": "No"},
      {"from": "retry_q", "to": "charge", "label": "retry up to 3x", "loop": true},
      {"from": "ship", "to": "refund", "label": "on return"}
    ]
  }
  </script>
</q-flow>

<div style="height: 1400px" aria-hidden="true"></div>

<q-flow id="refund-flow" summary="The refund process.">
  <script type="application/json">
  {
    "nodes": [
      {"id": "request", "label": "Refund requested"},
      {"id": "approve", "label": "Approve"},
      {"id": "payout", "label": "Pay out"}
    ],
    "edges": [
      {"from": "request", "to": "approve"},
      {"from": "approve", "to": "payout"}
    ]
  }
  </script>
</q-flow>

<q-flow id="flow-poller" summary="A poller that loops on itself.">
  <script type="application/json">
  {
    "nodes": [
      {"id": "poller", "label": "Status poller"},
      {"id": "done", "label": "Done"}
    ],
    "edges": [
      {"from": "poller", "to": "poller", "label": "every 30s"},
      {"from": "poller", "to": "done"}
    ]
  }
  </script>
</q-flow>

<q-flow id="flow-links" summary="Subprocesses with and without a linked flow.">
  <script type="application/json">
  {
    "nodes": [
      {"id": "wired", "label": "Wired", "shape": "subprocess", "flow": "refund-flow"},
      {"id": "lost", "label": "Lost", "shape": "subprocess", "flow": "refund-flow"},
      {"id": "bare", "label": "Bare", "shape": "subprocess"}
    ],
    "edges": [
      {"from": "wired", "to": "lost"},
      {"from": "lost", "to": "bare"}
    ]
  }
  </script>
</q-flow>

<q-flow id="flow-bom-link" summary="A subprocess whose flow is a lone byte order mark.">
  <script type="application/json">
  {
    "nodes": [
      {"id": "bom", "label": "Bom", "shape": "subprocess", "flow": "\ufeff"},
      {"id": "after", "label": "After"}
    ],
    "edges": [{"from": "bom", "to": "after"}]
  }
  </script>
</q-flow>

<q-flow id="&#xFEFF;" summary="The graph a byte order mark names.">
  <script type="application/json">
  {"nodes": [{"id": "only", "label": "Only"}], "edges": []}
  </script>
</q-flow>

<q-flow id="flow-blank-nel" summary="A subprocess whose flow is a lone next-line character.">
  <script type="application/json">
  {
    "nodes": [
      {"id": "nel", "label": "Nel", "shape": "subprocess", "flow": "refund-flow"},
      {"id": "after", "label": "After"}
    ],
    "edges": [{"from": "nel", "to": "after"}]
  }
  </script>
</q-flow>

<q-flow id="flow-blank-us" summary="A subprocess whose flow is a lone unit separator.">
  <script type="application/json">
  {
    "nodes": [
      {"id": "us", "label": "Us", "shape": "subprocess", "flow": "refund-flow"},
      {"id": "after", "label": "After"}
    ],
    "edges": [{"from": "us", "to": "after"}]
  }
  </script>
</q-flow>

<q-flow id="flow-bad-oval" summary="A graph with an unknown shape.">
  <script type="application/json">
  {"nodes": [{"id": "odd", "label": "Odd", "shape": "box"}], "edges": []}
  </script>
</q-flow>

<q-flow id="flow-bad-exit" summary="A decision with one exit.">
  <script type="application/json">
  {
    "nodes": [
      {"id": "lone", "label": "Lone?", "shape": "box"},
      {"id": "next", "label": "Next"}
    ],
    "edges": [{"from": "lone", "to": "next", "label": "Yes"}]
  }
  </script>
</q-flow>
"""


_TRACE_V1 = {"order": "R-1042", "status": "queued", "lines": [{"item": "Coffee beans", "qty": 2, "price": 18}]}
_TRACE_V2 = {**_TRACE_V1, "subtotal": 36, "discount": {"code": "LOYALTY10", "amount": 3.6}, "total": 32.4}
_TRACE_V3 = {**_TRACE_V2, "tax": 2.67, "total": 35.07}
_TRACE_V4 = {**_TRACE_V3, "status": "declined", "attempt": 1, "decline": "insufficient_funds"}
_TRACE_V6 = {**_TRACE_V4, "status": "retry_scheduled", "retry_at": "2026-10-18T09:00Z"}
_TRACE_V7 = {
    **{k: v for k, v in _TRACE_V6.items() if k not in ("decline", "retry_at")},
    "status": "paid",
    "attempt": 2,
    "charge": "ch_88",
}
_TRACE_V9 = {**_TRACE_V7, "status": "settled", "settled_at": "2026-10-18T09:02Z"}
_TRACE_PAID = {**_TRACE_V3, "status": "paid", "attempt": 1, "charge": "ch_88"}
_TRACE_SETTLED = {**_TRACE_PAID, "status": "settled", "settled_at": "2026-10-18T09:02Z"}
_TRACE_DEEP1 = {
    "customer": {
        "name": "Ada",
        "tags": ["vip"],
        "contact": "ada@example.com",
        "address": {"city": "Austin", "geo": {"zone": "S", "coordinates": {"lat": 30.27, "lng": -97.74}}},
    }
}
_TRACE_DEEP2 = {"customer": {**_TRACE_DEEP1["customer"], "tags": ["vip", "beta"]}}
_TRACE_DEEP3 = {
    "customer": {
        **_TRACE_DEEP2["customer"],
        "contact": {"email": "ada@example.com", "phone": "555-0100"},
        "address": {"city": "Austin", "geo": {"zone": "S", "coordinates": {"lat": 30.28, "lng": -97.74}}},
    }
}

RENEWAL_GRAPH = {
    "nodes": [
        {"id": "scheduler", "label": "Renewal scheduler"},
        {"id": "pricing", "label": "Pricing"},
        {"id": "tax", "label": "Tax"},
        {"id": "charge", "label": "Charge worker"},
        {"id": "paid", "label": "Paid?", "shape": "decision"},
        {"id": "retry", "label": "Retry queue"},
        {"id": "settle", "label": "Settlement"},
    ],
    "edges": [
        {"from": "scheduler", "to": "pricing"},
        {"id": "tax-domestic", "from": "pricing", "to": "tax", "label": "domestic quote"},
        {"id": "tax-intl", "from": "pricing", "to": "tax", "label": "cross-border quote"},
        {"from": "tax", "to": "charge"},
        {"from": "charge", "to": "paid"},
        {"from": "paid", "to": "settle", "label": "Yes"},
        {"from": "paid", "to": "retry", "label": "No"},
        {"id": "retry", "from": "retry", "to": "charge", "label": "retry up to 3x", "loop": True},
    ],
    "traces": [
        {
            "id": "succeeds",
            "label": "Card succeeds",
            "steps": [
                {"node": "scheduler", "value": _TRACE_V1},
                {"node": "pricing", "value": _TRACE_V2, "note": "Pricing applies the loyalty discount"},
                {"node": "tax", "via": "tax-domestic", "value": _TRACE_V3, "note": "Tax adds 8.25% sales tax"},
                {"node": "charge", "value": _TRACE_PAID, "note": "The card is accepted"},
                {"node": "paid", "value": _TRACE_PAID, "note": "Paid? answers Yes"},
                {"node": "settle", "value": _TRACE_SETTLED, "note": "The order settles"},
            ],
        },
        {
            "id": "declined",
            "label": "Card declined, retried",
            "steps": [
                {"node": "scheduler", "value": _TRACE_V1},
                {"node": "pricing", "value": _TRACE_V2, "note": "Pricing applies the loyalty discount"},
                {"node": "tax", "via": "tax-domestic", "value": _TRACE_V3, "note": "Tax adds 8.25% sales tax"},
                {"node": "charge", "value": _TRACE_V4, "note": "The card is declined"},
                {"node": "paid", "value": _TRACE_V4, "note": "Paid? answers No"},
                {"node": "retry", "value": _TRACE_V6, "note": "The retry is booked for tomorrow"},
                {"node": "charge", "value": _TRACE_V7, "note": "The second attempt succeeds"},
                {"node": "paid", "value": _TRACE_V7, "note": "Paid? answers Yes"},
                {"node": "settle", "value": _TRACE_V9, "note": "The order settles"},
            ],
        },
        {
            "id": "deep",
            "label": "Nested customer",
            "steps": [
                {"node": "scheduler", "value": _TRACE_DEEP1},
                {"node": "pricing", "value": _TRACE_DEEP2},
                {"node": "tax", "via": "tax-domestic", "value": _TRACE_DEEP3},
            ],
        },
    ],
}

BADVIA_GRAPH = {
    "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
    "edges": [{"id": "ab", "from": "a", "to": "b"}],
    "traces": [
        {
            "id": "t",
            "label": "T",
            "steps": [{"node": "a", "value": 1}, {"node": "b", "value": 2, "via": "ab"}],
        }
    ],
}

_WIDE_VALUE = {
    "order_id": "ord_4172",
    "status": "waiting",
    "attempt": 1,
    "wait_s": 2,
    "idempotency_key": "idem_9c3e",
    "customer": {"name": "Ada", "tags": ["vip"]},
}
WIDE_GRAPH = {
    "nodes": [
        {"id": "a", "label": "Checkout API"},
        {"id": "b", "label": "Retry queue"},
        {"id": "c", "label": "Retry worker"},
        {"id": "d", "label": "Order ledger"},
    ],
    "edges": [
        {"id": "a-b", "from": "a", "to": "b"},
        {"id": "b-c", "from": "b", "to": "c"},
        {"id": "c-d", "from": "c", "to": "d"},
        {"id": "d-a", "from": "d", "to": "a", "loop": True},
    ],
    "traces": [
        {
            "id": "long",
            "label": "Long walk",
            "steps": [
                {
                    "node": node,
                    **({"via": via} if via else {}),
                    "value": {**_WIDE_VALUE, "attempt": n},
                    "note": f"Step {n + 1} of the walk, with a note long enough to wrap onto a second line in the panel.",
                }
                for n, (node, via) in enumerate(
                    [("a", None), ("b", "a-b"), ("c", "b-c"), ("d", "c-d")]
                    + [("a", "d-a"), ("b", "a-b"), ("c", "b-c"), ("d", "c-d"), ("a", "d-a"), ("b", "a-b")]
                )
            ],
        }
    ],
}

# value placeholders swapped for non-JSON text after the build, so the build-time check never sees them
BADVALUE_CASES = {
    "inf": ('"BADVALUE"', "1e9999"),
    "neginf": ('{"deep": [{"n": "BADVALUE"}]}', '{"deep": [{"n": -1e9999}]}'),
    "sur": ('"BADVALUE"', r'"\ud800"'),
    "surpair": ('"BADVALUE"', r'"\ud83d\ude00"'),
    "surkey": ('{"BADVALUE": 1}', r'{"\udc00": 1}'),
    "surdeep": ('{"a": [{"k": "BADVALUE"}]}', r'{"a": [{"k": "x\ud800y"}]}'),
    "nested": ('"BADVALUE"', "[" * 12000 + "]" * 12000),
}


def _badvalue_graph(value: object) -> dict:
    return {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b"}],
        "traces": [
            {"id": "t", "label": "T", "steps": [{"node": "a", "value": 1}, {"node": "b", "value": value}]}
        ],
    }


def _badvalue_flow(name: str, before: str) -> str:
    graph = _badvalue_graph(json.loads(before.replace("BADVALUE", f"BAD_{name}")))
    return (
        f'<q-flow id="bv-{name}" summary="A trace value that is not JSON.">\n'
        f'  <script type="application/json">\n  {json.dumps(graph)}\n  </script>\n</q-flow>'
    )


# graph text swapped after the build: a lone surrogate must fail the whole graph, a valid pair must not
BADTEXT_CASES = {
    "label": r'"\ud800"',
    "emoji": r'"\ud83d\ude00 ok"',
}


def _badtext_flow(name: str) -> str:
    graph = {
        "nodes": [{"id": "a", "label": f"BADTEXT_{name}"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b"}],
    }
    return (
        f'<q-flow id="bt-{name}" summary="A node label that may not be UTF-8.">\n'
        f'  <script type="application/json">\n  {json.dumps(graph)}\n  </script>\n</q-flow>'
    )


BADVALUE_FLOWS = "\n".join(_badtext_flow(name) for name in BADTEXT_CASES) + "\n" + "\n".join(_badvalue_flow(name, before) for name, (before, _after) in BADVALUE_CASES.items())

FLOW_TRACES = f"""
<q-flow id="renewal" summary="How a renewal order is priced, taxed and charged.">
  <script type="application/json">
  {json.dumps(RENEWAL_GRAPH, indent=2)}
  </script>
</q-flow>

<q-flow id="wide" summary="A wide, shallow graph with a long trace." direction="right">
  <script type="application/json">
  {json.dumps(WIDE_GRAPH, indent=2)}
  </script>
</q-flow>

<q-flow id="plain" summary="A graph with no traces.">
  <script type="application/json">
  {{"nodes": [{{"id": "a", "label": "A"}}, {{"id": "b", "label": "B"}}], "edges": [{{"from": "a", "to": "b"}}]}}
  </script>
</q-flow>

<q-flow id="badvia" summary="A graph whose trace names an edge that is not there.">
  <script type="application/json">
  {json.dumps(BADVIA_GRAPH, indent=2)}
  </script>
</q-flow>
{BADVALUE_FLOWS}
"""


@pytest.fixture(scope="module")
def flow_shapes_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-flow-shapes")
    src = work / "shapes.src.html"
    src.write_text(HEADER + FLOW_SHAPES, encoding="utf-8")
    built = _build(src, work / "shapes.html")
    # the failing graphs and the dangling subprocess link are edited in after the build so the build-time check never sees them
    html = built.read_text(encoding="utf-8")
    oval = '{"id": "odd", "label": "Odd", "shape": "box"}'
    lone = '{"id": "lone", "label": "Lone?", "shape": "box"}'
    assert oval in html and lone in html
    html = html.replace(oval, '{"id": "odd", "label": "Odd", "shape": "oval"}')
    html = html.replace(lone, '{"id": "lone", "label": "Lone?", "shape": "decision"}')
    lost = '{"id": "lost", "label": "Lost", "shape": "subprocess", "flow": "refund-flow"}'
    assert lost in html
    html = html.replace(lost, '{"id": "lost", "label": "Lost", "shape": "subprocess", "flow": "nowhere"}')
    for node_id, escape in (("nel", "\\u0085"), ("us", "\\u001f")):
        wired = f'{{"id": "{node_id}", "label": "{node_id.capitalize()}", "shape": "subprocess", "flow": "refund-flow"}}'
        assert wired in html
        html = html.replace(wired, wired.replace("refund-flow", escape))
    built.write_text(html, encoding="utf-8")
    return built


@pytest.fixture(scope="module")
def flow_traces_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-flow-traces")
    src = work / "traces.src.html"
    src.write_text(HEADER + FLOW_TRACES, encoding="utf-8")
    built = _build(src, work / "traces.html")
    # the unknown via is edited in after the build so the build-time check never sees it
    html = built.read_text(encoding="utf-8")
    good = '"via": "ab"'
    assert html.count(good) == 1
    html = html.replace(good, '"via": "tax-eu"')
    for name, (before, after) in BADVALUE_CASES.items():
        marker = '"value": ' + before.replace("BADVALUE", f"BAD_{name}")
        assert html.count(marker) == 1, name
        html = html.replace(marker, f'"value": {after}')
    for name, after in BADTEXT_CASES.items():
        marker = f'"BADTEXT_{name}"'
        assert html.count(marker) == 1, name
        html = html.replace(marker, after)
    built.write_text(html, encoding="utf-8")
    return built


FLOW_GEOMETRY_JS = """
  const num = (s) => (s.match(/-?\\d+(?:\\.\\d+)?(?:e-?\\d+)?/g) || []).map(Number);
  const pathPoints = (d) => { const n = num(d); const out = []; for (let i = 0; i + 1 < n.length; i += 2) out.push({ x: n[i], y: n[i + 1] }); return out; };
  const box = (f, id) => f.querySelector('[data-q-flow-node="' + id + '"] [data-q-flow-box]').getBBox();
  const centreX = (b) => b.x + b.width / 2;
  const onRectEdge = (p, b, tol) => {
    const inX = p.x >= b.x - tol && p.x <= b.x + b.width + tol;
    const inY = p.y >= b.y - tol && p.y <= b.y + b.height + tol;
    const onVert = Math.abs(p.x - b.x) <= tol || Math.abs(p.x - (b.x + b.width)) <= tol;
    const onHorz = Math.abs(p.y - b.y) <= tol || Math.abs(p.y - (b.y + b.height)) <= tol;
    return inX && inY && (onVert || onHorz);
  };
  const edgeOf = (f, from, to) => f.querySelector('[data-q-flow-edge][data-q-flow-from="' + from + '"][data-q-flow-to="' + to + '"]');
"""


def test_flow_decision_draws_a_diamond_with_kind_outline_labelled_exits_and_a_left_to_right_chain(
    flow_shapes_page: Path,
) -> None:
    out = run(
        flow_shapes_page,
        ev(
            f"""(() => {{
              {FLOW_GEOMETRY_JS}
              const f = document.querySelector('#flow-checkout');
              const node = f.querySelector('[data-q-flow-node="paid"]');
              const poly = node.querySelector('[data-q-flow-box]');
              const b = poly.getBBox();
              const a = b.width / 2, h = b.height / 2, cx = b.x + a, cy = b.y + h;
              const startOfYes = pathPoints(edgeOf(f, 'paid', 'ship').querySelector('[data-q-flow-edge-line]').getAttribute('d'))[0];
              const onOutline = Math.abs(Math.abs(startOfYes.x - cx) / a + Math.abs(startOfYes.y - cy) / h - 1) * Math.min(a, h);
              const labels = [...f.querySelectorAll('[data-q-flow-edge-label] text')].map((t) => t.textContent);
              return {{
                ready: f.getAttribute('data-q-flow-ready'),
                shapeAttr: node.getAttribute('data-q-flow-shape'),
                tag: poly.tagName.toLowerCase(),
                pointCount: poly.getAttribute('points').trim().split(/\\s+/).length,
                stroke: poly.getAttribute('stroke'),
                stripe: node.querySelectorAll('[data-q-flow-stripe]').length,
                kindTag: node.querySelectorAll('[data-q-flow-kind-label]').length,
                label: node.querySelector('[data-q-flow-label]').textContent,
                aria: node.getAttribute('aria-label'),
                boxShape: f.querySelector('[data-q-flow-node="ship"]').getAttribute('data-q-flow-shape'),
                yes: labels.includes('Yes'),
                no: labels.includes('No'),
                xs: ['checkout', 'charge', 'paid', 'ship'].map((id) => centreX(box(f, id))),
                outlineDistance: onOutline,
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert d["shapeAttr"] == "decision"
    assert d["boxShape"] == "box"
    assert d["tag"] == "polygon"
    assert d["pointCount"] == 4
    assert d["stroke"] == "var(--q-color-chart-2)"
    assert d["stripe"] == 0
    assert d["kindTag"] == 0
    assert d["label"] == "Paid?"
    assert "decision" in d["aria"]
    assert d["yes"] is True and d["no"] is True
    assert d["xs"] == sorted(d["xs"]) and len(set(d["xs"])) == 4
    assert d["outlineDistance"] < 1.5


def test_flow_loop_edge_runs_from_to_with_return_marker_and_prefixed_label(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        ev(
            f"""(() => {{
              {FLOW_GEOMETRY_JS}
              const f = document.querySelector('#flow-checkout');
              const g = edgeOf(f, 'retry_q', 'charge');
              const base = g.querySelector('[data-q-flow-edge-line]');
              const pts = pathPoints(base.getAttribute('d'));
              const fwd = edgeOf(f, 'charge', 'paid');
              return {{
                loopAttr: g.hasAttribute('data-q-flow-loop'),
                forwardLoopAttr: fwd.hasAttribute('data-q-flow-loop'),
                startOnRetry: onRectEdge(pts[0], box(f, 'retry_q'), 1.5),
                endOnCharge: onRectEdge(pts[pts.length - 1], box(f, 'charge'), 1.5),
                markerStart: base.getAttribute('marker-start'),
                markerEnd: base.getAttribute('marker-end'),
                forwardMarkerStart: fwd.querySelector('[data-q-flow-edge-line]').getAttribute('marker-start'),
                label: g.querySelector('[data-q-flow-edge-label] text').textContent,
                markerIds: [...f.querySelectorAll('marker')].map((m) => m.id),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["loopAttr"] is True
    assert d["forwardLoopAttr"] is False
    assert d["startOnRetry"] is True
    assert d["endOnCharge"] is True
    assert d["markerStart"].startswith("url(#q-flow-return-")
    assert d["markerEnd"].startswith("url(#q-flow-arrow-")
    assert d["forwardMarkerStart"] is None
    assert d["label"].startswith("↩ ") and d["label"].endswith("retry up to 3x")
    assert any(i.startswith("q-flow-return-lit-") for i in d["markerIds"])


def test_flow_self_loop_draws_an_arc_above_the_node_with_its_label(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        ev(
            f"""(() => {{
              {FLOW_GEOMETRY_JS}
              const f = document.querySelector('#flow-poller');
              const g = edgeOf(f, 'poller', 'poller');
              const pts = pathPoints(g.querySelector('[data-q-flow-edge-line]').getAttribute('d'));
              const b = box(f, 'poller');
              return {{
                ready: f.getAttribute('data-q-flow-ready'),
                loopAttr: g.hasAttribute('data-q-flow-loop'),
                pointCount: pts.length,
                minY: Math.min(...pts.map((p) => p.y)),
                nodeTop: b.y,
                label: g.querySelector('[data-q-flow-edge-label] text').textContent,
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert d["loopAttr"] is True
    assert d["pointCount"] > 2
    assert d["minY"] < d["nodeTop"]
    assert d["label"] == "↩ every 30s"


def test_flow_subprocess_draws_double_rules_and_keeps_stripe_and_kind_tag(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        ev(
            f"""(() => {{
              {FLOW_GEOMETRY_JS}
              const f = document.querySelector('#flow-checkout');
              const node = f.querySelector('[data-q-flow-node="refund"]');
              const b = box(f, 'refund');
              const plain = box(f, 'ship');
              const rules = [...node.querySelectorAll('line[data-q-flow-subprocess-rule]')].map((l) => ({{
                x1: +l.getAttribute('x1'), x2: +l.getAttribute('x2'), y1: +l.getAttribute('y1'), y2: +l.getAttribute('y2'),
              }}));
              const texts = [...node.querySelectorAll('text')].map((t) => +t.getAttribute('x'));
              return {{
                shapeAttr: node.getAttribute('data-q-flow-shape'),
                rules, boxX: b.x, boxY: b.y, boxW: b.width, boxH: b.height,
                stripe: node.querySelectorAll('[data-q-flow-stripe]').length,
                kindTag: node.querySelector('[data-q-flow-kind-label]').textContent,
                texts,
                widerThanPlain: b.width >= plain.width + 16,
                aria: node.getAttribute('aria-label'),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["shapeAttr"] == "subprocess"
    assert len(d["rules"]) == 2
    for r in d["rules"]:
        assert r["x1"] == r["x2"]
        assert abs(r["y1"] - d["boxY"]) < 0.5 and abs(r["y2"] - (d["boxY"] + d["boxH"])) < 0.5
    xs = sorted(r["x1"] for r in d["rules"])
    assert xs[0] == pytest.approx(d["boxX"] + 8) and xs[1] == pytest.approx(d["boxX"] + d["boxW"] - 8)
    assert d["stripe"] == 1
    assert d["kindTag"] == "WORKER"
    assert all(x > xs[0] for x in d["texts"])
    assert d["widerThanPlain"] is True
    assert "subprocess" in d["aria"]


def test_flow_list_reads_decisions_loops_self_loops_and_subprocess_links(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        ev(
            """(() => {
              const text = (id, sel) => document.querySelector('#' + id + ' details[data-q-flow-list]').textContent;
              const checkout = document.querySelector('#flow-checkout details[data-q-flow-list]');
              const link = checkout.querySelector('a[href="#refund-flow"]');
              const paid = checkout.querySelector('[data-q-flow-list-node="paid"]');
              return {
                checkout: checkout.textContent,
                poller: text('flow-poller'),
                linkText: link && link.textContent,
                paidNested: paid.querySelectorAll('ul').length,
                refundEntry: checkout.querySelector('[data-q-flow-list-node="refund"]').textContent,
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert "Paid? (decision, worker): Yes → Ship, No → Retry queue" in d["checkout"]
    assert "↩ returns to Charge worker: retry up to 3x" in d["checkout"]
    assert "→ Issue refund (on return)" in d["checkout"]
    assert "↩ returns to itself: every 30s" in d["poller"]
    assert d["linkText"] == 'opens the "refund-flow" graph'
    assert d["paidNested"] == 0
    assert d["refundEntry"] == 'Issue refund (subprocess, worker): opens the "refund-flow" graph'


def test_flow_unknown_shape_and_decision_with_one_exit_fail_to_the_notice(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        ev(
            """(() => ['flow-bad-oval', 'flow-bad-exit'].map((id) => {
              const f = document.querySelector('#' + id);
              return {
                ready: f.getAttribute('data-q-flow-ready'),
                notice: !!f.querySelector('[data-q-flow-notice]'),
                svg: !!f.querySelector('[data-q-flow-svg]'),
              };
            }))()""",
            "d",
        ),
    )
    assert_clean(out)
    for state in out["results"]["d"]:
        assert state == {"ready": "error", "notice": True, "svg": False}


def test_flow_blank_subprocess_flow_follows_python_strip(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        ev(
            """(() => ['flow-bom-link', 'flow-blank-nel', 'flow-blank-us'].map((id) => {
              const f = document.querySelector('#' + id);
              return { id, ready: f.getAttribute('data-q-flow-ready') };
            }))()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == [
        {"id": "flow-bom-link", "ready": "true"},
        {"id": "flow-blank-nel", "ready": "error"},
        {"id": "flow-blank-us", "ready": "error"},
    ]


def test_flow_focus_follows_forward_edges_only_and_lights_a_loop_between_lit_ends(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        {"click": '#flow-checkout [data-q-flow-node="ship"]'},
        ev(
            f"""(() => {{
              {FLOW_GEOMETRY_JS}
              const f = document.querySelector('#flow-checkout');
              const ids = (attr) => [...f.querySelectorAll('[data-q-flow-node][' + attr + ']')].map((n) => n.getAttribute('data-q-flow-node')).sort();
              const loop = edgeOf(f, 'retry_q', 'charge');
              return {{
                lit: ids('data-q-flow-lit'),
                dim: ids('data-q-flow-dim'),
                noEdgeDim: edgeOf(f, 'paid', 'retry_q').hasAttribute('data-q-flow-dim'),
                loopDim: loop.hasAttribute('data-q-flow-dim'),
                loopLit: loop.hasAttribute('data-q-flow-lit'),
                loopMarker: loop.querySelector('[data-q-flow-edge-line]').getAttribute('marker-start'),
              }};
            }})()""",
            "ship",
        ),
        {"click": '#flow-checkout [data-q-flow-node="charge"]'},
        ev(
            f"""(() => {{
              {FLOW_GEOMETRY_JS}
              const f = document.querySelector('#flow-checkout');
              const loop = edgeOf(f, 'retry_q', 'charge');
              const line = loop.querySelector('[data-q-flow-edge-line]');
              return {{
                dimNodes: f.querySelectorAll('[data-q-flow-node][data-q-flow-dim]').length,
                litNodes: f.querySelectorAll('[data-q-flow-node][data-q-flow-lit]').length,
                loopLit: loop.hasAttribute('data-q-flow-lit'),
                loopHop: loop.hasAttribute('data-q-flow-hop'),
                stroke: line.getAttribute('stroke'),
                markerStart: line.getAttribute('marker-start'),
                markerEnd: line.getAttribute('marker-end'),
                forwardHop: edgeOf(f, 'charge', 'paid').hasAttribute('data-q-flow-hop'),
              }};
            }})()""",
            "charge",
        ),
        {"click": '#flow-checkout [data-q-flow-node="ship"]'},
        ev(
            f"""(() => {{
              {FLOW_GEOMETRY_JS}
              const f = document.querySelector('#flow-checkout');
              const line = edgeOf(f, 'retry_q', 'charge').querySelector('[data-q-flow-edge-line]');
              return {{ markerStart: line.getAttribute('marker-start'), stroke: line.getAttribute('stroke') }};
            }})()""",
            "back",
        ),
        {"press": "Escape"},
        ev(
            f"""(() => {{
              {FLOW_GEOMETRY_JS}
              const f = document.querySelector('#flow-checkout');
              const loop = edgeOf(f, 'retry_q', 'charge');
              const line = loop.querySelector('[data-q-flow-edge-line]');
              return {{
                markerStart: line.getAttribute('marker-start'),
                flags: ['data-q-flow-lit', 'data-q-flow-dim', 'data-q-flow-hop'].map((a) => loop.hasAttribute(a)),
              }};
            }})()""",
            "cleared",
        ),
    )
    assert_clean(out)
    ship = out["results"]["ship"]
    assert ship["lit"] == ["charge", "checkout", "paid", "refund", "ship"]
    assert ship["dim"] == ["retry_q"]
    assert ship["noEdgeDim"] is True
    assert ship["loopDim"] is True and ship["loopLit"] is False
    assert ship["loopMarker"].startswith("url(#q-flow-return-") and "-lit-" not in ship["loopMarker"]
    charge = out["results"]["charge"]
    assert charge["dimNodes"] == 0 and charge["litNodes"] == 6
    assert charge["loopLit"] is True
    assert charge["loopHop"] is False
    assert charge["stroke"] == "var(--q-color-accent)"
    assert charge["markerStart"].startswith("url(#q-flow-return-lit-")
    assert charge["markerEnd"].startswith("url(#q-flow-arrow-lit-")
    assert charge["forwardHop"] is True
    back = out["results"]["back"]
    assert back["markerStart"].startswith("url(#q-flow-return-") and "-lit-" not in back["markerStart"]
    assert back["stroke"] == "var(--q-color-text-muted)"
    cleared = out["results"]["cleared"]
    assert cleared["markerStart"].startswith("url(#q-flow-return-") and "-lit-" not in cleared["markerStart"]
    assert cleared["flags"] == [False, False, False]


FLOW_LOOP_DOTS_JS = """
  window.__loopDots = (f, from, to) => {
    const g = f.querySelector(`[data-q-flow-edge][data-q-flow-from="${from}"][data-q-flow-to="${to}"]`);
    const pulse = g.querySelector('[data-q-flow-edge-pulse]');
    const maskId = pulse.getAttribute('mask').slice(5, -1);
    const start = g.querySelector('[data-q-flow-edge-line]').getPointAtLength(0);
    const visible = [...f.querySelector('#' + CSS.escape(maskId)).querySelectorAll('circle')]
      .filter((c) => !c.hasAttribute('data-q-inactive'))
      .filter((c) => Math.hypot(Number(c.getAttribute('cx')) - start.x, Number(c.getAttribute('cy')) - start.y) > 1).length;
    return { visible, pulseInactive: pulse.hasAttribute('data-q-inactive') };
  };
"""


def test_flow_loop_edges_never_pulse_while_forward_edges_do(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        ev(FLOW_FAKE_CLOCK, "clock"),
        ev(FLOW_LOOP_DOTS_JS + "true", "helpers"),
        {"click": '#flow-checkout [data-q-flow-node="charge"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-checkout');
              const loopSeen = [];
              let forwardSeen = 0;
              for (let t = 1100; t <= 4400; t += 100) {
                window.__tick(t);
                loopSeen.push(window.__loopDots(f, 'retry_q', 'charge'));
                forwardSeen += window.__loopDots(f, 'checkout', 'charge').visible;
              }
              return {
                steps: loopSeen.length,
                loopVisible: loopSeen.reduce((n, s) => n + s.visible, 0),
                loopInactive: loopSeen.every((s) => s.pulseInactive),
                forwardSeen,
                pulsing: f.hasAttribute('data-q-flow-pulsing'),
              };
            })()""",
            "checkout",
        ),
        {"click": '#flow-poller [data-q-flow-node="poller"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-poller');
              const selfSeen = [];
              let forwardSeen = 0;
              for (let t = 5000; t <= 8000; t += 100) {
                window.__tick(t);
                selfSeen.push(window.__loopDots(f, 'poller', 'poller'));
                forwardSeen += window.__loopDots(f, 'poller', 'done').visible;
              }
              return {
                selfVisible: selfSeen.reduce((n, s) => n + s.visible, 0),
                selfInactive: selfSeen.every((s) => s.pulseInactive),
                selfLit: f.querySelector('[data-q-flow-edge][data-q-flow-from="poller"][data-q-flow-to="poller"]').hasAttribute('data-q-flow-lit'),
                forwardSeen,
              };
            })()""",
            "poller",
        ),
    )
    assert_clean(out)
    checkout = out["results"]["checkout"]
    assert checkout["steps"] >= 30
    assert checkout["pulsing"] is True
    assert checkout["loopVisible"] == 0 and checkout["loopInactive"] is True
    assert checkout["forwardSeen"] > 0
    poller = out["results"]["poller"]
    assert poller["selfLit"] is True
    assert poller["selfVisible"] == 0 and poller["selfInactive"] is True
    assert poller["forwardSeen"] > 0


def test_flow_reduced_motion_lights_a_loop_edge_statically(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        {"emulate": {"reducedMotion": "reduce"}},
        {"click": '#flow-checkout [data-q-flow-node="charge"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-checkout');
              const g = f.querySelector('[data-q-flow-edge][data-q-flow-from="retry_q"][data-q-flow-to="charge"]');
              return {
                lit: g.hasAttribute('data-q-flow-lit'),
                width: g.querySelector('[data-q-flow-edge-line]').getAttribute('stroke-width'),
                pulseInactive: g.querySelector('[data-q-flow-edge-pulse]').hasAttribute('data-q-inactive'),
                pulsing: f.hasAttribute('data-q-flow-pulsing'),
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {"lit": True, "width": "3.5", "pulseInactive": True, "pulsing": False}


def test_flow_enter_on_a_decision_announces_its_shape(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        {"focus": '#flow-checkout [data-q-flow-node="paid"]'},
        {"press": "Enter"},
        ev("document.querySelector('#flow-checkout [aria-live=polite]').textContent", "live"),
    )
    assert_clean(out)
    assert out["results"]["live"].startswith("Paid?, decision, worker,")


FLOW_REFUND_IN_VIEW = """(() => {
  const r = document.querySelector('#refund-flow').getBoundingClientRect();
  return r.top >= -2 && r.top < window.innerHeight - 40;
})()"""

FLOW_OPENED_STATE = """(() => {
  const target = document.querySelector('#refund-flow');
  const f = document.querySelector('#flow-checkout');
  const active = document.activeElement;
  return {
    top: target.getBoundingClientRect().top,
    selected: f.querySelector('[data-q-flow-node="refund"]').hasAttribute('data-q-flow-selected'),
    drawerOpen: !f.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
    expanded: f.hasAttribute('data-q-flow-expanded'),
    activeIsNode: !!active && active.hasAttribute('data-q-flow-node') && !!active.closest('#refund-flow'),
    targetDrawerClosed: target.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
  };
})()"""


def test_flow_subprocess_drawer_opens_the_linked_flow_and_focuses_its_node(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        ev("document.querySelector('#refund-flow').getBoundingClientRect().top > window.innerHeight", "offscreen"),
        {"click": '#flow-checkout [data-q-flow-node="refund"]'},
        ev(
            """(() => {
              const btn = document.querySelector('#flow-checkout [data-q-flow-drawer-flow] button');
              return {
                text: btn && btn.textContent,
                type: btn && btn.getAttribute('type'),
                attr: btn && btn.hasAttribute('data-q-flow-open-flow'),
                missing: document.querySelectorAll('#flow-checkout [data-q-flow-flow-missing]').length,
                sections: document.querySelectorAll('#flow-checkout [data-q-flow-drawer-flow]').length,
              };
            })()""",
            "drawer",
        ),
        {"click": "#flow-checkout [data-q-flow-open-flow]"},
        {"waitFor": FLOW_REFUND_IN_VIEW, "timeout": 8000},
        {"wait": 300},
        ev(FLOW_OPENED_STATE, "opened"),
    )
    assert_clean(out)
    assert out["results"]["offscreen"] is True
    assert out["results"]["drawer"] == {
        "text": "Open flow",
        "type": "button",
        "attr": True,
        "missing": 0,
        "sections": 1,
    }
    opened = out["results"]["opened"]
    assert -2 <= opened["top"] < 400, opened
    assert opened["selected"] is True and opened["drawerOpen"] is True
    assert opened["expanded"] is False
    assert opened["activeIsNode"] is True
    assert opened["targetDrawerClosed"] is True


def test_flow_open_flow_returns_an_expanded_graph_to_the_page_first(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        {"click": '#flow-checkout [data-q-flow-action="expand"]'},
        ev("document.querySelector('#flow-checkout').hasAttribute('data-q-flow-expanded')", "expanded"),
        {"click": '#flow-checkout [data-q-flow-node="refund"]'},
        {"click": "#flow-checkout [data-q-flow-open-flow]"},
        {"waitFor": FLOW_REFUND_IN_VIEW, "timeout": 8000},
        {"wait": 300},
        ev(FLOW_OPENED_STATE, "opened"),
    )
    assert_clean(out)
    assert out["results"]["expanded"] is True
    opened = out["results"]["opened"]
    assert opened["expanded"] is False
    assert opened["selected"] is True and opened["drawerOpen"] is True
    assert opened["activeIsNode"] is True


def test_flow_subprocess_link_to_a_missing_flow_reads_as_a_notice_without_a_button(
    flow_shapes_page: Path,
) -> None:
    out = run(
        flow_shapes_page,
        {"click": '#flow-links [data-q-flow-node="lost"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-links');
              const p = f.querySelector('p[data-q-flow-flow-missing]');
              return {
                text: p && p.textContent,
                buttons: f.querySelectorAll('[data-q-flow-open-flow]').length,
                sections: f.querySelectorAll('[data-q-flow-drawer-flow]').length,
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {
        "text": 'The linked flow "nowhere" isn\'t on this page.',
        "buttons": 0,
        "sections": 1,
    }


def test_flow_subprocess_without_a_flow_has_no_flow_section(flow_shapes_page: Path) -> None:
    out = run(
        flow_shapes_page,
        {"click": '#flow-links [data-q-flow-node="bare"]'},
        ev(
            """(() => {
              const f = document.querySelector('#flow-links');
              return {
                sections: f.querySelectorAll('[data-q-flow-drawer-flow]').length,
                drawerOpen: !f.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {"sections": 0, "drawerOpen": True}


# --- q-flow traces ----------------------------------------------------------------------------

FLOW_TRACE_HELPERS = """(() => {
  const f = document.querySelector('#renewal');
  const keyOf = (li) => {
    const k = li.querySelector(':scope > [data-q-flow-key], :scope > details > summary > [data-q-flow-key]');
    return k ? k.textContent.replace(/: $/, '') : null;
  };
  const tops = () => [...f.querySelectorAll('[data-q-flow-trace-value] > ul > li[data-q-flow-field]')];
  window.__tr = {
    f,
    node: (id) => f.querySelector('[data-q-flow-node="' + id + '"]'),
    edge: (from, to, label) => [...f.querySelectorAll('[data-q-flow-edge][data-q-flow-from="' + from + '"][data-q-flow-to="' + to + '"]')]
      .find((g) => label === undefined || (g.querySelector('[data-q-flow-edge-label] text') || { textContent: '' }).textContent.endsWith(label)),
    has: (el, attr) => el.hasAttribute(attr),
    keyOf,
    tops,
    top: (key) => tops().find((li) => keyOf(li) === key) || null,
    change: (key) => { const li = window.__tr.top(key); return li ? li.getAttribute('data-q-flow-change') : null; },
    changed: () => tops().filter((li) => li.getAttribute('data-q-flow-change') !== 'same').map(keyOf),
    counter: () => f.querySelector('[data-q-flow-trace-counter]').textContent,
    selected: () => [...f.querySelectorAll('[data-q-flow-node][data-q-flow-selected]')].map((n) => n.getAttribute('data-q-flow-node')),
    panelOpen: () => !f.querySelector('[data-q-flow-trace-panel]').hasAttribute('data-q-inactive'),
    drawerOpen: () => !f.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
  };
  return true;
})()"""

TRACE_BTN = '#renewal [data-q-flow-action="trace"]'
TRACE_NEXT = "#renewal [data-q-flow-trace-next]"
TRACE_PICKER = "#renewal [data-q-flow-trace-picker]"


def _trace_dot(n: int) -> str:
    return f'#renewal [data-q-flow-trace-dot="{n}"]'


def _pick_trace(label: str) -> dict:
    return {"select": {"selector": TRACE_PICKER, "label": label}}


def test_flow_trace_button_shows_only_with_traces_and_a_bad_via_fails_to_the_notice(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(
            """(() => {
              const plain = document.querySelector('#plain');
              const renewal = document.querySelector('#renewal');
              const btn = renewal.querySelector('[data-q-flow-action="trace"]');
              const bad = document.querySelector('#badvia');
              return {
                plainButton: plain.querySelector('[data-q-flow-action="trace"]') !== null,
                plainPanel: plain.querySelector('[data-q-flow-trace-panel]') !== null,
                plainReady: plain.getAttribute('data-q-flow-ready'),
                text: btn && btn.textContent,
                label: btn && btn.getAttribute('aria-label'),
                pressed: btn && btn.getAttribute('aria-pressed'),
                actions: [...renewal.querySelectorAll('[data-q-flow-controls] [data-q-flow-action]')].map((b) => b.getAttribute('data-q-flow-action')),
                panelClosed: renewal.querySelector('[data-q-flow-trace-panel]').hasAttribute('data-q-inactive'),
                tracing: renewal.hasAttribute('data-q-flow-tracing'),
                badNotice: bad.querySelector('[data-q-flow-notice]') !== null,
                badReady: bad.getAttribute('data-q-flow-ready'),
                badButton: bad.querySelector('[data-q-flow-action="trace"]') !== null,
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {
        "plainButton": False,
        "plainPanel": False,
        "plainReady": "true",
        "text": "Step through",
        "label": "Step through a trace",
        "pressed": "false",
        "actions": ["zoom-in", "zoom-out", "fit", "trace", "expand"],
        "panelClosed": True,
        "tracing": False,
        "badNotice": True,
        "badReady": "error",
        "badButton": False,
    }


def test_flow_trace_opens_on_step_one_clearing_focus_and_dimming_off_the_path(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": '#renewal [data-q-flow-node="pricing"]'},
        ev("window.__tr.drawerOpen()", "drawerBefore"),
        {"click": TRACE_BTN},
        ev(
            """(() => {
              const t = window.__tr;
              const f = t.f;
              const panel = f.querySelector('[data-q-flow-trace-panel]');
              const tree = f.querySelector('[data-q-flow-trace-value] [data-q-flow-tree]');
              const fields = [...f.querySelectorAll('[data-q-flow-trace-value] [data-q-flow-field]')];
              return {
                drawerOpen: t.drawerOpen(),
                panelOpen: t.panelOpen(),
                panelWidth: panel.getBoundingClientRect().width,
                picker: f.querySelector('[data-q-flow-trace-picker]').value,
                options: [...f.querySelectorAll('[data-q-flow-trace-picker] option')].map((o) => [o.value, o.textContent]),
                counter: t.counter(),
                selected: t.selected(),
                dimNodes: [...f.querySelectorAll('[data-q-flow-node][data-q-flow-dim]')].map((n) => n.getAttribute('data-q-flow-node')),
                dimmedEdges: [t.edge('paid', 'retry'), t.edge('retry', 'charge'), t.edge('pricing', 'tax', 'cross-border quote')].map((g) => g.hasAttribute('data-q-flow-dim')),
                litEdges: f.querySelectorAll('[data-q-flow-edge][data-q-flow-lit]').length,
                pulsing: f.hasAttribute('data-q-flow-pulsing'),
                changes: [...new Set(fields.map((li) => li.getAttribute('data-q-flow-change')))],
                treeBranches: tree !== null,
                tracing: f.hasAttribute('data-q-flow-tracing'),
                pressed: f.querySelector('[data-q-flow-action="trace"]').getAttribute('aria-pressed'),
                activeIsNext: document.activeElement === f.querySelector('[data-q-flow-trace-next]'),
                backDisabled: f.querySelector('[data-q-flow-trace-back]').disabled,
                nextDisabled: f.querySelector('[data-q-flow-trace-next]').disabled,
                dots: f.querySelectorAll('[data-q-flow-trace-dot]').length,
                current: [...f.querySelectorAll('[data-q-flow-trace-dot][aria-current="step"]')].map((b) => b.getAttribute('data-q-flow-trace-dot')),
                playText: f.querySelector('[data-q-flow-trace-play]').textContent,
                live: f.querySelector('[data-q-flow-trace-counter]').getAttribute('aria-live'),
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["drawerBefore"] is True
    d = out["results"]["d"]
    assert d["drawerOpen"] is False
    assert d["panelOpen"] is True and d["panelWidth"] > 100
    assert d["picker"] == "succeeds"
    assert d["options"] == [["succeeds", "Card succeeds"], ["declined", "Card declined, retried"], ["deep", "Nested customer"]]
    assert d["counter"].startswith("Step 1 of 6")
    assert d["selected"] == ["scheduler"]
    assert d["dimNodes"] == ["retry"]
    assert d["dimmedEdges"] == [True, True, True]
    assert d["litEdges"] == 0
    assert d["pulsing"] is False
    assert d["changes"] == ["same"] and d["treeBranches"] is True
    assert d["tracing"] is True and d["pressed"] == "true"
    assert d["activeIsNext"] is True
    assert d["backDisabled"] is True and d["nextDisabled"] is False
    assert d["dots"] == 6 and d["current"] == ["1"]
    assert d["playText"] == "Play" and d["live"] == "polite"


def test_flow_trace_counter_announces_the_node_and_note_in_a_hidden_span(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        {"click": TRACE_NEXT},
        ev(
            """(() => {
              const c = window.__tr.f.querySelector('[data-q-flow-trace-counter]');
              const hidden = c.querySelector('.q-visually-hidden');
              const note = window.__tr.f.querySelector('[data-q-flow-trace-note]');
              const dot = window.__tr.f.querySelector('[data-q-flow-trace-dot="2"]');
              return {
                text: c.textContent,
                hidden: hidden && hidden.textContent,
                note: note.textContent,
                noteHidden: note.hasAttribute('data-q-inactive'),
                dotLabel: dot.getAttribute('aria-label'),
              };
            })()""",
            "d",
        ),
        {"click": _trace_dot(1)},
        ev(
            """(() => {
              const note = window.__tr.f.querySelector('[data-q-flow-trace-note]');
              return { note: note.textContent, noteHidden: note.hasAttribute('data-q-inactive'), counter: window.__tr.counter() };
            })()""",
            "first",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {
        "text": "Step 2 of 6, Pricing: Pricing applies the loyalty discount",
        "hidden": ", Pricing: Pricing applies the loyalty discount",
        "note": "Pricing applies the loyalty discount",
        "noteHidden": False,
        "dotLabel": "Step 2: Pricing",
    }
    assert out["results"]["first"] == {"note": "", "noteHidden": True, "counter": "Step 1 of 6, Renewal scheduler"}


def test_flow_trace_next_lights_the_edge_the_step_names_and_marks_added_and_changed_fields(
    flow_traces_page: Path,
) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        {"click": TRACE_NEXT},
        {"click": TRACE_NEXT},
        ev(
            """(() => {
              const t = window.__tr;
              const total = t.top('total');
              return {
                selected: t.selected(),
                domestic: [t.has(t.edge('pricing', 'tax', 'domestic quote'), 'data-q-flow-lit'), t.has(t.edge('pricing', 'tax', 'domestic quote'), 'data-q-flow-dim')],
                intl: [t.has(t.edge('pricing', 'tax', 'cross-border quote'), 'data-q-flow-lit'), t.has(t.edge('pricing', 'tax', 'cross-border quote'), 'data-q-flow-dim')],
                litEdges: [...t.f.querySelectorAll('[data-q-flow-edge][data-q-flow-lit]')].length,
                pricingNode: ['data-q-flow-lit', 'data-q-flow-dim', 'data-q-flow-selected'].map((a) => t.node('pricing').hasAttribute(a)),
                tax: t.change('tax'),
                total: t.change('total'),
                old: total.querySelector('[data-q-flow-old]').textContent,
                neu: total.querySelector('[data-q-flow-new]').textContent,
                subtotal: t.change('subtotal'),
                pulsing: t.f.hasAttribute('data-q-flow-pulsing'),
                counter: t.counter(),
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["selected"] == ["tax"]
    assert d["domestic"] == [True, False]
    assert d["intl"] == [False, True]
    assert d["litEdges"] == 1
    assert d["pricingNode"] == [False, False, False]
    assert d["tax"] == "added" and d["total"] == "changed"
    assert d["old"] == "32.4" and d["neu"] == "35.07"
    assert d["subtotal"] == "same"
    assert d["pulsing"] is True
    assert d["counter"].startswith("Step 3 of 6")


def test_flow_trace_loop_edge_is_the_current_edge_and_pulses_while_removed_fields_show_for_one_step(
    flow_traces_page: Path,
) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_FAKE_CLOCK, "clock"),
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        _pick_trace("Card declined, retried"),
        {"click": _trace_dot(5)},
        ev("window.__tr.changed()", "step5"),
        {"click": _trace_dot(7)},
        ev(
            """(() => {
              const t = window.__tr;
              const loop = t.edge('retry', 'charge');
              window.__tick(1300);
              const arcs = window.__arcs(t.f, 'retry', 'charge');
              const line = loop.querySelector('[data-q-flow-edge-line]');
              return {
                loopLit: loop.hasAttribute('data-q-flow-lit'),
                loopDim: loop.hasAttribute('data-q-flow-dim'),
                dots: arcs.arcs.length,
                width: line.getAttribute('stroke-width'),
                markerStart: line.getAttribute('marker-start'),
                pulsing: t.f.hasAttribute('data-q-flow-pulsing'),
                pulseVisible: !loop.querySelector('[data-q-flow-edge-pulse]').hasAttribute('data-q-inactive'),
                otherPulses: [...t.f.querySelectorAll('[data-q-flow-edge]')].filter((g) => g !== loop && !g.querySelector('[data-q-flow-edge-pulse]').hasAttribute('data-q-inactive')).length,
                decline: t.change('decline'),
                retryAt: t.change('retry_at'),
                strike: getComputedStyle(t.top('decline').querySelector('[data-q-flow-key]')).textDecorationLine,
                counter: t.counter(),
              };
            })()""",
            "step7",
        ),
        {"click": TRACE_NEXT},
        ev(
            """(() => {
              const t = window.__tr;
              return { keys: t.tops().map(t.keyOf), lit: [...t.f.querySelectorAll('[data-q-flow-edge][data-q-flow-lit]')].length };
            })()""",
            "step8",
        ),
    )
    assert_clean(out)
    assert out["results"]["step5"] == []
    s7 = out["results"]["step7"]
    assert s7["loopLit"] is True and s7["loopDim"] is False
    assert s7["dots"] >= 1, s7
    assert s7["width"] == "2"
    assert s7["markerStart"].startswith("url(#q-flow-return-lit-")
    assert s7["pulsing"] is True and s7["pulseVisible"] is True
    assert s7["otherPulses"] == 0
    assert s7["decline"] == "removed" and s7["retryAt"] == "removed"
    assert s7["strike"] == "line-through"
    assert s7["counter"].startswith("Step 7 of 9")
    s8 = out["results"]["step8"]
    assert "decline" not in s8["keys"] and "retry_at" not in s8["keys"]
    assert s8["lit"] == 1


def test_flow_trace_changes_only_hides_same_fields_and_persists_across_steps_and_traces(
    flow_traces_page: Path,
) -> None:
    visible = """(() => {
      const t = window.__tr;
      return t.tops().filter((li) => getComputedStyle(li).display !== 'none').map(t.keyOf);
    })()"""
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        _pick_trace("Card declined, retried"),
        {"click": _trace_dot(7)},
        ev("window.__tr.f.querySelector('[data-q-flow-trace-changes]').checked", "before"),
        {"click": "#renewal [data-q-flow-trace-changes]"},
        ev(visible, "step7"),
        {"click": TRACE_NEXT},
        ev(
            """(() => {
              const t = window.__tr;
              const empty = t.f.querySelector('[data-q-flow-trace-empty]');
              return {
                checked: t.f.querySelector('[data-q-flow-trace-changes]').checked,
                empty: empty && empty.textContent,
                fields: t.tops().length,
              };
            })()""",
            "step8",
        ),
        {"click": _trace_dot(9)},
        ev(
            """(() => {
              const t = window.__tr;
              const tree = t.f.querySelector('[data-q-flow-tree]');
              return {
                attr: tree.hasAttribute('data-q-flow-changes-only'),
                visible: t.tops().filter((li) => getComputedStyle(li).display !== 'none').map(t.keyOf),
                empty: t.f.querySelector('[data-q-flow-trace-empty]') !== null,
              };
            })()""",
            "step9",
        ),
        _pick_trace("Card succeeds"),
        ev("window.__tr.f.querySelector('[data-q-flow-trace-changes]').checked", "afterSwitch"),
        {"click": _trace_dot(3)},
        ev(visible, "succeedsStep3"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["before"] is False
    assert sorted(r["step7"]) == ["attempt", "charge", "decline", "retry_at", "status"]
    assert r["step8"] == {"checked": True, "empty": "No changes at this step", "fields": 0}
    assert r["step9"]["attr"] is True and r["step9"]["empty"] is False
    assert sorted(r["step9"]["visible"]) == ["settled_at", "status"]
    assert r["afterSwitch"] is True
    assert sorted(r["succeedsStep3"]) == ["tax", "total"]


def test_flow_trace_branches_below_the_third_level_start_closed_unless_they_hold_a_change(
    flow_traces_page: Path,
) -> None:
    geo = """(() => {
      const t = window.__tr;
      const branches = [...t.f.querySelectorAll('details[data-q-flow-branch]')];
      const by = (key) => branches.find((d) => d.querySelector(':scope > summary [data-q-flow-key]').textContent === key + ': ');
      const g = by('geo');
      return {
        geoOpen: g.open,
        geoDepth: g.closest('li').getAttribute('data-q-flow-depth'),
        geoCount: g.querySelector(':scope > summary').textContent,
        geoHasChange: g.closest('li').hasAttribute('data-q-flow-has-change'),
        customerOpen: by('customer').open,
        addressOpen: by('address').open,
        coordinatesOpen: by('coordinates').open,
      };
    })()"""
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        _pick_trace("Nested customer"),
        ev(geo, "step1"),
        {"click": TRACE_NEXT},
        ev(geo, "step2"),
        {"click": TRACE_NEXT},
        ev(geo, "step3"),
    )
    assert_clean(out)
    r = out["results"]
    for key in ("step1", "step2"):
        assert r[key]["geoOpen"] is False and r[key]["geoDepth"] == "3" and r[key]["geoHasChange"] is False
        assert r[key]["customerOpen"] is True and r[key]["addressOpen"] is True
        assert r[key]["geoCount"].replace(" ", " ").endswith("{2}")
    assert r["step3"]["geoOpen"] is True and r["step3"]["geoHasChange"] is True
    assert r["step3"]["coordinatesOpen"] is True


def test_flow_trace_diff_marks_array_growth_by_index_and_a_type_change_as_changed(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        _pick_trace("Nested customer"),
        {"click": TRACE_NEXT},
        ev(
            """(() => {
              const t = window.__tr;
              const tags = [...t.f.querySelectorAll('li[data-q-flow-field]')].find((li) => t.keyOf(li) === 'tags');
              const items = [...tags.querySelectorAll(':scope > details > ul > li[data-q-flow-field]')]
                .map((li) => [t.keyOf(li), li.getAttribute('data-q-flow-change'), li.querySelector('[data-q-flow-val]').textContent]);
              return { tags: tags.getAttribute('data-q-flow-change'), hasChange: tags.hasAttribute('data-q-flow-has-change'), items };
            })()""",
            "growth",
        ),
        {"click": TRACE_NEXT},
        ev(
            """(() => {
              const t = window.__tr;
              const contact = [...t.f.querySelectorAll('li[data-q-flow-field]')].find((li) => t.keyOf(li) === 'contact');
              return {
                change: contact.getAttribute('data-q-flow-change'),
                branch: contact.querySelector('details') !== null,
                old: contact.querySelector('[data-q-flow-old]').textContent,
                neu: contact.querySelector('[data-q-flow-new]').textContent,
              };
            })()""",
            "retyped",
        ),
    )
    assert_clean(out)
    assert out["results"]["growth"] == {
        "tags": "same",
        "hasChange": True,
        "items": [["0", "same", '"vip"'], ["1", "added", '"beta"']],
    }
    assert out["results"]["retyped"] == {
        "change": "changed",
        "branch": False,
        "old": '"ada@example.com"',
        "neu": '{"email":"ada@example.com","phone":"555-0100"}',
    }


def test_flow_trace_node_click_jumps_to_its_next_visit_and_dots_jump_to_a_step(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        _pick_trace("Card declined, retried"),
        {"click": TRACE_NEXT},
        ev("window.__tr.counter().slice(0, 9)", "start"),
        {"click": '#renewal [data-q-flow-node="charge"]'},
        ev("window.__tr.counter().slice(0, 9)", "first"),
        {"click": '#renewal [data-q-flow-node="charge"]'},
        ev("window.__tr.counter().slice(0, 9)", "second"),
        {"click": '#renewal [data-q-flow-node="charge"]'},
        ev("window.__tr.counter().slice(0, 9)", "wrap"),
        {"click": _trace_dot(1)},
        ev(
            """(() => ({
              counter: window.__tr.counter().slice(0, 9),
              tracing: window.__tr.f.hasAttribute('data-q-flow-tracing'),
              selected: window.__tr.selected(),
            }))()""",
            "dot",
        ),
    )
    assert_clean(out)
    r = out["results"]
    assert r["start"] == "Step 2 of"
    assert r["first"] == "Step 4 of"
    assert r["second"] == "Step 7 of"
    assert r["wrap"] == "Step 4 of"
    assert r["dot"] == {"counter": "Step 1 of", "tracing": True, "selected": ["scheduler"]}


def test_flow_trace_picker_resets_to_step_one_on_the_new_traces_path(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        _pick_trace("Card declined, retried"),
        {"click": _trace_dot(4)},
        ev("window.__tr.counter().slice(0, 11)", "before"),
        ev("window.__tr.node('retry').hasAttribute('data-q-flow-dim')", "retryBefore"),
        {"focus": TRACE_PICKER},
        _pick_trace("Card succeeds"),
        ev(
            """(() => ({
              counter: window.__tr.counter().slice(0, 11),
              retryDim: window.__tr.node('retry').hasAttribute('data-q-flow-dim'),
              loopDim: window.__tr.edge('retry', 'charge').hasAttribute('data-q-flow-dim'),
              dots: window.__tr.f.querySelectorAll('[data-q-flow-trace-dot]').length,
              picker: document.activeElement === window.__tr.f.querySelector('[data-q-flow-trace-picker]'),
              selected: window.__tr.selected(),
            }))()""",
            "after",
        ),
    )
    assert_clean(out)
    r = out["results"]
    assert r["before"] == "Step 4 of 9"
    assert r["retryBefore"] is False
    assert r["after"] == {
        "counter": "Step 1 of 6",
        "retryDim": True,
        "loopDim": True,
        "dots": 6,
        "picker": True,
        "selected": ["scheduler"],
    }


def test_flow_trace_off_path_click_leaves_empty_canvas_stays_and_the_button_toggles(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        {"click": '#renewal [data-q-flow-node="retry"]'},
        ev(
            """(() => {
              const t = window.__tr;
              return {
                tracing: t.f.hasAttribute('data-q-flow-tracing'),
                panelOpen: t.panelOpen(),
                drawerOpen: t.drawerOpen(),
                drawerTitle: t.f.querySelector('[data-q-flow-drawer] h3').textContent,
                selected: t.selected(),
                pressed: t.f.querySelector('[data-q-flow-action="trace"]').getAttribute('aria-pressed'),
              };
            })()""",
            "left",
        ),
        {"click": TRACE_BTN},
        ev(
            """(() => {
              const t = window.__tr;
              const svg = t.f.querySelector('[data-q-flow-svg]');
              svg.dispatchEvent(new MouseEvent('click', { bubbles: true }));
              return {
                tracing: t.f.hasAttribute('data-q-flow-tracing'),
                panelOpen: t.panelOpen(),
                selected: t.selected(),
                counter: t.counter().slice(0, 9),
              };
            })()""",
            "empty",
        ),
        {"click": TRACE_BTN},
        ev(
            """(() => {
              const t = window.__tr;
              return {
                tracing: t.f.hasAttribute('data-q-flow-tracing'),
                panelOpen: t.panelOpen(),
                pressed: t.f.querySelector('[data-q-flow-action="trace"]').getAttribute('aria-pressed'),
                active: document.activeElement === t.f.querySelector('[data-q-flow-action="trace"]'),
                dimmed: t.f.querySelectorAll('[data-q-flow-dim]').length,
                lit: t.f.querySelectorAll('[data-q-flow-lit]').length,
                pulsing: t.f.hasAttribute('data-q-flow-pulsing'),
              };
            })()""",
            "closed",
        ),
        {"click": '#renewal [data-q-flow-node="pricing"]'},
        ev("window.__tr.drawerOpen() && window.__tr.selected().join()", "focusAfter"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["left"] == {
        "tracing": False,
        "panelOpen": False,
        "drawerOpen": True,
        "drawerTitle": "Retry queue",
        "selected": ["retry"],
        "pressed": "false",
    }
    assert r["empty"] == {"tracing": True, "panelOpen": True, "selected": ["scheduler"], "counter": "Step 1 of"}
    assert r["closed"] == {
        "tracing": False,
        "panelOpen": False,
        "pressed": "false",
        "active": True,
        "dimmed": 0,
        "lit": 0,
        "pulsing": False,
    }
    assert r["focusAfter"] == "pricing"


def test_flow_trace_list_carries_each_trace_with_the_same_text_as_the_builder(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(
            """(() => {
              const f = document.querySelector('#renewal');
              const body = f.querySelector('[data-q-flow-list-body]');
              const step = (trace, n) => {
                const li = f.querySelector('[data-q-flow-list-trace="' + trace + '"] [data-q-flow-list-step="' + n + '"]');
                return { text: li.firstChild.textContent, code: li.querySelector(':scope > pre > code').textContent, full: li.textContent };
              };
              const blocks = [...body.querySelectorAll(':scope > [data-q-flow-list-trace]')];
              return {
                order: [...body.children].map((c) => c.tagName.toLowerCase() + ':' + (c.getAttribute('data-q-flow-list-trace') || '')),
                titles: blocks.map((b) => b.querySelector(':scope > p > strong').textContent),
                counts: blocks.map((b) => b.querySelectorAll(':scope > ol > li').length),
                declined3: step('declined', 3),
                declined7: step('declined', 7),
                succeeds5: step('succeeds', 5),
                succeeds1: step('succeeds', 1),
                plain: document.querySelectorAll('#plain [data-q-flow-list-trace]').length,
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    pretty = lambda value: json.dumps(value, indent=2, ensure_ascii=False)  # noqa: E731
    assert d["order"] == ["ul:", "div:succeeds", "div:declined", "div:deep"]
    assert d["titles"] == ["Trace: Card succeeds", "Trace: Card declined, retried", "Trace: Nested customer"]
    assert d["counts"] == [6, 9, 3]
    assert d["declined3"]["text"] == 'Tax, via "domestic quote": Tax adds 8.25% sales tax'
    assert d["declined3"]["code"] == pretty(_TRACE_V3)
    assert d["declined3"]["full"] == d["declined3"]["text"] + pretty(_TRACE_V3)
    assert d["declined7"]["text"] == 'Charge worker, via "retry up to 3x": The second attempt succeeds'
    assert d["declined7"]["code"] == pretty(_TRACE_V7)
    assert d["succeeds5"]["text"] == "Paid?: Paid? answers Yes"
    assert d["succeeds1"]["text"] == "Renewal scheduler"
    assert d["succeeds1"]["code"] == pretty(_TRACE_V1)
    assert d["plain"] == 0


TRACE_PLAY = "#renewal [data-q-flow-trace-play]"

FLOW_TRACE_PLAY_STATE = """(() => {
  const f = window.__tr.f;
  const play = f.querySelector('[data-q-flow-trace-play]');
  return {
    step: window.__tr.counter().match(/^Step \\d+ of \\d+/)[0],
    play: play.textContent,
    pressed: play.getAttribute('aria-pressed'),
    nextDisabled: f.querySelector('[data-q-flow-trace-next]').disabled,
  };
})()"""


def _trace_tick(t: int, name: str) -> dict:
    return ev(f"(() => {{ window.__tick({t}); return {FLOW_TRACE_PLAY_STATE}; }})()", name)


def test_flow_trace_play_advances_every_1500ms_stops_on_the_last_step_and_restarts_from_one(
    flow_traces_page: Path,
) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_FAKE_CLOCK, "clock"),
        ev(FLOW_TRACE_HELPERS, "h"),
        ev("window.__tr.counter()", "idle"),
        {"click": TRACE_BTN},
        ev("(() => { window.__tick(1000); return window.__tr.counter().slice(0, 11); })()", "noAutoStart"),
        {"click": TRACE_PLAY},
        ev(FLOW_TRACE_PLAY_STATE, "started"),
        _trace_tick(2499, "t1499"),
        _trace_tick(2501, "t1501"),
        _trace_tick(4000, "t4000"),
        _trace_tick(4001, "t4001"),
        _trace_tick(5600, "t5600"),
        _trace_tick(7200, "t7200"),
        _trace_tick(8800, "t8800"),
        _trace_tick(20000, "later"),
        {"click": TRACE_PLAY},
        ev(FLOW_TRACE_PLAY_STATE, "restarted"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["noAutoStart"] == "Step 1 of 6"
    playing = {"play": "Pause", "pressed": "true", "nextDisabled": False}
    assert r["started"] == {"step": "Step 1 of 6", **playing}
    assert r["t1499"] == {"step": "Step 1 of 6", **playing}
    assert r["t1501"] == {"step": "Step 2 of 6", **playing}
    assert r["t4000"]["step"] == "Step 2 of 6"
    assert r["t4001"]["step"] == "Step 3 of 6"
    assert r["t5600"]["step"] == "Step 4 of 6"
    assert r["t7200"]["step"] == "Step 5 of 6"
    stopped = {"step": "Step 6 of 6", "play": "Play", "pressed": "false", "nextDisabled": True}
    assert r["t8800"] == stopped
    assert r["later"] == stopped
    assert r["restarted"] == {"step": "Step 1 of 6", **playing}


def test_flow_trace_play_stops_on_any_manual_step_dot_picker_node_click_close_and_relayout(
    flow_traces_page: Path,
) -> None:
    def started(name: str) -> list[dict]:
        return [
            {"click": TRACE_PLAY},
            ev("window.__tr.f.querySelector('[data-q-flow-trace-play]').textContent", name),
        ]

    def after(t: int, name: str) -> dict:
        return ev(
            f"""(() => {{
              window.__tick({t});
              const f = window.__tr.f;
              return {{
                step: window.__tr.counter().match(/^Step \\d+ of \\d+/)[0],
                play: f.querySelector('[data-q-flow-trace-play]').textContent,
                pressed: f.querySelector('[data-q-flow-trace-play]').getAttribute('aria-pressed'),
              }};
            }})()""",
            name,
        )

    out = run(
        flow_traces_page,
        ev(FLOW_FAKE_CLOCK, "clock"),
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        *started("p1"),
        {"click": TRACE_NEXT},
        after(10000, "next"),
        *started("p2"),
        {"click": '#renewal [data-q-flow-trace-back]'},
        after(20000, "back"),
        *started("p3"),
        {"click": _trace_dot(5)},
        after(30000, "dot"),
        *started("p4"),
        {"click": '#renewal [data-q-flow-node="tax"]'},
        after(40000, "node"),
        *started("p5"),
        _pick_trace("Card declined, retried"),
        after(50000, "picker"),
        *started("p6"),
        {"click": TRACE_BTN},
        after(60000, "closed"),
        {"click": TRACE_BTN},
        after(70000, "reopened"),
        *started("p7"),
        ev("window.__tr.f._setup()", "relayout"),
        {"wait": 300},
        ev(
            """(() => {
              const f = document.querySelector('#renewal');
              const play = f.querySelector('[data-q-flow-trace-play]');
              return { tracing: f.hasAttribute('data-q-flow-tracing'), play: play.textContent, pressed: play.getAttribute('aria-pressed') };
            })()""",
            "afterSetup",
        ),
    )
    assert_clean(out)
    r = out["results"]
    assert [r[f"p{n}"] for n in range(1, 8)] == ["Pause"] * 7
    assert r["next"] == {"step": "Step 2 of 6", "play": "Play", "pressed": "false"}
    assert r["back"] == {"step": "Step 1 of 6", "play": "Play", "pressed": "false"}
    assert r["dot"] == {"step": "Step 5 of 6", "play": "Play", "pressed": "false"}
    assert r["node"] == {"step": "Step 3 of 6", "play": "Play", "pressed": "false"}
    assert r["picker"] == {"step": "Step 1 of 9", "play": "Play", "pressed": "false"}
    assert r["closed"]["play"] == "Play" and r["reopened"]["play"] == "Play"
    assert r["reopened"]["step"] == "Step 1 of 9"
    assert r["afterSetup"] == {"tracing": False, "play": "Play", "pressed": "false"}


def test_flow_trace_play_stops_when_the_element_leaves_the_page(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_FAKE_CLOCK, "clock"),
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        {"click": TRACE_PLAY},
        ev(
            """(() => {
              const f = window.__tr.f;
              const counter = f.querySelector('[data-q-flow-trace-counter]');
              const host = f.parentNode;
              const next = f.nextSibling;
              f.remove();
              window.__tick(5000);
              window.__tick(9000);
              const frozen = counter.textContent.slice(0, 9);
              const play = f.querySelector('[data-q-flow-trace-play]').textContent;
              host.insertBefore(f, next);
              return { frozen, play };
            })()""",
            "gone",
        ),
    )
    assert_clean(out)
    assert out["results"]["gone"] == {"frozen": "Step 1 of", "play": "Play"}


def test_flow_trace_arrow_keys_step_from_the_panel_but_not_from_the_picker(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        {"press": "ArrowRight"},
        ev("window.__tr.counter().slice(0, 9)", "right"),
        {"press": "ArrowDown"},
        ev("window.__tr.counter().slice(0, 9)", "down"),
        {"press": "ArrowLeft"},
        ev("window.__tr.counter().slice(0, 9)", "left"),
        {"press": "ArrowUp"},
        ev("window.__tr.counter().slice(0, 9)", "up"),
        {"press": "ArrowUp"},
        ev("window.__tr.counter().slice(0, 9)", "floor"),
        _pick_trace("Card declined, retried"),
        {"click": TRACE_NEXT},
        ev("window.__tr.counter()", "declined2"),
        {"focus": TRACE_PICKER},
        {"press": "ArrowDown"},
        ev(
            """(() => ({
              counter: window.__tr.counter().slice(0, 9),
              picker: document.querySelector('#renewal [data-q-flow-trace-picker]').value,
            }))()""",
            "picker",
        ),
        {"focus": '#renewal [data-q-flow-node="charge"]'},
        {"press": "Enter"},
        ev("window.__tr.counter().slice(0, 9)", "enterOnNode"),
        {"press": "ArrowRight"},
        ev("document.activeElement.getAttribute('data-q-flow-node')", "nodeArrowKeepsFocusOnNodes"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["right"] == "Step 2 of"
    assert r["down"] == "Step 3 of"
    assert r["left"] == "Step 2 of"
    assert r["up"] == "Step 1 of"
    assert r["floor"] == "Step 1 of"
    assert r["declined2"].startswith("Step 2 of 9")
    assert r["declined2"].endswith(", Pricing: Pricing applies the loyalty discount")
    assert r["picker"]["counter"] != "Step 3 of"
    assert r["enterOnNode"] == "Step 4 of"
    assert r["nodeArrowKeepsFocusOnNodes"] is not None


def test_flow_trace_arrow_keys_step_once_after_the_graph_re_lays_out(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        ev("window.__tr.f.setAttribute('summary', 'Renewal flow, edited once.')", "edit1"),
        {"wait": 300},
        ev("window.__tr.f.setAttribute('summary', 'Renewal flow, edited twice.')", "edit2"),
        {"wait": 300},
        {"click": TRACE_BTN},
        ev(
            """(() => {
              window.__stepCalls = 0;
              const f = window.__tr.f;
              const real = f._traceStepBy;
              f._traceStepBy = function (d) { window.__stepCalls += 1; return real.call(this, d); };
              return document.activeElement === f.querySelector('[data-q-flow-trace-next]');
            })()""",
            "focusOnNext",
        ),
        {"press": "ArrowRight"},
        ev("({ counter: window.__tr.counter().slice(0, 9), calls: window.__stepCalls })", "right"),
        {"focus": TRACE_PICKER},
        ev("window.__stepCalls = 0", "reset"),
        {"press": "ArrowDown"},
        ev("window.__stepCalls", "pickerCalls"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["focusOnNext"] is True
    assert r["right"] == {"counter": "Step 2 of", "calls": 1}
    assert r["pickerCalls"] == 0


def test_flow_trace_escape_closes_trace_mode_first_and_returns_focus_to_the_button(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        {"press": "Escape"},
        ev(
            """(() => {
              const t = window.__tr;
              return {
                tracing: t.f.hasAttribute('data-q-flow-tracing'),
                panelOpen: t.panelOpen(),
                pressed: t.f.querySelector('[data-q-flow-action="trace"]').getAttribute('aria-pressed'),
                active: document.activeElement === t.f.querySelector('[data-q-flow-action="trace"]'),
                dim: t.f.querySelectorAll('[data-q-flow-dim]').length,
              };
            })()""",
            "closed",
        ),
        {"focus": '#renewal [data-q-flow-node="charge"]'},
        {"press": "Enter"},
        ev("({ drawerOpen: window.__tr.drawerOpen(), selected: window.__tr.selected() })", "focused"),
        {"press": "Escape"},
        ev("({ drawerOpen: window.__tr.drawerOpen(), selected: window.__tr.selected() })", "cleared"),
        {"click": '#renewal [data-q-flow-action="expand"]'},
        {"click": TRACE_BTN},
        {"press": "Escape"},
        ev(
            """(() => ({
              expanded: window.__tr.f.hasAttribute('data-q-flow-expanded'),
              tracing: window.__tr.f.hasAttribute('data-q-flow-tracing'),
            }))()""",
            "expandedTracing",
        ),
        {"press": "Escape"},
        ev("window.__tr.f.hasAttribute('data-q-flow-expanded')", "expandedAfter"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["closed"] == {"tracing": False, "panelOpen": False, "pressed": "false", "active": True, "dim": 0}
    assert r["focused"] == {"drawerOpen": True, "selected": ["charge"]}
    assert r["cleared"] == {"drawerOpen": False, "selected": []}
    assert r["expandedTracing"] == {"expanded": True, "tracing": False}
    assert r["expandedAfter"] is False


def test_flow_trace_escape_in_one_graph_closes_only_that_trace_and_never_moves_focus_into_another(
    flow_traces_page: Path,
) -> None:
    state = """(() => {
      const a = document.querySelector('#renewal');
      const b = document.querySelector('#wide');
      const btn = (f) => f.querySelector('[data-q-flow-action="trace"]');
      return {
        aTracing: a.hasAttribute('data-q-flow-tracing'),
        bTracing: b.hasAttribute('data-q-flow-tracing'),
        activeIsABtn: document.activeElement === btn(a),
        activeInB: b.contains(document.activeElement),
      };
    })()"""
    out = run(
        flow_traces_page,
        {"click": TRACE_BTN},
        {"click": '#wide [data-q-flow-action="trace"]'},
        ev(state, "both"),
        {"focus": TRACE_NEXT},
        {"press": "Escape"},
        ev(state, "afterA"),
        ev("document.activeElement.blur()", "blur"),
        {"press": "Escape"},
        ev(state, "afterBody"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["both"]["aTracing"] is True and r["both"]["bTracing"] is True
    assert r["afterA"] == {"aTracing": False, "bTracing": True, "activeIsABtn": True, "activeInB": False}
    assert r["afterBody"]["bTracing"] is False
    assert r["afterBody"]["activeInB"] is False


def test_flow_trace_reduced_motion_steps_and_plays_without_pulse_dots_and_with_a_thick_current_edge(
    flow_traces_page: Path,
) -> None:
    out = run(
        flow_traces_page,
        {"emulate": {"reducedMotion": "reduce"}},
        ev(FLOW_FAKE_CLOCK, "clock"),
        ev(FLOW_TRACE_HELPERS, "h"),
        {"click": TRACE_BTN},
        {"click": _trace_dot(4)},
        ev(
            """(() => {
              const t = window.__tr;
              window.__tick(1500);
              window.__tick(3000);
              const edge = t.edge('tax', 'charge');
              const line = edge.querySelector('[data-q-flow-edge-line]');
              const visibleDots = [...t.f.querySelectorAll('mask circle')].filter((c) => !c.hasAttribute('data-q-inactive')).length;
              return {
                lit: edge.hasAttribute('data-q-flow-lit'),
                width: line.getAttribute('stroke-width'),
                marker: line.getAttribute('marker-end').includes('arrow-lit'),
                pulsing: t.f.hasAttribute('data-q-flow-pulsing'),
                pulseHidden: edge.querySelector('[data-q-flow-edge-pulse]').hasAttribute('data-q-inactive'),
                visibleDots,
                counter: t.counter().slice(0, 9),
              };
            })()""",
            "step4",
        ),
        {"click": TRACE_NEXT},
        ev("window.__tr.counter().slice(0, 9)", "next"),
        {"click": TRACE_PLAY},
        ev("(() => { window.__tick(10000); window.__tick(11600); return window.__tr.counter().slice(0, 9); })()", "played"),
        ev("[...window.__tr.f.querySelectorAll('mask circle')].filter((c) => !c.hasAttribute('data-q-inactive')).length", "dotsAfterPlay"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["step4"] == {
        "lit": True,
        "width": "3.5",
        "marker": True,
        "pulsing": False,
        "pulseHidden": True,
        "visibleDots": 0,
        "counter": "Step 4 of",
    }
    assert r["next"] == "Step 5 of"
    assert r["played"] == "Step 6 of"
    assert r["dotsAfterPlay"] == 0


def test_flow_trace_pans_an_off_screen_current_node_into_view_at_the_same_zoom(flow_traces_page: Path) -> None:
    probe = """(() => {
      const f = document.querySelector('#renewal');
      const stage = f.querySelector('[data-q-flow-stage]').getBoundingClientRect();
      const n = f.querySelector('[data-q-flow-node="settle"]').getBoundingClientRect();
      const m = f.querySelector('[data-q-flow-viewport]').getAttribute('transform').match(/scale\\(([-\\d.e]+)\\)/);
      return {
        k: Number(m[1]),
        inside: n.left >= stage.left - 1 && n.right <= stage.right + 1 && n.top >= stage.top - 1 && n.bottom <= stage.bottom + 1,
      };
    })()"""
    zoom_in = '#renewal [data-q-flow-action="zoom-in"]'
    out = run(
        flow_traces_page,
        {"click": TRACE_BTN},
        {"click": zoom_in},
        {"click": zoom_in},
        {"click": zoom_in},
        {"click": zoom_in},
        {"click": zoom_in},
        {"click": zoom_in},
        {"click": _trace_dot(1)},
        ev(probe, "before"),
        {"click": _trace_dot(6)},
        ev(probe, "after"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["before"]["inside"] is False
    assert r["before"]["k"] > 1.5
    assert r["after"]["inside"] is True
    assert r["after"]["k"] == r["before"]["k"]


def test_flow_trace_leaves_focus_mode_exactly_as_it_was_before_tracing(flow_traces_page: Path) -> None:
    lit = """(() => {
      const f = document.querySelector('#renewal');
      const names = (sel, attr) => [...f.querySelectorAll(sel)].filter((n) => n.hasAttribute(attr)).map((n) => n.getAttribute('data-q-flow-node') || n.getAttribute('data-q-flow-from') + '>' + n.getAttribute('data-q-flow-to'));
      return {
        litNodes: names('[data-q-flow-node]', 'data-q-flow-lit'),
        dimNodes: names('[data-q-flow-node]', 'data-q-flow-dim'),
        litEdges: names('[data-q-flow-edge]', 'data-q-flow-lit'),
        dimEdges: names('[data-q-flow-edge]', 'data-q-flow-dim'),
        pulsing: f.hasAttribute('data-q-flow-pulsing'),
        drawer: !f.querySelector('[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
      };
    })()"""
    charge = '#renewal [data-q-flow-node="charge"]'
    out = run(
        flow_traces_page,
        {"click": charge},
        ev(lit, "before"),
        {"click": TRACE_BTN},
        {"click": TRACE_NEXT},
        {"click": TRACE_BTN},
        {"click": charge},
        ev(lit, "after"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["before"]["litNodes"] and r["before"]["drawer"] is True
    assert r["after"] == r["before"]


def test_flow_trace_grows_a_shallow_stage_so_the_value_tree_is_visible_beside_it(flow_traces_page: Path) -> None:
    probe = """(() => {
      const f = document.querySelector('#wide');
      const stage = f.querySelector('[data-q-flow-stage]').getBoundingClientRect();
      const panel = f.querySelector('[data-q-flow-trace-panel]').getBoundingClientRect();
      const top = f.querySelector('[data-q-flow-trace-value] li[data-q-flow-field]');
      const li = top ? top.getBoundingClientRect() : null;
      const m = f.querySelector('[data-q-flow-viewport]').getAttribute('transform').match(/scale\\(([-\\d.e]+)\\)/);
      return {
        stageHeight: stage.height,
        panelBottom: panel.bottom,
        fieldBottom: li ? li.bottom : null,
        tracing: f.hasAttribute('data-q-flow-tracing'),
        scale: m ? Number(m[1]) : null,
      };
    })()"""
    out = run(
        flow_traces_page,
        ev(probe, "rest"),
        {"click": "#wide [data-q-flow-action='trace']"},
        ev(probe, "open"),
        {"click": "#wide [data-q-flow-action='trace']"},
        ev(probe, "closed"),
        {"viewport": {"width": 375, "height": 800}},
        {"click": "#wide [data-q-flow-action='trace']"},
        ev(probe, "phone"),
        viewport={"width": 1280, "height": 900},
    )
    assert_clean(out)
    r = out["results"]
    assert r["open"]["tracing"] and r["open"]["stageHeight"] >= 440
    assert r["open"]["fieldBottom"] is not None and r["open"]["fieldBottom"] <= r["open"]["panelBottom"]
    assert not r["closed"]["tracing"] and r["closed"]["stageHeight"] < 440
    assert r["closed"]["stageHeight"] == r["rest"]["stageHeight"]
    assert r["phone"]["stageHeight"] < 440


def test_flow_trace_button_looks_pressed_while_trace_mode_is_open(flow_traces_page: Path) -> None:
    probe = """(() => {
      const b = document.querySelector('#renewal [data-q-flow-action="trace"]');
      const s = getComputedStyle(b);
      const probe = document.createElement('span');
      probe.style.color = 'var(--q-color-accent)';
      probe.style.backgroundColor = 'var(--q-color-accent-text)';
      document.body.append(probe);
      const accent = getComputedStyle(probe).color;
      const accentText = getComputedStyle(probe).backgroundColor;
      probe.remove();
      return {
        pressed: b.getAttribute('aria-pressed'), hovered: b.matches(':hover'),
        border: s.borderTopColor, background: s.backgroundColor, color: s.color, accent, accentText,
      };
    })()"""
    out = run(
        flow_traces_page,
        {"hover": "#plain"},
        ev(probe, "rest"),
        {"click": TRACE_BTN},
        {"hover": "#plain"},
        ev(probe, "open"),
        viewport={"width": 1280, "height": 900},
    )
    assert_clean(out)
    rest, opened = out["results"]["rest"], out["results"]["open"]
    assert rest["pressed"] == "false" and opened["pressed"] == "true"
    assert not rest["hovered"] and not opened["hovered"]
    assert opened["background"] == opened["accent"]
    assert opened["color"] == opened["accentText"]
    assert opened["background"] != rest["background"]
    assert opened["color"] != rest["color"]
    assert opened["border"] != rest["border"]


def test_flow_summary_keeps_its_44px_touch_target_on_a_graph_with_no_traces(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(
            """(() => {
              const s = getComputedStyle(document.querySelector('#plain > details > summary'));
              return { minHeight: s.minHeight, display: s.display, alignItems: s.alignItems, cursor: s.cursor };
            })()""",
            "summary",
        ),
    )
    assert_clean(out)
    assert out["results"]["summary"] == {"minHeight": "44px", "display": "flex", "alignItems": "center", "cursor": "pointer"}


def test_flow_trace_value_that_is_not_json_fails_to_the_notice(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        ev(
            """(() => Object.fromEntries([...document.querySelectorAll('q-flow[id^="bv-"]')].map((f) => [
              f.id.slice(3),
              { notice: f.querySelector('[data-q-flow-notice]') !== null, ready: f.getAttribute('data-q-flow-ready'),
                button: f.querySelector('[data-q-flow-action="trace"]') !== null },
            ])))()""",
            "d",
        ),
    )
    assert_clean(out)
    bad = {"notice": True, "ready": "error", "button": False}
    good = {"notice": False, "ready": "true", "button": True}
    assert out["results"]["d"] == {
        "inf": bad,
        "neginf": bad,
        "sur": bad,
        "surkey": bad,
        "surdeep": bad,
        "surpair": good,
        "nested": bad,
    }


def test_flow_graph_text_with_a_lone_surrogate_fails_to_the_notice_and_a_valid_pair_draws(
    flow_traces_page: Path,
) -> None:
    out = run(
        flow_traces_page,
        ev(
            """(() => Object.fromEntries([...document.querySelectorAll('q-flow[id^="bt-"]')].map((f) => [
              f.id.slice(3),
              { notice: f.querySelector('[data-q-flow-notice]') !== null, ready: f.getAttribute('data-q-flow-ready') },
            ])))()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {
        "label": {"notice": True, "ready": "error"},
        "emoji": {"notice": False, "ready": "true"},
    }


def test_flow_trace_panel_sits_below_the_stage_on_a_phone_and_beside_it_on_a_desktop(flow_traces_page: Path) -> None:
    geometry = """(() => {
      const f = document.querySelector('#renewal');
      const stage = f.querySelector('[data-q-flow-stage]').getBoundingClientRect();
      const panel = f.querySelector('[data-q-flow-trace-panel]').getBoundingClientRect();
      const style = getComputedStyle(f);
      return {
        tracing: f.hasAttribute('data-q-flow-tracing'),
        panelHeight: panel.height,
        belowStage: panel.top >= stage.bottom - 1,
        besideStage: panel.left >= stage.right - 1,
        widthRatio: panel.width / stage.width,
        sameTop: Math.abs(panel.top - stage.top) < 2,
        display: style.display,
        rows: style.gridTemplateRows,
        columns: style.gridTemplateColumns.split(' ').length,
        expanded: f.hasAttribute('data-q-flow-expanded'),
        innerHeight: window.innerHeight,
        panelVisible: panel.width > 0 && panel.height > 0,
        scrolls: getComputedStyle(f.querySelector('[data-q-flow-trace-panel]')).overflowY,
        maxHeight: getComputedStyle(f.querySelector('[data-q-flow-trace-panel]')).maxHeight,
      };
    })()"""
    expand = '#renewal [data-q-flow-action="expand"]'
    out = run(
        flow_traces_page,
        {"viewport": {"width": 375, "height": 800}},
        {"click": TRACE_BTN},
        ev(geometry, "phone"),
        {"click": expand},
        ev(geometry, "phoneExpanded"),
        {"click": expand},
        {"viewport": {"width": 1280, "height": 800}},
        ev(geometry, "desktop"),
        {"click": expand},
        ev(geometry, "desktopExpanded"),
        {"click": expand},
        ev(geometry, "desktopCollapsed"),
    )
    assert_clean(out)
    r = out["results"]
    phone = r["phone"]
    assert phone["tracing"] and phone["belowStage"] and 0.95 < phone["widthRatio"] < 1.05
    assert phone["display"] == "block"
    desk = r["desktop"]
    assert desk["tracing"] and desk["besideStage"] and desk["sameTop"] and desk["display"] == "grid"
    assert 0.2 < desk["widthRatio"] < 0.5
    for key in ("phoneExpanded", "desktopExpanded", "desktopCollapsed"):
        assert r[key]["tracing"] and r[key]["panelVisible"], key
    pe = r["phoneExpanded"]
    assert pe["expanded"] and pe["display"] == "grid" and pe["belowStage"]
    assert pe["panelHeight"] <= pe["innerHeight"] * 0.45 + 1
    assert pe["scrolls"] in ("auto", "scroll")
    de = r["desktopExpanded"]
    assert de["expanded"] and de["display"] == "grid" and de["besideStage"] and de["columns"] == 2
    assert len(de["rows"].split(" ")) >= 2
    assert r["desktopCollapsed"]["expanded"] is False and r["desktopCollapsed"]["besideStage"]


def test_flow_trace_panel_is_hidden_with_the_controls_when_printing(flow_traces_page: Path) -> None:
    out = run(
        flow_traces_page,
        {"click": TRACE_BTN},
        {"emulate": {"media": "print"}},
        ev(
            """(() => {
              const f = document.querySelector('#renewal');
              return ['[data-q-flow-trace-panel]', '[data-q-flow-controls]', '[data-q-flow-drawer]']
                .map((s) => getComputedStyle(f.querySelector(s)).display);
            })()""",
            "display",
        ),
    )
    assert_clean(out)
    assert out["results"]["display"] == ["none", "none", "none"]


# --- q-schema ---------------------------------------------------------------------------------


def _schema_field(name: str, ftype: str, key: object = None, nullable: bool = False) -> dict:
    field: dict = {"name": name, "type": ftype}
    if key:
        field["key"] = key
    if nullable:
        field["nullable"] = True
    return field


def _schema_rel(src: str, dst: str, from_card: str, to_card: str, label: str | None = None) -> dict:
    rel = {"from": src, "to": dst, "from_card": from_card, "to_card": to_card}
    if label:
        rel["label"] = label
    return rel


def _schema_tag(tag_id: str, summary: str, data: dict, notation: str | None = None) -> str:
    attr = f' notation="{notation}"' if notation else ""
    return (
        f'<q-schema id="{tag_id}" summary="{summary}"{attr}>\n  <script type="application/json">\n'
        f"{json.dumps(data, indent=2)}\n  </script>\n</q-schema>\n"
    )


SCHEMA_BILLING_DATA = {
    "kinds": {"core": 1, "billing": 2},
    "groups": [{"id": "billing", "label": "Billing"}],
    "entities": [
        {
            "id": "customer",
            "label": "Customer",
            "kind": "core",
            "fields": [
                _schema_field("id", "int", "PK"),
                _schema_field("email", "text", "UK"),
                _schema_field("first_name", "text"),
                _schema_field("last_name", "text"),
                _schema_field("created_at", "timestamp"),
            ],
        },
        {
            "id": "subscription",
            "label": "Subscription",
            "kind": "billing",
            "group": "billing",
            "detail": "<p>A recurring order for one customer.</p>",
            "fields": [
                _schema_field("id", "int", "PK"),
                _schema_field("customer_id", "int", "FK"),
                _schema_field("product_title", "text"),
                _schema_field("status", "text"),
                _schema_field("next_charge_date", "date"),
                _schema_field("interval", "text"),
            ],
        },
        {
            "id": "charge",
            "label": "Charge",
            "kind": "billing",
            "group": "billing",
            "fields": [
                _schema_field("id", "int", "PK"),
                _schema_field("status", "text"),
                _schema_field("total_price", "decimal"),
                _schema_field("currency", "text"),
                _schema_field("scheduled_at", "timestamp"),
                _schema_field("processed_at", "timestamp"),
                _schema_field("error_type", "text"),
                _schema_field("error", "text"),
                _schema_field("retry_count", "int"),
                _schema_field("tags", "text"),
                _schema_field("note", "text"),
                _schema_field("created_at", "timestamp"),
                _schema_field("updated_at", "timestamp"),
                _schema_field("customer_id", "int", "FK"),
                _schema_field("subscription_id", "int", "FK", nullable=True),
            ],
        },
        {
            "id": "line_item",
            "label": "Line item",
            "kind": "billing",
            "group": "billing",
            "fields": [
                _schema_field("id", "int", "PK"),
                _schema_field("charge_id", "int", "FK"),
                _schema_field("title", "text"),
                _schema_field("quantity", "int"),
                _schema_field("price", "decimal"),
            ],
        },
    ],
    "relationships": [
        _schema_rel("subscription.customer_id", "customer.id", "zero-or-many", "one", "has"),
        _schema_rel("charge.customer_id", "customer.id", "zero-or-many", "one", "is billed"),
        _schema_rel("charge.subscription_id", "subscription.id", "zero-or-many", "zero-or-one", "generates"),
        _schema_rel("line_item.charge_id", "charge.id", "one-or-many", "one", "contains"),
    ],
}

SCHEMA_EMPLOYEE_DATA = {
    "entities": [
        {
            "id": "employee",
            "label": "Employee",
            "fields": [
                _schema_field("id", "int", "PK"),
                _schema_field("manager_id", "int", "FK", nullable=True),
                _schema_field("name", "text"),
            ],
        }
    ],
    "relationships": [_schema_rel("employee.manager_id", "employee.id", "zero-or-many", "zero-or-one", "manages")],
}

SCHEMA_SMALL_DATA = {
    "entities": [
        {"id": "author", "label": "Author", "fields": [_schema_field("id", "int", "PK"), _schema_field("name", "text")]},
        {
            "id": "book",
            "label": "Book",
            "fields": [
                _schema_field("id", "int", "PK"),
                _schema_field("author_id", "int", "FK"),
                _schema_field("title", "text"),
            ],
        },
    ],
    "relationships": [_schema_rel("book.author_id", "author.id", "zero-or-many", "one", "wrote")],
}

SCHEMA_BROKEN_DATA = {
    "entities": [
        {"id": "note", "label": "Note", "fields": [_schema_field("id", "int", "PK"), _schema_field("body", "text")]},
        {"id": "tag", "label": "Tag", "fields": [_schema_field("id", "int", "PK"), _schema_field("note_id", "int", "FK")]},
    ],
    "relationships": [_schema_rel("tag.note_id", "note.id", "zero-or-many", "one")],
}

SCHEMA_CLASS_DATA = {
    "entities": [
        {"id": "parser", "label": "Parser", "stereotype": "interface", "methods": [{"signature": "parse(src: str) -> Ast"}]},
        {
            "id": "lexer",
            "label": "Lexer",
            "fields": [{"name": "src", "type": "str", "visibility": "private"}, {"name": "limit", "visibility": "public", "static": True}],
            "methods": [{"signature": "next() -> Token", "visibility": "public"}],
        },
    ],
    "relationships": [
        {"from": "parser", "to": "lexer", "type": "composition", "to_mult": "1", "label": "owns"},
        {"from": "lexer", "to": "parser", "type": "dependency"},
    ],
}

SCHEMA_PAGE = (
    '<button type="button" id="schema-before">Before the models</button>\n'
    + _schema_tag(
        "schema-billing", "Customers, their subscriptions, and the charges and line items billing creates.", SCHEMA_BILLING_DATA
    )
    + _schema_tag("schema-employee", "Employees and their managers.", SCHEMA_EMPLOYEE_DATA)
    + _schema_tag("schema-small", "Authors and their books.", SCHEMA_SMALL_DATA)
    + _schema_tag("schema-broken", "Notes and their tags.", SCHEMA_BROKEN_DATA)
    + _schema_tag("schema-uml", "Authors and their books, in an unknown notation.", SCHEMA_SMALL_DATA)
    + _schema_tag("schema-class", "Parsing classes.", SCHEMA_CLASS_DATA, notation="class")
)


@pytest.fixture(scope="module")
def schema_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-schema")
    src = work / "schema.src.html"
    src.write_text(HEADER + SCHEMA_PAGE, encoding="utf-8")
    built = _build(src, work / "schema.html")
    # the failing models are edited in after the build so the build-time check never sees them
    html = built.read_text(encoding="utf-8")
    bad_end = '"to": "note.id"'
    assert html.count(bad_end) == 1
    html = html.replace(bad_end, '"to": "note.uuid"')
    unknown = '<q-schema id="schema-uml" summary="Authors and their books, in an unknown notation.">'
    assert unknown in html
    html = html.replace(unknown, unknown.replace(">", ' notation="uml">'))
    built.write_text(html, encoding="utf-8")
    return built


SCHEMA_GEOMETRY_JS = """
  const num = (s) => (s.match(/-?\\d+(?:\\.\\d+)?(?:e-?\\d+)?/g) || []).map(Number);
  const pathPoints = (d) => { const n = num(d); const out = []; for (let i = 0; i + 1 < n.length; i += 2) out.push({ x: n[i], y: n[i + 1] }); return out; };
  const card = (m, id) => m.querySelector('[data-q-schema-entity="' + id + '"]');
  const cardBox = (m, id) => card(m, id).querySelector('[data-q-schema-card]').getBBox();
  const rowY = (m, id, name) => Number(card(m, id).querySelector('[data-q-schema-field="' + name + '"]').getAttribute('data-q-schema-row-y'));
  const relAt = (m, idx) => m.querySelector('[data-q-schema-rel="' + idx + '"]');
  const lineOf = (rel) => rel.querySelector('[data-q-flow-edge-line]');
  const segDistance = (p, a, b) => {
    const dx = b.x - a.x, dy = b.y - a.y;
    const len2 = dx * dx + dy * dy;
    const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2));
    return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
  };
  const markKind = (m, url) => {
    const id = (url || '').replace(/^url\\(#/, '').replace(/\\)$/, '');
    const mk = m.querySelector('[id="' + id + '"]');
    return mk && mk.getAttribute('data-q-schema-mark');
  };
  const entityIds = (m, attr) => [...m.querySelectorAll('[data-q-schema-entity][' + attr + ']')].map((e) => e.getAttribute('data-q-schema-entity')).sort();
  const relIdx = (m, attr) => [...m.querySelectorAll('[data-q-schema-rel][' + attr + ']')].map((e) => Number(e.getAttribute('data-q-schema-rel'))).sort();
  const drawerState = (m) => {
    const d = m.querySelector('[data-q-flow-drawer]');
    return {
      open: !d.hasAttribute('data-q-inactive'),
      heading: d.querySelector('h3') && d.querySelector('h3').textContent,
      fields: [...d.querySelectorAll('[data-q-schema-drawer-field]')].map((e) => e.textContent),
      buttons: [...d.querySelectorAll('[data-q-flow-edge-btn]')].map((e) => e.textContent),
    };
  };
"""

SCHEMA_RELS = [
    (0, "subscription", "customer_id", "customer", "id", "zero-or-many", "one", "has"),
    (1, "charge", "customer_id", "customer", "id", "zero-or-many", "one", "is billed"),
    (2, "charge", "subscription_id", "subscription", "id", "zero-or-many", "zero-or-one", "generates"),
    (3, "line_item", "charge_id", "charge", "id", "one-or-many", "one", "contains"),
]


def test_schema_billing_draws_four_cards_with_three_inside_the_billing_panel(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              const g = m.querySelector('[data-q-flow-group="billing"] [data-q-flow-group-box]');
              const gb = {{ x: +g.getAttribute('x'), y: +g.getAttribute('y'), w: +g.getAttribute('width'), h: +g.getAttribute('height') }};
              const inside = (id) => {{
                const b = cardBox(m, id);
                return b.x >= gb.x && b.y >= gb.y && b.x + b.width <= gb.x + gb.w && b.y + b.height <= gb.y + gb.h;
              }};
              const accent = (id) => card(m, id).querySelector('[data-q-schema-accent]').getAttribute('fill');
              return {{
                ready: m.getAttribute('data-q-flow-ready'),
                cards: [...m.querySelectorAll('[data-q-schema-entity]')].map((e) => e.getAttribute('data-q-schema-entity')),
                inside: ['customer', 'subscription', 'charge', 'line_item'].map(inside),
                accents: ['customer', 'subscription', 'charge', 'line_item'].map(accent),
                rels: m.querySelectorAll('[data-q-schema-rel]').length,
                groupLabel: m.querySelector('[data-q-flow-group-header] text').textContent,
                role: card(m, 'charge').getAttribute('role'),
                aria: card(m, 'charge').getAttribute('aria-label'),
                listOpen: m.querySelector('[data-q-flow-list]').open,
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert d["cards"] == ["customer", "subscription", "charge", "line_item"]
    assert d["inside"] == [False, True, True, True]
    assert d["accents"] == ["var(--q-color-chart-1)"] + ["var(--q-color-chart-2)"] * 3
    assert d["rels"] == 4
    assert d["groupLabel"] == "Billing"
    assert d["role"] == "button"
    assert d["aria"] == "Charge, billing, 15 fields, 3 relationships"
    assert d["listOpen"] is False


def test_schema_each_line_runs_between_the_field_rows_it_names_with_its_marks_and_label(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              return {json.dumps(SCHEMA_RELS)}.map(([idx, fromE, fromF, toE, toF]) => {{
                const rel = relAt(m, idx);
                const line = lineOf(rel);
                const pts = pathPoints(line.getAttribute('d'));
                const first = pts[0], last = pts[pts.length - 1];
                const toBox = cardBox(m, toE), fromBox = cardBox(m, fromE);
                const lbl = rel.querySelector('[data-q-schema-rel-label]');
                const lb = lbl.querySelector('rect').getBBox();
                const centre = {{ x: lb.x + lb.width / 2, y: lb.y + lb.height / 2 }};
                let near = Infinity;
                for (let i = 0; i + 1 < pts.length; i += 1) near = Math.min(near, segDistance(centre, pts[i], pts[i + 1]));
                return {{
                  from: rel.getAttribute('data-q-schema-from'),
                  to: rel.getAttribute('data-q-schema-to'),
                  fromMark: rel.getAttribute('data-q-schema-from-mark'),
                  toMark: rel.getAttribute('data-q-schema-to-mark'),
                  startRow: Math.abs(first.y - rowY(m, toE, toF)),
                  startEdge: Math.abs(first.x - (toBox.x + toBox.width)),
                  endRow: Math.abs(last.y - rowY(m, fromE, fromF)),
                  endEdge: Math.abs(last.x - fromBox.x),
                  startMarker: markKind(m, line.getAttribute('marker-start')),
                  endMarker: markKind(m, line.getAttribute('marker-end')),
                  label: lbl.textContent,
                  labelOffLine: near,
                }};
              }});
            }})()""",
            "rels",
        ),
    )
    assert_clean(out)
    for (idx, from_e, _ff, to_e, _tf, from_card, to_card, label), got in zip(SCHEMA_RELS, out["results"]["rels"]):
        assert (got["from"], got["to"]) == (from_e, to_e), idx
        assert (got["fromMark"], got["toMark"]) == (from_card, to_card), idx
        assert got["startRow"] <= 1 and got["endRow"] <= 1, (idx, got)
        assert got["startEdge"] <= 1 and got["endEdge"] <= 1, (idx, got)
        assert got["startMarker"] == to_card and got["endMarker"] == from_card, (idx, got)
        assert got["label"] == label, idx
        assert got["labelOffLine"] <= 14, (idx, got)


def test_schema_marks_are_scoped_markers_with_theme_colours_per_model(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            """(() => {
              const ids = (m) => [...m.querySelectorAll('marker')].map((e) => e.id);
              const billing = document.querySelector('#schema-billing');
              const small = document.querySelector('#schema-small');
              const some = billing.querySelector('marker');
              const kinds = [...new Set([...billing.querySelectorAll('marker[data-q-schema-mark]')].map((e) => e.getAttribute('data-q-schema-mark')))].sort();
              return {
                orient: some.getAttribute('orient'),
                kinds,
                disjoint: ids(billing).every((id) => !ids(small).includes(id)),
                sameSvgIds: new Set(ids(billing)).size === ids(billing).length,
                strokes: [...billing.querySelectorAll('marker *')].every((e) => ['stroke', 'fill'].every((a) => !e.hasAttribute(a) || e.getAttribute(a) === 'none' || e.getAttribute(a).startsWith('var(--q-color-'))),
              };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["orient"] == "auto-start-reverse"
    assert d["kinds"] == ["one", "one-or-many", "zero-or-many", "zero-or-one"]
    assert d["disjoint"] is True and d["sameSvgIds"] is True and d["strokes"] is True


def test_schema_charge_folds_to_eight_rows_with_keys_and_related_fields_shown(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              const c = card(m, 'charge');
              const rows = [...c.querySelectorAll('[data-q-schema-field]')];
              const more = c.querySelectorAll('[data-q-schema-more]');
              const lastRow = rows[rows.length - 1];
              const moreY = Number(more[0].querySelector('[data-q-schema-row-bg]').getAttribute('y'));
              return {{
                names: rows.map((r) => r.getAttribute('data-q-schema-field')),
                types: rows.map((r) => r.querySelector('[data-q-schema-type]').textContent),
                badges: [...c.querySelectorAll('[data-q-schema-badge]')].map((b) => b.getAttribute('data-q-schema-badge') + ':' + b.textContent),
                moreCount: more.length,
                moreText: more[0].textContent,
                moreBelowRows: moreY >= Number(lastRow.getAttribute('data-q-schema-row-y')),
                customerMore: card(m, 'customer').querySelectorAll('[data-q-schema-more]').length,
                customerRows: card(m, 'customer').querySelectorAll('[data-q-schema-field]').length,
                nullableNote: rows[rows.length - 1].textContent,
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["names"] == [
        "id",
        "status",
        "total_price",
        "currency",
        "scheduled_at",
        "processed_at",
        "customer_id",
        "subscription_id",
    ]
    assert d["types"][0] == "int" and d["types"][2] == "decimal"
    assert d["badges"] == ["PK:PK", "FK:FK", "FK:FK"]
    assert d["moreCount"] == 1 and d["moreText"] == "+7 more" and d["moreBelowRows"] is True
    assert d["customerMore"] == 0 and d["customerRows"] == 5


def test_schema_self_relationship_is_a_loop_from_the_manager_row_to_the_id_row(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-employee');
              const rel = relAt(m, 0);
              const line = lineOf(rel);
              const d = line.getAttribute('d');
              const pts = pathPoints(d);
              const b = cardBox(m, 'employee');
              const lbl = rel.querySelector('[data-q-schema-rel-label]');
              return {{
                ready: m.getAttribute('data-q-flow-ready'),
                startRow: Math.abs(pts[0].y - rowY(m, 'employee', 'manager_id')),
                endRow: Math.abs(pts[pts.length - 1].y - rowY(m, 'employee', 'id')),
                startEdge: Math.abs(pts[0].x - (b.x + b.width)),
                endEdge: Math.abs(pts[pts.length - 1].x - (b.x + b.width)),
                reach: Math.max(...pts.map((p) => p.x)) - (b.x + b.width),
                rounded: d.includes('Q'),
                pointCount: pts.length,
                startMarker: markKind(m, line.getAttribute('marker-start')),
                endMarker: markKind(m, line.getAttribute('marker-end')),
                label: lbl.textContent,
                labelBeside: lbl.querySelector('rect').getBBox().x >= b.x + b.width,
                cards: m.querySelectorAll('[data-q-schema-entity]').length,
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true" and d["cards"] == 1
    assert d["startRow"] <= 1 and d["endRow"] <= 1
    assert d["startEdge"] <= 1 and d["endEdge"] <= 1
    assert 20 <= d["reach"] <= 30
    assert d["rounded"] is True and d["pointCount"] > 2
    assert (d["startMarker"], d["endMarker"]) == ("zero-or-many", "zero-or-one")
    assert d["label"] == "manages" and d["labelBeside"] is True


def test_schema_focus_lights_a_card_its_lines_and_direct_neighbours_and_opens_its_drawer(schema_page: Path) -> None:
    out = run(
        schema_page,
        {"click": '#schema-billing [data-q-schema-entity="subscription"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              return {{
                lit: entityIds(m, 'data-q-flow-lit'),
                dim: entityIds(m, 'data-q-flow-dim'),
                selected: entityIds(m, 'data-q-flow-selected'),
                litRels: relIdx(m, 'data-q-flow-lit'),
                dimRels: relIdx(m, 'data-q-flow-dim'),
                drawer: drawerState(m),
                kind: m.querySelector('[data-q-flow-drawer-kind]').textContent,
                detail: m.querySelector('[data-q-flow-drawer-detail]').textContent,
                live: m.querySelector('[data-q-flow-live]').textContent,
                pulsing: m.hasAttribute('data-q-flow-pulsing'),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["lit"] == ["charge", "customer", "subscription"]
    assert d["dim"] == ["line_item"]
    assert d["selected"] == ["subscription"]
    assert d["litRels"] == [0, 2]
    assert d["dimRels"] == [1, 3]
    assert d["drawer"]["open"] is True
    assert d["drawer"]["heading"] == "Subscription"
    assert d["drawer"]["fields"] == [
        "id: int, PK",
        "customer_id: int, FK",
        "product_title: text",
        "status: text",
        "next_charge_date: date",
        "interval: text",
    ]
    assert d["drawer"]["buttons"] == ["has: Customer (customer_id → id)", "generates: Charge (subscription_id → id)"]
    assert d["kind"] == "billing"
    assert d["detail"] == "A recurring order for one customer."
    assert d["live"] == "Subscription, billing, 6 fields, 2 relationships"
    assert d["pulsing"] is False


def test_schema_relationship_button_refocuses_the_entity_at_the_other_end(schema_page: Path) -> None:
    out = run(
        schema_page,
        {"click": '#schema-billing [data-q-schema-entity="subscription"]'},
        {"click": '#schema-billing [data-q-flow-edge-btn][data-q-flow-target="charge"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              const drawer = drawerState(m);
              return {{
                lit: entityIds(m, 'data-q-flow-lit'),
                selected: entityIds(m, 'data-q-flow-selected'),
                heading: drawer.heading,
                fieldCount: drawer.fields.length,
                last: drawer.fields[drawer.fields.length - 1],
                buttons: drawer.buttons,
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["lit"] == ["charge", "customer", "line_item", "subscription"]
    assert d["selected"] == ["charge"]
    assert d["heading"] == "Charge" and d["fieldCount"] == 15
    assert d["last"] == "subscription_id: int, FK, can be empty"
    assert d["buttons"] == [
        "is billed: Customer (customer_id → id)",
        "generates: Subscription (subscription_id → id)",
        "contains: Line item (charge_id \u2192 id)",
    ]


def test_schema_more_row_click_focuses_the_entity_and_lists_every_field(schema_page: Path) -> None:
    out = run(
        schema_page,
        {"click": "#schema-billing [data-q-schema-more]"},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              return {{ selected: entityIds(m, 'data-q-flow-selected'), drawer: drawerState(m) }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["selected"] == ["charge"]
    assert d["drawer"]["open"] is True and d["drawer"]["heading"] == "Charge"
    assert len(d["drawer"]["fields"]) == 15


SCHEMA_CLEARED_JS = f"""(() => {{
  {SCHEMA_GEOMETRY_JS}
  const m = document.querySelector('#schema-billing');
  return {{
    lit: entityIds(m, 'data-q-flow-lit'),
    dim: entityIds(m, 'data-q-flow-dim'),
    selected: entityIds(m, 'data-q-flow-selected'),
    litRels: relIdx(m, 'data-q-flow-lit'),
    dimRels: relIdx(m, 'data-q-flow-dim'),
    drawerOpen: drawerState(m).open,
  }};
}})()"""
SCHEMA_NOT_FOCUSED = {"lit": [], "dim": [], "selected": [], "litRels": [], "dimRels": [], "drawerOpen": False}
SCHEMA_FOCUS_SUBSCRIPTION = {"click": '#schema-billing [data-q-schema-entity="subscription"]'}


def test_schema_escape_empty_canvas_and_close_button_each_clear_focus(schema_page: Path) -> None:
    out = run(
        schema_page,
        SCHEMA_FOCUS_SUBSCRIPTION,
        {"press": "Escape"},
        ev(SCHEMA_CLEARED_JS, "escape"),
        SCHEMA_FOCUS_SUBSCRIPTION,
        ev(
            "document.querySelector('#schema-billing [data-q-flow-svg]').dispatchEvent(new MouseEvent('click', { bubbles: true })), 1",
            "tap",
        ),
        ev(SCHEMA_CLEARED_JS, "empty"),
        SCHEMA_FOCUS_SUBSCRIPTION,
        {"click": "#schema-billing [data-q-flow-drawer-close]"},
        ev(SCHEMA_CLEARED_JS, "close"),
    )
    assert_clean(out)
    for key in ("escape", "empty", "close"):
        assert out["results"][key] == SCHEMA_NOT_FOCUSED, key


def test_schema_group_header_click_dims_the_cards_outside_it_and_opens_no_drawer(schema_page: Path) -> None:
    out = run(
        schema_page,
        {"click": '#schema-billing [data-q-flow-group-header="billing"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              return {{
                lit: entityIds(m, 'data-q-flow-lit'),
                dim: entityIds(m, 'data-q-flow-dim'),
                drawerOpen: drawerState(m).open,
                dimRels: relIdx(m, 'data-q-flow-dim'),
                litRels: relIdx(m, 'data-q-flow-lit'),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {
        "lit": ["charge", "line_item", "subscription"],
        "dim": ["customer"],
        "drawerOpen": False,
        "dimRels": [0, 1],
        "litRels": [2, 3],
    }


def test_schema_keyboard_roving_tabindex_arrows_enter_announce_and_zoom_keys(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            "document.querySelector('#schema-billing [data-q-flow-viewport]').getAttribute('transform')",
            "t0",
        ),
        {"focus": "#schema-before"},
        {"press": "Tab"},
        ev(
            """(() => {
              const m = document.querySelector('#schema-billing');
              return {
                onCard: document.activeElement.getAttribute('data-q-schema-entity'),
                roving: m.querySelectorAll('[data-q-schema-entity][tabindex="0"]').length,
              };
            })()""",
            "entered",
        ),
        {"press": "Tab"},
        ev("document.activeElement.hasAttribute('data-q-schema-entity')", "stillOnCard"),
        {"focus": '#schema-billing [data-q-schema-entity][tabindex="0"]'},
        {"press": "ArrowRight"},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              const from = cardBox(m, 'customer');
              const fx = from.x + from.width / 2, fy = from.y + from.height / 2;
              let best = null, bestScore = Infinity;
              for (const id of ['subscription', 'charge', 'line_item']) {{
                const b = cardBox(m, id);
                const dx = b.x + b.width / 2 - fx, dy = b.y + b.height / 2 - fy;
                if (dx > 2 && dx + Math.abs(dy) * 1.5 < bestScore) {{ best = id; bestScore = dx + Math.abs(dy) * 1.5; }}
              }}
              return {{ moved: document.activeElement.getAttribute('data-q-schema-entity'), expected: best }};
            }})()""",
            "arrow",
        ),
        {"focus": '#schema-billing [data-q-schema-entity="subscription"]'},
        {"press": "Enter"},
        ev("document.querySelector('#schema-billing [data-q-flow-live]').textContent", "live"),
        ev("document.querySelector('#schema-billing [data-q-flow-drawer]').hasAttribute('data-q-inactive')", "drawerClosed"),
        {"press": "+"},
        ev("document.querySelector('#schema-billing [data-q-flow-viewport]').getAttribute('transform')", "tPlus"),
        {"press": "-"},
        ev("document.querySelector('#schema-billing [data-q-flow-viewport]').getAttribute('transform')", "tMinus"),
        {"press": "0"},
        ev("document.querySelector('#schema-billing [data-q-flow-viewport]').getAttribute('transform')", "tFit"),
    )
    assert_clean(out)
    res = out["results"]
    assert res["entered"] == {"onCard": "customer", "roving": 1}
    assert res["stillOnCard"] is False
    assert res["arrow"]["moved"] == res["arrow"]["expected"] and res["arrow"]["moved"] is not None
    assert res["live"] == "Subscription, billing, 6 fields, 2 relationships"
    assert res["drawerClosed"] is False
    scale = lambda t: float(re.search(r"scale\(([-0-9.e]+)\)", t).group(1))  # noqa: E731
    assert scale(res["tPlus"]) > scale(res["t0"])
    assert scale(res["tMinus"]) < scale(res["tPlus"])
    assert res["tFit"] == res["t0"]


def test_schema_theme_toggle_recolours_without_moving_cards(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              const svg = m.querySelector('[data-q-flow-svg]');
              const snap = () => ['customer', 'subscription', 'charge', 'line_item'].map((id) => {{
                const b = cardBox(m, id);
                return [b.x, b.y, b.width, b.height];
              }});
              const rect = card(m, 'charge').querySelector('[data-q-schema-card]');
              const line = lineOf(relAt(m, 0));
              document.documentElement.setAttribute('data-theme', 'light');
              const before = snap();
              const lightFill = getComputedStyle(rect).fill;
              const lightStroke = getComputedStyle(line).stroke;
              document.documentElement.setAttribute('data-theme', 'dark');
              const after = snap();
              const attrs = [rect.getAttribute('fill'), rect.getAttribute('stroke'), line.getAttribute('stroke'),
                card(m, 'charge').querySelector('[data-q-schema-accent]').getAttribute('fill')];
              return {{
                samePositions: JSON.stringify(before) === JSON.stringify(after),
                sameSvg: m.querySelector('[data-q-flow-svg]') === svg,
                fillChanged: lightFill !== getComputedStyle(rect).fill,
                strokeChanged: lightStroke !== getComputedStyle(line).stroke,
                attrs,
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["samePositions"] is True and d["sameSvg"] is True
    assert d["fillChanged"] is True and d["strokeChanged"] is True
    assert all(a.startswith("var(--q-color-") for a in d["attrs"]), d["attrs"]


def test_schema_expand_fills_the_screen_and_escape_returns_it_to_the_page(schema_page: Path) -> None:
    out = run(
        schema_page,
        {"click": '#schema-billing [data-q-flow-action="expand"]'},
        ev("document.querySelector('#schema-billing').hasAttribute('data-q-flow-expanded')", "expanded"),
        {"press": "Escape"},
        ev("document.querySelector('#schema-billing').hasAttribute('data-q-flow-expanded')", "after"),
    )
    assert_clean(out)
    assert out["results"]["expanded"] is True
    assert out["results"]["after"] is False


def test_schema_drawer_is_a_bottom_sheet_on_a_phone(schema_page: Path) -> None:
    out = run(
        schema_page,
        {"viewport": {"width": 375, "height": 800}},
        {"click": '#schema-billing [data-q-schema-entity="charge"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              const stage = m.querySelector('[data-q-flow-stage]').getBoundingClientRect();
              const drawer = m.querySelector('[data-q-flow-drawer]').getBoundingClientRect();
              return {{
                fullWidth: Math.abs(drawer.width - stage.width) <= 2,
                atBottom: Math.abs(drawer.bottom - stage.bottom) <= 2,
                topFraction: (drawer.top - stage.top) / stage.height,
                lit: entityIds(m, 'data-q-flow-lit'),
                btnHeights: [...m.querySelectorAll('[data-q-flow-edge-btn]')].map((b) => b.getBoundingClientRect().height >= 44),
              }};
            }})()""",
            "sheet",
        ),
    )
    assert_clean(out)
    sheet = out["results"]["sheet"]
    assert sheet["fullWidth"] is True and sheet["atBottom"] is True
    assert sheet["topFraction"] >= 0.45 - 0.01
    assert sheet["lit"] == ["charge", "customer", "line_item", "subscription"]
    assert sheet["btnHeights"] == [True, True, True]


SCHEMA_LIST_JS = """(() => {
  const lists = {};
  for (const id of ['schema-billing', 'schema-employee', 'schema-small', 'schema-class']) {
    const d = document.querySelector('#' + id + ' [data-q-flow-list]');
    lists[id] = {
      summary: d.querySelector('summary').textContent,
      text: d.querySelector('[data-q-flow-list-body]').textContent,
      entities: [...d.querySelectorAll('[data-q-schema-list-entity]')].map((e) => e.getAttribute('data-q-schema-list-entity') + '|' + e.textContent),
      groups: [...d.querySelectorAll('[data-q-flow-list-group]')].map((e) => e.getAttribute('data-q-flow-list-group')),
      rels: [...d.querySelectorAll('[data-q-schema-list-rels] > li')].map((e) => e.textContent),
    };
  }
  return lists;
})()"""


def test_schema_js_text_list_equals_the_python_fallback_list(schema_page: Path) -> None:
    js = run(schema_page, ev(SCHEMA_LIST_JS, "lists"))
    assert_clean(js)
    nojs = run(schema_page, ev(SCHEMA_LIST_JS, "lists"), javaScript=False)
    assert nojs["failedSteps"] == [] and nojs["pageErrors"] == []
    js_lists, py_lists = js["results"]["lists"], nojs["results"]["lists"]
    assert js_lists == py_lists
    billing = js_lists["schema-billing"]
    assert billing["summary"] == "Data model as a list"
    assert billing["groups"] == ["billing"]
    assert billing["rels"][0] == (
        "Each Customer has zero or many Subscriptions, and each Subscription has one Customer "
        "(subscription.customer_id → customer.id)"
    )
    assert js_lists["schema-class"]["summary"] == "Class diagram as a list"


def test_schema_without_javascript_shows_the_notice_and_the_open_list(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            """(() => {
              const m = document.querySelector('#schema-billing');
              const notice = m.querySelector('[data-q-flow-notice]');
              const details = m.querySelector('[data-q-flow-list]');
              return {
                notice: notice.textContent,
                noticeVisible: notice.getBoundingClientRect().height > 0,
                open: details.open,
                listVisible: details.querySelector('[data-q-flow-list-body]').getBoundingClientRect().height > 0,
                entities: details.querySelectorAll('[data-q-schema-list-entity]').length,
                ready: m.hasAttribute('data-q-flow-ready'),
              };
            })()""",
            "d",
        ),
        javaScript=False,
    )
    assert out["failedSteps"] == [] and out["pageErrors"] == []
    assert out["results"]["d"] == {
        "notice": "JavaScript is off, so this data model is shown as a list below.",
        "noticeVisible": True,
        "open": True,
        "listVisible": True,
        "entities": 4,
        "ready": False,
    }


def test_schema_failing_models_show_the_notice_and_the_open_list_while_others_render(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            """(() => {
              const state = (id) => {
                const m = document.querySelector('#' + id);
                const notice = m.querySelector('[data-q-flow-notice]');
                return {
                  ready: m.getAttribute('data-q-flow-ready'),
                  notice: notice && notice.textContent,
                  open: m.querySelector('[data-q-flow-list]').open,
                  svg: !!m.querySelector('[data-q-flow-svg]'),
                  entities: m.querySelectorAll('[data-q-schema-list-entity]').length,
                };
              };
              return { broken: state('schema-broken'), uml: state('schema-uml'), cls: state('schema-class'), billing: state('schema-billing'), small: state('schema-small') };
            })()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["broken"] == {"ready": "error", "notice": "This data model could not be drawn.", "open": True, "svg": False, "entities": 0}
    assert d["uml"]["ready"] == "error" and d["uml"]["notice"] == "This data model could not be drawn."
    assert d["cls"]["ready"] == "true" and d["cls"]["svg"] is True and d["cls"]["open"] is False
    assert d["billing"]["ready"] == "true" and d["billing"]["svg"] is True
    assert d["small"]["ready"] == "true" and d["small"]["open"] is False


def test_schema_models_keep_their_own_focus(schema_page: Path) -> None:
    out = run(
        schema_page,
        {"click": '#schema-small [data-q-schema-entity="author"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              const s = document.querySelector('#schema-small');
              return {{
                billing: {{ lit: entityIds(m, 'data-q-flow-lit'), dim: entityIds(m, 'data-q-flow-dim'), drawer: drawerState(m).open }},
                small: {{ lit: entityIds(s, 'data-q-flow-lit'), selected: entityIds(s, 'data-q-flow-selected'), drawer: drawerState(s).heading }},
              }};
            }})()""",
            "first",
        ),
        {"click": '#schema-billing [data-q-schema-entity="customer"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const s = document.querySelector('#schema-small');
              return {{ selected: entityIds(s, 'data-q-flow-selected'), drawer: drawerState(s).heading }};
            }})()""",
            "second",
        ),
    )
    assert_clean(out)
    first, second = out["results"]["first"], out["results"]["second"]
    assert first["billing"] == {"lit": [], "dim": [], "drawer": False}
    assert first["small"] == {"lit": ["author", "book"], "selected": ["author"], "drawer": "Author"}
    assert second == {"selected": ["author"], "drawer": "Author"}


SCHEMA_BAD_MODELS = {
    "duplicate entity id": {"entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}] * 2},
    "entity id with a dot": {"entities": [{"id": "a.b", "label": "A", "fields": [{"name": "id", "type": "int"}]}]},
    "no entities": {"entities": []},
    "blank label": {"entities": [{"id": "a", "label": "  ", "fields": [{"name": "id", "type": "int"}]}]},
    "no fields": {"entities": [{"id": "a", "label": "A", "fields": []}]},
    "null fields": {"entities": [{"id": "a", "label": "A", "fields": None}]},
    "duplicate field": {"entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}] * 2}]},
    "unknown key": {"entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int", "key": "PRIMARY"}]}]},
    "coordinates": {"entities": [{"id": "a", "label": "A", "x": 1, "fields": [{"name": "id", "type": "int"}]}]},
    "undeclared kind": {"entities": [{"id": "a", "label": "A", "kind": "audit", "fields": [{"name": "id", "type": "int"}]}]},
    "unknown group": {"entities": [{"id": "a", "label": "A", "group": "ledger", "fields": [{"name": "id", "type": "int"}]}]},
    "group loop": {
        "groups": [{"id": "g", "label": "G", "parent": "h"}, {"id": "h", "label": "H", "parent": "g"}],
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}],
    },
    "script in detail": {"entities": [{"id": "a", "label": "A", "detail": "<script>1</script>", "fields": [{"name": "id", "type": "int"}]}]},
    "nine kinds": {
        "kinds": {f"k{i}": 1 for i in range(9)},
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}],
    },
    "methods on an entity": {"entities": [{"id": "a", "label": "A", "methods": [], "fields": [{"name": "id", "type": "int"}]}]},
    "stereotype on an entity": {"entities": [{"id": "a", "label": "A", "stereotype": "enum", "fields": [{"name": "id", "type": "int"}]}]},
    "relationship to an unknown entity": {
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}],
        "relationships": [_schema_rel("a.id", "b.id", "one", "one")],
    },
    "relationship to an unknown field": {
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}],
        "relationships": [_schema_rel("a.id", "a.uuid", "one", "one")],
    },
    "relationship end without a field": {
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}],
        "relationships": [_schema_rel("a", "a.id", "one", "one")],
    },
    "unknown cardinality": {
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}],
        "relationships": [_schema_rel("a.id", "a.id", "many", "one")],
    },
    "blank relationship label": {
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}],
        "relationships": [_schema_rel("a.id", "a.id", "one", "one", " ")],
    },
    "relationship type in a data model": {
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int"}]}],
        "relationships": [{**_schema_rel("a.id", "a.id", "one", "one"), "type": "inherits"}],
    },
}
SCHEMA_MUTUAL_FIELDS = [_schema_field("id", "int", "PK"), _schema_field("a_id", "int", "FK"), _schema_field("b_id", "int", "FK")]
SCHEMA_GOOD_MODELS = {
    "mutual references": {
        "entities": [
            {"id": "a", "label": "A", "fields": SCHEMA_MUTUAL_FIELDS},
            {"id": "b", "label": "B", "fields": SCHEMA_MUTUAL_FIELDS},
        ],
        "relationships": [
            _schema_rel("a.b_id", "b.id", "zero-or-many", "one", "points at"),
            _schema_rel("b.a_id", "a.id", "zero-or-many", "one", "points back"),
            _schema_rel("b.a_id", "a.id", "one", "zero-or-one"),
        ],
    },
    "nested groups with cross-group lines": {
        "groups": [{"id": "outer", "label": "Outer"}, {"id": "inner", "label": "Inner", "parent": "outer"}],
        "entities": [
            {"id": "a", "label": "A", "group": "inner", "fields": SCHEMA_MUTUAL_FIELDS},
            {"id": "b", "label": "B", "group": "outer", "fields": SCHEMA_MUTUAL_FIELDS},
            {"id": "c", "label": "C", "fields": SCHEMA_MUTUAL_FIELDS},
        ],
        "relationships": [
            _schema_rel("a.b_id", "b.id", "zero-or-many", "one"),
            _schema_rel("c.a_id", "a.id", "one-or-many", "zero-or-one", "owns"),
            _schema_rel("c.b_id", "b.id", "one", "one"),
        ],
    },
    "two self-relationships on one card": {
        "entities": [
            {
                "id": "node",
                "label": "Node",
                "fields": [_schema_field("id", "int", "PK"), _schema_field("parent_id", "int", "FK"), _schema_field("prev_id", "int", "FK")],
            }
        ],
        "relationships": [
            _schema_rel("node.parent_id", "node.id", "zero-or-many", "zero-or-one", "parent"),
            _schema_rel("node.prev_id", "node.id", "zero-or-one", "zero-or-one", "previous"),
            _schema_rel("node.id", "node.id", "one", "one"),
        ],
    },
    "two-key field": {"entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int", "key": ["PK", "FK"]}]}]},
    "a label with spaces around": {
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "type": "int", "note": "n"}]}],
        "relationships": [_schema_rel("a.id", "a.id", "one", "zero-or-one", " owns ")],
    },
}


def test_schema_runtime_rejects_the_same_data_the_kit_check_fails(schema_page: Path) -> None:
    cases = {**{name: data for name, data in SCHEMA_BAD_MODELS.items()}, **SCHEMA_GOOD_MODELS}
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              const cases = {json.dumps(cases)};
              const mount = Object.entries(cases).map(([name, data]) => {{
                const el = document.createElement('q-schema');
                el.setAttribute('summary', name);
                const s = document.createElement('script');
                s.type = 'application/json';
                s.textContent = JSON.stringify(data);
                el.appendChild(s);
                document.body.appendChild(el);
                return [name, el];
              }});
              const wait = (el) => new Promise((resolve) => {{
                const t0 = Date.now();
                const poll = () => (el.hasAttribute('data-q-flow-ready') || Date.now() - t0 > 8000 ? resolve(el.getAttribute('data-q-flow-ready')) : setTimeout(poll, 20));
                poll();
              }});
              return Object.fromEntries(await Promise.all(mount.map(async ([name, el]) => [name, await wait(el)])));
            }})()""",
            "ready",
        ),
    )
    assert_clean(out)
    ready = out["results"]["ready"]
    assert {name: ready[name] for name in SCHEMA_BAD_MODELS} == {name: "error" for name in SCHEMA_BAD_MODELS}
    assert {name: ready[name] for name in SCHEMA_GOOD_MODELS} == {name: "true" for name in SCHEMA_GOOD_MODELS}


SCHEMA_MOUNT_JS = """
  const mountSchema = (data, opts = {}) => {
    const el = document.createElement('q-schema');
    if (opts.summary !== null) el.setAttribute('summary', opts.summary === undefined ? 'A model' : opts.summary);
    if (opts.notation) el.setAttribute('notation', opts.notation);
    const s = document.createElement('script');
    s.setAttribute('type', opts.type || 'application/json');
    s.textContent = JSON.stringify(data);
    el.appendChild(s);
    document.body.appendChild(el);
    return el;
  };
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const settle = (el) => new Promise((resolve) => {
    const t0 = Date.now();
    const poll = () => (el.hasAttribute('data-q-flow-ready') || Date.now() - t0 > 8000 ? resolve(el.getAttribute('data-q-flow-ready')) : setTimeout(poll, 20));
    poll();
  });
  const failureState = (el) => {
    const notice = el.querySelector('[data-q-flow-notice]');
    const list = el.querySelector('[data-q-flow-list]');
    return {
      ready: el.getAttribute('data-q-flow-ready'),
      notice: notice && notice.textContent,
      svg: !!el.querySelector('[data-q-flow-svg]'),
      open: !!list && list.open,
      title: list && list.querySelector('summary') && list.querySelector('summary').textContent,
      entities: el.querySelectorAll('[data-q-schema-list-entity]').length,
    };
  };
"""

SCHEMA_ODD_IDS = ["constructor", "__proto__", "toString"]


def _schema_odd_id_model() -> dict:
    fields = [_schema_field("id", "int", "PK"), _schema_field("self_id", "int", "FK"), _schema_field("next_id", "int", "FK")]
    entities = [{"id": eid, "label": eid, "fields": fields} for eid in SCHEMA_ODD_IDS]
    relationships = []
    for i, eid in enumerate(SCHEMA_ODD_IDS):
        relationships.append(_schema_rel(f"{eid}.self_id", f"{eid}.id", "zero-or-many", "one", "self"))
        relationships.append(_schema_rel(f"{eid}.next_id", f"{SCHEMA_ODD_IDS[(i + 1) % 3]}.id", "zero-or-many", "one", "next"))
    return {"entities": entities, "relationships": relationships}


def test_schema_entity_ids_named_like_object_properties_still_draw_and_focus(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const el = mountSchema({json.dumps(_schema_odd_id_model())});
              el.id = 'schema-odd';
              const ready = await settle(el);
              const focusOn = async (id) => {{
                el.querySelector('[data-q-schema-entity="' + id + '"]').dispatchEvent(new MouseEvent('click', {{ bubbles: true }}));
                await sleep(50);
                const d = el.querySelector('[data-q-flow-drawer]');
                return {{
                  selected: [...el.querySelectorAll('[data-q-schema-entity][data-q-flow-selected]')].map((e) => e.getAttribute('data-q-schema-entity')),
                  heading: d.querySelector('h3') && d.querySelector('h3').textContent,
                  open: !d.hasAttribute('data-q-inactive'),
                }};
              }};
              return {{
                ready,
                cards: [...el.querySelectorAll('[data-q-schema-entity]')].map((e) => e.getAttribute('data-q-schema-entity')),
                rels: el.querySelectorAll('[data-q-schema-rel]').length,
                focusConstructor: await focusOn('constructor'),
                focusProto: await focusOn('__proto__'),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert sorted(d["cards"]) == sorted(SCHEMA_ODD_IDS)
    assert d["rels"] == 6
    assert d["focusConstructor"] == {"selected": ["constructor"], "heading": "constructor", "open": True}
    assert d["focusProto"] == {"selected": ["__proto__"], "heading": "__proto__", "open": True}


def test_schema_endpoints_whose_ids_and_field_names_hold_colons_keep_their_own_ports(schema_page: Path) -> None:
    model = {
        "entities": [
            {"id": "a:b", "label": "AB", "fields": [_schema_field("id", "int", "PK"), _schema_field("c", "int", "FK")]},
            {
                "id": "a",
                "label": "A",
                "fields": [_schema_field("id", "int", "PK"), _schema_field("x", "text"), _schema_field("b:c", "int", "FK")],
            },
            {"id": "z", "label": "Z", "fields": [_schema_field("id", "int", "PK")]},
        ],
        "relationships": [
            _schema_rel("a:b.c", "z.id", "zero-or-many", "one"),
            _schema_rel("a.b:c", "z.id", "zero-or-many", "one"),
        ],
    }
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              {SCHEMA_GEOMETRY_JS}
              const el = mountSchema({json.dumps(model)});
              const ready = await settle(el);
              const ends = (idx, fromId, fromField) => {{
                const pts = pathPoints(lineOf(relAt(el, idx)).getAttribute('d'));
                const first = pts[0], last = pts[pts.length - 1];
                const zBox = cardBox(el, 'z'), fBox = cardBox(el, fromId);
                const segs = pts.slice(1).map((p, i) => Math.abs(p.x - pts[i].x) < 1 || Math.abs(p.y - pts[i].y) < 1);
                return {{
                  startDy: Math.abs(first.y - rowY(el, 'z', 'id')),
                  endDy: Math.abs(last.y - rowY(el, fromId, fromField)),
                  startX: first.x - (zBox.x + zBox.width),
                  endX: last.x - fBox.x,
                  orthogonal: segs.every(Boolean),
                }};
              }};
              return {{ ready, first: ends(0, 'a:b', 'c'), second: ends(1, 'a', 'b:c') }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    for key in ("first", "second"):
        got = d[key]
        assert got["startDy"] <= 1 and got["endDy"] <= 1, (key, got)
        assert abs(got["startX"]) <= 1 and abs(got["endX"]) <= 1, (key, got)
        assert got["orthogonal"] is True, (key, got)


def test_schema_fold_ignores_a_related_field_whose_joined_id_and_name_collide_with_another(schema_page: Path) -> None:
    plain = [f"p{i}" for i in range(1, 9)]
    model = {
        "entities": [
            {"id": "a", "label": "A", "fields": [*[_schema_field(n, "text") for n in plain], _schema_field("b\u0000c", "text")]},
            {"id": "a\u0000b", "label": "AB", "fields": [_schema_field("id", "int", "PK"), _schema_field("c", "int", "FK")]},
            {"id": "z", "label": "Z", "fields": [_schema_field("id", "int", "PK")]},
        ],
        "relationships": [_schema_rel("a\u0000b.c", "z.id", "zero-or-many", "one")],
    }
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const el = mountSchema({json.dumps(model)});
              const ready = await settle(el);
              const c = el.querySelector('[data-q-schema-entity="a"]');
              return {{
                ready,
                names: [...c.querySelectorAll('[data-q-schema-field]')].map((r) => r.getAttribute('data-q-schema-field')),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert d["names"] == plain
    assert d["names"][7] == "p8"


def test_schema_ids_named_like_the_layout_graph_keep_every_card_and_line(schema_page: Path) -> None:
    ids = ["root", "rel0", "port:root:id:WEST"]
    fields = [_schema_field("id", "int", "PK"), _schema_field("ref", "int", "FK")]
    entities = [{"id": eid, "label": eid, "fields": fields} for eid in ids]
    entities[0]["group"] = "n0"
    model = {
        "groups": [{"id": "n0", "label": "Group"}],
        "entities": entities,
        "relationships": [
            _schema_rel(f"{ids[i]}.ref", f"{ids[(i + 1) % 3]}.id", "zero-or-many", "one") for i in range(3)
        ],
    }
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const el = mountSchema({json.dumps(model)});
              const ready = await settle(el);
              return {{
                ready,
                cards: [...el.querySelectorAll('[data-q-schema-entity]')].map((e) => e.getAttribute('data-q-schema-entity')).sort(),
                rels: el.querySelectorAll('[data-q-schema-rel]').length,
                groups: el.querySelectorAll('[data-q-flow-group]').length,
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert d["cards"] == sorted(ids) and d["rels"] == 3 and d["groups"] == 1


def test_schema_a_pending_layout_never_replaces_a_later_failure(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const valid = {json.dumps(SCHEMA_SMALL_DATA)};
              const invalid = mountSchema(valid);
              invalid.querySelector('script').textContent = '{{ not json';
              const toClass = mountSchema(valid);
              const script = toClass.querySelector('script');
              script.textContent = JSON.stringify({json.dumps(SCHEMA_CLASS_LOOP_DATA)}).replace('dependency', 'inherits');
              toClass.setAttribute('notation', 'class');
              await sleep(1500);
              return {{ invalid: failureState(invalid), toClass: failureState(toClass) }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["invalid"]["ready"] == "error" and d["invalid"]["svg"] is False
    assert d["invalid"]["notice"] == "This data model could not be drawn."
    assert d["toClass"]["ready"] == "error" and d["toClass"]["svg"] is False
    assert d["toClass"]["notice"] == "This class diagram could not be drawn."


def test_schema_missing_or_blank_summary_is_a_parse_failure(schema_page: Path) -> None:
    html = schema_page.read_text(encoding="utf-8")
    attr = '<q-schema id="schema-small" summary="Authors and their books.">'
    assert html.count(attr) == 1
    page = schema_page.with_name("schema-nosummary.html")
    page.write_text(html.replace(attr, '<q-schema id="schema-small">'), encoding="utf-8")
    out = run(
        page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const blank = mountSchema({json.dumps(SCHEMA_SMALL_DATA)}, {{ summary: '  ' }});
              const missing = mountSchema({json.dumps(SCHEMA_SMALL_DATA)}, {{ summary: null }});
              await Promise.all([settle(blank), settle(missing)]);
              return {{
                built: failureState(document.querySelector('#schema-small')),
                blank: failureState(blank),
                missing: failureState(missing),
                billing: document.querySelector('#schema-billing').getAttribute('data-q-flow-ready'),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    for key in ("built", "blank", "missing"):
        assert d[key]["ready"] == "error" and d[key]["svg"] is False and d[key]["entities"] == 0, key
    assert d["billing"] == "true"


def test_schema_json_script_type_is_trimmed_and_case_folded_like_the_kit_check(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const el = mountSchema({json.dumps(SCHEMA_SMALL_DATA)}, {{ type: ' Application/JSON ' }});
              const first = await settle(el);
              el.querySelector('script').textContent = '{{ not json';
              await sleep(200);
              return {{ first, afterEdit: failureState(el) }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["first"] == "true"
    assert d["afterEdit"]["ready"] == "error" and d["afterEdit"]["svg"] is False


def test_schema_a_model_that_stops_parsing_empties_the_list_but_keeps_it_open(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const el = mountSchema({json.dumps(SCHEMA_SMALL_DATA)});
              await settle(el);
              const before = failureState(el);
              el.querySelector('script').textContent = '{{ not json';
              await sleep(200);
              return {{ before, after: failureState(el) }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["before"]["ready"] == "true" and d["before"]["entities"] == 2
    after = d["after"]
    assert after["ready"] == "error" and after["entities"] == 0 and after["open"] is True
    assert after["title"] == "Data model as a list"
    assert after["notice"] == "This data model could not be drawn."


def test_schema_data_that_never_parsed_still_gets_a_titled_open_list(schema_page: Path) -> None:
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const mountBroken = (notation) => {{
                const el = document.createElement('q-schema');
                el.setAttribute('summary', 'x');
                if (notation) el.setAttribute('notation', notation);
                const s = document.createElement('script');
                s.setAttribute('type', 'application/json');
                s.textContent = '{{not json';
                el.appendChild(s);
                document.body.appendChild(el);
                return el;
              }};
              const er = mountBroken(null);
              const cls = mountBroken('class');
              const toClass = mountSchema({json.dumps(SCHEMA_SMALL_DATA)});
              const toEr = mountSchema({json.dumps(SCHEMA_CLASS_DATA)}, {{ notation: 'class' }});
              await Promise.all([settle(er), settle(cls), settle(toClass), settle(toEr)]);
              toClass.querySelector('script').textContent = '{{not json';
              toClass.setAttribute('notation', 'class');
              toEr.querySelector('script').textContent = '{{not json';
              toEr.removeAttribute('notation');
              await sleep(300);
              const bodies = (el) => el.querySelectorAll('[data-q-flow-list-body]').length;
              return {{
                er: {{ ...failureState(er), bodies: bodies(er), lists: er.querySelectorAll('[data-q-flow-list]').length }},
                cls: {{ ...failureState(cls), bodies: bodies(cls), lists: cls.querySelectorAll('[data-q-flow-list]').length }},
                toClass: {{ ...failureState(toClass), bodies: bodies(toClass), lists: toClass.querySelectorAll('[data-q-flow-list]').length }},
                toEr: {{ ...failureState(toEr), bodies: bodies(toEr), lists: toEr.querySelectorAll('[data-q-flow-list]').length }},
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    for key, title, noun in (
        ("er", "Data model as a list", "data model"),
        ("cls", "Class diagram as a list", "class diagram"),
        ("toClass", "Class diagram as a list", "class diagram"),
        ("toEr", "Data model as a list", "data model"),
    ):
        got = d[key]
        assert got["ready"] == "error" and got["svg"] is False, key
        assert got["notice"] == f"This {noun} could not be drawn.", key
        assert got["open"] is True and got["title"] == title, key
        assert got["entities"] == 0 and got["bodies"] == 1 and got["lists"] == 1, key


def test_schema_thousands_of_nested_groups_reach_a_ready_state_without_a_page_error(schema_page: Path) -> None:
    depth = 4000
    groups = [{"id": f"g{i}", "label": f"G{i}", **({"parent": f"g{i - 1}"} if i else {})} for i in range(depth)]
    model = {
        "groups": groups,
        "entities": [{"id": "deep", "label": "Deep", "group": f"g{depth - 1}", "fields": [_schema_field("id", "int", "PK")]}],
    }
    out = run(
        schema_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const el = mountSchema({json.dumps(model)});
              const ready = await settle(el);
              await sleep(300);
              el.getBoundingClientRect();
              let nesting = 0;
              const stack = [[el, 0]];
              while (stack.length) {{
                const [node, level] = stack.pop();
                nesting = Math.max(nesting, level);
                for (const child of node.children) stack.push([child, level + 1]);
              }}
              return {{ ready, nesting, state: failureState(el), groups: el.querySelectorAll('[data-q-flow-list-group]').length }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] in ("true", "error")
    assert d["groups"] == depth and d["nesting"] < 300
    if d["ready"] == "error":
        assert d["state"]["open"] is True and d["state"]["notice"] == "This data model could not be drawn."


def test_schema_click_on_blank_panel_space_clears_entity_focus_and_closes_the_drawer(schema_page: Path) -> None:
    out = run(
        schema_page,
        {"click": '#schema-billing [data-q-schema-entity="charge"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-billing');
              const focused = {{ selected: entityIds(m, 'data-q-flow-selected'), drawerOpen: drawerState(m).open }};
              m.scrollIntoView();
              const box = m.querySelector('[data-q-flow-group="billing"] [data-q-flow-group-box]');
              const r = box.getBoundingClientRect();
              let hit = null;
              for (let y = r.top + 6; y < r.bottom - 4 && !hit; y += 6) {{
                for (let x = r.left + 6; x < r.right - 4 && !hit; x += 6) {{
                  if (document.elementFromPoint(x, y) === box) hit = box;
                }}
              }}
              if (hit) hit.dispatchEvent(new MouseEvent('click', {{ bubbles: true }}));
              return {{ found: !!hit, focused, after: {{ selected: entityIds(m, 'data-q-flow-selected'), lit: entityIds(m, 'data-q-flow-lit'), drawerOpen: drawerState(m).open }} }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["found"] is True
    assert d["focused"] == {"selected": ["charge"], "drawerOpen": True}
    assert d["after"] == {"selected": [], "lit": [], "drawerOpen": False}


# --- q-schema, class notation -----------------------------------------------------------------


def _class_attr(name: str, ftype: str | None = None, visibility: str | None = "private", static: bool = False) -> dict:
    attr: dict = {"name": name}
    if ftype:
        attr["type"] = ftype
    if visibility:
        attr["visibility"] = visibility
    if static:
        attr["static"] = True
    return attr


def _class_method(signature: str, visibility: str | None = "private", abstract: bool = False) -> dict:
    method: dict = {"signature": signature}
    if visibility:
        method["visibility"] = visibility
    if abstract:
        method["abstract"] = True
    return method


SCHEMA_PARSER_DATA = {
    "kinds": {"api": 1, "internals": 3},
    "entities": [
        {"id": "parser", "label": "Parser", "kind": "api", "stereotype": "interface", "methods": [_class_method("parse(src: str) -> Ast", "public")]},
        {
            "id": "recursivedescentparser",
            "label": "RecursiveDescentParser",
            "kind": "internals",
            "fields": [
                _class_attr("max_depth", "int", "public", static=True),
                _class_attr("lexer", "Lexer"),
                _class_attr("pos", "int"),
                _class_attr("depth", "int"),
                _class_attr("errors", "list"),
                _class_attr("options", "dict"),
            ],
            "methods": [
                _class_method("parse(src: str) -> Ast", "public"),
                _class_method("expr() -> Ast"),
                _class_method("term() -> Ast"),
                _class_method("factor() -> Ast"),
                _class_method("expect(kind: TokenKind) -> Token"),
                _class_method("peek() -> Token"),
                _class_method("error(msg: str)"),
            ],
        },
        {
            "id": "lexer",
            "label": "Lexer",
            "kind": "internals",
            "fields": [_class_attr("src", "str"), _class_attr("pos", "int")],
            "methods": [_class_method("next() -> Token", "public"), _class_method("peek() -> Token", "public")],
        },
        {
            "id": "token",
            "label": "Token",
            "kind": "internals",
            "fields": [_class_attr("kind", "TokenKind", "public"), _class_attr("text", "str", "public"), _class_attr("line", "int", "public")],
        },
        {
            "id": "tokenkind",
            "label": "TokenKind",
            "kind": "internals",
            "stereotype": "enum",
            "fields": [_class_attr(v, None, None) for v in ("NUMBER", "IDENT", "PLUS", "LPAREN", "RPAREN", "EOF")],
        },
        {
            "id": "ast",
            "label": "Ast",
            "kind": "api",
            "stereotype": "abstract",
            "methods": [_class_method("accept(v: Visitor)", "public", abstract=True)],
        },
        {
            "id": "binaryexpr",
            "label": "BinaryExpr",
            "kind": "api",
            "fields": [_class_attr("left", "Ast", "public"), _class_attr("op", "TokenKind", "public"), _class_attr("right", "Ast", "public")],
        },
    ],
    "relationships": [
        {"from": "recursivedescentparser", "to": "parser", "type": "implements"},
        {"from": "recursivedescentparser", "to": "lexer", "type": "composition", "to_mult": "1"},
        {"from": "lexer", "to": "token", "type": "dependency", "label": "produces"},
        {"from": "token", "to": "tokenkind", "type": "association", "directed": True},
        {"from": "binaryexpr", "to": "ast", "type": "inherits"},
        {"from": "binaryexpr", "to": "ast", "type": "aggregation", "to_mult": "2", "label": "operands"},
        {"from": "parser", "to": "ast", "type": "dependency", "label": "returns"},
    ],
}

SCHEMA_CLASS_SELF_DATA = {
    "entities": [
        {"id": "node", "label": "Node", "fields": [_class_attr("value", "int")], "methods": [_class_method("walk()", "public")]},
        {"id": "leaf", "label": "Leaf", "methods": [_class_method("value() -> int", "public")]},
        {"id": "root", "label": "Root", "methods": [_class_method("build()", "public")]},
    ],
    "relationships": [
        {"from": "node", "to": "node", "type": "aggregation", "from_mult": "0..1", "to_mult": "*", "label": "children"},
        {"from": "leaf", "to": "node", "type": "inherits"},
        {"from": "root", "to": "node", "type": "composition", "to_mult": "1"},
    ],
}

SCHEMA_CLASS_LOOP_SUMMARY = "Two classes that will inherit each other."
SCHEMA_CLASS_LOOP_DATA = {
    "entities": [
        {"id": "a", "label": "A", "methods": [_class_method("run()", "public")]},
        {"id": "b", "label": "B", "methods": [_class_method("run()", "public")]},
    ],
    "relationships": [{"from": "a", "to": "b", "type": "inherits"}, {"from": "b", "to": "a", "type": "dependency"}],
}

SCHEMA_CLASS_PAGE = (
    _schema_tag(
        "schema-parser",
        "The parser's public interface, its recursive descent implementation and the AST it returns.",
        SCHEMA_PARSER_DATA,
        notation="class",
    )
    + _schema_tag("schema-class-self", "A tree node that contains nodes.", SCHEMA_CLASS_SELF_DATA, notation="class")
    + _schema_tag("schema-small", "Authors and their books.", SCHEMA_SMALL_DATA)
    + (
        f'<q-schema id="schema-class-loop" summary="{SCHEMA_CLASS_LOOP_SUMMARY}" notation="class">'
        f'<script type="application/json">{json.dumps(SCHEMA_CLASS_LOOP_DATA, separators=(",", ":"))}</script></q-schema>\n'
    )
)


@pytest.fixture(scope="module")
def schema_class_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-schema-class")
    src = work / "schema-class.src.html"
    src.write_text(HEADER + SCHEMA_CLASS_PAGE, encoding="utf-8")
    built = _build(src, work / "schema-class.html")
    # the inheritance loop is edited in after the build so the build-time check never sees it
    html = built.read_text(encoding="utf-8")
    loop_edge = '"type":"dependency"'
    assert html.count(loop_edge) == 1
    built.write_text(html.replace(loop_edge, '"type":"inherits"'), encoding="utf-8")
    return built


SCHEMA_CLASS_UML_MARKS = [
    # (index, from entity, to entity, from mark, to mark, dashed, from mult, to mult, label)
    (0, "recursivedescentparser", "parser", "none", "triangle", True, None, None, None),
    (1, "recursivedescentparser", "lexer", "diamond-filled", "none", False, None, "1", None),
    (2, "lexer", "token", "none", "arrow", True, None, None, "produces"),
    (3, "token", "tokenkind", "none", "arrow", False, None, None, None),
    (4, "binaryexpr", "ast", "none", "triangle", False, None, None, None),
    (5, "binaryexpr", "ast", "diamond-hollow", "none", False, None, "2", "operands"),
    (6, "parser", "ast", "none", "arrow", True, None, None, "returns"),
]


def test_schema_class_parser_draws_seven_compartmented_cards_with_stereotypes_and_modifiers(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              const header = (id) => card(m, id).querySelector('[data-q-schema-stereo]');
              const midY = (id) => {{ const b = cardBox(m, id); return b.y + b.height / 2; }};
              const rowText = (id, attr, key) => card(m, id).querySelector('[' + attr + '="' + key + '"] text');
              const style = (el) => getComputedStyle(el);
              const rules = (id) => card(m, id).querySelectorAll('[data-q-schema-rule]').length;
              return {{
                ready: m.getAttribute('data-q-flow-ready'),
                cards: [...m.querySelectorAll('[data-q-schema-entity]')].map((e) => e.getAttribute('data-q-schema-entity')),
                stereotypes: Object.fromEntries([...m.querySelectorAll('[data-q-schema-stereotype]')].map((e) => [e.getAttribute('data-q-schema-entity'), e.getAttribute('data-q-schema-stereotype')])),
                parserHeader: header('parser').textContent,
                astHeader: header('ast').textContent,
                enumHeader: header('tokenkind').textContent,
                lexerHeader: header('lexer'),
                enumRows: [...card(m, 'tokenkind').querySelectorAll('[data-q-schema-field]')].map((r) => r.querySelector('text').textContent),
                labels: Object.fromEntries([...m.querySelectorAll('[data-q-schema-entity]')].map((e) => [e.getAttribute('data-q-schema-entity'), e.querySelector('[data-q-schema-label]').textContent])),
                parserAbove: midY('parser') < midY('recursivedescentparser'),
                astAbove: midY('ast') < midY('binaryexpr'),
                staticUnderlined: style(rowText('recursivedescentparser', 'data-q-schema-field', 'max_depth')).textDecorationLine.includes('underline'),
                plainNotUnderlined: !style(rowText('recursivedescentparser', 'data-q-schema-field', 'lexer')).textDecorationLine.includes('underline'),
                abstractItalic: style(rowText('ast', 'data-q-schema-method', '0')).fontStyle,
                plainNotItalic: style(rowText('lexer', 'data-q-schema-method', '0')).fontStyle,
                texts: [card(m, 'recursivedescentparser').querySelector('[data-q-schema-field="max_depth"] text').textContent,
                        card(m, 'recursivedescentparser').querySelector('[data-q-schema-field="lexer"] text').textContent,
                        card(m, 'ast').querySelector('[data-q-schema-method="0"] text').textContent,
                        card(m, 'token').querySelector('[data-q-schema-field="line"] text').textContent],
                rules: rules('lexer'),
                accents: ['parser', 'lexer'].map((id) => card(m, id).querySelector('[data-q-schema-accent]').getAttribute('fill')),
                listOpen: m.querySelector('[data-q-flow-list]').open,
                ariaLexer: card(m, 'lexer').getAttribute('aria-label'),
                noun: m.querySelector('[data-q-flow-controls]').getAttribute('aria-label'),
                drawerLabel: m.querySelector('[data-q-flow-drawer]').getAttribute('aria-label'),
                expandLabel: m.querySelector('[data-q-flow-action="expand"]').getAttribute('aria-label'),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert d["cards"] == ["parser", "recursivedescentparser", "lexer", "token", "tokenkind", "ast", "binaryexpr"]
    assert d["stereotypes"] == {"parser": "interface", "tokenkind": "enum", "ast": "abstract"}
    assert "«interface»" in d["parserHeader"] and "«abstract»" in d["astHeader"] and "«enum»" in d["enumHeader"]
    assert d["lexerHeader"] is None
    assert d["enumRows"] == ["NUMBER", "IDENT", "PLUS", "LPAREN", "RPAREN", "EOF"]
    assert d["labels"]["parser"] == "Parser" and d["labels"]["recursivedescentparser"] == "RecursiveDescentParser"
    assert d["parserAbove"] is True
    assert d["astAbove"] is True
    assert d["staticUnderlined"] is True and d["plainNotUnderlined"] is True
    assert d["abstractItalic"] == "italic" and d["plainNotItalic"] == "normal"
    assert d["texts"] == ["+ max_depth: int", "- lexer: Lexer", "+ accept(v: Visitor)", "+ line: int"]
    assert d["rules"] == 1
    assert d["accents"] == ["var(--q-color-chart-1)", "var(--q-color-chart-3)"]
    assert d["listOpen"] is False
    assert d["ariaLexer"] == "Lexer, internals, 4 members, 2 relationships"
    assert d["noun"] == "Diagram controls"
    assert d["drawerLabel"] == "Class details"
    assert d["expandLabel"] == "Expand diagram"


def test_schema_class_lines_run_between_the_cards_with_uml_marks_multiplicities_and_labels(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              const onBorder = (p, id) => {{
                const b = cardBox(m, id);
                const inX = p.x >= b.x - 1 && p.x <= b.x + b.width + 1;
                const inY = p.y >= b.y - 1 && p.y <= b.y + b.height + 1;
                const edge = (Math.abs(p.x - b.x) <= 1 || Math.abs(p.x - b.x - b.width) <= 1) && inY
                  || (Math.abs(p.y - b.y) <= 1 || Math.abs(p.y - b.y - b.height) <= 1) && inX;
                return edge;
              }};
              return {json.dumps(SCHEMA_CLASS_UML_MARKS)}.map(([idx, fromE, toE]) => {{
                const rel = relAt(m, idx);
                const line = lineOf(rel);
                const pts = pathPoints(line.getAttribute('d'));
                const first = pts[0], last = pts[pts.length - 1];
                const mult = (side) => {{
                  const el = rel.querySelector('[data-q-schema-mult="' + side + '"]');
                  if (!el) return null;
                  const x = +el.getAttribute('x'), y = +el.getAttribute('y');
                  return {{ text: el.textContent, nearFrom: Math.hypot(x - first.x, y - first.y), nearTo: Math.hypot(x - last.x, y - last.y) }};
                }};
                const lbl = rel.querySelector('[data-q-schema-rel-label]');
                return {{
                  from: rel.getAttribute('data-q-schema-from'),
                  to: rel.getAttribute('data-q-schema-to'),
                  fromMark: rel.getAttribute('data-q-schema-from-mark'),
                  toMark: rel.getAttribute('data-q-schema-to-mark'),
                  startMarker: markKind(m, line.getAttribute('marker-start')),
                  endMarker: markKind(m, line.getAttribute('marker-end')),
                  dash: line.getAttribute('stroke-dasharray'),
                  firstOnFrom: onBorder(first, fromE),
                  lastOnTo: onBorder(last, toE),
                  fromMult: mult('from'),
                  toMult: mult('to'),
                  label: lbl && lbl.textContent,
                }};
              }});
            }})()""",
            "rels",
        ),
    )
    assert_clean(out)
    for (idx, from_e, to_e, from_mark, to_mark, dashed, from_mult, to_mult, label), got in zip(SCHEMA_CLASS_UML_MARKS, out["results"]["rels"]):
        where = f"rel {idx}"
        assert (got["from"], got["to"]) == (from_e, to_e), where
        assert (got["fromMark"], got["toMark"]) == (from_mark, to_mark), where
        # the path runs from the from end to the to end, so the markers sit where the data says
        assert got["startMarker"] == (None if from_mark == "none" else from_mark), where
        assert got["endMarker"] == (None if to_mark == "none" else to_mark), where
        assert bool(got["dash"]) is dashed, where
        assert got["firstOnFrom"] and got["lastOnTo"], where
        assert (got["fromMult"] and got["fromMult"]["text"]) == from_mult, where
        assert (got["toMult"] and got["toMult"]["text"]) == to_mult, where
        assert got["label"] == label, where
        if to_mult:
            assert got["toMult"]["nearTo"] < got["toMult"]["nearFrom"] and got["toMult"]["nearTo"] < 48, where


def test_schema_class_card_fold_shows_four_and_four_with_a_more_row_and_short_cards_show_everything(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              const state = (id) => {{
                const c = card(m, id);
                const more = c.querySelectorAll('[data-q-schema-more]');
                const rows = [...c.querySelectorAll('[data-q-schema-field], [data-q-schema-method]')];
                const lastRow = Math.max(...rows.map((r) => Number(r.getAttribute('data-q-schema-row-y'))));
                return {{
                  attrs: [...c.querySelectorAll('[data-q-schema-field]')].map((r) => r.getAttribute('data-q-schema-field')),
                  methods: [...c.querySelectorAll('[data-q-schema-method]')].map((r) => r.getAttribute('data-q-schema-method')),
                  more: [...more].map((e) => e.textContent),
                  moreBelow: more.length ? Number(more[0].querySelector('[data-q-schema-row-bg]').getAttribute('y')) >= lastRow : null,
                  inside: rows.every((r) => Number(r.getAttribute('data-q-schema-row-y')) < cardBox(m, id).y + cardBox(m, id).height),
                }};
              }};
              return {{ rdp: state('recursivedescentparser'), lexer: state('lexer') }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["rdp"]["attrs"] == ["max_depth", "lexer", "pos", "depth"]
    assert d["rdp"]["methods"] == ["0", "1", "2", "3"]
    assert d["rdp"]["more"] == ["+5 more"] and d["rdp"]["moreBelow"] is True and d["rdp"]["inside"] is True
    assert d["lexer"] == {"attrs": ["src", "pos"], "methods": ["0", "1"], "more": [], "moreBelow": None, "inside": True}


def test_schema_class_focus_lights_the_card_its_lines_and_neighbours_and_the_drawer_lists_members_and_buttons(
    schema_class_page: Path,
) -> None:
    out = run(
        schema_class_page,
        {"click": '#schema-parser [data-q-schema-entity="lexer"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              const d = m.querySelector('[data-q-flow-drawer]');
              return {{
                lit: entityIds(m, 'data-q-flow-lit'),
                dim: entityIds(m, 'data-q-flow-dim'),
                selected: entityIds(m, 'data-q-flow-selected'),
                litRels: relIdx(m, 'data-q-flow-lit'),
                dimRels: relIdx(m, 'data-q-flow-dim'),
                drawer: drawerState(m),
                methods: [...d.querySelectorAll('[data-q-schema-drawer-method]')].map((e) => e.textContent),
                live: m.querySelector('[data-q-flow-live]').textContent,
              }};
            }})()""",
            "d",
        ),
        {"click": '#schema-parser [data-q-flow-edge-btn][data-q-flow-target="token"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              return {{ selected: entityIds(m, 'data-q-flow-selected'), buttons: drawerState(m).buttons, fields: drawerState(m).fields }};
            }})()""",
            "next",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["lit"] == ["lexer", "recursivedescentparser", "token"]
    assert d["dim"] == ["ast", "binaryexpr", "parser", "tokenkind"]
    assert d["selected"] == ["lexer"]
    assert d["litRels"] == [1, 2] and d["dimRels"] == [0, 3, 4, 5, 6]
    assert d["drawer"]["open"] is True and d["drawer"]["heading"] == "Lexer"
    assert d["drawer"]["fields"] == ["private src: str", "private pos: int"]
    assert d["methods"] == ["public next() -> Token", "public peek() -> Token"]
    assert d["drawer"]["buttons"] == ["part of: RecursiveDescentParser", "produces: Token"]
    assert d["live"] == "Lexer, internals, 4 members, 2 relationships"
    nxt = out["results"]["next"]
    assert nxt["selected"] == ["token"]
    assert nxt["buttons"] == ["used by: Lexer", "associated with: TokenKind"]
    assert nxt["fields"] == ["public kind: TokenKind", "public text: str", "public line: int"]


def test_schema_class_drawer_says_stereotype_static_and_abstract_in_words_and_reverse_verbs(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        {"click": '#schema-parser [data-q-schema-entity="ast"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              const d = m.querySelector('[data-q-flow-drawer]');
              const st = d.querySelector('[data-q-schema-drawer-stereotype]');
              return {{ stereotype: st && st.textContent, methods: [...d.querySelectorAll('[data-q-schema-drawer-method]')].map((e) => e.textContent), buttons: drawerState(m).buttons }};
            }})()""",
            "ast",
        ),
        {"click": '#schema-parser [data-q-schema-entity="recursivedescentparser"]'},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              const d = m.querySelector('[data-q-flow-drawer]');
              return {{
                fields: drawerState(m).fields,
                methods: [...d.querySelectorAll('[data-q-schema-drawer-method]')].map((e) => e.textContent),
                buttons: drawerState(m).buttons,
              }};
            }})()""",
            "rdp",
        ),
    )
    assert_clean(out)
    ast, rdp = out["results"]["ast"], out["results"]["rdp"]
    assert ast["stereotype"] == "«abstract»"
    assert ast["methods"] == ["public abstract accept(v: Visitor)"]
    assert ast["buttons"] == ["inherited by: BinaryExpr", "aggregated by: BinaryExpr", "used by: Parser"]
    assert rdp["fields"][0] == "public static max_depth: int" and len(rdp["fields"]) == 6
    assert len(rdp["methods"]) == 7 and rdp["methods"][6] == "private error(msg: str)"
    assert rdp["buttons"] == ["implements: Parser", "composed of: Lexer"]


def test_schema_class_more_row_click_focuses_the_class_and_lists_every_member(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        {"click": "#schema-parser [data-q-schema-more]"},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              const d = m.querySelector('[data-q-flow-drawer]');
              return {{ selected: entityIds(m, 'data-q-flow-selected'), fields: drawerState(m).fields.length, methods: d.querySelectorAll('[data-q-schema-drawer-method]').length }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {"selected": ["recursivedescentparser"], "fields": 6, "methods": 7}


def test_schema_class_self_relationship_is_a_loop_off_the_east_edge_that_keeps_neighbours_clear(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-class-self');
              const rel = relAt(m, 0);
              const pts = pathPoints(lineOf(rel).getAttribute('d'));
              const b = cardBox(m, 'node');
              const xs = pts.map((p) => p.x);
              const lbl = rel.querySelector('[data-q-schema-rel-label]');
              const lb = lbl.getBBox();
              const others = ['leaf', 'root'].map((id) => cardBox(m, id));
              const loopRight = Math.max(...xs, lb.x + lb.width);
              const clashes = others.filter((o) => o.x < loopRight + 4 && o.x + o.width > b.x + b.width && o.y < b.y + b.height && o.y + o.height > b.y);
              const edgeEnds = [0, 1, 2].map((i) => {{
                const p = pathPoints(lineOf(relAt(m, i)).getAttribute('d'));
                return [p[0], p[p.length - 1]];
              }});
              const onAnyBorder = (p) => ['node', 'leaf', 'root'].some((id) => {{
                const c = cardBox(m, id);
                const inX = p.x >= c.x - 1 && p.x <= c.x + c.width + 1, inY = p.y >= c.y - 1 && p.y <= c.y + c.height + 1;
                return ((Math.abs(p.x - c.x) <= 1 || Math.abs(p.x - c.x - c.width) <= 1) && inY) || ((Math.abs(p.y - c.y) <= 1 || Math.abs(p.y - c.y - c.height) <= 1) && inX);
              }});
              return {{
                ready: m.getAttribute('data-q-flow-ready'),
                startsOnEast: Math.abs(pts[0].x - (b.x + b.width)) <= 1,
                endsOnEast: Math.abs(pts[pts.length - 1].x - (b.x + b.width)) <= 1,
                out: Math.max(...xs) - (b.x + b.width),
                distinctRows: Math.abs(pts[0].y - pts[pts.length - 1].y) > 4,
                marks: [rel.getAttribute('data-q-schema-from-mark'), rel.getAttribute('data-q-schema-to-mark')],
                mults: [rel.querySelector('[data-q-schema-mult="from"]').textContent, rel.querySelector('[data-q-schema-mult="to"]').textContent],
                label: lbl.textContent,
                clashes: clashes.length,
                allEndsOnCards: edgeEnds.flat().every(onAnyBorder),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert d["startsOnEast"] and d["endsOnEast"] and d["distinctRows"]
    assert d["out"] >= 20
    assert d["marks"] == ["diamond-hollow", "none"]
    assert d["mults"] == ["0..1", "*"] and d["label"] == "children"
    assert d["clashes"] == 0
    assert d["allEndsOnCards"] is True


def test_schema_class_marks_are_scoped_to_the_model_and_recolour_with_the_theme(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const parser = document.querySelector('#schema-parser');
              const small = document.querySelector('#schema-small');
              const kinds = (m) => [...new Set([...m.querySelectorAll('marker[data-q-schema-mark]')].map((e) => e.getAttribute('data-q-schema-mark')))].sort();
              const ids = (m) => [...m.querySelectorAll('marker')].map((e) => e.id);
              const colours = [...parser.querySelectorAll('marker[data-q-schema-mark] [stroke]')].map((e) => e.getAttribute('stroke'));
              return {{
                parserKinds: kinds(parser),
                smallKinds: kinds(small),
                shared: ids(parser).filter((id) => ids(small).includes(id)).length,
                themed: colours.every((c) => c.startsWith('var(--q-color-')),
              }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["parserKinds"] == ["arrow", "diamond-filled", "diamond-hollow", "triangle"]
    assert d["smallKinds"] == ["one", "one-or-many", "zero-or-many", "zero-or-one"]
    assert d["shared"] == 0 and d["themed"] is True


SCHEMA_PARSER_LIST_JS = """(() => {
  const d = document.querySelector('#schema-parser [data-q-flow-list]');
  return {
    summary: d.querySelector('summary').textContent,
    text: d.querySelector('[data-q-flow-list-body]').textContent,
    entities: [...d.querySelectorAll('[data-q-schema-list-entity]')].map((e) => e.getAttribute('data-q-schema-list-entity') + '|' + e.textContent),
    rels: [...d.querySelectorAll('[data-q-schema-list-rels] > li')].map((e) => e.textContent),
  };
})()"""


def test_schema_class_js_text_list_equals_the_python_fallback_list(schema_class_page: Path) -> None:
    js = run(schema_class_page, ev(SCHEMA_PARSER_LIST_JS, "list"))
    assert_clean(js)
    nojs = run(schema_class_page, ev(SCHEMA_PARSER_LIST_JS, "list"), javaScript=False)
    assert nojs["failedSteps"] == [] and nojs["pageErrors"] == []
    assert js["results"]["list"] == nojs["results"]["list"]
    listing = js["results"]["list"]
    assert listing["summary"] == "Class diagram as a list"
    assert listing["rels"] == [
        "RecursiveDescentParser implements Parser",
        "RecursiveDescentParser is composed of 1 Lexer",
        "Lexer depends on Token (produces)",
        "Token is associated with TokenKind",
        "BinaryExpr inherits from Ast",
        "BinaryExpr aggregates 2 Ast (operands)",
        "Parser depends on Ast (returns)",
    ]
    assert any(e.startswith("parser|Parser (api, interface)") for e in listing["entities"])


def test_schema_class_without_javascript_says_class_diagram_in_the_notice(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        ev(
            """(() => {
              const m = document.querySelector('#schema-parser');
              return { notice: m.querySelector('[data-q-flow-notice]').textContent, open: m.querySelector('[data-q-flow-list]').open };
            })()""",
            "d",
        ),
        javaScript=False,
    )
    assert out["failedSteps"] == [] and out["pageErrors"] == []
    assert out["results"]["d"] == {"notice": "JavaScript is off, so this class diagram is shown as a list below.", "open": True}


def test_schema_class_data_that_fails_shows_the_class_notice_and_the_open_list(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        ev(
            f"""(() => {{
              {SCHEMA_MOUNT_JS}
              const m = document.querySelector('#schema-class-loop');
              return {{ loop: failureState(m), parser: document.querySelector('#schema-parser').getAttribute('data-q-flow-ready') }};
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["loop"] == {
        "ready": "error",
        "notice": "This class diagram could not be drawn.",
        "svg": False,
        "open": True,
        "title": "Class diagram as a list",
        "entities": 0,
    }
    assert d["parser"] == "true"


SCHEMA_CLASS_BAD_MODELS = {
    "cross-notation key on an attribute": {"entities": [{"id": "a", "label": "A", "fields": [{"name": "id", "key": "PK"}]}]},
    "cross-notation cardinality": {
        "entities": [{"id": "a", "label": "A"}],
        "relationships": [{"from": "a", "to": "a", "type": "dependency", "from_card": "one"}],
    },
    "unknown stereotype": {"entities": [{"id": "a", "label": "A", "stereotype": "mixin"}]},
    "unknown visibility on an attribute": {"entities": [{"id": "a", "label": "A", "fields": [{"name": "x", "visibility": "internal"}]}]},
    "unknown visibility on a method": {"entities": [{"id": "a", "label": "A", "methods": [{"signature": "f()", "visibility": "internal"}]}]},
    "null fields": {"entities": [{"id": "a", "label": "A", "fields": None}]},
    "null methods": {"entities": [{"id": "a", "label": "A", "methods": None}]},
    "duplicate attribute": {"entities": [{"id": "a", "label": "A", "fields": [{"name": "x"}, {"name": "x"}]}]},
    "duplicate method": {"entities": [{"id": "a", "label": "A", "methods": [{"signature": "f()"}, {"signature": "f()"}]}]},
    "unknown class": {"entities": [{"id": "a", "label": "A"}], "relationships": [{"from": "a", "to": "b", "type": "dependency"}]},
    "member-level end": {
        "entities": [{"id": "a", "label": "A", "fields": [{"name": "x"}]}],
        "relationships": [{"from": "a.x", "to": "a", "type": "dependency"}],
    },
    "unknown relationship type": {"entities": [{"id": "a", "label": "A"}], "relationships": [{"from": "a", "to": "a", "type": "extends"}]},
    "missing relationship type": {"entities": [{"id": "a", "label": "A"}], "relationships": [{"from": "a", "to": "a"}]},
    "multiplicity many": {
        "entities": [{"id": "a", "label": "A"}],
        "relationships": [{"from": "a", "to": "a", "type": "association", "to_mult": "many"}],
    },
    "multiplicity n greater than m": {
        "entities": [{"id": "a", "label": "A"}],
        "relationships": [{"from": "a", "to": "a", "type": "association", "from_mult": "3..2"}],
    },
    "directed on a dependency": {
        "entities": [{"id": "a", "label": "A"}],
        "relationships": [{"from": "a", "to": "a", "type": "dependency", "directed": True}],
    },
    "inheritance loop": {
        "entities": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "relationships": [{"from": "a", "to": "b", "type": "inherits"}, {"from": "b", "to": "a", "type": "implements"}],
    },
    "class that inherits itself": {"entities": [{"id": "a", "label": "A"}], "relationships": [{"from": "a", "to": "a", "type": "inherits"}]},
    "coordinates on a method": {"entities": [{"id": "a", "label": "A", "methods": [{"signature": "f()", "x": 1}]}]},
}
SCHEMA_CLASS_GOOD_MODELS = {
    "empty class with no members": {"entities": [{"id": "a", "label": "A"}]},
    "dotted class ids": {"entities": [{"id": "a.b", "label": "AB"}, {"id": "c", "label": "C"}], "relationships": [{"from": "a.b", "to": "c", "type": "dependency"}]},
    "diamond of inheritance": {
        "entities": [{"id": n, "label": n.upper()} for n in "abcd"],
        "relationships": [
            {"from": "b", "to": "a", "type": "inherits"},
            {"from": "c", "to": "a", "type": "inherits"},
            {"from": "d", "to": "b", "type": "inherits"},
            {"from": "d", "to": "c", "type": "implements"},
        ],
    },
    "aggregating its own parent": {
        "entities": [{"id": "p", "label": "P"}, {"id": "c", "label": "C"}],
        "relationships": [{"from": "c", "to": "p", "type": "inherits"}, {"from": "c", "to": "p", "type": "aggregation"}, {"from": "p", "to": "c", "type": "composition"}],
    },
    "two self relationships and a stereotype": {
        "entities": [{"id": "n", "label": "N", "stereotype": "abstract", "methods": [{"signature": "f()", "abstract": True}]}],
        "relationships": [
            {"from": "n", "to": "n", "type": "aggregation", "label": "kids", "to_mult": "0..*"},
            {"from": "n", "to": "n", "type": "association", "directed": True, "label": "next"},
        ],
    },
    "grouped classes": {
        "groups": [{"id": "g", "label": "G"}],
        "entities": [{"id": "a", "label": "A", "group": "g"}, {"id": "b", "label": "B", "group": "g"}, {"id": "c", "label": "C"}],
        "relationships": [{"from": "a", "to": "b", "type": "inherits"}, {"from": "c", "to": "a", "type": "dependency"}],
    },
    "prototype-named ids": {
        "entities": [{"id": "constructor", "label": "C", "methods": [{"signature": "f()"}]}, {"id": "__proto__", "label": "P"}],
        "relationships": [{"from": "constructor", "to": "__proto__", "type": "inherits"}],
    },
}


def test_schema_class_runtime_rejects_the_same_data_the_kit_check_fails(schema_class_page: Path) -> None:
    cases = {**SCHEMA_CLASS_BAD_MODELS, **SCHEMA_CLASS_GOOD_MODELS}
    out = run(
        schema_class_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const cases = {json.dumps(cases)};
              const mount = Object.entries(cases).map(([name, data]) => [name, mountSchema(data, {{ notation: 'class' }})]);
              return Object.fromEntries(await Promise.all(mount.map(async ([name, el]) => [name, await settle(el)])));
            }})()""",
            "ready",
        ),
    )
    assert_clean(out)
    ready = out["results"]["ready"]
    assert {name: ready[name] for name in SCHEMA_CLASS_BAD_MODELS} == {name: "error" for name in SCHEMA_CLASS_BAD_MODELS}
    assert {name: ready[name] for name in SCHEMA_CLASS_GOOD_MODELS} == {name: "true" for name in SCHEMA_CLASS_GOOD_MODELS}


def test_schema_class_fold_follows_the_four_four_and_spare_row_rules(schema_class_page: Path) -> None:
    def entity(attrs: int, methods: int) -> dict:
        return {
            "id": "c",
            "label": "C",
            "fields": [{"name": f"a{i}", "type": "int"} for i in range(attrs)],
            "methods": [{"signature": f"m{i}()"} for i in range(methods)],
        }

    shapes = [(6, 7), (2, 9), (11, 1), (3, 4), (5, 3), (0, 10), (9, 0)]
    out = run(
        schema_class_page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const cases = {json.dumps([{"entities": [entity(a, m)]} for a, m in shapes])};
              const els = cases.map((data) => mountSchema(data, {{ notation: 'class' }}));
              await Promise.all(els.map(settle));
              return els.map((el) => {{
                const more = el.querySelector('[data-q-schema-more]');
                return [el.querySelectorAll('[data-q-schema-field]').length, el.querySelectorAll('[data-q-schema-method]').length, more && more.textContent];
              }});
            }})()""",
            "d",
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == [[4, 4, "+5 more"], [2, 6, "+3 more"], [7, 1, "+4 more"], [3, 4, None], [5, 3, None], [0, 8, "+2 more"], [8, 0, "+1 more"]]


def test_schema_class_keyboard_enter_announces_and_escape_clears(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        {"focus": '#schema-parser [data-q-schema-entity="parser"]'},
        {"press": "Enter"},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              return {{ live: m.querySelector('[data-q-flow-live]').textContent, selected: entityIds(m, 'data-q-flow-selected'), drawer: drawerState(m).open }};
            }})()""",
            "entered",
        ),
        {"press": "Escape"},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              return {{ selected: entityIds(m, 'data-q-flow-selected'), drawer: drawerState(m).open }};
            }})()""",
            "cleared",
        ),
    )
    assert_clean(out)
    assert out["results"]["entered"] == {"live": "Parser, api, interface, 1 member, 2 relationships", "selected": ["parser"], "drawer": True}
    assert out["results"]["cleared"] == {"selected": [], "drawer": False}


def test_schema_class_theme_toggle_recolours_without_moving_cards(schema_class_page: Path) -> None:
    out = run(
        schema_class_page,
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              window.__before = ['parser', 'ast', 'binaryexpr'].map((id) => JSON.stringify(cardBox(m, id)));
              window.__svg = m.querySelector('[data-q-flow-svg]');
              return true;
            }})()""",
            "before",
        ),
        {"emulate": {"colorScheme": "dark"}},
        ev(
            f"""(() => {{
              {SCHEMA_GEOMETRY_JS}
              const m = document.querySelector('#schema-parser');
              return {{
                same: ['parser', 'ast', 'binaryexpr'].map((id) => JSON.stringify(cardBox(m, id))).join() === window.__before.join(),
                sameSvg: window.__svg === m.querySelector('[data-q-flow-svg]'),
                ready: m.getAttribute('data-q-flow-ready'),
              }};
            }})()""",
            "after",
        ),
    )
    assert_clean(out)
    assert out["results"]["after"] == {"same": True, "sameSvg": True, "ready": "true"}


REFERENCE_EXAMPLE = SKILL / "templates" / "report" / "examples" / "reference.src.html"


def test_schema_reference_example_builds_clean_and_draws_both_models(tmp_path: Path) -> None:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    page = tmp_path / "reference.html"
    proc = subprocess.run(
        [sys.executable, str(CLI), "build", str(REFERENCE_EXAMPLE), "--out", str(page)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["checks"]["passed"] is True and result["checks"]["failures"] == []
    assert result["warnings"] == []
    out = run(
        page,
        ev(
            f"""(async () => {{
              {SCHEMA_MOUNT_JS}
              const models = [...document.querySelectorAll('q-schema')];
              await Promise.all(models.map(settle));
              return models.map((m) => ({{
                notation: m.getAttribute('notation'),
                ready: m.getAttribute('data-q-flow-ready'),
                cards: m.querySelectorAll('[data-q-schema-entity]').length,
                lines: m.querySelectorAll('[data-q-schema-rel]').length,
                summary: (m.getAttribute('summary') || '').split('. ').length,
              }}));
            }})()""",
            "models",
        ),
    )
    assert_clean(out)
    assert out["results"]["models"] == [
        {"notation": None, "ready": "true", "cards": 4, "lines": 4, "summary": 1},
        {"notation": "class", "ready": "true", "cards": 7, "lines": 7, "summary": 1},
    ]


# --- q-sequence -------------------------------------------------------------------------------

SEQ_KINDS = {"person": 1, "ui": 2, "service": 3, "external": 4, "store": 5}


def _seq_part(pid: str, label: str, kind: str | None = None, detail: str | None = None) -> dict:
    part: dict = {"id": pid, "label": label}
    if kind:
        part["kind"] = kind
    if detail:
        part["detail"] = detail
    return part


def _seq_msg(frm: str, to: str, label: str, mtype: str, mid: str | None = None, **extra: object) -> dict:
    step: dict = {"from": frm, "to": to, "label": label, "type": mtype}
    if mid:
        step["id"] = mid
    step.update(extra)
    return step


_SEQ_V1 = {"order": "C-2207", "items": 2, "total": 48}
_SEQ_V2 = {**_SEQ_V1, "amount": 48, "currency": "usd"}
_SEQ_V3 = {**_SEQ_V2, "attempt": 1, "card": "•••• 4242"}
_SEQ_V5 = {**_SEQ_V3, "attempt": 2}
_SEQ_V6 = {**_SEQ_V5, "charge": "ch_91", "status": "succeeded"}

SEQ_CHECKOUT_DATA = {
    "kinds": SEQ_KINDS,
    "participants": [
        _seq_part("shopper", "Shopper", "person"),
        _seq_part("checkout", "Checkout", "ui", "<p>The page the shopper pays on.</p>"),
        _seq_part("billing", "Billing", "service"),
        _seq_part("stripe", "Stripe", "external", "<p>Card processor. Charges are <strong>idempotent</strong>.</p>"),
        _seq_part("ledger", "Ledger", "store"),
    ],
    "steps": [
        _seq_msg("shopper", "checkout", "place order", "call", "place-order", detail="<p>The cart and the shipping address.</p>"),
        _seq_msg("checkout", "billing", "charge order", "call", "charge-order"),
        {
            "fragment": "loop",
            "label": "up to 3 attempts",
            "steps": [
                _seq_msg("billing", "stripe", "create charge", "call", "create-charge", detail="<p>Sends the amount and a <code>payment_method</code>.</p>"),
                {
                    "fragment": "alt",
                    "branches": [
                        {"label": "card valid", "steps": [_seq_msg("stripe", "billing", "charge succeeded", "reply", "charge-ok")]},
                        {
                            "label": "card declined",
                            "steps": [
                                _seq_msg("stripe", "billing", "card declined", "reply", "charge-declined"),
                                {"note": "waits 2 seconds before retrying", "over": ["billing"]},
                            ],
                        },
                    ],
                },
            ],
        },
        {"fragment": "opt", "label": "charge succeeded", "steps": [_seq_msg("billing", "ledger", "record payment", "async", "record")]},
        _seq_msg("billing", "checkout", "order paid", "reply", "paid"),
        _seq_msg("checkout", "shopper", "show receipt", "reply", "show-receipt"),
    ],
    "traces": [
        {
            "id": "succeeds",
            "label": "Card succeeds",
            "steps": [
                {"message": "place-order", "value": _SEQ_V1},
                {"message": "charge-order", "value": _SEQ_V2},
                {"message": "create-charge", "value": _SEQ_V3},
                {"message": "charge-ok", "value": {**_SEQ_V3, "charge": "ch_91", "status": "succeeded"}},
                {"message": "record", "value": {**_SEQ_V3, "charge": "ch_91", "status": "succeeded"}, "note": "async, nothing waits for it"},
                {"message": "paid", "value": {**_SEQ_V3, "charge": "ch_91", "status": "paid"}},
            ],
        },
        {
            "id": "declined",
            "label": "Declined, then retried",
            "steps": [
                {"message": "place-order", "value": _SEQ_V1},
                {"message": "charge-order", "value": _SEQ_V2},
                {"message": "create-charge", "value": _SEQ_V3},
                {"message": "charge-declined", "value": {**_SEQ_V3, "decline": "insufficient_funds"}},
                {"message": "create-charge", "value": _SEQ_V5},
                {"message": "charge-ok", "value": _SEQ_V6},
                {"message": "record", "value": _SEQ_V6},
                {"message": "paid", "value": {**_SEQ_V6, "status": "paid"}},
            ],
        },
    ],
}

SEQ_SELF_DATA = {
    "participants": [_seq_part("client", "Client"), _seq_part("billing", "Billing")],
    "steps": [
        _seq_msg("client", "billing", "request", "async"),
        _seq_msg("billing", "billing", "validate cart", "call"),
        _seq_msg("billing", "client", "response", "async"),
    ],
}

SEQ_SESSION_DATA = {
    "kinds": {"service": 3},
    "participants": [_seq_part("billing", "Billing", "service"), _seq_part("receipt-worker", "Receipt worker", "service")],
    "steps": [
        _seq_msg("billing", "receipt-worker", "start session", "call", create=True),
        _seq_msg("receipt-worker", "billing", "session ready", "reply"),
        _seq_msg("billing", "receipt-worker", "send receipt", "async"),
        {"end": "receipt-worker"},
    ],
}

SEQ_STACK_DATA = {
    "participants": [_seq_part("a", "A"), _seq_part("b", "B"), _seq_part("c", "C")],
    "steps": [
        _seq_msg("a", "b", "outer", "call"),
        _seq_msg("b", "c", "ask", "call"),
        _seq_msg("c", "b", "call back", "call"),
        _seq_msg("b", "c", "back", "reply"),
        _seq_msg("c", "b", "answer", "reply"),
        _seq_msg("b", "a", "done", "reply"),
    ],
}

SEQ_BAD_DATA = {
    "participants": [_seq_part("a", "A"), _seq_part("b-ok", "B")],
    "steps": [_seq_msg("a", "b-ok", "ping", "async")],
}


def _seq_element(sid: str, summary: str, data: dict) -> str:
    return f'<q-sequence id="{sid}" summary="{summary}">\n  <script type="application/json">\n  {json.dumps(data, indent=2)}\n  </script>\n</q-sequence>\n'


SEQ_CHECKOUT = (
    _seq_element("checkout", "Checkout charges the card through Billing and Stripe, retrying a declined card.", SEQ_CHECKOUT_DATA)
    + _seq_element("selfmsg", "Billing validates a cart it was sent.", SEQ_SELF_DATA)
    + _seq_element("session", "Billing starts a receipt worker and later ends it.", SEQ_SESSION_DATA)
    + _seq_element("stack", "A call back into a busy participant.", SEQ_STACK_DATA)
    + _seq_element("bad", "A sequence whose data is edited after the build.", SEQ_BAD_DATA)
    + '<div style="height: 1200px"></div>\n'
)

SEQ_DATA_BY_ID = {"checkout": SEQ_CHECKOUT_DATA, "selfmsg": SEQ_SELF_DATA, "session": SEQ_SESSION_DATA, "stack": SEQ_STACK_DATA}


@pytest.fixture(scope="module")
def seq_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-sequence")
    src = work / "sequence.src.html"
    src.write_text(HEADER + SEQ_CHECKOUT, encoding="utf-8")
    built = _build(src, work / "sequence.html")
    # the unknown participant is edited in after the build so the build-time check never sees it
    html = built.read_text(encoding="utf-8")
    good = '"to": "b-ok"'
    assert html.count(good) == 1
    built.write_text(html.replace(good, '"to": "b-gone"'), encoding="utf-8")
    return built


SEQ_HELPERS = """
const q = (id) => document.querySelector('#' + id);
const num = (el, name) => parseFloat(el.getAttribute(name));
const nums = (el) => (el.getAttribute('d').match(/-?\\d+(?:\\.\\d+)?/g) || []).map(Number);
const lifeX = (root, id) => num(root.querySelector('[data-q-sequence-lifeline="' + id + '"]'), 'x1');
const msg = (root, n) => root.querySelector('[data-q-sequence-message="' + n + '"]');
const lineOf = (root, n) => msg(root, n).querySelector('[data-q-sequence-line]');
const lineY = (root, n) => nums(lineOf(root, n))[1];
const hitOf = (root, n) => msg(root, n).querySelector('[data-q-sequence-hit]');
const dashes = (el) => { const v = getComputedStyle(el).strokeDasharray; return v === 'none' ? [] : v.match(/\\d+(?:\\.\\d+)?/g).map(Number); };
const barsOf = (root, id) => [...root.querySelectorAll('[data-q-sequence-bar="' + id + '"]')]
  .map((b) => ({ x: num(b, 'x'), width: num(b, 'width'), top: num(b, 'y'), bottom: num(b, 'y') + num(b, 'height') }))
  .sort((a, b) => a.top - b.top);
"""


def _seq_eval(body: str, name: str = "d") -> dict:
    return ev(f"(async () => {{ {SEQ_HELPERS} {body} }})()", name)


def _close(a: float, b: float, tol: float = 0.6) -> bool:
    return abs(a - b) <= tol


def test_seq_draws_one_shell_in_order_with_the_summary_as_the_svg_label(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('checkout');
            const svg = root.querySelector('[data-q-sequence-svg]');
            const controls = root.querySelector(':scope > [data-q-sequence-controls]');
            return {
              ready: root.getAttribute('data-q-sequence-ready'),
              children: [...root.children].map((c) => c.tagName.toLowerCase() + (c.getAttribute('data-q-sequence-controls') !== null ? ':controls' : c.hasAttribute('data-q-sequence-pinned') ? ':pinned' : c.hasAttribute('data-q-sequence-stage') ? ':stage' : c.hasAttribute('data-q-flow-trace-panel') ? ':trace' : c.hasAttribute('data-q-flow-drawer') ? ':drawer' : c.hasAttribute('data-q-sequence-live') ? ':live' : c.hasAttribute('data-q-sequence-list') ? ':list' : '')),
              controlsRole: controls.getAttribute('role'),
              controlsLabel: controls.getAttribute('aria-label'),
              buttons: controls.querySelectorAll('button').length,
              svgParent: svg.parentElement.hasAttribute('data-q-sequence-stage'),
              svgRole: svg.getAttribute('role'),
              svgLabel: svg.getAttribute('aria-label'),
              live: root.querySelector(':scope > [data-q-sequence-live]').getAttribute('aria-live'),
              liveHidden: root.querySelector(':scope > [data-q-sequence-live]').classList.contains('q-visually-hidden'),
              listOpen: root.querySelector(':scope > details[data-q-sequence-list]').open,
              notice: root.querySelectorAll('[data-q-sequence-notice]').length,
              strips: root.querySelectorAll('[data-q-sequence-pinned] button[data-q-sequence-header]').length,
              columns: root.querySelectorAll('[data-q-sequence-lifeline]').length,
              messages: root.querySelectorAll('[data-q-sequence-message]').length,
              display: getComputedStyle(root).display,
              overflowX: getComputedStyle(root.querySelector('[data-q-sequence-stage]')).overflowX,
              pinnedPosition: getComputedStyle(root.querySelector('[data-q-sequence-pinned]')).position,
            };
            """
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true"
    assert d["children"] == ["script", "div:controls", "div:pinned", "div:stage", "aside:trace", "aside:drawer", "div:live", "details:list"]
    assert (d["controlsRole"], d["controlsLabel"], d["buttons"]) == ("toolbar", "Diagram controls", 1)
    assert d["svgParent"] and d["svgRole"] == "img"
    assert d["svgLabel"] == "Checkout charges the card through Billing and Stripe, retrying a declined card."
    assert d["live"] == "polite" and d["liveHidden"]
    assert d["listOpen"] is False and d["notice"] == 0
    assert (d["strips"], d["columns"], d["messages"]) == (5, 5, 8)
    assert d["display"] == "block" and d["overflowX"] == "auto" and d["pinnedPosition"] == "sticky"


def test_seq_numbers_messages_in_row_order_and_styles_each_type(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('checkout');
            const rows = [...root.querySelectorAll('[data-q-sequence-message]')].map((g) => {
              const n = g.getAttribute('data-q-sequence-message');
              const [x1, y, x2] = (() => { const p = nums(g.querySelector('[data-q-sequence-line]')); return [p[0], p[1], p[p.length - 2]]; })();
              const head = g.querySelector('[data-q-sequence-head]');
              return {
                n: Number(n),
                label: g.querySelector('[data-q-sequence-label]').textContent,
                y: y,
                dash: dashes(g.querySelector('[data-q-sequence-line]')),
                headFill: getComputedStyle(head).fill === 'none' ? 'open' : 'filled',
                dir: Math.sign(x2 - x1),
                endX: x2,
                aria: g.getAttribute('aria-label'),
                role: g.getAttribute('role'),
                hitY: num(g.querySelector('[data-q-sequence-hit]'), 'y'),
              };
            });
            return { rows: rows, lifelines: ['shopper', 'checkout', 'billing', 'stripe', 'ledger'].map((id) => lifeX(root, id)) };
            """
        ),
    )
    assert_clean(out)
    rows = out["results"]["d"]["rows"]
    lifelines = out["results"]["d"]["lifelines"]
    assert [r["n"] for r in rows] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [r["label"] for r in rows] == [
        "1. place order",
        "2. charge order",
        "3. create charge",
        "4. charge succeeded",
        "5. card declined",
        "6. record payment",
        "7. order paid",
        "8. show receipt",
    ]
    ys = [r["y"] for r in rows]
    assert ys == sorted(ys) and len(set(ys)) == 8
    assert [r["dash"] for r in rows] == [[], [], [], [6, 4], [6, 4], [], [6, 4], [6, 4]]
    assert [r["headFill"] for r in rows] == ["filled", "filled", "filled", "open", "open", "open", "open", "open"]
    assert [r["dir"] for r in rows] == [1, 1, 1, -1, -1, 1, -1, -1]
    targets = [1, 2, 3, 2, 2, 4, 1, 0]
    for r, t in zip(rows, targets):
        assert abs(r["endX"] - lifelines[t]) <= 12, (r["n"], r["endX"], lifelines[t])
    assert rows[2]["aria"] == "Message 3 of 8, Billing to Stripe, create charge, call"
    assert rows[5]["aria"] == "Message 6 of 8, Billing to Ledger, record payment, async"
    assert all(r["role"] == "button" for r in rows)
    assert lifelines == sorted(lifelines)


def test_seq_self_message_row_is_taller_and_opens_no_bar(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('selfmsg');
            const self = nums(lineOf(root, 2));
            const hits = [1, 2, 3].map((n) => num(hitOf(root, n), 'height'));
            return {
              hits: hits,
              startX: self[0], endX: self[self.length - 2], maxX: Math.max(...self.filter((v, i) => i % 2 === 0)),
              life: lifeX(root, 'billing'),
              bars: root.querySelectorAll('[data-q-sequence-bar]').length,
              headFill: getComputedStyle(msg(root, 2).querySelector('[data-q-sequence-head]')).fill === 'none' ? 'open' : 'filled',
              label: msg(root, 2).querySelector('[data-q-sequence-label]').textContent,
            };
            """
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["hits"][1] > d["hits"][0] and d["hits"][1] > d["hits"][2]
    assert d["hits"][0] == d["hits"][2]
    assert _close(d["startX"], d["life"]) and _close(d["endX"], d["life"]) and d["maxX"] > d["life"] + 20
    assert d["bars"] == 0
    assert d["headFill"] == "filled" and d["label"] == "2. validate cart"


def test_seq_fragments_box_exactly_their_rows_and_span_their_columns(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('checkout');
            const box = (type) => {
              const g = root.querySelector('[data-q-sequence-fragment="' + type + '"]');
              const r = g.querySelector('[data-q-sequence-fragment-box]');
              return {
                left: num(r, 'x'), right: num(r, 'x') + num(r, 'width'), top: num(r, 'y'), bottom: num(r, 'y') + num(r, 'height'),
                tab: g.querySelector('[data-q-sequence-fragment-tab]').textContent,
                label: [...g.querySelectorAll('[data-q-sequence-fragment-label]')].map((t) => t.textContent),
                sections: [...g.querySelectorAll('[data-q-sequence-section-label]')].map((t) => t.textContent),
                dividers: g.querySelectorAll('[data-q-sequence-divider]').length,
                dash: g.querySelector('[data-q-sequence-divider]') ? dashes(g.querySelector('[data-q-sequence-divider]')) : null,
              };
            };
            const rowTop = (n) => num(hitOf(root, n), 'y');
            const rowBottom = (n) => num(hitOf(root, n), 'y') + num(hitOf(root, n), 'height');
            const note = root.querySelector('[data-q-sequence-note] rect');
            return {
              loop: box('loop'), alt: box('alt'), opt: box('opt'),
              fragments: [...root.querySelectorAll('[data-q-sequence-fragment]')].map((g) => g.getAttribute('data-q-sequence-fragment')),
              rows: [1, 2, 3, 4, 5, 6, 7].map((n) => [rowTop(n), rowBottom(n)]),
              noteTop: num(note, 'y'), noteBottom: num(note, 'y') + num(note, 'height'),
              noteText: root.querySelector('[data-q-sequence-note]').textContent,
              noteCenter: num(note, 'x') + num(note, 'width') / 2,
              life: ['checkout', 'billing', 'stripe', 'ledger'].map((id) => lifeX(root, id)),
              dividerY: num(root.querySelector('[data-q-sequence-divider]'), 'y1'),
            };
            """
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["fragments"] == ["loop", "alt", "opt"]
    checkout, billing, stripe, ledger = d["life"]
    rows = d["rows"]
    loop, alt, opt = d["loop"], d["alt"], d["opt"]
    assert (loop["tab"], loop["label"], loop["sections"], loop["dividers"]) == ("loop", ["up to 3 attempts"], [], 0)
    assert loop["top"] >= rows[1][1] - 0.5 and loop["top"] <= rows[2][0]
    assert loop["bottom"] >= d["noteBottom"] and loop["bottom"] <= opt["top"]
    assert checkout < loop["left"] < billing and stripe < loop["right"] < ledger
    assert (alt["tab"], alt["sections"], alt["dividers"], alt["dash"]) == ("alt", ["card valid", "card declined"], 1, [6, 4])
    assert alt["top"] >= rows[2][1] - 0.5 and alt["top"] <= rows[3][0]
    assert alt["bottom"] >= d["noteBottom"] and alt["bottom"] <= loop["bottom"]
    assert loop["left"] < alt["left"] < billing and stripe < alt["right"] < loop["right"]
    assert alt["top"] < d["dividerY"] < rows[4][0]
    assert (opt["tab"], opt["label"], opt["sections"]) == ("opt", ["charge succeeded"], [])
    assert opt["top"] >= loop["bottom"] and opt["top"] <= rows[5][0] and opt["bottom"] >= rows[5][1]
    assert opt["bottom"] <= rows[6][0]
    assert checkout < opt["left"] < billing and ledger < opt["right"]
    assert d["noteText"] == "waits 2 seconds before retrying"
    assert _close(d["noteCenter"], billing, 1.5)
    assert d["noteTop"] >= rows[4][1] - 0.5


def test_seq_activation_bars_follow_the_call_and_reply_walk(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('checkout');
            const ys = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => lineY(root, n));
            return {
              ys: ys,
              bars: Object.fromEntries(['shopper', 'checkout', 'billing', 'stripe', 'ledger'].map((id) => [id, barsOf(root, id)])),
              life: Object.fromEntries(['checkout', 'billing', 'stripe'].map((id) => [id, lifeX(root, id)])),
              dividerY: num(root.querySelector('[data-q-sequence-divider]'), 'y1'),
            };
            """
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    ys, bars = d["ys"], d["bars"]
    assert bars["shopper"] == [] and bars["ledger"] == []
    assert len(bars["checkout"]) == 1 and len(bars["billing"]) == 1 and len(bars["stripe"]) == 2
    assert _close(bars["checkout"][0]["top"], ys[0]) and _close(bars["checkout"][0]["bottom"], ys[7])
    assert _close(bars["billing"][0]["top"], ys[1]) and _close(bars["billing"][0]["bottom"], ys[6])
    first, second = bars["stripe"]
    assert _close(first["top"], ys[2]) and _close(first["bottom"], ys[3])
    assert _close(second["top"], d["dividerY"]) and _close(second["bottom"], ys[4])
    for pid, bar in (("checkout", bars["checkout"][0]), ("billing", bars["billing"][0]), ("stripe", first)):
        assert _close(bar["x"] + bar["width"] / 2, d["life"][pid], 0.6)


def test_seq_a_call_into_a_busy_participant_stacks_an_offset_bar(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('stack');
            return { bars: barsOf(root, 'b'), ys: [1, 2, 3, 4, 5, 6].map((n) => lineY(root, n)), a: barsOf(root, 'a'), c: barsOf(root, 'c') };
            """
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    ys = d["ys"]
    assert d["a"] == [] and len(d["c"]) == 1
    assert _close(d["c"][0]["top"], ys[1]) and _close(d["c"][0]["bottom"], ys[4])
    outer, inner = d["bars"]
    assert _close(outer["top"], ys[0]) and _close(outer["bottom"], ys[5])
    assert _close(inner["top"], ys[2]) and _close(inner["bottom"], ys[3])
    assert inner["x"] > outer["x"] and inner["x"] < outer["x"] + outer["width"]


def test_seq_headers_carry_the_kind_tag_and_accent_from_the_chart_number(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const probe = (value) => { const p = document.createElement('span'); p.style.background = value; document.body.appendChild(p); const c = getComputedStyle(p).backgroundColor; p.remove(); return c; };
            const strip = (root) => [...root.querySelectorAll('[data-q-sequence-pinned] button[data-q-sequence-header]')].map((b) => {
              const tag = b.querySelector('[data-q-sequence-kind-tag]');
              return {
                id: b.getAttribute('data-q-sequence-header'),
                label: b.querySelector('[data-q-sequence-header-label]').textContent,
                tag: tag ? tag.textContent : null,
                accent: getComputedStyle(b.querySelector('[data-q-sequence-accent]')).backgroundColor,
                center: b.getBoundingClientRect().left + b.getBoundingClientRect().width / 2,
                type: b.getAttribute('type'),
              };
            });
            const root = q('checkout');
            const life = (id) => root.querySelector('[data-q-sequence-lifeline="' + id + '"]');
            return {
              headers: strip(root),
              plain: strip(q('selfmsg')),
              charts: [1, 2, 3, 4, 5].map((n) => probe('var(--q-color-chart-' + n + ')')),
              border: probe('var(--q-color-border)'),
              lifeDash: dashes(life('billing')),
              lifeLeft: ['shopper', 'checkout', 'billing', 'stripe', 'ledger'].map((id) => life(id).getBoundingClientRect().left),
            };
            """
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert [h["label"] for h in d["headers"]] == ["Shopper", "Checkout", "Billing", "Stripe", "Ledger"]
    assert [h["tag"] for h in d["headers"]] == ["person", "ui", "service", "external", "store"]
    assert [h["accent"] for h in d["headers"]] == d["charts"]
    assert all(h["type"] == "button" for h in d["headers"])
    assert len(set(d["charts"])) == 5
    assert [h["tag"] for h in d["plain"]] == [None, None]
    assert [h["accent"] for h in d["plain"]] == [d["border"], d["border"]]
    assert d["lifeDash"] and sum(d["lifeDash"]) > 0
    for header, left in zip(d["headers"], d["lifeLeft"]):
        assert abs(header["center"] - left) <= 1, (header["id"], header["center"], left)


def test_seq_a_created_participant_starts_at_its_creating_row_and_ends_in_an_x(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('session');
            const created = root.querySelector('[data-q-sequence-created="receipt-worker"]');
            const box = created.querySelector('rect');
            const life = root.querySelector('[data-q-sequence-lifeline="receipt-worker"]');
            const end = root.querySelector('[data-q-sequence-end="receipt-worker"]');
            const endBox = end.getBBox();
            const first = nums(lineOf(root, 1));
            const strip = (id) => getComputedStyle(root.querySelector('[data-q-sequence-pinned] [data-q-sequence-header="' + id + '"]')).opacity;
            return {
              boxTop: num(box, 'y'), boxBottom: num(box, 'y') + num(box, 'height'), boxLeft: num(box, 'x'),
              boxLabel: created.textContent,
              y1: lineY(root, 1), y2: lineY(root, 2), y3: lineY(root, 3),
              lifeTop: num(life, 'y1'), lifeBottom: num(life, 'y2'),
              billingTop: num(root.querySelector('[data-q-sequence-lifeline="billing"]'), 'y1'),
              billingBottom: num(root.querySelector('[data-q-sequence-lifeline="billing"]'), 'y2'),
              endCenterY: endBox.y + endBox.height / 2, endCenterX: endBox.x + endBox.width / 2,
              lifeX: num(life, 'x1'),
              firstEndX: first[first.length - 2],
              bars: barsOf(root, 'receipt-worker'),
              stripWorker: strip('receipt-worker'), stripBilling: strip('billing'),
              createdCount: root.querySelectorAll('[data-q-sequence-created]').length,
              endCount: root.querySelectorAll('[data-q-sequence-end]').length,
            };
            """
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["createdCount"] == 1 and d["endCount"] == 1
    assert d["boxTop"] < d["y1"] < d["boxBottom"] and _close(d["y1"], (d["boxTop"] + d["boxBottom"]) / 2, 1)
    assert d["boxLabel"].find("Receipt worker") >= 0
    assert d["lifeTop"] >= d["boxBottom"] - 0.5 and d["lifeTop"] < d["y2"]
    assert d["billingTop"] == 0 and d["billingBottom"] > d["lifeBottom"] - 0.5
    assert d["y3"] < d["endCenterY"] and _close(d["lifeBottom"], d["endCenterY"], 1.5)
    assert _close(d["endCenterX"], d["lifeX"], 1)
    assert _close(d["firstEndX"], d["boxLeft"], 1.5)
    assert len(d["bars"]) == 1 and d["bars"][0]["top"] >= d["boxBottom"] - 0.5 and _close(d["bars"][0]["bottom"], d["y2"])
    assert d["stripWorker"] == "0" and d["stripBilling"] == "1"


PHONE_PIN = """
const root = q('checkout');
const stage = root.querySelector('[data-q-sequence-stage]');
const strip = root.querySelector('[data-q-sequence-pinned]');
const svg = root.querySelector('[data-q-sequence-svg]');
const label = msg(root, 3).querySelector('[data-q-sequence-label]');
const lined = () => ['shopper', 'checkout', 'billing', 'stripe', 'ledger'].map((id) => {
  const b = strip.querySelector('[data-q-sequence-header="' + id + '"]').getBoundingClientRect();
  const l = root.querySelector('[data-q-sequence-lifeline="' + id + '"]').getBoundingClientRect();
  return Math.abs(b.left + b.width / 2 - l.left);
});
const pinState = () => ({ stuck: strip.hasAttribute('data-q-sequence-stuck'), top: strip.getBoundingClientRect().top, off: lined(), left: stage.scrollLeft });
"""


def test_seq_phone_scrolls_sideways_at_full_size_with_headers_pinned_and_in_step(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 375, "height": 400}},
        _seq_eval(
            PHONE_PIN
            + """
            const rect = label.getBoundingClientRect();
            return {
              scrolls: stage.scrollWidth > stage.clientWidth + 100,
              svgScaled: Math.abs(svg.getBoundingClientRect().width - num(svg, 'width')) > 0.5,
              labelHeight: rect.height, fontSize: getComputedStyle(label).fontSize,
              stuckAtRest: strip.hasAttribute('data-q-sequence-stuck'),
              pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
            };
            """,
            "rest",
        ),
        _seq_eval("window.scrollTo(0, q('checkout').getBoundingClientRect().top + window.scrollY + 220)", "down"),
        {"wait": 300},
        _seq_eval(PHONE_PIN + "return pinState();", "first"),
        _seq_eval("(() => { const s = q('checkout').querySelector('[data-q-sequence-stage]'); s.scrollLeft = s.scrollWidth; })()", "sideways"),
        {"wait": 300},
        _seq_eval(PHONE_PIN + "return pinState();", "second"),
        _seq_eval("window.scrollTo(0, q('checkout').getBoundingClientRect().bottom + window.scrollY + 300)", "past"),
        {"wait": 300},
        _seq_eval(PHONE_PIN + "return pinState();", "third"),
        _seq_eval("window.scrollTo(0, 0)", "up"),
        {"wait": 300},
        _seq_eval(PHONE_PIN + "return pinState();", "back"),
        {"viewport": {"width": 1280, "height": 800}},
        _seq_eval(PHONE_PIN + "return { labelHeight: label.getBoundingClientRect().height, fontSize: getComputedStyle(label).fontSize };", "wide"),
    )
    assert_clean(out)
    rest, wide = out["results"]["rest"], out["results"]["wide"]
    assert rest["scrolls"] and not rest["svgScaled"] and not rest["pageOverflow"] and not rest["stuckAtRest"]
    assert rest["fontSize"] == "14px" == wide["fontSize"]
    assert abs(rest["labelHeight"] - wide["labelHeight"]) <= 0.5
    first, second, third, back = (out["results"][k] for k in ("first", "second", "third", "back"))
    assert first["stuck"] is True and first["top"] == 0 and max(first["off"]) <= 1
    assert second["left"] > 100 and second["stuck"] is True and second["top"] == 0 and max(second["off"]) <= 1
    assert third["stuck"] is False and third["top"] < 0
    assert back["stuck"] is False and back["top"] > 0


SEQ_CANON = """
const canon = (n) => n.nodeType === 3
  ? JSON.stringify(n.nodeValue)
  : n.tagName.toLowerCase() + '[' + [...n.attributes].map((a) => a.name + '=' + a.value).sort().join(',') + '](' + [...n.childNodes].map(canon).join('') + ')';
const listOf = (id) => {
  const details = document.querySelector('#' + id + ' > details[data-q-sequence-list]');
  const copy = details.cloneNode(true);
  copy.normalize();
  copy.removeAttribute('open');
  return canon(copy);
};
"""


def test_seq_runtime_list_matches_the_builders_list_and_follows_edits(seq_page: Path) -> None:
    ids = ["checkout", "selfmsg", "session", "stack"]
    lists = "return { " + ", ".join(f"{i}: listOf('{i}')" for i in ids) + " };"
    runtime = run(seq_page, ev(f"(() => {{ {SEQ_CANON} {lists} }})()", "lists"))
    builder = run(seq_page, ev(f"(() => {{ {SEQ_CANON} {lists} }})()", "lists"), javaScript=False)
    assert_clean(runtime)
    assert_clean(builder)
    for sid in ids:
        assert runtime["results"]["lists"][sid] == builder["results"]["lists"][sid], sid
        assert "data-q-sequence-list-body" in runtime["results"]["lists"][sid]
    shape = run(
        seq_page,
        _seq_eval(
            """
            const root = q('checkout');
            const body = root.querySelector('[data-q-sequence-list-body]');
            const msgs = [...body.querySelectorAll('[data-q-sequence-list-message]')];
            const loop = body.querySelector('[data-q-sequence-list-fragment="loop"]');
            const alt = body.querySelector('[data-q-sequence-list-fragment="alt"]');
            const step = body.querySelector('[data-q-sequence-list-trace="declined"] [data-q-sequence-list-step="4"]');
            return {
              summary: root.querySelector('details[data-q-sequence-list] > summary').textContent,
              participants: [...body.querySelectorAll('[data-q-sequence-list-participants] > li')].map((li) => li.textContent),
              numbers: msgs.map((li) => li.getAttribute('data-q-sequence-list-message')),
              m3: msgs[2].firstChild.textContent,
              m3Detail: msgs[2].querySelector('[data-q-sequence-list-detail]').textContent,
              m6: msgs[5].firstChild.textContent,
              loopText: loop.firstChild.textContent,
              altText: alt.firstChild.textContent,
              branches: [...alt.querySelectorAll(':scope > ol > li')].map((li) => li.firstChild.textContent),
              note: body.querySelector('[data-q-sequence-list-note]').textContent,
              step4: step.firstChild.textContent,
              step4Code: step.querySelector(':scope > pre > code').textContent,
              traces: [...body.querySelectorAll('[data-q-sequence-list-trace] > p > strong')].map((s) => s.textContent),
            };
            """
        ),
    )
    assert_clean(shape)
    s = shape["results"]["d"]
    assert s["summary"] == "Diagram as a list"
    assert s["participants"][0] == "Shopper (person)"
    assert s["participants"][3] == "Stripe (external): Card processor. Charges are idempotent."
    assert s["numbers"] == [str(n) for n in range(1, 9)]
    assert s["m3"] == "3. Billing → Stripe: create charge (call)"
    assert s["m3Detail"] == "Sends the amount and a payment_method."
    assert s["m6"] == "6. Billing → Ledger: record payment (async)"
    assert s["loopText"] == "loop: up to 3 attempts"
    assert s["altText"] == "alt: card valid / card declined"
    assert s["branches"] == ["card valid", "card declined"]
    assert s["note"] == "Note over Billing: waits 2 seconds before retrying"
    assert s["step4"] == "4. message 5, Stripe → Billing, card declined"
    assert s["step4Code"] == json.dumps(SEQ_CHECKOUT_DATA["traces"][1]["steps"][3]["value"], indent=2, ensure_ascii=False)
    assert s["traces"] == ["Trace: Card succeeds", "Trace: Declined, then retried"]
    edited = run(
        seq_page,
        _seq_eval(
            """
            const root = q('checkout');
            const script = root.querySelector(':scope > script');
            const svg = root.querySelector('[data-q-sequence-svg]');
            script.textContent = script.textContent.replace('"Shopper"', '"Buyer"');
            await new Promise((r) => setTimeout(r, 300));
            return {
              first: root.querySelector('[data-q-sequence-list-participants] > li').textContent,
              header: root.querySelector('[data-q-sequence-header="shopper"] [data-q-sequence-header-label]').textContent,
              redrawn: root.querySelector('[data-q-sequence-svg]') !== svg,
              ready: root.getAttribute('data-q-sequence-ready'),
              svgs: root.querySelectorAll('[data-q-sequence-svg]').length,
            };
            """
        ),
    )
    assert_clean(edited)
    assert edited["results"]["d"] == {"first": "Buyer (person)", "header": "Buyer", "redrawn": True, "ready": "true", "svgs": 1}


def test_seq_theme_toggle_recolors_lifelines_and_arrows_without_a_redraw(seq_page: Path) -> None:
    colors = """
      const root = q('checkout');
      const cs = (el, prop) => getComputedStyle(el)[prop];
      const snap = () => ({
        life: cs(root.querySelector('[data-q-sequence-lifeline="billing"]'), 'stroke'),
        arrow: cs(lineOf(root, 1), 'stroke'),
        bar: cs(root.querySelector('[data-q-sequence-bar]'), 'fill'),
        box: cs(root.querySelector('[data-q-sequence-fragment-box]'), 'stroke'),
        header: cs(root.querySelector('[data-q-sequence-header="billing"]'), 'backgroundColor'),
      });
    """
    out = run(
        seq_page,
        _seq_eval(colors + "window.__svg = root.querySelector('[data-q-sequence-svg]'); window.__lines = root.querySelectorAll('[data-q-sequence-line]').length; return snap();", "light"),
        ev("document.documentElement.setAttribute('data-theme', 'dark')", "toggle"),
        {"wait": 150},
        _seq_eval(
            colors
            + """
            return { colors: snap(), same: window.__svg === root.querySelector('[data-q-sequence-svg]') && window.__svg.isConnected,
                     lines: root.querySelectorAll('[data-q-sequence-line]').length === window.__lines, ready: root.getAttribute('data-q-sequence-ready') };
            """,
            "dark",
        ),
        colorScheme="light",
    )
    assert_clean(out)
    light, dark = out["results"]["light"], out["results"]["dark"]
    assert dark["same"] and dark["lines"] and dark["ready"] == "true"
    for key in ("life", "arrow", "bar", "box", "header"):
        assert light[key] != dark["colors"][key], key


def test_seq_a_bad_payload_shows_the_notice_opens_the_list_and_flags_an_error(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('bad');
            const notice = root.querySelector('[data-q-sequence-stage] [data-q-sequence-notice]');
            return {
              ready: root.getAttribute('data-q-sequence-ready'),
              notice: notice && notice.textContent,
              noticeTag: notice && notice.tagName,
              listOpen: root.querySelector(':scope > details[data-q-sequence-list]').open,
              listText: root.querySelector('[data-q-sequence-list-message]').textContent,
              svg: root.querySelector('[data-q-sequence-svg]') !== null,
              strip: root.querySelector('[data-q-sequence-header]') !== null,
              button: root.querySelector('[data-q-sequence-action]') !== null,
              good: q('checkout').getAttribute('data-q-sequence-ready'),
            };
            """
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {
        "ready": "error",
        "notice": "This diagram could not be drawn. The full diagram is listed below.",
        "noticeTag": "P",
        "listOpen": True,
        "listText": "1. A → B: ping (async)",
        "svg": False,
        "strip": False,
        "button": False,
        "good": "true",
    }


def test_seq_without_scripts_shows_the_injected_list_with_unnumbered_steps(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('checkout');
            const style = (sel) => getComputedStyle(root.querySelector(sel)).listStyleType;
            const details = root.querySelector(':scope > details[data-q-sequence-list]');
            return {
              open: details.open,
              visible: details.getBoundingClientRect().height > 0,
              notice: root.querySelector('[data-q-sequence-stage] > [data-q-sequence-notice]').textContent,
              svg: root.querySelector('svg') !== null,
              steps: style('[data-q-sequence-list-steps]'),
              nested: style('[data-q-sequence-list-fragment="loop"] > ol'),
              deep: style('[data-q-sequence-list-fragment="alt"] > ol > li > ol'),
              trace: style('[data-q-sequence-list-trace="succeeds"] > ol'),
              messages: root.querySelectorAll('[data-q-sequence-list-message]').length,
              ready: root.hasAttribute('data-q-sequence-ready'),
            };
            """
        ),
        javaScript=False,
    )
    assert_clean(out)
    assert out["results"]["d"] == {
        "open": True,
        "visible": True,
        "notice": "JavaScript is off, so the diagram is shown as a list below.",
        "svg": False,
        "steps": "none",
        "nested": "none",
        "deep": "none",
        "trace": "none",
        "messages": 8,
        "ready": False,
    }


def test_seq_the_runtime_list_also_has_unnumbered_steps(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            """
            const root = q('checkout');
            root.querySelector('details[data-q-sequence-list]').open = true;
            const style = (sel) => getComputedStyle(root.querySelector(sel)).listStyleType;
            return [style('[data-q-sequence-list-steps]'), style('[data-q-sequence-list-fragment="alt"] > ol > li > ol'), style('[data-q-sequence-list-trace="declined"] > ol')];
            """
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == ["none", "none", "none"]


def _seq_base(*steps: dict, **extra: object) -> dict:
    return {
        "participants": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}],
        "steps": list(steps) if steps else [_seq_msg("a", "b", "x", "call")],
        **extra,
    }


def _seq_nested_detail(depth: int) -> str:
    pairs, odd = divmod(depth, 2)
    return "<ul><li>" * pairs + ("<b>x</b>" if odd else "x") + "</li></ul>" * pairs


def _seq_nested(depth: int) -> dict:
    inner: dict = _seq_msg("a", "b", "deep", "async")
    for _ in range(depth):
        inner = {"fragment": "loop", "steps": [inner]}
    return _seq_base(inner)


def _seq_bad_text_cases() -> dict[str, str]:
    return {
        "root array": "[]",
        "root null": "null",
        "truncated": '{"participants": [',
        "lone surrogate in a label": json.dumps(_seq_base(_seq_msg("a", "b", "bad \ud800", "call"))),
    }


def _seq_cases() -> dict[str, dict]:
    m = _seq_msg

    def worker(*steps: dict) -> dict:
        data = _seq_base(*steps)
        data["participants"].append({"id": "w", "label": "Worker"})
        return data

    def patched(fn) -> dict:
        data = _seq_base()
        fn(data)
        return data

    def traced(*steps: dict, **trace: object) -> dict:
        return _seq_base(m("a", "b", "x", "call", "m1"), m("b", "a", "y", "reply", "m2"), traces=[{"id": "t", "label": "T", "steps": list(steps), **trace}])

    ok_steps = [{"message": "m1", "value": 1}, {"message": "m2", "value": {"k": [1, 2]}}]
    cases: dict[str, dict] = {
        "base": _seq_base(),
        "constructor and __proto__ ids": {
            "participants": [{"id": "constructor", "label": "C"}, {"id": "__proto__", "label": "P"}],
            "steps": [m("constructor", "__proto__", "x", "call", "toString"), m("__proto__", "constructor", "y", "reply", "valueOf")],
            "traces": [{"id": "hasOwnProperty", "label": "T", "steps": [{"message": "toString", "value": 1}, {"message": "valueOf", "value": 2}]}],
        },
        "create then end": worker(m("a", "w", "go", "call", create=True), m("w", "a", "ok", "reply"), {"end": "w"}),
        "end without create": worker(m("a", "w", "go", "async"), {"end": "w"}),
        "note over repeated ids": _seq_base(m("a", "b", "x", "call"), {"note": "n", "over": ["a", "a", "c"]}),
        "all four fragments": _seq_base(
            {"fragment": "opt", "steps": [m("a", "b", "o", "async")]},
            {"fragment": "loop", "label": "l", "steps": [m("a", "b", "l", "async")]},
            {"fragment": "alt", "branches": [{"label": "x", "steps": [m("a", "b", "p", "async")]}, {"label": "y", "steps": [m("a", "c", "q", "async")]}]},
            {"fragment": "par", "label": "both", "branches": [{"label": "x", "steps": [m("a", "b", "r", "async")]}, {"label": "y", "steps": [m("a", "c", "s", "async")]}]},
        ),
        "depth 100": _seq_nested(100),
        "participant detail 32 deep": patched(lambda d: d["participants"][0].update(detail=_seq_nested_detail(32))),
        "participant detail 33 deep": patched(lambda d: d["participants"][0].update(detail=_seq_nested_detail(33))),
        "message detail 32 deep": patched(lambda d: d["steps"][0].update(detail=_seq_nested_detail(32))),
        "message detail 33 deep": patched(lambda d: d["steps"][0].update(detail=_seq_nested_detail(33))),
        "valid details": patched(lambda d: (d["participants"][0].update(detail="<p>ok <a href='#x'>link</a></p>"), d["steps"][0].update(detail="<ul><li>one</li></ul>"))),
        "empty detail": patched(lambda d: d["steps"][0].update(detail="")),
        "null kind and detail": patched(lambda d: (d["participants"][0].update(kind=None, detail=None), d["steps"][0].update(detail=None))),
        "kinds declared and unused": patched(lambda d: d.update(kinds={"x": 1, "y": 8})),
        "valid traces": traced(*ok_steps),
        "participants not a list": patched(lambda d: d.update(participants={"id": "a"})),
        "participants empty": patched(lambda d: d.update(participants=[])),
        "participants missing": patched(lambda d: d.pop("participants")),
        "participant not an object": patched(lambda d: d["participants"].append("d")),
        "participant without id": patched(lambda d: d["participants"].append({"label": "D"})),
        "participant blank id": patched(lambda d: d["participants"].append({"id": " ", "label": "D"})),
        "participant blank label": patched(lambda d: d["participants"].append({"id": "d", "label": " "})),
        "participant label number": patched(lambda d: d["participants"].append({"id": "d", "label": 3})),
        "17 participants": patched(lambda d: d["participants"].extend({"id": f"p{i}", "label": f"P{i}"} for i in range(14))),
        "16 participants": patched(lambda d: d["participants"].extend({"id": f"p{i}", "label": f"P{i}"} for i in range(13))),
        "undeclared kind": patched(lambda d: d["participants"][0].update(kind="x")),
        "kind not a string": patched(lambda d: (d.update(kinds={"1": 1}), d["participants"][0].update(kind=1))),
        "kind a prototype name": patched(lambda d: d["participants"][0].update(kind="constructor")),
        "participant detail forbidden": patched(lambda d: d["participants"][0].update(detail="<script>x</script>")),
        "participant detail unknown tag": patched(lambda d: d["participants"][0].update(detail="<table></table>")),
        "participant detail number": patched(lambda d: d["participants"][0].update(detail=3)),
        "message detail onclick": patched(lambda d: d["steps"][0].update(detail="<p onclick='x'>y</p>")),
        "message detail javascript href": patched(lambda d: d["steps"][0].update(detail="<a href='javascript:x'>y</a>")),
        "kinds not an object": patched(lambda d: d.update(kinds=[1])),
        "kinds null": patched(lambda d: d.update(kinds=None)),
        "nine kinds": patched(lambda d: d.update(kinds={f"k{i}": 1 for i in range(9)})),
        "kind color true": patched(lambda d: d.update(kinds={"k": True})),
        "kind color 0": patched(lambda d: d.update(kinds={"k": 0})),
        "kind color 9": patched(lambda d: d.update(kinds={"k": 9})),
        "kind color 1.5": patched(lambda d: d.update(kinds={"k": 1.5})),
        "kind color string": patched(lambda d: d.update(kinds={"k": "1"})),
        "kind blank name": patched(lambda d: d.update(kinds={" ": 1})),
        "duplicate participant ids": patched(lambda d: d["participants"].append({"id": "a", "label": "Again"})),
        "message id equals participant id": patched(lambda d: d["steps"][0].update(id="a")),
        "duplicate message ids": _seq_base(m("a", "b", "x", "call", "same"), m("b", "a", "y", "reply", "same")),
        "message id blank": patched(lambda d: d["steps"][0].update(id=" ")),
        "message id null": patched(lambda d: d["steps"][0].update(id=None)),
        "message id number": patched(lambda d: d["steps"][0].update(id=3)),
        "steps missing": patched(lambda d: d.pop("steps")),
        "steps empty": patched(lambda d: d.update(steps=[])),
        "steps not a list": patched(lambda d: d.update(steps={"from": "a"})),
        "no message only a note": _seq_base({"note": "n", "over": ["a"]}),
        "step empty object": _seq_base(m("a", "b", "x", "call"), {}),
        "step a string": _seq_base(m("a", "b", "x", "call"), "oops"),
        "step note and from": _seq_base({"note": "n", "over": ["a"], **m("a", "b", "x", "call")}),
        "step end and note": _seq_base(m("a", "b", "x", "call"), {"end": "a", "note": "n", "over": ["a"]}),
        "step fragment and end": _seq_base(m("a", "b", "x", "call"), {"fragment": "opt", "steps": [m("a", "b", "y", "call")], "end": "a"}),
        "message without from": _seq_base({"to": "b", "label": "x", "type": "call"}),
        "message without to": _seq_base({"from": "a", "label": "x", "type": "call"}),
        "message blank label": _seq_base(m("a", "b", " ", "call")),
        "message label number": _seq_base(m("a", "b", 3, "call")),
        "message unknown sender": _seq_base(m("z", "b", "x", "call")),
        "message unknown receiver": _seq_base(m("a", "z", "x", "call")),
        "message without type": _seq_base({"from": "a", "to": "b", "label": "x"}),
        "message type return": _seq_base(m("a", "b", "x", "return")),
        "message type number": _seq_base(m("a", "b", "x", 5)),
        "message type prototype name": _seq_base(m("a", "b", "x", "constructor")),
        "create false": _seq_base(m("a", "b", "x", "call", create=False)),
        "create a string": _seq_base(m("a", "b", "x", "call", create="yes")),
        "create null": _seq_base(m("a", "b", "x", "call", create=None)),
        "self create": _seq_base(m("a", "a", "x", "call", create=True)),
        "created twice": _seq_base(m("a", "b", "x", "call", create=True), m("c", "b", "y", "call", create=True)),
        "touch before create": _seq_base(m("b", "c", "x", "call"), m("a", "b", "y", "call", create=True)),
        "note before create": _seq_base({"note": "n", "over": ["b"]}, m("a", "b", "y", "call", create=True)),
        "end before create": _seq_base({"end": "b"}, m("a", "b", "y", "call", create=True)),
        "touch after end": _seq_base(m("a", "b", "x", "call"), {"end": "b"}, m("a", "b", "y", "call")),
        "note after end": _seq_base(m("a", "b", "x", "call"), {"end": "b"}, {"note": "n", "over": ["b"]}),
        "ended twice": _seq_base(m("a", "b", "x", "call"), {"end": "b"}, {"end": "b"}),
        "create inside a fragment then touch above": _seq_base(m("b", "c", "x", "call"), {"fragment": "opt", "steps": [m("a", "b", "y", "call", create=True)]}),
        "note without text": _seq_base(m("a", "b", "x", "call"), {"over": ["a"], "note": " "}),
        "note without over": _seq_base(m("a", "b", "x", "call"), {"note": "n"}),
        "note over empty": _seq_base(m("a", "b", "x", "call"), {"note": "n", "over": []}),
        "note over a string": _seq_base(m("a", "b", "x", "call"), {"note": "n", "over": "a"}),
        "note over unknown": _seq_base(m("a", "b", "x", "call"), {"note": "n", "over": ["z"]}),
        "note over a number": _seq_base(m("a", "b", "x", "call"), {"note": "n", "over": [3]}),
        "end unknown": _seq_base(m("a", "b", "x", "call"), {"end": "z"}),
        "end a number": _seq_base(m("a", "b", "x", "call"), {"end": 3}),
        "fragment unknown type": _seq_base({"fragment": "critical", "steps": [m("a", "b", "x", "call")]}),
        "fragment type number": _seq_base({"fragment": 3, "steps": [m("a", "b", "x", "call")]}),
        "fragment blank label": _seq_base({"fragment": "opt", "label": " ", "steps": [m("a", "b", "x", "call")]}),
        "fragment null label": _seq_base({"fragment": "opt", "label": None, "steps": [m("a", "b", "x", "call")]}),
        "fragment label number": _seq_base({"fragment": "opt", "label": 3, "steps": [m("a", "b", "x", "call")]}),
        "alt one branch": _seq_base({"fragment": "alt", "branches": [{"label": "x", "steps": [m("a", "b", "x", "call")]}]}),
        "par one branch": _seq_base({"fragment": "par", "branches": [{"label": "x", "steps": [m("a", "b", "x", "call")]}]}),
        "alt without branches": _seq_base({"fragment": "alt", "steps": [m("a", "b", "x", "call")]}),
        "alt branches not a list": _seq_base({"fragment": "alt", "branches": {"label": "x"}}),
        "alt branch without label": _seq_base({"fragment": "alt", "branches": [{"steps": [m("a", "b", "x", "call")]}, {"label": "y", "steps": [m("a", "b", "y", "call")]}]}),
        "alt branch blank label": _seq_base({"fragment": "alt", "branches": [{"label": " ", "steps": [m("a", "b", "x", "call")]}, {"label": "y", "steps": [m("a", "b", "y", "call")]}]}),
        "alt branch not an object": _seq_base({"fragment": "alt", "branches": ["x", {"label": "y", "steps": [m("a", "b", "y", "call")]}]}),
        "alt branch without steps": _seq_base({"fragment": "alt", "branches": [{"label": "x"}, {"label": "y", "steps": [m("a", "b", "y", "call")]}]}),
        "alt branch empty steps": _seq_base({"fragment": "alt", "branches": [{"label": "x", "steps": []}, {"label": "y", "steps": [m("a", "b", "y", "call")]}]}),
        "loop without steps": _seq_base(m("a", "b", "x", "call"), {"fragment": "loop"}),
        "loop empty steps": _seq_base(m("a", "b", "x", "call"), {"fragment": "loop", "steps": []}),
        "loop steps not a list": _seq_base(m("a", "b", "x", "call"), {"fragment": "loop", "steps": {"from": "a"}}),
        "opt holding a bad message": _seq_base({"fragment": "opt", "steps": [m("a", "z", "x", "call")]}),
        "traces not a list": traced(*ok_steps, ) | {"traces": {"id": "t"}},
        "traces null": _seq_base(traces=None),
        "trace not an object": _seq_base(traces=["t"]),
        "trace without id": traced(*ok_steps) | {"traces": [{"label": "T", "steps": ok_steps}]},
        "trace blank id": traced(*ok_steps) | {"traces": [{"id": " ", "label": "T", "steps": ok_steps}]},
        "trace blank label": traced(*ok_steps) | {"traces": [{"id": "t", "label": " ", "steps": ok_steps}]},
        "duplicate trace ids": traced(*ok_steps) | {"traces": [{"id": "t", "label": "T", "steps": ok_steps}, {"id": "t", "label": "U", "steps": ok_steps}]},
        "trace steps not a list": traced(*ok_steps) | {"traces": [{"id": "t", "label": "T", "steps": {"a": 1}}]},
        "trace one step": traced(ok_steps[0]),
        "trace step not an object": traced(ok_steps[0], "m2"),
        "trace step without message": traced(ok_steps[0], {"value": 1}),
        "trace step without value": traced(ok_steps[0], {"message": "m2"}),
        "trace step message number": traced(ok_steps[0], {"message": 2, "value": 1}),
        "trace step unknown message": traced(ok_steps[0], {"message": "nope", "value": 1}),
        "trace step names a participant": traced(ok_steps[0], {"message": "a", "value": 1}),
        "trace step note null": traced(ok_steps[0], {"message": "m2", "value": 1, "note": None}),
        "trace step note number": traced(ok_steps[0], {"message": "m2", "value": 1, "note": 3}),
        "trace step value null is a value": traced(ok_steps[0], {"message": "m2", "value": None}),
        "trace value over 400 lines": traced(ok_steps[0], {"message": "m2", "value": list(range(400))}),
        "trace value at 400 lines": traced(ok_steps[0], {"message": "m2", "value": list(range(398))}),
        "trace value lone surrogate": traced(ok_steps[0], {"message": "m2", "value": "x\ud800"}),
    }
    return cases


def test_seq_runtime_accepts_and_rejects_exactly_what_the_python_check_does(seq_page: Path) -> None:
    sys.path.insert(0, str(SKILL / "scripts"))
    from htmlkit import kitcheck

    def python_verdict(text: str) -> str:
        builder = kitcheck._TreeBuilder()
        builder.feed(f'<q-sequence summary="s"><script type="application/json">{text}</script></q-sequence>')
        builder.close()
        builder.finish()
        node = next(n for n in builder.nodes if n.tag == "q-sequence")
        return "error" if kitcheck._validate_sequence_node(node, lambda _l, _m: None, lambda _l, _m: None) is None else "true"

    texts = {name: json.dumps(data) for name, data in _seq_cases().items()}
    texts.update(_seq_bad_text_cases())
    names = list(texts)
    expected = [python_verdict(texts[name]) for name in names]
    assert "true" in expected and "error" in expected
    out = run(
        seq_page,
        ev(
            """(async (texts) => {
              const host = document.createElement('div');
              document.body.appendChild(host);
              const els = texts.map((text) => {
                const el = document.createElement('q-sequence');
                el.setAttribute('summary', 's');
                const script = document.createElement('script');
                script.type = 'application/json';
                script.textContent = text;
                el.appendChild(script);
                host.appendChild(el);
                return el;
              });
              for (let i = 0; i < 100 && !els.every((el) => el.hasAttribute('data-q-sequence-ready')); i += 1) {
                await new Promise((r) => setTimeout(r, 100));
              }
              return els.map((el) => el.getAttribute('data-q-sequence-ready'));
            })(""" + json.dumps([texts[n] for n in names]) + ")",
            "got",
        ),
    )
    assert_clean(out)
    got = out["results"]["got"]
    assert len(got) == len(names)
    mismatches = [(n, e, g) for n, e, g in zip(names, expected, got) if e != g]
    assert mismatches == []


SEQ_MAKE = """
const make = (data, id) => {
  const el = document.createElement('q-sequence');
  el.id = id;
  el.setAttribute('summary', 's');
  const script = document.createElement('script');
  script.type = 'application/json';
  script.textContent = JSON.stringify(data);
  el.appendChild(script);
  document.body.appendChild(el);
  return el;
};
const settle = async (el) => {
  for (let i = 0; i < 100 && !el.hasAttribute('data-q-sequence-ready'); i += 1) {
    await new Promise((r) => setTimeout(r, 50));
  }
  return el.getAttribute('data-q-sequence-ready');
};
"""


def test_seq_invalid_data_during_a_pending_font_wait_leaves_only_the_error_notice(seq_page: Path) -> None:
    out = run(
        seq_page,
        _seq_eval(
            SEQ_MAKE
            + """
            Object.defineProperty(document.fonts, 'ready', { configurable: true, value: new Promise((r) => { window.finishFonts = r; }) });
            const el = make(%s, 'stale');
            await new Promise((r) => setTimeout(r, 100));
            el.querySelector('script').textContent = '{ not json';
            await new Promise((r) => setTimeout(r, 200));
            window.finishFonts();
            await new Promise((r) => setTimeout(r, 400));
            delete document.fonts.ready;
            return {
              ready: el.getAttribute('data-q-sequence-ready'),
              notice: el.querySelectorAll('[data-q-sequence-notice]').length,
              svg: el.querySelectorAll('[data-q-sequence-svg]').length,
            };
            """
            % json.dumps(SEQ_BAD_DATA | {"steps": [_seq_msg("a", "b-ok", "ping", "async")]})
        ),
    )
    assert_clean(out)
    assert out["results"]["d"] == {"ready": "error", "notice": 1, "svg": 0}


def test_seq_a_label_note_or_header_with_one_long_word_stays_inside_the_svg(seq_page: Path) -> None:
    word = "W" * 130
    data = {
        "participants": [{"id": "a", "label": "A"}, {"id": "b", "label": word}, {"id": "c", "label": "C"}],
        "steps": [
            _seq_msg("a", "c", word, "async"),
            {"note": word, "over": ["b"]},
            _seq_msg("b", "b", word, "async"),
        ],
    }
    out = run(
        seq_page,
        _seq_eval(
            SEQ_MAKE
            + """
            const el = make(%s, 'longword');
            const ready = await settle(el);
            const svg = el.querySelector('[data-q-sequence-svg]');
            const width = num(svg, 'width');
            const boxes = [...svg.querySelectorAll('text, [data-q-sequence-note] rect')].map((n) => {
              const b = n.getBBox();
              return { tag: n.tagName, left: b.x, right: b.x + b.width };
            });
            const note = el.querySelector('[data-q-sequence-note] rect');
            return {
              ready, width, count: boxes.length,
              outside: boxes.filter((b) => b.left < -0.5 || b.right > width + 0.5),
              noteLeft: num(note, 'x'), noteRight: num(note, 'x') + num(note, 'width'),
              labelLines: el.querySelector('[data-q-sequence-label]').querySelectorAll('tspan').length,
            };
            """
            % json.dumps(data)
        ),
    )
    assert_clean(out)
    got = out["results"]["d"]
    assert got["ready"] == "true"
    assert got["outside"] == []
    assert got["noteLeft"] >= 0 and got["noteRight"] <= got["width"]
    assert got["labelLines"] > 1


def test_seq_an_unanswered_call_in_a_fragment_closes_at_the_fragment_edge(seq_page: Path) -> None:
    m = _seq_msg
    cases = {
        "opt": _seq_base({"fragment": "opt", "steps": [m("a", "b", "call", "call")]}, m("a", "b", "later", "async")),
        "loop": _seq_base({"fragment": "loop", "steps": [m("a", "b", "call", "call")]}, m("a", "b", "later", "async")),
    }
    out = run(
        seq_page,
        _seq_eval(
            SEQ_MAKE
            + """
            const result = {};
            const cases = %s;
            for (const name of Object.keys(cases)) {
              const el = make(cases[name], 'frag-' + name);
              await settle(el);
              const box = el.querySelector('[data-q-sequence-fragment-box]');
              result[name] = { boxEnd: num(box, 'y') + num(box, 'height'), bars: barsOf(el, 'b') };
            }
            return result;
            """
            % json.dumps(cases)
        ),
    )
    assert_clean(out)
    for name, got in out["results"]["d"].items():
        assert len(got["bars"]) == 1, name
        assert _close(got["bars"][0]["bottom"], got["boxEnd"], 0.01), (name, got)


def test_seq_detail_nesting_passes_at_32_deep_and_fails_hard_at_33(seq_page: Path) -> None:
    def on_part(depth: int) -> dict:
        data = _seq_base()
        data["participants"][0]["detail"] = _seq_nested_detail(depth)
        return data

    def on_msg(depth: int) -> dict:
        data = _seq_base()
        data["steps"][0]["detail"] = _seq_nested_detail(depth)
        return data

    cases = {"part32": on_part(32), "part33": on_part(33), "msg32": on_msg(32), "msg33": on_msg(33)}
    out = run(
        seq_page,
        _seq_eval(
            SEQ_MAKE
            + """
            const result = {};
            const cases = %s;
            for (const name of Object.keys(cases)) {
              const el = make(cases[name], 'depth-' + name);
              const ready = await settle(el);
              result[name] = { ready, notice: el.querySelectorAll('[data-q-sequence-notice]').length, svg: el.querySelectorAll('[data-q-sequence-svg]').length };
            }
            return result;
            """
            % json.dumps(cases)
        ),
    )
    assert_clean(out)
    ok = {"ready": "true", "notice": 0, "svg": 1}
    bad = {"ready": "error", "notice": 1, "svg": 0}
    assert out["results"]["d"] == {"part32": ok, "part33": bad, "msg32": ok, "msg33": bad}


SEQ_FOCUS_JS = """
const root = q('checkout');
const drawer = () => root.querySelector(':scope > aside[data-q-flow-drawer]');
const numbers = (sel) => [...root.querySelectorAll(sel)].map((m) => Number(m.getAttribute('data-q-sequence-message')));
const ids = (sel, attr) => [...new Set([...root.querySelectorAll(sel)].map((e) => e.getAttribute(attr)))].sort();
const state = () => {
  const d = drawer();
  const h3 = d.querySelector('h3');
  return {
    focus: root.getAttribute('data-q-sequence-focus'),
    focusMessage: root.getAttribute('data-q-sequence-focus-message'),
    litMessages: numbers('[data-q-sequence-message][data-q-sequence-lit]'),
    dimMessages: numbers('[data-q-sequence-message][data-q-sequence-dim]'),
    litLifelines: ids('[data-q-sequence-lifeline][data-q-sequence-lit]', 'data-q-sequence-lifeline'),
    dimLifelines: ids('[data-q-sequence-lifeline][data-q-sequence-dim]', 'data-q-sequence-lifeline'),
    litBars: ids('[data-q-sequence-bar][data-q-sequence-lit]', 'data-q-sequence-bar'),
    dimBars: ids('[data-q-sequence-bar][data-q-sequence-dim]', 'data-q-sequence-bar'),
    litNotes: root.querySelectorAll('[data-q-sequence-note][data-q-sequence-lit]').length,
    dimNotes: root.querySelectorAll('[data-q-sequence-note][data-q-sequence-dim]').length,
    litHeaders: ids('[data-q-sequence-header][data-q-sequence-lit]', 'data-q-sequence-header'),
    dimHeaders: root.querySelectorAll('[data-q-sequence-header][data-q-sequence-dim]').length,
    fragmentMarks: root.querySelectorAll('[data-q-sequence-fragment][data-q-sequence-lit], [data-q-sequence-fragment][data-q-sequence-dim], [data-q-sequence-fragment] [data-q-sequence-lit], [data-q-sequence-fragment] [data-q-sequence-dim]').length,
    open: !d.hasAttribute('data-q-inactive'),
    title: h3 ? h3.textContent : null,
    text: d.textContent,
    buttons: [...d.querySelectorAll('button')].map((b) => b.textContent).filter((t) => t !== 'Close'),
    active: document.activeElement ? (document.activeElement.getAttribute('data-q-sequence-message') || document.activeElement.getAttribute('data-q-sequence-header')) : null,
  };
};
"""

SEQ_STRIPE = '#checkout [data-q-sequence-header="stripe"]'
SEQ_MSG_HIT = '#checkout [data-q-sequence-message="{n}"] [data-q-sequence-hit]'


def test_seq_clicking_a_participant_lights_its_messages_dims_the_rest_and_opens_its_drawer(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 800}},
        {"click": SEQ_STRIPE},
        _seq_eval(
            SEQ_FOCUS_JS
            + """
            const s = state();
            const d = drawer();
            s.kindTag = d.querySelector('[data-q-flow-drawer-kind]').textContent;
            s.strong = d.querySelector('[data-q-flow-drawer-detail] strong').textContent;
            s.directChild = d.parentElement === root && d.classList.contains('q-flow-drawer');
            s.label = d.getAttribute('aria-label');
            const dimmed = msg(root, 1);
            const lit = msg(root, 3);
            s.dimOpacity = getComputedStyle(dimmed).opacity;
            s.litOpacity = getComputedStyle(lit).opacity;
            s.litStroke = getComputedStyle(lit.querySelector('[data-q-sequence-line]')).strokeWidth;
            s.litLifeline = getComputedStyle(root.querySelector('[data-q-sequence-lifeline="stripe"]')).strokeWidth;
            s.fragmentOpacity = getComputedStyle(root.querySelector('[data-q-sequence-fragment]')).opacity;
            return s;
            """,
            "on",
        ),
        {"click": SEQ_STRIPE},
        _seq_eval(SEQ_FOCUS_JS + "return state();", "off"),
    )
    assert_clean(out)
    on, off = out["results"]["on"], out["results"]["off"]
    assert on["focus"] == "stripe" and on["focusMessage"] is None
    assert on["litMessages"] == [3, 4, 5] and on["dimMessages"] == [1, 2, 6, 7, 8]
    assert on["litLifelines"] == ["stripe"] and on["dimLifelines"] == ["billing", "checkout", "ledger", "shopper"]
    assert on["litBars"] == ["stripe"] and on["dimBars"] == ["billing", "checkout"]
    assert (on["litNotes"], on["dimNotes"]) == (0, 1)
    assert on["litHeaders"] == ["stripe"] and on["dimHeaders"] == 0
    assert on["fragmentMarks"] == 0 and on["fragmentOpacity"] == "1"
    assert (on["dimOpacity"], on["litOpacity"], on["litStroke"], on["litLifeline"]) == ("0.22", "1", "2.5px", "2.5px")
    assert on["open"] is True and on["directChild"] is True and on["label"] == "Details"
    assert on["title"] == "Stripe" and on["kindTag"] == "external" and on["strong"] == "idempotent"
    assert "Card processor. Charges are idempotent." in on["text"]
    assert on["buttons"] == ["receives 3. create charge", "sends 4. charge succeeded", "sends 5. card declined"]
    assert off["focus"] is None and off["focusMessage"] is None and off["open"] is False
    for key in ("litMessages", "dimMessages", "litLifelines", "dimLifelines", "litBars", "dimBars", "litHeaders"):
        assert off[key] == [], key
    assert (off["litNotes"], off["dimNotes"], off["fragmentMarks"]) == (0, 0, 0)


def test_seq_clicking_a_message_opens_its_drawer_with_the_pair_the_fragments_and_the_detail(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 800}},
        {"click": SEQ_MSG_HIT.format(n=2)},
        _seq_eval(SEQ_FOCUS_JS + "return state();", "two"),
        {"click": '#checkout [data-q-sequence-goto-message="7"]'},
        _seq_eval(SEQ_FOCUS_JS + "const s = state(); s.roving = msg(root, 7).getAttribute('tabindex'); return s;", "seven"),
        {"click": SEQ_MSG_HIT.format(n=5)},
        _seq_eval(SEQ_FOCUS_JS + "return state();", "five"),
        {"click": SEQ_MSG_HIT.format(n=3)},
        _seq_eval(SEQ_FOCUS_JS + "return state();", "three"),
        {"click": "#checkout > aside[data-q-flow-drawer] [data-q-flow-drawer-close]"},
        _seq_eval(SEQ_FOCUS_JS + "return state();", "closed"),
        {"click": SEQ_MSG_HIT.format(n=2)},
        {"click": SEQ_MSG_HIT.format(n=2)},
        _seq_eval(SEQ_FOCUS_JS + "return state();", "again"),
        {"click": SEQ_MSG_HIT.format(n=2)},
        _seq_eval(SEQ_FOCUS_JS + "root.querySelector('[data-q-sequence-svg]').dispatchEvent(new MouseEvent('click', { bubbles: true })); return state();", "empty"),
    )
    assert_clean(out)
    two, seven, five, three = (out["results"][k] for k in ("two", "seven", "five", "three"))
    assert two["focusMessage"] == "2" and two["focus"] is None
    assert two["litMessages"] == [2] and two["dimMessages"] == [1, 3, 4, 5, 6, 7, 8]
    assert two["litHeaders"] == ["billing", "checkout"] and two["dimHeaders"] == 0
    assert two["litLifelines"] == [] and two["dimLifelines"] == ["billing", "checkout", "ledger", "shopper", "stripe"]
    assert (two["litNotes"], two["dimNotes"], two["fragmentMarks"]) == (0, 1, 0)
    assert two["title"] == "2. charge order" and two["open"] is True
    assert "Checkout → Billing" in two["text"] and "call" in two["text"]
    assert "answered by 7. order paid" in two["buttons"]
    assert seven["focusMessage"] == "7" and seven["litMessages"] == [7] and seven["title"] == "7. order paid"
    assert "answers 2. charge order" in seven["buttons"] and seven["roving"] == "0" and seven["active"] == "7"
    assert five["title"] == "5. card declined"
    assert "inside loop: up to 3 attempts, alt: card declined" in five["text"]
    assert "answers 3. create charge" in five["buttons"]
    assert [t for t in three["buttons"] if t.startswith("answer")] == ["answered by 4. charge succeeded", "answered by 5. card declined"]
    at = {k: three["text"].index(k) for k in ("3. create charge", "Billing → Stripe", "answered by 4.", "answered by 5.", "inside loop: up to 3 attempts", "payment_method")}
    assert list(at.values()) == sorted(at.values()), at
    closed, again, empty = (out["results"][k] for k in ("closed", "again", "empty"))
    for gone in (closed, again, empty):
        assert gone["focusMessage"] is None and gone["open"] is False and gone["litMessages"] == [] and gone["dimMessages"] == []
    assert closed["active"] == "3"


def test_seq_keyboard_roves_headers_and_messages_and_announces_the_focused_message(seq_page: Path) -> None:
    before = "const b = document.createElement('button'); b.id = 'before-' + '{id}'; b.textContent = 'before'; q('{id}').before(b); b.focus();"
    where = """
    const a = document.activeElement;
    return { header: a.getAttribute('data-q-sequence-header'), message: a.getAttribute('data-q-sequence-message'), tag: a.tagName.toLowerCase(), inList: !!a.closest('details[data-q-sequence-list]'), inRoot: !!a.closest('#checkout') };
    """
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 800}},
        _seq_eval(before.format(id="checkout")),
        {"press": "Tab"},
        _seq_eval("return document.activeElement.getAttribute('data-q-sequence-action');", "toolbar"),
        {"press": "Tab"},
        _seq_eval(where, "tab"),
        _seq_eval(
            """
            const stops = [...q('checkout').querySelectorAll('[data-q-sequence-header], [data-q-sequence-message]')];
            return { total: stops.length, zero: stops.filter((e) => e.getAttribute('tabindex') === '0').map((e) => e.getAttribute('data-q-sequence-header')) };
            """,
            "roving",
        ),
        {"press": "Tab"},
        _seq_eval(where, "out"),
        {"press": "Shift+Tab"},
        _seq_eval(where, "back"),
        {"press": "ArrowRight"},
        _seq_eval(where, "right"),
        {"press": "ArrowLeft"},
        _seq_eval(where, "left"),
        {"press": "ArrowLeft"},
        _seq_eval(where, "leftEdge"),
        {"focus": SEQ_STRIPE},
        {"press": "ArrowDown"},
        _seq_eval(where, "downFromStripe"),
        {"press": "ArrowDown"},
        _seq_eval(where, "four"),
        {"press": "ArrowDown"},
        _seq_eval(where, "five"),
        {"press": "ArrowUp"},
        _seq_eval(where, "upToFour"),
        {"focus": '#checkout [data-q-sequence-message="8"]'},
        {"press": "ArrowDown"},
        _seq_eval(where, "pastEnd"),
        {"focus": '#checkout [data-q-sequence-message="1"]'},
        {"press": "ArrowUp"},
        _seq_eval(where, "upFromOne"),
        {"focus": '#checkout [data-q-sequence-message="3"]'},
        {"press": "Enter"},
        _seq_eval(SEQ_FOCUS_JS + "return { live: root.querySelector(':scope > [data-q-sequence-live]').textContent, label: msg(root, 3).getAttribute('aria-label'), state: state() };", "enter"),
        {"press": "Escape"},
        _seq_eval(SEQ_FOCUS_JS + "return { live: root.querySelector(':scope > [data-q-sequence-live]').textContent, state: state() };", "escape"),
        {"focus": '#checkout [data-q-sequence-header="billing"]'},
        {"press": "Enter"},
        _seq_eval(SEQ_FOCUS_JS + "return { live: root.querySelector(':scope > [data-q-sequence-live]').textContent, state: state() };", "headerEnter"),
        _seq_eval(before.format(id="session")),
        {"press": "Tab"},
        _seq_eval(where, "sessionTab"),
        {"press": "ArrowRight"},
        _seq_eval(
            where
            + """
            """,
            "created",
        ),
        _seq_eval(
            """
            const a = document.activeElement;
            return { late: a.hasAttribute('data-q-sequence-late'), opacity: getComputedStyle(a).opacity, tabindex: a.getAttribute('tabindex') };
            """,
            "createdLook",
        ),
    )
    assert_clean(out)
    r = out["results"]
    assert r["toolbar"] == "trace"
    assert (r["tab"]["header"], r["tab"]["tag"]) == ("shopper", "button")
    assert r["roving"] == {"total": 5 + 8, "zero": ["shopper"]}
    assert r["out"]["inList"] and r["out"]["tag"] == "summary" and r["out"]["header"] is None
    assert r["back"]["header"] == "shopper"
    assert r["right"]["header"] == "checkout" and r["left"]["header"] == "shopper" and r["leftEdge"]["header"] == "shopper"
    assert r["downFromStripe"]["message"] == "3"
    assert r["four"]["message"] == "4" and r["five"]["message"] == "5" and r["upToFour"]["message"] == "4"
    assert r["pastEnd"]["message"] == "8"
    assert r["upFromOne"]["header"] == "shopper"
    announced = "Message 3 of 8, Billing to Stripe, create charge, call"
    assert r["enter"]["live"] == announced == r["enter"]["label"]
    assert r["enter"]["state"]["focusMessage"] == "3" and r["enter"]["state"]["open"] is True
    esc = r["escape"]["state"]
    assert esc["focusMessage"] is None and esc["open"] is False and esc["active"] == "3"
    assert r["headerEnter"]["live"] == "Billing, service, sends 3, receives 3"
    assert r["headerEnter"]["state"]["focus"] == "billing" and r["headerEnter"]["state"]["active"] == "billing"
    assert r["sessionTab"]["header"] == "billing"
    assert r["created"]["header"] == "receipt-worker"
    assert r["createdLook"] == {"late": True, "opacity": "1", "tabindex": "0"}


def test_seq_moving_keyboard_focus_scrolls_the_target_into_view_under_reduced_motion(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 375, "height": 500}},
        {"emulate": {"reducedMotion": "reduce"}},
        _seq_eval("window.scrollTo(0, q('checkout').getBoundingClientRect().top + window.scrollY - 20)"),
        {"focus": '#checkout [data-q-sequence-header="shopper"]'},
        {"press": "ArrowRight"},
        {"press": "ArrowRight"},
        {"press": "ArrowRight"},
        {"wait": 700},
        _seq_eval(
            """
            const root = q('checkout');
            const stage = root.querySelector('[data-q-sequence-stage]');
            const strip = root.querySelector('[data-q-sequence-pinned]');
            const h = document.activeElement.getBoundingClientRect();
            const s = stage.getBoundingClientRect();
            return { id: document.activeElement.getAttribute('data-q-sequence-header'), left: h.left - s.left, right: s.right - h.right, scrolled: stage.scrollLeft > 100, strip: strip.scrollLeft, page: window.scrollX };
            """,
            "header",
        ),
        *[{"press": "ArrowDown"}] * 6,
        {"wait": 700},
        _seq_eval(
            """
            const root = q('checkout');
            const strip = root.querySelector('[data-q-sequence-pinned]').getBoundingClientRect();
            const m = document.activeElement.getBoundingClientRect();
            return { n: document.activeElement.getAttribute('data-q-sequence-message'), top: m.top - strip.bottom, bottom: window.innerHeight - m.bottom };
            """,
            "message",
        ),
        *[{"press": "ArrowUp"}] * 7,
        {"wait": 700},
        _seq_eval(
            """
            const root = q('checkout');
            const strip = root.querySelector('[data-q-sequence-pinned]').getBoundingClientRect();
            const m = document.activeElement.getBoundingClientRect();
            return { n: document.activeElement.getAttribute('data-q-sequence-message'), top: m.top - strip.bottom };
            """,
            "up",
        ),
    )
    assert_clean(out)
    header, message, up = (out["results"][k] for k in ("header", "message", "up"))
    assert header["id"] == "stripe" and header["scrolled"] and header["left"] >= -1 and header["right"] >= -1
    assert header["strip"] == 0 and header["page"] == 0
    assert message["n"] == "8" and message["top"] >= 0 and message["bottom"] >= 0
    assert up["n"] == "1" and up["top"] >= 0


def test_seq_the_drawer_is_a_bottom_sheet_on_a_phone_and_a_sticky_second_column_beside_the_diagram(seq_page: Path) -> None:
    probe = """
    const root = q('checkout');
    const d = root.querySelector(':scope > aside[data-q-flow-drawer]');
    const cs = getComputedStyle(d);
    const r = d.getBoundingClientRect();
    const stage = root.querySelector('[data-q-sequence-stage]').getBoundingClientRect();
    return { position: cs.position, maxHeight: cs.maxHeight, left: r.left, right: r.right, top: r.top, bottom: r.bottom, height: r.height, width: r.width,
      vh: window.innerHeight, vw: document.documentElement.clientWidth, cssTop: cs.top, column: cs.gridColumnStart, rootDisplay: getComputedStyle(root).display,
      columns: getComputedStyle(root).gridTemplateColumns.split(' ').length, stageRight: stage.right, overflowY: cs.overflowY, shown: cs.display !== 'none' };
    """
    out = run(
        seq_page,
        {"viewport": {"width": 375, "height": 800}},
        {"click": SEQ_MSG_HIT.format(n=1)},
        _seq_eval(probe, "phone"),
        {"viewport": {"width": 1280, "height": 800}},
        _seq_eval("window.scrollTo(0, 0)"),
        {"click": SEQ_MSG_HIT.format(n=2)},
        _seq_eval(probe, "wideTop"),
        _seq_eval("window.scrollTo(0, q('checkout').getBoundingClientRect().top + window.scrollY + 200)"),
        {"wait": 700},
        _seq_eval(probe, "wideScrolled"),
        _seq_eval("window.scrollTo(0, 0)"),
        {"click": "#checkout [data-q-flow-drawer-close]"},
        _seq_eval(probe, "wideClosed"),
        {"emulate": {"media": "print"}},
        _seq_eval(
            """
            const d = q('checkout').querySelector(':scope > aside[data-q-flow-drawer]');
            return { display: getComputedStyle(d).display };
            """,
            "print",
        ),
    )
    assert_clean(out)
    phone, top, scrolled, closed = (out["results"][k] for k in ("phone", "wideTop", "wideScrolled", "wideClosed"))
    assert phone["position"] == "fixed" and phone["maxHeight"] == "440px" and phone["overflowY"] == "auto"
    assert phone["left"] == 0 and phone["width"] == phone["vw"] and phone["bottom"] == phone["vh"] and phone["height"] <= 440
    assert phone["rootDisplay"] == "block"
    assert top["rootDisplay"] == "grid" and top["columns"] == 2 and top["column"] == "2" and top["position"] == "sticky"
    assert top["left"] >= top["stageRight"] - 1
    assert scrolled["position"] == "sticky" and scrolled["top"] >= 0 and scrolled["bottom"] <= scrolled["vh"]
    assert abs(scrolled["top"] - float(scrolled["cssTop"].removesuffix("px"))) <= 1
    assert closed["rootDisplay"] == "block" and closed["shown"] is False
    assert out["results"]["print"]["display"] == "none"


SEQ_WITH_FLOW = _seq_element("checkout", "Checkout charges the card through Billing and Stripe, retrying a declined card.", SEQ_CHECKOUT_DATA) + _seq_element(
    "selfmsg", "Billing validates a cart it was sent.", SEQ_SELF_DATA
) + """
<q-flow id="plain" summary="A graph with no traces.">
  <script type="application/json">
  {"nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], "edges": [{"from": "a", "to": "b"}]}
  </script>
</q-flow>
"""


@pytest.fixture(scope="module")
def seq_flow_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-sequence-flow")
    src = work / "sequence-flow.src.html"
    src.write_text(HEADER + SEQ_WITH_FLOW, encoding="utf-8")
    return _build(src, work / "sequence-flow.html")


def test_seq_escape_clears_focus_unless_the_key_came_from_inside_another_diagram(seq_flow_page: Path) -> None:
    probe = """
    const root = q('checkout');
    const d = root.querySelector(':scope > aside[data-q-flow-drawer]');
    const a = document.activeElement;
    return { focus: root.getAttribute('data-q-sequence-focus-message'), open: !d.hasAttribute('data-q-inactive'), active: a ? (a.id || a.getAttribute('data-q-flow-node') || a.getAttribute('data-q-sequence-message')) : null };
    """
    outside = "const b = document.createElement('button'); b.id = 'outside'; b.textContent = 'outside'; document.body.prepend(b); b.focus();"
    out = run(
        seq_flow_page,
        {"viewport": {"width": 1280, "height": 800}},
        {"click": SEQ_MSG_HIT.format(n=2)},
        _seq_eval(probe, "focused"),
        {"focus": "#plain [data-q-flow-node]"},
        {"press": "Escape"},
        _seq_eval(probe, "fromFlow"),
        {"focus": '#selfmsg [data-q-sequence-message="1"]'},
        {"press": "Escape"},
        _seq_eval(probe, "fromOtherSequence"),
        _seq_eval(outside),
        {"press": "Escape"},
        _seq_eval(probe, "fromOutside"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["focused"]["focus"] == "2" and r["focused"]["open"] is True
    assert r["fromFlow"]["focus"] == "2" and r["fromFlow"]["open"] is True
    assert r["fromOtherSequence"]["focus"] == "2" and r["fromOtherSequence"]["open"] is True
    assert r["fromOutside"]["focus"] is None and r["fromOutside"]["open"] is False
    assert r["fromOutside"]["active"] == "outside"


# --- q-sequence trace mode --------------------------------------------------------------------

SEQ_TRACE_BTN = '#checkout [data-q-sequence-action="trace"]'
SEQ_TRACE_NEXT = "#checkout [data-q-flow-trace-next]"
SEQ_TRACE_PICKER = "#checkout [data-q-flow-trace-picker]"
SEQ_TRACE_COLLAPSE = "#checkout [data-q-sequence-trace-collapse]"

SEQ_TRACE_HELPERS = """
const root = q('checkout');
const panel = root.querySelector(':scope > [data-q-flow-trace-panel]');
const numberOf = (g) => Number(g.getAttribute('data-q-sequence-message'));
const msgs = () => [...root.querySelectorAll('[data-q-sequence-message]')];
const keyOf = (li) => li.querySelector(':scope > [data-q-flow-key], :scope > details > summary > [data-q-flow-key]').textContent.replace(/: $/, '');
const changes = () => [...panel.querySelectorAll('[data-q-flow-trace-value] > ul > li[data-q-flow-field]')]
  .filter((li) => li.getAttribute('data-q-flow-change') !== 'same')
  .map((li) => [keyOf(li), li.getAttribute('data-q-flow-change')]);
const maskDotsActive = (g) => {
  const pulse = g.querySelector('[data-q-sequence-pulse]');
  const id = pulse.getAttribute('mask').replace(/^url\\(#|\\)$/g, '');
  return [...document.getElementById(id).querySelectorAll('circle')].filter((c) => !c.hasAttribute('data-q-inactive')).length;
};
const state = () => ({
  tracing: root.hasAttribute('data-q-sequence-tracing'),
  pressed: root.querySelector('[data-q-sequence-action="trace"]').getAttribute('aria-pressed'),
  panelOpen: !panel.hasAttribute('data-q-inactive'),
  drawerOpen: !root.querySelector(':scope > aside[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
  focus: root.getAttribute('data-q-sequence-focus') || root.getAttribute('data-q-sequence-focus-message'),
  counter: panel.querySelector('[data-q-flow-trace-counter]').textContent,
  current: msgs().filter((g) => g.hasAttribute('data-q-sequence-current')).map(numberOf),
  lit: msgs().filter((g) => g.hasAttribute('data-q-sequence-lit')).map(numberOf),
  dim: msgs().filter((g) => g.hasAttribute('data-q-sequence-dim')).map(numberOf),
  notesDim: [...root.querySelectorAll('[data-q-sequence-note]')].map((n) => n.hasAttribute('data-q-sequence-dim')),
  pulsing: msgs().filter((g) => !g.querySelector('[data-q-sequence-pulse]').hasAttribute('data-q-inactive')).map(numberOf),
  dots: msgs().map(maskDotsActive).reduce((a, b) => a + b, 0),
  dotsOf: msgs().filter((g) => maskDotsActive(g) > 0).map(numberOf),
  widths: msgs().map((g) => g.querySelector('[data-q-sequence-line]').getAttribute('stroke-width')),
});
"""


def _seq_trace_eval(body: str, name: str = "d") -> dict:
    return ev(f"(async () => {{ {SEQ_HELPERS} {SEQ_TRACE_HELPERS} {body} }})()", name)


def _seq_pick(label: str) -> dict:
    return {"select": {"selector": SEQ_TRACE_PICKER, "label": label}}


def test_seq_step_through_shows_only_with_traces_and_opens_on_step_one_clearing_focus(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 800}},
        _seq_eval(
            """
            const other = q('selfmsg');
            return {
              buttons: other.querySelectorAll('[data-q-sequence-action]').length,
              controlsEmpty: other.querySelector('[data-q-sequence-controls]').children.length,
              panel: other.querySelector('[data-q-flow-trace-panel]') !== null,
              aria: q('checkout').querySelector('[data-q-sequence-action="trace"]').getAttribute('aria-pressed'),
              text: q('checkout').querySelector('[data-q-sequence-action="trace"]').textContent,
              label: q('checkout').querySelector('[data-q-sequence-action="trace"]').getAttribute('aria-label'),
              actions: [...q('checkout').querySelectorAll('[data-q-sequence-controls] button')].map((b) => b.getAttribute('data-q-sequence-action')),
            };
            """,
            "plain",
        ),
        {"click": '#checkout [data-q-sequence-header="stripe"]'},
        _seq_trace_eval("return state();", "focused"),
        {"click": SEQ_TRACE_BTN},
        _seq_trace_eval(
            """
            const p = panel.getBoundingClientRect();
            const stage = root.querySelector('[data-q-sequence-stage]').getBoundingClientRect();
            const cs = getComputedStyle(panel);
            return Object.assign(state(), {
              focusAttrs: [root.hasAttribute('data-q-sequence-focus'), root.hasAttribute('data-q-sequence-focus-message')],
              headersLit: root.querySelectorAll('[data-q-sequence-header][data-q-sequence-lit]').length,
              picker: panel.querySelector('[data-q-flow-trace-picker]').value,
              options: [...panel.querySelectorAll('[data-q-flow-trace-picker] option')].map((o) => o.textContent),
              marks: panel.querySelectorAll('[data-q-flow-trace-value] [data-q-flow-change]:not([data-q-flow-change="same"])').length,
              rootDisplay: getComputedStyle(root).display,
              position: cs.position,
              column: cs.gridColumnStart,
              besideStage: p.left >= stage.right - 1,
              activeIsNext: document.activeElement === panel.querySelector('[data-q-flow-trace-next]'),
              backDisabled: panel.querySelector('[data-q-flow-trace-back]').disabled,
              stepDots: panel.querySelectorAll('[data-q-flow-trace-dot]').length,
              ariaDot: panel.querySelector('[data-q-flow-trace-dot="1"]').getAttribute('aria-label'),
              pulseDots: maskDotsActive(msg(root, 1)),
              pulseWidth: msg(root, 1).querySelector('[data-q-sequence-pulse]').getAttribute('stroke-width'),
              pulseBases: root.querySelectorAll('defs mask').length,
              grad: root.querySelectorAll('defs radialGradient').length,
              maskIds: [...root.querySelectorAll('defs mask')].every((m) => m.id.startsWith(root._uid)),
              gradId: root.querySelector('defs radialGradient').id.startsWith(root._uid),
              lineStroke: getComputedStyle(msg(root, 1).querySelector('[data-q-sequence-line]')).stroke,
              accent: getComputedStyle(root).getPropertyValue('--q-color-accent'),
            });
            """,
            "open",
        ),
    )
    assert_clean(out)
    r = out["results"]
    assert r["plain"] == {
        "buttons": 0,
        "controlsEmpty": 0,
        "panel": False,
        "aria": "false",
        "text": "Step through",
        "label": "Step through a trace",
        "actions": ["trace"],
    }
    assert r["focused"]["focus"] == "stripe" and r["focused"]["drawerOpen"] is True and r["focused"]["tracing"] is False
    assert r["focused"]["panelOpen"] is False and r["focused"]["dim"] == [1, 2, 6, 7, 8]
    o = r["open"]
    assert o["focusAttrs"] == [False, False] and o["focus"] is None and o["drawerOpen"] is False
    assert o["tracing"] is True and o["pressed"] == "true" and o["panelOpen"] is True
    assert o["counter"] == "Step 1 of 6, message 1, Shopper to Checkout, place order"
    assert o["picker"] == "succeeds" and o["options"] == ["Card succeeds", "Declined, then retried"]
    assert o["current"] == [1] and o["lit"] == [1]
    assert o["dim"] == [5, 8] and o["notesDim"] == [True]
    assert o["headersLit"] == 0
    assert o["pulsing"] == [1] and o["dotsOf"] == [1] and o["pulseDots"] >= 1 and o["dots"] == o["pulseDots"]
    assert o["pulseWidth"] == "6"
    assert o["pulseBases"] == 8 and o["grad"] == 1 and o["maskIds"] is True and o["gradId"] is True
    assert o["marks"] == 0
    assert o["rootDisplay"] == "grid" and o["position"] == "sticky" and o["column"] == "2" and o["besideStage"] is True
    assert o["activeIsNext"] is True and o["backDisabled"] is True
    assert o["stepDots"] == 6
    assert o["ariaDot"] == "Step 1: message 1, Shopper to Checkout, place order"
    assert o["widths"] == ["1.5"] * 8


def test_seq_declined_trace_marks_each_step_and_returns_to_message_three_on_the_retry(seq_page: Path) -> None:
    after_next = """
    const s = state();
    const cur = s.current[0];
    return {
      counter: s.counter,
      current: s.current,
      changes: changes(),
      pulsing: s.pulsing,
      dotsOf: s.dotsOf,
      dim: s.dim,
      lit: s.lit,
      line: msg(root, cur).querySelector('[data-q-sequence-line]').getAttribute('stroke-width'),
    };
    """
    steps: list[dict] = [
        {"viewport": {"width": 1280, "height": 800}},
        {"click": SEQ_TRACE_BTN},
        _seq_pick("Declined, then retried"),
        _seq_trace_eval(after_next, "s1"),
    ]
    for n in range(2, 9):
        steps += [{"click": SEQ_TRACE_NEXT}, _seq_trace_eval(after_next, f"s{n}")]
    steps.append(_seq_trace_eval("return { next: panel.querySelector('[data-q-flow-trace-next]').disabled, dots: panel.querySelectorAll('[data-q-flow-trace-dot]').length };", "end"))
    out = run(seq_page, *steps)
    assert_clean(out)
    r = out["results"]
    expected_current = [1, 2, 3, 5, 3, 4, 6, 7]
    expected_changes = [
        [],
        [["amount", "added"], ["currency", "added"]],
        [["attempt", "added"], ["card", "added"]],
        [["decline", "added"]],
        [["attempt", "changed"], ["decline", "removed"]],
        [["charge", "added"], ["status", "added"]],
        [],
        [["status", "changed"]],
    ]
    for step in range(1, 9):
        s = r[f"s{step}"]
        n = expected_current[step - 1]
        assert s["counter"].startswith(f"Step {step} of 8, message {n}, "), s["counter"]
        assert s["current"] == [n] and s["lit"] == [n], (step, s)
        assert s["changes"] == expected_changes[step - 1], (step, s["changes"])
        assert s["pulsing"] == [n], (step, s["pulsing"])
        assert s["dotsOf"] == [n], (step, s["dotsOf"])
        assert s["dim"] == [8], (step, s["dim"])
    assert r["s5"]["current"] == r["s3"]["current"] == [3]
    assert r["end"] == {"next": True, "dots": 8}


def test_seq_trace_counter_and_dots_name_the_message_from_to_and_label(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 800}},
        {"click": SEQ_TRACE_BTN},
        {"click": SEQ_TRACE_NEXT},
        {"click": SEQ_TRACE_NEXT},
        _seq_trace_eval(
            """
            const counter = panel.querySelector('[data-q-flow-trace-counter]');
            return {
              text: counter.textContent,
              live: counter.getAttribute('aria-live'),
              hidden: counter.querySelector('.q-visually-hidden').textContent,
              dot: panel.querySelector('[data-q-flow-trace-dot="3"]').getAttribute('aria-label'),
              current: [...panel.querySelectorAll('[data-q-flow-trace-dot][aria-current="step"]')].map((b) => b.textContent),
              note: panel.querySelector('[data-q-flow-trace-note]').hasAttribute('data-q-inactive'),
            };
            """,
            "d",
        ),
        {"click": '#checkout [data-q-flow-trace-dot="5"]'},
        _seq_trace_eval(
            """
            return {
              text: panel.querySelector('[data-q-flow-trace-counter]').textContent,
              note: panel.querySelector('[data-q-flow-trace-note]').textContent,
              noteShown: !panel.querySelector('[data-q-flow-trace-note]').hasAttribute('data-q-inactive'),
              current: state().current,
            };
            """,
            "noted",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["text"] == "Step 3 of 6, message 3, Billing to Stripe, create charge"
    assert d["live"] == "polite" and d["hidden"] == ", message 3, Billing to Stripe, create charge"
    assert d["dot"] == "Step 3: message 3, Billing to Stripe, create charge"
    assert d["current"] == ["3"] and d["note"] is True
    noted = out["results"]["noted"]
    assert noted["text"] == "Step 5 of 6, message 6, Billing to Ledger, record payment: async, nothing waits for it"
    assert noted["note"] == "async, nothing waits for it" and noted["noteShown"] is True and noted["current"] == [6]


def test_seq_clicks_while_tracing_jump_to_the_next_visit_and_an_off_trace_message_leaves_trace_mode(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 800}},
        {"click": SEQ_TRACE_BTN},
        _seq_pick("Declined, then retried"),
        {"click": SEQ_TRACE_NEXT},
        _seq_trace_eval("return state().counter.slice(0, 9);", "at2"),
        {"click": SEQ_MSG_HIT.format(n=3)},
        _seq_trace_eval("return state().counter.slice(0, 9);", "first"),
        {"click": SEQ_MSG_HIT.format(n=3)},
        _seq_trace_eval("return state().counter.slice(0, 9);", "second"),
        {"click": SEQ_MSG_HIT.format(n=3)},
        _seq_trace_eval("return state().counter.slice(0, 9);", "wrapped"),
        {"click": SEQ_MSG_HIT.format(n=5)},
        _seq_trace_eval("return state().counter.slice(0, 9);", "back"),
        _seq_eval(
            """
            q('checkout').querySelector('[data-q-sequence-svg]').dispatchEvent(new MouseEvent('click', { bubbles: true }));
            return null;
            """,
            "emptyClick",
        ),
        _seq_trace_eval("return { counter: state().counter.slice(0, 9), tracing: state().tracing, panelOpen: state().panelOpen };", "afterEmpty"),
        {"click": SEQ_MSG_HIT.format(n=8)},
        _seq_trace_eval(
            """
            const drawer = root.querySelector(':scope > aside[data-q-flow-drawer]');
            return Object.assign(state(), {
              title: drawer.querySelector('h3').textContent,
              dimCount: msgs().filter((g) => g.hasAttribute('data-q-sequence-dim')).length,
              pulseVisible: root.querySelectorAll('[data-q-sequence-pulse]:not([data-q-inactive])').length,
              currentAttr: root.querySelectorAll('[data-q-sequence-current]').length,
              panelShown: getComputedStyle(panel).display !== 'none',
              bodyPad: document.body.style.paddingBottom,
            });
            """,
            "off",
        ),
    )
    assert_clean(out)
    r = out["results"]
    assert r["at2"] == "Step 2 of"
    assert r["first"] == "Step 3 of"
    assert r["second"] == "Step 5 of"
    assert r["wrapped"] == "Step 3 of"
    assert r["back"] == "Step 4 of"
    assert r["afterEmpty"] == {"counter": "Step 4 of", "tracing": True, "panelOpen": True}
    off = r["off"]
    assert off["tracing"] is False and off["panelOpen"] is False and off["pressed"] == "false" and off["panelShown"] is False
    assert off["drawerOpen"] is True and off["focus"] == "8" and off["title"] == "8. show receipt"
    assert off["dim"] == [1, 2, 3, 4, 5, 6, 7] and off["lit"] == [8]
    assert off["pulseVisible"] == 0 and off["currentAttr"] == 0 and off["dots"] == 0 and off["bodyPad"] == ""


def test_seq_a_header_click_leaves_trace_mode_and_escape_or_the_button_close_it_returning_to_rest(seq_page: Path) -> None:
    rest = """
    const s = state();
    return {
      tracing: s.tracing,
      pressed: s.pressed,
      panelOpen: s.panelOpen,
      dimOrLit: s.dim.length + s.lit.length + s.current.length + s.notesDim.filter(Boolean).length,
      pulsing: s.pulsing.length,
      dots: s.dots,
      widths: [...new Set(s.widths)],
      active: document.activeElement === root.querySelector('[data-q-sequence-action="trace"]'),
      drawer: s.drawerOpen,
    };
    """
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 800}},
        {"click": SEQ_TRACE_BTN},
        {"click": '#checkout [data-q-sequence-header="ledger"]'},
        _seq_trace_eval("return Object.assign(state(), { title: root.querySelector(':scope > aside[data-q-flow-drawer] h3').textContent });", "header"),
        {"click": SEQ_TRACE_BTN},
        {"click": SEQ_TRACE_NEXT},
        {"press": "Escape"},
        _seq_trace_eval(rest, "escape"),
        {"click": SEQ_TRACE_BTN},
        {"click": SEQ_TRACE_BTN},
        _seq_trace_eval(rest, "toggled"),
        {"click": SEQ_TRACE_BTN},
        {"click": '#checkout [data-q-flow-trace-dot="4"]'},
        _seq_trace_eval("return state().counter.slice(0, 9);", "dot"),
        {"focus": '#checkout [data-q-sequence-message="1"]'},
        {"press": "Enter"},
        _seq_trace_eval("return state().counter.slice(0, 9);", "enter"),
    )
    assert_clean(out)
    r = out["results"]
    h = r["header"]
    assert h["tracing"] is False and h["panelOpen"] is False and h["drawerOpen"] is True and h["focus"] == "ledger" and h["title"] == "Ledger"
    assert h["dim"] == [1, 2, 3, 4, 5, 7, 8] and h["pulsing"] == [] and h["dots"] == 0
    resting = {"tracing": False, "pressed": "false", "panelOpen": False, "dimOrLit": 0, "pulsing": 0, "dots": 0, "widths": ["1.5"], "drawer": False}
    assert r["escape"] == {**resting, "active": True}
    assert r["toggled"] == {**resting, "active": True}
    assert r["dot"] == "Step 4 of"
    assert r["enter"] == "Step 1 of"


def test_seq_reduced_motion_steps_without_pulse_dots_and_draws_the_current_line_thick(seq_page: Path) -> None:
    probe = """
    const s = state();
    const cur = msg(root, s.current[0]);
    const line = cur.querySelector('[data-q-sequence-line]');
    return {
      counter: s.counter.slice(0, 9),
      current: s.current,
      dots: s.dots,
      pulsing: s.pulsing,
      attr: line.getAttribute('stroke-width'),
      computed: getComputedStyle(line).strokeWidth,
      others: msgs().filter((g) => g !== cur).map((g) => g.querySelector('[data-q-sequence-line]').getAttribute('stroke-width')),
      head: cur.querySelector('[data-q-sequence-head]') !== null,
    };
    """
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 800}},
        {"emulate": {"reducedMotion": "reduce"}},
        {"click": SEQ_TRACE_BTN},
        _seq_trace_eval(probe, "s1"),
        {"click": SEQ_TRACE_NEXT},
        _seq_trace_eval(probe, "s2"),
        {"click": SEQ_TRACE_NEXT},
        {"wait": 1500},
        _seq_trace_eval(probe, "s3"),
        {"click": '#checkout [data-q-flow-trace-play]'},
        {"waitFor": "document.querySelector('#checkout [data-q-flow-trace-counter]').textContent.startsWith('Step 6 of 6')", "timeout": 20000},
        _seq_trace_eval(probe, "played"),
    )
    assert_clean(out)
    r = out["results"]
    assert [r[k]["counter"] for k in ("s1", "s2", "s3", "played")] == ["Step 1 of", "Step 2 of", "Step 3 of", "Step 6 of"]
    assert [r[k]["current"] for k in ("s1", "s2", "s3", "played")] == [[1], [2], [3], [7]]
    for key in ("s1", "s2", "s3", "played"):
        assert r[key]["dots"] == 0 and r[key]["pulsing"] == [], (key, r[key])
        assert r[key]["attr"] == "3.5" and r[key]["computed"] == "3.5px", (key, r[key])
        assert set(r[key]["others"]) == {"1.5"} and r[key]["head"] is True


def test_seq_reduced_motion_scrolls_land_immediately_for_trace_steps_and_keyboard_moves(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 1280, "height": 400}},
        {"emulate": {"reducedMotion": "reduce"}},
        _seq_eval(
            """
            window.scrollTo({ top: q('checkout').getBoundingClientRect().top + window.scrollY - 20, behavior: 'instant' });
            return { smooth: getComputedStyle(document.documentElement).scrollBehavior };
            """,
            "setup",
        ),
        {"click": SEQ_TRACE_BTN},
        _seq_trace_eval(
            """
            const next = panel.querySelector('[data-q-flow-trace-next]');
            const before = window.scrollY;
            const seen = [];
            for (let i = 0; i < 5; i += 1) {
              next.click();
              seen.push(window.scrollY);
            }
            const strip = root.querySelector('[data-q-sequence-pinned]').getBoundingClientRect();
            const cur = root.querySelector('[data-q-sequence-current]').getBoundingClientRect();
            await new Promise((r) => setTimeout(r, 900));
            return { before, seen, settled: window.scrollY, curTop: cur.top - strip.bottom, curBottom: window.innerHeight - cur.bottom, counter: state().counter.slice(0, 9) };
            """,
            "trace",
        ),
        {"click": SEQ_TRACE_BTN},
        _seq_eval("window.scrollTo({ top: q('checkout').getBoundingClientRect().top + window.scrollY - 20, behavior: 'instant' });", "reset"),
        {"focus": '#checkout [data-q-sequence-message="1"]'},
        _seq_trace_eval(
            """
            const before = window.scrollY;
            const seen = [];
            for (let i = 0; i < 6; i += 1) {
              document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
              seen.push(window.scrollY);
            }
            await new Promise((r) => setTimeout(r, 900));
            return { before, seen, settled: window.scrollY, n: document.activeElement.getAttribute('data-q-sequence-message') };
            """,
            "keys",
        ),
    )
    assert_clean(out)
    r = out["results"]
    assert r["setup"]["smooth"] == "smooth"
    t = r["trace"]
    assert t["counter"] == "Step 6 of"
    assert t["seen"][-1] == t["settled"] and t["settled"] > t["before"], t
    assert t["curTop"] >= 0 and t["curBottom"] >= 0, t
    k = r["keys"]
    assert k["n"] == "7"
    assert k["seen"][-1] == k["settled"] and k["settled"] > k["before"], k


def test_seq_phone_pins_the_panel_to_the_bottom_collapses_it_and_keeps_the_current_message_above_it(seq_page: Path) -> None:
    probe = """
    const p = panel.getBoundingClientRect();
    const cs = getComputedStyle(panel);
    const strip = root.querySelector('[data-q-sequence-pinned]').getBoundingClientRect();
    const cur = root.querySelector('[data-q-sequence-current]');
    const c = cur ? cur.getBoundingClientRect() : null;
    const shown = (sel) => panel.querySelector(sel).getClientRects().length > 0;
    const btn = panel.querySelector('[data-q-sequence-trace-collapse]');
    return {
      position: cs.position, maxHeight: cs.maxHeight, overflowY: cs.overflowY, left: p.left, right: p.right, bottom: p.bottom, height: p.height, vh: window.innerHeight, vw: document.documentElement.clientWidth,
      rootDisplay: getComputedStyle(root).display,
      expanded: btn.getAttribute('aria-expanded'), collapseShown: getComputedStyle(btn).display !== 'none', collapseInButtons: btn.parentElement.classList.contains('q-flow-trace-buttons'), collapseLast: btn.parentElement.lastElementChild === btn,
      value: shown('[data-q-flow-trace-value]'), dots: shown('[data-q-flow-trace-dots]'), picker: shown('[data-q-flow-trace-picker]'), toggle: shown('.q-flow-trace-toggle'),
      counter: shown('[data-q-flow-trace-counter]'), back: shown('[data-q-flow-trace-back]'), next: shown('[data-q-flow-trace-next]'), play: shown('[data-q-flow-trace-play]'),
      aboveBy: c ? p.top - c.bottom : null, belowStrip: c ? c.top - strip.bottom : null,
      pad: getComputedStyle(document.body).paddingBottom, inlinePad: document.body.style.paddingBottom,
      touch: [...panel.querySelectorAll('.q-flow-trace-buttons > button')].map((b) => Math.round(Math.min(b.getBoundingClientRect().width, b.getBoundingClientRect().height))),
    };
    """
    out = run(
        seq_page,
        {"viewport": {"width": 375, "height": 700}},
        _seq_eval("window.scrollTo({ top: q('checkout').getBoundingClientRect().top + window.scrollY - 440, behavior: 'instant' })"),
        {"click": SEQ_TRACE_BTN},
        {"wait": 800},
        _seq_trace_eval(probe, "open"),
        {"click": SEQ_TRACE_NEXT},
        {"click": SEQ_TRACE_NEXT},
        {"click": SEQ_TRACE_NEXT},
        {"click": SEQ_TRACE_NEXT},
        {"click": SEQ_TRACE_NEXT},
        {"wait": 800},
        _seq_trace_eval(probe, "stepped"),
        {"click": SEQ_TRACE_COLLAPSE},
        _seq_trace_eval(probe, "collapsed"),
        {"click": "#checkout [data-q-flow-trace-back]"},
        {"wait": 800},
        _seq_trace_eval(probe, "collapsedStep"),
        {"click": SEQ_TRACE_COLLAPSE},
        _seq_trace_eval(probe, "expanded"),
        {"viewport": {"width": 1280, "height": 800}},
        _seq_trace_eval(probe, "wide"),
        {"viewport": {"width": 375, "height": 700}},
        {"click": SEQ_TRACE_BTN},
        _seq_trace_eval("return { inlinePad: document.body.style.paddingBottom, tracing: state().tracing };", "closed"),
    )
    assert_clean(out)
    r = out["results"]
    o = r["open"]
    assert o["position"] == "fixed" and o["maxHeight"] == "350px" and o["overflowY"] == "auto"
    assert o["left"] == 0 and o["right"] == o["vw"] and o["bottom"] == o["vh"] and o["height"] <= 350
    assert o["rootDisplay"] == "block"
    assert o["aboveBy"] >= 0 and o["belowStrip"] >= 0, o
    assert o["expanded"] == "true" and o["collapseShown"] and o["collapseInButtons"] and o["collapseLast"]
    assert o["value"] and o["dots"] and o["picker"] and o["toggle"]
    assert abs(float(o["pad"].removesuffix("px")) - o["height"]) <= 1 and o["inlinePad"] != ""
    assert all(size >= 44 for size in o["touch"]), o["touch"]
    s = r["stepped"]
    assert s["aboveBy"] >= 0 and s["belowStrip"] >= 0, s
    assert abs(float(s["pad"].removesuffix("px")) - s["height"]) <= 1
    c = r["collapsed"]
    assert c["expanded"] == "false" and c["collapseShown"]
    assert (c["counter"], c["back"], c["next"], c["play"]) == (True, True, True, True)
    assert (c["value"], c["dots"], c["picker"], c["toggle"]) == (False, False, False, False)
    assert c["height"] < s["height"] and c["bottom"] == c["vh"]
    assert abs(float(c["pad"].removesuffix("px")) - c["height"]) <= 1
    cs = r["collapsedStep"]
    assert cs["aboveBy"] >= 0 and cs["belowStrip"] >= 0, cs
    e = r["expanded"]
    assert e["expanded"] == "true" and e["value"] is True and e["height"] > c["height"]
    w = r["wide"]
    assert w["position"] == "sticky" and w["collapseShown"] is False and w["value"] is True and w["rootDisplay"] == "grid"
    assert r["closed"] == {"inlinePad": "", "tracing": False}


def test_seq_a_rebuild_keeps_one_collapse_button_last_in_the_panel_buttons(seq_page: Path) -> None:
    out = run(
        seq_page,
        {"viewport": {"width": 375, "height": 700}},
        {"click": SEQ_TRACE_BTN},
        _seq_trace_eval(
            """
            const script = root.querySelector(':scope > script[type="application/json"]');
            script.textContent = script.textContent + ' ';
            await new Promise((r) => setTimeout(r, 400));
            const again = root.querySelector(':scope > [data-q-flow-trace-panel]');
            const s = state();
            return {
              ready: root.getAttribute('data-q-sequence-ready'),
              collapse: again.querySelectorAll('[data-q-sequence-trace-collapse]').length,
              last: again.querySelector('.q-flow-trace-buttons').lastElementChild.hasAttribute('data-q-sequence-trace-collapse'),
              panels: root.querySelectorAll(':scope > [data-q-flow-trace-panel]').length,
              tracing: root.hasAttribute('data-q-sequence-tracing'),
              panelOpen: !again.hasAttribute('data-q-inactive'),
              buttons: root.querySelectorAll('[data-q-sequence-action="trace"]').length,
              pressed: root.querySelector('[data-q-sequence-action="trace"]').getAttribute('aria-pressed'),
              order: [...root.children].map((c) => c.hasAttribute('data-q-flow-trace-panel') ? 'panel' : c.hasAttribute('data-q-sequence-stage') ? 'stage' : c.hasAttribute('data-q-flow-drawer') ? 'drawer' : c.tagName.toLowerCase()),
              bodyPad: document.body.style.paddingBottom,
            };
            """,
            "d",
        ),
    )
    assert_clean(out)
    d = out["results"]["d"]
    assert d["ready"] == "true" and d["collapse"] == 1 and d["last"] is True and d["panels"] == 1
    assert d["tracing"] is False and d["panelOpen"] is False and d["buttons"] == 1 and d["pressed"] == "false"
    assert d["order"] == ["script", "div", "div", "stage", "panel", "drawer", "div", "details"]
    assert d["bodyPad"] == ""


SEQ_WITH_TRACING_FLOW = (
    _seq_element("checkout", "Checkout charges the card through Billing and Stripe, retrying a declined card.", SEQ_CHECKOUT_DATA)
    + f"""<q-flow id="renewal" summary="How a renewal order is priced, taxed and charged.">
  <script type="application/json">
  {json.dumps(RENEWAL_GRAPH, indent=2)}
  </script>
</q-flow>
"""
    + _schema_tag("schema-small", "Authors and their books.", SCHEMA_SMALL_DATA)
)


@pytest.fixture(scope="module")
def seq_trace_escape_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    work = tmp_path_factory.mktemp("kit-sequence-trace-escape")
    src = work / "sequence-trace-escape.src.html"
    src.write_text(HEADER + SEQ_WITH_TRACING_FLOW, encoding="utf-8")
    return _build(src, work / "sequence-trace-escape.html")


def test_seq_escape_inside_the_sequence_closes_both_traces_and_inside_the_graph_only_the_graphs(seq_trace_escape_page: Path) -> None:
    state = """
    const seq = q('checkout');
    const flow = q('renewal');
    return {
      seq: seq.hasAttribute('data-q-sequence-tracing'),
      flow: flow.hasAttribute('data-q-flow-tracing'),
      seqBtnFocused: document.activeElement === seq.querySelector('[data-q-sequence-action="trace"]'),
      flowBtnFocused: document.activeElement === flow.querySelector('[data-q-flow-action="trace"]'),
    };
    """
    out = run(
        seq_trace_escape_page,
        {"viewport": {"width": 1280, "height": 900}},
        {"click": SEQ_TRACE_BTN},
        {"click": '#renewal [data-q-flow-action="trace"]'},
        _seq_eval(state, "both"),
        {"focus": "#renewal [data-q-flow-trace-next]"},
        {"press": "Escape"},
        _seq_eval(state, "fromGraph"),
        {"click": '#renewal [data-q-flow-action="trace"]'},
        {"focus": SEQ_TRACE_NEXT},
        {"press": "Escape"},
        _seq_eval(state, "fromSequence"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["both"] == {"seq": True, "flow": True, "seqBtnFocused": False, "flowBtnFocused": False}
    assert r["fromGraph"] == {"seq": True, "flow": False, "seqBtnFocused": False, "flowBtnFocused": True}
    assert r["fromSequence"] == {"seq": False, "flow": False, "seqBtnFocused": True, "flowBtnFocused": False}


def test_seq_escape_from_inside_a_schema_leaves_a_tracing_or_focused_sequence_alone(seq_trace_escape_page: Path) -> None:
    state = """
    const seq = q('checkout');
    return {
      tracing: seq.hasAttribute('data-q-sequence-tracing'),
      focus: seq.getAttribute('data-q-sequence-focus-message'),
      drawer: !seq.querySelector(':scope > aside[data-q-flow-drawer]').hasAttribute('data-q-inactive'),
    };
    """
    out = run(
        seq_trace_escape_page,
        {"viewport": {"width": 1280, "height": 900}},
        {"click": SEQ_MSG_HIT.format(n=2)},
        _seq_eval(state, "focused"),
        {"focus": "#schema-small [data-q-schema-entity]"},
        {"press": "Escape"},
        _seq_eval(state, "focusedFromSchema"),
        {"click": SEQ_TRACE_BTN},
        _seq_eval(state, "tracing"),
        {"focus": "#schema-small [data-q-schema-entity]"},
        {"press": "Escape"},
        _seq_eval(state, "tracingFromSchema"),
        _seq_eval("const b = document.createElement('button'); b.id = 'outside'; document.body.prepend(b); b.focus();"),
        {"press": "Escape"},
        _seq_eval(state, "fromOutside"),
    )
    assert_clean(out)
    r = out["results"]
    assert r["focused"] == {"tracing": False, "focus": "2", "drawer": True}
    assert r["focusedFromSchema"] == {"tracing": False, "focus": "2", "drawer": True}
    assert r["tracing"] == {"tracing": True, "focus": None, "drawer": False}
    assert r["tracingFromSchema"] == {"tracing": True, "focus": None, "drawer": False}
    assert r["fromOutside"] == {"tracing": False, "focus": None, "drawer": False}
