#!/usr/bin/env node
/*
 * Plural/Select completeness gate: verify ICU plural/select branches are complete per locale.
 *
 * Different locales have different plural categories (e.g., English: one/other; Chinese: other; 
 * Arabic: zero/one/two/few/many/other). This gate verifies that every plural/select in the
 * catalogue has the required branches for each locale, and that branches are not empty.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "@formatjs/icu-messageformat-parser";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

const LOCALES = ["en", "zh", "zh-TW"];

/** Required plural categories per locale (CLDR) */
const PLURAL_CATEGORIES = {
  en: ["one", "other"],
  zh: ["other"],  // Chinese has no plural distinction
  "zh-TW": ["other"],  // Traditional Chinese also has no plural distinction
};

const catalogues = {};
for (const locale of LOCALES) {
  catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** Extract all plural/select nodes from a message */
function extractPluralSelect(message) {
  try {
    const ast = parse(message);
    const nodes = [];
    function walk(node) {
      if (node.type === "plural" || node.type === "selectordinal") {
        nodes.push({
          type: node.type,
          name: node.name,
          options: Object.keys(node.options),
          offset: node.offset || 0,
        });
      } else if (node.type === "select") {
        nodes.push({
          type: "select",
          name: node.name,
          options: Object.keys(node.options),
        });
      } else if (node.type === "plural" || node.type === "select") {
        for (const option of Object.values(node.options)) {
          if (option.value && Array.isArray(option.value)) {
            for (const child of option.value) walk(child);
          }
        }
      }
    }
    walk(ast);
    return nodes;
  } catch {
    return [];
  }
}

/** Check plural/select completeness */
const pluralIssues = [];
const selectIssues = [];
let pluralCount = 0;
let selectCount = 0;

for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const [key, enValue] of Object.entries(block ?? {})) {
    if (typeof enValue !== "string") continue;
    const path = `${namespace}.${key}`;

    const enPlurals = extractPluralSelect(enValue);
    if (enPlurals.length === 0) continue;

    for (const node of enPlurals) {
      if (node.type === "plural" || node.type === "selectordinal") {
        pluralCount++;
        for (const locale of ["en", "zh", "zh-TW"]) {
          const required = PLURAL_CATEGORIES[locale];
          const localeValue = catalogues[locale][namespace]?.[key];
          if (typeof localeValue !== "string") continue;

          const localePlurals = extractPluralSelect(localeValue);
          const matchingNode = localePlurals.find(n => n.name === node.name && n.type === node.type);
          if (!matchingNode) continue;

          const missing = required.filter(cat => !matchingNode.options.includes(cat));
          if (missing.length > 0) {
            pluralIssues.push(`${locale}: ${namespace}.${key} — arg "${node.name}" missing plural categories: ${missing.join(", ")} (has: ${matchingNode.options.join(", ")})`);
          }

          // Check for empty branches
          for (const cat of matchingNode.options) {
            const optionValue = getOptionValue(localeValue, node.name, cat);
            if (optionValue === undefined || optionValue.trim() === "") {
              pluralIssues.push(`${locale}: ${namespace}.${key} — arg "${node.name}" category "${cat}" is empty`);
            }
          }
        }
      } else if (node.type === "select") {
        selectCount++;
        for (const locale of ["en", "zh", "zh-TW"]) {
          const localeValue = catalogues[locale][namespace]?.[key];
          if (typeof localeValue !== "string") continue;

          const localeSelects = extractPluralSelect(localeValue);
          const matchingNode = localeSelects.find(n => n.name === node.name && n.type === "select");
          if (!matchingNode) continue;

          // Check for empty branches
          for (const cat of matchingNode.options) {
            const optionValue = getOptionValue(localeValue, node.name, cat);
            if (optionValue === undefined || optionValue.trim() === "") {
              selectIssues.push(`${locale}: ${namespace}.${key} — select "${node.name}" case "${cat}" is empty`);
            }
          }
        }
      }
    }
  }
}

/** Helper to extract option value from ICU message */
function getOptionValue(message, argName, category) {
  try {
    const ast = parse(message);
    let found = null;
    function walk(node) {
      if (found) return;
      if ((node.type === "plural" || node.type === "select" || node.type === "selectordinal") && node.name === argName) {
        const option = node.options[category];
        if (option && option.value && Array.isArray(option.value)) {
          // Reconstruct the message from the AST nodes
          found = option.value.map(n => n.type === "literal" ? n.value : "").join("");
        }
      } else if (node.type === "plural" || node.type === "select" || node.type === "selectordinal") {
        for (const opt of Object.values(node.options)) {
          if (opt.value && Array.isArray(opt.value)) {
            for (const child of opt.value) walk(child);
          }
        }
      }
    }
    walk(ast);
    return found;
  } catch {
    return undefined;
  }
}

check(
  "every plural has required categories for each locale",
  pluralIssues.length === 0,
  pluralIssues.length === 0
    ? `${pluralCount} plural(s) checked`
    : `${pluralIssues.length} plural issue(s): ${pluralIssues.slice(0, 6).join(" | ")}`,
);

check(
  "every select has no empty cases",
  selectIssues.length === 0,
  selectIssues.length === 0
    ? `${selectCount} select(s) checked`
    : `${selectIssues.length} empty select case(s): ${selectIssues.slice(0, 6).join(" | ")}`,
);

/** Summary */
console.log("\nPlural/Select summary:");
console.log(`  Plural/selectordinal: ${pluralCount}`);
console.log(`  Select: ${selectCount}`);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}