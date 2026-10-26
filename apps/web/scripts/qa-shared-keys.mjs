#!/usr/bin/env node
/*
 * A key NAME shared across namespaces is not a contract. A VALUE shared across namespaces is.
 *
 * This gate used to count the first thing. It read every key whose *name* appeared in more than one namespace and
 * asked that a human name a reason for each one — 234 rows on 2026-10-26, of which 133 were named by a pattern or by
 * hand and 101 were admitted by a tolerance ("Allow up to 120 unnamed keys … within tolerance"). Two consequences,
 * both measured:
 *
 *   - A tolerance cannot see a new site. Any new key that happened to share a name with one in another namespace
 *     raised 101 to 102 and passed, so the gate could not tell a deliberate reuse from the first day of a drift.
 *   - The rows it was counting were mostly not shared at all. `backLabel` appears in fifteen namespaces and holds
 *     fifteen different sentences; `askFailed` holds three different sentences. They share a convention of naming,
 *     not copy, and 136 of the 234 rows are like that.
 *
 * The defect the gate exists for is the other thing: one English sentence stored in two namespaces must be
 * *translated* the same way, or the same label reads differently on two pages and a translator has to fix it twice.
 * The old gate never compared a value. Measured on the same tree, of the **98** rows whose English really is one
 * sentence across all the namespaces that hold it, **24** carried different Chinese — `community.publishing` said
 * "发布中…" where `creator.publishing` said "正在发布…", `community.thAnswer` said "回答" where three other
 * namespaces said "作答", `myFootball.openDrill` said "打开动作" where the coach page said "打开训练". None of
 * them could move the old gate's verdict.
 *
 * So the population is value-shared rows, and there are two verdicts:
 *
 *   1. A **divergence** — the same English sentence translated differently across the namespaces that hold it — is
 *      green only for the rows named in DIVERGENCES, each with the reason the two contexts really differ. Nine rows
 *      survive that review: `home` is the nav's Home page and a fixture's home side ("首页" vs "主队"); `thP` is
 *      played in the league table and passes in the match table ("场" vs "传"); `vs` is a token in the challenge
 *      card and 对阵 in the fixture line. Every other divergence was the same phrase translated twice and was
 *      aligned on 2026-10-26, in both Chinese catalogues, rather than named.
 *   2. The **population of duplicated sentences** is a ceiling that may only fall — 98 sentences held in **234**
 *      namespace bindings today. The binding count is what is held, not the row count: a sentence added to a sixth
 *      namespace is a sixth copy to keep in step, and counting rows alone would let it spread without a word. A new
 *      sentence stored in a second namespace raises the count by two, which is what this gate says; wiring a page to
 *      a shared key lowers it.
 *
 * What this gate does *not* claim: that two namespaces holding one English sentence should share a key. The
 * catalogue is namespace-scoped on purpose, and `nobody` in the club's fixture table ("无对手", no opponent) and in
 * the scout's report ("无人", no person) is the proof that the same word can be two different sentences. That is
 * exactly why the divergence list is named row by row instead of derived from the English.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const LOCALES = { zh: "zh.json", "zh-TW": "zh-TW.json" };

// Identity is the key AND the namespaces that hold it: a key that starts being shared with a fourth namespace is a
// different row, and the reason written for the three it used to have does not answer for it.
const id = (key, namespaces) => `${key}|${namespaces.join(",")}`;

const DIVERGENCES = new Map([
  [id("home", ["nav", "simulate"]), "the nav's Home page (首页) and the home side of a fixture (主队)"],
  [id("nobody", ["club", "scout"]), "no opponent in the club's fixture table (无对手), no person in the scout's report (无人)"],
  [id("searching", ["knowledge", "scout"]), "the library's retrieval (检索) and the scout's player search (搜索)"],
  [id("thFixture", ["careerDetail", "club", "scout", "world"]), "the match-up in two tables (对阵) and the scheduled round in the others (赛程)"],
  [id("thGd", ["career", "careerDetail", "worldCompetition"]), "the league table abbreviates the column to one character (净) to fit"],
  [id("vs", ["careerDetail", "challenges"]), "'vs' is a token in the challenge card and 对阵 in the fixture line"],
  [id("erase", ["community", "creator"]), "delete a post (删除), or erase the account's own data (擦除)"],
  [id("playing", ["club", "simulate"]), "a round in progress (正在开踢) and a stored match being played back (播放中)"],
  [id("thP", ["worldCompetition", "worldMatch"]), "'P' is played in the league table (场) and passes in the match table (传)"],
]);

// The rows whose English is one sentence, counted in namespace bindings: a sentence held by six namespaces is six
// copies, so a sixth namespace added to an existing sentence raises the count by one. May only fall.
const VALUE_CEILING = 234;
const NAMESPACE_FLOOR = 30;

const read = (file) => JSON.parse(readFileSync(join(MESSAGES, file), "utf8"));
const english = read("en.json");
const catalogues = { zh: read(LOCALES.zh), "zh-TW": read(LOCALES["zh-TW"]) };

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const byKey = new Map();
for (const [namespace, block] of Object.entries(english)) {
  for (const key of Object.keys(block)) {
    if (!byKey.has(key)) byKey.set(key, new Set());
    byKey.get(key).add(namespace);
  }
}

const valueShared = [];
const nameOnly = [];
for (const [key, set] of byKey) {
  if (set.size < 2) continue;
  const namespaces = [...set].sort();
  const sentences = new Set(namespaces.map((namespace) => english[namespace][key]));
  if (sentences.size === 1) valueShared.push({ key, namespaces, sentence: [...sentences][0] });
  else nameOnly.push({ key, namespaces });
}
valueShared.sort((a, b) => a.key.localeCompare(b.key));
nameOnly.sort((a, b) => a.key.localeCompare(b.key));

// A value-shared row whose key is absent from a Chinese catalogue would read as a divergence and send someone to
// re-translate a key that simply is not there; the population guard charges that instead.
const missing = [];
const divergent = [];
for (const row of valueShared) {
  for (const locale of Object.keys(LOCALES)) {
    for (const namespace of row.namespaces) {
      if (typeof catalogues[locale][namespace]?.[row.key] !== "string") {
        missing.push(`${locale}:${namespace}.${row.key}`);
      }
    }
  }
  const zh = new Set(row.namespaces.map((namespace) => catalogues.zh[namespace]?.[row.key]));
  const zhTw = new Set(row.namespaces.map((namespace) => catalogues["zh-TW"][namespace]?.[row.key]));
  if (zh.size > 1 || zhTw.size > 1) {
    const shown = (locale) =>
      row.namespaces.map((namespace) => `${namespace}=${JSON.stringify(catalogues[locale][namespace]?.[row.key])}`).join(" ");
    divergent.push({ ...row, zh: shown("zh"), zhTw: shown("zh-TW") });
  }
}

const namespaces = Object.keys(english).length;
check(
  "the scan reads three catalogues and finds both populations",
  namespaces >= NAMESPACE_FLOOR && valueShared.length > 0 && nameOnly.length > 0 && missing.length === 0,
  `namespaces=${namespaces} value-shared=${valueShared.length} name-only=${nameOnly.length}`
    + (missing.length ? ` missing-from-chinese=${missing.slice(0, 4).join(", ")}` : ""),
);

const unreviewed = divergent.filter((row) => !DIVERGENCES.has(id(row.key, row.namespaces)));
check(
  "no unreviewed cross-namespace translation drift",
  unreviewed.length === 0,
  unreviewed.length === 0
    ? `${divergent.length} named divergence(s)`
    : unreviewed
        .slice(0, 4)
        .map((row) => `${id(row.key, row.namespaces)} en=${JSON.stringify(row.sentence)} ${row.zh}`)
        .join(" | "),
);

// A named reason that no longer holds is a hiding place: the site was aligned or the key was removed, and the
// ledger entry would swallow the next divergence to appear under the same key.
const diverging = new Set(divergent.map((row) => id(row.key, row.namespaces)));
const stale = [...DIVERGENCES.keys()].filter((entry) => !diverging.has(entry));
check(
  "every named divergence still diverges",
  stale.length === 0,
  stale.length === 0 ? `${DIVERGENCES.size} ledger entr(y/ies) current` : `no longer divergent: ${stale.join(", ")}`,
);

const bindings = valueShared.reduce((total, row) => total + row.namespaces.length, 0);
check(
  "the duplicated-sentence population does not exceed its reviewed ceiling",
  bindings <= VALUE_CEILING,
  `${bindings} binding(s) across ${valueShared.length} row(s), ceiling ${VALUE_CEILING}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log("");
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
}
console.log(`Summary: ${namespaces} namespaces, ${byKey.size} distinct key names`);
console.log(`  ${valueShared.length} key(s) hold the same English sentence in every namespace that has them`);
console.log(`  ${nameOnly.length} key name(s) are shared while their values differ — independent keys, not findings`);
console.log(`  ${divergent.length} of the value-shared rows are translated differently across namespaces, all named:`);
for (const row of divergent) {
  console.log(`    ${id(row.key, row.namespaces)}  ${row.zh}  |  ${row.zhTw}`);
  console.log(`      reviewed: ${DIVERGENCES.get(id(row.key, row.namespaces)) ?? "UNREVIEWED"}`);
}
if (stale.length) {
  console.log("  ledger entries that no longer hold:");
  for (const entry of stale) console.log(`    ${entry} — ${DIVERGENCES.get(entry)}`);
}

if (failed.length) process.exitCode = 1;
