#!/usr/bin/env node
/*
 * Token drift gate: detect when technical tokens diverge from the catalogue.
 *
 * The locale-token gate names the values that are supposed to be identical across all languages. This gate
 * holds that those named tokens remain stable — a token that was identical across locales but diverges in a
 * new commit is a finding. Conversely, a value that diverges but is not named is also a finding.
 *
 * **Three holes found in it on 2026-11-08, all cured here.** (1) It re-stated the definer's 45 paths *and*
 * their 45 reasons as its own literal. The two copies agreed the day this was written, which is how a copy
 * survives: it agrees right up to the edit only one of them gets, and an empty exemption set would have made
 * the check below green by naming nothing. The table is now read from `qa-locale-tokens.mjs`, and a file that
 * cannot be read or a table that cannot be scraped is a finding. (2) Its `LOCALES` named `zh` and `zh-TW` in
 * the source, so a locale that ships — `ar.json`, a byte copy of English — was compared by nothing. The
 * directory now decides the population, and a plane holding no catalogue beside the fallback is refused rather
 * than passed. (3) Both walks descended exactly two levels, so a value three levels deep was never visited by
 * the check whose whole job is visiting values. Every leaf at every depth is read now.
 *
 * The reverse check keeps this gate's own **lenient** rule: a shared value of three characters or fewer, or
 * one holding no letters, is not charged here. `qa-locale-tokens.mjs` holds the strict version of that
 * direction and charges every shared value that carries no name, which is why the two gates can print
 * different counts for one tree — this one witnesses stability, that one owns the rule.
 *
 * Files only: no server, no browser, no port.
 */

import { readdirSync, readFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const DEFINER = join(WEB, "scripts", "qa-locale-tokens.mjs");

/** A *text* read, folded to `\n`: the scrape below runs regular expressions over source, and a source file's
 *  line endings differ between a Windows checkout and the git object for the same commit. */
const readText = (path) => readFileSync(path, "utf8").replace(/\r\n/g, "\n");

/**
 * The named technical tokens, read from the gate that defines them and states why each is language-neutral.
 *
 * `[\s\S]` so the block is found whichever line endings the file carries; the per-entry pattern reads the path
 * *and* the reason, because a finding that cannot quote the reason a value was named for is one no reader can
 * act on.
 */
const table = (() => {
  let source;
  try {
    source = readText(DEFINER);
  } catch {
    return { entries: [], error: `${basename(DEFINER)} is not where this gate looks for it (${DEFINER})` };
  }
  const body = /const TOKENS = new Map\(\[([\s\S]*?)\]\);/.exec(source);
  if (!body) {
    return { entries: [], error: `${basename(DEFINER)} holds no \`const TOKENS = new Map([...])\` table for this gate to read` };
  }
  const entries = [...body[1].matchAll(/\[\s*"([^"]+)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,?\s*\]/g)].map((match) => [match[1], match[2]]);
  if (entries.length === 0) {
    return { entries: [], error: `the table in ${basename(DEFINER)} scraped to zero entries, so its entries are no longer written as ["path", "reason"]` };
  }
  return { entries, error: null };
})();
const NAMED_TOKENS = new Map(table.entries);

/** The French-only doublets, read from the same definer: `fr` alone exempts them (and is held to them the
 *  same way); no other locale reads FR_TOKENS, so a French-only name cannot excuse a key for the rest.
 *  A missing FR_TOKENS table is a finding, for the same reason an unreadable TOKENS table is. */
const frTable = (() => {
  try {
    const source = readText(DEFINER);
    const body = /const FR_TOKENS = new Map\(\[([\s\S]*?)\]\);/.exec(source);
    if (!body) {
      return { entries: [], error: `${basename(DEFINER)} holds no \`const FR_TOKENS = new Map([...])\` table for this gate to read` };
    }
    const entries = [...body[1].matchAll(/\[\s*"([^"]+)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,?\s*\]/g)].map((match) => [match[1], match[2]]);
    if (entries.length === 0) {
      return { entries: [], error: `the FR_TOKENS table in ${basename(DEFINER)} scraped to zero entries` };
    }
    return { entries, error: null };
  } catch {
    return { entries: [], error: `${basename(DEFINER)} is not where this gate looks for it (${DEFINER})` };
  }
})();
const FR_NAMED_TOKENS = new Map(frTable.entries);
/** The exemption set for one locale, in the same shape the definer exposes. */
const exemptFor = (locale) =>
  locale === "fr" ? new Set([...NAMED_TOKENS.keys(), ...FR_NAMED_TOKENS.keys()]) : new Set(NAMED_TOKENS.keys());

/** Discovery, not a candidate list: the directory decides which locales are compared. */
const SHIPPED = (() => {
  try {
    return readdirSync(MESSAGES)
      .filter((name) => name.endsWith(".json"))
      .map((name) => basename(name, ".json"))
      .sort();
  } catch {
    return [];
  }
})();
const LOCALES = SHIPPED.filter((locale) => locale !== "en");

/** Every string leaf as `dotted.path -> value`, at whatever depth it sits. Two nested loops reached nothing
 *  below the second level, and a leaf the census never visits cannot be charged by it. */
const leaves = (node, prefix = "", out = new Map()) => {
  if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) leaves(value, prefix ? `${prefix}.${key}` : key, out);
    return out;
  }
  if (typeof node === "string") out.set(prefix, node);
  return out;
};

/** A catalogue that will not parse reads as empty, which the population check below charges; a silent `{}`
 *  would instead make every comparison pass by finding nothing. */
const parse = (locale) => {
  try {
    return leaves(JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8")));
  } catch {
    return new Map();
  }
};
const ENGLISH = parse("en");
const LEAVES = new Map(LOCALES.map((locale) => [locale, parse(locale)]));
const populationOk = SHIPPED.includes("en") && ENGLISH.size > 0 && LOCALES.length > 0;

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/* 1. The exemption sets are read from their definer, not copied into this file. */
check(
  "the named-token table is read from the gate that defines it",
  table.error === null && frTable.error === null,
  table.error === null && frTable.error === null
    ? `${NAMED_TOKENS.size} language-neutral entries and ${FR_NAMED_TOKENS.size} French-only entries read from ${basename(DEFINER)}; no token path is a literal in this file`
    : (table.error ?? frTable.error),
);

/* 2. The population every comparison below is graded on. */
check(
  "the fallback and at least one other catalogue are on this plane",
  populationOk,
  populationOk
    ? `${LOCALES.length} catalogue(s) beside the fallback (${LOCALES.join(", ")}), ${ENGLISH.size} English leaf(s) at every depth`
    : `messages/ ships ${SHIPPED.join(", ") || "nothing"} — ${SHIPPED.includes("en") ? "no catalogue beside en.json, so every comparison below has no second side" : "no en.json, so there is no reference to compare against"}`,
);

/* 3. Every named token still means the same thing in every language that ships. The language-neutral 45 are
 *    judged for every locale; the French-only doublets are judged for `fr` alone, which is the only locale
 *    that exempts them. */
const tokenDrift = [];
const missingTokens = [];
const checks3 = (locale) => (locale === "fr" ? [...NAMED_TOKENS, ...FR_NAMED_TOKENS] : [...NAMED_TOKENS]);
if (populationOk && table.error === null && frTable.error === null) {
  for (const locale of LOCALES) {
    for (const [path, reason] of checks3(locale)) {
      const enVal = ENGLISH.get(path);
      if (enVal === undefined) {
        missingTokens.push(`${path} is not in the English catalogue`);
        continue;
      }
      const other = LEAVES.get(locale);
      if (!other.has(path)) missingTokens.push(`${path} is not in ${locale}.json`);
      else if (other.get(path) !== enVal) tokenDrift.push(`${path}: ${locale}="${other.get(path)}" !== en="${enVal}" (reason: ${reason})`);
    }
  }
}

const stableOk = populationOk && table.error === null && frTable.error === null && tokenDrift.length === 0 && missingTokens.length === 0;
check(
  "every named technical token is still identical across all locales",
  stableOk,
  stableOk
    ? `${NAMED_TOKENS.size} language-neutral token(s) plus ${FR_NAMED_TOKENS.size} French-only doublet(s) held to their catalogues`
    : !populationOk || table.error || frTable.error
      ? `not judged — ${table.error ?? frTable.error ?? `messages/ ships ${SHIPPED.join(", ") || "nothing"}, ${ENGLISH.size} English leaf(s) and ${LOCALES.length} locale(s) to compare them with`}`
      : `drift: ${tokenDrift.slice(0, 4).join(" | ")}; missing: ${missingTokens.slice(0, 4).join(" | ")}`,
);

/* 4. The reverse direction: a value every language shares that carries no name. */
const unnamedIdentical = [];
let eligible = 0;
if (populationOk) {
  for (const [path, enVal] of ENGLISH) {
    if (enVal.length <= 3 || !/[a-zA-Z]/.test(enVal)) continue;
    eligible += 1;
    for (const locale of LOCALES) {
      if (exemptFor(locale).has(path)) continue;
      if (LEAVES.get(locale).get(path) === enVal) unnamedIdentical.push(`${locale}: ${path}: "${enVal}"`);
    }
  }
}

const reverseOk = populationOk && unnamedIdentical.length === 0;
check(
  "no unnamed identical values that should be named tokens",
  reverseOk,
  reverseOk
    ? `${eligible} of the ${ENGLISH.size} English leaf(s) visited are eligible for this rule; none is shared by a catalogue without a name`
    : !populationOk
      ? `not judged — messages/ ships ${SHIPPED.join(", ") || "nothing"}, ${ENGLISH.size} English leaf(s) and ${LOCALES.length} locale(s) to compare them with`
      : `${unnamedIdentical.length} unnamed identical value(s): ${unnamedIdentical.slice(0, 6).join(" | ")}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
