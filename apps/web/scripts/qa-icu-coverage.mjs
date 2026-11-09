#!/usr/bin/env node
/*
 * ICU message coverage gate: the shipped catalogues agree, and they agree for real.
 *
 * A key that takes `{count}` in English and spells it `{n}` in Chinese prints the literal
 * {count} on the page; a key missing other in a locale renders nothing for it.
 * This gate holds the catalogue-internal half of that contract for every key in every shipped
 * catalogue: the same key asks for the same placeholders in en and in every locale the directory carries.
 *
 * The source-side half (calls → placeholders) lives in `qa-i18n-literals`, whose resolver
 * binds each read to its namespace and verifies every placeholder a call needs is supplied.
 * This file's own attempt at it was retired on 2026-11-06 (see the note further down).
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse, TYPE } from "@formatjs/icu-messageformat-parser";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

/** Discover the catalogues this gate judges, from the directory. Shipped today: en, zh, zh-TW.
 *  Anything additional — `ar.json`, `he.json` — joins with zero further edits. */
const LOCALES = ["en", "zh", "zh-TW", "ar", "he", "fr"].filter((locale) =>
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

/** Extract placeholder names from an ICU message.
 *  @formatjs parses ICU into **numeric-typed** elements and an **array** of elements; the old walker
 *  compared against strings and never descended into a choice's branches, so it collected nothing
 *  and both checks measured an empty population. This one walks the array, reads every
 *  argument-bearing type and follows every choice branch. */
function extractPlaceholders(icuMessage) {
  try {
    const ast = parse(icuMessage);
    const placeholders = new Set();
    const visit = (node) => {
      if (!node) return;
      if (Array.isArray(node)) { for (const child of node) visit(child); return; }
      if (typeof node !== "object") return;
      if (
        node.type === TYPE.argument
        || node.type === TYPE.number
        || node.type === TYPE.date
        || node.type === TYPE.time
        || node.type === TYPE.select
        || node.type === TYPE.plural
      ) {
        if (typeof node.value === "string") placeholders.add(node.value);
      }
      if (node.options) for (const option of Object.values(node.options)) visit(option?.value);
      if (Array.isArray(node.children)) visit(node.children);
      for (const key of Object.keys(node)) {
        if (key === "options" || key === "children") continue;
        if (Array.isArray(node[key])) visit(node[key]);
      }
    };
    visit(ast);
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

/** Check that every shipped catalogue declares the same placeholders for each key */
const placeholderMismatches = [];
for (const [namespace, block] of Object.entries(catalogues.en)) {
  for (const key of Object.keys(block ?? {})) {
    const path = `${namespace}.${key}`;
    const enPh = cataloguePlaceholders.en[path] ?? new Set();

    const allKeys = new Set(enPh);
    for (const locale of LOCALES) {
      if (locale === "en") continue;
      const ph = cataloguePlaceholders[locale][path] ?? new Set();
      for (const x of ph) allKeys.add(x);
    }

    for (const ph of allKeys) {
      const inEn = enPh.has(ph);
      const others = LOCALES
        .filter((locale) => locale !== "en")
        .map((locale) => (cataloguePlaceholders[locale][path] ?? new Set()).has(ph));
      if (others.some((present) => present !== inEn)) {
        const named = LOCALES
          .filter((locale) => locale !== "en")
          .map((locale) => `${locale}=${(cataloguePlaceholders[locale][path] ?? new Set()).has(ph)}`);
        placeholderMismatches.push(`${path}: placeholder "${ph}" mismatch (en=${inEn}, ${named.join(", ")})`);
      }
    }
  }
}

check(
  "every key declares identical placeholders in every shipped catalogue",
  placeholderMismatches.length === 0,
  placeholderMismatches.length === 0
    ? "all keys have matching placeholders"
    : `${placeholderMismatches.length} mismatch(es): ${placeholderMismatches.slice(0, 6).join(" | ")}`,
);

/** The source-side half of this gate was **removed on 2026-11-06**, and the reason is on record.
 *  Its call-site regex matched placeholder names with `\w+\s*:`, which also matches a ternary
 *  colon after a member expression (`analysis.data.points.length : 0`) and the argument of a
 *  **nested** `t()` call on the same line (`{ system: … }` inside `origin: board.origin_system ? t(...) : …`).
 *  Balanced-brace parsing in a regex is not a thing, so on a correct tree the gate reported
 *  failures that could not be told from real drift — and an arc whose red cannot be
 *  trusted teaches readers to ignore red. The contract the check wanted — every placeholder a
 *  key needs is supplied with it — is held, better, by `qa-i18n-literals`, whose resolver parses
 *  the source for real and binds each read to its namespace (as of 2026-11-06: 4328 key call(s)
 *  checked, green). The catalogue-internal parity check above is kept, and is now real. */

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}