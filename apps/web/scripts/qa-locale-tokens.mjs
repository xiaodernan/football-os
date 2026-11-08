#!/usr/bin/env node
/*
 * The locales' technical tokens: the values that are the same in every language, and only those.
 *
 * Two claims in this project were conventions rather than measurements, and this file is both of them
 * turned into checks.
 *
 * **The first: "the identical values are the ones that are supposed to be identical."** A key whose
 * Chinese value is byte-identical to its English value is, by that claim, a technical token — an
 * acronym, a unit, an API field name printed as itself, a proper name used as an example. The claim was
 * never checked, so an English *phrase* could sit in the Chinese catalogue untranslated and nobody
 * would know: a Chinese reader saw "weekly minutes" as a cap's name, and "pressing, transitions" as an
 * example of what to type. So the set of identical values is now **named**, key by key, with the reason
 * each one is the same in every language — and a key that is not named is a finding.
 *
 * **The second: "the English catalogue is English."** `en.json` held `scout.placeholder` in Chinese —
 * "e.g. 找一个 22 岁以下、左脚、能踢 CM、预算 2000 万以下的球员" — so an English reader was shown a Chinese
 * sentence, and the Chinese catalogue's identical value made the coverage figures call it translated.
 * Neither the copy gate (which reads the source, not the catalogue) nor the locale sweep (which looks
 * for *English* on a Chinese page) could see it. So the English file now has to hold no Chinese.
 *
 * Files only: no server, no browser, no port, which is why it belongs with the other file-only gates in
 * `scripts/check.sh` and in CI.
 *
 * **Two holes found in it on 2026-11-08, both the same shape.** Its `LOCALES` named `zh` and `zh-TW` in the
 * source, so an `ar.json` that is a byte copy of `en.json` — every message of it still English — added
 * nothing to any of these checks and this gate stayed green beside it; the measured pre-fix run is §41. And
 * every walk here descended exactly two levels, so a Chinese sentence written three levels deep inside
 * `en.json` passed the very check this file was written to hold: `en.json` carrying Chinese was the
 * *founding* defect, and the census that looks for it could not see past `probe.deep`. Both are cured — the
 * directory now decides which locales are judged, every leaf at every depth is visited, a locale that ships
 * without a floor on record is a finding rather than an absence, and a check holds that this table is copied
 * nowhere else.
 */

import { readdirSync, readFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const SELF = basename(fileURLToPath(import.meta.url));

/**
 * Discovery, not a candidate list: the directory decides which locales are judged.
 *
 * The old line was `const LOCALES = ["zh", "zh-TW"]`. A locale that ships — `ar.json`, `he.json`, a `fr.json`
 * nobody intended — joined every catalogue in the build and was judged by none of these five checks, which is
 * how a byte copy of English could sit beside a green gate.
 */
const SHIPPED = readdirSync(MESSAGES)
  .filter((name) => name.endsWith(".json"))
  .map((name) => basename(name, ".json"))
  .sort();
const LOCALES = SHIPPED.filter((locale) => locale !== "en");

/**
 * The values that are the same in every language, and why.
 *
 * Each entry names a key and the *kind* of thing it is, because a list without reasons is the same as
 * no list at all: it is a place where an untranslated phrase goes to stop the gate from noticing.
 */
const TOKENS = new Map([
  // An acronym, a unit, or a file format: the same word in every language.
  ["settings.apiBadge", "the API's own name"],
  ["world.thOvr", "the rating scale's own name"],
  ["world.thPot", "the rating scale's own name"],
  ["worldTeam.thOvr", "the rating scale's own name"],
  ["worldTeam.thPot", "the rating scale's own name"],
  ["worldPlayer.thRpe", "the scale's own name"],
  ["worldTraining.thRpe", "the scale's own name"],
  ["careerDetail.thLedgerXg", "the metric's own name"],
  ["simulationAggregates.thXg", "the metric's own name"],
  ["simulate.blockThXG", "the metric's own name"],
  ["club.tableHeaderRPE", "the scale's own name"],
  ["club.tableHeaderHTTP", "the protocol's own name"],
  ["portfolio.pdfTitle", "the file format's own name"],
  ["knowledge.bm25Chip", "the ranking function's own name"],

  // An API field name printed as itself: the name an operator greps for, and the name the tier owns.
  ["club.capNameMax", "an API field name"],
  ["club.capTeamNameMax", "an API field name"],
  ["club.capNoteMax", "an API field name"],
  ["club.capCountry", "an API field name"],
  ["club.capKinds", "an API field name"],
  ["club.capRatingRange", "an API field name"],
  ["club.capReviewWeeksRange", "an API field name"],
  ["worldPlayer.recentFormEyebrow", "an API field name"],
  ["academy.sharedWithGuardian", "an API field name"],
  ["scout.comparisonNull", "an API field name and its null"],
  ["knowledge.provenanceFooter", "the API's own field names"],
  ["video.measuredEyebrow", "the API's own field name"],

  // A template whose parts are names, numbers or the API's own enums: there is no sentence to translate.
  ["tactics.tableA", "a template of a side's name"],
  ["tactics.tableB", "a template of a side's name"],
  ["tactics.tableDelta", "the two sides' own letters"],
  ["challenges.clubOption", "a template of names and figures"],
  ["challenges.cardObjective", "a template of a figure"],
  ["challenges.vs", "the word every football page uses"],
  ["community.busyEllipsis", "a punctuation mark"],
  ["simulate.xgLine", "a template of the metric's own name and two figures"],
  ["club.matrixDefault", "a template of the API's own values"],
  ["club.consentEyebrow", "a template of two figures"],
  ["careerDetail.eyebrow", "a template of names"],
  ["worldPlayer.eyebrow", "a template of names"],
  ["worldMatch.eyebrow", "a template of names"],
  ["worldCompetition.metaTitleKind", "a template of the API's own kind"],
  ["graph.listingTitle", "a template of the API's own kind"],
  ["graph.backLabel", "a template of the API's own kind and slug"],

  // A proper name used as an example of a name.
  ["club.createNamePlaceholder", "an example proper name"],
  ["club.teamNamePlaceholder", "an example proper name"],
  ["club.playerSlugPlaceholder", "an example slug"],
]);

const catalogue = (locale) => JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));

/**
 * A *text* read, folded to `\n`.
 *
 * These two files are the only ones here that a regular expression runs over, and a regular expression reads
 * line endings: `messages/README.md` is CRLF on a Windows checkout and LF in the git object the same commit
 * holds, so an unfolded read is a verdict that depends on where the reader stood. A JSON read needs no
 * folding — a raw `\r` cannot sit inside a JSON string, so the same bytes parse to the same object on either
 * plane, which is why `catalogue` above is plain.
 */
const readText = (path) => readFileSync(path, "utf8").replace(/\r\n/g, "\n");

/**
 * Every string leaf as `dotted.path -> value`, at whatever depth it sits.
 *
 * Each walk below used to be two nested `Object.entries` loops, so a value three levels down was never
 * reached: the outer loop saw an object, `typeof value !== "string"` moved past it, and the check reported a
 * clean verdict about a leaf it had not visited. Measured on 2026-11-08 (§41): a Chinese sentence written at
 * `probe.chinese.inner` passed the check this file exists to hold.
 */
const leaves = (node, prefix = "", out = new Map()) => {
  if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) leaves(value, prefix ? `${prefix}.${key}` : key, out);
    return out;
  }
  if (typeof node === "string") out.set(prefix, node);
  return out;
};

/** Read each catalogue once. The old code called `catalogue(locale)` from inside the per-key loop, so every
 *  key re-parsed every file: the walks below are the same census for a fraction of the reads. */
const english = catalogue("en");
const ENGLISH = leaves(english);
const LEAVES = new Map(SHIPPED.map((locale) => [locale, leaves(catalogue(locale))]));
const valuesOf = (locale) => LEAVES.get(locale) ?? new Map();

/** What every check below is graded on, printed so a reader can see the population rather than assume it. */
const JUDGED = `${LOCALES.length} catalogue(s) beside the fallback (${LOCALES.join(", ") || "none"}), ${ENGLISH.size} English leaf(s)`;

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/* --- the first claim: the English file is English --- */
const cjk = /\p{Script=Han}/u;
const chineseInEnglish = [];
for (const [path, value] of ENGLISH) {
  if (cjk.test(value)) chineseInEnglish.push(path);
}

check(
  "the English catalogue holds no Chinese",
  chineseInEnglish.length === 0,
  chineseInEnglish.length === 0
    ? `${ENGLISH.size} English leaf(s) read at every depth`
    : `${chineseInEnglish.length} value(s) in English that are Chinese: ${chineseInEnglish.slice(0, 6).join(", ")}`,
);

/* The population. Every other check on this plane compares the fallback against a second catalogue, so a
 * plane where `messages/` holds only `en.json` gives all four of them nothing to compare and a green line
 * each. Refuse instead. */
check(
  "the directory ships at least one catalogue beside the fallback",
  SHIPPED.includes("en") && LOCALES.length > 0,
  SHIPPED.includes("en") && LOCALES.length > 0
    ? JUDGED
    : SHIPPED.includes("en")
      ? `messages/ ships en.json alone — the four comparison rules below have no second side, so ${ENGLISH.size} English leaf(s) went unjudged`
      : `messages/ ships ${SHIPPED.join(", ") || "nothing"} — no en.json, so the reference every check below compares against is missing`,
);

/* --- the second claim: the identical values are the named ones --- */
const unnamed = [];
const stale = [];
for (const locale of LOCALES) {
  const other = valuesOf(locale);
  for (const [path, value] of ENGLISH) {
    if (other.get(path) === value && !TOKENS.has(path)) unnamed.push(`${locale}: ${path}`);
  }
}
for (const path of TOKENS.keys()) {
  const value = ENGLISH.get(path);
  if (value === undefined) {
    stale.push(`${path} is not in the English catalogue at all`);
    continue;
  }
  for (const locale of LOCALES) {
    const other = valuesOf(locale);
    if (!other.has(path)) stale.push(`${locale}: ${path} is named a token but the catalogue holds no such key`);
    else if (other.get(path) !== value) stale.push(`${locale}: ${path} is named a token but is translated`);
  }
}

check(
  "every value any catalogue shares with the English is a named technical token",
  unnamed.length === 0,
  unnamed.length === 0
    ? `${TOKENS.size} token(s) named; ${LOCALES.length} catalogue(s) compared (${LOCALES.join(", ") || "none"})`
    : `${unnamed.length} identical value(s) that are not named: ${unnamed.slice(0, 8).join(" | ")}`,
);

check(
  "every named technical token is still a token",
  stale.length === 0,
  stale.length === 0
    ? `${TOKENS.size} token(s) checked across ${LOCALES.length} catalogue(s)`
    : `${stale.length} stale name(s): ${stale.slice(0, 8).join(" | ")}`,
);

/**
 * The catalogue's own table: the figures it publishes, checked against the catalogue itself.
 *
 * `apps/web/messages/README.md` states how many keys the catalogue holds and how many of them are
 * translated, and that table is the number a reader is given. It was stale twice in this arc — once
 * because nothing recomputed it, and once because four keys landed after the last recompute and only
 * the API's suite could see it. This gate can see it too: the population and the translated count are
 * both derivable from the catalogues the directory ships, and the two numbers the table states are the
 * two numbers a reader is given. The loop is over the discovered locales, so an `ar.json` that ships
 * without a row in this table is a finding, not an omission nobody was asked about.
 */
const translatedCount = (locale) => {
  const other = valuesOf(locale);
  let count = 0;
  for (const [path, value] of ENGLISH) {
    if (other.get(path) !== value) count += 1;
  }
  return count;
};

let readme = "";
try {
  readme = readText(join(MESSAGES, "README.md"));
} catch {
  readme = "";
}
const population = ENGLISH.size;
const staleRows = [];
for (const locale of LOCALES) {
  const row = new RegExp(`\\|\\s*\`?${locale}\\.json\`?\\s*\\|\\s*(\\d+) of (\\d+)`, "u").exec(readme);
  if (!row) {
    staleRows.push(`${locale}: the table states no figure`);
    continue;
  }
  const stated = Number(row[1]);
  const statedPopulation = Number(row[2]);
  const translated = translatedCount(locale);
  if (statedPopulation !== population) {
    staleRows.push(`${locale}: the table counts a population of ${statedPopulation}; the catalogue holds ${population}`);
  }
  if (stated !== translated) {
    staleRows.push(`${locale}: the table claims ${stated} translated keys; the catalogue holds ${translated}`);
  }
}

check(
  "the catalogue's own table states the figures the catalogue holds",
  staleRows.length === 0,
  staleRows.length === 0
    ? `${population} key(s); ${LOCALES.map((locale) => `${locale} ${translatedCount(locale)}`).join(", ")} translated`
    : staleRows.join(" | "),
);

/**
 * The sentences held under two keys, and whether they are worded the same way in every language.
 *
 * A sentence written twice is a translation written twice, and the two will drift: the reader meets
 * one button written two ways. The count is a **floor** for now, at the count this gate read when it
 * learned to see the shape, and it may only fall — every sentence that is brought into line lowers
 * it. A repeat inside one namespace is a tier's own name in its own surfaces, which is deliberate.
 *
 * The floors are keyed on the locales that have been **measured**, and a catalogue that ships without
 * one is a finding: the old `drift = { zh: [], "zh-TW": [] }` plus a discovered locale was a crash, and
 * a crash is not a verdict either. Shipping a new language means writing down the count its copy starts
 * at, which is the argument the floor exists to force.
 */
const DRIFT_FLOORS = { zh: 0, "zh-TW": 0, ar: 0, he: 0 };
const holders = new Map();
for (const [path, value] of ENGLISH) {
  if (value.length <= 12) continue;
  if (!holders.has(value)) holders.set(value, []);
  holders.get(value).push(path);
}
const drift = new Map(LOCALES.map((locale) => [locale, []]));
const noFloor = [];
for (const [value, keys] of holders) {
  if (keys.length < 2) continue;
  if (new Set(keys.map((path) => path.split(".")[0])).size === 1) continue;
  for (const locale of LOCALES) {
    if (!Object.hasOwn(DRIFT_FLOORS, locale)) continue;
    const wordings = new Set(keys.map((path) => valuesOf(locale).get(path)));
    if (wordings.size > 1) drift.get(locale).push(`${value.slice(0, 40)} — ${keys.join(", ")}`);
  }
}
const driftFindings = [];
for (const locale of LOCALES) {
  if (!Object.hasOwn(DRIFT_FLOORS, locale)) {
    noFloor.push(`${locale}: ${locale}.json ships but no floor is on record — write DRIFT_FLOORS.${locale} at the count this rule measures today, with the reason if it is not 0`);
    continue;
  }
  const found = drift.get(locale);
  if (found.length > DRIFT_FLOORS[locale]) {
    driftFindings.push(
      `${locale}: ${found.length} sentence(s) held under two keys are worded more than one way (floor ${DRIFT_FLOORS[locale]}): ${found.slice(0, 4).join(" | ")}`,
    );
  }
}

check(
  "a sentence held under two keys is worded the same way in every language",
  driftFindings.length === 0 && noFloor.length === 0,
  driftFindings.length === 0 && noFloor.length === 0
    ? `${holders.size} distinct sentence(s) over ${LOCALES.length} catalogue(s); floors ${Object.entries(DRIFT_FLOORS).map(([l, n]) => `${l} ${n}`).join(", ")}`
    : [...noFloor, ...driftFindings].join(" | "),
);

/**
 * The table is defined once. A second copy is where an exemption goes stale.
 *
 * `qa-token-drift.mjs` held the same 45 paths and the same 45 reasons as its own literal on 2026-11-08, and
 * because the two copies agreed, nothing was wrong — which is exactly how a copy survives: it agrees right up
 * to the edit that only one of them gets. This census counts, for every script sitting beside this one, how
 * many of the paths defined here appear as an entry literal in its own source, and charges any file that
 * holds enough of them to be a table rather than a passing mention.
 */
const COPY_THRESHOLD = 5;
const SCRIPTS_DIR = join(WEB, "scripts");
const copiers = [];
for (const name of readdirSync(SCRIPTS_DIR).filter((f) => f.endsWith(".mjs"))) {
  if (name === SELF) continue;
  const text = readText(join(SCRIPTS_DIR, name));
  const held = [...TOKENS.keys()].filter((path) => text.includes(`["${path}",`)).length;
  if (held >= COPY_THRESHOLD) copiers.push(`${name} re-states ${held} of the ${TOKENS.size} entries as its own literals`);
}

check(
  "this table is defined in one file and read by every gate that needs it",
  copiers.length === 0,
  copiers.length === 0
    ? `${TOKENS.size} entries defined here; no other script in scripts/ holds ${COPY_THRESHOLD}+ of them as literals`
    : copiers.join(" | "),
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);

/** Four of the checks above are *comparisons*, and with no second catalogue each of them visits nothing and
 *  prints a clean line. The population check reds, so the gate does not pass — but a reader scanning for
 *  `FAIL` should not have to work out which PASSes judged anything. */
if (LOCALES.length === 0) {
  console.log(`\nNOT JUDGED  the shared-value rule, the named-token rule, the catalogue's own table and the drift floors compared nothing: messages/ holds no catalogue beside en.json (${SHIPPED.join(", ") || "not even that"}).`);
}

if (failed.length) {
  console.log("");
  console.log("Every value below is the same in every language without a reason, or is named without being one:");
  for (const path of unnamed) console.log(`  ${path}`);
  for (const path of stale) console.log(`  ${path}`);
  process.exitCode = 1;
}
