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
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const LOCALES = ["zh", "zh-TW"];

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
const english = catalogue("en");

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/* --- the first claim: the English file is English --- */
const cjk = /\p{Script=Han}/u;
const chineseInEnglish = [];
for (const [namespace, block] of Object.entries(english)) {
  if (!block || typeof block !== "object") continue;
  for (const [key, value] of Object.entries(block)) {
    if (typeof value === "string" && cjk.test(value)) chineseInEnglish.push(`${namespace}.${key}`);
  }
}

check(
  "the English catalogue holds no Chinese",
  chineseInEnglish.length === 0,
  chineseInEnglish.length === 0
    ? `${Object.keys(english).length} namespaces read`
    : `${chineseInEnglish.length} value(s) in English that are Chinese: ${chineseInEnglish.slice(0, 6).join(", ")}`,
);

/* --- the second claim: the identical values are the named ones --- */
const unnamed = [];
const stale = [];
for (const locale of LOCALES) {
  const other = catalogue(locale);
  for (const [namespace, block] of Object.entries(english)) {
    if (!block || typeof block !== "object") continue;
    for (const [key, value] of Object.entries(block)) {
      if (typeof value !== "string") continue;
      if (other[namespace]?.[key] !== value) continue;
      const path = `${namespace}.${key}`;
      if (!TOKENS.has(path)) unnamed.push(`${locale}: ${path}`);
    }
  }
}
for (const path of TOKENS.keys()) {
  const dot = path.indexOf(".");
  const namespace = path.slice(0, dot);
  const key = path.slice(dot + 1);
  const value = english[namespace]?.[key];
  if (typeof value !== "string") {
    stale.push(`${path} is not in the English catalogue at all`);
    continue;
  }
  for (const locale of LOCALES) {
    if (catalogue(locale)[namespace]?.[key] !== value) {
      stale.push(`${locale}: ${path} is named a token but is translated`);
    }
  }
}

check(
  "every value the Chinese catalogues share with the English is a named technical token",
  unnamed.length === 0,
  unnamed.length === 0
    ? `${TOKENS.size} token(s) named`
    : `${unnamed.length} identical value(s) that are not named: ${unnamed.slice(0, 8).join(" | ")}`,
);

check(
  "every named technical token is still a token",
  stale.length === 0,
  stale.length === 0 ? `${TOKENS.size} token(s) checked` : `${stale.length} stale name(s): ${stale.slice(0, 8).join(" | ")}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  console.log("Every value below is the same in every language without a reason, or is named without being one:");
  for (const path of unnamed) console.log(`  ${path}`);
  for (const path of stale) console.log(`  ${path}`);
  process.exitCode = 1;
}
