#!/usr/bin/env node
/*
 * Plural/Select completeness gate: verify ICU plural/select branches are complete per locale.
 *
 * Different locales have different plural categories (e.g., English: one/other; Chinese: other;
 * Arabic: zero/one/two/few/many/other). This gate verifies that every plural/select in the
 * catalogue has the required branches for each locale, and that branches are not empty.
 *
 * Three of this gate's verdicts used to be unprovable from these bytes, so it now witnesses them:
 *   - The population came only from the walker, whose first version compared the numeric `TYPE` enum
 *     against strings, found nothing, and printed "0 plurals checked" as a PASS. The scan check now
 *     compares the walker against the catalogue's own `, plural,` / `, select,` / `, selectordinal,`
 *     spellings message by message: a walker that has gone blind cannot agree with the text it reads.
 *   - `en.json` holds 89 plural nodes and NO select and NO selectordinal; `zh` and `zh-TW` hold 25
 *     each. A rule judged on an empty population is green by absence, so those checks print the empty
 *     count and point at `qa-plural-select-witness.mjs`, which is where a select, an ordinal and an
 *     Arabic plural are actually run. That file, not these bytes, is the evidence they work.
 *   - Scan equality is also green at zero spelled and zero parsed, so a catalogue whose plurals were
 *     deleted wholesale needs a number to fall through: the floor below.
 *   - One rule turned out to be unreachable from below: a plural or select written *without* its `other`
 *     clause does not parse at all — the app's parser answers `MISSING_OTHER_CLAUSE` — so the category
 *     checks can only ever be charged for the categories CLDR names besides `other` (`one`, Arabic's
 *     `zero`, English's ordinal `few` and `many`), and an emptied `other` branch is charged as empty
 *     instead. That is what the parse ledger is for: it is the check that sees the malformed message the
 *     completeness rules cannot, not a spare.
 *   - The locale list is a candidate set, not a discovery: `ar.json` and `he.json` are judged because
 *     their names are written above, and a fourth catalogue — `fr.json` — would sit in the same
 *     directory unread by this gate while every other catalogue gate counted it. The discovery check
 *     refuses a file the directory holds and the gate does not name.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse, TYPE } from "@formatjs/icu-messageformat-parser";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

/** The locales the gate judges, discovered from the catalogue directory. A locale gets judged
 *  the day its file exists — adding `ar.json` or `he.json` attaches the Arabic/Hebrew plural set
 *  (CLDR: `zero/one/two/few/many/other` for Arabic, `one/two/other` for Hebrew) with zero
 *  further edits, and their absence keeps the population at three rather than splitting the gate
 *  in two. */
const LOCALES = ["en", "zh", "zh-TW", "ar", "he"].filter((locale) => existsSync(join(MESSAGES, `${locale}.json`)));

/** Every catalogue the directory actually holds. Compared against `LOCALES` by the discovery check
 *  below, because the candidate list above is a list of *names*: a language added without writing its
 *  name here is a catalogue this gate would pass over in silence while its sibling gates counted it. */
const ON_DISK = readdirSync(MESSAGES).filter((file) => file.endsWith(".json")).map((file) => file.slice(0, -5));
const UNDISCOVERED = ON_DISK.filter((locale) => !LOCALES.includes(locale));

/** Required *cardinal* plural categories per locale (CLDR). */
const PLURAL_CATEGORIES = {
  en: ["one", "other"],
  zh: ["other"],  // Chinese has no plural distinction
  "zh-TW": ["other"],  // Traditional Chinese also has no plural distinction
  ar: ["zero", "one", "two", "few", "many", "other"],  // CLDR: Arabic has six plural categories
  he: ["one", "two", "other"],  // CLDR: singular (1), exactly two, and everything else
};

/** Required *ordinal* categories per locale (CLDR's ordinal ranges). `1st/2nd/3rd` come from a
 *  different table than `one/other`, so a `selectordinal` must not be judged by the cardinal set —
 *  the walker used to extract the `ordinal` flag and then ignore it. Only the sets stated here were
 *  checked against CLDR: English has five ordinal categories, Chinese and Traditional Chinese have
 *  `other` alone, and Arabic's ordinal table is `other` alone too (its six-category table is
 *  cardinal). `he` is deliberately absent: this file has not verified Hebrew's ordinal ranges, so a
 *  Hebrew ordinal makes the gate refuse for a declared table rather than judge it against
 *  `undefined` — which is a TypeError, and a crash is not a verdict. The same refusal covers a locale
 *  file added that has no cardinal row either. */
const ORDINAL_CATEGORIES = {
  en: ["one", "two", "few", "many", "other"],
  zh: ["other"],
  "zh-TW": ["other"],
  ar: ["other"],
};

/** A floor, not a ratchet: it sits under the population the tree carries today (89 plural nodes at
 *  5e79ab8, 87 in this lane's uncommitted `en.json`), so it cannot red a plural another lane is
 *  mid-edit on, while a walker that reads nothing fails it by the whole population. The scan check is
 *  the moving guard; this one catches what scan cannot see — a catalogue whose plurals were deleted. */
const PLURAL_FLOOR = 80;

const catalogues = {};
for (const locale of LOCALES) {
  catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** Messages the app's own ICU parser refused, named as `locale: namespace.key — first line of the
 *  error`. `extractPluralSelect` used to answer a parse failure with `[]`, which dropped the message
 *  from the population silently, so the gate certified messages it had not read. `qa-icu-messages.mjs`
 *  refuses malformed messages as well, but that is another gate's wiring: this gate's verdicts rest on
 *  this count, so it keeps its own ledger. */
const parseFailures = [];
const chargedFailures = new Set();
const chargeParseFailure = (where, error) => {
  const line = `${where} — ${String(error?.message ?? error).split("\n")[0]}`;
  if (!chargedFailures.has(line)) {
    chargedFailures.add(line);
    parseFailures.push(line);
  }
};

/** Extract all plural/select nodes from a message.
 *  @formatjs parses an ICU message into an **array** of elements whose `type` is a **numeric**
 *  enum (`TYPE.plural === 6`, not `"plural"`), and an argument's name is `.value`, not `.name`;
 *  the first version of this gate compared against strings and counted nothing, so "0 plurals
 *  checked" was agreement-by-blindness. Arrays are traversed, choice branches are followed,
 *  and a selectordinal is a plural with `pluralType === "ordinal"`. */
function extractPluralSelect(message, where) {
  try {
    const ast = parse(message);
    const nodes = [];
    const isChoice = (node) => node.type === TYPE.plural || node.type === TYPE.select;
    const visit = (node) => {
      if (!node) return;
      if (Array.isArray(node)) { for (const child of node) visit(child); return; }
      if (typeof node !== "object") return;
      if (isChoice(node)) {
        nodes.push({
          type: node.type === TYPE.plural ? "plural" : "select",
          ordinal: node.pluralType === "ordinal",
          name: node.value,
          options: Object.keys(node.options ?? {}),
        });
        for (const option of Object.values(node.options ?? {})) visit(option?.value);
        return;
      }
      if (node.options) for (const option of Object.values(node.options)) visit(option?.value);
      if (Array.isArray(node.children)) visit(node.children);
      for (const key of Object.keys(node)) {
        if (key === "options" || key === "children") continue;
        if (Array.isArray(node[key])) visit(node[key]);
      }
    };
    visit(ast);
    return nodes;
  } catch (error) {
    if (where) chargeParseFailure(where, error);
    return [];
  }
}

/** Which rule judges a choice node. A select's cases are named by the message (gender, state, tier);
 *  a plural's categories come from CLDR's cardinal table and an ordinal's from its ordinal table. */
const kindOf = (node) => (node.type === "select" ? "select" : node.ordinal ? "ordinal" : "cardinal");
const LABEL = { cardinal: "plural", ordinal: "ordinal", select: "select" };

/* ── Pass 1 — read every message of every shipped catalogue and compare what the parser returns with
 *    what the same message spells. Two independent readings of one population, so neither half can be
 *    green because the other went blind. Spellings are counted inside the *decoded* value, so both
 *    halves walk the same strings instead of a file scan compared against a message scan. ─────────── */
const SPELLINGS = [
  { kind: "cardinal", label: ", plural,", re: /,\s*plural,/g },
  { kind: "ordinal", label: ", selectordinal,", re: /,\s*selectordinal,/g },
  { kind: "select", label: ", select,", re: /,\s*select,/g },
];

const census = {};
const scanMismatches = [];
for (const locale of LOCALES) {
  const found = { cardinal: 0, ordinal: 0, select: 0 };
  const spelled = { cardinal: 0, ordinal: 0, select: 0 };
  let messages = 0;
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const [key, value] of Object.entries(block ?? {})) {
      if (typeof value !== "string") continue;
      messages++;
      const where = `${locale}: ${namespace}.${key}`;
      const here = { found: { cardinal: 0, ordinal: 0, select: 0 }, spelled: { cardinal: 0, ordinal: 0, select: 0 } };
      for (const entry of SPELLINGS) here.spelled[entry.kind] += (value.match(entry.re) ?? []).length;
      for (const node of extractPluralSelect(value, where)) here.found[kindOf(node)]++;
      for (const entry of SPELLINGS) {
        found[entry.kind] += here.found[entry.kind];
        spelled[entry.kind] += here.spelled[entry.kind];
        if (here.found[entry.kind] !== here.spelled[entry.kind]) {
          scanMismatches.push(`${where}: ${entry.label} spelled ${here.spelled[entry.kind]}, parsed ${here.found[entry.kind]}`);
        }
      }
    }
  }
  census[locale] = { found, spelled, messages };
}

const pairLine = (kind) => LOCALES.map((l) => `${l} ${census[l].spelled[kind]}/${census[l].found[kind]}`).join(", ");

check(
  "every catalogue in the directory is a locale this gate names",
  UNDISCOVERED.length === 0,
  UNDISCOVERED.length === 0
    ? `${LOCALES.join(", ")} — ${ON_DISK.length} catalogue(s) on disk, ${LOCALES.length} judged`
    : `${UNDISCOVERED.map((locale) => `${locale}.json`).join(", ")} sits in messages/ and is not in this ` +
      `gate's locale list, so its plurals are judged by nobody — add the name and its CLDR categories above`,
);

check(
  "the walker finds every choice argument the catalogues spell",
  scanMismatches.length === 0,
  scanMismatches.length === 0
    ? `plural ${pairLine("cardinal")}, ordinal ${pairLine("ordinal")}, select ${pairLine("select")} ` +
      `(spelled/parsed over ${LOCALES.map((l) => census[l].messages).join("/")} messages)`
    : `${scanMismatches.length} message(s) whose spelling and parse disagree: ${scanMismatches.slice(0, 6).join(" | ")}`,
);

check(
  "every message this gate judges parses as ICU",
  parseFailures.length === 0,
  parseFailures.length === 0
    ? `${LOCALES.map((l) => census[l].messages).join(" + ")} messages parsed by the app's own parser`
    : `${parseFailures.length} message(s) the parser refused, so they left the population: ${parseFailures.slice(0, 6).join(" | ")}`,
);

check(
  `the English plural population clears its vacuity floor (${PLURAL_FLOOR})`,
  census.en.found.cardinal >= PLURAL_FLOOR,
  `en holds ${census.en.found.cardinal} plural node(s) across ${LOCALES.length} shipped locale(s); floor ${PLURAL_FLOOR}`,
);

/* ── Pass 2 — judge each English choice against the same key in every shipped catalogue. A locale that
 *    flattens the choice (Chinese renders "1 deal" and "7 deals" with the same words) is not a finding —
 *    placeholder parity belongs to `qa-icu-messages.mjs` — but it is disclosed, because how many
 *    comparisons were actually made is the difference between this check testing the tree and testing
 *    itself. ─────────────────────────────────────────────────────────────────────────────────────── */
const issues = { cardinal: [], ordinal: [], select: [] };
const emptyTally = () => Object.fromEntries(LOCALES.map((l) => [l, { cardinal: 0, ordinal: 0, select: 0 }]));
const judged = emptyTally();
const flattened = emptyTally();
const englishNodes = { cardinal: 0, ordinal: 0, select: 0 };

for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const [key, enValue] of Object.entries(block ?? {})) {
    if (typeof enValue !== "string") continue;
    const path = `${namespace}.${key}`;
    for (const node of extractPluralSelect(enValue, `en: ${path}`)) {
      const kind = kindOf(node);
      englishNodes[kind]++;
      for (const locale of LOCALES) {
        const localeValue = catalogues[locale][namespace]?.[key];
        if (typeof localeValue !== "string") continue;
        const where = `${locale}: ${path}`;
        const matching = extractPluralSelect(localeValue, where).find((n) => n.name === node.name && kindOf(n) === kind);
        if (!matching) {
          flattened[locale][kind]++;
          continue;
        }
        judged[locale][kind]++;

        // The categories this rule demands of this locale. A select has no CLDR table: its cases are the
        // ones English declares plus `other`, because a translation that drops one silently renders the
        // fallback sentence instead of the case the reader's language has a word for.
        const demanded =
          kind === "select" ? [...new Set([...node.options, "other"])]
          : kind === "ordinal" ? ORDINAL_CATEGORIES[locale]
          : PLURAL_CATEGORIES[locale];
        if (!demanded) {
          issues[kind].push(
            `${where}: arg "${node.name}" needs ${LABEL[kind]} categories and this gate declares none for ` +
            `"${locale}" — state its CLDR categories instead of judging it against nothing`,
          );
          continue;
        }
        const missing = demanded.filter((cat) => !matching.options.includes(cat));
        if (missing.length > 0) {
          issues[kind].push(
            `${where}: ${LABEL[kind]} "${node.name}" missing ${kind === "select" ? "cases" : "categories"}: ` +
            `${missing.join(", ")} (has: ${matching.options.join(", ") || "none"})`,
          );
        }
        for (const cat of matching.options) {
          const branch = getOptionValue(localeValue, node.name, cat, where);
          if (branch === undefined || branch.trim() === "") {
            issues[kind].push(`${where}: ${LABEL[kind]} "${node.name}" category "${cat}" is empty`);
          }
        }
      }
    }
  }
}

/** Read one branch of one choice as text — same numeric-TYPE traversal as the walker; a branch holding
 *  nothing but a placeholder is non-empty, because `{#}` is the message saying the figure. */
function getOptionValue(message, argName, category, where) {
  try {
    const ast = parse(message);
    let found = null;
    const visit = (node) => {
      if (found !== null) return;
      if (!node) return;
      if (Array.isArray(node)) { for (const child of node) visit(child); return; }
      if (typeof node !== "object") return;
      const isChoice = node.type === TYPE.plural || node.type === TYPE.select;
      if (isChoice && node.value === argName) {
        const option = node.options?.[category];
        if (option?.value && Array.isArray(option.value)) {
          const text = option.value.map((n) => (n.type === TYPE.literal ? n.value : "")).join("");
          found = text.trim() === "" && option.value.length > 0 ? " placeholder" : text;
        }
        return;
      }
      if (isChoice) { for (const option of Object.values(node.options ?? {})) visit(option?.value); return; }
      for (const key of Object.keys(node)) {
        if (key === "options" || key === "children") continue;
        if (Array.isArray(node[key])) visit(node[key]);
      }
    };
    visit(ast);
    return found ?? undefined;
  } catch (error) {
    if (where) chargeParseFailure(where, error);
    return undefined;
  }
}

const compareLine = (kind) =>
  LOCALES.map((l) => `${judged[l][kind]} ${l}${flattened[l][kind] ? ` (${flattened[l][kind]} flattened)` : ""}`).join(", ");
const emptyNote = (kind) =>
  `0 ${LABEL[kind]} node(s) in the catalogue — this rule is run by qa-plural-select-witness.mjs, not by these bytes`;

check(
  "every plural has required categories for each locale",
  issues.cardinal.length === 0,
  issues.cardinal.length === 0
    ? `${englishNodes.cardinal} English plural(s); comparisons per locale: ${compareLine("cardinal")}`
    : `${issues.cardinal.length} plural issue(s): ${issues.cardinal.slice(0, 6).join(" | ")}`,
);

check(
  "every ordinal has required ordinal categories for each locale",
  issues.ordinal.length === 0,
  issues.ordinal.length === 0
    ? (englishNodes.ordinal
        ? `${englishNodes.ordinal} English ordinal(s); comparisons per locale: ${compareLine("ordinal")}`
        : emptyNote("ordinal"))
    : `${issues.ordinal.length} ordinal issue(s): ${issues.ordinal.slice(0, 6).join(" | ")}`,
);

check(
  "every select keeps English's cases and has no empty case",
  issues.select.length === 0,
  issues.select.length === 0
    ? (englishNodes.select
        ? `${englishNodes.select} English select(s); comparisons per locale: ${compareLine("select")}`
        : emptyNote("select"))
    : `${issues.select.length} select issue(s): ${issues.select.slice(0, 6).join(" | ")}`,
);

/** Summary */
console.log("\nPlural/Select summary:");
for (const kind of ["cardinal", "ordinal", "select"]) {
  console.log(
    `  ${LABEL[kind]}: en ${englishNodes[kind]} node(s); ` +
    LOCALES.map((l) => `${l} judged ${judged[l][kind]}, flat ${flattened[l][kind]}`).join("; "),
  );
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
