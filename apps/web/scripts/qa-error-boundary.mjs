#!/usr/bin/env node
/*
 * The tree's own failure boundary.
 *
 * A page that throws is caught by the framework's own error screen unless the tree holds a boundary —
 * and the framework's screen says "Application error: a server-side exception has occurred while
 * loading the page" in **every** language, on a page whose every other sentence comes from the
 * catalogue. The tree had a `not-found.tsx` in the reader's language and no boundary at all, so the
 * failure a reader meets most often was the one page in the tier that spoke none of its languages.
 *
 * Two checks, and they are the whole claim:
 *
 *  1. the tree holds a failure boundary, and it is a client component (Next.js requires one, and a
 *     server component cannot hold the retry);
 *  2. the boundary's sentences live in the catalogue, in the same namespace and the same key set in
 *     all three languages — so a reader in any of them is shown a sentence, and a key that exists in
 *     one file and not another fails here rather than falling back to English at runtime.
 *
 * Files only: no server, no browser.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const BOUNDARY = join(WEB, "app", "error.tsx");

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
};

const catalogue = (locale) => JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));

let source = "";
try {
  source = readFileSync(BOUNDARY, "utf8");
} catch {
  source = "";
}

const isClient = /^\s*["']use client["']/u.test(source);
const namespace = /useTranslations\(\s*["']([^"']+)["']\s*\)/u.exec(source)?.[1] ?? "";

check(
  "the tree holds a failure boundary, and it is a client component",
  source.length > 0 && isClient,
  source.length === 0
    ? "app/error.tsx does not exist, so a page that throws is the framework's own error screen"
    : isClient
      ? "app/error.tsx is a client component"
      : "app/error.tsx is not a client component",
);

const keySets = ["en", "zh", "zh-TW"].map((locale) => Object.keys(catalogue(locale)[namespace] ?? {}).sort().join("|"));
const same = namespace !== "" && keySets[0] !== "" && keySets.every((set) => set === keySets[0]);

check(
  "the boundary's sentences are in the catalogue, in all three languages",
  same,
  namespace === ""
    ? "app/error.tsx reads no catalogue namespace"
    : same
      ? `${namespace} holds ${keySets[0] === "" ? 0 : keySets[0].split("|").length} key(s) in each of three catalogues`
      : `${namespace} does not hold the same keys in all three catalogues`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
