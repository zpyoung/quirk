/**
 * Maintainer-only build of the offline Web Awesome vendor directory.
 *
 * Bundles the free components listed in COMPONENTS into one IIFE, concatenates the real
 * theme CSS into one stylesheet, and records both in vendor/libraries.json. Run it only
 * when the `@awesome.me/webawesome` pin in package.json is bumped:
 *
 *   pnpm install --ignore-scripts && node build-webawesome.mjs
 *
 * Output is self-contained: no module imports, no network fetches at runtime, and no icon
 * ever resolves to the Font Awesome CDN. A new version directory is added next to the old
 * ones; existing version directories and other libraries.json entries are left alone.
 */
import { build } from "esbuild";
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, "..", "..");
const VENDOR = join(SKILL, "vendor");
const PACKAGE = "@awesome.me/webawesome";
const PACKAGE_DIR = join(HERE, "node_modules", PACKAGE);
const DIST = join(PACKAGE_DIR, "dist");

const COMPONENTS = [
  "button", "button-group", "callout", "card", "checkbox", "details", "dialog", "divider",
  "drawer", "icon", "input", "option", "radio", "radio-group", "select", "switch", "tab",
  "tab-group", "tab-panel", "tag", "textarea", "tooltip",
];

const ICON_ALIASES = { "circle-info": "info", "triangle-exclamation": "warning" };
const DARK_CLASS = "wa-dark";
const DEFAULT_LIBRARY_MARKER = "src/components/icon/library.default.ts";
const OFFLINE_ICONS = "offline-icons";

const escapeInline = (text, kind) =>
  kind === "js" ? text.replace(/<\/script/gi, "<\\/script") : text.replace(/<\/style/gi, "<\\/style");
const sha256 = (text) => createHash("sha256").update(text, "utf8").digest("hex");

function loadIcons() {
  const dir = join(HERE, "icons");
  const icons = {};
  for (const file of readdirSync(dir).filter((f) => f.endsWith(".svg")).sort()) {
    icons[file.slice(0, -4)] = readFileSync(join(dir, file), "utf8").trim();
  }
  for (const [alias, target] of Object.entries(ICON_ALIASES)) icons[alias] = icons[target];
  return icons;
}

/**
 * Replaces the stock `default` icon library (Font Awesome CDN URLs) with one that serves
 * the inline set as data URIs, and fails the build if that chunk can no longer be found.
 */
function offlineIconsPlugin(icons) {
  let replaced = false;
  return {
    name: "offline-icons",
    setup(b) {
      b.onResolve({ filter: new RegExp(`^${OFFLINE_ICONS}$`) }, () => ({ path: OFFLINE_ICONS, namespace: OFFLINE_ICONS }));
      b.onLoad({ filter: /.*/, namespace: OFFLINE_ICONS }, () => ({
        contents: `
          const icons = ${JSON.stringify(icons)};
          export const offlineLibrary = {
            name: "default",
            resolver: (name) => "data:image/svg+xml," + encodeURIComponent(icons[name] ?? ""),
            mutator: (svg) => {
              if (!svg.hasAttribute("fill")) svg.setAttribute("fill", "currentColor");
            },
          };
        `,
        loader: "js",
      }));
      b.onLoad({ filter: /chunk\.[A-Z0-9]+\.js$/ }, (args) => {
        const source = readFileSync(args.path, "utf8");
        if (!source.includes(DEFAULT_LIBRARY_MARKER)) return null;
        replaced = true;
        return {
          contents: `
            import { offlineLibrary } from "${OFFLINE_ICONS}";
            export const getIconFolder = () => "solid";
            export const library_default_default = offlineLibrary;
          `,
          loader: "js",
          resolveDir: HERE,
        };
      });
      b.onEnd(() => {
        if (!replaced) throw new Error("default icon library chunk not found; the package layout changed");
      });
    },
  };
}

async function bundleJs(icons) {
  const imports = COMPONENTS.map((c) => `import "${PACKAGE}/dist/components/${c}/${c}.js";`).join("\n");
  const entry = `
    ${imports}
    import { registerIconLibrary } from "${PACKAGE}/dist/components/icon/library.js";
    import { offlineLibrary } from "${OFFLINE_ICONS}";
    registerIconLibrary("default", offlineLibrary);
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
    plugins: [offlineIconsPlugin(icons)],
  });
  return result.outputFiles[0].text;
}

function inlineImports(file, seen, parts) {
  if (seen.has(file)) return;
  seen.add(file);
  const source = readFileSync(file, "utf8");
  const importRe = /@import\s+url\(\s*['"]?([^'")]+)['"]?\s*\)\s*;/g;
  let last = 0;
  let match;
  while ((match = importRe.exec(source)) !== null) {
    parts.push(source.slice(last, match.index));
    inlineImports(resolve(dirname(file), match[1]), seen, parts);
    last = match.index + match[0].length;
  }
  parts.push(source.slice(last));
}

function bundleCss() {
  const parts = [];
  inlineImports(join(DIST, "styles", "webawesome.css"), new Set(), parts);
  const css = parts.join("\n");
  if (/@import/.test(css) || /url\(\s*['"]?https?:/.test(css)) {
    throw new Error("theme CSS still references another file or a remote url");
  }
  if (!css.includes(`.${DARK_CLASS}`)) throw new Error(`theme CSS has no .${DARK_CLASS} selector`);
  return css;
}

function fileEntry(path, kind, position, text) {
  return {
    path,
    kind,
    sha256: sha256(text),
    inline_sha256: sha256(escapeInline(text, kind)),
    position,
    inline: true,
  };
}

async function main() {
  const pkg = JSON.parse(readFileSync(join(PACKAGE_DIR, "package.json"), "utf8"));
  const pinned = JSON.parse(readFileSync(join(HERE, "package.json"), "utf8")).dependencies[PACKAGE];
  if (pkg.version !== pinned) throw new Error(`installed ${pkg.version} does not match pin ${pinned}`);
  const version = pkg.version;

  const outDir = join(VENDOR, "webawesome", version);
  mkdirSync(outDir, { recursive: true });

  const js = await bundleJs(loadIcons());
  const css = bundleCss();
  writeFileSync(join(outDir, "webawesome.bundle.js"), js, "utf8");
  writeFileSync(join(outDir, "webawesome.css"), css, "utf8");
  copyFileSync(join(PACKAGE_DIR, "LICENSE.md"), join(outDir, "LICENSE"));
  writeFileSync(join(outDir, "NOTES.md"), `dark-class: ${DARK_CLASS}\n`, "utf8");

  const manifestPath = join(VENDOR, "libraries.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const lib = manifest.libraries.webawesome ?? { versions: {} };
  lib.current = version;
  lib.versions[version] = {
    package: PACKAGE,
    license: pkg.license,
    license_file: "LICENSE",
    source: `https://registry.npmjs.org/${PACKAGE}/-/webawesome-${version}.tgz`,
    files: [
      fileEntry("webawesome.css", "css", "head", css),
      fileEntry("webawesome.bundle.js", "js", "body-end", js),
    ],
  };
  manifest.libraries.webawesome = lib;
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf8");

  console.log(JSON.stringify({ ok: true, version, outDir, js_bytes: js.length, css_bytes: css.length }));
}

if (!existsSync(DIST)) {
  console.error("webawesome is not installed; run `pnpm install --ignore-scripts` first");
  process.exit(1);
}
main().catch((err) => {
  console.error(err);
  process.exit(1);
});
