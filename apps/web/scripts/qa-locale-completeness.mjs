#!/usr/bin/env node
/*
 * Locale completeness gate: every namespace has the same keys in every shipped locale.
 *
 * The catalogues are N parallel JSON files (three today — `en`, `zh`, `zh-TW`). A key that exists in
 * English but not in another locale is a translation gap. A key that exists in another locale but not
 * in English is a dead key (already caught by qa-unused-keys). The gate holds parity across the
 * shipped locales — and whichever locales the directory names next: drop `ar.json` in, and the gate
 * judges four instead of three, with zero edits to this file.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

/** Discover the catalogues present. Shipped today: en, zh, zh-TW. Anything dropped in
 *  additionally — `ar.json`, `he.json` — is judged by the same rules. */
const LOCALES = ["en", "zh", "zh-TW", "ar", "he"].filter((locale) =>
  existsSync(join(MESSAGES, `${locale}.json`)),
);

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

/** Check each namespace for key parity across every discovered locale */
const parityFailures = [];
const others = LOCALES.filter((locale) => locale !== "en");

for (const namespace of namespaces) {
  const enKeys = new Set(Object.keys(catalogues.en[namespace] ?? {}));

  for (const locale of others) {
    const keys = new Set(Object.keys(catalogues[locale][namespace] ?? {}));
    for (const key of enKeys) {
      if (!keys.has(key)) parityFailures.push(`${namespace}.${key}: missing in ${locale}`);
    }
    for (const key of keys) {
      if (!enKeys.has(key)) parityFailures.push(`${namespace}.${key}: extra in ${locale} (not in en)`);
    }
  }
}

check(
  "every namespace has identical keys in every locale the directory carries",
  parityFailures.length === 0,
  parityFailures.length === 0
    ? `${namespaces.length} namespace(s) have full parity across ${LOCALES.join(", ")}`
    : `${parityFailures.length} parity gap(s): ${parityFailures.slice(0, 8).join(" | ")}`,
);

/** Namespace-level summary */
const namespaceStats = {};
for (const namespace of namespaces) {
  namespaceStats[namespace] = Object.fromEntries(
    LOCALES.map((locale) => [
      locale,
      Object.keys(catalogues[locale][namespace] ?? {}).length,
    ]),
  );
}

console.log("\nNamespace key counts:");
for (const [ns, counts] of Object.entries(namespaceStats).sort((a, b) => b[1].en - a[1].en)) {
  const marks = LOCALES.map((locale) => `${locale}=${counts[locale]}`).join(" ");
  const match = LOCALES.every((locale) => counts[locale] === counts.en) ? "✓" : "✗";
  console.log(`  ${match} ${ns}: ${marks}`);
}

/** Total population check */
const totals = Object.fromEntries(
  LOCALES.map((locale) => [
    locale,
    Object.values(namespaceStats).reduce((sum, c) => sum + c[locale], 0),
  ]),
);
const reference = totals.en;
const populationOk = LOCALES.every((locale) => totals[locale] === reference);

check(
  "catalogue population is equal across every shipped locale",
  populationOk,
  LOCALES.map((locale) => `${locale}=${totals[locale]}`).join(" "),
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
