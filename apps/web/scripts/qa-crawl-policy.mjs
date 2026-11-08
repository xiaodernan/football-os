#!/usr/bin/env node
/*
Three files decide what a crawler may see, and until this gate existed each of them only *described* the others in a
comment. `middleware.ts` says which routes need a session. `app/robots.ts` says which prefixes a crawler may not
enter, and excepts one path from a disallowed prefix. `app/sitemap.ts` says which routes are offered for indexing.
Each page may also declare its own `robots: { index: … }`. The rules that tie them together are prose in all four
places — "a session-gated route is disallowed rather than offered to the crawl as a redirect chain"
(robots.ts), "the sitemap cannot advertise a slug that no page answers" (sitemap.ts), "a longer `Allow` match wins"
(robots.ts) — and prose moves when a prefix is added only if somebody remembers it.

Measured by this walk on the tree it landed on: 59 pages, 34 gated, 10 advertised, 30 declaring `index:false`.
**8 of the 34 gated pages were in no disallowed prefix at all** — `/agents`, the four `/graph` pages and the three
`/simulation/aggregates` pages. Seven of those eight carry a self-declared `noindex`, and that declaration is inert:
a signed-out fetch — which is the only fetch a crawler makes — answers 307 to `/login`, and a redirect response has
no `<head>` for a bot to read. The privacy of those surfaces rested on a meta tag behind a door the bot never opens.
`/agents` declared nothing at all. The fix is the three prefixes; this file is the rule that keeps them listed.

Checks, each able to refuse on its own:
  1  the walk reads all three decisions and the population floors hold  — a blind walk would grade an empty set and report "0 problems"
  2  GATED ⇒ DISALLOWED                    — every route `isProtected` refuses must be closed to the crawl too; the defect class above
  3  ADVERTISED ⇒ NOT GATED                — the sitemap's own promise, static half: the map may not point at a redirect
  4  ADVERTISED under a disallowed prefix ⇒ a strictly longer Allow covers it — and at least one page exercises that mechanism
  5  ADVERTISED ⇒ no self-declared `index:false` — one route cannot be both offered for indexing and told by its own bytes not to be indexed
  6  every ALLOWED entry still earns its place: it matches a page that is reachable *and* under a disallowed prefix — an exemption for a door that was never locked is a hiding place for the next route given that name
  7  disallowed prefixes that match no page are exactly the non-page surfaces, each re-proved from its own spelling  — today `/api/`
*/

import { readdirSync, readFileSync } from "node:fs";
import { join, resolve, sep } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

// `fileURLToPath`, never `URL.pathname`: this repo's own path is non-ASCII and the pathname form comes back
// percent-encoded, which no filesystem call resolves. `QA_CRAWL_WEB` points the same walk at an arm plane.
const WEB = resolve(process.env.QA_CRAWL_WEB ?? fileURLToPath(new URL("..", import.meta.url)));
const APP = join(WEB, "app");
const MIDDLEWARE = join(WEB, "middleware.ts");

// Floors measured on the population at this ref. A walk that narrows itself, or a decision list emptied by an
// edit, goes red here before any of the rules below can be graded on a set too small to fail.
const FLOOR_PAGES = 59;
const FLOOR_GATED = 34;
const FLOOR_ADVERTISED = 10;
const FLOOR_NOINDEX = 30;
const FLOOR_DISALLOWED = 20;

const fail = (m) => {
  console.error(`FATAL: ${m}`);
  process.exit(2);
};

/** Compile a region of a shipped file and hand back the value of one of its declarations. */
const regionOf = (file, startNeedle, stopNeedle) => {
  const src = readFileSync(file, "utf8");
  const start = src.indexOf(startNeedle);
  const stop = src.indexOf(stopNeedle, start + startNeedle.length);
  if (start < 0 || stop < 0) fail(`${file}: could not slice between ${JSON.stringify(startNeedle)} and ${JSON.stringify(stopNeedle)} (start=${start}, stop=${stop}) — the gate read nothing`);
  return ts.transpileModule(src.slice(start, stop), { compilerOptions: { target: ts.ScriptTarget.ES2020 } }).outputText;
};

const take = (compiled, name) => {
  try {
    return new Function(`${compiled}; return ${name};`)();
  } catch (err) {
    fail(`${name} could not be evaluated out of the shipped bytes: ${err.message}`);
  }
};

const mwRegion = regionOf(MIDDLEWARE, "const PROTECTED_PREFIXES", "\nfunction preferredLocale");
const isProtected = take(mwRegion, "isProtected");
const PROTECTED_PREFIXES = take(mwRegion, "[...PROTECTED_PREFIXES]");
const PUBLIC_EXCEPTIONS = take(mwRegion, "[...PUBLIC_EXCEPTIONS]");
if (typeof isProtected !== "function") fail("middleware's isProtected was not a function — check 2 has no judge to ask");

const robRegion = regionOf(join(APP, "robots.ts"), "const DISALLOWED", "export default function robots");
const DISALLOWED = take(robRegion, "[...DISALLOWED]");
const ALLOWED = take(robRegion, "[...ALLOWED]");

const smRegion = regionOf(join(APP, "sitemap.ts"), "const PUBLIC", "type Row");
const PUBLIC = take(smRegion, "[...PUBLIC]");

/**
 * A page can carry the noindex decision without writing it: `sharedMetadata` sets `robots` itself, so the share
 * pages built through it have no `robots:` literal for the walk below to find. Counting only literals would make
 * the census shrink every time a page hands the decision to the helper — the safer page would read as the
 * unprotected one. So the helper is loaded and asked, and a page inherits the declaration only while the shipped
 * module really returns one.
 */
const SITE_TS = join(WEB, "lib", "site.ts");
const sharedRobots = (() => {
  const compiled = ts.transpileModule(readFileSync(SITE_TS, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
  let site;
  try {
    site = new Function("exports", `${compiled}\nreturn exports;`)({});
  } catch (err) {
    fail(`${SITE_TS} could not be evaluated: ${err.message}`);
  }
  if (typeof site.sharedMetadata !== "function") fail(`${SITE_TS} exports no sharedMetadata — a page that delegates its robots decision has no judge to ask`);
  return site.sharedMetadata({ title: "gate", description: "gate", sharePath: "/tactics/shared/abc123", canonicalPath: "/tactics" }).robots;
})();

const inheritsSharedRobots = (file, src) => {
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.ESNext, true, ts.ScriptKind.TSX);
  let called = false;
  let imported = false;
  const walkNode = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "sharedMetadata") called = true;
    // A local function of the same name would satisfy the call test while returning whatever it liked.
    if (ts.isImportDeclaration(node) && /(^|\/)lib\/site$/.test(node.moduleSpecifier.text ?? "")
      && ts.isNamedImports(node.importClause?.namedBindings)
      && node.importClause.namedBindings.elements.some((e) => e.name.text === "sharedMetadata")) imported = true;
    node.getChildren(sf).forEach(walkNode);
  };
  walkNode(sf);
  return called && imported;
};

/* ---- the page population, with each page's own robots declaration read structurally ---- */
const pageFiles = [];
(function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (entry.name === "page.tsx") pageFiles.push(p);
  }
})(APP);

const routeOf = (file) => {
  const rel = file.slice(APP.length).split(sep).join("/").replace(/(^|\/)page\.tsx$/, "$1").replace(/(^|\/)\([^/]+\)/g, "$1");
  return "/" + rel.split("/").filter(Boolean).map((s) => (s.startsWith("[") ? "sample-token" : s)).join("/");
};

/**
 * `robots:` on a page is one decision, and a regex that stops at the first `}` reads a nested object as a smaller
 * one — so the walk finds the property and asks its initializer what it says. A value that is not an object literal
 * (a computed expression, a string like "none") is reported as opaque rather than silently counted as a declaration.
 */
const robotsOf = (file, src) => {
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.ESNext, true, ts.ScriptKind.TSX);
  let out = null;
  const readBool = (node) =>
    node === undefined ? undefined
      : node.kind === ts.SyntaxKind.TrueKeyword ? true
        : node.kind === ts.SyntaxKind.FalseKeyword ? false
          : "opaque";
  const walkNode = (node) => {
    if (ts.isPropertyAssignment(node) && node.name.getText() === "robots") {
      if (!ts.isObjectLiteralExpression(node.initializer)) {
        // A declaration the walk cannot read is refused, not skipped: `robots: computedFlag` would otherwise drop
        // the page out of check 5's population and quietly narrow the rule it is supposed to be graded against.
        out = { props: {}, opaque: true };
        return;
      }
      const props = {};
      let opaque = false;
      for (const p of node.initializer.properties) {
        if (ts.isShorthandPropertyAssignment(p)) { props[p.name.getText()] = true; continue; }
        if (!ts.isPropertyAssignment(p)) { opaque = true; continue; }
        props[p.name.getText()] = readBool(p.initializer);
        if (props[p.name.getText()] === "opaque") opaque = true;
      }
      out = { props, opaque };
    }
    node.getChildren(sf).forEach(walkNode);
  };
  walkNode(sf);
  return out;
};

const pages = pageFiles.map((f) => {
  const src = readFileSync(f, "utf8");
  const route = routeOf(f);
  const rb = robotsOf(f, src);
  const inherited = rb === null && inheritsSharedRobots(f, src);
  const match = (list) => list.filter((p) => route === p || route.startsWith(`${p}/`));
  const longest = (list) => list.reduce((m, x) => (x.length > m.length ? x : m), "");
  const dis = match(DISALLOWED);
  const all = match(ALLOWED);
  return {
    rel: f.slice(WEB.length + 1).split(sep).join("/"),
    route,
    gated: isProtected(route),
    declaresRobots: rb !== null,
    inheritedRobots: inherited,
    opaqueRobots: rb?.opaque ?? false,
    noindex: rb ? String(rb.props.index) === "false" : (inherited && String(sharedRobots?.index) === "false"),
    disallowed: dis,
    allowed: all,
    // The standard robots.ts cites: the longer pattern wins, so an Allow beats a Disallow only when it is longer.
    covered: all.length > 0 && longest(all).length > longest(dis).length,
    advertised: PUBLIC.some((e) => e.path === route),
  };
});

/* ---- the checks ---- */
let passed = 0;
let checks = 0;
const failed = [];
const check = (label, ok, detail) => {
  checks += 1;
  if (ok) { passed += 1; return; }
  failed.push(`${label}${detail ? ` — ${detail}` : ""}`);
  console.log(`FAIL ${label}${detail ? ` — ${detail}` : ""}`);
};

check(`1 the walk reads the three decisions and the population floors hold (pages>=${FLOOR_PAGES}, gated>=${FLOOR_GATED}, advertised>=${FLOOR_ADVERTISED}, noindex>=${FLOOR_NOINDEX}, disallowed>=${FLOOR_DISALLOWED})`,
  pages.length >= FLOOR_PAGES
    && PROTECTED_PREFIXES.length > 0 && PUBLIC_EXCEPTIONS.length > 0
    && DISALLOWED.length >= FLOOR_DISALLOWED && ALLOWED.length > 0 && PUBLIC.length >= FLOOR_ADVERTISED
    && pages.filter((p) => p.gated).length >= FLOOR_GATED
    && pages.filter((p) => p.advertised).length >= FLOOR_ADVERTISED
    && pages.filter((p) => p.noindex).length >= FLOOR_NOINDEX,
  `pages=${pages.length} gated=${pages.filter((p) => p.gated).length} advertised=${pages.filter((p) => p.advertised).length} noindex=${pages.filter((p) => p.noindex).length} (written ${pages.filter((p) => p.noindex && p.declaresRobots).length}, inherited ${pages.filter((p) => p.noindex && p.inheritedRobots).length}) disallowed=${DISALLOWED.length} allowed=${ALLOWED.length}`);

const ungated = pages.filter((p) => p.gated && p.disallowed.length === 0);
check(`2 GATED but not DISALLOWED: a signed-out reader is redirected, and the crawler is told nothing (${ungated.length})`,
  ungated.length === 0,
  ungated.map((p) => `${p.route} (${p.rel}) noindex=${p.noindex}`).join(", "));

const advertisedGated = pages.filter((p) => p.advertised && p.gated);
check("3 ADVERTISED but gated: the map points a crawler at a redirect chain", advertisedGated.length === 0,
  advertisedGated.map((p) => p.route).join(", "));

const advertisedBlocked = pages.filter((p) => p.advertised && p.disallowed.length > 0);
const blockedWithoutAllow = advertisedBlocked.filter((p) => !p.covered);
check("4a ADVERTISED under a disallowed prefix without a strictly longer Allow", blockedWithoutAllow.length === 0,
  blockedWithoutAllow.map((p) => `${p.route} disallow=${JSON.stringify(p.disallowed)} allow=${JSON.stringify(p.allowed)}`).join(", "));
check(`4b the Allow-wins mechanism has a carrier (>= 1 advertised page sits under a disallowed prefix)`,
  advertisedBlocked.length >= 1, `found ${advertisedBlocked.length}: the clause would grade an empty set`);

const advertisedNoindex = pages.filter((p) => p.advertised && p.noindex);
check("5 ADVERTISED and self-declared noindex: one route, two opposite instructions", advertisedNoindex.length === 0,
  advertisedNoindex.map((p) => p.route).join(", "));

const staleAllow = ALLOWED.filter((a) => !pages.some((p) => p.allowed.includes(a) && !p.gated));
check("6 STALE ALLOW: an exception that covers no reachable page", staleAllow.length === 0,
  staleAllow.map((a) => `${a} — no page under it is ungated`).join(", "));

// The one non-page prefix in the list, re-proved from its own spelling on every run: `/api/` closes the JSON proxy,
// which has no `page.tsx` for a walk to find. Anything else joining it is a disallow aimed at a route that no longer exists.
const NOT_A_PAGE = ["/api/"];
const orphanDisallowed = DISALLOWED.filter((d) => !pages.some((p) => p.disallowed.includes(d)));
const ledgeredOnly = orphanDisallowed.every((d) => NOT_A_PAGE.includes(d) && d.startsWith("/api"));
const ledgerStillOrphans = NOT_A_PAGE.every((d) => orphanDisallowed.includes(d));
check(`7 every disallowed prefix that matches no page is a ledgered non-page surface (${orphanDisallowed.join(", ") || "none"})`,
  ledgeredOnly && ledgerStillOrphans,
  `orphans=${JSON.stringify(orphanDisallowed)} ledger=${JSON.stringify(NOT_A_PAGE)} nonApi=${JSON.stringify(orphanDisallowed.filter((d) => !d.startsWith("/api")))}`);

const opaque = pages.filter((p) => p.opaqueRobots);
check("8 every page's robots declaration is readable as booleans", opaque.length === 0,
  opaque.map((p) => `${p.route} (${p.rel})`).join(", "));

console.log(`CHECKS passed=${passed} total=${checks} failed=${checks - passed}`);
console.log(`  population=${pages.length} pages | gated=${pages.filter((p) => p.gated).length} | advertised=${pages.filter((p) => p.advertised).length}`
  + ` | noindex=${pages.filter((p) => p.noindex).length} | disallowed=${DISALLOWED.length} (${DISALLOWED.length - orphanDisallowed.length} matching a page, ${orphanDisallowed.length} not)`);
if (process.env.QA_CRAWL_ROWS) {
  for (const p of pages) {
    console.log(`  ${p.route} gated=${p.gated ? "Y" : "-"} advertised=${p.advertised ? "Y" : "-"} noindex=${p.noindex ? "Y" : "-"}`
      + ` disallow=${p.disallowed.join("+") || "-"} allow=${p.allowed.join("+") || "-"}`);
  }
}
console.log(`ran qa-crawl-policy against ${WEB}`);
process.exitCode = failed.length ? 1 : 0;
