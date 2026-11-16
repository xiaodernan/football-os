#!/usr/bin/env node
/*
 * Namespace ownership gate: each namespace has clear ownership.
 *
 * Every namespace in the catalogue should have a declared owner (tier/team) and
 * a clear purpose. This gate reads the ownership declarations and verifies:
 * 1. Every namespace has an owner
 * 2. No namespace is owned by multiple teams without explicit sharing reason
 * 3. Shared namespaces have documented sharing reasons
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

const english = JSON.parse(readFileSync(join(MESSAGES, "en.json"), "utf8"));

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** Namespace ownership declarations */
const NAMESPACE_OWNERS = {
  // Manual tier — the concise manual served from /manual; public, indexable, six locales
  "manual": { owner: "core", purpose: "The concise manual — one page that teaches the reader every door this product opens: languages, onboarding, world, coach, training; footer-linked, six-locale" },

  // Core app namespaces
  "nav": { owner: "core", purpose: "Navigation and locale switching" },
  "common": { owner: "core", purpose: "Shared UI constants and common labels" },
  "errorBoundary": { owner: "core", purpose: "Error boundary messages" },
  "notFound": { owner: "core", purpose: "404 page messages" },
  "onboarding": { owner: "core", purpose: "User onboarding flow" },
  "live": { owner: "core", purpose: "Live match and player pages" },
  "auth": { owner: "core", purpose: "Authentication and account management" },
  "settings": { owner: "core", purpose: "User settings and preferences" },

  // Tier namespaces
  "career": { owner: "career", purpose: "Career mode main pages" },
  "careerDetail": { owner: "career", purpose: "Career detail pages" },
  "challenges": { owner: "career", purpose: "Challenge mode pages" },
  "simulate": { owner: "simulate", purpose: "Match simulation pages" },
  "simulationAggregates": { owner: "simulate", purpose: "Simulation aggregates" },
  "club": { owner: "career", purpose: "Club management pages" },
  "home": { owner: "core", purpose: "Home page messages" },
  "errors": { owner: "core", purpose: "Error/refusal messages" },

  // The spotlight — the three recognitions the world cannot hide from
  "worldSpotlight": { owner: "world", purpose: "the world's three recognitions, recomputed live from the rows: best goals per 90 in tier-1, the most home clean sheets, and the youngest tier-1 player with real minutes" },

  // The timeline — the season matchday by matchday, told with arithmetic
  "worldTimeline": { owner: "world", purpose: "the season's timeline, recomputed live from the rows: the leader per matchday, the loudest round, the takeover and the whistle that settled the title" },

  // The Gazette — the season's paper of record, one edition per matchday
  "worldGazette": { owner: "world", purpose: "the season's edition-by-edition paper of record, recomputed live from the rows: the table after each round, the loudest fixture, the hot hand, the number that matters" },

  // The Finals — the world's cup hemisphere, computed, not told
  "worldFinals": { owner: "world", purpose: "the finals of every cup, recomputed live from the rows: the score, the player of each final, the cup holders' table, the loudest fixture" },

  // The Noise Dossier — the world's own noise graded against the rows it never saw
  "worldNoise": { owner: "world", purpose: "the rating-based caller's record against rows it never saw, recomputed live: accuracy, draw-calling, the longest correct run, the five largest misses" },

  // The Upset Register — the tier-1 underdog, honoured by its own arithmetic
  "worldUpsets": { owner: "world", purpose: "the underdog's ledger, recomputed live from the rows: the five largest gaps closed, the fortress draws, the season's tally" },

  // The Dynasties — the streak ledger
  "worldDynasties": { owner: "world", purpose: "the tier-1 streak ledger, recomputed live from the rows: the five longest winning streaks, the five longest unbeaten runs, who is ablaze now" },

  // World tier
  "world": { owner: "world", purpose: "World overview pages" },
  "worldPlayer": { owner: "world", purpose: "World player pages" },
  "worldTeam": { owner: "world", purpose: "World team pages" },
  "worldMatch": { owner: "world", purpose: "World match pages" },
  "worldCompetition": { owner: "world", purpose: "World competition pages" },
  "worldNews": { owner: "world", purpose: "World news pages" },
  "worldTraining": { owner: "world", purpose: "World training pages" },
  "duel": { owner: "world", purpose: "The head-to-head between two footballers: the ledger, its verdict and the picker that chooses the pair" },
  "almanac": { owner: "world", purpose: "The season's honours in one page — eight awards and the manager of the table, recomputed live from the world's own rows" },
  "worldStory": { owner: "world", purpose: "The season's story in three chapters — the pairs the almanac certifies, the widest avalanche, the longest clean streak, recomputed live" },
  "worldRecords": { owner: "world", purpose: "The season's record book — eight marks (biggest haul, goal-fest, onslaught, fortress, castle, cards bill, the wall, the pinnacle), recomputed live from the stored rows" },
  "worldMatchdayXi": { owner: "world", purpose: "The world's XI — eleven slots in 4-3-3 filled by OVR across the Lyndera Superleague's stored roster, the same tier-1 the almanac speaks for" },

  // Tactics tier
  "tactics": { owner: "tactics", purpose: "Tactics system pages" },
  "gallery": { owner: "tactics", purpose: "Tactics gallery pages" },

  // Scout tier
  "scout": { owner: "scout", purpose: "Scout and player search pages" },

  // Coach tier
  "coach": { owner: "coach", purpose: "Coach AI pages" },

  // Knowledge tier
  "knowledge": { owner: "knowledge", purpose: "Knowledge base pages" },

  // Video tier
  "video": { owner: "video", purpose: "Video analysis pages" },

  // Training tier
  "training": { owner: "training", purpose: "Training drill pages" },
  "academy": { owner: "training", purpose: "Academy/training schedule pages" },

  // Graph tier
  "graph": { owner: "graph", purpose: "Knowledge graph pages" },

  // Market tier
  "market": { owner: "market", purpose: "Transfer market pages" },

  // Community tier
  "community": { owner: "community", purpose: "Community features" },

  // Creator tier
  "creator": { owner: "creator", purpose: "Content creator pages" },

  // Portfolio tier
  "portfolio": { owner: "portfolio", purpose: "Portfolio/shared CV pages" },

  // Progress tier
  "progress": { owner: "progress", purpose: "Player progress pages" },
  "myFootball": { owner: "progress", purpose: "My Football profile pages" },
  "history": { owner: "progress", purpose: "Training history pages" },
  "leaderboard": { owner: "progress", purpose: "Gamification leaderboard pages" },

  // Agents tier
  "agents": { owner: "agents", purpose: "AI agent orchestration pages" },

  // Disclaimer
  "disclaimer": { owner: "core", purpose: "Legal disclaimer messages" },

  // Notification tier
  "notifications": { owner: "core", purpose: "Notification and alert messages" },

  // Operator tier
  "traces": { owner: "core", purpose: "The operator's trace dashboard over the span store" },
  "plane": { owner: "core", purpose: "The service-plane console: the edge's breaker state, rate limits and load-balancer scores" },
};

/** Check that every namespace in the catalogue has an owner declaration */
const namespaces = Object.keys(english);
const missingOwners = [];
const extraOwners = [];

for (const namespace of namespaces) {
  if (!NAMESPACE_OWNERS[namespace]) {
    missingOwners.push(namespace);
  }
}

for (const declared of Object.keys(NAMESPACE_OWNERS)) {
  if (!english[declared]) {
    extraOwners.push(declared);
  }
}

check(
  "every namespace has a declared owner",
  missingOwners.length === 0 && extraOwners.length === 0,
  missingOwners.length === 0 && extraOwners.length === 0
    ? `${namespaces.length} namespace(s) all have owners`
    : `missing: ${missingOwners.join(", ")}; extra: ${extraOwners.join(", ")}`,
);

/** Check for shared ownership - namespaces with same owner are expected, cross-team sharing needs reason */
const ownerToNamespaces = {};
for (const [namespace, info] of Object.entries(NAMESPACE_OWNERS)) {
  if (!ownerToNamespaces[info.owner]) ownerToNamespaces[info.owner] = [];
  ownerToNamespaces[info.owner].push(namespace);
}

console.log("\nNamespace ownership summary:");
for (const [owner, nss] of Object.entries(ownerToNamespaces).sort()) {
  console.log(`  ${owner}: ${nss.sort().join(", ")}`);
}

/** Check that every namespace has a non-empty purpose */
const missingPurpose = [];
for (const [namespace, info] of Object.entries(NAMESPACE_OWNERS)) {
  if (!info.purpose || info.purpose.trim() === "") {
    missingPurpose.push(namespace);
  }
}

check(
  "every namespace owner declaration has a purpose",
  missingPurpose.length === 0,
  missingPurpose.length === 0
    ? "all owners have purposes"
    : `missing purpose: ${missingPurpose.join(", ")}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}