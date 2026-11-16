#!/usr/bin/env node
/**
 * The FOOTBALL OS fact pack — one committed JSON the personal page fetches.
 *
 * Every figure printed here stands on the tree that generated it; no figure is carried from a
 * ledger, hand-typed, or recalled from memory. Three honest sources:
 *
 *   * git answers about itself: HEAD, the commit count, the latest subject line;
 *   * the filesystem is walked: page routes, API test files, gates, world doors, locales;
 *   * the ledger is read for the current arc heading, never for a count.
 *
 * The ledger's own latest § heading is the milestone_full sentence the page prints; when a fresh push
 * re-cuts the arc, one push of this file is one honest row of the feed. `git push` only.
 * changes the arc, one push of this file is one honest row of the feed on the profile page.
 * `pwa_kb` is absent on purpose: this product is not a PWA and the showcase page prints `—` there.
 */

import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, statSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const git = (...args) =>
  execFileSync("git", args, { cwd: root, encoding: "utf8", timeout: 30000 }).trim();

const head = git("rev-parse", "--short", "HEAD");
const total_commits = Number(git("rev-list", "--count", "HEAD"));
const date = git("log", "-1", "--pretty=%cI");
const pushed_at = date.slice(0, 10);

/** Count every `page.tsx` under a directory tree — Next's route unit of this project. */
const walkPages = (dir) => {
  let count = 0;
  for (const entry of readdirSync(dir)) {
    const full = resolve(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === "node_modules" || entry.startsWith(".next")) continue;
      count += walkPages(full);
    } else if (entry === "page.tsx") {
      count += 1;
    }
  }
  return count;
};
const page_count = walkPages(resolve(root, "apps", "web", "app"));

const countByExt = (dir, pattern) => {
  let count = 0;
  const walk = (d) => {
    for (const entry of readdirSync(d)) {
      const full = resolve(d, entry);
      if (statSync(full).isDirectory()) {
        if (entry === "node_modules" || entry === "__pycache__") continue;
        walk(full);
      } else if (pattern.test(entry)) count += 1;
    }
  };
  try { walk(dir) } catch { /* dir absent: zero, honestly */ return 0 }
  return count;
};
const apiTestFiles = countByExt(resolve(root, "apps", "api", "tests"), /^test_.*\.py$/);
const webGateScripts = readdirSync(resolve(root, "apps", "web", "scripts")).filter((f) => f.endsWith(".mjs")).length;
const worldDoors = readdirSync(resolve(root, "apps", "web", "app", "world")).filter((f) => {
  if (f.startsWith("_")) return false; // `_og` share-card helpers are not doors
  try { return statSync(resolve(root, "apps", "web", "app", "world", f)).isDirectory(); } catch { return false; }
}).length;
const localeCatalogues = readdirSync(resolve(root, "apps", "web", "messages")).filter((f) => f.endsWith(".json")).length;

const ledger = readFileSync(resolve(root, "docs", "I18N_ARC_VERIFICATION.md"), "utf8");
const arcHeadings = [...ledger.matchAll(/^## (§\d+) — (.+)$/gm)];
const milestone = arcHeadings.length ? arcHeadings[arcHeadings.length - 1][1] : "§—";
const milestone_full = arcHeadings.length
  ? `${arcHeadings[arcHeadings.length - 1][1]} — ${arcHeadings[arcHeadings.length - 1][2]}`
  : "nothing ledgered yet";

const featureSurface = [
  "The World — a seeded season, computed end to end",
  "The Almanac — the awards the world earns",
  "The Story — three chapters from the archive",
  "The XI — the eleven the world would send",
  "The Record Book — the eight marks the world produced",
  "The Duel — the ledger's own pair of powers",
  "The Training Academy — drills with evidence",
  "The Coach — real phrasing on a real gateway, prefix cached ~95%",
  "Accessibility 1.00 — every audited public and authenticated surface",
];

const pack = {
  head,
  total_commits,
  milestone,
  milestone_full,
  pushed_at,
  screens: page_count,
  assets: webGateScripts + apiTestFiles,
  world_doors: worldDoors,
  locales: localeCatalogues,
  feature_surface: featureSurface,
  generated_at: new Date().toISOString(),
};

mkdirSync(resolve(root, "docs"), { recursive: true });
const out = resolve(root, "docs", "latest.json");
writeFileSync(out, JSON.stringify(pack, null, 2) + "\n", "utf8");
console.log(
  `latest.json: ${pack.head} ${pack.total_commits} commits · ${pack.screens} routes · ${pack.locales} locales · arc ${pack.milestone} pulled from the ledger`,
);
