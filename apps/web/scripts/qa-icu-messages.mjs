#!/usr/bin/env node
/**
 * The catalogues' ICU gate.
 *
 * A catalogue message is a program, not a string: next-intl parses it when the page renders it, and a
 * message that does not parse throws **instead of** printing. Nothing in the build reads a catalogue —
 * next-intl resolves a key in the browser — so a malformed message compiles, typechecks, lints, and
 * then 500s the page that reads it, and a key nobody reads today is a trap waiting for the reader who
 * wires it tomorrow.
 *
 * This gate parses **every message in all three catalogues** with the app's own parser
 * (`@formatjs/icu-messageformat-parser`, the one next-intl depends on) and refuses three things:
 *
 *  1. a message that does not parse — `{{count}}` is a mustache placeholder, and ICU reads the second
 *     brace as the end of an argument that never began;
 *  2. a plural or a select with no `other` branch — the branch every locale needs and the one ICU
 *     requires, because `other` is what a value outside the named cases falls back to;
 *  3. a message whose placeholders differ from the placeholders the **same key** holds in the other two
 *     catalogues — a key that takes `{count}` in English and `{n}` in Chinese prints the literal
 *     `{count}` on the Chinese page.
 *
 * Files only: no server, no browser, no port, which is why it runs in `scripts/check.sh` and not in the
 * live-tier walks.
 */
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { parse } = require("@formatjs/icu-messageformat-parser");

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const LOCALES = ["en", "zh", "zh-TW"];

/** The placeholders a message holds, as the set of names an argument or a `#` would print. */
const placeholdersOf = (ast) => {
  const names = new Set();
  const walk = (node) => {
    if (!node || typeof node !== "object") return;
    if (node.type === "argument") names.add(node.value);
    if (node.type === "function" || node.type === "select" || node.type === "plural" || node.type === "selectordinal") {
      names.add("#");
      for (const option of Object.values(node.options ?? {})) walk(option.value);
    }
    if (node.type === "octothorpe") names.add("#");
  };
  for (const element of ast) walk(element);
  names.delete("#");
  return [...names].sort();
};

const catalogues = new Map();
for (const locale of LOCALES) {
  const raw = readFileSync(join(MESSAGES, `${locale}.json`), "utf8");
  catalogues.set(locale, JSON.parse(raw));
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** Every key in the English catalogue, flattened, with the namespace it lives in. */
const flatten = (block, prefix = "") => {
  const out = new Map();
  for (const [key, value] of Object.entries(block)) {
    const path = `${prefix}${key}`;
    if (value && typeof value === "object") for (const [inner, text] of flatten(value, `${path}.`)) out.set(inner, text);
    else out.set(path, value);
  }
  return out;
};

const failures = [];
let checked = 0;
const placeholders = new Map();

for (const locale of LOCALES) {
  const flat = flatten(catalogues.get(locale));
  for (const [path, value] of flat) {
    if (typeof value !== "string") continue;
    checked += 1;
    let ast;
    try {
      ast = parse(value);
    } catch (error) {
      failures.push(`${locale}.${path} does not parse: ${String(error?.message ?? error).slice(0, 120)}`);
      continue;
    }
    placeholders.set(`${locale}.${path}`, placeholdersOf(ast));
    for (const element of ast) {
      if (element.type !== "plural" && element.type !== "select" && element.type !== "selectordinal") continue;
      if (!element.options || !element.options.other) {
        failures.push(`${locale}.${path} has a ${element.type} with no "other" branch`);
      }
    }
  }
}

check(
  "every message in every catalogue parses as ICU",
  failures.length === 0,
  failures.length === 0 ? `${checked} message(s) parsed` : `${failures.length} message(s) refused`,
);

/**
 * The same key in three catalogues must ask for the same values: a key that takes `{count}` in English
 * and `{n}` in Chinese prints the literal `{count}` on the Chinese page, and no build step can see it.
 */
const mismatched = [];
const english = flatten(catalogues.get("en"));
for (const locale of LOCALES.filter((each) => each !== "en")) {
  const other = flatten(catalogues.get(locale));
  for (const [path, value] of english) {
    if (typeof value !== "string" || !other.has(path)) continue;
    const mine = placeholders.get(`en.${path}`) ?? [];
    const theirs = placeholders.get(`${locale}.${path}`) ?? [];
    if (mine.join(",") !== theirs.join(",")) {
      mismatched.push(`${locale}.${path} asks for {${theirs.join(", ")}} and English asks for {${mine.join(", ")}}`);
    }
  }
}

check(
  "the same key asks for the same placeholders in every catalogue",
  mismatched.length === 0,
  mismatched.length === 0 ? `${english.size} key(s) compared across ${LOCALES.length} catalogues` : `${mismatched.length} key(s) disagree`,
);

for (const failure of failures) console.log(`  - ${failure}`);
for (const failure of mismatched) console.log(`  - ${failure}`);

const failed = checks.filter((each) => !each.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
process.exitCode = failed.length === 0 ? 0 : 1;
