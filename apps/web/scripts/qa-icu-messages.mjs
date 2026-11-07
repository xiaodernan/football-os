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
 * This gate parses **every message in every catalogue the directory carries** with the app's own parser
 * (`@formatjs/icu-messageformat-parser`, the one next-intl depends on) and refuses three things:
 *
 *  1. a message that does not parse — `{{count}}` is a mustache placeholder, and ICU reads the second
 *     brace as the end of an argument that never began;
 *  2. a plural or a select with no `other` branch — the branch every locale needs and the one ICU
 *     requires, because `other` is what a value outside the named cases falls back to;
 *  3. a message whose placeholders differ from the placeholders the **same key** holds in the other
 *     shipped catalogues — a key that takes `{count}` in English and `{n}` in Chinese prints the literal
 *     `{count}` on the Chinese page.
 *
 * Files only: no server, no browser, no port, which is why it runs in `scripts/check.sh` and not in the
 * live-tier walks.
 *
 * Correction recorded 2026-11-06: checks 2 and 3 were **vacuous** from the gate's birth — the walker
 * compared `node.type` against strings (`"argument"`, `"plural"`) while this parser emits numeric
 * `TYPE` enums and parses a message into an **array** of elements, so both checks measured an empty
 * population and passed. The walkers now traverse the array and the choice branches, and the figures
 * below are real. A green that cannot see its population is not agreement.
 */
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { parse, TYPE } = require("@formatjs/icu-messageformat-parser");

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
/** Discover the catalogues the gate judges, from the directory. Shipped today: en, zh, zh-TW.
 *  Anything additional — `ar.json`, `he.json` — is judged by the same rules with zero further edits. */
const LOCALES = ["en", "zh", "zh-TW", "ar", "he"].filter((locale) =>
  existsSync(join(MESSAGES, `${locale}.json`)),
);

/** The placeholders a message holds, as the set of names an argument or a choice would print.
 *  @formatjs parses ICU into **numeric-typed** elements (`TYPE.argument === 1`, not `"argument"`),
 *  and parses a message into an **array** of elements; the old walker compared against strings, so
 *  it collected nothing and the gate reported 4269 keys in agreement over a population it had read
 *  as empty. This version walks the array, reads every argument-bearing type — number, date and
 *  time are arguments too, and a `#` inside a choice is not a name — and follows each choice
 *  branch into its value. */
const placeholdersOf = (ast) => {
  const names = new Set();
  const walk = (node) => {
    if (!node) return;
    if (Array.isArray(node)) { for (const child of node) walk(child); return; }
    if (typeof node !== "object") return;
    if (
      node.type === TYPE.argument
      || node.type === TYPE.number
      || node.type === TYPE.date
      || node.type === TYPE.time
      || node.type === TYPE.select
      || node.type === TYPE.plural
    ) {
      if (typeof node.value === "string") names.add(node.value);
    }
    if (node.options) for (const option of Object.values(node.options)) walk(option?.value);
    if (Array.isArray(node.children)) walk(node.children);
    for (const key of Object.keys(node)) {
      if (key === "options" || key === "children") continue;
      const value = node[key];
      if (Array.isArray(value)) walk(value);
    }
  };
  walk(ast);
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
    const checkChoice = (node) => {
      if (!node) return;
      if (Array.isArray(node)) { for (const child of node) checkChoice(child); return; }
      if (typeof node !== "object") return;
      if (node.type === TYPE.plural || node.type === TYPE.select) {
        if (!node.options || !node.options.other) {
          failures.push(`${locale}.${path} has a choice with no "other" branch`);
        }
        for (const option of Object.values(node.options ?? {})) checkChoice(option?.value);
        return;
      }
      for (const key of Object.keys(node)) {
        if (key === "options") continue;
        const value = node[key];
        if (Array.isArray(value)) checkChoice(value);
      }
    };
    checkChoice(ast);
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
