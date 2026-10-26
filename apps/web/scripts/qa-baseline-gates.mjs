#!/usr/bin/env node
/*
 * Baseline-gate behaviour gate: runs the translation-freshness and population-floor gates against a scratch
 * repository whose only differences are a stale key, a deleted key and a broken parity, and holds each verdict.
 *
 * Why this file exists. Both gates compared their catalogues with a baseline they read from an untracked file, and
 * when that file was absent they printed `CHECKS passed=0 total=0 failed=0` and exited 0 — which is what a clean
 * checkout looks like, CI included. The floor gate also held its three-locale parity check inside the baseline
 * branch, so a tree whose English catalogue had a key the Chinese ones lacked passed that gate without the parity
 * claim being evaluated at all. Through the freshness gate, a baseline commit the clone could not read (a depth-1
 * checkout) made it rewrite the baseline to HEAD and pass: a shallow clone certified its own stale keys.
 *
 * This gate is the behavioural witness for the repaired contract: red when a translation lags, red when a key is
 * deleted, red when the locales disagree even with no baseline, and red — as a refusal, never a silent pass — when
 * no baseline can be read. It builds every case in `mkdtemp`, with commits that differ from the baseline by exactly
 * the one edit each case names, and it needs no server, no browser and no port: git and the two scripts only.
 *
 * Predictions (written before the first run): 16 checks, all green.
 *   A/A   freshness rc 0 total=2 — a baseline equal to HEAD still compares instead of "passing trivially".
 *   B/A   freshness rc 0 total=2;   zh-stale/A rc 1 passed=1 failed=1, Simplified red and Traditional green.
 *   zh-TW-stale/A the mirror;       both-stale/A rc 1 passed=0 failed=2.
 *   file  zh-stale with `.gate-baseline`=A is the same red as zh-stale/A.
 *   deadbeef rc 1 total=1 and the file is still absent;  none rc 1 total=1 naming the three ways to supply one.
 *   shallow clone rc 1 total=1 naming the clone (the CI shape).
 *   floor B/A rc 0 total=3;  deleted/A rc 1 passed=1 failed=2 (total and namespace, parity green).
 *   floor parity-break with no baseline rc 1 total=2 failed=2 (refusal + parity);  with base A rc 1 total=3 failed=1.
 *   floor deadbeef rc 1 total=2 failed=1 (the refusal; parity still runs and passes);  --init-baseline then no env
 *   rc 0 total=3. The floor's minimum is two checks because parity is evaluated unconditionally; freshness's is one.
 *
 * Files only: no server, no browser, no port.
 */

import { mkdtempSync, mkdirSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(HERE, "..");
const FRESHNESS = join(HERE, "qa-translation-freshness.mjs");
const FLOOR = join(HERE, "qa-population-floor.mjs");

const ROOT = mkdtempSync(join(tmpdir(), "baseline-gates-"));
const MESSAGES = join(ROOT, "apps/web/messages");
mkdirSync(MESSAGES, { recursive: true });
const NO_HOOKS = join(ROOT, "no-hooks");
mkdirSync(NO_HOOKS);

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

// The machine's global git config may install hooks that run the real project's linters inside a fixture, and may
// sign commits; both are irrelevant here and one of them cannot work without a GPG key.
const GIT_CONFIG = ["-c", `core.hooksPath=${NO_HOOKS}`, "-c", "commit.gpgsign=false", "-c", "user.email=gate@example.com", "-c", "user.name=gate"];
const git = (...args) => {
  const result = spawnSync("git", [...GIT_CONFIG, ...args], { cwd: ROOT, encoding: "utf8" });
  if (result.status !== 0) throw new Error(`git ${args.join(" ")} failed: ${(result.stderr ?? "").trim()}`);
  return (result.stdout ?? "").trim();
};

const write = (locale, catalogues) => writeFileSync(join(MESSAGES, `${locale}.json`), `${JSON.stringify(catalogues, null, 2)}\n`);
const writeAll = (all) => { for (const [locale, blocks] of Object.entries(all)) write(locale, blocks); };
const commit = (message) => { git("add", "-A"); git("commit", "-qm", message); return git("rev-parse", "HEAD"); };

const stray = () => {
  rmSync(join(MESSAGES, ".gate-baseline"), { force: true });
  rmSync(join(MESSAGES, ".population-baseline"), { force: true });
};
const at = (rev) => { git("checkout", "-q", rev); stray(); };

const run = (script, base) => {
  const env = { ...process.env, QA_I18N_WEB: join(ROOT, "apps/web") };
  delete env.QA_BASELINE_COMMIT;
  if (base) env.QA_BASELINE_COMMIT = base;
  const result = spawnSync(process.execPath, [script], { cwd: WEB, env, encoding: "utf8" });
  return { status: result.status, out: `${result.stdout ?? ""}${result.stderr ?? ""}` };
};

const textOf = (observation) => (typeof observation === "string" ? observation : observation.out);
const tally = (observation) => {
  const match = textOf(observation).match(/CHECKS passed=(\d+) total=(\d+) failed=(\d+)/);
  return match ? { passed: Number(match[1]), total: Number(match[2]), failed: Number(match[3]) } : null;
};
const verdictLine = (observation, needle) => textOf(observation).split(/\r?\n/).find((line) => line.includes(needle)) ?? "";
const said = (observation, needle) => textOf(observation).includes(needle);

git("init", "-q", "--initial-branch=main");

const translated = {
  en: { common: { a: "Alpha", b: "Beta" }, home: { title: "Home" } },
  zh: { common: { a: "甲", b: "乙" }, home: { title: "首页" } },
  "zh-TW": { common: { a: "甲", b: "乙" }, home: { title: "首頁" } },
};
writeAll(translated);
const A = commit("A: every catalogue translated");

const followed = {
  en: { common: { a: "Alpha two", b: "Beta" }, home: { title: "Home" } },
  zh: { common: { a: "甲二", b: "乙" }, home: { title: "首页" } },
  "zh-TW": { common: { a: "甲二", b: "乙" }, home: { title: "首頁" } },
};
writeAll(followed);
const B = commit("B: English changed and both translations followed");

// Only zh lags: English moved and Traditional Chinese followed, Simplified did not.
git("checkout", "-q", "-b", "side-zh", B);
writeAll({
  en: { common: { a: "Alpha two", b: "Beta" }, home: { title: "Home two" } },
  zh: { common: { a: "甲二", b: "乙" }, home: { title: "首页" } },
  "zh-TW": { common: { a: "甲二", b: "乙" }, home: { title: "首頁二" } },
});
const ZH_STALE = commit("English moved, Traditional followed, Simplified lagged");

// Only zh-TW lags: the mirror image.
git("checkout", "-q", "-b", "side-zhtw", B);
writeAll({
  en: { common: { a: "Alpha two", b: "Beta" }, home: { title: "Home two" } },
  zh: { common: { a: "甲二", b: "乙" }, home: { title: "首页二" } },
  "zh-TW": { common: { a: "甲二", b: "乙" }, home: { title: "首頁" } },
});
const ZHTW_STALE = commit("English moved, Simplified followed, Traditional lagged");

// Both lag.
git("checkout", "-q", "-b", "side-both", B);
writeAll({
  en: { common: { a: "Alpha two", b: "Beta" }, home: { title: "Home two" } },
  zh: { common: { a: "甲二", b: "乙" }, home: { title: "首页" } },
  "zh-TW": { common: { a: "甲二", b: "乙" }, home: { title: "首頁" } },
});
const BOTH_STALE = commit("English moved and neither translation followed");

// On main: a key deleted from all three locales, then a key added to English only.
git("checkout", "-q", "main");
writeAll({
  en: { common: { a: "Alpha two" }, home: { title: "Home" } },
  zh: { common: { a: "甲二" }, home: { title: "首页" } },
  "zh-TW": { common: { a: "甲二" }, home: { title: "首頁" } },
});
const DELETED = commit("common.b deleted from all three locales");
writeAll({
  en: { common: { a: "Alpha two", c: "Gamma" }, home: { title: "Home" } },
  zh: { common: { a: "甲二" }, home: { title: "首页" } },
  "zh-TW": { common: { a: "甲二" }, home: { title: "首頁" } },
});
const PARITY = commit("common.c added to English only");

const commits = [A, B, ZH_STALE, ZHTW_STALE, BOTH_STALE, DELETED, PARITY];
const present = commits.filter((sha) => spawnSync("git", [...GIT_CONFIG, "cat-file", "-e", `${sha}^{commit}`], { cwd: ROOT }).status === 0);
check(
  "1 the fixture holds seven commits, one edit apart from the baseline each case names",
  present.length === commits.length,
  `${present.length}/${commits.length} commits present`,
);

// Freshness: the baseline commit equals HEAD. The first version's "No changes since baseline. Gate passes trivially."
// branch reported zero checks; comparing identical catalogues is cheap and honest, so it runs now.
at(A);
let out = run(FRESHNESS, A);
let count = tally(out);
check(
  "2 freshness with a baseline equal to HEAD still compares (rc 0, two checks)",
  out.status === 0 && count?.total === 2 && count.failed === 0,
  `rc=${out.status} tally=${JSON.stringify(count)}`,
);

at(B);
out = run(FRESHNESS, A);
count = tally(out);
check(
  "3 freshness is green when both translations followed the English change (rc 0, two checks)",
  out.status === 0 && count?.total === 2 && count.failed === 0,
  `rc=${out.status} tally=${JSON.stringify(count)}`,
);

at(ZH_STALE);
out = run(FRESHNESS, A);
count = tally(out);
check(
  "4 freshness charges Simplified when only it lagged (rc 1, failed=1, Traditional green)",
  out.status === 1 && count?.failed === 1 && verdictLine(out, "no stale Simplified").startsWith("FAIL") && verdictLine(out, "no stale Traditional").startsWith("PASS"),
  `rc=${out.status} tally=${JSON.stringify(count)} | ${verdictLine(out, "no stale Simplified")}`,
);

at(ZHTW_STALE);
out = run(FRESHNESS, A);
count = tally(out);
check(
  "5 freshness charges Traditional when only it lagged (rc 1, failed=1, Simplified green)",
  out.status === 1 && count?.failed === 1 && verdictLine(out, "no stale Traditional").startsWith("FAIL") && verdictLine(out, "no stale Simplified").startsWith("PASS"),
  `rc=${out.status} tally=${JSON.stringify(count)} | ${verdictLine(out, "no stale Traditional")}`,
);

at(BOTH_STALE);
out = run(FRESHNESS, A);
count = tally(out);
check(
  "6 freshness charges both locales when neither followed (rc 1, failed=2)",
  out.status === 1 && count?.failed === 2,
  `rc=${out.status} tally=${JSON.stringify(count)}`,
);

at(ZH_STALE);
writeFileSync(join(MESSAGES, ".gate-baseline"), A);
out = run(FRESHNESS);
count = tally(out);
check(
  "7 freshness still reads the baseline file --init-baseline writes (same red, no env)",
  out.status === 1 && count?.failed === 1 && verdictLine(out, "no stale Simplified").startsWith("FAIL"),
  `rc=${out.status} tally=${JSON.stringify(count)}`,
);

at(ZH_STALE);
out = run(FRESHNESS, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef");
count = tally(out);
check(
  "8 freshness refuses a baseline commit it cannot read, and does not rewrite the baseline (the reset bug)",
  out.status === 1 && count?.total === 1 && said(out, "is not a commit this checkout can read") && !existsSync(join(MESSAGES, ".gate-baseline")),
  `rc=${out.status} tally=${JSON.stringify(count)} baseline-written=${existsSync(join(MESSAGES, ".gate-baseline"))}`,
);

out = run(FRESHNESS);
count = tally(out);
check(
  "9 freshness refuses when no baseline is supplied at all (rc 1, one failing check)",
  out.status === 1 && count?.total === 1 && count.failed === 1 && said(out, "no baseline commit"),
  `rc=${out.status} tally=${JSON.stringify(count)}`,
);

const SHALLOW = join(ROOT, "..", `baseline-gates-shallow-${process.pid}`);
const clone = spawnSync("git", ["clone", "-q", "--depth", "1", pathToFileURL(ROOT).href, SHALLOW], { encoding: "utf8" });
if (clone.status === 0) {
  const env = { ...process.env, QA_I18N_WEB: join(SHALLOW, "apps/web"), QA_BASELINE_COMMIT: A };
  const result = spawnSync(process.execPath, [FRESHNESS], { cwd: WEB, env, encoding: "utf8" });
  const shallowOut = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  check(
    "10 freshness refuses inside a depth-1 clone, naming the clone rather than passing on a truncated history",
    result.status === 1 && tally(shallowOut)?.total === 1 && said(shallowOut, "shallow clone"),
    `rc=${result.status} | ${verdictLine(shallowOut, "a baseline commit is resolvable")}`,
  );
  rmSync(SHALLOW, { recursive: true, force: true });
} else {
  check("10 freshness refuses inside a depth-1 clone", false, `the fixture clone failed: ${(clone.stderr ?? "").trim()}`);
}

// Population floor.
at(B);
out = run(FLOOR, A);
count = tally(out);
check(
  "11 floor is green against a baseline it reads from a commit (rc 0, three checks)",
  out.status === 0 && count?.total === 3 && count.failed === 0,
  `rc=${out.status} tally=${JSON.stringify(count)}`,
);

at(DELETED);
out = run(FLOOR, A);
count = tally(out);
check(
  "12 floor charges a deleted key twice: total and its namespace (rc 1, failed=2, parity green)",
  out.status === 1 && count?.failed === 2 && verdictLine(out, "catalogue total population never regresses").startsWith("FAIL") && verdictLine(out, "per-namespace populations never regress").includes("common: 2 -> 1") && verdictLine(out, "all three locales have identical population").startsWith("PASS"),
  `rc=${out.status} tally=${JSON.stringify(count)} | ${verdictLine(out, "per-namespace populations never regress")}`,
);

at(PARITY);
out = run(FLOOR);
count = tally(out);
check(
  "13 floor evaluates locale parity with no baseline at all (rc 1: the refusal and the parity break)",
  out.status === 1 && count?.total === 2 && count.failed === 2 && said(out, "a baseline population is resolvable") && said(out, "parity issues"),
  `rc=${out.status} tally=${JSON.stringify(count)} | ${verdictLine(out, "all three locales have identical population")}`,
);

out = run(FLOOR, A);
count = tally(out);
check(
  "14 floor charges locale parity beside a resolvable baseline (rc 1, failure is parity alone)",
  out.status === 1 && count?.total === 3 && count.failed === 1 && verdictLine(out, "all three locales have identical population").startsWith("FAIL"),
  `rc=${out.status} tally=${JSON.stringify(count)}`,
);

at(B);
out = run(FLOOR, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef");
count = tally(out);
check(
  "15 floor refuses a baseline commit it cannot read (rc 1: the refusal fails, parity still runs and passes)",
  out.status === 1 && count?.total === 2 && count.failed === 1 && said(out, "is not a commit this checkout can read") && verdictLine(out, "all three locales have identical population").startsWith("PASS"),
  `rc=${out.status} tally=${JSON.stringify(count)}`,
);

at(B);
const init = spawnSync(process.execPath, [FLOOR, "--init-baseline"], { cwd: WEB, env: { ...process.env, QA_I18N_WEB: join(ROOT, "apps/web") }, encoding: "utf8" });
const wroteFile = existsSync(join(MESSAGES, ".population-baseline"));
out = run(FLOOR);
count = tally(out);
check(
  "16 --init-baseline writes a reading the next run accepts (rc 0, three checks)",
  init.status === 0 && wroteFile && out.status === 0 && count?.total === 3,
  `init rc=${init.status} file=${wroteFile} rc=${out.status} tally=${JSON.stringify(count)}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  console.log(`\nfixture kept at ${ROOT}`);
  process.exitCode = 1;
} else if (!process.argv.includes("--keep")) {
  rmSync(ROOT, { recursive: true, force: true });
}
