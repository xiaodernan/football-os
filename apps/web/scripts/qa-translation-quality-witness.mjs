#!/usr/bin/env node
/*
 * The translation-quality gate's verdicts, on scratch catalogues.
 *
 * `qa-translation-quality.mjs` judges three catalogues on disk (en, zh, zh-TW) and owns rules for two more
 * (ar, he) that ship in no checkout. Reading it green therefore says nothing about the Arabic script rule,
 * the Hebrew script rule, the discovery of a fourth catalogue, or the exemption set it used to copy by hand.
 * This file builds a fixture per verdict and runs the **shipped** gate against each through `QA_I18N_WEB`, so
 * what is measured is the gate's behaviour rather than its code being read.
 *
 * Predictions, written before the first run (2026-11-08; baseline: 3 shipped catalogues, 9 checks, the two
 * script rules dormant, 45 named tokens, 90 messages identical to English across zh and zh-TW, all 90 named;
 * the session-language list below now widens to ar and he the day one of them ships).
 *   0  the shipped gate on the real catalogues: 9/9, both script lines reading `dormant`, and the DORMANT
 *      trailer naming both — a PASS that says it judged nothing is the cure for hole 1.
 *   A  an `ar.json` of two Arabic messages and one Latin holdout: 1 red, the Arabic script check, naming that
 *      path — the per-message branch, not the whole-file one.
 *   B  an `ar.json` that is a byte copy of `en.json`: 2 reds — the Arabic script check (0 of >100 messages
 *      show the script) and the identical check (thousands unnamed). This is hole 2: pre-fix 6/6 green.
 *   C  an `ar.json` in which no message carries copy (one named token, one `{count}`): 1 red, the Arabic
 *      script check, saying 0 message(s) carry copy — a shipped file judged nothing must not read clean.
 *   D  an `ar.json` correctly written in Arabic: 9/9, the Arabic line counting "2 of 2", the trailer naming
 *      Hebrew only. The arm that proves a real translation passes, so the floor cannot be an accident.
 *   E  the same holdout shape in `he.json`: 1 red, the Hebrew script check alone, and the Arabic line still
 *      reads dormant.
 *   F  a `fr.json` in the directory: 1 red, the discovery check, naming the file. Hole 3: pre-fix 6/6 green.
 *   G  a zh message identical to English with no named reason: 1 red, the identical check, naming the path.
 *   H  a plane whose `scripts/qa-locale-tokens.mjs` is gone: the exemption-table check reds and says the
 *      table is unreadable — and the empty set it produces is charged by the identical check rather than
 *      silently exempting nothing. The exact red set is measured on the first run, not asserted blind.
 *   I  four planted English-structure messages in zh (two `due to`, two `make sure`): the literal check
 *      counts 4. With `/g` and no `lastIndex` reset the same fixture scores 2 — measured here before the
 *      reset landed (`hits=2` versus `hits=4`), so half the population was read as clean by luck of order.
 *   J  the real catalogues after the fixture arms: 9/9, so no arm leaked into the tree.
 * Checks: 11, all green on the cured gate.
 *
 * Revised after the first run, which red 3 of these 11 and taught two things. (1) A and E were witness bugs,
 * twice over: a fixture holding *only* the Latin holdout leaves `scriptMessages` at zero, so the gate took
 * its whole-file branch — the one that says "0 of 1 show the script" and quotes no path — and my expectation
 * of a quoted path was asking the wrong branch for the wrong evidence. Both arms now ship two correctly
 * written messages beside the holdout, which is the shape the rule exists for and the one that names the
 * path. (2) F was a gate defect, not an arm bug: the discovery line printed the locale (`fr`) where the
 * reader needs the filename (`fr.json`) to act on it, and the arm's `fr.json` expectation caught that. The
 * gate now prints the file. Arm H's red set was written as "measure on the first run" because an empty
 * exemption table reaches past the table check; it measured `TABLE` plus the identical check over all 90
 * identical-to-English messages, which is the honest shape of the damage and is now pinned by a count
 * derived from the fixture rather than by the number 90.
 *
 * Files only: no server, no browser, no port.
 */

import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, cpSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const GATE = resolve(HERE, "qa-translation-quality.mjs");
const WEB = resolve(HERE, "..");
const REAL = join(WEB, "messages");
const TOKENS_SOURCE = join(WEB, "scripts", "qa-locale-tokens.mjs");
const LOCALES = ["en", "zh", "zh-TW", "ar", "he", "fr"].filter((locale) => existsSync(join(REAL, `${locale}.json`)));

/** One named token path, taken from the table rather than copied here: arm C needs a message the gate is
 *  supposed to exempt, and a hand-written path would go stale the day the table changes. */
const A_TOKEN = (() => {
  const body = /const TOKENS = new Map\(\[([\s\S]*?)\]\);/.exec(readFileSync(TOKENS_SOURCE, "utf8"));
  return /\[\s*"([^"]+)"\s*,/.exec(body[1])[1];
})();

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const root = mkdtempSync(join(tmpdir(), "qa-translation-quality-witness-"));
function fixture(name, { withTokens = true, locales = LOCALES } = {}) {
  const dir = join(root, name);
  mkdirSync(join(dir, "messages"), { recursive: true });
  for (const locale of locales) cpSync(join(REAL, `${locale}.json`), join(dir, "messages", `${locale}.json`));
  if (withTokens) {
    mkdirSync(join(dir, "scripts"), { recursive: true });
    cpSync(TOKENS_SOURCE, join(dir, "scripts", "qa-locale-tokens.mjs"));
  }
  return dir;
}
const read = (dir, locale) => JSON.parse(readFileSync(join(dir, "messages", `${locale}.json`), "utf8"));
const write = (dir, locale, data) =>
  writeFileSync(join(dir, "messages", `${locale}.json`), `${JSON.stringify(data, null, 2)}\n`);
/** One key of one scratch namespace, in one catalogue. A locale the tree does not ship gets a file
 *  created here, so the gate's own discovery is what the arm exercises. */
function setKey(dir, locale, key, value) {
  const path = join(dir, "messages", `${locale}.json`);
  const catalogue = existsSync(path) ? read(dir, locale) : {};
  (catalogue.witness ??= {})[key] = value;
  write(dir, locale, catalogue);
}
/** The same, at a dotted path of the catalogue's own choosing — arm C needs a message the gate really does
 *  exempt, and a named token lives at its declared `namespace.key`, not under a scratch namespace. */
function setPath(dir, locale, dottedPath, value) {
  const [namespace, key] = dottedPath.split(".");
  const path = join(dir, "messages", `${locale}.json`);
  const catalogue = existsSync(path) ? read(dir, locale) : {};
  (catalogue[namespace] ??= {})[key] = value;
  write(dir, locale, catalogue);
}
/** A message built to pass every other rule this gate holds, so an arm's single red is the charged one:
 *  three-letter words that all sit in the gate's allowed list, and no sentence-ending punctuation. */
const LATIN_HOLDOUT = "Match report is ready";
const ARABIC_COPY = "تقرير المباراة جاهز الآن";
const HEBREW_COPY = "דוח המשחק מוכן עכשיו";

const run = (dir) => {
  const result = spawnSync(process.execPath, [GATE], { env: { ...process.env, QA_I18N_WEB: dir }, encoding: "utf8" });
  const out = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  const tally = /CHECKS passed=(\d+) total=(\d+) failed=(\d+)/.exec(out);
  return {
    status: result.status,
    out,
    passed: tally ? Number(tally[1]) : null,
    total: tally ? Number(tally[2]) : null,
    failed: tally ? Number(tally[3]) : null,
    crashed: !tally && /TypeError|SyntaxError|ReferenceError/.test(out),
    reds: [...out.matchAll(/^FAIL\s{2}([^\n—]*?)\s+—/gm)].map((m) => m[1].trim()),
  };
};
const verdict = (out, label) =>
  (out.includes(`FAIL  ${label}`) ? "FAIL" : out.includes(`PASS  ${label}`) ? "PASS" : "absent");
const escapeRe = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
/** The gate's own words for one check, taken from its line rather than restated here: an expectation that
 *  quotes the printed reason goes red when the reason changes, which is the point. */
const detailOf = (out, label) =>
  (new RegExp(`^(?:PASS|FAIL)\\s{2}${escapeRe(label)}[^\\n]*? — ([^\\n]*)$`, "m").exec(out) ?? [])[1] ?? "";
const tallyOf = (r) => `rc=${r.status} passed=${r.passed} total=${r.total} failed=${r.failed}`;
const redSet = (r) => `reds: ${r.reds.join(" | ") || "(none)"}`;

const DISCOVER = "every catalogue in messages/ is a locale this gate has rules for";
const TABLE = "the technical-token exemption set is read from the gate that names each one";
const IDENTICAL = "every message byte-identical to English is a named technical token";
const UNTRANSLATED = "no untranslated English words in translations";
const PUNCT = "proper punctuation per locale";
const ENCODING = "no encoding issues (mojibake) in translations";
const LITERAL = "no overly literal English structures in Chinese translations";
const SCRIPT_AR = "every Arabic message in ar.json shows Arabic script";
const SCRIPT_HE = "every Hebrew message in he.json shows Hebrew script";
const ALL = [DISCOVER, TABLE, IDENTICAL, UNTRANSLATED, PUNCT, ENCODING, LITERAL, SCRIPT_AR, SCRIPT_HE];

const GREEN = (r) => r.status === 0 && r.passed === 9 && r.total === 9 && r.failed === 0;
/** Exactly one refusal, and it is the one the arm charges: an arm that reddens a second check has found a
 *  defect in the gate or in the arm, not a proof. */
const ONLY = (r, label) =>
  r.status === 1 && r.failed === 1 && r.total === 9 && verdict(r.out, label) === "FAIL" &&
  ALL.filter((l) => l !== label).every((l) => verdict(r.out, l) === "PASS");

// 0 — the shipped gate against the real catalogues, and both script rules it must count out loud. The
//     population figures are derived from the live catalogues rather than copied, so a translation batch that
//     grew the catalogue cannot leave the witness guessing at a stale number.
const zero = run(fixture("0-baseline"));
const arJudged = Number((/every Arabic message[^\n]*— (\d+) of/.exec(zero.out) ?? [])[1] ?? 0);
const heJudged = Number((/every Hebrew message[^\n]*— (\d+) of/.exec(zero.out) ?? [])[1] ?? 0);
check(
  "0 the shipped gate reads the real catalogues 9/9 with both script rules counted",
  GREEN(zero) && arJudged > 4000 && heJudged > 4000
    && detailOf(zero.out, SCRIPT_AR).startsWith(`${arJudged} of ${arJudged}`)
    && detailOf(zero.out, SCRIPT_HE).startsWith(`${heJudged} of ${heJudged}`)
    && !zero.out.includes("DORMANT"),
  `${tallyOf(zero)}; ar=${arJudged} he=${heJudged}; ${detailOf(zero.out, SCRIPT_AR)}`,
);

// A — one Latin holdout sitting in an otherwise correctly written Arabic catalogue.
const latin = fixture("A-arabic-latin-holdout");
setKey(latin, "ar", "report", ARABIC_COPY);
setKey(latin, "ar", "deals", "{count} صفقة");
setKey(latin, "ar", "holdout", LATIN_HOLDOUT);
const a = run(latin);
check(
  "A one Latin message among Arabic ones reds the Arabic script arm and names the path",
  ONLY(a, SCRIPT_AR) && detailOf(a.out, SCRIPT_AR).startsWith(`1 of ${arJudged + 3} message(s) judged in ar.json are Latin text`)
    && detailOf(a.out, SCRIPT_AR).includes("ar: witness.holdout")
    && detailOf(a.out, SCRIPT_AR).includes(LATIN_HOLDOUT) && !a.out.includes("DORMANT  Arabic"),
  `${tallyOf(a)}; ${detailOf(a.out, SCRIPT_AR).slice(0, 170)}; ${redSet(a)}`,
);

// B — the hole: ar.json as a byte copy of en.json.
const copyPlane = fixture("B-arabic-copy-of-english");
cpSync(join(REAL, "en.json"), join(copyPlane, "messages", "ar.json"));
const b = run(copyPlane);
const bJudged = Number((/^0 of (\d+) message\(s\)/.exec(detailOf(b.out, SCRIPT_AR)) ?? [])[1] ?? 0);
check(
  "B an ar.json copied from en.json reddens the script check and the identical check, not a 6/6 pass",
  b.status === 1 && b.failed === 2 && verdict(b.out, SCRIPT_AR) === "FAIL" && verdict(b.out, IDENTICAL) === "FAIL"
    && bJudged > 100 && detailOf(b.out, SCRIPT_AR).includes("reader cannot read")
    && ALL.filter((l) => l !== SCRIPT_AR && l !== IDENTICAL).every((l) => verdict(b.out, l) === "PASS"),
  `${tallyOf(b)}; ar judged ${bJudged}; ${redSet(b)}`,
);

// C — a shipped Arabic catalogue that carries no copy at all.
const noCopy = fixture("C-arabic-nothing-judged", { locales: ["en", "zh", "zh-TW"] });
const enCopy = read(noCopy, "en");
setPath(noCopy, "ar", A_TOKEN, enCopy[A_TOKEN.split(".")[0]][A_TOKEN.split(".")[1]]);
setKey(noCopy, "ar", "counter", "{count}");
const c = run(noCopy);
check(
  "C an ar.json of named tokens and bare placeholders is a red that says it judged nothing",
  ONLY(c, SCRIPT_AR) && detailOf(c.out, SCRIPT_AR).includes("0 message(s) carry copy")
    && detailOf(c.out, IDENTICAL).includes("named in qa-locale-tokens.mjs"),
  `${tallyOf(c)}; ${detailOf(c.out, SCRIPT_AR).slice(0, 170)}; ${redSet(c)}`,
);

// D — the same file correctly translated: the floor must not bite real work.
const realArabic = fixture("D-arabic-correctly-written", { locales: ["en", "zh", "zh-TW"] });
setKey(realArabic, "ar", "report", ARABIC_COPY);
setKey(realArabic, "ar", "deals", "{count} صفقة");
const d = run(realArabic);
check(
  "D an ar.json written in Arabic passes with its population counted, not its absence noted",
  GREEN(d) && detailOf(d.out, SCRIPT_AR).startsWith("2 of 2 message(s) judged in ar.json")
    && detailOf(d.out, SCRIPT_HE).startsWith("dormant") && d.out.includes("Hebrew script (he.json absent)"),
  `${tallyOf(d)}; ${detailOf(d.out, SCRIPT_AR)}; ${redSet(d)}`,
);

// E — the same holdout shape in Hebrew.
const hebrew = fixture("E-hebrew-latin-holdout", { locales: ["en", "zh", "zh-TW"] });
setKey(hebrew, "he", "report", HEBREW_COPY);
setKey(hebrew, "he", "deals", "{count} עסקה");
setKey(hebrew, "he", "holdout", LATIN_HOLDOUT);
const e = run(hebrew);
check(
  "E one Latin message among Hebrew ones reds the Hebrew script check alone",
  ONLY(e, SCRIPT_HE) && detailOf(e.out, SCRIPT_HE).startsWith("1 of 3 message(s) judged in he.json are Latin text")
    && detailOf(e.out, SCRIPT_HE).includes("he: witness.holdout")
    && detailOf(e.out, SCRIPT_AR).startsWith("dormant"),
  `${tallyOf(e)}; ${detailOf(e.out, SCRIPT_HE).slice(0, 170)}; ${redSet(e)}`,
);

// F — a catalogue the gate never named. `fr` is the shipped sixth now, so the plane plants a language with no
// rule anywhere: Esperanto. The discovery check must name it rather than pass it over silently.
const esperanto = fixture("F-locale-outside-the-candidate-list");
setKey(esperanto, "eo", "plain", LATIN_HOLDOUT);
const f = run(esperanto);
check(
  "F a catalogue with no rule is named by the discovery check rather than passed over",
  ONLY(f, DISCOVER) && detailOf(f.out, DISCOVER).includes("eo.json") && verdict(f.out, UNTRANSLATED) === "PASS",
  `${tallyOf(f)}; ${detailOf(f.out, DISCOVER).slice(0, 170)}; ${redSet(f)}`,
);

// G — an identical message nobody named.
const unnamed = fixture("G-identical-message-unnamed");
const enPlane = read(unnamed, "en");
(enPlane.witness ??= {}).unnamedCopy = LATIN_HOLDOUT;
write(unnamed, "en", enPlane);
setKey(unnamed, "zh", "unnamedCopy", LATIN_HOLDOUT);
const g = run(unnamed);
check(
  "G a zh message copied from English with no named reason is charged by name",
  ONLY(g, IDENTICAL) && detailOf(g.out, IDENTICAL).includes("zh: witness.unnamedCopy")
    && verdict(g.out, UNTRANSLATED) === "PASS",
  `${tallyOf(g)}; ${detailOf(g.out, IDENTICAL).slice(0, 170)}; ${redSet(g)}`,
);

// H — the exemption table missing from the plane.
const noTable = fixture("H-exemption-table-absent", { withTokens: false });
/** Every message this plane copies from English, counted here rather than read off the gate: with no table,
 *  none of them is named, so the identical check must report all of them. A hand-written count would rot the
 *  day the lane adds a key. */
const identicalExpected = (() => {
  const reference = read(noTable, "en");
  let count = 0;
  for (const locale of ["zh", "zh-TW", "ar", "he", "fr"]) {
    if (!existsSync(join(noTable, "messages", `${locale}.json`))) continue;
    for (const [namespace, block] of Object.entries(read(noTable, locale))) {
      for (const [key, value] of Object.entries(block ?? {})) {
        if (typeof value === "string" && reference[namespace]?.[key] === value) count += 1;
      }
    }
  }
  return count;
})();
const h = run(noTable);
check(
  "H a plane with no qa-locale-tokens.mjs reds the exemption table and the checks its absence opens",
  h.crashed === false && h.total === 9 && h.status === 1 && h.failed === 4
    && verdict(h.out, TABLE) === "FAIL"
    && detailOf(h.out, TABLE).includes("no qa-locale-tokens.mjs beside this gate")
    && verdict(h.out, IDENTICAL) === "FAIL"
    && detailOf(h.out, IDENTICAL).startsWith(`${identicalExpected} of ${identicalExpected}`)
    && verdict(h.out, SCRIPT_AR) === "FAIL"
    && detailOf(h.out, SCRIPT_AR).includes("judged in ar.json are Latin text")
    && verdict(h.out, SCRIPT_HE) === "FAIL"
    && detailOf(h.out, SCRIPT_HE).includes("judged in he.json are Latin text"),
  `${tallyOf(h)}; ${identicalExpected} identical message(s) on this plane; ${redSet(h)}`,
);

// I — the /g lastIndex skip: four planted messages, and the count the gate prints.
const literal = fixture("I-literal-structure-counted");
setKey(literal, "zh", "dueA", "due to first planted message");
setKey(literal, "zh", "dueB", "due to second planted message");
setKey(literal, "zh", "sureA", "make sure first planted message");
setKey(literal, "zh", "sureB", "make sure second planted message");
const i = run(literal);
check(
  "I four literal-structure messages count four, not the two the shared lastIndex read",
  verdict(i.out, LITERAL) === "FAIL" && detailOf(i.out, LITERAL).startsWith("4 literal translation issue(s)")
    && i.failed >= 1 && i.total === 9,
  `${tallyOf(i)}; ${detailOf(i.out, LITERAL).slice(0, 190)}; ${redSet(i)}`,
);

// J — nothing leaked into the tree.
const j = run(WEB);
check(
  "J the real catalogues still read 9/9 after the fixture arms, with both script rules counted",
  GREEN(j) && detailOf(j.out, SCRIPT_HE).startsWith(`${heJudged} of ${heJudged}`) && !j.out.includes("DORMANT"),
  `${tallyOf(j)}; ${redSet(j)}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name}${entry.detail ? ` — ${entry.detail}` : ""}`);
  console.log(`\nfixture kept for inspection: ${root}`);
  process.exitCode = 1;
} else if (!process.argv.includes("--keep")) {
  rmSync(root, { recursive: true, force: true });
}
