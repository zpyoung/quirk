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
HEADER = '<!-- quirk-src {"template": "report", "title": "Kit elements", "mode": "offline"} -->\n<!-- slot: main -->\n'

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


# --- report layout ---------------------------------------------------------------------------------


def test_report_uses_wide_screens_and_keeps_the_aside_in_view(tmp_path: Path) -> None:
    reason = _node_ready()
    if reason:
        pytest.skip(reason)
    filler = "\n".join(f"<p>Paragraph {i} of the report body, long enough to wrap at the prose measure.</p>" for i in range(60))
    src = tmp_path / "wide.src.html"
    src.write_text(
        HEADER + filler + "\n<!-- slot: aside -->\n<aside aria-label=\"About these numbers\"><p>Sample data.</p></aside>\n",
        encoding="utf-8",
    )
    page = _build(src, tmp_path / "wide.html")
    out = run(
        page,
        ev("(window.scrollTo({ top: 2000, behavior: 'instant' }), window.scrollY > 1000)", "scrolled"),
        ev(
            """(() => {
              const main = document.querySelector('main').getBoundingClientRect();
              const p = document.querySelector('main p').getBoundingClientRect();
              const aside = document.querySelector('aside').getBoundingClientRect();
              return {
                wideMain: main.width > 960,
                proseCapped: p.width < main.width,
                asideInView: aside.top >= 0 && aside.top < window.innerHeight,
                fits: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
              };
            })()""",
            "layout",
        ),
        viewport={"width": 2000, "height": 900},
    )
    assert_clean(out)
    assert out["results"]["scrolled"] is True
    assert out["results"]["layout"] == {"wideMain": True, "proseCapped": True, "asideInView": True, "fits": True}
