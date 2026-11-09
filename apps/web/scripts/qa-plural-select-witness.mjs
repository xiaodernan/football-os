#!/usr/bin/env node
/*
 * The plural/select gate's verdicts, on scratch catalogues.
 *
 * `qa-plural-select.mjs` judges a population the repository only partly has: 89 plural nodes and NO select
 * and NO selectordinal in `en.json` at 55f7ea7, three catalogues on disk, and one CLDR row per locale that
 * does not ship. Reading that gate green therefore proves nothing about the select branch, the ordinal
 * branch, the Arabic or Hebrew rows, or the floor — and its anti-blindness scan agrees with itself at zero
 * spelled and zero parsed. This file builds a fixture per verdict and runs the **shipped** gate against each
 * through `QA_I18N_WEB`, so what is measured is the gate's behaviour rather than its code being read.
 *
 * Predictions, written before the first run (2026-11-08; baseline: 3 shipped locales, en 89 / zh 25 /
 * zh-TW 25 plural nodes, 0 selects, 0 ordinals, plural floor 80, passed=7 total=7).
 *   0  the shipped gate reads the real catalogues 7/7 green.
 *   A  a complete select in all three catalogues: 7/7, and the select check reads "1 English select(s)"
 *      instead of pointing at this file — the branch fires on bytes.
 *   B  that select's `other` branch emptied in Chinese: 1 red, the select check.
 *   C  the same select translated without English's `female` case: 1 red, the select check, naming `female`.
 *   D  an English plural carrying `other` and no `one`: 1 red, the plural check, "missing categories: one".
 *   E  an English plural whose `one` branch holds nothing: 1 red, the plural check.
 *   F  a complete ordinal in all three: 7/7 and "1 English ordinal(s)" — the `ordinal` flag the walker has
 *      always extracted is read by a rule.
 *   G  that ordinal with English's `few` dropped: 1 red, the ORDINAL check, "missing categories: few". The
 *      arm that proves the ordinal table rather than the cardinal one is applied: against
 *      `en: [one, other]` the same message would pass.
 *   H  that ordinal's `other` emptied in Chinese: 1 red, the ORDINAL check.
 *   I  an `ar.json` that ships in no checkout holding 5 of CLDR's six Arabic cardinal categories: 1 red, the
 *      plural check, "missing categories: zero". The row exists in the table while the file does not.
 *   J  a `he.json` carrying an ordinal: 1 red, the ordinal check, saying this gate declares no ordinal
 *      categories for `he` — and the run still prints its tally, because a TypeError is not a verdict.
 *   K  a `fr.json` in the directory: 1 red, the discovery check, naming the file. The gate's locale list is
 *      a candidate set, and a catalogue outside it is judged by nobody while every other gate counts it.
 *   L  a message the app's parser refuses (an unclosed plural): 2 reds — the parse ledger and the scan,
 *      which reads the same message as spelled-but-not-parsed. Two readings both seeing it is the point.
 *   M  a plural written with no `other` clause: the same 2 reds, charged as `MISSING_OTHER_CLAUSE`. This is
 *      the arm that records why the completeness checks can never name a missing `other` — ICU refuses the
 *      message before they see it — so the parse ledger is the check that owns that defect, not a spare.
 *   N  every plural spelling deleted from `en.json`: 1 red, the floor alone; scan goes green at en 0/0 and
 *      the plural check goes green judging nothing, which is why a number sits beside the equality.
 *   O  the real catalogues after the fixture arms: 7/7, so no arm leaked into the tree.
 * Checks: 16, all green on the cured gate.
 *
 * Revised after the first run, which red 10 of these 16 and taught three things. (1) Two were witness
 * bugs: the detail regex stopped at the first ` — ` so it read nothing for the select check, whose name
 * carries an em-dash clause, and the expected issue texts quoted the *key* (`"deals"`) where the gate
 * quotes the *argument* (`"count"`) — fixed here, not in the gate. (2) My `en` ordinal fixture shipped
 * four categories where CLDR names five, so the gate was right to charge `many` and the fixtures F/G/H
 * were wrong; corrected, and G now drops `few` from a complete five. (3) The arm I wrote as "a Chinese
 * plural with no other branch" does not exist: `{count, plural, one {…}}` fails to parse, so the plural
 * check stayed green and the parse ledger plus the scan went red instead. That truth is now arm M, and
 * the gate's header says so; the unreachable wording it exposed (`is a ordinal`) and the discovery
 * message that printed `fr .json` were fixed in the gate, arms J and K being their witnesses.
 *
 * Files only: no server, no browser, no port.
 */

import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, cpSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const GATE = resolve(HERE, "qa-plural-select.mjs");
const REAL = resolve(HERE, "..", "messages");
const LOCALES = ["en", "zh", "zh-TW", "ar", "he", "fr"].filter((locale) => existsSync(join(REAL, `${locale}.json`)));

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const root = mkdtempSync(join(tmpdir(), "qa-plural-select-witness-"));
function copyReal(dir) {
  for (const locale of LOCALES) cpSync(join(REAL, `${locale}.json`), join(dir, "messages", `${locale}.json`));
}
const fixture = (name) => {
  const dir = join(root, name);
  mkdirSync(join(dir, "messages"), { recursive: true });
  copyReal(dir);
  return dir;
};
const read = (dir, locale) => JSON.parse(readFileSync(join(dir, "messages", `${locale}.json`), "utf8"));
const write = (dir, locale, data) =>
  writeFileSync(join(dir, "messages", `${locale}.json`), `${JSON.stringify(data, null, 2)}\n`);
/** One key of one scratch namespace, in one catalogue of one fixture. A locale the tree does not ship
 *  gets a file created here, so the gate's own discovery is what the arm exercises. */
const setKey = (dir, locale, key, value) => {
  const path = join(dir, "messages", `${locale}.json`);
  const catalogue = existsSync(path) ? read(dir, locale) : {};
  (catalogue.witness ??= {})[key] = value;
  write(dir, locale, catalogue);
};
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
  };
};
const verdict = (out, label) =>
  (out.includes(`FAIL  ${label}`) ? "FAIL" : out.includes(`PASS  ${label}`) ? "PASS" : "absent");
const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
/** The gate's own words for one check, taken from its line rather than restated here: an expectation that
 *  quotes the printed reason goes red when the reason changes, which is the point. */
const detailOf = (out, label) =>
  (new RegExp(`^(?:PASS|FAIL)\\s{2}${escape(label)}[^\\n]*? — ([^\\n]*)$`, "m").exec(out) ?? [])[1] ?? "";
const tallyOf = (r) => `rc=${r.status} passed=${r.passed} total=${r.total} failed=${r.failed}`;

const DISCOVER = "every catalogue in the directory is a locale this gate names";
const SCAN = "the walker finds every choice argument the catalogues spell";
const PARSE = "every message this gate judges parses as ICU";
const FLOOR = "the English plural population clears its vacuity floor";
const PLURAL = "every plural has required categories for each locale";
const ORDINAL = "every ordinal has required ordinal categories for each locale";
const SELECT = "every select keeps English";
const ALL = [DISCOVER, SCAN, PARSE, FLOOR, PLURAL, ORDINAL, SELECT];

const GREEN = (r) => r.status === 0 && r.passed === 7 && r.total === 7 && r.failed === 0;
/** Exactly one refusal, and it is the one the arm charges: an arm that reddens a second check has found a
 *  defect in the gate or in the arm, not a proof. */
const ONLY = (r, label) =>
  r.status === 1 && r.failed === 1 && r.total === 7 && verdict(r.out, label) === "FAIL" &&
  ALL.filter((l) => l !== label).every((l) => verdict(r.out, l) === "PASS");
/** The two readings of the population disagreeing is always a pair: scan sees spelled-but-not-parsed and
 *  the ledger names the parser's complaint. */
const BOTH_READINGS = (r) =>
  r.status === 1 && r.failed === 2 && verdict(r.out, SCAN) === "FAIL" && verdict(r.out, PARSE) === "FAIL";

// 0 — the shipped gate against the real catalogues.
const zero = run(fixture("0-baseline"));
check(
  "0 the shipped gate reads the real catalogues 7/7 green",
  GREEN(zero) && zero.out.includes("messages parsed by the app's own parser"),
  tallyOf(zero),
);

const SELECT_EN = "{gender, select, male {He signed} female {She signed} other {They signed}}";
const ORD_EN = "{place, selectordinal, one {#st} two {#nd} few {#rd} many {#th} other {#th}}";
const ORD_ZH = "{place, selectordinal, other {第 # 名}}";
const PLURAL_EN = "{count, plural, one {# deal} other {# deals}}";

// A — a complete select in every shipped catalogue: the branch fires on bytes.
const selectComplete = fixture("A-select-complete");
setKey(selectComplete, "en", "byGender", SELECT_EN);
setKey(selectComplete, "zh", "byGender", "{gender, select, male {他已签约} female {她已签约} other {他们已签约}}");
setKey(selectComplete, "zh-TW", "byGender", "{gender, select, male {他已簽約} female {她已簽約} other {他們已簽約}}");
const a = run(selectComplete);
check(
  "A a complete select in all three catalogues stays 7/7 and is counted, not assumed",
  GREEN(a) && detailOf(a.out, SELECT).startsWith("1 English select(s)"),
  `${tallyOf(a)}; ${detailOf(a.out, SELECT)}`,
);

// B — one emptied branch of that select.
const selectEmpty = fixture("B-select-empty-branch");
setKey(selectEmpty, "en", "byGender", SELECT_EN);
setKey(selectEmpty, "zh", "byGender", "{gender, select, male {他已签约} female {她已签约} other {}}");
setKey(selectEmpty, "zh-TW", "byGender", "{gender, select, male {他已簽約} female {她已簽約} other {他們已簽約}}");
const b = run(selectEmpty);
check(
  "B an emptied select branch reds the select check alone",
  ONLY(b, SELECT) && detailOf(b.out, SELECT).includes('select "gender" category "other" is empty'),
  `${tallyOf(b)}; ${detailOf(b.out, SELECT).slice(0, 160)}`,
);

// C — a translation that drops one of English's cases.
const selectCase = fixture("C-select-missing-case");
setKey(selectCase, "en", "byGender", SELECT_EN);
setKey(selectCase, "zh", "byGender", "{gender, select, male {他已签约} other {他们已签约}}");
setKey(selectCase, "zh-TW", "byGender", "{gender, select, male {他已簽約} female {她已簽約} other {他們已簽約}}");
const c = run(selectCase);
check(
  "C a select translated without one of English's cases names the case",
  ONLY(c, SELECT) && detailOf(c.out, SELECT).includes('select "gender" missing cases: female'),
  `${tallyOf(c)}; ${detailOf(c.out, SELECT).slice(0, 160)}`,
);

// D — an English plural that only ever says the fallback.
const noOne = fixture("D-plural-missing-one");
setKey(noOne, "en", "deals", "{count, plural, other {# deals}}");
const d = run(noOne);
check(
  "D a plural with no one branch reds the plural check alone",
  ONLY(d, PLURAL) && detailOf(d.out, PLURAL).includes('plural "count" missing categories: one'),
  `${tallyOf(d)}; ${detailOf(d.out, PLURAL).slice(0, 160)}`,
);

// E — an English plural whose `one` branch holds nothing.
const emptyOne = fixture("E-plural-empty-one");
setKey(emptyOne, "en", "deals", "{count, plural, one {} other {# deals}}");
const e = run(emptyOne);
check(
  "E an empty English plural branch is charged even with a complete category set",
  ONLY(e, PLURAL) && detailOf(e.out, PLURAL).includes('plural "count" category "one" is empty'),
  `${tallyOf(e)}; ${detailOf(e.out, PLURAL).slice(0, 160)}`,
);

// F — a complete ordinal: the flag the walker extracts is read by a rule.
const ordinal = fixture("F-ordinal-complete");
setKey(ordinal, "en", "finished", ORD_EN);
setKey(ordinal, "zh", "finished", ORD_ZH);
setKey(ordinal, "zh-TW", "finished", ORD_ZH);
const f = run(ordinal);
check(
  "F a complete ordinal in all three catalogues stays 7/7 and is counted",
  GREEN(f) && detailOf(f.out, ORDINAL).startsWith("1 English ordinal(s)"),
  `${tallyOf(f)}; ${detailOf(f.out, ORDINAL)}`,
);

// G — the same ordinal with English's `few` gone. Only CLDR's *ordinal* table demands `few`.
const ordinalFew = fixture("G-ordinal-missing-few");
setKey(ordinalFew, "en", "finished", "{place, selectordinal, one {#st} two {#nd} many {#th} other {#th}}");
setKey(ordinalFew, "zh", "finished", ORD_ZH);
setKey(ordinalFew, "zh-TW", "finished", ORD_ZH);
const g = run(ordinalFew);
check(
  "G an ordinal missing few reds the ORDINAL check, which only the ordinal table can ask",
  ONLY(g, ORDINAL) && detailOf(g.out, ORDINAL).includes('ordinal "place" missing categories: few'),
  `${tallyOf(g)}; ${detailOf(g.out, ORDINAL).slice(0, 160)}`,
);

// H — an ordinal whose Chinese fallback says nothing.
const ordinalEmpty = fixture("H-ordinal-empty-other");
setKey(ordinalEmpty, "en", "finished", ORD_EN);
setKey(ordinalEmpty, "zh", "finished", "{place, selectordinal, other {}}");
setKey(ordinalEmpty, "zh-TW", "finished", ORD_ZH);
const h = run(ordinalEmpty);
check(
  "H an emptied ordinal branch reds the ORDINAL check, not the plural one",
  ONLY(h, ORDINAL) && detailOf(h.out, ORDINAL).includes('zh: witness.finished: ordinal "place" category "other" is empty'),
  `${tallyOf(h)}; ${detailOf(h.out, ORDINAL).slice(0, 160)}`,
);

// I — Arabic's six categories, with no ar.json shipping in the tree.
const arabic = fixture("I-arabic-five-of-six");
setKey(arabic, "en", "deals", PLURAL_EN);
setKey(arabic, "ar", "deals", "{count, plural, one {صفقة} two {صفقتان} few {صفقات} many {صفرة} other {صفقة}}");
const i = run(arabic);
check(
  "I an Arabic plural with five of CLDR's six categories names the sixth",
  ONLY(i, PLURAL) && detailOf(i.out, PLURAL).includes('ar: witness.deals: plural "count" missing categories: zero'),
  `${tallyOf(i)}; ${detailOf(i.out, PLURAL).slice(0, 160)}`,
);

// J — Hebrew ships no ordinal table here, so an ordinal in Hebrew is refused, not judged blind.
const hebrew = fixture("J-hebrew-ordinal-without-table");
setKey(hebrew, "en", "finished", ORD_EN);
setKey(hebrew, "zh", "finished", ORD_ZH);
setKey(hebrew, "zh-TW", "finished", ORD_ZH);
setKey(hebrew, "he", "finished", "{place, selectordinal, one {ראשון} two {שני} other {ה-#}}");
const j = run(hebrew);
check(
  "J a locale whose ordinal table was never declared refuses instead of judging against undefined",
  ONLY(j, ORDINAL) && detailOf(j.out, ORDINAL).includes('needs ordinal categories and this gate declares none for "he"')
    && !j.crashed && j.passed === 6 && j.total === 7,
  `${tallyOf(j)}; ${detailOf(j.out, ORDINAL).slice(0, 190)}`,
);

// K — a catalogue in the directory that the gate's candidate list does not name. `fr` is the shipped
// sixth now, so the plane plants a language with no plural row anywhere: Esperanto. The discovery check
// must name it rather than pass it over silently.
const esperanto = fixture("K-locale-outside-the-candidate-list");
setKey(esperanto, "en", "deals", PLURAL_EN);
setKey(esperanto, "eo", "deals", "{count, plural, one {transakcio} other {transakcioj}}");
const k = run(esperanto);
check(
  "K a catalogue with no plural row is named by the discovery check rather than passed over",
  ONLY(k, DISCOVER) && detailOf(k.out, DISCOVER).includes("eo.json") && verdict(k.out, PLURAL) === "PASS",
  `${tallyOf(k)}; ${detailOf(k.out, DISCOVER).slice(0, 160)}`,
);

// L — a message the app's own parser refuses outright.
const broken = fixture("L-unparseable-message");
setKey(broken, "en", "broken", "{count, plural, one {# deal");
const l = run(broken);
check(
  "L a message the parser refuses is charged by the ledger and by the scan",
  BOTH_READINGS(l) && detailOf(l.out, PARSE).includes("en: witness.broken")
    && detailOf(l.out, SCAN).includes("spelled 1, parsed 0"),
  `${tallyOf(l)}; ${detailOf(l.out, PARSE).slice(0, 130)}`,
);

// M — the plural with no `other`: ICU refuses it, so completeness never gets to judge it.
const noOther = fixture("M-plural-without-other");
setKey(noOther, "en", "deals", "{count, plural, one {# deal}}");
const m = run(noOther);
check(
  "M a plural written without its other clause is a parse refusal, which is why no completeness rule names it",
  BOTH_READINGS(m) && detailOf(m.out, PARSE).includes("MISSING_OTHER_CLAUSE") && verdict(m.out, PLURAL) === "PASS",
  `${tallyOf(m)}; ${detailOf(m.out, PARSE).slice(0, 130)}`,
);

// N — every plural spelling deleted from the English catalogue.
const gutted = fixture("N-english-plurals-deleted");
const enAll = read(gutted, "en");
let removed = 0;
for (const [namespace, block] of Object.entries(enAll)) {
  for (const [key, value] of Object.entries(block ?? {})) {
    if (typeof value !== "string" || !/, plural,/.test(value)) continue;
    enAll[namespace][key] = "flat {count}";
    removed++;
  }
}
write(gutted, "en", enAll);
const n = run(gutted);
check(
  "N a catalogue with its plurals deleted falls through the floor, the only check that sees it",
  ONLY(n, FLOOR) && verdict(n.out, SCAN) === "PASS" && n.out.includes("en 0/0") && verdict(n.out, PLURAL) === "PASS"
    && detailOf(n.out, FLOOR).includes("en holds 0 plural node(s)"),
  `${tallyOf(n)}; ${removed} English key(s) flattened; ${detailOf(n.out, FLOOR)}`,
);

// O — nothing leaked into the tree.
const o = run(resolve(HERE, ".."));
check(
  "O the real catalogues still read 7/7 after the fixture arms",
  GREEN(o) && o.out.includes("messages parsed by the app's own parser"),
  tallyOf(o),
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
