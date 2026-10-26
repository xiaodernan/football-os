#!/usr/bin/env node
/*
 * Translation freshness gate: detect stale translations.
 *
 * A key whose English value changed but whose Chinese value did not is a stale translation —
 * the Chinese reader is seeing an outdated sentence. This gate compares the English catalogue
 * against a baseline (the commit the change started from) and flags keys where:
 * 1. English changed but Chinese didn't
 * 2. English changed but Traditional Chinese didn't
 *
 * Where the baseline comes from: `--base <commit>`, or `QA_BASELINE_COMMIT` (CI sets it from the
 * event that started the run: the commit a push replaced, or a pull request's base), or the
 * `.gate-baseline` file that `--init-baseline` writes. A gate with nothing to compare against has
 * checked nothing, so this one refuses instead of passing: the first version reported zero checks
 * and exited 0 whenever that file was absent — which is every clean checkout, including CI's — and
 * when a commit could not be read it rewrote the file and passed, so a shallow clone reported
 * success and made the stale keys its own new baseline.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const REPO = resolve(WEB, "..", "..");
const BASELINE_FILE = join(MESSAGES, ".gate-baseline");
const ZERO_COMMIT = "0".repeat(40);

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const git = (...args) => spawnSync("git", args, { cwd: REPO, encoding: "utf8" });

/** Get the baseline commit recorded by --init-baseline, if this checkout has one */
function readBaselineFile() {
  try {
    return readFileSync(BASELINE_FILE, "utf8").trim() || null;
  } catch {
    return null;
  }
}

/** Save the current commit as the new baseline */
function saveBaselineCommit(commit) {
  writeFileSync(BASELINE_FILE, commit);
}

/** The baseline named for this run, before it is checked against this repository */
function requestedBaseline() {
  const at = process.argv.indexOf("--base");
  if (at !== -1) return { ref: (process.argv[at + 1] ?? "").trim(), source: "--base" };
  const env = (process.env.QA_BASELINE_COMMIT ?? "").trim();
  if (env) return { ref: env, source: "QA_BASELINE_COMMIT" };
  const file = readBaselineFile();
  return file ? { ref: file, source: BASELINE_FILE } : null;
}

/** Resolve the requested baseline to a commit that this checkout can actually read */
function resolveBaseline() {
  const requested = requestedBaseline();
  if (!requested) {
    return { error: "no baseline commit: pass --base <commit>, set QA_BASELINE_COMMIT, or write one with --init-baseline" };
  }
  if (requested.ref === ZERO_COMMIT) {
    return { error: `${requested.source} names ${ZERO_COMMIT}, which git reports for a branch's first push: there is no earlier commit to compare with` };
  }
  // A shallow clone answers merge-base from the commits it fetched, so a truncated history would
  // read as a legitimate baseline. Refusing here is the only way to tell a short baseline from a
  // real one, and it is the defect this gate had in CI (a depth-1 checkout whose `git show` failed).
  if (git("rev-parse", "--is-shallow-repository").stdout.trim() === "true") {
    return { error: `this is a shallow clone, so ${requested.ref} (${requested.source}) may be missing and a comparison would read a truncated history; fetch the full history (checkout fetch-depth: 0) and rerun` };
  }
  const commit = git("rev-parse", "--verify", "--quiet", `${requested.ref}^{commit}`);
  if (commit.status !== 0) {
    return { error: `${requested.ref} (${requested.source}) is not a commit this checkout can read` };
  }
  const resolved = commit.stdout.trim();
  const base = git("merge-base", "HEAD", resolved);
  if (base.status !== 0) {
    return { error: `${requested.ref} shares no ancestor with HEAD, so nothing below it describes this tree` };
  }
  return { commit: base.stdout.trim(), source: requested.source };
}

/** Get a catalogue at a specific commit */
function getCatalogueAtCommit(locale, commit) {
  try {
    const result = git("show", `${commit}:apps/web/messages/${locale}.json`);
    if (result.status !== 0) return null;
    return JSON.parse(result.stdout);
  } catch {
    return null;
  }
}

/** Get current catalogues */
function getCurrentCatalogues() {
  const catalogues = {};
  for (const locale of ["en", "zh", "zh-TW"]) {
    catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
  }
  return catalogues;
}

/** Get current commit hash */
const currentCommit = (git("rev-parse", "HEAD").stdout ?? "").trim();

/** CLI: --init-baseline writes this checkout's HEAD as the baseline */
if (process.argv.includes("--init-baseline")) {
  saveBaselineCommit(currentCommit);
  console.log(`Baseline set to ${currentCommit}`);
}

const baseline = resolveBaseline();

if (baseline.error) {
  console.log(`No comparison ran: ${baseline.error}`);
  check("a baseline commit is resolvable", false, baseline.error);
} else {
  console.log(`Comparing baseline ${baseline.commit.slice(0, 8)} (${baseline.source}) -> current ${currentCommit.slice(0, 8)}`);

  const current = getCurrentCatalogues();
  const base = {
    en: getCatalogueAtCommit("en", baseline.commit),
    zh: getCatalogueAtCommit("zh", baseline.commit),
    "zh-TW": getCatalogueAtCommit("zh-TW", baseline.commit),
  };
  const missing = ["en", "zh", "zh-TW"].filter((locale) => !base[locale]);

  if (missing.length) {
    check(
      "the baseline commit supplies all three catalogues",
      false,
      `${missing.join(", ")} could not be read at ${baseline.commit.slice(0, 8)}; nothing was compared and the baseline was left as it was`,
    );
  } else {
    const staleZh = [];
    const staleZhTw = [];

    for (const [namespace, block] of Object.entries(current.en)) {
      for (const [key, enValue] of Object.entries(block)) {
        if (typeof enValue !== "string") continue;

        const baselineEn = base.en[namespace]?.[key];
        const baselineZh = base.zh[namespace]?.[key];
        const baselineZhTw = base["zh-TW"][namespace]?.[key];
        const currentZh = current.zh[namespace]?.[key];
        const currentZhTw = current["zh-TW"][namespace]?.[key];

        // English changed but Chinese didn't
        if (baselineEn !== undefined && enValue !== baselineEn) {
          if (currentZh === baselineZh) {
            staleZh.push(`${namespace}.${key}: en="${enValue.slice(0, 40)}" vs baseline="${baselineEn.slice(0, 40)}" (zh unchanged)`);
          }
          if (currentZhTw === baselineZhTw) {
            staleZhTw.push(`${namespace}.${key}: en="${enValue.slice(0, 40)}" vs baseline="${baselineEn.slice(0, 40)}" (zh-TW unchanged)`);
          }
        }
      }
    }

    check(
      "no stale Simplified Chinese translations (en changed, zh unchanged)",
      staleZh.length === 0,
      staleZh.length === 0
        ? "no stale zh translations"
        : `${staleZh.length} stale zh translation(s): ${staleZh.slice(0, 4).join(" | ")}`,
    );

    check(
      "no stale Traditional Chinese translations (en changed, zh-TW unchanged)",
      staleZhTw.length === 0,
      staleZhTw.length === 0
        ? "no stale zh-TW translations"
        : `${staleZhTw.length} stale zh-TW translation(s): ${staleZhTw.slice(0, 4).join(" | ")}`,
    );
  }
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
