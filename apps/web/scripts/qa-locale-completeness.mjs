#!/usr/bin/env node
/*
 * Locale completeness gate: every namespace has the same keys in all 3 locales.
 *
 * The catalogues are three parallel JSON files. A key that exists in English but not in
 * Chinese (or Traditional Chinese) is a translation gap. A key that exists in Chinese
 * but not English is a dead key (already caught by qa-unused-keys). This gate holds that
 * every namespace has identical key sets across all three locales — parity is the floor.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const LOCALES = ["en", "zh", "zh-TW"];

const catalogues = {};
for (const locale of LOCALES) {
  catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** Get all namespaces from English catalogue (the reference) */
const namespaces = Object.keys(catalogues.en);

/** Check each namespace for key parity across locales */
const parityFailures = [];

for (const namespace of namespaces) {
  const enKeys = new Set(Object.keys(catalogues.en[namespace] ?? {}));
  const zhKeys = new Set(Object.keys(catalogues.zh[namespace] ?? {}));
  const zhTwKeys = new Set(Object.keys(catalogues["zh-TW"][namespace] ?? {}));

  // Keys in English but missing in Chinese
  for (const key of enKeys) {
    if (!zhKeys.has(key)) {
      parityFailures.push(`${namespace}.${key}: missing in zh`);
    }
    if (!zhTwKeys.has(key)) {
      parityFailures.push(`${namespace}.${key}: missing in zh-TW`);
    }
  }

  // Keys in Chinese but not in English (dead keys - already caught elsewhere but flag here too)
  for (const key of zhKeys) {
    if (!enKeys.has(key)) {
      parityFailures.push(`${namespace}.${key}: extra in zh (not in en)`);
    }
  }
  for (const key of zhTwKeys) {
    if (!enKeys.has(key)) {
      parityFailures.push(`${namespace}.${key}: extra in zh-TW (not in en)`);
    }
  }
}

check(
  "every namespace has identical keys in all three locales",
  parityFailures.length === 0,
  parityFailures.length === 0
    ? `${namespaces.length} namespace(s) have full parity`
    : `${parityFailures.length} parity gap(s): ${parityFailures.slice(0, 8).join(" | ")}`,
);

/** Namespace-level summary */
const namespaceStats = {};
for (const namespace of namespaces) {
  const enCount = Object.keys(catalogues.en[namespace] ?? {}).length;
  const zhCount = Object.keys(catalogues.zh[namespace] ?? {}).length;
  const zhTwCount = Object.keys(catalogues["zh-TW"][namespace] ?? {}).length;
  namespaceStats[namespace] = { en: enCount, zh: zhCount, "zh-TW": zhTwCount };
}

console.log("\nNamespace key counts:");
for (const [ns, counts] of Object.entries(namespaceStats).sort((a, b) => b[1].en - a[1].en)) {
  const match = counts.en === counts.zh && counts.en === counts["zh-TW"] ? "✓" : "✗";
  console.log(`  ${match} ${ns}: en=${counts.en} zh=${counts.zh} zh-TW=${counts["zh-TW"]}`);
}

/** Total population check */
const totalEn = Object.values(namespaceStats).reduce((sum, c) => sum + c.en, 0);
const totalZh = Object.values(namespaceStats).reduce((sum, c) => sum + c.zh, 0);
const totalZhTw = Object.values(namespaceStats).reduce((sum, c) => sum + c["zh-TW"], 0);

check(
  "catalogue population is equal across all three locales",
  totalEn === totalZh && totalEn === totalZhTw,
  `en=${totalEn} zh=${totalZh} zh-TW=${totalZhTw}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}