#!/usr/bin/env node
/*
 * Key drift detection gate: detect when the same key has diverging meanings across locales.
 *
 * A key that has the same English sentence across multiple namespaces but different Chinese
 * translations in each namespace is a "semantic drift" - the key name is the same but the
 * meaning has diverged. This gate compares translations of identical English sentences
 * across namespaces and flags inconsistencies.
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

/** Build a map of English sentence -> { namespace, key, translations } */
const sentenceMap = new Map();

for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const [key, enValue] of Object.entries(block ?? {})) {
    if (typeof enValue !== "string") continue;
    if (!sentenceMap.has(enValue)) {
      sentenceMap.set(enValue, []);
    }
    sentenceMap.get(enValue).push({
      namespace,
      key,
      zh: catalogues.zh[namespace]?.[key],
      "zh-TW": catalogues["zh-TW"][namespace]?.[key],
    });
  }
}

/** Find sentences that appear in multiple namespaces */
const multiNamespaceSentences = [];
for (const [sentence, entries] of sentenceMap) {
  const namespaces = new Set(entries.map(e => e.namespace));
  if (namespaces.size > 1) {
    multiNamespaceSentences.push({ sentence, entries });
  }
}

/** Check for translation drift: same English sentence, different Chinese translations */
const driftIssues = [];

for (const { sentence, entries } of multiNamespaceSentences) {
  const zhTranslations = new Set(entries.map(e => e.zh).filter(Boolean));
  const zhTwTranslations = new Set(entries.map(e => e["zh-TW"]).filter(Boolean));

  // If Chinese translations differ across namespaces, it's drift
  if (zhTranslations.size > 1) {
    const details = entries.map(e => `${e.namespace}.${e.key}: "${e.zh}"`).join(" | ");
    driftIssues.push(`zh: "${sentence.slice(0, 50)}" has ${zhTranslations.size} different translations — ${details}`);
  }

  if (zhTwTranslations.size > 1) {
    const details = entries.map(e => `${e.namespace}.${e.key}: "${e["zh-TW"]}"`).join(" | ");
    driftIssues.push(`zh-TW: "${sentence.slice(0, 50)}" has ${zhTwTranslations.size} different translations — ${details}`);
  }
}

check(
  "identical English sentences have consistent translations across namespaces",
  driftIssues.length === 0,
  driftIssues.length === 0
    ? `${multiNamespaceSentences.length} sentence(s) shared across namespaces, all consistent`
    : `${driftIssues.length} drift issue(s): ${driftIssues.slice(0, 4).join(" | ")}`,
);

/** Also check: same key in different namespaces, same English, different translations */
const keyDriftIssues = [];

for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const [key, enValue] of Object.entries(block ?? {})) {
    if (typeof enValue !== "string") continue;

    // Find other namespaces with same key
    const otherNamespaces = Object.keys(catalogues.en).filter(ns => 
      ns !== namespace && catalogues.en[ns]?.[key] === enValue
    );

    if (otherNamespaces.length > 0) {
      const allNamespaces = [namespace, ...otherNamespaces];
      const zhTranslations = new Set();
      const zhTwTranslations = new Set();

      for (const ns of allNamespaces) {
        const zh = catalogues.zh[ns]?.[key];
        const zhTw = catalogues["zh-TW"][ns]?.[key];
        if (zh) zhTranslations.add(zh);
        if (zhTw) zhTwTranslations.add(zhTw);
      }

      if (zhTranslations.size > 1) {
        keyDriftIssues.push(`zh: key "${key}" (in ${allNamespaces.join(", ")}) has ${zhTranslations.size} different translations`);
      }
      if (zhTwTranslations.size > 1) {
        keyDriftIssues.push(`zh-TW: key "${key}" (in ${allNamespaces.join(", ")}) has ${zhTwTranslations.size} different translations`);
      }
    }
  }
}

check(
  "same key across namespaces has consistent translations",
  keyDriftIssues.length === 0,
  keyDriftIssues.length === 0
    ? `no key drift across namespaces`
    : `${keyDriftIssues.length} key drift issue(s): ${keyDriftIssues.slice(0, 4).join(" | ")}`,
);

/** Summary */
console.log("\nDrift detection summary:");
console.log(`  English sentences shared across namespaces: ${multiNamespaceSentences.length}`);
console.log(`  Keys shared across namespaces with same English: checked`);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}