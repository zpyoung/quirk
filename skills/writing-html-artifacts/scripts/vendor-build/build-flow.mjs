/**
 * Maintainer-only build of the offline flow vendor directory (`vendor/flow/<version>/`).
 *
 * Bundles `elkjs` (the layered layout engine), `d3-zoom` and `d3-selection` into one browser
 * IIFE that assigns `window.quirkFlow = { ELK, zoom, zoomIdentity, zoomTransform, select }`,
 * writes the combined EPL-2.0 and ISC license file, and records the hashes in
 * `vendor/libraries.json`.
 */
import { build } from "esbuild";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, "..", "..");
const VENDOR = join(SKILL, "vendor");
const NODE_MODULES = join(HERE, "node_modules");

const ASCII_CI = (word) => [...word].map((c) => `[${c}${c.toUpperCase()}]`).join("");
const SCRIPT_CLOSER = new RegExp(`</${ASCII_CI("script")}`, "g");
const escapeInline = (text) => text.replace(SCRIPT_CLOSER, "<\\/script");
const sha256 = (text) => createHash("sha256").update(text, "utf8").digest("hex");

function readPkg(name) {
  return JSON.parse(readFileSync(join(NODE_MODULES, name, "package.json"), "utf8"));
}

async function bundleJs() {
  const entry = `
    import ELK from "elkjs/lib/elk.bundled.js";
    import { zoom, zoomIdentity, zoomTransform } from "d3-zoom";
    import { select } from "d3-selection";
    window.quirkFlow = { ELK, zoom, zoomIdentity, zoomTransform, select };
  `;
  const result = await build({
    stdin: { contents: entry, resolveDir: HERE, loader: "js" },
    bundle: true,
    write: false,
    format: "iife",
    platform: "browser",
    target: "es2022",
    minifyWhitespace: true,
    minifySyntax: true,
    legalComments: "none",
    logLevel: "warning",
  });
  return result.outputFiles[0].text;
}

function buildLicense() {
  const d3ZoomLic = readFileSync(join(NODE_MODULES, "d3-zoom", "LICENSE"), "utf8").trim();
  const d3SelLic = readFileSync(join(NODE_MODULES, "d3-selection", "LICENSE"), "utf8").trim();
  return [
    "Copyright (c) 2008, 2024 Kiel University and others (elkjs, EPL-2.0); Copyright 2010-2023 Mike Bostock (d3-zoom, d3-selection, ISC)",
    "",
    "=== elkjs (Eclipse Public License 2.0) ===",
    "SPDX-License-Identifier: EPL-2.0",
    "This bundle includes Eclipse Layout Kernel (ELK) via elkjs under the Eclipse Public License v2.0",
    "(https://www.eclipse.org/legal/epl-2.0/).",
    "",
    "=== d3-zoom (ISC) ===",
    d3ZoomLic,
    "",
    "=== d3-selection (ISC) ===",
    d3SelLic,
    "",
  ].join("\n");
}

const elkPkg = readPkg("elkjs");
const version = elkPkg.version;
const outDir = join(VENDOR, "flow", version);
mkdirSync(outDir, { recursive: true });

const js = await bundleJs();
const jsName = "flow.bundle.js";
writeFileSync(join(outDir, jsName), js, "utf8");
writeFileSync(join(outDir, "LICENSE"), buildLicense(), "utf8");

const manifestPath = join(VENDOR, "libraries.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
if (!manifest.libraries.flow) {
  manifest.libraries.flow = { current: version, versions: {} };
}
manifest.libraries.flow.current = version;
manifest.libraries.flow.versions[version] = {
  package: "elkjs",
  license: "EPL-2.0 AND ISC",
  license_file: "LICENSE",
  source: `https://registry.npmjs.org/elkjs/-/elkjs-${version}.tgz`,
  files: [
    {
      path: jsName,
      kind: "js",
      position: "body-end",
      inline: true,
      sha256: sha256(js),
      inline_sha256: sha256(escapeInline(js)),
    },
  ],
};
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ library: "flow", version, bytes: Buffer.byteLength(js, "utf8") }));
