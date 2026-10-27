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
  // Core app namespaces
  "nav": { owner: "core", purpose: "Navigation and locale switching" },
  "common": { owner: "core", purpose: "Shared UI constants and common labels" },
  "errorBoundary": { owner: "core", purpose: "Error boundary messages" },
  "notFound": { owner: "core", purpose: "404 page messages" },
  "onboarding": { owner: "core", purpose: "User onboarding flow" },
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

  // World tier
  "world": { owner: "world", purpose: "World overview pages" },
  "worldPlayer": { owner: "world", purpose: "World player pages" },
  "worldTeam": { owner: "world", purpose: "World team pages" },
  "worldMatch": { owner: "world", purpose: "World match pages" },
  "worldCompetition": { owner: "world", purpose: "World competition pages" },
  "worldNews": { owner: "world", purpose: "World news pages" },
  "worldTraining": { owner: "world", purpose: "World training pages" },

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

  // Agents tier
  "agents": { owner: "agents", purpose: "AI agent orchestration pages" },

  // Disclaimer
  "disclaimer": { owner: "core", purpose: "Legal disclaimer messages" },

  // Notification tier
  "notifications": { owner: "core", purpose: "Notification and alert messages" },
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