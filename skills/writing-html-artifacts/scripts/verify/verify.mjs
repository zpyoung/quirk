#!/usr/bin/env node
/**
 * Browser verification for a single HTML file: console cleanliness, responsive layout,
 * light/dark text contrast and network isolation.
 *
 * Usage: node verify.mjs FILE OUT_DIR MODE [--no-js]   (MODE is "offline" or "connected")
 *
 * With --no-js every context runs with JavaScript disabled, screenshots are named
 * `{width}-{scheme}-nojs.png`, and a fifth check, `fallback`, fails any `q-*` element without
 * `data-from` whose text is empty or whose box has no height (checked at 375px in both schemes).
 *
 * Offline mode aborts every http(s) request and fails the network check on any; connected mode
 * lets them through and only reports the URLs. In connected mode a navigation that fails or times
 * out is recorded as a network failure and the report is still written.
 *
 * A --no-js report carries `no_js: true`; a normal report has no such key.
 *
 * Writes OUT_DIR/report.json and four full-page screenshots, prints the report to stdout.
 * Exit codes: 0 passed, 1 failed, 2 usage error, 3 no browser could be launched.
 * Never downloads a browser; it only drives one that is already installed.
 */
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright-core";

const WIDTHS = [375, 1280];
const SCHEMES = ["light", "dark"];
const HEIGHT = 800;
const MAX_DETAILS = 20;
const NAV_TIMEOUT_MS = Number(process.env.QUIRK_VERIFY_NAV_TIMEOUT_MS) || 30000;
const LOCAL_SCHEMES = ["file:", "data:", "blob:", "about:"];

const [, , fileArg, outArg, mode, flag, ...extra] = process.argv;
if (!fileArg || !outArg || !["offline", "connected"].includes(mode) || (flag && flag !== "--no-js") || extra.length) {
  console.error("usage: verify.mjs FILE OUT_DIR offline|connected [--no-js]");
  process.exit(2);
}
const noJs = flag === "--no-js";

const file = path.resolve(fileArg);
const outDir = path.resolve(outArg);
const url = pathToFileURL(file).href;

/** Launches the first available browser; returns `{browser, label}` or null. */
async function launchBrowser() {
  const candidates = [
    ["chrome", { channel: "chrome" }],
    ["msedge", { channel: "msedge" }],
  ];
  if (process.env.CHROME_PATH) {
    candidates.push(["CHROME_PATH", { executablePath: process.env.CHROME_PATH }]);
  }
  let bundled = null;
  try {
    bundled = chromium.executablePath();
  } catch {
    bundled = null;
  }
  if (bundled && existsSync(bundled)) {
    candidates.push(["chromium", { executablePath: bundled }]);
  }
  for (const [label, options] of candidates) {
    try {
      return { browser: await chromium.launch({ headless: true, ...options }), label };
    } catch (err) {
      console.error(`browser ${label} did not launch: ${String(err.message).split("\n")[0]}`);
    }
  }
  return null;
}

/**
 * Runs inside the page. Returns one finding string per sampled element whose text contrast
 * is below WCAG AA (4.5:1, or 3:1 from 24px up), plus a count of elements it could not judge.
 */
function sampleContrast() {
  const SELECTOR = "body, h1, h2, h3, h4, h5, h6, p, li, td, th, label, button, a";
  const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  ctx.canvas.width = ctx.canvas.height = 1;

  const parse = (css) => {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = "#000";
    ctx.fillStyle = css;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    return { r, g, b, a: a / 255 };
  };
  const over = (top, under) => ({
    r: top.r * top.a + under.r * (1 - top.a),
    g: top.g * top.a + under.g * (1 - top.a),
    b: top.b * top.a + under.b * (1 - top.a),
    a: 1,
  });
  const lum = ({ r, g, b }) => {
    const lin = (v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  };
  const hex = ({ r, g, b }) =>
    "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");

  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  const declaresDark = getComputedStyle(document.documentElement).colorScheme.includes("dark");
  const canvas = dark && declaresDark ? { r: 18, g: 18, b: 18, a: 1 } : { r: 255, g: 255, b: 255, a: 1 };

  const background = (el) => {
    const layers = [];
    for (let node = el; node; node = node.parentElement) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage !== "none") return null;
      const bg = parse(cs.backgroundColor);
      if (bg.a > 0) layers.push(bg);
      if (bg.a === 1) break;
    }
    return layers.reduceRight((under, layer) => over(layer, under), canvas);
  };

  const findings = [];
  let unjudged = 0;
  for (const el of document.querySelectorAll(SELECTOR)) {
    const text = [...el.childNodes]
      .filter((n) => n.nodeType === Node.TEXT_NODE)
      .map((n) => n.textContent)
      .join(" ")
      .trim();
    if (!text) continue;
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (cs.display === "none" || cs.visibility !== "visible" || rect.width === 0 || rect.height === 0) continue;
    if (Number(cs.opacity) === 0) continue;
    const bg = background(el);
    if (!bg) {
      unjudged += 1;
      continue;
    }
    const fg = over(parse(cs.color), bg);
    const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a);
    const ratio = (hi + 0.05) / (lo + 0.05);
    const size = parseFloat(cs.fontSize);
    const needed = size >= 24 ? 3 : 4.5;
    if (ratio < needed) {
      const label = text.length > 30 ? text.slice(0, 30) + "..." : text;
      findings.push(
        `<${el.tagName.toLowerCase()}> "${label}" contrast ${ratio.toFixed(2)}:1 < ${needed}:1 (${hex(fg)} on ${hex(bg)})`,
      );
    }
  }
  return { findings, unjudged };
}

/**
 * Runs inside the page. Returns one finding per `q-*` element that has no `data-from` and renders
 * nothing: empty text or a zero-height box. Elements with `data-from` are built entirely by script,
 * so they are exempt.
 */
function sampleFallback() {
  const findings = [];
  for (const el of document.querySelectorAll("*")) {
    if (!el.tagName.startsWith("Q-") || el.hasAttribute("data-from")) continue;
    const tag = el.tagName.toLowerCase();
    if (el.innerText.trim() === "") findings.push(`<${tag}> has no visible text without JavaScript`);
    else if (el.getBoundingClientRect().height === 0) findings.push(`<${tag}> has zero height without JavaScript`);
  }
  return findings;
}

function check(details) {
  return { passed: details.length === 0, details };
}

async function verify(browser, label, sha) {
  const consoleDetails = [];
  const viewportDetails = [];
  const themeDetails = [];
  const navigationDetails = [];
  const fallbackDetails = [];
  const requests = new Set();
  const screenshots = [];
  let skippedBackgrounds = 0;

  runs: for (const scheme of SCHEMES) {
    for (const width of WIDTHS) {
      const run = `${width}px ${scheme}`;
      const context = await browser.newContext({
        viewport: { width, height: HEIGHT },
        colorScheme: scheme,
        serviceWorkers: "block",
        javaScriptEnabled: !noJs,
      });
      const blocked = new Set();
      await context.route(/^https?:/, (route) => {
        const target = route.request().url();
        requests.add(target);
        if (mode === "connected") return route.continue();
        blocked.add(target);
        return route.abort();
      });
      context.on("request", (req) => {
        const target = req.url();
        if (!LOCAL_SCHEMES.some((s) => target.startsWith(s))) requests.add(target);
      });

      const page = await context.newPage();
      page.on("console", (msg) => {
        if (msg.type() !== "error") return;
        // offline only: a blocked request logs "Failed to load resource"; the network check owns that failure
        if (blocked.has(msg.location().url)) return;
        consoleDetails.push(`${run}: console.error: ${msg.text()}`);
      });
      page.on("pageerror", (err) => consoleDetails.push(`${run}: pageerror: ${err.message}`));

      try {
        await page.goto(url, { waitUntil: "load", timeout: NAV_TIMEOUT_MS });
      } catch (err) {
        if (mode !== "connected") throw err;
        navigationDetails.push(`${run}: navigation to ${url} failed: ${String(err.message).split("\n")[0]}`);
        await context.close();
        break runs;
      }
      if (!noJs) {
        try {
          await page.waitForFunction(
            () => [...document.querySelectorAll("q-flow")].every((el) => el.hasAttribute("data-q-flow-ready")),
            null,
            { timeout: 10000 },
          );
        } catch {
          consoleDetails.push(`${run}: q-flow did not finish laying out within 10s`);
        }
      }
      await page.waitForTimeout(150);

      const shot = path.join(outDir, `${width}-${scheme}${noJs ? "-nojs" : ""}.png`);
      await page.screenshot({ path: shot, fullPage: true });
      screenshots.push(shot);

      if (width === WIDTHS[0]) {
        const { scrollWidth, clientWidth } = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        }));
        if (scrollWidth > clientWidth) {
          viewportDetails.push(`${run}: scrollWidth ${scrollWidth} exceeds clientWidth ${clientWidth}`);
        }
        if (noJs) {
          const findings = await page.evaluate(sampleFallback);
          findings.forEach((f) => fallbackDetails.push(`${run}: ${f}`));
        }
      }
      if (width === WIDTHS[WIDTHS.length - 1]) {
        const { findings, unjudged } = await page.evaluate(sampleContrast);
        findings.forEach((f) => themeDetails.push(`${scheme}: ${f}`));
        skippedBackgrounds += unjudged;
      }
      await context.close();
    }
  }

  const requestList = [...requests].sort();
  const networkDetails = requestList.map((r) => `${mode === "offline" ? "blocked" : "reported"} request: ${r}`);
  const network =
    mode === "offline"
      ? check(networkDetails)
      : { passed: navigationDetails.length === 0, details: [...navigationDetails, ...networkDetails] };
  const themes = check(themeDetails);
  if (skippedBackgrounds > 0) {
    themes.details.push(`note: ${skippedBackgrounds} sampled elements sit on a background image and were not judged`);
  }

  const checks = {
    console: check(consoleDetails.slice(0, MAX_DETAILS)),
    viewports: check(viewportDetails),
    themes: { passed: themes.passed, details: themes.details.slice(0, MAX_DETAILS) },
    network,
  };
  if (noJs) checks.fallback = check(fallbackDetails.slice(0, MAX_DETAILS));
  const status = Object.values(checks).every((c) => c.passed) ? "passed" : "failed";
  return { status, file_sha256: sha, browser: label, checks, screenshots, requests: requestList, ...(noJs && { no_js: true }) };
}

async function main() {
  const sha = createHash("sha256").update(await readFile(file)).digest("hex");
  await mkdir(outDir, { recursive: true });

  const launched = await launchBrowser();
  let report;
  if (!launched) {
    report = {
      status: "not-browser-verified",
      file_sha256: sha,
      browser: null,
      checks: {},
      screenshots: [],
      requests: [],
      ...(noJs && { no_js: true }),
    };
  } else {
    try {
      report = await verify(launched.browser, launched.label, sha);
    } finally {
      await launched.browser.close();
    }
  }

  await writeFile(path.join(outDir, "report.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report));
  process.exit(report.status === "passed" ? 0 : report.status === "failed" ? 1 : 3);
}

main().catch((err) => {
  console.error(err);
  process.exit(4);
});
