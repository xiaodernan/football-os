#!/usr/bin/env node
/**
 * qa-locale-discovery.mjs — the census of *how* each gate gets the locales it judges.
 *
 * Why this file exists. Four ledgers say the i18n gates "discover the catalogue files in the directory and
 * judge every one of them". Measured here: of the scripts that load catalogues, a minority read the
 * directory; the rest name the locales they will judge inside their own source. While three catalogues ship
 * and every one of those lists contains three catalogues, the difference is invisible. It is not invisible
 * the day a fourth ships — the parity gate documented as the judge of parity would print its agreement
 * sentence over a catalogue it never opened. That is the defect §40 cured in `qa-translation-quality`, §41
 * cured in the two token gates, and this file holds for the other thirty: a green line spoken about a
 * population the file wrote out by hand.
 *
 * The site taxonomy, per script that reaches into `messages/`:
 *   derived    the locale list comes from `readdirSync` over the messages directory — the tree decides;
 *   list       a bracketed literal of locale tags used to choose catalogues (the statement or the loop body
 *              that follows it builds a messages path, calls existsSync, or reads a catalogue);
 *   map        an object literal keyed by locale tag, read the same way (`{ zh: "zh.json", … }`);
 *   targeted   no list at all, but the file names one locale directly — `catalogue("en")`, `messages/zh.json`;
 *   data       a locale literal that chooses nothing: fixture content a witness plants, or the keys of a
 *              CLDR category table. Counted and disclosed, never judged — a witness names locales in its
 *              fixtures on purpose, and charging that would teach everyone to switch the gate off.
 * Six claims:
 *   1. the census admits every script that reaches into messages/, and its admitted count may only rise, so
 *      a gate cannot leave this census by changing how it spells a path;
 *   2. every catalogue that ships is inside the population of every script that names one, unless a ledger
 *      row states why that script's rules do not cover it;
 *   3. no site inside such a script iterates a narrower list than the script itself loads, unless a row says
 *      why that check is about one locale;
 *   4. the number of derived scripts may only rise — the ratchet that makes each conversion visible;
 *   5. every ledger row is still true: the file is in the census, its recorded shape and tokens still match
 *      what is read now, and the ceiling on rows may only fall;
 *   6. a population site names no locale tag outside the planned set, so adding a language is a decision.
 *
 * Files only — no server, no browser. Run from apps/web, or point QA_I18N_WEB at another checkout.
 * `--census` prints the whole table this gate reads, which is where its ledger rows come from.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const SCRIPTS = join(WEB, "scripts");

/** Text reads fold CRLF: `core.autocrlf=true` with no `.gitattributes` gives the same file different lines
 *  on disk and in the commit, and every claim here is scraped from text. JSON reads do not need it. */
const readText = (path) => readFileSync(path, "utf8").replace(/\r\n/g, "\n");

const PLANNED = new Set(["en", "zh", "zh-TW", "ar", "he"]);
const TAG_RE = /^(?:[a-z]{2}|[a-z]{2}-[A-Z]{2})$/;

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/** The statement that starts at `from`, up to the first `;` at nesting depth zero. */
function statementFrom(src, from) {
  let depth = 0;
  for (let i = from; i < src.length; i++) {
    const c = src[i];
    if ("([{".includes(c)) depth += 1;
    else if (")}]".includes(c)) depth -= 1;
    else if (c === ";" && depth === 0) return src.slice(from, i + 1);
  }
  return src.slice(from, from + 240);
}

/** Locale tags inside the literals of one statement's text: bracketed lists and locale-keyed object maps. */
function tagsIn(text) {
  const tags = new Set();
  for (const m of text.matchAll(/\[[^\]]*\]/g))
    for (const t of m[0].matchAll(/"([a-zA-Z-]{2,6})"/g)) if (PLANNED.has(t[1])) tags.add(t[1]);
  for (const m of text.matchAll(/[{,]\s*"?([a-zA-Z-]{2,6})"?\s*:/g)) if (PLANNED.has(m[1])) tags.add(m[1]);
  return [...tags];
}

/** Every tag-shaped quoted token inside a list, planned or not — claim 6 needs the unplanned ones. */
function allTagsIn(text) {
  const tags = new Set();
  for (const m of text.matchAll(/\[[^\]]*\]/g))
    for (const t of m[0].matchAll(/"([a-z]{2}(?:-[A-Z]{2})?)"/g)) if (TAG_RE.test(t[1])) tags.add(t[1]);
  return [...tags];
}

/** Does this text *choose catalogues*? The test is what the statement or the body after it does, not
 *  whether it mentions a language: a rule table mentions languages and chooses nothing. */
const SELECTS = /MESSAGES|messages|\.json|existsSync|catalogue|catalogues|dict\b|readFileSync|\bread\(|\bparse\(|writeFileSync|cpSync|rmSync|loadAll/;
/** …and one more spelling: a bare list assigned to a name that is later used to select
 *  (`for (const locale of BASE)`, `catalogues[locale]`, `${locale}.json`). */
const SELECTS_ELSEWHERE = /\bof\s+([A-Za-z_$][\w$]*)\b|\[\s*\1\s*\]|`\$\{\s*\1\s*\}`|\1\s*\.json/;

function loadsCatalogues(src) {
  return /["'`]messages["'`]/.test(src) || /messages\/[A-Za-z-]+\.json/.test(src) || /\$\{[^}]*\}\.json/.test(src) || /\bcatalogue\w*\s*\(/.test(src);
}

/** A catalogue named without a list at all: `catalogue('en')`, `catalogues["zh-TW"]`, `"en.json"`,
 *  `messages/zh.json`. A file that only ever spells one of these has a population of one — which this
 *  census discloses rather than charges, because a rule about English copy is not a rule about all copy. */
const DIRECT_TARGET =
  /catalogue\w*\s*\(\s*["'](en|zh|zh-TW|ar|he)["']\s*\)|["'`]messages\/(?:[A-Za-z-]+\/)?(en|zh|zh-TW|ar|he)\.json["'`]|catalogues\s*\[\s*["'](en|zh|zh-TW|ar|he)["']\s*\]|["'](en|zh|zh-TW|ar|he)\.json["']/g;

/** Discovery in the one shape that means it: the directory itself, not a source tree being walked.
 *  `readdirSync(dir, { withFileTypes: true })` appears in eight of these files to walk `app/` and
 *  `components/`; crediting that would call them all derived, which is exactly the kind of green this
 *  census exists to refuse. */
const DERIVED = /readdirSync\s*\(\s*MESSAGES\b/;

const scriptFiles = readdirSync(SCRIPTS).filter((name) => name.endsWith(".mjs")).sort();
const shipped = readdirSync(MESSAGES)
  .filter((name) => name.endsWith(".json"))
  .map((name) => basename(name, ".json"))
  .sort();

const census = [];
let dataSites = 0;
for (const name of scriptFiles) {
  const src = readText(join(SCRIPTS, name));
  if (!loadsCatalogues(src)) continue;
  const lines = src.split("\n");
  const sites = [];
  const push = (kind, label, raw, ln) => {
    const toks = tagsIn(raw);
    const unplanned = allTagsIn(raw).filter((t) => !PLANNED.has(t));
    sites.push({ kind, label, toks, unplanned, ln });
  };
  let cursor = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const decl = /^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=/.exec(line);
    const loop = /for\s*\(\s*(?:const|let)\s+([\w$]+)\s+of\s+(\[[^\]]*\])/.exec(line);
    const chain = /\[(?:"[a-z]{2}(?:-[A-Z]{2})?"(?:,\s*"[a-z]{2}(?:-[A-Z]{2})?")*)\]\.(every|some|map|filter|forEach|flat|join)\(/.exec(line);
    if (loop) {
      if (tagsIn(loop[2]).length) {
        if (SELECTS.test(lines.slice(i + 1, i + 10).join("\n"))) push("loop", `for (${loop[1]})`, loop[2], i + 1);
        else dataSites += 1;
      }
    } else if (chain) {
      if (tagsIn(chain[0]).length) {
        if (SELECTS.test(lines.slice(i, i + 4).join("\n"))) push("chain", `.${chain[1]}`, chain[0], i + 1);
        else dataSites += 1;
      }
    } else if (decl) {
      const text = statementFrom(src, cursor);
      if (tagsIn(text).length) {
        const idRe = new RegExp(SELECTS_ELSEWHERE.source.replace(/\\1/g, `\\b${decl[1]}\\b`), "g");
        if (SELECTS.test(text) || idRe.test(src.slice(cursor + text.length))) push("list", decl[1], text, i + 1);
        else dataSites += 1;
      }
    }
    cursor += line.length + 1;
  }
  const derived = DERIVED.test(src);
  const direct = [...new Set([...src.matchAll(DIRECT_TARGET)].map((m) => m[1] || m[2] || m[3] || m[4]))];
  const named = [...new Set(sites.flatMap((s) => s.toks))];
  // The universe is the widest reading available: every catalogue the file names by list, by map key, by a
  // direct read, or by a quoted filename. A file cannot open a catalogue it never spells in any of those.
  const spelled = [...new Set([...src.matchAll(/["'](en|zh|zh-TW|ar|he)(?:\.json)?["']/g)].map((m) => m[1]))];
  const universe = [...new Set([...(derived ? shipped : []), ...named, ...direct, ...spelled])];
  census.push({
    name,
    derived,
    sites,
    direct,
    universe,
    shape: derived ? "derived" : sites.length ? "named" : direct.length ? "targeted" : "unmeasured",
  });
}

/* ------------------------------------------------------------------ the ledger
 * A row excuses one file, or one site, from claims 2 and 3, and states why the narrower population is
 * defensible. Rows are keyed by file for file rows and by `file::label::sorted tags` for site rows, so a
 * conversion that removes the site orphans the row and claim 5 reddens it: the ledger cannot collect the
 * debts of files that no longer have them. */
const FILE_LEDGER = new Map([
  ["qa-api-strings.mjs", "Publishes the API's refusal codes and checks each one against the catalogues that must hold it; the reference English string is read as the code's own text, so the four locales under judgement are the four that must each carry a translation of it."],
  ["qa-shared-keys.mjs", "Its claim is that one key carries two different meanings in the two translated catalogues. English is the language the key is authored in, so an English value cannot diverge from itself, and `ar`/`he` have no rule here yet — the row is about zh and zh-TW and says so."],
  ["qa-locale-formatting.mjs", "Holds a formatting table per locale (skeletons and number styles). A locale outside the table is charged by its own check with a named finding rather than skipped, so the list is the rule set, not a candidate filter."],
  ["qa-rtl-readiness.mjs", "Judges direction, not copy: it names the LTR locales it expects to ship and filters the RTL set by existence, so a `he.json` that lands is opened by the second list and the first is a statement of today's plan."],
  ["qa-market.mjs", "An evidence walk against a production build: it opens the page under an English cookie and a Simplified Chinese cookie and compares the painted arithmetic against the two catalogues it was written around — the claims under test are the DOM's own figures, which script-variant glyphs do not change; zh-TW holds this tree's same key set and is held by the source-side gates (completeness, tokens, ICU parity), not by a per-locale browser rebuild that triples the walk's runtime."],
  ["qa-arabic-rtl-walk.mjs", "A live-tier, Arabic-first production walk for the RTL milestone's item 6. It drives the page under `fo_locale=ar` on a freshly seeded disposable PostgreSQL and asserts `<html dir=\"rtl\">`, Arabic glyphs in the served body text and zero `MISSING_MESSAGE` entries — the Chinese-language sibling studies are already carried by `visual-qa.mjs` and `qa-market.mjs` on their own planes, and zh/zh-TW's presence on this page is held by the source-side gates on the same tree; this walk does not pretend to cover them."],
  ["visual-qa.mjs", "The same rule for the flagship walks: two cookie languages by design — the English fallback and the zh translation — because the claims are claims about the painted page's catalogue values in those two; a Traditional Chinese pass would triple a production-build browser walk to re-prove glyph shapes, while the script-variant catalogue is held by the source-side gates on the plane between builds."],
  ["qa-baseline-gates.mjs", "A behavioural witness for the freshness and population-floor gates: it builds scratch catalogues to prove the gates' failure paths (stale key, deleted key, parity break, unreadable baseline) — deliberately minimal triples of en/zh/zh-TW, because the gates under test judge exactly those Chinese-pair populations and nothing this plane could show about the question the shipped `ar.json` answers."],
]);

const SITE_LEDGER = new Map([
  ["qa-key-drift.mjs::for (locale)::zh,zh-TW", "The drift rule compares a key's two translated spellings against each other; English is the side the candidate comes from, so the loop names the two sides it compares rather than the population the file loads."],
  ["qa-locale-content.mjs::for (locale)::zh,zh-TW", "Finds keys that exist in one translated catalogue and not in English. The two lists are the two translations this tree has; the day `ar.json` ships this loop is the first thing that must widen, and §41 counted it as the debt this census now holds."],
  ["qa-locale-fallback.mjs::zhTw::zh-TW", "A second, deliberately narrower claim beside the main loop: Traditional Chinese keeps its own simplified character list, so this read is about `zh-TW` alone and the fallback rule above still walks every catalogue."],
  ["qa-token-gates-witness.mjs::for (locale)::zh,zh-TW", "Fixture arm E: the two files this witness deletes to build a plane where only the fallback ships. It chooses nothing about the real tree — the arm's own prediction names the population it produces."],
  ["qa-token-gates-witness.mjs::noLocales::zh,zh-TW", "The same arm's fixture builder, naming the catalogues it removes so the plane ships one. Charged as data by the census; listed here because the shape is identical to a population site."],
  ["qa-translation-quality-witness.mjs::identicalExpected::ar,he,zh,zh-TW", "The identical-to-English count excludes English by definition — the gate's identical-to-English rule judges the translated catalogues' copies of the English text, and English has nothing to compare itself against; `existsSync` skips any of the four that does not ship on the plane yet."],
  ["qa-translation-quality-witness.mjs::for (locale)::ar,he,zh,zh-TW", "The same loop's fixture-side counterpart: the plane carries the translated catalogues and no English side is ever counted, because every message there matches itself. `existsSync` skips any of the four that does not ship on the plane yet."],
  ["qa-token-gates-witness.mjs::loseArFloor::ar,zh,zh-TW", "Arm A2: the plane's definer is rewritten to drop only the `ar: 0` floor line, because the arm witnesses the floor mechanism itself — a byte-copy `ar.json` with no recorded floor must red `DRIFT_FLOORS.ar`, and the shipped plane (the witness's own HEAD basis plus working tree) now carries the line this arm is designed to take away."],
  ["qa-translation-quality-witness.mjs::noCopy::en,zh,zh-TW", "Fixture arm C: a three-catalogue plane built from the shipped set only, so the Arabic-script arm judges the one planted message instead of 4218 shipped Arabic messages — the arm's name now spans the copies the three arms share."],
  ["qa-translation-quality-witness.mjs::realArabic::en,zh,zh-TW", "Fixture arm D: the same minimal three-catalogue plane with one Arabic room added for the arm's own message — the §40-style minimal plane, and the shipped `ar.json` adds no signal to an arm that asserts a two-message population."],
  ["qa-translation-quality-witness.mjs::hebrew::en,zh,zh-TW", "Fixture arm E: the same minimal plane with one Hebrew room — the arm needs the Hebrew-script verdict alone, and the shipped tree's Arabic rules are judged elsewhere; the arm is not about the shipped population."],
  ["qa-key-drift.mjs::.map::zh,zh-TW", "The drift rule compares a key's two translated spellings against each other; English is the side the candidate comes from, so the map names the two sides it compares, exactly as the for-loop beside it does."],
  ["qa-locale-content.mjs::localeOnlyKeys::zh,zh-TW", "The locale-only-keys comparison asks which keys exist in one translated catalogue and not in English; the two lists are the two translations this tree ships, and the day `ar.json` lands this set is the first thing that must widen — §41's named debt, the same as the loop beside it."],
  ["qa-key-drift-witness.mjs::synthetic::ar,en,zh,zh-TW", "Fixture arm D: the synthetic plane is built from the shipped catalogues only, holding two namespaces of byte-identical sentences so the gate's drift ceilings have population to judge; a synthetic `ar` adds nothing this arm can read, and its prediction names the four it deals with — `he` does not ship, so it stays out."],
  ["qa-metadata-title.mjs::.every::zh,zh-TW", "The tab-key check asks whether the title differs from English in each translation. Its two tags are the two translations that exist; the file's own population comes from the discovery line above."],
  ["qa-token-gates-witness.mjs::BASE::en,zh,zh-TW", "The committed basis every fixture plane derives from: HEAD's shipped catalogues, read with `git show HEAD:apps/web/messages/<locale>` — a dirty worktree would inherit another lane's debt, and an `ar` catalogue is not on HEAD yet, so the basis names the three that are."],
  ["qa-token-gates-witness.mjs::aEligible::en", "Arm A's prediction: the shared-value count is derived from the *English* plane of the byte-copy fixture, whose names are the identical keys an `ar` byte copy must red; the filter exempts the same tokens and short values the drift gate's lenient rule exempts."],
]);

const FILE_ROW_CEILING = FILE_LEDGER.size;
const SITE_ROW_CEILING = SITE_LEDGER.size;
const ADMISSION_FLOOR = census.length;
const DERIVED_FLOOR = census.filter((c) => c.derived).length;

const siteKey = (file, site) => `${file}::${site.label}::${[...site.toks].sort().join(",")}`;
const narrowOf = (entry) => entry.sites.filter((s) => entry.universe.some((t) => !s.toks.includes(t)));

const fileFindings = [];
const siteFindings = [];
const subsetReaders = [];
for (const entry of census) {
  if (entry.derived) continue;
  const missing = shipped.filter((locale) => !entry.universe.includes(locale));
  if (entry.universe.length > 1) {
    if (missing.length && !FILE_LEDGER.has(entry.name))
      fileFindings.push(`${entry.name} (${entry.shape} [${entry.universe.join(",")}]) does not name ${missing.map((m) => `${m}.json`).join(", ")}`);
  } else if (missing.length) {
    subsetReaders.push(`${entry.name} reads ${entry.universe.join(", ") || "no catalogue this census can attribute"}`);
  }
  for (const site of narrowOf(entry))
    if (!FILE_LEDGER.has(entry.name) && !SITE_LEDGER.has(siteKey(entry.name, site)))
      siteFindings.push(`${entry.name} L${site.ln} ${site.label} = [${site.toks.join(",")}] is narrower than the file's [${entry.universe.join(",")}]`);
}

const staleFiles = [...FILE_LEDGER.keys()].filter((name) => !census.some((c) => c.name === name));
const siteKeysNow = new Set(census.flatMap((c) => c.sites.map((s) => siteKey(c.name, s))));
const staleSites = [...SITE_LEDGER.keys()].filter((key) => !siteKeysNow.has(key));

check(
  "the census admits every script that reaches into messages/, by how it reads",
  census.length >= ADMISSION_FLOOR,
  `${census.length} of ${scriptFiles.length} scripts in ${basename(SCRIPTS)}/ load catalogues and ${scriptFiles.length - census.length} name no messages path; admitted floor ${ADMISSION_FLOOR}, may only rise — ${census.filter((c) => c.derived).length} derive the population from the directory, ${census.filter((c) => !c.derived && c.sites.length).length} name it in their own source, ${census.filter((c) => c.shape === "targeted").length} read a single locale directly`,
);

check(
  "every catalogue that ships is inside the population of every script that names one",
  fileFindings.length === 0,
  fileFindings.length
    ? `${fileFindings.length} charge(s): ${fileFindings.slice(0, 5).join(" | ")}${fileFindings.length > 5 ? ` | … (+${fileFindings.length - 5})` : ""}`
    : `${shipped.length} shipped catalogue(s) [${shipped.join(", ")}] against ${census.filter((c) => c.shape !== "derived").length} non-derived script(s); ${[...FILE_LEDGER.keys()].filter((n) => census.some((c) => c.name === n)).length} hold a file row and ${census.filter((c) => c.shape === "named").length} name the whole shipped set`,
);

check(
  "no site inside a loading script iterates a narrower list than the script loads, unless a row says why",
  siteFindings.length === 0,
  siteFindings.length
    ? `${siteFindings.length} unexcused site(s): ${siteFindings.join(" | ")}`
    : `${census.reduce((n, c) => n + narrowOf(c).length, 0)} narrower site(s) read, every one on the site ledger; ${siteFindings.length} unexcused`,
);

check(
  "the count of scripts that read the directory rather than name it may only rise",
  census.filter((c) => c.derived).length >= DERIVED_FLOOR,
  `${census.filter((c) => c.derived).length} derived of ${census.length} loading scripts; floor ${DERIVED_FLOOR} — the derived set is ${census.filter((c) => c.derived).map((c) => c.name.replace(/^qa-|\.mjs$/g, "")).join(", ")}`,
);

check(
  "every ledger row is still true of the file it names, and the ceilings may only fall",
  staleFiles.length === 0 && staleSites.length === 0 && FILE_LEDGER.size <= FILE_ROW_CEILING && SITE_LEDGER.size <= SITE_ROW_CEILING,
  staleFiles.length || staleSites.length
    ? `stale row(s): ${[...staleFiles, ...staleSites].join(" | ")} — the site or file it excuses is gone, so the debt is paid and the row must go`
    : `${FILE_LEDGER.size} file row(s) (ceiling ${FILE_ROW_CEILING}) + ${SITE_LEDGER.size} site row(s) (ceiling ${SITE_ROW_CEILING}); shortest reason ${Math.min(...[...FILE_LEDGER.values(), ...SITE_LEDGER.values()].map((r) => r.length))} characters`,
);

const unplanned = [];
for (const entry of census)
  for (const site of entry.sites)
    for (const t of site.unplanned) unplanned.push(`${entry.name} L${site.ln} ${site.label} names ${t}`);
check(
  "no population site names a locale tag the project has not planned",
  unplanned.length === 0,
  unplanned.length
    ? `${unplanned.length} site(s): ${unplanned.join(" | ")}`
    : `the planned set is [${[...PLANNED].join(", ")}], stated once in this file; ${census.reduce((n, c) => n + c.sites.length, 0)} site(s) read, ${dataSites} further locale literal(s) that are fixture content or table keys and were counted, not judged`,
);

if (process.argv.includes("--census")) {
  console.log(`\nCENSUS  ${census.length} scripts that load catalogues; ${shipped.length} shipped [${shipped.join(", ")}]`);
  for (const entry of census) {
    const missing = shipped.filter((l) => !entry.universe.includes(l));
    console.log(
      `  ${entry.name.padEnd(34)} ${entry.shape.padEnd(9)} universe=[${entry.universe.join(",")}] ` +
        `miss=${missing.length ? missing.join(",") : "-"} sites=${entry.sites.length}` +
        `${FILE_LEDGER.has(entry.name) ? " [file row]" : ""}`,
    );
    for (const s of entry.sites)
      console.log(
        `      L${String(s.ln).padStart(4)} ${s.kind.padEnd(6)} ${s.label} = [${s.toks.join(",")}]` +
          `${s.unplanned.length ? ` UNPLANNED[${s.unplanned.join(",")}]` : ""}${SITE_LEDGER.has(siteKey(entry.name, s)) ? " [site row]" : ""}`,
      );
  }
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  for (const f of failed) console.log(`  FAILED  ${f.name}`);
  process.exit(1);
}

const silent = census.filter((c) => !c.derived && !c.sites.some((s) => s.toks.includes("ar") || s.toks.includes("he")));
console.log(
  `\nSILENT  ${silent.length} script(s) name no unshipped locale anywhere, so a fourth catalogue would reach none of their rules: ` +
    `${silent.map((c) => c.name).join(", ") || "(none)"} — today that is a plan, not a defect: every shipped catalogue is named by every one of them. ` +
    `The day an unplanned one ships, these are the files whose green line speaks about a population they wrote out by hand.`,
);
console.log(
  `NOT JUDGED  ${dataSites} locale literal(s) that select nothing (fixture content and CLDR table keys), ` +
    `${scriptFiles.length - census.length} script(s) that never reach into messages/, and ${census.filter((c) => c.shape === "unmeasured").length} loading script(s) ` +
    `whose population this census could not attribute to a site — it claims nothing about any of them.`,
);
