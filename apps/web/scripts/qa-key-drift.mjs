#!/usr/bin/env node
/*
 * Translation drift, measured on the population where it is a defect.
 *
 * The gate this replaces compared translations **across namespaces**: the same English sentence in
 * `simulate` and in `worldMatch` had to carry the same Chinese, and the same key name in two namespaces
 * had to carry the same Chinese. On 2026-10-25 that population held **119** sentence drifts and **107**
 * key drifts, and a review of every one found **no defect**: "Home" is the nav's homepage and the match's
 * home team; `thP` is "played" in one table and "passes" in the other; "Plan" is a subscription in
 * `settings` and a training programme in `coach`. So the gate was red on a hundred-percent-correct tree,
 * and CI (which runs it) had never reached the steps after it. A threshold that a correct tree cannot
 * meet is not a gate: it is a step that always fails.
 *
 * This file asks the question the old one was reaching for, in the population where the answer means
 * something: **inside one namespace**, two keys with the same English sentence are the same sentence in
 * the same context, so they must carry the same Chinese. That population is **125** groups at the
 * 2026-10-29 ratchet and **12** of them diverge; every one is named in `REVIEWED` with its reason, and a
 * group that is not named is red. The ledger is keyed on **identity** (`namespace|key1,key2`), not a
 * count, so fixing one group cannot pay for a new one.
 *
 * The cross-namespace population is still **measured**, as a ceiling that may only fall: a new shared
 * sentence with a divergent translation, or a new shared key name that diverges, raises the count and is
 * red. Its ceilings were the reviewed 2026-10-25 figures (119/107) and were ratcheted on 2026-10-28 to
 * the figures the tree actually measures — the review's population dissolved under the alignment cures,
 * so a stale ceiling would stop biting.
 *
 * Checks:
 *   1  the scan reads three parallel catalogues, and finds both populations — a parse that returns
 *      nothing, or a locale missing keys, must not read as "no drift"
 *   2  no unreviewed same-context drift — an identity not in `REVIEWED`
 *   3  cross-namespace sentence drift does not exceed its reviewed ceiling
 *   4  cross-namespace key drift does not exceed its reviewed ceiling
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

const LOCALES = ["en", "zh", "zh-TW"];

/**
 * Same-context drift sites reviewed on 2026-10-25, keyed by `namespace|sorted keys`.
 *
 * Each is a pair (or group) of keys in one namespace that share an English sentence and deliberately
 * carry different Chinese. A group whose keys change, or a new group, is not covered by these reasons
 * and is red.
 */
const REVIEWED = {
  "common|name,personName": "a record's name and a person's full name",
  "scout|askingFee,kvAskingFee,thAskingFee": "one fee under a value label and a column header; the Chinese files use synonyms",
  "scout|atClub,awayAt": "'currently at' and 'away at' are different relations",
  "scout|bandsTitle,kvBands": "the section title and the key-value label",
  "scout|careerLabel,listCareerPlaceholder": "a field label and its placeholder",
  "tactics|tableValue,thValue": "a cell label and its column header",
  "tactics|tableFormula,thHowObtained": "a cell label and its column header",
  "tactics|framesTitle,playPhaseChange": "the panel title and the action it offers",
  "knowledge|askEyebrow,askLibrary": "the eyebrow and the action",
  "club|eraseFixture,noticeErase,tableHeaderErase,tableHeaderErase2": "the action, the notice and two column headers",
  "errors|no_such_club,no_such_team": "one club, whose noun the API fixes as 'club'; the Chinese files use two synonyms",
  "simulate|ariaSubstitutions,substitutionsLabel": "a field label and its accessible name; the aria reads as a count ('换人次数'), the label as the action ('换人'), mirrored in both CJK locales",
};

/** Cross-namespace drift, measured. Ratcheted on 2026-10-29 to the figures this HEAD measures
 * (96 sentence issues over 248 shared sentences, 42 key issues over 260 shared keys) — the
 * same-sense alignment cures of 2026-10-27..29 dissolved most of the 2026-10-25 review's 119/107
 * and no new drift arrived (dce0734 measured 119/107 exactly; b59544b measured 99/42; the plan-share
 * landing measured 106 before its Opened/Closed/Career/Child/Token/Link-ready alignments took it to
 * 96). These may only fall further. */
const SENTENCE_CEILING = 96;
const KEY_CEILING = 42;

const catalogues = {};
for (const locale of LOCALES) {
  catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const pairs = (object) => Object.entries(object ?? {}).filter(([, value]) => typeof value === "string");

/** 1. The scan's own premise: three catalogues with the same keys, and both populations non-empty. */
const catalogueIssues = [];
const namespaces = new Set(LOCALES.flatMap((locale) => Object.keys(catalogues[locale])));
for (const namespace of [...namespaces].sort()) {
  const sets = LOCALES.map((locale) =>
    pairs(catalogues[locale][namespace]).map(([key]) => key).sort().join("\u0000"));
  if (new Set(sets).size > 1) {
    const counts = LOCALES.map((locale) => pairs(catalogues[locale][namespace]).length).join("/");
    catalogueIssues.push(`${namespace}: ${LOCALES.join("/")} hold ${counts} key(s)`);
  }
}

// Cross-namespace population, counted exactly as the old gate counted it so the ceilings mean what the
// review measured: one issue per (sentence, locale) and one per (key, namespace, locale).
const sentenceMap = new Map();
for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const [key, enValue] of pairs(block)) {
    if (!sentenceMap.has(enValue)) sentenceMap.set(enValue, []);
    sentenceMap.get(enValue).push({ namespace, key });
  }
}

let sharedSentences = 0;
let sentenceDrift = 0;
for (const [, entries] of sentenceMap) {
  if (new Set(entries.map((entry) => entry.namespace)).size < 2) continue;
  sharedSentences += 1;
  for (const locale of ["zh", "zh-TW"]) {
    const translations = new Set(entries.map((entry) => catalogues[locale][entry.namespace]?.[entry.key]).filter(Boolean));
    if (translations.size > 1) sentenceDrift += 1;
  }
}

let sharedKeys = 0;
let keyDrift = 0;
for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const [key, enValue] of pairs(block)) {
    const others = Object.keys(catalogues.en).filter((ns) => ns !== namespace && catalogues.en[ns]?.[key] === enValue);
    if (others.length === 0) continue;
    sharedKeys += 1;
    for (const locale of ["zh", "zh-TW"]) {
      const translations = new Set(
        [namespace, ...others].map((ns) => catalogues[locale][ns]?.[key]).filter(Boolean),
      );
      if (translations.size > 1) keyDrift += 1;
    }
  }
}

// Same-context population: groups of two or more keys, inside one namespace, that share an English
// sentence. Check 2 judges the drifting subset; check 1 holds that the groups themselves were found.
let sameContextGroups = 0;
const driftSites = [];
for (const [namespace, block] of Object.entries(catalogues.en)) {
  const groups = new Map();
  for (const [key, enValue] of pairs(block)) {
    if (!groups.has(enValue)) groups.set(enValue, []);
    groups.get(enValue).push(key);
  }
  for (const [sentence, keys] of groups) {
    if (keys.length < 2) continue;
    sameContextGroups += 1;
    const translations = ["zh", "zh-TW"].map((locale) =>
      new Set(keys.map((key) => catalogues[locale][namespace]?.[key]).filter(Boolean)));
    if (translations.every((set) => set.size <= 1)) continue;
    driftSites.push({ namespace, keys: [...keys].sort(), sentence, translations });
  }
}

check(
  "the scan reads three parallel catalogues and finds both populations",
  catalogueIssues.length === 0 && sharedSentences > 0 && sharedKeys > 0 && sameContextGroups > 0,
  catalogueIssues.length > 0
    ? `${catalogueIssues.length} namespace(s) with unequal keys across locales: ${catalogueIssues.slice(0, 4).join(" | ")}`
    : `${sharedSentences} sentence(s) shared across namespaces, ${sharedKeys} shared key(s), ${sameContextGroups} same-context group(s)`,
);

/** 2. Every same-context drift site must be named with its reason. */
const unreviewed = driftSites.filter((site) => !Object.hasOwn(REVIEWED, `${site.namespace}|${site.keys.join(",")}`));
const staleSites = Object.keys(REVIEWED).filter(
  (identity) => !driftSites.some((site) => `${site.namespace}|${site.keys.join(",")}` === identity),
);

check(
  "no unreviewed same-context translation drift",
  unreviewed.length === 0,
  unreviewed.length === 0
    ? `${driftSites.length} drifting site(s) of ${sameContextGroups} group(s), all named (${staleSites.length} ledger entr${staleSites.length === 1 ? "y" : "ies"} no longer drift)`
    : `${unreviewed.length} site(s) not in the ledger: ${unreviewed.slice(0, 4).map((site) => `${site.namespace}|${site.keys.join(",")}`).join(" | ")}`,
);

/** 3 and 4. The cross-namespace population may only fall. */
check(
  "cross-namespace sentence drift does not exceed its reviewed ceiling",
  sentenceDrift <= SENTENCE_CEILING,
  `${sentenceDrift} issue(s) over ${sharedSentences} shared sentence(s), ceiling ${SENTENCE_CEILING}`,
);

check(
  "cross-namespace key drift does not exceed its reviewed ceiling",
  keyDrift <= KEY_CEILING,
  `${keyDrift} issue(s) over ${sharedKeys} shared key(s), ceiling ${KEY_CEILING}`,
);

/** The full list, so a red names every site rather than a sample. */
console.log("\nSame-context drift sites (each must be in the ledger):");
for (const site of driftSites) {
  const identity = `${site.namespace}|${site.keys.join(",")}`;
  const reason = REVIEWED[identity] ? `reviewed: ${REVIEWED[identity]}` : "NOT IN THE LEDGER";
  const values = site.translations.map((set, index) => `${["zh", "zh-TW"][index]}=${[...set].join(" / ")}`);
  console.log(`  ${identity}  [${values.join("; ")}]  ${reason}`);
}
if (staleSites.length > 0) {
  console.log(`\nLedger entries that no longer drift (prune when convenient): ${staleSites.join(", ")}`);
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
