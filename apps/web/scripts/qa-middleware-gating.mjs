#!/usr/bin/env node
/*
Who gates the gate: `middleware.ts` decides which routes a signed-out reader may reach, and this file asks that
decision of every page in the app. It loads the shipped `isProtected` itself — the source region is transpiled
with the repo's own TypeScript and called — so a change to the *matching* logic (not just the lists it reads)
moves this verdict. No server, no browser, no port: it belongs beside the other static gates.

The defect it found, and the reason it exists: `PROTECTED_PREFIXES` matches by prefix, so listing `/video` and
`/portfolio` reached straight down into `/video/shared/<token>` and `/portfolio/shared/<token>` — the two pages
whose entire design is a link handed to a person with no account. `PUBLIC_EXCEPTIONS` was an exact-set lookup, so
it could never answer for a page one dynamic segment deep. A live read of both surfaces, in all three locales,
returned **HTTP 307 to `/login`** while `/tactics/shared/<token>` — same design, under a prefix nobody listed —
returned 200. `shape-D live read: 18 green, 6 red of 24`, and every red was one of those two pages.

Checks, each able to refuse on its own:
  1  the middleware region compiled and `isProtected` is callable            — a judge that never ran reads as "no problem found"
  2  the page population is non-empty and contains the three share routes    — the subject must exist before its fate
  3  both spellings of "this page needs a session" fire on some page         — one spelling silently mis-files the pages that use the other
  4  MISGATED: a page with no path to a session is gated                     — the class that bounced the share readers
  5  EXEMPTED-WHILE-PRIVATE: a page under a listed prefix is exempt but gates itself — exemption must not cost a signed-in reader their token
  6  STALE-EXEMPTION: an exception entry matches no page                     — a dead exemption is a hiding place for the next route given that name

Run on the current tree it is green; witness arms in `.scratch/` (see the record) each turn one clause red and
name the route the clause is about.
*/

import { readdirSync, readFileSync } from "node:fs";
import { join, sep } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

// `fileURLToPath`, never `URL.pathname`: this repo's own path is non-ASCII, and the pathname form comes back
// percent-encoded (`…/%E8%B6%B3%E7%90%83…`), which no filesystem call resolves.
const WEB = fileURLToPath(new URL("..", import.meta.url));
const MIDDLEWARE = join(WEB, "middleware.ts");
const APP_DIR = join(WEB, "app");

const failures = [];
const note = (row) => failures.push(row);

/* 1 — load the shipped decision, not a paraphrase of it. */
const src = readFileSync(MIDDLEWARE, "utf8");
const start = src.indexOf("const PROTECTED_PREFIXES");
const stop = src.indexOf("\nfunction preferredLocale");
if (start < 0 || stop < 0 || stop < start) {
  console.error(`FATAL: could not slice the decision region out of middleware.ts (start=${start}, stop=${stop}) — the gate read nothing`);
  process.exit(1);
}
const region = src.slice(start, stop);
const compiled = ts.transpileModule(region, { compilerOptions: { target: ts.ScriptTarget.ES2020 } }).outputText;
let isProtected;
let PUBLIC_EXCEPTIONS;
try {
  isProtected = new Function(`${compiled}; return isProtected;`)();
  PUBLIC_EXCEPTIONS = new Function(`${compiled}; return [...PUBLIC_EXCEPTIONS];`)();
} catch (err) {
  console.error(`FATAL: middleware's own decision region did not compile to a callable: ${err.message}`);
  process.exit(1);
}
if (typeof isProtected !== "function") {
  console.error("FATAL: isProtected was not a function — check 1 has no judge to ask");
  process.exit(1);
}

/* 2 — the population: every page file, with Next's route-group folders stripped and dynamic segments filled. */
const pageFiles = [];
(function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (entry.name === "page.tsx") pageFiles.push(p);
  }
})(APP_DIR);

const routeOf = (file) => {
  const rel = file.slice(APP_DIR.length).split(sep).join("/");
  const segments = rel.replace(/\\/g, "/").replace(/(^|\/)page\.tsx$/, "$1").replace(/(^|\/)\([^/]+\)/g, "$1").split("/").filter(Boolean);
  return `/${segments.map((s) => (s.startsWith("[") ? "sample-token" : s)).join("/")}` || "/";
};

const routes = pageFiles.map(routeOf);
const SHARE_ROUTES = ["/portfolio/shared/sample-token", "/tactics/shared/sample-token", "/video/shared/sample-token"];
const missing = SHARE_ROUTES.filter((r) => !routes.includes(r));
if (routes.length < 40) note(`POPULATION ${routes.length} pages scanned — below the 40 this census was written against, so a narrowed walk is reading too little`);
for (const r of missing) note(`POPULATION ${r} is not in the walked pages — the gate cannot judge a surface it never found`);

/* 3 — the two spellings of "this page needs a session", each of which must actually fire. */
const bodies = pageFiles.map((file) => ({ file: file.slice(WEB.length + 1), route: routeOf(file), src: readFileSync(file, "utf8") }));
const readsSession = (b) => /\bcurrentUser\(/.test(b.src);
const bounces = (b) => /redirect\(\s*["'`]\/login/.test(b.src);
const sessionReaders = bodies.filter(readsSession);
const bouncers = bodies.filter(bounces);
if (!sessionReaders.length) note("PREDICATE no page matched `currentUser()` — the first spelling of a session read has no witness, so pages using only it are invisible");
if (!bouncers.length) note("PREDICATE no page matched `redirect(\"/login…\")` — the second spelling has no witness, which is how /progress, /history and /settings were mis-filed as public");
// The two spellings are not the same set, and the census must say so out loud: /progress redirects on the API's
// 401 without ever naming currentUser(), /club reads the session and never bounces by that literal.
const onlyBounce = bouncers.filter((b) => !readsSession(b));
if (!onlyBounce.length) note("PREDICATE every page that redirects to /login also calls currentUser() — the 401-only shape has no witness on this plane");

/* 4 + 5 — ask the shipped function about each page. */
const listedPrefixes = () => {
  const m = /PROTECTED_PREFIXES = \[([\s\S]*?)\]/.exec(region);
  return m ? [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]) : [];
};
const prefixes = listedPrefixes();
if (!prefixes.length) note("PARSE PROTECTED_PREFIXES read 0 entries — an empty protected list would make every later check green for the wrong reason");

let gatedCount = 0;
let privateCount = 0;
for (const b of bodies) {
  const isPrivate = readsSession(b) || bounces(b);
  const decided = isProtected(b.route);
  if (decided) gatedCount += 1;
  if (isPrivate) privateCount += 1;
  // The prefix must be matched the way isProtected matches it. Arm A4 showed the cost of getting this wrong: matching
  // only `${p}/` meant the route `/club` — the prefix itself — had no evidence, and exempting the whole club area
  // from the middleware looked like a one-page change instead of the nine-page change it is.
  const under = prefixes.filter((p) => b.route === p || b.route.startsWith(`${p}/`));
  // 4 — a page that never routes a reader to a session is gated away from the reader it was written for.
  if (!isPrivate && decided) {
    note(`MISGATED ${b.route} (${b.file}) — reads no session and has no path to /login, yet the shipped isProtected() gates it`);
  }
  // 5 — an exemption that swallows a session page costs a signed-in reader the forwarded/refreshed token.
  if (isPrivate && decided === false && under.length) {
    note(`EXEMPTED-WHILE-PRIVATE ${b.route} (${b.file}) — under listed prefix ${under.join(",")} but exempt, so its expired token is never refreshed mid-render`);
  }
}

/* 6 — every exception must answer for at least one page that exists. */
for (const exception of PUBLIC_EXCEPTIONS) {
  const hits = routes.filter((r) => r === exception || r.startsWith(`${exception}/`));
  if (!hits.length) note(`STALE-EXEMPTION ${exception} matches no page route (${routes.length} scanned) — a name with no referent is a hiding place for the next route given it`);
}

console.log(`middleware gating census: ${routes.length} pages | ${privateCount} read or redirect to a session | ${gatedCount} gated by isProtected()`);
console.log(`exceptions in force: ${PUBLIC_EXCEPTIONS.join(", ")}`);
if (failures.length) {
  for (const f of failures) console.error("  RED " + f);
  console.error(`middleware gating census: ${failures.length} problem rows`);
  process.exit(1);
}
console.log("middleware gating census: green");
