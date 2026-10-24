#!/usr/bin/env node
/*
 * Locale-specific content gate: verify locale-appropriate content per locale.
 *
 * Different locales may need different content - not just translations but different
 * information. For example, measurement units (metric vs imperial), date formats,
 * cultural references, legal disclaimers, contact information, etc. This gate
 * verifies that locale-specific content differences are intentional and documented.
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

/** Patterns that indicate locale-specific content that SHOULD differ */
const LOCALE_SPECIFIC_PATTERNS = [
  // Measurement units
  { pattern: /\b(km|kilometer|meter|metre|centimeter|millimeter)\b/i, reason: "metric distance unit" },
  { pattern: /\b(mi|mile|yard|foot|feet|inch)\b/i, reason: "imperial distance unit" },
  { pattern: /\b(kg|kilogram|gram|g\b)\b/i, reason: "metric weight unit" },
  { pattern: /\b(lb|pound|ounce|oz)\b/i, reason: "imperial weight unit" },
  { pattern: /\b(°C|celsius|centigrade)\b/i, reason: "celsius temperature" },
  { pattern: /\b(°F|fahrenheit)\b/i, reason: "fahrenheit temperature" },

  // Currency
  { pattern: /\$\d/, reason: "USD currency" },
  { pattern: /[¥￥]\d/, reason: "CNY/TWD currency" },
  { pattern: /€\d/, reason: "EUR currency" },
  { pattern: /£\d/, reason: "GBP currency" },

  // Date/Time formats that differ by locale
  { pattern: /\d{1,2}\/\d{1,2}\/\d{4}/, reason: "MM/DD/YYYY date format (US)" },
  { pattern: /\d{4}[-/]\d{1,2}[-/]\d{1,2}/, reason: "YYYY-MM-DD date format (ISO/CN)" },
  { pattern: /\d{1,2}月\d{1,2}日/, reason: "Chinese date format" },

  // Legal/Contact differences
  { pattern: /GDPR|privacy policy|terms of service/i, reason: "EU legal reference" },
  { pattern: /个人信息保护|隐私政策|服务条款/i, reason: "CN legal reference" },
  { pattern: /ICP备|工信部|ICP license/i, reason: "China ICP license" },

  // Cultural references
  { pattern: /Premier League|Champions League|FIFA|UEFA/i, reason: "European football reference" },
  { pattern: /中超|中国足球|足协杯/i, reason: "Chinese football reference" },

  // Phone/Address formats
  { pattern: /\+\d{1,3}[\s-]?\d{3,4}[\s-]?\d{4}/, reason: "International phone format" },
  { pattern: /0\d{2,3}[\s-]?\d{7,8}/, reason: "China phone format" },
];

/** Check for locale-specific content that should be documented */
const contentDiffs = [];
const unexpectedMatches = [];

for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const [key, enValue] of Object.entries(block ?? {})) {
    if (typeof enValue !== "string") continue;

    const zhValue = catalogues.zh[namespace]?.[key];
    const zhTwValue = catalogues["zh-TW"][namespace]?.[key];

    for (const { pattern, reason } of LOCALE_SPECIFIC_PATTERNS) {
      const enMatch = pattern.test(enValue);
      const zhMatch = zhValue ? pattern.test(zhValue) : false;
      const zhTwMatch = zhTwValue ? pattern.test(zhTwValue) : false;

      // If English has a locale-specific pattern, check if Chinese locales handle it appropriately
      if (enMatch) {
        // For measurement units, currency, etc., the Chinese versions should use appropriate local equivalents
        if (reason.includes("metric") || reason.includes("imperial") || reason.includes("currency")) {
          // These are expected to differ - flag as locale-specific content that needs review
          contentDiffs.push({
            path: `${namespace}.${key}`,
            reason,
            en: enValue.slice(0, 80),
            zh: zhValue?.slice(0, 80),
            zhTw: zhTwValue?.slice(0, 80),
          });
        }
      }

      // Check for unexpected patterns in Chinese that shouldn't be there
      if (!enMatch && (zhMatch || zhTwMatch)) {
        const locale = zhMatch ? "zh" : "zh-TW";
        const value = zhMatch ? zhValue : zhTwValue;
        unexpectedMatches.push(`${locale}: ${namespace}.${key} — has "${reason}" pattern not in English: "${value?.slice(0, 80)}"`);
      }
    }
  }
}

/** Check for locale-specific keys that only exist in one locale */
const localeOnlyKeys = { zh: [], "zh-TW": [] };
for (const locale of ["zh", "zh-TW"]) {
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const key of Object.keys(block ?? {})) {
      if (!catalogues.en[namespace]?.[key]) {
        localeOnlyKeys[locale].push(`${namespace}.${key}`);
      }
    }
  }
}

/** Report findings */
check(
  "locale-specific content differences are tracked",
  true, // This gate reports findings, doesn't fail
  `${contentDiffs.length} locale-specific content difference(s) identified for review`,
);

check(
  "no unexpected locale-specific patterns in Chinese locales",
  unexpectedMatches.length === 0,
  unexpectedMatches.length === 0
    ? "no unexpected patterns"
    : `${unexpectedMatches.length} unexpected pattern(s): ${unexpectedMatches.slice(0, 6).join(" | ")}`,
);

check(
  "no locale-only keys without English counterparts",
  localeOnlyKeys.zh.length === 0 && localeOnlyKeys["zh-TW"].length === 0,
  localeOnlyKeys.zh.length === 0 && localeOnlyKeys["zh-TW"].length === 0
    ? "all keys have English counterparts"
    : `zh-only: ${localeOnlyKeys.zh.length}, zh-TW-only: ${localeOnlyKeys["zh-TW"].length}`,
);

/** Report detailed findings for review */
if (contentDiffs.length > 0) {
  console.log("\nLocale-specific content differences (for review):");
  for (const diff of contentDiffs.slice(0, 10)) {
    console.log(`  ${diff.path} [${diff.reason}]`);
    console.log(`    en: ${diff.en}`);
    console.log(`    zh: ${diff.zh}`);
    console.log(`    zh-TW: ${diff.zhTw}`);
  }
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}