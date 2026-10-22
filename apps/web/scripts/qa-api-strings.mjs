#!/usr/bin/env node
/*
 * The API's sentences, and the copies of them the web tier holds.
 *
 * The web side of the arc asked which catalogue keys are read by nothing — and found 226, then took the
 * floor to zero. This file asks the same question of the **other side of the wire**: the API publishes
 * sentences, the web tier reads them, and where else does the web tier hold a *copy*?
 *
 * A copy in the web tier's own code is a dead string. The API's sentence is the live one — it is what the
 * API answers with, and the refusal boundary hands it to the reader — so a copy in a page is a sentence
 * the API can change without the page following it, and a second place to fix when it does.
 *
 * The API's refusal sentences reach the web tier through the **catalogue**: the `errors` namespace, one
 * key per code, and the contract test in `apps/api/tests/test_locale_claims.py` holds the English value
 * to be the API's own message. So the catalogue is the source of truth for "the API's sentences", and
 * this gate reads them from there rather than teaching a second census of the API's source.
 *
 * Three checks:
 *
 *  1. **no file in the web tier's own code holds a copy of a sentence the catalogue owns** — the
 *     dead-copy check, and the one that found the web tier's own copy of a refusal;
 *  2. **the refusal boundary is wired on both paths** — the server's own read (`lib/server.ts`) and the
 *     browser's proxy (`app/api/v1/[...path]/route.ts`), because a boundary that exists but is not called
 *     is a mechanism nobody has;
 *  3. **every refusal code's sentence is translated in both Chinese catalogues**, so no Chinese reader is
 *     shown the API's English.
 *
 * Files only: no server, no browser, no port, which is why it belongs with the other file-only gates.
 */

import { readFileSync, readdirSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const LOCALES = ["zh", "zh-TW"];

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
};

const catalogue = (locale) => JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));

const english = catalogue("en");
const errors = english.errors ?? {};
const codes = Object.keys(errors);

/**
 * The sentences the catalogue owns: the `errors` namespace, one per refusal code.
 *
 * A sentence shorter than a phrase is not a sentence, and a copy of a word would be a coincidence rather
 * than a copy, so only the ones long enough to be copy are compared.
 */
const sentences = codes
  .map((code) => ({ code, value: String(errors[code] ?? "") }))
  .filter((entry) => entry.value.length >= 15);

/** Every file in the web tier that could hold a copy. */
const sourceFiles = [];
const walk = (dir) => {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const name = entry.name;
    if (name === "node_modules" || name === "messages" || name === ".git" || name.startsWith(".next")) continue;
    const full = join(dir, name);
    if (entry.isDirectory()) {
      walk(full);
      continue;
    }
    if (/\.(ts|tsx|mjs|js)$/u.test(name)) sourceFiles.push(full);
  }
};
walk(WEB);

/**
 * The string literals in a source file, with the line each one starts on.
 *
 * Comments are **not** literals: the refusal boundary's own comment quotes the API's sentence to explain
 * why the sentence is the API's, and a gate that read comments as code would call that a copy. So this
 * walks the source once, tracking the three states a JavaScript file can be in — code, string, comment —
 * and a regular expression literal is skipped as well, because a `/` in code is not a string's end.
 */
const literalsIn = (source) => {
  const found = [];
  let index = 0;
  let line = 1;
  let previous = "";
  while (index < source.length) {
    const character = source[index];
    const next = source[index + 1];
    if (character === "\n") {
      line += 1;
      index += 1;
      continue;
    }
    if (character === "/" && next === "/") {
      while (index < source.length && source[index] !== "\n") index += 1;
      continue;
    }
    if (character === "/" && next === "*") {
      index += 2;
      while (index < source.length && !(source[index] === "*" && source[index + 1] === "/")) {
        if (source[index] === "\n") line += 1;
        index += 1;
      }
      index += 2;
      continue;
    }
    // A regular expression literal: a `/` that follows an operator, an opening bracket or a comma.
    if (character === "/" && !next && previous === "") index += 1;
    if (character === "/" && next !== "/" && next !== "*" && "([{,;=!?&|:+\n".includes(previous)) {
      index += 1;
      let inClass = false;
      while (index < source.length) {
        const here = source[index];
        if (here === "\\") {
          index += 2;
          continue;
        }
        if (here === "\n") line += 1;
        if (here === "[") inClass = true;
        else if (here === "]") inClass = false;
        else if (here === "/" && !inClass) break;
        index += 1;
      }
      index += 1;
      previous = "/";
      continue;
    }
    if (character === '"' || character === "'" || character === "`") {
      const quote = character;
      const startLine = line;
      index += 1;
      let value = "";
      while (index < source.length && source[index] !== quote) {
        if (source[index] === "\\") {
          value += source[index + 1] ?? "";
          index += 2;
          continue;
        }
        if (source[index] === "\n") line += 1;
        value += source[index];
        index += 1;
      }
      index += 1;
      found.push({ value, line: startLine });
      previous = quote;
      continue;
    }
    previous = character;
    index += 1;
  }
  return found;
};

const copies = [];
for (const file of sourceFiles) {
  const source = readFileSync(file, "utf8");
  for (const literal of literalsIn(source)) {
    // A literal this long is a parse artefact rather than a sentence, and a paragraph of code is not a
    // copy of a refusal.
    if (literal.value.length > 400) continue;
    for (const entry of sentences) {
      if (!literal.value.includes(entry.value)) continue;
      copies.push(`${relative(WEB, file).replace(/\\/gu, "/")}:${literal.line} holds a copy of errors.${entry.code}`);
    }
  }
}

check(
  "no file in the web tier's own code holds a copy of a sentence the catalogue owns",
  copies.length === 0,
  copies.length === 0
    ? `${sentences.length} sentence(s) owned by the catalogue, ${sourceFiles.length} file(s) read`
    : `${copies.length} copy/copies: ${copies.slice(0, 8).join(" | ")}`,
);

/**
 * The source with its comments removed, and its imports removed as well.
 *
 * The refusal boundary's own comment quotes the API's sentence to explain why the sentence is the API's,
 * and a gate that read comments as code would call that a copy; and a file that *imports* the localiser
 * has not necessarily *used* it. So a name is only "used" when it survives both.
 */
const stripComments = (source) => {
  let out = "";
  let index = 0;
  let previous = "";
  while (index < source.length) {
    const character = source[index];
    const next = source[index + 1];
    if (character === "/" && next === "/") {
      while (index < source.length && source[index] !== "\n") index += 1;
      continue;
    }
    if (character === "/" && next === "*") {
      index += 2;
      while (index < source.length && !(source[index] === "*" && source[index + 1] === "/")) {
        if (source[index] === "\n") out += "\n";
        index += 1;
      }
      index += 2;
      continue;
    }
    if (character === '"' || character === "'" || character === "`") {
      const quote = character;
      out += character;
      index += 1;
      while (index < source.length && source[index] !== quote) {
        if (source[index] === "\\") {
          out += source[index] + (source[index + 1] ?? "");
          index += 2;
          continue;
        }
        out += source[index];
        index += 1;
      }
      out += quote;
      index += 1;
      previous = quote;
      continue;
    }
    out += character;
    previous = character;
    index += 1;
  }
  return out;
};

/** The source with its import statements removed, so a name that is only imported does not count. */
const withoutImports = (source) => source.replace(/import\s+[^;]*?from\s+["'][^"']+["'];?/gu, "");

/**
 * The boundary, and the two paths that have to call it.
 *
 * A refusal reaches a reader through exactly two doors — the server's own read and the browser's proxy —
 * and a localiser that nothing calls is a mechanism nobody has.
 */
const boundary = join(WEB, "lib", "refusals.ts");
const doors = [
  { label: "the server's own read", file: join(WEB, "lib", "server.ts") },
  { label: "the browser's proxy", file: join(WEB, "app", "api", "v1", "[...path]", "route.ts") },
];
const unwired = [];
let boundaryExports = false;
try {
  boundaryExports = /export\s+async\s+function\s+localiseRefusal/u.test(readFileSync(boundary, "utf8"));
} catch {
  unwired.push("lib/refusals.ts does not exist");
}
if (!boundaryExports) unwired.push("lib/refusals.ts does not export localiseRefusal");
for (const door of doors) {
  let source = "";
  try {
    source = readFileSync(door.file, "utf8");
  } catch {
    unwired.push(`${door.label}: ${relative(WEB, door.file).replace(/\\/gu, "/")} does not exist`);
    continue;
  }
  // The localiser is passed as a reference by one door and called by the other, so what is checked is
  // that the name is *used* — and used outside the import that brings it in.
  const used = withoutImports(stripComments(source));
  if (!/\blocaliseRefusal\b/u.test(used)) unwired.push(`${door.label} does not use localiseRefusal`);
}

check(
  "the refusal boundary is wired on both paths a refusal arrives through",
  unwired.length === 0,
  unwired.length === 0 ? `localiseRefusal is called by ${doors.length} path(s)` : unwired.join(" | "),
);

/** A refusal's sentence is prose, so it is translated — never a token the same in every language. */
const untranslated = [];
for (const code of codes) {
  const value = String(errors[code] ?? "");
  for (const locale of LOCALES) {
    const other = String(catalogue(locale).errors?.[code] ?? "");
    if (other === value) untranslated.push(`${locale}: errors.${code} is the English sentence`);
    if (!other) untranslated.push(`${locale}: errors.${code} is missing`);
  }
}

check(
  "every refusal code's sentence is translated in both Chinese catalogues",
  untranslated.length === 0,
  untranslated.length === 0
    ? `${codes.length} code(s) translated in ${LOCALES.length} Chinese catalogue(s)`
    : untranslated.slice(0, 8).join(" | "),
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
