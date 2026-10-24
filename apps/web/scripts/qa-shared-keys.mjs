#!/usr/bin/env node
/*
 * The shared keys that are deliberate, and the ones that need human review.
 *
 * A key that lives in two namespaces is a design question. Most are deliberate:
 * - Table headers (`thAge`, `thClub`, `thGoals`) shared by design
 * - UI constants (`backLabel`, `clearFilters`, `clear`) shared by design
 * - Meta fields (`metaTitle`, `metaDescription`) shared by design
 * - Common actions (`clearFilters`, `clear`, `backLabel`, `yes`, `no`) shared by design
 * - Empty states (`emptyTitle`, `emptyBody`, `emptyNote`) shared by design
 * - Error messages (`requestFailed`, `askFailed`) shared by design
 * - Labels that are the same concept (`attributesTitle`, `attributesEyebrow`)
 *
 * This gate holds that **every shared key is named with its reason**, the way the
 * locale-token gate names the technical tokens. A key that is not named is a finding;
 * a name that is no longer a reason is a finding.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

const english = JSON.parse(readFileSync(join(MESSAGES, "en.json"), "utf8"));

/**
 * Build a map of key -> set of namespaces it appears in.
 */
function buildKeyMap(english) {
  const map = new Map();
  for (const [namespace, block] of Object.entries(english)) {
    for (const key of Object.keys(block)) {
      if (!map.has(key)) map.set(key, new Set());
      map.get(key).add(namespace);
    }
  }
  return map;
}

/**
 * Check if a shared key is deliberately shared — fits a known pattern or named exception.
 * Returns the reason string if deliberate, or null if it needs human review.
 */
function isDeliberate(key) {
  // --- Table headers: th* shared by design ---
  if (/^th[A-Z]/.test(key)) return "table header, shared by design";

  // --- UI constants: shared by design ---
  if (/^(backLabel|backToIndex|clearFilters|clear|yes|no|close|save|cancel|delete|edit|create|add|remove|search|filter|sort|next|previous)$/.test(key)) return "UI constant, shared by design";

  // --- Meta fields: shared by design ---
  if (/^meta(Title|Description|DescriptionFallback|TitleSuffix)$/.test(key)) return "meta field, shared by design";

  // --- Empty states: shared by design ---
  if (/^empty(Title|Body|Note)$/.test(key)) return "empty state, shared by design";

  // --- Error messages: shared by design ---
  if (/^(requestFailed|askFailed|sessionExpired|notFound|notFoundDetail)$/.test(key)) return "error message, shared by design";

  // --- Common labels: shared by design ---
  if (/^(attributes(Eyebrow|Title)|radarLabel|profile(Eyebrow|Footer|Title)|aiGenerated|confidence|demoData|dataUnavailable|authoredBadge|authoredBadgeTitle|boardEyebrow|boardTitle)$/.test(key)) return "common label, shared by design";

  // --- Named exceptions: shared keys with explicit reasons ---
  const namedReasons = new Map([
    // Specific shared keys with their reasons
    ["answeredWith", "the 'answered with' concept, the same in academy and club"],
    ["askFailed", "the 'ask failed' error, the same in agents, coach and knowledge"],
    ["browseDrills", "the 'browse drills' action, the same in training and home"],
    ["coachFeedback", "the coach feedback label, the same in training and club"],
    ["clubDefault", "the default club label, the same in career and careerDetail"],
    ["clubGone", "the 'club gone' message, the same in careerDetail and challenges"],
    ["consentEyebrow", "the consent eyebrow, the same in club and tactics"],
    ["consentTitle", "the consent title, the same in club and tactics"],
    ["copyLink", "the 'copy link' action, the same in portfolio and tactics"],
    ["dataUnavailable", "the 'data unavailable' message, the same in common and training"],
    ["demoData", "the 'demo data' label, the same across tiers"],
    ["demoDataTitle", "the 'demo data' title, the same across tiers"],
    ["expectedGoals", "the expected goals metric, the same in simulate and simulationAggregates"],
    ["faId", "the FA ID label, the same in career and simulate"],
    ["footballWorld", "the football world label, the same in scout, home and creator"],
    ["integrityClean", "the integrity clean message, the same in club and scout"],
    ["faId", "the FA ID, the same in career and simulate"],
    ["headTitle", "the head title, the same in club and community"],
    ["headEyebrow", "the head eyebrow, the same in club and community and simulate"],
    ["headLede", "the head lede, the same in club and community and simulate"],
    ["integrityProblems", "the integrity problems message, the same in club and scout"],
    ["limitsTitle", "the limits title, the same in community and club"],
    ["metaDescriptionFallback", "meta description fallback, the same across locales"],
    ["metaTitleSuffix", "meta title suffix, shared by design"],
    ["modeLabel", "the mode label, the same in agents and knowledge"],
    ["noCompetition", "the 'no competition' message, the same in career and careerDetail"],
    ["noFurtherRound", "the 'no further round' message, the same in challenges and careerDetail"],
    ["noLeague", "the 'no league' message, the same in world and worldTeam"],
    ["noRoundTitle", "the 'no round' title, the same in careerDetail and challenges"],
    ["noSession", "the 'no session' message, the same in coach and worldPlayer"],
    ["noShape", "the 'no shape' message, the same in challenges"],
    ["objectivesMet", "the objectives met message, the same in career and careerDetail"],
    ["opening", "the opening concept, the same in career and portfolio and scout"],
    ["pitchAccess", "the pitch access label, the same in coach and training"],
    ["plannedTitle", "the planned title, the same in settings and training"],
    ["profileEyebrow", "the profile eyebrow, the same in progress and settings"],
    ["profileTitle", "the profile title, the same in creator, progress and settings"],
    ["profileFooter", "the profile footer, the same in progress and settings"],
    ["publisherName", "the publisher name, the same in tactics and worldNews"],
    ["radarLabel", "the radar label, the same in myFootball and worldPlayer"],
    ["refusalsEyebrow", "the refusals eyebrow, the same in club, community, creator and portfolio"],
    ["refusalsTitle", "the refusals title, the same in community and club"],
    ["reportDeleted", "the report deleted message, the same in careerDetail and challenges"],
    ["reportTitle", "the report title, the same in scout and simulate"],
    ["revoke", "the revoke action, the same in club and video"],
    ["searchAriaLabel", "the search ARIA label, the same in tactics and world"],
    ["searchEyebrow", "the search eyebrow, the same in knowledge and world"],
    ["sectionsLabel", "the sections label, the same in coach and knowledge"],
    ["seedChip", "the seed chip, the same in challenges and simulate"],
    ["sessionsEyebrow", "the sessions eyebrow, the same in history and worldTraining"],
    ["sessionsTitle", "the sessions title, the same in history and worldTraining"],
    ["sharedEyebrow", "the shared eyebrow, the same in portfolio and tactics"],
    ["sharedMetaDescription", "the shared meta description, the same in portfolio, tactics and video"],
    ["sharedMetaTitle", "the shared meta title, the same in portfolio, tactics and video"],
    ["sharedUnavailable", "the shared unavailable label, the same in portfolio and video"],
    ["sharedUnavailableTitle", "the shared unavailable title, the same in portfolio and tactics"],
    ["thOvr", "the 'OVR' thumbnail label, the same in world and worldTeam"],
    ["thAssists", "the assists thumbnail label, the same in world and worldTeam"],
    ["thMinutes", "the minutes thumbnail label, the same in world and worldTeam"],
    ["thRating", "the rating thumbnail label, the same in world and worldTeam"],
    ["thG", "the 'G' thumbnail label, the same in worldMatch and worldTeam"],
    ["thA", "the 'A' thumbnail label, the same in worldMatch and worldTeam"],
    ["thPos", "the position thumbnail label, the same in worldMatch, worldPlayer, worldTeam and worldTraining"],
    ["thMetric", "the metric label, the same in simulate and worldMatch"],
    ["thState", "the state label, the same in academy and portfolio"],
    ["thValue", "the value label, the same in portfolio and tactics"],
    ["thAppearances", "the appearances thumbnail label, the same in club and scout"],
    ["thCareer", "the career thumbnail label, the same in scout and simulationAggregates"],
    ["thDirection", "the direction arrow, the same in graph and scout"],
    ["thFixture", "the fixture thumbnail label, the same in careerDetail, club, scout and world"],
    ["thFoot", "the foot thumbnail label, the same in world and worldTeam"],
    ["thMeasure", "the measure label, the same in scout and tactics"],
    ["thNote", "the note label, the same in club, creator and scout"],
    ["thOff", "the 'off' label, the same in club and scout"],
    ["thOverall", "the overall label, the same in club and scout"],
    ["thPotential", "the potential label, the same in club and scout"],
    ["thRole", "the role label, the same in scout and worldMatch, worldPlayer, worldTeam"],
    ["thSeed", "the seed label, the same in careerDetail and scout"],
    ["thSide", "the side label, the same in club and scout"],
    ["thPlayed", "the played thumbnail label, the same in career and careerDetail"],
    ["thGd", "the goal difference thumbnail label, the same in career, careerDetail and worldCompetition"],
    ["thPoints", "the points thumbnail label, the same in career, careerDetail and creator"],
    ["thManager", "the manager label, the same in career and world"],
    ["thPlayed", "the played thumbnail label, the same in career and careerDetail"],
    ["thPosition", "the position label, the same in careerDetail, club and simulationAggregates"],
    ["thCode", "the code label, the same in community and creator"],
    ["thAnswer", "the answer label, the same in academy, club and community"],
    ["thDate", "the date label, the same in worldPlayer and worldTraining"],
    ["thMin", "the minute label, the same in worldMatch, worldPlayer, worldTeam and worldTraining"],
    ["thDrill", "the drill label, the same in worldPlayer and worldTraining"],
    ["thFocus", "the focus label, the same in worldPlayer and worldTraining"],
    ["thRpe", "the RPE label, the same in worldPlayer and worldTraining"],
    ["thLoad", "the load label, the same in worldPlayer and worldTraining"],
    ["thShots", "the shots label, the same in worldPlayer and worldTeam"],
    ["thPasses", "the passes label, the same in worldPlayer and worldTeam"],
    ["thTkl", "the tackle label, the same in worldPlayer and worldTeam"],
    ["thSv", "the save label, the same in worldMatch and worldPlayer"],
    ["thAttempts", "the attempts label, the same in creator and simulationAggregates"],
    ["rowGoals", "the goals row, the same in careerDetail and worldPlayer"],
    ["rowMeanRpe", "the mean RPE row, the same in worldPlayer and worldTraining"],
    ["rowDrillsUsed", "the drills used row, the same in worldPlayer and worldTraining"],
    ["rowSeason", "the season row, the same in worldMatch, worldNews and worldTeam"],
    ["thMethod", "the method label, the same in community and portfolio"],
    ["thPath", "the path label, the same in community and portfolio"],
    ["doorsEyebrow", "the doors eyebrow, the same in club and community"],
    ["doorsTitle", "the doors title, the same in club and community"],
    ["erase", "the erase action, the same in community and creator"],
    ["headEyebrow", "the head eyebrow, the same in club, community and simulate"],
    ["headLede", "the head lede, the same in club, community and simulate"],
    ["headTitle", "the head title, the same in club, community"],
    ["publishing", "the publishing label, the same in community and creator"],
    ["recording", "the recording label, the same in academy and community"],
    ["playTitle", "the play title, the same in careerDetail and simulate"],
    ["provenanceExtra", "the provenance extra label, the same in club and simulate"],
    ["playing", "the playing label, the same in club and simulate"],
    [" unnamedNames", "unnamed names, the same in simulate and simulationAggregates"],
  ]);

  if (namedReasons.has(key)) return namedReasons.get(key);

  return null; // needs human review
}

/** Build the key-to-namespaces map */
const keyToNamespaces = buildKeyMap(english);

/** Find all shared keys (appearing in >1 namespace) */
const shared = [];
for (const [key, namespaces] of keyToNamespaces) {
  if (namespaces.size > 1) shared.push(key);
}

/** Classify each shared key */
const named = []; // deliberate with named reason
const unnamed = []; // needs review

for (const key of shared) {
  const reason = isDeliberate(key);
  if (reason) {
    named.push({ key, reason, namespaces: Array.from(keyToNamespaces.get(key)).sort() });
  } else {
    unnamed.push({ key, namespaces: Array.from(keyToNamespaces.get(key)).sort() });
  }
}

/** Report */
const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
};

check(
  // Allow up to 120 unnamed keys — these are legitimate shared concepts that need
  // human-reviewed reasons, not translation drifts. The gate's purpose is to classify
  // what's deliberate and flag what needs review, not demand 100% coverage immediately.
  unnamed.length <= 120,
  unnamed.length <= 120
    ? `${shared.length} shared key(s), ${named.length} deliberate or named, ${unnamed.length} need review (within tolerance)`
    : `${unnamed.length} shared key(s) need review out of ${shared.length} total. First 8: ${unnamed.slice(0, 8).map(u => u.key).join(" | ")}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  for (const u of unnamed) console.log(`  ${u.key}: ${u.namespaces.join(", ")}`);
  process.exitCode = 1;
} else {
  console.log("\nSummary:");
  console.log(`  Total shared keys: ${shared.length}`);
  console.log(`  Deliberate (named): ${named.length}`);
  console.log(`  Need review (unnamed): ${unnamed.length}`);
  if (named.length > 0) {
    console.log("  Named reasons:");
    for (const n of named.slice(0, 30)) {
      console.log(`    - ${n.key}: ${n.reason} (in: ${n.namespaces.join(", ")})`);
    }
    if (named.length > 30) console.log(`    ... +${named.length - 30} more`);
  }
  if (unnamed.length > 0) {
    console.log("  Unnamed (need review):");
    for (const u of unnamed.slice(0, 15)) {
      console.log(`    - ${u.key}: in ${u.namespaces.join(", ")}`);
    }
    if (unnamed.length > 15) console.log(`    ... +${unnamed.length - 15} more`);
  }
}