#!/usr/bin/env node
/*
 * The API-strings gate's verdicts, on scratch catalogues and source trees.
 *
 * `qa-api-strings.mjs` judges three things, each independently:
 *
 *   1. no file in the web tier's source holds a copy of a sentence the `errors` catalogue owns;
 *   2. the localiser is called on both paths a refusal arrives through (server's own read and the browser's proxy);
 *   3. every refusal code's sentence is translated in every non-English catalogue.
 *
 * This file takes each arm apart by building exactly one tree per verdict and running the **shipped** script
 * on it, so the gate's own behaviour is what is measured, rather than its code being read. Predictions, written
 * before the first run against the real tree (43 namespaces, refuses≠3 checks / checks 1-3):
 *
 *   0  the real tree: 3/3 green.
 *   A  a file in the web tier carrying an exact copy of a catalogue-owned refusal sentence: failed=1 — check 1
 *      names the file and line holding the copy. The sentence is taken from the real catalogue, so the
 *      intervention cannot time-travel the fixture backwards.
 *   B  `lib/refusals.ts` deleted from the fixture tree: failed=1 — check 2 names the missing door
 *      (both the server's read and the browser's proxy fail-existence first). Every other check stays green,
 *      which is the control that holds the arm as narrow as the verdict.
 *   C  one Chinese catalogue's `errors` namespace given a value byte-identical to English: failed=1 — check 3
 *      names the code. The tree keeps its values and keys, so the catalogue population can't move.
 *   D  the real tree after the arms: 3/3, so no fixture leaked into the tree.
 *
 * Arable shape — no server, no browser, no port.
 */

import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, cpSync, existsSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const GATE = resolve(HERE, "qa-api-strings.mjs");
const REAL = resolve(HERE, "..");
const MESSAGES = resolve(REAL, "messages");
const LOCALES = ["en", "zh", "zh-TW", "ar", "he"].filter((locale) =>
  existsSync(join(MESSAGES, `${locale}.json`)),
);
const WEB = REAL;

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const root = mkdtempSync(join(tmpdir(), "qa-api-strings-witness-"));
const fixture = (name) => {
  const dir = join(root, name);
  mkdirSync(join(dir, "messages"), { recursive: true });
  mkdirSync(join(dir, "lib"), { recursive: true });
  mkdirSync(join(dir, "app", "api", "v1", "[...path]"), { recursive: true });
  mkdirSync(join(dir, "src-a11y"), { recursive: true });
  return dir;
};
const copyWeb = (dir) => {
  // Copy the source tree the gate actually walks. The gate reads .ts/.tsx/.mjs/.js files but skips
  // node_modules, messages (done above), .git, .next, and other heavy ignore-areas; the fixture does
  // the same.
  const SKIP = new Set(["node_modules", ".next", ".git", "out", "dist", ".vercel", ".turbo", ".cache"]);
  const copy = (src, dst) => {
    for (const entry of readdirSync(src, { withFileTypes: true })) {
      const name = entry.name;
      if (SKIP.has(name) || name.startsWith(".next")) continue;
      const from = join(src, name);
      const to = join(dst, name);
      if (entry.isDirectory()) { mkdirSync(to, { recursive: true }); copy(from, to); }
      else cpSync(from, to);
    }
  };
  copy(WEB, dir);
};
const read = (dir, locale) => JSON.parse(readFileSync(join(dir, "messages", `${locale}.json`), "utf8"));
const write = (dir, locale, data) => writeFileSync(join(dir, "messages", `${locale}.json`), `${JSON.stringify(data, null, 2)}\n`);
const run = (dir) => {
  const env = { ...process.env, QA_I18N_WEB: dir };
  const result = spawnSync(process.execPath, [GATE], { env, encoding: "utf8" });
  const out = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  const tally = /CHECKS passed=(\d+) total=(\d+) failed=(\d+)/.exec(out);
  return {
    status: result.status,
    out,
    passed: tally ? Number(tally[1]) : null,
    total: tally ? Number(tally[2]) : null,
  };
};
const unmount = () => { try { rmSync(root, { recursive: true, force: true }); } catch {} };

process.on("exit", unmount);

// 0 — the real catalogues, read by the shipped gate.
{
  const zero = run(WEB);
  check(
    "0 the shipped gate reads the real catalogues green",
    zero.status === 0 && zero.passed === 3 && zero.total === 3,
    `passed=${zero.passed} total=${zero.total} status=${zero.status}`,
  );
}

// A — a copy of a catalogue-owned refusal sentence inside the source tree.
{
  const arm = fixture("copy-of-sentence");
  copyWeb(arm);
  const english = JSON.parse(readFileSync(join(arm, "messages", "en.json"), "utf8"));
  const sentence = String(english.errors[Object.keys(english.errors).find((k) => String(english.errors[k]).length >= 15)] ?? "");
  const file = join(arm, "lib", "owned-by-web.ts");
  writeFileSync(file, `// the sentence: ${sentence}\nexport const x = "${sentence}";\n`);
  const a = run(arm);
  const hit = a.out.includes("holds a copy of errors.");
  check(
    "A a copy of a catalogue-owned refusal sentence reds check 1",
    a.status === 1 && hit,
    `status=${a.status} hit=${hit} out_first=${a.out.split("\n").find((line) => line.startsWith("FAIL")) ?? "(none)"}`,
  );
}

// B — the localiser's door is missing.
{
  const arm = fixture("missing-localiser");
  copyWeb(arm);
  rmSync(join(arm, "lib", "refusals.ts"), { force: true });
  const b = run(arm);
  const doctrine = b.out.includes("does not export localiseRefusal") || b.out.includes("lib/refusals.ts does not exist");
  check(
    "B a missing localiser door reds check 2",
    b.status === 1 && doctrine,
    `status=${b.status} doctrine=${doctrine}`,
  );
}

// C — a refusal sentence left in English in zh.json — check 3 names it.
{
  const arm = fixture("refusal-left-untranslated");
  copyWeb(arm);
  const en = JSON.parse(readFileSync(join(arm, "messages", "en.json"), "utf8"));
  const zh = JSON.parse(readFileSync(join(arm, "messages", "zh.json"), "utf8"));
  const target = Object.keys(zh.errors ?? {}).find((k) => (zh.errors[k] ?? "") !== "" && typeof zh.errors[k] === "string");
  zh.errors[target] = en.errors[target];
  write(arm, "zh", zh);
  const c = run(arm);
  const named = c.out.includes(`zh: errors.${target} is the English sentence`);
  check(
    "C a real refusal sentence left in English reds check 3 naming the code",
    c.status === 1 && named,
    `status=${c.status} named=${named}`,
  );
}

// D — the real tree after the arms: 3/3 green, so nothing leaked out.
{
  const zero = run(WEB);
  check(
    "D the real catalogues still read green after the arms",
    zero.status === 0 && zero.passed === 3 && zero.total === 3,
    `passed=${zero.passed} total=${zero.total} status=${zero.status}`,
  );
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
