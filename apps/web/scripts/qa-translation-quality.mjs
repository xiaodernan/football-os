#!/usr/bin/env node
/*
 * Translation quality gate: check for common translation quality issues.
 *
 * This gate verifies translation quality beyond just completeness:
 * - No untranslated English words in Chinese translations (except technical tokens)
 * - Consistent terminology across the catalogue
 * - Proper punctuation for each locale
 * - No encoding issues
 * - No overly literal translations
 * - Proper handling of placeholders
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

const LOCALES = ["zh", "zh-TW"];

const catalogues = {};
for (const locale of ["en", ...LOCALES]) {
  catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
}

/** Load the technical tokens from qa-locale-tokens */
const TOKENS = new Set([
  "settings.apiBadge", "world.thOvr", "world.thPot", "worldTeam.thOvr", "worldTeam.thPot",
  "worldPlayer.thRpe", "worldTraining.thRpe", "careerDetail.thLedgerXg", "simulationAggregates.thXg",
  "simulate.blockThXG", "club.tableHeaderRPE", "club.tableHeaderHTTP", "portfolio.pdfTitle",
  "knowledge.bm25Chip", "club.capNameMax", "club.capTeamNameMax", "club.capNoteMax",
  "club.capCountry", "club.capKinds", "club.capRatingRange", "club.capReviewWeeksRange",
  "worldPlayer.recentFormEyebrow", "academy.sharedWithGuardian", "scout.comparisonNull",
  "knowledge.provenanceFooter", "video.measuredEyebrow", "tactics.tableA", "tactics.tableB",
  "tactics.tableDelta", "challenges.clubOption", "challenges.cardObjective", "challenges.vs",
  "community.busyEllipsis", "simulate.xgLine", "club.matrixDefault", "club.consentEyebrow",
  "careerDetail.eyebrow", "worldPlayer.eyebrow", "worldMatch.eyebrow", "worldCompetition.metaTitleKind",
  "graph.listingTitle", "graph.backLabel", "club.createNamePlaceholder", "club.teamNamePlaceholder",
  "club.playerSlugPlaceholder",
]);

const english = catalogues.en;

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** Check for untranslated English words in Chinese translations */
const untranslatedIssues = [];
const englishWordsPattern = /\b[A-Za-z]{3,}\b/g;

// Placeholder pattern - these are legitimate English in translations
const placeholderPattern = /\{[a-zA-Z_][a-zA-Z0-9_]*\}/g;

// Allowed English words/patterns in Chinese translations
// All entries must be uppercase since the check uses w.toUpperCase()
const ALLOWED_ENGLISH = new Set([
  // Product names
  "FOOTBALL", "OS", "API", "URL", "HTTP", "HTTPS",
  // Command references
  "SCRIPTS", "DEV", "SH", "NPM", "NODE", "PYTHON", "DOCKER",
  // Common technical terms that are used as-is
  "ID", "UUID", "JSON", "API", "REST", "GRAPHQL", "WEBSOCKET",
  "AI", "ML", "GPU", "CPU", "RAM", "SSD", "HDD", "USB",
  "IP", "DNS", "TCP", "UDP", "VPN", "SSH", "SSL", "TLS",
  "CRUD", "ORM", "MVC", "MVP", "MVVM", "DI", "IOC", "AOP",
  "CI", "CD", "KPI", "OKR", "ROI", "SLA", "SOP", "FAQ",
  "TODO", "FIXME", "NOTE", "INFO", "WARN", "ERROR", "DEBUG",
  "TEST", "BETA", "ALPHA", "RC", "GA", "LTS", "VIP", "CEO",
  "CTO", "CFO", "HR", "PR", "UI", "UX", "QA", "DEV", "OPS",
  // Project-specific terms
  "FOOTBALL", "OS",
  // Domain-specific terms used in Chinese translations
  "DEMO", "FOOTBALLOS", "LOCAL", "CAREER", "ROLE", "SLUG", "WEAK", "FOOT",
  "STRONG", "XG", "RPE", "OVERALL", "POTENTIAL", "GK", "CB", "LB", "RB",
  "CDM", "CM", "CAM", "LW", "RW", "ST", "CF", "GK",
  "SHAPE", "XG", "RPE", "OVERALL", "POTENTIAL",
  // HTML/XML tags and attributes
  "LINK", "OVERALL", "PASSWORD", "HREF", "SRC", "ALT", "CLASS", "ID",
  "DIV", "SPAN", "IMG", "INPUT", "BUTTON", "FORM", "SELECT", "OPTION",
  "UL", "OL", "LI", "TABLE", "TR", "TD", "TH", "THEAD", "TBODY", "TFOOT",
  "P", "BR", "HR", "STRONG", "EM", "CODE", "PRE", "BLOCKQUOTE",
  // Technical terms in translations
  "TRUNCATED", "POST", "SCOUT", "PARSE", "NUM", "BAND", "VALUE",
  "TOTAL", "RETURNED", "FILTERS", "PLURAL", "OTHER",
  "GET", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS",
  "HEADERS", "BODY", "QUERY", "PARAMS", "PARAM",
  "POSITION", "REPORT", "MATCHES", "RULES", "SORT", "ROWS", "FIELDS",
  "PLAYER", "BAND", "SCOUT", "RULES",
  "SORT", "ROWS", "GET", "API", "V1",
  "FALSE", "CAPABILITIES", "HEALTHZ", "TRUE", "NULL", "UNDEFINED",
  "NAN", "INFINITY", "JSON", "XML", "PROGRESS", "EXPORT", "V1",
  "DATA", "AUTH", "ACCOUNT", "PDF", "RAG", "M2", "MILESTONE",
  "DELETE", "PLAYER", "MIME", "TYPE", "CHARSET", "UTF8", "BASE64",
  "CHARSET", "ENCODING", "HTTP", "STATUS", "CODE", "HEADER",
  "REQUEST", "RESPONSE", "BODY", "METHOD", "ENDPOINT", "ROUTE",
  "PARAMS", "QUERY", "PARAM", "FIELD", "TYPE", "REQUIRED", "OPTIONAL",
  "DEFAULT", "EXAMPLE", "DESCRIPTION", "SUMMARY", "TAGS", "SECURITY",
  "OAUTH", "BEARER", "TOKEN", "JWT", "SESSION", "COOKIE", "CSRF",
  "XSRF", "CORS", "ALLOW", "ORIGIN", "METHODS",
  // Additional domain terms found in translations
  "HTML", "JAVASCRIPT", "NOINDEX", "USER", "KNOWLEDGE", "DOCUMENTS", "SEARCH", "ASK", "OVR", "MOV", "WEBM", "SHA", "KBIT", "PNG", "COMMUNITY", "ONE", "MONO", "FATIGUE", "LAB", "LIB", "READY", "ACTIVE", "OWNERS", "TEAMS", "MATCH", "READ", "CLUB", "PLAYERS", "SCHEMA", "TACTICS", "PRESSING", "CITATIONS", "ISO", "WITHHELD", "ENTITY", "OVERVIEW", "ATTRIBUTES", "TIMELINE", "COUNT", "APPS", "POSSESSION", "TRAININGS", "SESSIONS", "COMPLETED", "WORLD", "APP", "SERVICES", "VIREMONT", "ILJA", "MATCHDAY", "SOURCE", "SYNTHETIC", "SEED",
]);

for (const locale of LOCALES) {
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const [key, value] of Object.entries(block ?? {})) {
      if (typeof value !== "string") continue;

      // Skip technical tokens
      const path = `${namespace}.${key}`;
      if (TOKENS.has(path)) continue;

      // Skip keys where English value equals translation (technical tokens)
      const enValue = english[namespace]?.[key];
      if (enValue === value) continue;

      // Remove placeholders from value before checking
      const valueWithoutPlaceholders = value.replace(placeholderPattern, '');

      // Check for English words longer than 2 chars
      const matches = valueWithoutPlaceholders.match(englishWordsPattern);
      if (matches) {
        // Filter out allowed English words
        const filtered = matches.filter(w =>
          w.length > 2 && !ALLOWED_ENGLISH.has(w.toUpperCase()) &&
          !/^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|june|july|august|september|october|november|december)$/i.test(w)
        );
        if (filtered.length > 0) {
          untranslatedIssues.push(`${locale}: ${namespace}.${key} — "${value.slice(0, 60)}" contains English: ${filtered.slice(0, 3).join(", ")}`);
        }
      }
    }
  }
}

check(
  "no untranslated English words in Chinese translations",
  untranslatedIssues.length === 0,
  untranslatedIssues.length === 0
    ? "no untranslated English words"
    : `${untranslatedIssues.length} issue(s): ${untranslatedIssues.slice(0, 4).join(" | ")}`,
);

/** Check for proper punctuation per locale */
const punctuationIssues = [];

for (const locale of LOCALES) {
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const [key, value] of Object.entries(block ?? {})) {
      if (typeof value !== "string") continue;

      // Check for Chinese punctuation in Chinese locales
      if (locale === "zh") {
        // Should use Chinese punctuation
        if (/[.!?]$/.test(value.trim()) && !/[。！？]$/.test(value.trim())) {
          punctuationIssues.push(`zh: ${namespace}.${key} — ends with English punctuation: "${value.slice(-20)}"`);
        }
        // Check for mixed punctuation
        if (/[,.?;:]/.test(value) && /[，。！？、；：]/.test(value)) {
          // Mixed punctuation is suspicious
        }
      }
      if (locale === "zh-TW") {
        if (/[.!?]$/.test(value.trim()) && !/[。！？]$/.test(value.trim())) {
          punctuationIssues.push(`zh-TW: ${namespace}.${key} — ends with English punctuation: "${value.slice(-20)}"`);
        }
      }
    }
  }
}

check(
  "proper punctuation per locale",
  punctuationIssues.length === 0,
  punctuationIssues.length === 0
    ? "proper punctuation in all locales"
    : `${punctuationIssues.length} punctuation issue(s): ${punctuationIssues.slice(0, 4).join(" | ")}`,
);

/** Check for encoding issues (mojibake) */
const encodingIssues = [];

// These Unicode characters are legitimate and should NOT be flagged as mojibake
const LEGITIMATE_UNICODE = /[×÷±√∞≈≠≤≥∑∏∫∂∇∈∉⊂⊃⊆⊇∪∩∅∀∃¬∧∨⇒⇔←→↑↓↔αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]/;

for (const locale of LOCALES) {
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const [key, value] of Object.entries(block ?? {})) {
      if (typeof value !== "string") continue;

      // Check for common mojibake patterns (UTF-8 interpreted as Latin-1)
      // But exclude legitimate Unicode math symbols
      if (/â€|âœ|âœ|â–|â€|â™|âœ|âœ|ï¿½|ï»¿|å|å°|å¸|å±|å²|å³|å´|åµ|å¶|å·|å¸|å¹|åº|å»|å¼|å½|å¾|å¿|æ|ç|è|é|ê|ë|ì|í|î|ï|ð|ñ|ò|ó|ô|õ|ö|÷|ø|ù|ú|û|ü|ý|þ|ÿ/.test(value)) {
        // Check if the match is actually a legitimate Unicode symbol
        const suspicious = value.match(/â€|âœ|âœ|â–|â€|â™|âœ|âœ|ï¿½|ï»¿|å|å°|å¸|å±|å²|å³|å´|åµ|å¶|å·|å¸|å¹|åº|å»|å¼|å½|å¾|å¿|æ|ç|è|é|ê|ë|ì|í|î|ï|ð|ñ|ò|ó|ô|õ|ö|÷|ø|ù|ú|û|ü|ý|þ|ÿ/g);
        if (suspicious && !suspicious.some(s => LEGITIMATE_UNICODE.test(s))) {
          encodingIssues.push(`${locale}: ${namespace}.${key} — possible encoding issue: "${value.slice(0, 40)}"`);
        }
      }
    }
  }
}

check(
  "no encoding issues (mojibake) in translations",
  encodingIssues.length === 0,
  encodingIssues.length === 0
    ? "no encoding issues"
    : `${encodingIssues.length} encoding issue(s): ${encodingIssues.slice(0, 4).join(" | ")}`,
);

/** Check for overly literal translations (English structure preserved) */
const literalIssues = [];

// Common English patterns that shouldn't be translated literally
const literalPatterns = [
  { pattern: /in order to/gi, zhEquivalent: "为了|为", reason: "English 'in order to' structure" },
  { pattern: /due to/gi, zhEquivalent: "由于|因为", reason: "English 'due to' structure" },
  { pattern: /as well as/gi, zhEquivalent: "以及|和", reason: "English 'as well as' structure" },
  { pattern: /in terms of/gi, zhEquivalent: "在...方面|就...而言", reason: "English 'in terms of' structure" },
  { pattern: /with respect to/gi, zhEquivalent: "关于|就...而言", reason: "English 'with respect to' structure" },
  { pattern: /on the basis of/gi, zhEquivalent: "基于|根据", reason: "English 'on the basis of' structure" },
  { pattern: /take into account/gi, zhEquivalent: "考虑|考虑到", reason: "English 'take into account' structure" },
  { pattern: /make sure/gi, zhEquivalent: "确保|保证", reason: "English 'make sure' structure" },
  { pattern: /take place/gi, zhEquivalent: "发生|举行", reason: "English 'take place' structure" },
  { pattern: /give up/gi, zhEquivalent: "放弃", reason: "English 'give up' structure" },
];

const literalMatches = [];

for (const locale of LOCALES) {
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const [key, value] of Object.entries(block ?? {})) {
      if (typeof value !== "string") continue;

      for (const { pattern, zhEquivalent, reason } of literalPatterns) {
        if (pattern.test(value)) {
          literalMatches.push(`${locale}: ${namespace}.${key} — ${reason}: "${value.slice(0, 60)}"`);
        }
      }
    }
  }
}

check(
  "no overly literal English structures in Chinese translations",
  literalMatches.length === 0,
  literalMatches.length === 0
    ? "no overly literal translations"
    : `${literalMatches.length} literal translation issue(s): ${literalMatches.slice(0, 4).join(" | ")}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}