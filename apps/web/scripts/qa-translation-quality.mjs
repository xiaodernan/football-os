#!/usr/bin/env node
/*
 * Translation quality gate: check for common translation quality issues.
 *
 * This gate verifies translation quality beyond just completeness:
 * - No untranslated English words in translations (except technical tokens)
 * - Proper punctuation for each locale
 * - No encoding issues (mojibake) in translations
 * - No overly literal English structures in translations
 * - Arabic messages carry Arabic script (when ar.json ships); Hebrew likewise (when he.json ships) — same shape, same rule
 * - a message byte-identical to English is a *named* technical token, in every locale that ships
 *
 * Cured 2026-11-08 over three holes of the same class — a green line that judged nothing — found by the
 * M6 §6 re-read and measured first (docs/I18N_ARC_VERIFICATION.md §40):
 *   1. the two script checks printed `every Arabic message carries Arabic script` on a tree where no
 *      `ar.json` exists, so a dormant rule and a clean one were the same sentence;
 *   2. they printed it too when `ar.json` **is** a byte copy of `en.json`: every message is identical to
 *      English, every message is skipped, and a catalogue that shows an Arabic reader English passes as
 *      translated (measured pre-fix: 6/6 green, 4224 messages that never became Arabic);
 *   3. `LOCALES` was a candidate list filtered by existence, so a fourth catalogue — `fr.json` — joined the
 *      build and was judged by nobody (measured pre-fix: 6/6 green with one planted).
 * The exemption set is now read from `qa-locale-tokens.mjs`, the gate that records *why* each key is
 * language-neutral, instead of being copied: on 2026-11-08 the same 45 paths were written out by hand in
 * three files (`qa-locale-tokens.mjs`, `qa-token-drift.mjs` and this gate), and a copy is where an exemption
 * goes to drift. This gate is no longer one of the copies.
 *
 * Files only: no server, no browser, no port.
 */

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

/** The locales this gate owns a rule for. `ar` and `he` carry a script rule the day their catalogue ships;
 *  a catalogue outside this set is charged by filename rather than passing unseen. */
const KNOWN_LOCALES = new Set(["zh", "zh-TW", "ar", "he"]);

/** Discovery, not a candidate list: every JSON file in the directory is loaded, and `en` is the reference
 *  every other locale is compared against. */
const SHIPPED = readdirSync(MESSAGES)
  .filter((name) => name.endsWith(".json"))
  .map((name) => basename(name, ".json"))
  .sort();
const LOCALES = SHIPPED.filter((locale) => locale !== "en");

const catalogues = {};
for (const locale of SHIPPED) {
  catalogues[locale] = JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));
}

/** The values that are the same in every language, read from the gate that names the reason for each one.
 *  An unreadable table is a finding, not a silent empty exemption set: zero keys would make every technical
 *  token a defect, and the gate would be red for a reason its own output does not state. */
const TOKENS_FILE = join(WEB, "scripts", "qa-locale-tokens.mjs");
const tokenTable = (() => {
  if (!existsSync(TOKENS_FILE)) return { keys: new Set(), error: `no ${basename(TOKENS_FILE)} beside this gate` };
  const body = /const TOKENS = new Map\(\[([\s\S]*?)\]\);/.exec(readFileSync(TOKENS_FILE, "utf8"));
  if (!body) return { keys: new Set(), error: `${basename(TOKENS_FILE)} holds no \`const TOKENS = new Map([...])\` table` };
  return { keys: new Set([...body[1].matchAll(/\[\s*"([^"]+)"\s*,/g)].map((match) => match[1])), error: null };
})();
const TOKENS = tokenTable.keys;

const english = catalogues.en ?? {};

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/* Discovery. The old `LOCALES` was a candidate list filtered by `existsSync`, so a catalogue that joined
 * the build outside those four names was loaded by nobody and judged by nothing — a planted `fr.json` held
 * any copy at all and this gate stayed green. Now the directory decides the population and a name without a
 * rule is a finding rather than an absence. */
const unknownLocales = SHIPPED.filter((locale) => locale !== "en" && !KNOWN_LOCALES.has(locale));
check(
  "every catalogue in messages/ is a locale this gate has rules for",
  unknownLocales.length === 0 && SHIPPED.includes("en"),
  unknownLocales.length === 0
    ? `messages/ ships ${SHIPPED.length} catalogue(s): reference en, judged ${LOCALES.join(", ") || "(none besides en)"}; KNOWN_LOCALES covers ${[...KNOWN_LOCALES].join(", ")}`
    : `${unknownLocales.map((locale) => `${locale}.json`).join(", ")} ship(s) in messages/ with no rule here — add it to KNOWN_LOCALES (and a punctuation/encoding arm) or remove the file`,
);

/* The exemption set. Three hand copies of the same 45 keys existed on 2026-11-08 (this file,
 * `qa-locale-tokens.mjs`, `qa-token-drift.mjs`); the copy is where an exemption goes stale, so the set is
 * read from the gate that records *why* each key is language-neutral. An unreadable table is charged as a
 * finding: zero exemptions would make every technical token a defect, and the red would name a symptom
 * instead of the cause. */
check(
  "the technical-token exemption set is read from the gate that names each one",
  tokenTable.error === null && TOKENS.size > 0,
  tokenTable.error === null
    ? `${TOKENS.size} exempt path(s) read at run time from ${basename(TOKENS_FILE)}`
    : `exemption set unreadable — ${tokenTable.error}`,
);

/* Identical-to-English messages. The old gate treated "this value equals the English one" as proof the key
 * is language-neutral, and skipped it in silence — which is the hole that lets a byte copy of `en.json`
 * shipped as `ar.json` pass for a translation (measured pre-fix: 6/6 green over 4224 such messages). The
 * tree's own rule is stronger and already true: every one of the 45 per locale is listed with a reason in
 * `qa-locale-tokens.mjs`. So identical is allowed only when named. */
let identicalCount = 0;
const identicalUnnamed = [];

for (const locale of LOCALES) {
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const [key, value] of Object.entries(block ?? {})) {
      if (typeof value !== "string") continue;
      if (english[namespace]?.[key] !== value) continue;
      identicalCount += 1;
      const path = `${namespace}.${key}`;
      if (TOKENS.has(path)) continue;
      identicalUnnamed.push(`${locale}: ${path} — "${value.slice(0, 40)}"`);
    }
  }
}

check(
  "every message byte-identical to English is a named technical token",
  identicalUnnamed.length === 0,
  identicalUnnamed.length === 0
    ? identicalCount === 0
      ? `no message in ${LOCALES.join(", ")} is byte-identical to English on this plane`
      : `${identicalCount} message(s) across ${LOCALES.join(", ")} are byte-identical to English, each named in ${basename(TOKENS_FILE)}`
    : `${identicalUnnamed.length} of ${identicalCount} identical-to-English message(s) carry no named reason: ${identicalUnnamed.slice(0, 4).join(" | ")}`,
);

/** Check for untranslated English words in translations (zh, zh-TW and, once it ships, ar) */
const untranslatedIssues = [];
let messagesScanned = 0;
let wordScanned = 0;
let namedTokenSkips = 0;
let identicalSkips = 0;
const englishWordsPattern = /\b[A-Za-z]{3,}\b/g;

// Placeholder pattern - these are legitimate English in translations.
// A message is an ICU program, and its arguments come in two shapes: a bare `{count}`, and the
// `{count, plural, one {# round} other {# rounds}}` form. The old pattern matched only the first, so the
// argument name inside a plural (`opensIn`, `inRounds`) was read as an untranslated English word — the gate
// went red on 22 correctly translated Chinese messages the moment the market's window copy gained plurals.
// Matching the name up to its `}` or `,` covers both, and the branch keywords (`plural`, `one`, `other`) are
// allowed below because they are syntax, not copy.
const placeholderPattern = /\{\s*[A-Za-z_][A-Za-z0-9_]*\s*(?=[,}])/g;

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
  "TOTAL", "RETURNED", "FILTERS", "PLURAL", "OTHER", "SELECT", "SELECTORDINAL", "OFFSET",
  "ZERO", "ONE", "TWO", "FEW", "MANY",
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
      messagesScanned += 1;

      const path = `${namespace}.${key}`;
      if (TOKENS.has(path)) {
        namedTokenSkips += 1;
        continue;
      }

      // An identical value has already been charged — named or not — by the check above; skipping it here
      // avoids reporting the same message twice under two different verdicts.
      if (english[namespace]?.[key] === value) {
        identicalSkips += 1;
        continue;
      }

      // Remove placeholders from value before checking
      wordScanned += 1;
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
  "no untranslated English words in translations",
  untranslatedIssues.length === 0,
  untranslatedIssues.length === 0
    ? `${wordScanned} message(s) word-scanned across ${LOCALES.join(", ")}; ${namedTokenSkips} exempted as named tokens and ${identicalSkips} as identical to English, the identical ones charged by the check above`
    : `${wordScanned} scanned, ${untranslatedIssues.length} issue(s): ${untranslatedIssues.slice(0, 4).join(" | ")}`,
);

/** Check for proper punctuation per locale */
const punctuationIssues = [];

const ARABIC_SCRIPT = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
const HEBREW_SCRIPT = /[\u0590-\u05FF\uFB1D-\uFB4F]/;

for (const locale of LOCALES) {
  for (const [namespace, block] of Object.entries(catalogues[locale])) {
    for (const [key, value] of Object.entries(block ?? {})) {
      if (typeof value !== "string") continue;

      // Check for Chinese punctuation in Chinese locales
      if (locale === "zh") {
        if (/[.!?]$/.test(value.trim()) && !/[。！？]$/.test(value.trim())) {
          punctuationIssues.push(`zh: ${namespace}.${key} — ends with English punctuation: "${value.slice(-20)}"`);
        }
      }
      if (locale === "zh-TW") {
        if (/[.!?]$/.test(value.trim()) && !/[。！？]$/.test(value.trim())) {
          punctuationIssues.push(`zh-TW: ${namespace}.${key} — ends with English punctuation: "${value.slice(-20)}"`);
        }
      }
      // An Arabic message that ends in Latin sentence-ending punctuation is the tell that the edit
      // didn't reach the reader's script; the Arabic full stop is the same byte-class the Chinese
      // pass accepts below (\.).
      if (locale === "ar" && ARABIC_SCRIPT.test(value)) {
        if (/[.!?]$/.test(value.trim())) {
          punctuationIssues.push(`ar: ${namespace}.${key} — ends with Latin punctuation inside Arabic text: "${value.slice(-20)}"`);
        }
      }
      // A Hebrew message that ends in an Arabic full stop (؟) or in Chinese sentence-ending punctuation
      // is the same tell as the Arabic arm — the editor reached for the wrong script's full stop.
      if (locale === "he" && HEBREW_SCRIPT.test(value)) {
        if (/[؟。！？]$/.test(value.trim())) {
          punctuationIssues.push(`he: ${namespace}.${key} — ends with a non-Hebrew full stop: "${value.slice(-20)}"`);
        }
      }
    }
  }
}

check(
  "proper punctuation per locale",
  punctuationIssues.length === 0,
  punctuationIssues.length === 0
    ? `${messagesScanned} message(s) visited across ${LOCALES.join(", ")}; the sentence-ending-punctuation rules fire for zh and zh-TW, and for ar and he the day their catalogues ship`
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
      if (locale === "ar" && /[ØÙÚÛ]/.test(value)) {
        // Arabic UTF-8 first byte (D8-DB) read as Latin-1 is exactly this pair; no Arabic text
        // and no named token uses the capital Latin-1 letters, so this reds only mojibake.
        encodingIssues.push(`${locale}: ${namespace}.${key} — Arabic script bytes decoded as Latin-1: "${value.slice(0, 40)}"`);
      } else if (locale === "he" && /[ÊËÌÍÎÏÐÑÒÓÔÕ]/.test(value) && !HEBREW_SCRIPT.test(value)) {
        // Hebrew letters encode to U+05A0-U+05FF, whose two-byte UTF-8 leading byte lands at Ê-Õ if read
        // as Latin-1. No Hebrew token uses these bytes legitimately, so flagging them with no Hebrew
        // script in the message reds only mojibake.
        encodingIssues.push(`${locale}: ${namespace}.${key} — Hebrew script bytes decoded as Latin-1: "${value.slice(0, 40)}"`);
      } else if (/â€|âœ|âœ|â–|â€|â™|âœ|âœ|ï¿½|ï»¿|å|å°|å¸|å±|å²|å³|å´|åµ|å¶|å·|å¸|å¹|åº|å»|å¼|å½|å¾|å¿|æ|ç|è|é|ê|ë|ì|í|î|ï|ð|ñ|ò|ó|ô|õ|ö|÷|ø|ù|ú|û|ü|ý|þ|ÿ/) {
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
    ? `${messagesScanned} message(s) scanned across ${LOCALES.join(", ")} for the Latin-1-misread byte classes`
    : `${encodingIssues.length} encoding issue(s): ${encodingIssues.slice(0, 4).join(" | ")}`,
);

/** Check for overly literal translations (English structure preserved) */

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
        // These patterns carry /g, and `RegExp.test` resumes from `lastIndex` when it does. Without the
        // reset, a message whose match sits before the previous message's match-end is read as clean — four
        // planted literal-structure messages over two patterns scored 2 hits pre-fix and 4 with the reset.
        pattern.lastIndex = 0;
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
    ? `${messagesScanned} message(s) scanned across ${LOCALES.join(", ")} against ${literalPatterns.length} English-structure patterns; the loop reads every shipped locale, so an ar or he catalogue is judged by this Chinese-named rule the day it ships`
    : `${literalMatches.length} literal translation issue(s): ${literalMatches.slice(0, 4).join(" | ")}`,
);

/* Script assertions (item 4, language arms): every non-technical message in an RTL catalogue carries the
 * script of its locale. A message that is pure placeholder/punctuation carries no signal and is exempt; a
 * message with Latin letters but no RTL script is an untranslated holdout, suspect the moment the file ships.
 *
 * Table-driven now, and the verdict says which way it was reached. Pre-fix both lines printed
 * `every Arabic message carries Arabic script` whether `ar.json` existed at all (measured: 6/6 on a tree with
 * no such file) and also when it was a byte copy of `en.json` (measured: 6/6 over 4224 messages that never
 * became Arabic) — a dormant rule, an emptied rule and a clean rule were one and the same sentence. So:
 * an absent catalogue says dormant, a shipped one says how many messages it judged and how many of those
 * showed the script, and a shipped catalogue that judged nothing — or judged everything and found no script
 * anywhere — is a finding rather than a pass. The floor is on messages *showing* the script, not on messages
 * carrying Latin letters: a correctly translated `ar.json` holds almost no Latin text, so a Latin-signal
 * floor would have refused the very work the rule exists to protect. */
const SCRIPT_RULES = [
  { locale: "ar", name: "Arabic", test: ARABIC_SCRIPT },
  { locale: "he", name: "Hebrew", test: HEBREW_SCRIPT },
];

for (const rule of SCRIPT_RULES) {
  const issues = [];
  const ships = SHIPPED.includes(rule.locale);
  let copyMessages = 0;
  let scriptMessages = 0;
  let namedExempts = 0;

  if (ships) {
    for (const [namespace, block] of Object.entries(catalogues[rule.locale])) {
      for (const [key, value] of Object.entries(block ?? {})) {
        if (typeof value !== "string") continue;
        const path = `${namespace}.${key}`;
        if (TOKENS.has(path)) {
          namedExempts += 1;
          continue;
        }
        // What is left once the placeholders and the punctuation are gone is the copy a reader sees. An empty
        // remainder says the message carries no language at all, so no script can be asked of it.
        const copy = value.replace(placeholderPattern, "").replace(/[\s\p{P}\p{S}\p{N}]/gu, "");
        if (copy.length === 0) continue;
        copyMessages += 1;
        if (rule.test.test(value)) {
          scriptMessages += 1;
          continue;
        }
        if (/[A-Za-z]/.test(copy)) {
          issues.push(`${rule.locale}: ${path} — Latin text with no ${rule.name} script and no named reason: "${value.slice(0, 60)}"`);
        }
      }
    }
  }

  let scriptDetail;
  if (!ships) {
    scriptDetail = `dormant — no ${rule.locale}.json on this plane, 0 message(s) judged; the rule arms the day the file ships`;
  } else if (copyMessages === 0) {
    scriptDetail = `${rule.locale}.json ships but 0 message(s) carry copy — every entry was a named token (${namedExempts}), a placeholder or punctuation — so this rule judged nothing`;
  } else if (scriptMessages === 0) {
    scriptDetail = `0 of ${copyMessages} message(s) in ${rule.locale}.json show ${rule.name} script, and ${issues.length} of them are Latin text — a file an ${rule.name} reader cannot read passes as a translation`;
  } else if (issues.length > 0) {
    scriptDetail = `${issues.length} of ${copyMessages} message(s) judged in ${rule.locale}.json are Latin text with no ${rule.name} script: ${issues.slice(0, 4).join(" | ")}`;
  } else {
    scriptDetail = `${scriptMessages} of ${copyMessages} message(s) judged in ${rule.locale}.json show ${rule.name} script and none is left in Latin; ${namedExempts} exempt as named tokens`;
  }

  check(
    `every ${rule.name} message in ${rule.locale}.json shows ${rule.name} script`,
    issues.length === 0 && (!ships || (copyMessages > 0 && scriptMessages > 0)),
    scriptDetail,
  );
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
const dormantRules = SCRIPT_RULES.filter((rule) => !SHIPPED.includes(rule.locale));
if (dormantRules.length) {
  console.log(`DORMANT  ${dormantRules.map((rule) => `${rule.name} script (${rule.locale}.json absent)`).join(", ")} — a PASS with this note judged nothing on this plane`);
}
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}