#!/usr/bin/env node
/*
§81 2c, continued — the count of copy the catalogues do not carry, and a ceiling that may only fall.

The arc's own record is a set of numbers measured at named refs: "A 24 sites, B 168, C 40 — 231 distinct
sites", "the union fell by 14 for 15 wired attributes". A number nobody recomputes is a number nobody
notices falling, and a number that is not gated is a number a new page can raise without anybody saying
so. This file is the gate for that: it walks every `.tsx` under `app/`, finds the copy that is written in
English in the source, and refuses a total above the committed floor.

What it counts, and why each shape is a shape:

* **JSX text** — `>No round played yet<`. The copy the reader sees, standing between two tags.
* **A label-ish attribute** — `title="…"`, `label="…"`, `placeholder="…"`, `aria-label="…"`, and the
  rest of the set a page uses to hand copy to a component. These are the shape a JSX-text scan cannot
  see, because the copy is an argument, not a child.
* **A label-ish object property** — `metadata = { title: "…" }`, `back={{ label: "…" }}`. The fourth
  shape the arc found: a copy inside an object literal, which neither a JSX-text scan nor an attribute
  scan reaches.

What it does not count, because a copy that is not copy is not a finding: class names, hrefs, ids, type
attributes, keys, URLs, paths, camelCase identifiers, `ALL_CAPS` constants, and the technical acronyms a
page prints as itself (RPE, HTTP, xG, API). The allowlist is short and its members are named.

The floor only falls. A slice that wires a page to its catalogue lowers it; a page that adds copy in
English raises the count, and the gate says so. The floor is this file's own `FLOOR_SITES` constant, and
the message names the file and line of every site it found, so the work is a list and not a hunt.

Files only: no server, no browser, no port — which is why it belongs with the other file-only gates in
`scripts/check.sh` and in CI, and why the script-inventory gate requires a runner to name it.
*/

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { createRequire as createRequireForJson } from "node:module";
import { join, resolve, sep } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const APP = join(WEB, "app");
/**
 * The components directory carries copy too, and a page is only as localised as the components it
 * renders: `components/CreatorWorkbench.tsx` holds the tier's own buttons and sentences, and no scan
 * of `app/` could see them. The population is therefore both directories.
 */
const COMPONENTS = join(WEB, "components");

/** The committed ceiling on English literal sites. i18n work lowers it; nothing else may. */
/**
 * The ceiling on English literal sites over the whole population: every `.tsx` under `app/` and
 * every `.tsx` under `components/`. A page is only as localised as the components it renders, and
 * the components hold copy — the workbench's buttons, the club and academy tools' sentences, the
 * scout panels' headings. A scan of `app/` alone could not see any of it.
 *
 * It may only fall.
 */
const FLOOR_SITES = 346;

/** The population the walk must find, so a scan that narrows itself cannot pass by finding nothing. */
const FLOOR_FILES = 70;

/** Attributes whose string value is copy the reader sees. */
const LABEL_ATTRIBUTES = new Set([
  "alt", "aria-label", "description", "empty", "error", "eyebrow", "heading", "label",
  "lede", "note", "placeholder", "subtitle", "title",
]);

/** Object-literal properties whose string value is copy the reader sees. */
const LABEL_PROPERTIES = new Set([
  "description", "empty", "error", "eyebrow", "heading", "label", "lede", "subtitle", "title",
]);

/**
 * Words a page prints as themselves: a rating scale, a protocol, a file format, a product name.
 * Short and closed — every member is a thing the product prints in English on purpose.
 */
/**
 * Values that are not copy, and the reason each one is not.
 *
 * A field name is not copy. `data_origin: synthetic` is the provenance envelope the API prints, and
 * translating it would break the one string an operator greps for; the same holds for the cap names
 * `max_depth` / `max_edges` / `max_nodes`, the parameter `identity_retained=`, the example address
 * `you@example.com`, the export file name, and the product's own name.
 */
const TECHNICAL_PATTERNS = [
  /^data_origin\b/,
  /^is_demo_data\b/,
  /^(max_depth|max_edges|max_nodes)\b/,
  /^identity_retained=/,
  /^you@example\.com$/,
  /^footballos-export\.json$/,
  /^FOOTBALL OS$/,
];

const TECHNICAL = new Set([
  "AI", "API", "CV", "DRI", "FM", "GB", "GPS", "HTML", "HTTP", "ID", "JSON", "MB", "MVP", "PDF",
  "PM", "RPE", "SQL", "TBD", "URL", "UTC", "U19", "U21", "VS", "X", "XGD", "xG", "xT",
]);

/**
 * The catalogue the keys are checked against. The English file is the one that must hold every key:
 * a locale may lag, but the fallback must not, or a page renders an error instead of a sentence.
 */
const CATALOGUE = JSON.parse(readFileSync(join(WEB, "messages", "en.json"), "utf8"));

const files = [];
const walk = (dir) => {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (entry.name.endsWith(".tsx")) files.push(p);
  }
};
walk(APP);
walk(COMPONENTS);

const relOf = (p) => p.slice(WEB.length + 1).split(sep).join("/");

/**
 * Whether a string is copy in English.
 *
 * The test is deliberately conservative: a value that could be a key, a path, an identifier or a
 * technical word is not a finding, because a gate that cries wolf gets switched off.
 */
const isEnglishCopy = (value) => {
  const text = value.trim();
  if (!text || text.length < 2) return false;
  if (text.includes("{") || text.includes("}") || text.includes("<")) return false;
  if (/^https?:\/\//i.test(text) || text.startsWith("/")) return false;
  if (/^[a-z0-9-]+$/.test(text)) return false; // kebab-case, or a key
  if (/^[A-Z0-9_]+$/.test(text)) return false; // a constant
  if (/^[a-z]+[A-Z]/.test(text)) return false; // camelCase identifier
  if (/[^\x00-\x7F]/.test(text)) return false; // already translated
  if (TECHNICAL_PATTERNS.some((pattern) => pattern.test(text))) return false; // a field name, not copy
  const words = text.match(/[A-Za-z][A-Za-z'’-]*/g) ?? [];
  if (words.length === 0) return false;
  if (words.length === 1) {
    const only = words[0];
    // A single capitalised word is copy ("Players", "Close"); a lowercase one is usually a value.
    if (!/^[A-Z]/.test(only)) return false;
    if (TECHNICAL.has(only)) return false;
    return only.length > 2;
  }
  // Two or more words: it is a sentence unless every word is technical.
  return !words.every((word) => TECHNICAL.has(word));
};

const sites = [];
/** Per file: the namespaces it binds and the keys it asks for. */
const keyCalls = new Map();
let parsed = 0;
let diagnostics = 0;

for (const file of files) {
  const text = readFileSync(file, "utf8");
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  if (source.parseDiagnostics?.length) diagnostics += source.parseDiagnostics.length;
  parsed += 1;
  const rel = relOf(file);
  const position = (node) => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;

  const namespaces = new Set();
  const keys = new Set();

  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.arguments.length > 0) {
      const callee = node.expression.text;
      const first = node.arguments[0];
      if ((callee === "useTranslations" || callee === "getTranslations") && ts.isStringLiteral(first)) {
        namespaces.add(first.text);
      } else if (/^t[a-z]{0,2}$/.test(callee) && ts.isStringLiteral(first) && /^[A-Za-z0-9_]+$/.test(first.text)) {
        keys.add(first.text);
      }
    }
    if (ts.isJsxText(node)) {
      const copy = node.text.replace(/\s+/g, " ").trim();
      if (isEnglishCopy(copy)) sites.push({ file: rel, line: position(node), shape: "jsx", copy });
    }
    if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
      const name = node.name.getText().replace(/^aria-/, "aria-");
      if (LABEL_ATTRIBUTES.has(name) && isEnglishCopy(node.initializer.text)) {
        sites.push({ file: rel, line: position(node), shape: `attr:${name}`, copy: node.initializer.text.trim() });
      }
    }
    if (ts.isPropertyAssignment(node) && node.name && ts.isIdentifier(node.name) && ts.isStringLiteral(node.initializer)) {
      const name = node.name.text;
      if (LABEL_PROPERTIES.has(name) && isEnglishCopy(node.initializer.text)) {
        sites.push({ file: rel, line: position(node), shape: `object:${name}`, copy: node.initializer.text.trim() });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  keyCalls.set(rel, { namespaces, keys });
}

const byFile = new Map();
for (const site of sites) byFile.set(site.file, (byFile.get(site.file) ?? 0) + 1);

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  const mark = ok ? "PASS" : "FAIL";
  console.log(`${mark}  ${name}${detail ? ` — ${detail}` : ""}`);
};

check(
  "the walk finds the population",
  files.length >= FLOOR_FILES && parsed === files.length && diagnostics === 0,
  `${files.length} .tsx files, ${parsed} parsed, ${diagnostics} parse diagnostics (floor ${FLOOR_FILES})`,
);

check(
  "the English literal count is at or below the committed floor",
  sites.length <= FLOOR_SITES,
  `${sites.length} site(s) against a floor of ${FLOOR_SITES}`,
);

/**
 * A key the catalogue does not hold is a runtime error, not a build error: next-intl throws
 * MISSING_MESSAGE the first time the page renders that string. The copy gate counts English
 * literals; this check is the other half — every key the source asks for is in the catalogue.
 */
const missingKeys = [];
for (const [file, { namespaces, keys }] of keyCalls) {
  for (const key of keys) {
    const held = [...namespaces].some((namespace) =>
      Object.prototype.hasOwnProperty.call(CATALOGUE[namespace] ?? {}, key),
    );
    if (!held) missingKeys.push({ file, key, namespaces: [...namespaces].sort() });
  }
}

check(
  "every key the source asks for is in the catalogue",
  missingKeys.length === 0,
  missingKeys.length === 0
    ? `${[...keyCalls.values()].reduce((total, entry) => total + entry.keys.size, 0)} key call(s) checked`
    : `${missingKeys.length} key(s) the catalogue does not hold`,
);

for (const [file, count] of [...byFile.entries()].sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1))) {
  console.log(`      ${String(count).padStart(3)}  ${file}`);
}

const failed = checks.filter((c) => !c.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  console.log("Every site above is copy the catalogues do not carry. Wire it to a key, or say why it stays in English.");
  for (const site of sites) console.log(`  ${site.file}:${site.line} [${site.shape}] ${site.copy.slice(0, 90)}`);
  if (missingKeys.length) {
    console.log("");
    console.log("Every key below is asked for and not in the catalogue. next-intl throws MISSING_MESSAGE for it.");
    for (const missing of missingKeys) {
      console.log(`  ${missing.file}: ${missing.namespaces.join("/")} has no key ${JSON.stringify(missing.key)}`);
    }
  }
  process.exitCode = 1;
}
