#!/usr/bin/env node
/*
 * Locale fallback gate: every key present in the English catalogue must also
 * be present (and non-empty) in the Chinese catalogues.
 *
 * next-intl falls back to English when a key is absent from a locale's
 * catalogue. A Chinese reader then sees an English sentence on a supposedly
 * Chinese page — the same defect the copy gate was born to close, but on the
 * catalogue side rather than the source side.
 *
 * The gate reads all three catalogues and reports every key that exists in
 * en.json but is missing, null, or empty-string in zh.json or zh-TW.json.
 * The floor is zero: every key the English catalogue holds must be translated
 * in both Chinese locales.
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

/** Flatten a catalogue into a map of "namespace.key" -> value */
function flatten(cat) {
  const out = {};
  for (const [namespace, block] of Object.entries(cat ?? {})) {
    if (block && typeof block === "object" && !Array.isArray(block)) {
      for (const [key, value] of Object.entries(block)) {
        out[`${namespace}.${key}`] = value;
      }
    }
  }
  return out;
}

const en = flatten(catalogues.en);
const zh = flatten(catalogues.zh);
const zhTw = flatten(catalogues["zh-TW"]);

const missingInZh = [];
const missingInZhTw = [];

for (const [fullKey, enValue] of Object.entries(en)) {
  if (typeof enValue !== "string") continue;

  const zhValue = zh[fullKey];
  if (zhValue === undefined || zhValue === null || zhValue === "") {
    missingInZh.push(`${fullKey} (en: "${enValue}")`);
  }

  const zhTwValue = zhTw[fullKey];
  if (zhTwValue === undefined || zhTwValue === null || zhTwValue === "") {
    missingInZhTw.push(`${fullKey} (en: "${enValue}")`);
  }
}

check(
  "every key in en.json has a non-empty value in zh.json",
  missingInZh.length === 0,
  missingInZh.length === 0
    ? `${Object.keys(en).length} key(s) all present in zh`
    : `${missingInZh.length} key(s) missing or empty in zh: ${missingInZh.slice(0, 5).join(", ")}${missingInZh.length > 5 ? " ..." : ""}`
);

check(
  "every key in en.json has a non-empty value in zh-TW.json",
  missingInZhTw.length === 0,
  missingInZhTw.length === 0
    ? `${Object.keys(en).length} key(s) all present in zh-TW`
    : `${missingInZhTw.length} key(s) missing or empty in zh-TW: ${missingInZhTw.slice(0, 5).join(", ")}${missingInZhTw.length > 5 ? " ..." : ""}`
);

const totalMissing = missingInZh.length + missingInZhTw.length;
const floor = 0;

check(
  "locale fallback floor — no key missing or empty in any Chinese locale",
  totalMissing <= floor,
  `${totalMissing} key(s) missing or empty against a floor of ${floor}`
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}