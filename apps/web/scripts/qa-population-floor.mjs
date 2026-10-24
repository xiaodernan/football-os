#!/usr/bin/env node
/*
 * Catalogue size regression gate: population floor enforcement.
 *
 * The catalogue's total key count and per-namespace counts are commitments.
 * A regression (fewer keys) means translations were deleted; an increase
 * means new keys added without corresponding source calls (caught by qa-unused-keys).
 * This gate holds that the population never falls below the committed floor.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const LOCALES = ["en", "zh", "zh-TW"];

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

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

/** Get baseline population from .gate-baseline */
function getBaselinePopulation() {
  try {
    const baselineFile = join(MESSAGES, ".population-baseline");
    return JSON.parse(readFileSync(baselineFile, "utf8"));
  } catch {
    return null;
  }
}

/** Save current population as baseline */
function saveBaselinePopulation(population) {
  const baselineFile = join(MESSAGES, ".population-baseline");
  writeFileSync(baselineFile, JSON.stringify(population, null, 2));
}

/** Get population at a specific commit */
function getPopulationAtCommit(commit) {
  try {
    const result = spawnSync("git", ["show", `${commit}:apps/web/messages/en.json`], {
      cwd: resolve(join(MESSAGES, "..", "..")),
      encoding: "utf8",
    });
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

const catalogues = getCurrentCatalogues();
const currentPop = computePopulation(catalogues);

/** CLI: --init-baseline to set current population as baseline */
if (process.argv.includes("--init-baseline")) {
  saveBaselinePopulation(currentPop);
  console.log(`Population baseline saved: ${JSON.stringify(currentPop, null, 2)}`);
  process.exit(0);
}

const baselinePop = getBaselinePopulation();

if (!baselinePop) {
  console.log("No population baseline found. Run with --init-baseline to set initial baseline.");
  console.log("Current population:", JSON.stringify(currentPop, null, 2));
  process.exitCode = 0;
} else {
  console.log(`Baseline population: ${baselinePop.en.total} keys`);
  console.log(`Current population:  ${currentPop.en.total} keys`);

  /** Check total population never falls below baseline */
  const totalRegression = currentPop.en.total < baselinePop.en.total;
  const totalDiff = currentPop.en.total - baselinePop.en.total;

  check(
    "catalogue total population never regresses",
    !totalRegression,
    totalRegression
      ? `REGRESSION: ${baselinePop.en.total} -> ${currentPop.en.total} (diff: ${totalDiff})`
      : `${baselinePop.en.total} -> ${currentPop.en.total} (diff: ${totalDiff >= 0 ? "+" : ""}${totalDiff})`,
  );

  /** Check per-namespace populations never regress */
  const namespaceRegressions = [];
  for (const [namespace, baselineCount] of Object.entries(baselinePop.en.byNamespace)) {
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

  /** Check that all three locales have same population */
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
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}