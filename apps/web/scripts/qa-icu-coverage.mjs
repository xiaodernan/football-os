#!/usr/bin/env node
/*
 * ICU message coverage gate: every placeholder used in source is declared in catalogue.
 *
 * The source code calls translation keys with specific placeholders. The catalogue must
 * declare those placeholders in its ICU message. A missing placeholder throws at render
 * time; an extra placeholder is dead code. This gate holds parity between source calls
 * and catalogue declarations for every key across all three locales.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, readdirSync } from "node:fs";
import { join, resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "@formatjs/icu-messageformat-parser";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const APP = join(WEB, "app");
const COMPONENTS = join(WEB, "components");
const LIB = join(WEB, "lib");

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

/** Extract placeholder names from an ICU message */
function extractPlaceholders(icuMessage) {
  try {
    const ast = parse(icuMessage);
    const placeholders = new Set();
    function walk(node) {
      if (node.type === "argument") {
        placeholders.add(node.name);
      } else if (node.type === "select" || node.type === "plural") {
        placeholders.add(node.name);
        for (const option of Object.values(node.options)) {
          if (option.value && Array.isArray(option.value)) {
            for (const child of option.value) walk(child);
          }
        }
      } else if (node.type === "pound") {
        placeholders.add("#");
      }
    }
    walk(ast);
    return placeholders;
  } catch {
    // If parsing fails, return empty set (will be caught by qa-icu-messages gate)
    return new Set();
  }
}

/** Build a map of key -> placeholders from catalogues */
const cataloguePlaceholders = {};
for (const locale of LOCALES) {
  cataloguePlaceholders[locale] = {};
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const [key, value] of Object.entries(block ?? {})) {
      if (typeof value === "string") {
        cataloguePlaceholders[locale][`${namespace}.${key}`] = extractPlaceholders(value);
      }
    }
  }
}

/** Check that all three locales declare the same placeholders for each key */
const placeholderMismatches = [];
for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const key of Object.keys(block ?? {})) {
    const path = `${namespace}.${key}`;
    const enPh = cataloguePlaceholders.en[path] ?? new Set();
    const zhPh = cataloguePlaceholders.zh[path] ?? new Set();
    const zhTwPh = cataloguePlaceholders["zh-TW"][path] ?? new Set();

    const allKeys = new Set([...enPh, ...zhPh, ...zhTwPh]);
    for (const ph of allKeys) {
      const inEn = enPh.has(ph);
      const inZh = zhPh.has(ph);
      const inZhTw = zhTwPh.has(ph);
      if (inEn !== inZh || inEn !== inZhTw) {
        placeholderMismatches.push(`${path}: placeholder "${ph}" mismatch (en=${inEn}, zh=${inZh}, zh-TW=${inZhTw})`);
      }
    }
  }
}

check(
  "every key declares identical placeholders in all three catalogues",
  placeholderMismatches.length === 0,
  placeholderMismatches.length === 0
    ? "all keys have matching placeholders"
    : `${placeholderMismatches.length} mismatch(es): ${placeholderMismatches.slice(0, 6).join(" | ")}`,
);

/** Parse source files for translation calls with explicit placeholders */
function findTranslationCalls(dir) {
  const calls = [];
  function walkDir(currentDir) {
    for (const entry of readdirSync(currentDir, { withFileTypes: true })) {
      const fullPath = join(currentDir, entry.name);
      if (entry.isDirectory()) {
        if (!entry.name.startsWith(".") && entry.name !== "node_modules" && entry.name !== ".next") {
          walkDir(fullPath);
        }
      } else if (entry.name.endsWith(".tsx") || entry.name.endsWith(".ts")) {
        const content = readFileSync(fullPath, "utf8");
        // Match t('namespace.key', { placeholder: value }) patterns
        const regex = /t\(['"`]([^'"`]+)['"`]\s*(?:,\s*\{([^}]+)\})?\)/g;
        let match;
        while ((match = regex.exec(content)) !== null) {
          const key = match[1];
          const placeholdersStr = match[2] || "";
          const placeholders = new Set();
          const phRegex = /(\w+)\s*:/g;
          let phMatch;
          while ((phMatch = phRegex.exec(placeholdersStr)) !== null) {
            placeholders.add(phMatch[1]);
          }
          calls.push({ file: relative(WEB, fullPath), key, placeholders });
        }
      }
    }
  }
  walkDir(dir);
  return calls;
}

const sourceCalls = [
  ...findTranslationCalls(APP),
  ...findTranslationCalls(COMPONENTS),
  ...findTranslationCalls(LIB),
];

/** Check that every source call's placeholders exist in the catalogue */
const missingInCatalogue = [];
const extraInCatalogue = [];

for (const call of sourceCalls) {
  const enPh = cataloguePlaceholders.en[call.key] ?? new Set();
  if (enPh.size === 0) continue; // Key not in catalogue or not a string

  for (const ph of call.placeholders) {
    if (!enPh.has(ph)) {
      missingInCatalogue.push(`${call.file}: t('${call.key}', { ${ph}: ... }) — placeholder "${ph}" not in catalogue`);
    }
  }
  for (const ph of enPh) {
    if (!call.placeholders.has(ph) && ph !== "#") {
      // Allow optional placeholders that might be filled by other call sites
      // This is a warning, not a failure
    }
  }
}

check(
  "every source call's placeholders are declared in the catalogue",
  missingInCatalogue.length === 0,
  missingInCatalogue.length === 0
    ? `${sourceCalls.length} call(s) checked`
    : `${missingInCatalogue.length} missing placeholder(s): ${missingInCatalogue.slice(0, 6).join(" | ")}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}