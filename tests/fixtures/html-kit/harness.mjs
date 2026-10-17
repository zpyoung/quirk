#!/usr/bin/env node
/**
 * Browser harness for the component kit's element tests.
 *
 * Usage: node harness.mjs '<json spec>'   or   echo '<json spec>' | node harness.mjs
 *        (a spec argument starting with "@" names a JSON file)
 *
 * Spec:
 *   file          absolute path of the built HTML page (required)
 *   viewport      {width, height}, default 1024x800
 *   colorScheme   "light" | "dark", default "light"
 *   media         "print" | "screen"; applied before the first step
 *   javaScript    false to load the page with JavaScript disabled (default true)
 *   hasTouch      true to give the context touch input (for touchDrag)
 *   permissions   Playwright permission names to grant, e.g. ["clipboard-write"]; default none
 *   initScripts   JS source strings injected before any page script runs
 *   steps         ordered list, each one of:
 *     {press: "ArrowRight"}                    keyboard press on the focused element
 *     {focus: "css"}                           focus the first match
 *     {click: "css"}                           real mouse click on the first match
 *     {hover: "css"}                           move the mouse over the first match
 *     {type: "text"}                           type text into the focused element, one key at a time
 *     {drag: {from, to, at}}                   mouse press near the top of `from`, move to `to`, release; `at` is where in
 *                                              `to` to land: "center" (default), "top" or "bottom"
 *     {dragHold: {from, to, at}}               like drag, but stops before the release; pair with mouseUp
 *     {mouseUp: true}                          release the mouse button
 *     {select: {selector, label}}              choose the option with that label in a <select>
 *     {touchDrag: {from, to, at}}              the same with touch input (needs hasTouch: true)
 *     {copyFile: {from, to}}                   copy a file on disk, e.g. to rebuild the page under test
 *     {eval: "expr", as: "name"}               evaluate a JS expression (promises are awaited)
 *     {emulate: {media, colorScheme}}          change emulated media after load
 *     {viewport: {width, height}}              resize
 *     {reload: true}                           reload the page
 *     {wait: ms}                               pause
 *     {waitFor: "expr", timeout: ms}           wait until the expression is truthy
 *
 * Output: one JSON object on stdout:
 *   {results: {name: value}, consoleErrors: [...], pageErrors: [...], failedSteps: [...]}
 * A step that throws is recorded in failedSteps and the run continues. Exit codes: 0 ran,
 * 2 usage error, 3 no browser could be launched. Never downloads a browser.
 */
import { createRequire } from "node:module";
import { copyFileSync, existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const verifyDir = path.resolve(here, "../../../skills/writing-html-artifacts/scripts/verify");
const require = createRequire(path.join(verifyDir, "package.json"));
const { chromium } = require("playwright-core");

async function readSpec() {
  const arg = process.argv[2];
  if (arg) {
    return JSON.parse(arg.startsWith("@") ? readFileSync(arg.slice(1), "utf8") : arg);
  }
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

/** Mirrors verify.mjs: the first of Chrome, Edge, CHROME_PATH or a bundled Chromium that launches. */
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
      return await chromium.launch({ headless: true, ...options });
    } catch (err) {
      console.error(`browser ${label} did not launch: ${String(err.message).split("\n")[0]}`);
    }
  }
  return null;
}

/** Viewport point to press at, and the one to release at, for a drag between two elements. */
async function dragPoints(page, drag) {
  const from = await page.locator(drag.from).first().boundingBox();
  const to = await page.locator(drag.to).first().boundingBox();
  if (!from || !to) throw new Error(`drag needs both elements on screen: ${drag.from} -> ${drag.to}`);
  const at = drag.at || "center";
  const y = at === "top" ? to.y + 2 : at === "bottom" ? to.y + to.height - 2 : to.y + to.height / 2;
  return {
    start: { x: from.x + from.width / 2, y: from.y + Math.min(14, from.height / 2) },
    end: { x: to.x + to.width / 2, y },
  };
}

async function mouseDrag(page, drag, release = true) {
  const { start, end } = await dragPoints(page, drag);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move((start.x + end.x) / 2, (start.y + end.y) / 2, { steps: 6 });
  await page.mouse.move(end.x, end.y, { steps: 6 });
  if (release) await page.mouse.up();
}

async function touchDrag(page, drag) {
  const { start, end } = await dragPoints(page, drag);
  const cdp = await page.context().newCDPSession(page);
  const touch = (type, point) =>
    cdp.send("Input.dispatchTouchEvent", { type, touchPoints: point ? [{ x: point.x, y: point.y, id: 1 }] : [] });
  await touch("touchStart", start);
  for (let i = 1; i <= 8; i += 1) {
    const t = i / 8;
    await touch("touchMove", { x: start.x + (end.x - start.x) * t, y: start.y + (end.y - start.y) * t });
  }
  await touch("touchEnd", null);
  await cdp.detach();
}

let spec;
try {
  spec = await readSpec();
  if (!spec || typeof spec.file !== "string") throw new Error("spec.file is required");
} catch (err) {
  console.error(`usage: harness.mjs '<json spec>' (${err.message})`);
  process.exit(2);
}

const browser = await launchBrowser();
if (!browser) process.exit(3);

const out = { results: {}, consoleErrors: [], pageErrors: [], failedSteps: [] };
try {
  const context = await browser.newContext({
    viewport: spec.viewport || { width: 1024, height: 800 },
    colorScheme: spec.colorScheme || "light",
    javaScriptEnabled: spec.javaScript !== false,
    permissions: spec.permissions || [],
    hasTouch: spec.hasTouch === true,
  });
  for (const source of spec.initScripts || []) await context.addInitScript(source);
  const page = await context.newPage();
  page.on("console", (msg) => {
    if (msg.type() === "error") out.consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => out.pageErrors.push(String(err.message || err)));
  if (spec.media) await page.emulateMedia({ media: spec.media });

  await page.goto(pathToFileURL(path.resolve(spec.file)).href, { waitUntil: "load" });
  if (spec.javaScript !== false) {
    try {
      await page.waitForFunction(
        () => [...document.querySelectorAll("q-flow, q-schema")].every((el) => el.hasAttribute("data-q-flow-ready")),
        null,
        { timeout: 10000 },
      );
    } catch (err) {
      out.failedSteps.push({ index: -1, step: { waitFor: "q-flow, q-schema" }, error: String(err.message).split("\n")[0] });
    }
  }

  const steps = spec.steps || [];
  for (let i = 0; i < steps.length; i += 1) {
    const step = steps[i];
    try {
      if ("press" in step) await page.keyboard.press(step.press);
      else if ("type" in step) await page.keyboard.type(step.type);
      else if ("drag" in step) await mouseDrag(page, step.drag);
      else if ("dragHold" in step) await mouseDrag(page, step.dragHold, false);
      else if ("mouseUp" in step) await page.mouse.up();
      else if ("select" in step) await page.locator(step.select.selector).first().selectOption({ label: step.select.label });
      else if ("touchDrag" in step) await touchDrag(page, step.touchDrag);
      else if ("copyFile" in step) copyFileSync(step.copyFile.from, step.copyFile.to);
      else if ("focus" in step) await page.locator(step.focus).first().focus();
      else if ("click" in step) await page.locator(step.click).first().click();
      else if ("hover" in step) await page.locator(step.hover).first().hover();
      else if ("eval" in step) out.results[step.as ?? String(i)] = await page.evaluate(step.eval);
      else if ("emulate" in step) await page.emulateMedia(step.emulate);
      else if ("viewport" in step) await page.setViewportSize(step.viewport);
      else if ("reload" in step) {
        await page.reload({ waitUntil: "load" });
        if (spec.javaScript !== false) {
          await page.waitForFunction(
            () => [...document.querySelectorAll("q-flow, q-schema")].every((el) => el.hasAttribute("data-q-flow-ready")),
            null,
            { timeout: 10000 },
          );
        }
      }
      else if ("wait" in step) await page.waitForTimeout(step.wait);
      else if ("waitFor" in step) await page.waitForFunction(step.waitFor, null, { timeout: step.timeout ?? 5000 });
      else throw new Error(`unknown step: ${JSON.stringify(step)}`);
    } catch (err) {
      out.failedSteps.push({ index: i, step, error: String(err.message).split("\n")[0] });
    }
  }
} finally {
  await browser.close();
}
process.stdout.write(JSON.stringify(out));
