#!/usr/bin/env node
/*
 * Catalogue size regression gate: population floor enforcement.
 *
 * The catalogue's total key count and per-namespace counts are commitments.
 * A regression (fewer keys) means translations were deleted; an increase
 * means new keys added without corresponding source calls (caught by qa-unused-keys).
 * This gate holds that the population never falls below the baseline.
 *
 * Where the baseline comes from: `--base <commit>` or `QA_BASELINE_COMMIT` (CI sets it from the
 * event that started the run), read out of `apps/web/messages/en.json` at that commit, or the
 * `.population-baseline` file that `--init-baseline` writes. The three-locale parity check is a
 * fact about the current tree alone and runs whether or not a baseline exists — the first version
 * held it inside the baseline branch, so on every clean checkout (which has no file: CI included)
 * all three checks vanished behind "No population baseline found" and the gate exited 0.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const REPO = resolve(WEB, "..", "..");
const BASELINE_FILE = join(MESSAGES, ".population-baseline");
const ZERO_COMMIT = "0".repeat(40);

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const git = (...args) => spawnSync("git", args, { cwd: REPO, encoding: "utf8" });

/** Get current catalogues */
function getCurrentCatalogues() {
  const catalogues = {};
  for (const locale of ["en", "zh", "zh-TW"]) {
    catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
  }
  return catalogues;
}

/** Compute population stats */
function computePopulation(catalogues) {
  const stats = {};
  for (const locale of ["en", "zh", "zh-TW"]) {
    const cat = catalogues[locale];
    let total = 0;
    const byNamespace = {};
    for (const [namespace, block] of Object.entries(cat)) {
      const count = Object.keys(block ?? {}).length;
      byNamespace[namespace] = count;
      total += count;
    }
    stats[locale] = { total, byNamespace };
  }
  return stats;
}

/** The baseline named for this run, before it is checked against this repository */
function requestedBaseline() {
  const at = process.argv.indexOf("--base");
  if (at !== -1) return { ref: (process.argv[at + 1] ?? "").trim(), source: "--base" };
  const env = (process.env.QA_BASELINE_COMMIT ?? "").trim();
  if (env) return { ref: env, source: "QA_BASELINE_COMMIT" };
  return null;
}

/** Get population at a specific commit */
function getPopulationAtCommit(commit) {
  try {
    const result = git("show", `${commit}:apps/web/messages/en.json`);
    if (result.status !== 0) return null;
    const cat = JSON.parse(result.stdout);
    let total = 0;
    const byNamespace = {};
    for (const [namespace, block] of Object.entries(cat)) {
      const count = Object.keys(block ?? {}).length;
      byNamespace[namespace] = count;
      total += count;
    }
    return { total, byNamespace };
  } catch {
    return null;
  }
}

/** Save current population as baseline */
function saveBaselinePopulation(population) {
  writeFileSync(BASELINE_FILE, JSON.stringify(population, null, 2));
}

/** Read the population recorded by --init-baseline, refusing anything that is not a reading */
function readBaselineFile() {
  let text;
  try {
    text = readFileSync(BASELINE_FILE, "utf8");
  } catch {
    return { error: "no baseline: pass --base <commit>, set QA_BASELINE_COMMIT, or write one with --init-baseline" };
  }
  try {
    const parsed = JSON.parse(text);
    const en = parsed?.en;
    if (!en || typeof en.total !== "number" || typeof en.byNamespace !== "object" || en.byNamespace === null) {
      return { error: `${BASELINE_FILE} is not a population reading (expected {"en":{"total":…,"byNamespace":{…}}})` };
    }
    return { population: parsed, description: BASELINE_FILE };
  } catch (error) {
    return { error: `${BASELINE_FILE} could not be parsed: ${error.message}` };
  }
}

/** Resolve the baseline population from the named commit, or from the baseline file */
function resolveBaselinePopulation() {
  const requested = requestedBaseline();
  if (!requested) return readBaselineFile();
  if (requested.ref === ZERO_COMMIT) {
    return { error: `${requested.source} names ${ZERO_COMMIT}, which git reports for a branch's first push: there is no earlier commit to compare with` };
  }
  // A shallow clone holds only the commits it fetched, so `git show <baseline>` fails there and the
  // gate would first refuse for a reason that names the clone, not the catalogue.
  if (git("rev-parse", "--is-shallow-repository").stdout.trim() === "true") {
    return { error: `this is a shallow clone, so ${requested.ref} (${requested.source}) may be missing; fetch the full history (checkout fetch-depth: 0) and rerun` };
  }
  const commit = git("rev-parse", "--verify", "--quiet", `${requested.ref}^{commit}`);
  if (commit.status !== 0) {
    return { error: `${requested.ref} (${requested.source}) is not a commit this checkout can read` };
  }
  const resolved = commit.stdout.trim();
  const population = getPopulationAtCommit(resolved);
  if (!population) {
    return { error: `apps/web/messages/en.json at ${requested.ref} could not be read or parsed` };
  }
  return { population: { en: population }, description: `${requested.source} ${resolved.slice(0, 8)}` };
}

const catalogues = getCurrentCatalogues();
const currentPop = computePopulation(catalogues);

/** CLI: --init-baseline to set current population as baseline */
if (process.argv.includes("--init-baseline")) {
  saveBaselinePopulation(currentPop);
  console.log(`Population baseline saved: ${JSON.stringify(currentPop, null, 2)}`);
  process.exit(0);
}

const baseline = resolveBaselinePopulation();

if (baseline.error) {
  console.log(`No baseline reading: ${baseline.error}`);
  check("a baseline population is resolvable", false, baseline.error);
} else {
  const base = baseline.population.en;
  console.log(`Baseline population: ${base.total} keys (${baseline.description})`);
  console.log(`Current population:  ${currentPop.en.total} keys`);

  /** Check total population never falls below baseline */
  const totalRegression = currentPop.en.total < base.total;
  const totalDiff = currentPop.en.total - base.total;

  check(
    "catalogue total population never regresses",
    !totalRegression,
    totalRegression
      ? `REGRESSION: ${base.total} -> ${currentPop.en.total} (diff: ${totalDiff})`
      : `${base.total} -> ${currentPop.en.total} (diff: ${totalDiff >= 0 ? "+" : ""}${totalDiff})`,
  );

  /** Check per-namespace populations never regress */
  const namespaceRegressions = [];
  for (const [namespace, baselineCount] of Object.entries(base.byNamespace)) {
    const currentCount = currentPop.en.byNamespace[namespace] ?? 0;
    if (currentCount < baselineCount) {
      namespaceRegressions.push(`${namespace}: ${baselineCount} -> ${currentCount}`);
    }
  }

  check(
    "per-namespace populations never regress",
    namespaceRegressions.length === 0,
    namespaceRegressions.length === 0
      ? "all namespaces at or above baseline"
      : `${namespaceRegressions.length} regression(s): ${namespaceRegressions.slice(0, 6).join(" | ")}`,
  );
}

/** Check that all three locales have same population - a fact about this tree, with or without a baseline */
const parityIssues = [];
for (const locale of ["zh", "zh-TW"]) {
  if (currentPop[locale].total !== currentPop.en.total) {
    parityIssues.push(`${locale}: ${currentPop[locale].total} vs en: ${currentPop.en.total}`);
  }
}

check(
  "all three locales have identical population",
  parityIssues.length === 0,
  parityIssues.length === 0
    ? `en=${currentPop.en.total} zh=${currentPop.zh.total} zh-TW=${currentPop["zh-TW"].total}`
    : `parity issues: ${parityIssues.join(" | ")}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
