#!/usr/bin/env node
/*
 * The key-drift gate's verdicts, on scratch catalogues.
 *
 * `qa-key-drift.mjs` judges two populations: same-context drift inside one namespace (identity-keyed,
 * every site in the ledger) and cross-namespace drift measured against a ceiling that may only fall.
 * This file builds a fixture per verdict and runs the **shipped** script against each through
 * `QA_I18N_WEB`, so the gate's own behaviour is what is measured rather than its code being read.
 *
 * Predictions, written before the first run:
 *   A  the real catalogues: CHECKS passed=4 total=4 failed=0, rc 0.
 *   B  one namespace's sentence given a second Chinese value: failed=1 — check 2 ("no unreviewed
 *      same-context translation drift") names the identity, and B2 holds that the red names the site.
 *      The fixture is chosen so the sentence and the key are unique to that namespace, so neither
 *      ceiling can move: a red here can only be check 2.
 *   C  a key deleted from zh: failed=1 — check 1, because the three catalogues no longer carry the same
 *      keys and every drift count below it would be under-read.
 *   D  a synthetic catalogue with 60 sentences and 60 keys shared across two namespaces, each translated
 *      differently: failed=2 — checks 3 and 4 (120 sentence issues over a ceiling of 119; 240 key issues
 *      over 107), while check 1 passes because the scan found its (same-key) population.
 *   E  three empty catalogues: failed=1 — check 1. Every drift count is zero and the ceilings are met,
 *      so without the population guard an unreadable catalogue would read as a clean one.
 *   F  one reviewed site made to agree: passed=4, and the gate prints that one ledger entry no longer
 *      drifts — shrinkage is allowed, and visible.
 *   G  A again after F: passed=4, so F's fixture did not leak into the tree.
 * Checks: 10, all green on the fixed gate.
 *
 * Files only: no server, no browser, no port.
 */

import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, cpSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const GATE = resolve(HERE, "qa-key-drift.mjs");
const REAL = resolve(HERE, "..", "messages");
const LOCALES = ["en", "zh", "zh-TW"];

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const root = mkdtempSync(join(tmpdir(), "qa-key-drift-witness-"));
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
const run = (dir) => {
  const result = spawnSync(process.execPath, [GATE], {
    env: { ...process.env, QA_I18N_WEB: dir },
    encoding: "utf8",
  });
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

const SCAN = "the scan reads three parallel catalogues and finds both populations";
const SAME = "no unreviewed same-context translation drift";
const SENTENCE = "cross-namespace sentence drift does not exceed its reviewed ceiling";
const KEY = "cross-namespace key drift does not exceed its reviewed ceiling";

// A — the real catalogues, read by the shipped gate.
const baseline = fixture("baseline");
copyReal(baseline);
const a = run(baseline);
check(
  "A the shipped gate reads the real catalogues 4/4 green",
  a.status === 0 && a.passed === 4 && a.total === 4 && a.failed === 0,
  tally(a),
);

// B — one namespace, one sentence, a second Chinese value. The sentence and the key are unique to the
// namespace, so only check 2 can move.
const drift = fixture("new-drift");
copyReal(drift);
const enB = read(drift, "en");
const zhB = read(drift, "zh");
const sentenceNamespaces = new Map();
for (const [namespace, block] of Object.entries(enB)) {
  for (const sentence of Object.values(block)) {
    if (!sentenceNamespaces.has(sentence)) sentenceNamespaces.set(sentence, new Set());
    sentenceNamespaces.get(sentence).add(namespace);
  }
}
let target = null;
for (const [namespace, block] of Object.entries(enB)) {
  const groups = new Map();
  for (const [key, sentence] of Object.entries(block)) {
    if (!groups.has(sentence)) groups.set(sentence, []);
    groups.get(sentence).push(key);
  }
  for (const [sentence, keys] of groups) {
    if (keys.length < 2 || sentenceNamespaces.get(sentence).size !== 1) continue;
    if (new Set(keys.map((key) => zhB[namespace][key])).size !== 1) continue;
    const unique = keys.find((key) => !Object.keys(enB).some((ns) => ns !== namespace && Object.hasOwn(enB[ns], key)));
    if (unique) {
      target = { namespace, keys, sentence, key: unique };
      break;
    }
  }
  if (target) break;
}
check(
  "B a same-context group unique to one namespace was found",
  target !== null,
  target ? `${target.namespace}|${target.keys.join(",")}` : "none found, so the arm would be vacuous",
);
if (target) {
  zhB[target.namespace][target.key] = "另一位译者写的不一样";
  write(drift, "zh", zhB);
  const b = run(drift);
  check(
    "B an unreviewed same-context drift reds check 2 and nothing else",
    b.status === 1 && b.failed === 1 && b.total === 4 && verdict(b.out, SAME) === "FAIL"
      && verdict(b.out, SCAN) === "PASS" && verdict(b.out, SENTENCE) === "PASS" && verdict(b.out, KEY) === "PASS",
    `${tally(b)}; ${SAME}=${verdict(b.out, SAME)}`,
  );
  check(
    "B2 the red names the site it charges",
    b.out.includes(`${target.namespace}|${[...target.keys].sort().join(",")}`),
    `${target.namespace}|${[...target.keys].sort().join(",")}`,
  );
}

// C — one key removed from one locale: the scan's own premise fails.
const nonParallel = fixture("non-parallel");
copyReal(nonParallel);
const zhC = read(nonParallel, "zh");
const removable = Object.keys(read(nonParallel, "en").common).find(
  (key) => Object.values(read(nonParallel, "en").common).filter((value) => value === read(nonParallel, "en").common[key]).length === 1,
);
delete zhC.common[removable];
write(nonParallel, "zh", zhC);
const c = run(nonParallel);
check(
  "C a locale missing a key reds check 1 and nothing else",
  c.status === 1 && c.failed === 1 && verdict(c.out, SCAN) === "FAIL" && verdict(c.out, SAME) === "PASS",
  `${tally(c)} (deleted zh.common.${removable}); ${SCAN}=${verdict(c.out, SCAN)}`,
);

// D — a synthetic catalogue past both ceilings: 60 sentences and 60 keys shared by two namespaces, each
// translated differently. The agreeing pair inside `alpha` keeps check 1's population guard satisfied.
const ceilings = fixture("ceilings");
const synthetic = { en: { alpha: { x1: "Agree", x2: "Agree" }, beta: {} }, zh: { alpha: { x1: "同意", x2: "同意" }, beta: {} }, "zh-TW": { alpha: { x1: "同意", x2: "同意" }, beta: {} } };
for (let index = 0; index < 60; index += 1) {
  const sentence = `Shared sentence ${index}`;
  synthetic.en.alpha[`k${index}`] = sentence;
  synthetic.en.beta[`k${index}`] = sentence;
  synthetic.zh.alpha[`k${index}`] = `甲 ${index}`;
  synthetic.zh.beta[`k${index}`] = `乙 ${index}`;
  synthetic["zh-TW"].alpha[`k${index}`] = `甲 ${index}`;
  synthetic["zh-TW"].beta[`k${index}`] = `乙 ${index}`;
}
for (const locale of LOCALES) write(ceilings, locale, synthetic[locale]);
const d = run(ceilings);
check(
  "D drift past both ceilings reds checks 3 and 4, not the population guard",
  d.status === 1 && d.failed === 2 && verdict(d.out, SCAN) === "PASS" && verdict(d.out, SAME) === "PASS"
    && verdict(d.out, SENTENCE) === "FAIL" && verdict(d.out, KEY) === "FAIL",
  `${tally(d)}; ${SENTENCE}=${verdict(d.out, SENTENCE)} ${KEY}=${verdict(d.out, KEY)}`,
);

// E — empty catalogues: every count is zero, so only the population guard can refuse.
const empty = fixture("empty");
for (const locale of LOCALES) write(empty, locale, {});
const e = run(empty);
check(
  "E empty catalogues red the population guard rather than passing vacuously",
  e.status === 1 && e.failed === 1 && verdict(e.out, SCAN) === "FAIL" && verdict(e.out, SAME) === "PASS",
  `${tally(e)}; ${SCAN}=${verdict(e.out, SCAN)}`,
);

// F — a reviewed site made to agree: the gate stays green and says the entry is prunable.
const shrinkage = fixture("shrinkage");
copyReal(shrinkage);
const zhF = read(shrinkage, "zh");
const twF = read(shrinkage, "zh-TW");
zhF.errors.no_such_team = zhF.errors.no_such_club;
twF.errors.no_such_team = twF.errors.no_such_club;
write(shrinkage, "zh", zhF);
write(shrinkage, "zh-TW", twF);
const f = run(shrinkage);
check(
  "F a reviewed site that stops drifting keeps the gate green",
  f.status === 0 && f.passed === 4 && f.total === 4,
  tally(f),
);
// The baseline's drifting count, read from the gate's own detail line, is what F must fall below by one.
const baselineDrift = Number(/(\d+) drifting site\(s\) of \d+ group\(s\)/.exec(a.out)?.[1]);
check(
  "F2 the gate reports one site fewer and one ledger entry it no longer needs",
  Number.isFinite(baselineDrift) && baselineDrift > 0
    && f.out.includes(`${baselineDrift - 1} drifting site(s)`) && f.out.includes("1 ledger entry no longer drift"),
  `baseline=${baselineDrift} after=${/(\d+) drifting site\(s\)/.exec(f.out)?.[1]} note=${f.out.includes("1 ledger entry no longer drift")}`,
);

// G — the fixture did not leak into the real catalogues.
const g = run(baseline);
check(
  "G the real catalogues still read 4/4 after the fixture arms",
  g.status === 0 && g.passed === 4 && g.failed === 0,
  tally(g),
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
