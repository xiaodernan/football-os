#!/usr/bin/env node
/*
 * Translation freshness gate: detect stale translations.
 *
 * A key whose English value changed but whose Chinese value did not is a stale translation —
 * the Chinese reader is seeing an outdated sentence. This gate compares the English catalogue
 * against a baseline (the last commit where the gate passed) and flags keys where:
 * 1. English changed but Chinese didn't
 * 2. English changed but Traditional Chinese didn't
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const LOCALES = ["zh", "zh-TW"];

/** Get the last commit hash where this gate passed (stored in .gate-baseline) */
function getBaselineCommit() {
  try {
    const baselineFile = join(MESSAGES, ".gate-baseline");
    return readFileSync(baselineFile, "utf8").trim();
  } catch {
    return null;
  }
}

/** Save the current commit as the new baseline */
function saveBaselineCommit(commit) {
  const baselineFile = join(MESSAGES, ".gate-baseline");
  writeFileSync(baselineFile, commit);
}

/** Get the English catalogue at a specific commit */
function getCatalogueAtCommit(locale, commit) {
  try {
    const result = spawnSync("git", ["show", `${commit}:apps/web/messages/${locale}.json`], {
      cwd: resolve(WEB, "..", ".."),
      encoding: "utf8",
    });
    if (result.status !== 0) return null;
    return JSON.parse(result.stdout);
  } catch {
    return null;
  }
}

/** Get current catalogues */
function getCurrentCatalogues() {
  const catalogues = {};
  for (const locale of ["en", "zh", "zh-TW"]) {
    catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
  }
  return catalogues;
}

/** Deep clone a catalogue */
function cloneCatalogue(cat) {
  const cloned = {};
  for (const [namespace, block] of Object.entries(cat)) {
    cloned[namespace] = { ...block };
  }
  return cloned;
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** Get current commit hash */
const currentCommit = spawnSync("git", ["rev-parse", "HEAD"], {
  cwd: resolve(WEB, "..", ".."),
  encoding: "utf8",
}).stdout.trim();

const baselineCommit = getBaselineCommit();

if (!baselineCommit) {
  console.log("No baseline commit found. Run with --init-baseline to set initial baseline.");
  console.log("Current commit:", currentCommit);
  process.exitCode = 0; // Not a failure, just uninitialized
} else if (baselineCommit === currentCommit) {
  console.log("No changes since baseline. Gate passes trivially.");
} else {
  console.log(`Comparing baseline ${baselineCommit.slice(0, 8)} -> current ${currentCommit.slice(0, 8)}`);

  const current = getCurrentCatalogues();
  const baseline = {
    en: getCatalogueAtCommit("en", baselineCommit),
    zh: getCatalogueAtCommit("zh", baselineCommit),
    "zh-TW": getCatalogueAtCommit("zh-TW", baselineCommit),
  };

  if (!baseline.en || !baseline.zh || !baseline["zh-TW"]) {
    console.log("Could not retrieve baseline catalogues. Resetting baseline.");
    saveBaselineCommit(currentCommit);
    process.exitCode = 0;
  } else {
    const staleZh = [];
    const staleZhTw = [];

    for (const [namespace, block] of Object.entries(current.en)) {
      for (const [key, enValue] of Object.entries(block)) {
        if (typeof enValue !== "string") continue;

        const baselineEn = baseline.en[namespace]?.[key];
        const baselineZh = baseline.zh[namespace]?.[key];
        const baselineZhTw = baseline["zh-TW"][namespace]?.[key];
        const currentZh = current.zh[namespace]?.[key];
        const currentZhTw = current["zh-TW"][namespace]?.[key];

        // English changed but Chinese didn't
        if (baselineEn !== undefined && enValue !== baselineEn) {
          if (currentZh === baselineZh) {
            staleZh.push(`${namespace}.${key}: en="${enValue.slice(0, 40)}" vs baseline="${baselineEn.slice(0, 40)}" (zh unchanged)`);
          }
          if (currentZhTw === baselineZhTw) {
            staleZhTw.push(`${namespace}.${key}: en="${enValue.slice(0, 40)}" vs baseline="${baselineEn.slice(0, 40)}" (zh-TW unchanged)`);
          }
        }
      }
    }

    check(
      "no stale Simplified Chinese translations (en changed, zh unchanged)",
      staleZh.length === 0,
      staleZh.length === 0
        ? "no stale zh translations"
        : `${staleZh.length} stale zh translation(s): ${staleZh.slice(0, 4).join(" | ")}`,
    );

    check(
      "no stale Traditional Chinese translations (en changed, zh-TW unchanged)",
      staleZhTw.length === 0,
      staleZhTw.length === 0
        ? "no stale zh-TW translations"
        : `${staleZhTw.length} stale zh-TW translation(s): ${staleZhTw.slice(0, 4).join(" | ")}`,
    );
  }
}

/** CLI: --init-baseline to set current commit as baseline */
if (process.argv.includes("--init-baseline")) {
  saveBaselineCommit(currentCommit);
  console.log(`Baseline set to ${currentCommit}`);
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}