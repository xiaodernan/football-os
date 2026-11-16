#!/usr/bin/env node
/*
 * The shared-key gate's verdicts, on scratch catalogues.
 *
 * `qa-shared-keys.mjs` judges one population — the keys whose English sentence is the same in every namespace
 * that holds them — and asks two questions of it: a translation that differs across those namespaces must be a
 * named divergence, and the population itself is a ceiling that may only fall. This file builds a fixture per
 * verdict and runs the **shipped** script against each through `QA_I18N_WEB`, so the gate's behaviour is what is
 * measured rather than its code being read.
 *
 * Predictions, written before the first run (2026-10-26; baseline: 40 namespaces, 98 value-shared rows,
 * 136 name-only rows, 9 named divergences, passed=4 total=4).
 * Revised 2026-11-06 for the live surface: 43 namespaces, 101 value-shared rows, 151 name-only rows,
 * 10 named divergences (`live|nav,settings` added), the ceiling ratcheted 234 → 240 on the same review;
 * the fixture arms below were re-measured against that baseline:
 *   0  the shipped gate reads the real catalogues 4/4 green (asserted with the live divergence count, never a pin).
 * Revised 2026-11-16 — the population has fallen legitimately since (honest improvements removed duplicate
 * bindings): today the shipped gate prints 9 named divergences and 228 bindings against the same 240 review
 * ceiling, so the arms must derive from the tree instead of pinning:
 *   0  arm 0 asserts the phrase with any count — a count that legitimately falls must not turn affirmation into a lie.
 *   B  the marker is added to as many namespaces as the gate's OWN `VALUE_CEILING` requires (read from GATE's source,
 *      crossed by the bindings the real catalogues print) — twelve copies no longer exceed a 240 ceiling at 228.
 *   A  one namespace's Chinese value for a value-shared key given a unique string: failed=1 — check 2 names
 *      `adding|scout,training`. The row keeps its English, so neither the ledger nor the ceiling can move.
 *   B  the marker copies: ceiling reds, drift stays green, bindings print past 240.
 *   C  a named divergence aligned away (`simulate.home` → the nav's 首页): failed=1 — check 3, which refuses a
 *      ledger that no longer holds; the row itself leaves the divergence list, so check 2 stays green.
 *   D  three empty catalogues: failed=2 — check 1 (the population guard) and check 3 (stale entries ledgered).
 *      Check 2 is green at zero rows, which is precisely why the guard exists rather than why the arm is vacuous.
 *   E  a shared key NAME with a different English value (`career.asking`): green 4/4 — name-only sharing is not a
 *      finding, which is the control that keeps the gate from drifting back to counting names.
 *   F  the real catalogues after the fixture arms: 4/4, so no arm leaked into the tree.
 *   (The 2026-11-06 draft of arm B pinned "twelve copies" — a 240-ceiling contract; the cure keeps the arm's
 *    claim — the ceiling can red when the population crosses it — by deriving the crossing, not the number.)
 * Checks: 8, all green on the fixed gate.
 *
 * Files only: no server, no browser, no port.
 */

import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, cpSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const GATE = resolve(HERE, "qa-shared-keys.mjs");
const REAL = resolve(HERE, "..", "messages");
const LOCALES = ["en", "zh", "zh-TW", "ar", "he", "fr"].filter((locale) =>
  existsSync(join(REAL, `${locale}.json`)),
);

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const root = mkdtempSync(join(tmpdir(), "qa-shared-keys-witness-"));
const fixture = (name) => {
  const dir = join(root, name);
  mkdirSync(join(dir, "messages"), { recursive: true });
  return dir;
};
const copyReal = (dir) => {
  for (const locale of LOCALES) cpSync(join(REAL, `${locale}.json`), join(dir, "messages", `${locale}.json`));
};
const read = (dir, locale) => JSON.parse(readFileSync(join(dir, "messages", `${locale}.json`), "utf8"));
const write = (dir, locale, data) => writeFileSync(join(dir, "messages", `${locale}.json`), `${JSON.stringify(data, null, 2)}\n`);
const run = (dir, unset) => {
  const env = { ...process.env, QA_I18N_WEB: dir };
  if (unset) delete env.QA_I18N_WEB;
  const result = spawnSync(process.execPath, [GATE], { env, encoding: "utf8" });
  const out = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  const tally = /CHECKS passed=(\d+) total=(\d+) failed=(\d+)/.exec(out);
  return {
    status: result.status,
    out,
    passed: tally ? Number(tally[1]) : null,
    total: tally ? Number(tally[2]) : null,
    failed: tally ? Number(tally[3]) : null,
  };
};
const verdict = (out, label) => (out.includes(`FAIL  ${label}`) ? "FAIL" : out.includes(`PASS  ${label}`) ? "PASS" : "absent");
const tally = (r) => `rc=${r.status} passed=${r.passed} total=${r.total} failed=${r.failed}`;
// The name-only census is counted against the run's own baseline rather than a pinned literal: the arm's claim is
// that it adds exactly one row, and a catalogue that grows legitimately must not turn that claim into a stale number.
const nameOnlyRows = (out) => Number(/(\d+) key name\(s\) are shared while their values differ/u.exec(out)?.[1] ?? -1);

const SCAN = "the scan reads three catalogues and finds both populations";
const DRIFT = "no unreviewed cross-namespace translation drift";
const STALE = "every named divergence still diverges";
const CEILING = "the duplicated-sentence population does not exceed its reviewed ceiling";

// 0 — the real catalogues, read by the shipped gate.
const baseline = fixture("baseline");
copyReal(baseline);
const zero = run(baseline);
check(
  "0 the shipped gate reads the real catalogues 4/4 green",
  zero.status === 0 && zero.passed === 4 && zero.total === 4 && zero.failed === 0
    && /\d+ of the value-shared rows are translated differently/.test(zero.out),
  tally(zero),
);

// A — a value-shared row translated a second way, with no ledger entry.
const drift = fixture("new-divergence");
copyReal(drift);
const zhA = read(drift, "zh");
const twA = read(drift, "zh-TW");
zhA.training.adding = "正在加入…";
twA.training.adding = "正在加入…";
write(drift, "zh", zhA);
write(drift, "zh-TW", twA);
const a = run(drift);
check(
  "A an unreviewed cross-namespace divergence reds check 2 and nothing else",
  a.status === 1 && a.failed === 1 && a.total === 4 && verdict(a.out, DRIFT) === "FAIL"
    && verdict(a.out, SCAN) === "PASS" && verdict(a.out, STALE) === "PASS" && verdict(a.out, CEILING) === "PASS",
  `${tally(a)}; ${DRIFT}=${verdict(a.out, DRIFT)}`,
);
check(
  "A2 the red names the row it charges",
  a.out.includes("adding|scout,training"),
  "adding|scout,training",
);

// B — a never-before-seen marker sentence, one copy per namespace, added until the population crosses the gate's
//     OWN reviewed ceiling. The crossing point is derived at run time from (a) the `VALUE_CEILING` the gate
//     declares and (b) the bindings the real catalogues print — so a legitimately smaller real population can
//     never turn "twelve copies do not cross a 240 ceiling" into a false red, nor a bigger one into a quiet pass.
//     The drift check must stay green all the way; the ceiling may red.
const duplicate = fixture("duplicate-sentence");
copyReal(duplicate);
const gateSource = readFileSync(GATE, "utf8");
const ceilingMatch = /VALUE_CEILING = (\d+)/.exec(gateSource);
const ceiling = ceilingMatch ? Number(ceilingMatch[1]) : null;
const baselineBindings = Number(/(\d+) binding\(s\) across/.exec(zero.out)?.[1] ?? -1);
const realEnglish = JSON.parse(readFileSync(join(REAL, "en.json"), "utf8"));
const namespaceNames = Object.keys(realEnglish);
const need = ceiling !== null && baselineBindings >= 0 ? ceiling - baselineBindings + 1 : -1;
if (need > 0 && need <= namespaceNames.length) {
  const targetNamespaces = namespaceNames.slice().sort().slice(0, need);
  for (const [locale, sentence] of [["en", "Viremont Fifty Duplicate Marker"], ["zh", "维里蒙特五十重复标记"], ["zh-TW", "維里蒙特五十重複標記"]]) {
    const catalogue = read(duplicate, locale);
    for (const ns of targetNamespaces) {
      catalogue[ns].thDuplicateMarker = sentence;
    }
    write(duplicate, locale, catalogue);
  }
}
const b = run(duplicate);
const over = Number(/(\d+) binding\(s\) across/.exec(b.out)?.[1] ?? 0);
check(
  "B marker copies red the ceiling and not the drift check",
  b.status === 1 && b.failed === 1 && verdict(b.out, CEILING) === "FAIL"
    && verdict(b.out, DRIFT) === "PASS" && over > (ceiling ?? 240) && need > 0 && need <= namespaceNames.length,
  `${tally(b)}; ${CEILING}=${verdict(b.out, CEILING)} bindings=${over} ceiling=${ceiling} need=${need}`,
);

// C — a ledger entry that no longer holds: the named row is aligned away.
const aligned = fixture("stale-ledger");
copyReal(aligned);
const zhC = read(aligned, "zh");
const twC = read(aligned, "zh-TW");
zhC.simulate.home = "首页";
twC.simulate.home = "首頁";
write(aligned, "zh", zhC);
write(aligned, "zh-TW", twC);
const c = run(aligned);
check(
  "C a named divergence that stops diverging reds the ledger check",
  c.status === 1 && c.failed === 1 && verdict(c.out, STALE) === "FAIL"
    && verdict(c.out, DRIFT) === "PASS" && c.out.includes("no longer divergent: home|nav,simulate"),
  `${tally(c)}; ${STALE}=${verdict(c.out, STALE)}`,
);

// D — empty catalogues: zero rows, so only the guard and the now-stale ledger can refuse.
const empty = fixture("empty");
for (const locale of LOCALES) write(empty, locale, {});
const d = run(empty);
check(
  "D empty catalogues red the population guard, not a vacuous drift check",
  d.status === 1 && d.failed === 2 && verdict(d.out, SCAN) === "FAIL" && verdict(d.out, STALE) === "FAIL"
    && verdict(d.out, DRIFT) === "PASS" && verdict(d.out, CEILING) === "PASS",
  `${tally(d)}; ${SCAN}=${verdict(d.out, SCAN)} ${DRIFT}=${verdict(d.out, DRIFT)}`,
);

// E — a shared name with a different value is not a finding.
const nameOnly = fixture("name-only");
copyReal(nameOnly);
for (const [locale, sentence] of [["en", "A different question"], ["zh", "另一个问题"], ["zh-TW", "另一個問題"]]) {
  const catalogue = read(nameOnly, locale);
  catalogue.career.asking = sentence;
  write(nameOnly, locale, catalogue);
}
const e = run(nameOnly);
check(
  "E a shared key name with a different sentence stays green",
  e.status === 0 && e.passed === 4 && e.total === 4 && nameOnlyRows(e.out) === nameOnlyRows(zero.out) + 1,
  tally(e),
);

// F — the fixture did not leak into the real catalogues.
const f = run(null, true);
check(
  "F the real catalogues still read 4/4 after the fixture arms",
  f.status === 0 && f.passed === 4 && f.failed === 0,
  tally(f),
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
