#!/usr/bin/env node
/*
 * Token drift gate: detect when technical tokens diverge from the catalogue.
 *
 * The locale-token gate names the values that are supposed to be identical across
 * all languages. This gate holds that those named tokens remain stable — a token
 * that was identical across locales but diverges in a new commit is a finding.
 * Conversely, a value that diverges but is not named is also a finding.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const LOCALES = ["zh", "zh-TW"];

/** The named technical tokens from qa-locale-tokens.mjs */
const NAMED_TOKENS = new Map([
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
  ["club.createNamePlaceholder", "an example proper name"],
  ["club.teamNamePlaceholder", "an example proper name"],
  ["club.playerSlugPlaceholder", "an example slug"],
]);

const english = JSON.parse(readFileSync(join(MESSAGES, "en.json"), "utf8"));
const zh = JSON.parse(readFileSync(join(MESSAGES, "zh.json"), "utf8"));
const zhTw = JSON.parse(readFileSync(join(MESSAGES, "zh-TW.json"), "utf8"));

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** Check that every named token is still identical across all three locales */
const tokenDrift = [];
const missingTokens = [];

for (const [path, reason] of NAMED_TOKENS) {
  const dot = path.indexOf(".");
  const namespace = path.slice(0, dot);
  const key = path.slice(dot + 1);

  const enVal = english[namespace]?.[key];
  const zhVal = zh[namespace]?.[key];
  const zhTwVal = zhTw[namespace]?.[key];

  if (enVal === undefined) {
    missingTokens.push(`${path} is not in English catalogue`);
    continue;
  }

  if (zhVal !== enVal) {
    tokenDrift.push(`${path}: zh="${zhVal}" !== en="${enVal}" (reason: ${reason})`);
  }
  if (zhTwVal !== enVal) {
    tokenDrift.push(`${path}: zh-TW="${zhTwVal}" !== en="${enVal}" (reason: ${reason})`);
  }
}

check(
  "every named technical token is still identical across all locales",
  tokenDrift.length === 0 && missingTokens.length === 0,
  tokenDrift.length === 0 && missingTokens.length === 0
    ? `${NAMED_TOKENS.size} token(s) stable`
    : `drift: ${tokenDrift.slice(0, 4).join(" | ")}; missing: ${missingTokens.slice(0, 4).join(" | ")}`,
);

/** Check for new identical values that should be named (the reverse direction) */
const unnamedIdentical = [];
for (const [namespace, block] of Object.entries(english)) {
  for (const [key, enVal] of Object.entries(block)) {
    if (typeof enVal !== "string") continue;
    const path = `${namespace}.${key}`;
    if (NAMED_TOKENS.has(path)) continue;

    const zhVal = zh[namespace]?.[key];
    const zhTwVal = zhTw[namespace]?.[key];

    if (zhVal === enVal && zhTwVal === enVal) {
      // This value is identical across all three locales but not named
      // Allow short values (acronyms, numbers) to reduce noise
      if (enVal.length > 3 && /[a-zA-Z]/.test(enVal)) {
        unnamedIdentical.push(`${path}: "${enVal}"`);
      }
    }
  }
}

check(
  "no unnamed identical values that should be named tokens",
  unnamedIdentical.length === 0,
  unnamedIdentical.length === 0
    ? "no new unnamed identical values"
    : `${unnamedIdentical.length} unnamed identical value(s): ${unnamedIdentical.slice(0, 6).join(" | ")}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}