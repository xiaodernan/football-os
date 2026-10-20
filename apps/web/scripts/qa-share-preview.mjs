#!/usr/bin/env node
/*
§109 — a share link previews the page it points at, the card carries the picture its own tag promises, and the
picture is the project's.

Three files used to make this decision in isolation. `app/layout.tsx` declared a site-level `openGraph` block, the
three `/…/shared/<token>` pages declared `title` + `description` + `robots` and nothing else, and Next therefore
handed a reader who pasted a link into a chat the *site's* card: "FOOTBALL OS" over the tagline, for a page whose
whole purpose is one person's CV, board or clip. `docs/SEO_VERIFICATION.md` §3 recorded the second half honestly —
"No `og:image` / `twitter:image`. There is no licensed or project-authored image asset to point at" — while
`pageMetadata` had been printing `card: "summary_large_image"` on every indexed page since it landed, which is a
promise of a picture the site did not have.

Measured on the tree this gate landed on: **3 share pages**, none declaring an `openGraph` of its own. Two of them
(`tactics`, `video`) hand-wrote `title` + `description` + `robots`; the third (`portfolio`) already called
`sharedMetadata` — a helper **HEAD did not have**, which is the finding in
`docs/SHARE_PREVIEW_VERIFICATION.md` §109b: `cc0ad34` wired that page and committed the page only, so
`npx tsc --noEmit` over a clean `git archive HEAD` plane answers one error, `TS2305 … has no exported member
'sharedMetadata'`, and the site did not build. `public/og.png` did not exist either; the card string appeared twice
in the shipped bytes, both times in a helper, both times without an image. What fixed both is one helper that a page
cannot misuse — `sharedMetadata()` decides `noindex` and the parent canonical itself, so a caller cannot forget them
— and one asset rendered by `scripts/make_og_image.mjs` out of `lib/site.ts`, `app/icon.svg` and
`styles/globals.css`.

Checks, each able to refuse on its own:
  1  the walk finds the share population (>= FLOOR) and every page parsed   — a blind walk would grade an empty set and print "0 problems"
  2  each share page builds its metadata through `sharedMetadata`, imported from `lib/site.ts` — by its binding, not by a name that could be a local function
  3  the helper's own output names the *page*: og title/description are the page's, `og:url` is the share URL, the canonical is the parent, and the two are never the same bytes
  4  `noindex`/`nofollow` is the helper's decision, not the caller's — a share token is the credential
  5  both readers carry the picture: `openGraph.images` and `twitter.images` each hold one entry at the declared size
  6  no `summary_large_image` anywhere in the shipped bytes without an image behind it — graded by *calling* the helpers and by walking every hand-written `twitter` block in `app/`
  7  the asset answers: `public/og.png` exists, is a PNG, its IHDR says the size the metadata declares, and it is too big to be a placeholder
  8  the generator renders at the declared size and carries **no copy** of the wordmark or the tagline — it reads them out of `lib/site.ts`, so one author owns each sentence
  9  every canonical a share page declares is a static page the app answers, and no share path is advertised in the sitemap

Files only: no server, no browser, no port. The live half — that a built server serves `/og.png` and that a share
page's `<head>` carries the tags — is a `next build` + `next start` leg recorded in
`docs/SHARE_PREVIEW_VERIFICATION.md`, not a claim this file makes.
*/

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve, sep } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

// `fileURLToPath`, never `URL.pathname`: this repo's own path is non-ASCII and the pathname form comes back
// percent-encoded, which no filesystem call resolves. `QA_SHARE_WEB` points the same walk at an arm plane.
const WEB = resolve(process.env.QA_SHARE_WEB ?? fileURLToPath(new URL("..", import.meta.url)));
const APP = join(WEB, "app");
const SITE_TS = join(WEB, "lib", "site.ts");
const GENERATOR = resolve(WEB, "..", "..", "scripts", "make_og_image.mjs");

const FLOOR_SHARE_PAGES = 3;
// A 1200x630 card carrying a mark and two lines of type does not compress below this; a flat placeholder does.
const FLOOR_ASSET_BYTES = 10_000;

const die = (m) => {
  console.error(`FATAL: ${m}`);
  process.exit(2);
};
for (const [what, file] of [["lib/site.ts", SITE_TS], ["the card generator", GENERATOR], ["the page tree", APP]]) {
  if (!existsSync(file)) die(`${what} is missing at ${file} — the rule has nothing left to grade`);
}

/** Evaluate the shipped module, so every assertion below is about what the pages actually get, not about prose. */
const site = (() => {
  const compiled = ts.transpileModule(readFileSync(SITE_TS, "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
  }).outputText;
  return new Function("exports", `${compiled}\nreturn exports;`)({});
})();
const { SITE_NAME, SITE_TAGLINE, OG_IMAGE_PATH, OG_IMAGE_WIDTH, OG_IMAGE_HEIGHT, absolute, pageMetadata, sharedMetadata } = site;
for (const name of ["SITE_NAME", "SITE_TAGLINE", "OG_IMAGE_PATH", "OG_IMAGE_WIDTH", "OG_IMAGE_HEIGHT", "absolute", "pageMetadata", "sharedMetadata"]) {
  if (site[name] === undefined) die(`lib/site.ts exports no ${name} — this gate's subject disappeared`);
}
if (typeof pageMetadata !== "function" || typeof sharedMetadata !== "function") die("the two metadata helpers are not callable");

const sample = { title: "Shared Board", description: "A board one owner published by link." };
const built = sharedMetadata({ ...sample, sharePath: "/tactics/shared/abc123", canonicalPath: "/tactics" });
const indexed = pageMetadata({ ...sample, path: "/tactics" });

/* ---- the share population ---- */
const pages = [];
const walkApp = (dir) => {
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walkApp(p);
    else if (entry.name === "page.tsx") pages.push(p);
  }
};
walkApp(APP);
const sharePages = pages.filter((p) => p.split(sep).join("/").includes("/shared/"));

const relOf = (p) => p.slice(WEB.length + 1).split(sep).join("/");
const visit = (node, fn) => { fn(node); ts.forEachChild(node, (c) => visit(c, fn)); };

/** A page is wired through the helper only if it *imports* it from `lib/site.ts` — a local function of the same
 * name would otherwise satisfy a call-shape test while producing whatever it liked. */
const siteBinding = (sf, name) => sf.statements.some((st) => ts.isImportDeclaration(st)
  && /(^|\/)lib\/site$/.test(st.moduleSpecifier.text ?? "")
  && ts.isNamedImports(st.importClause?.namedBindings)
  && st.importClause.namedBindings.elements.some((e) => e.name.text === name));

const rows = sharePages.map((file) => {
  const src = readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.ESNext, true, ts.ScriptKind.TSX);
  let call = null;
  let declaresOwnOpenGraph = false;
  visit(sf, (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "sharedMetadata") call = node;
    if (ts.isPropertyAssignment(node) && node.name.getText() === "openGraph") declaresOwnOpenGraph = true;
  });
  const arg = call?.arguments[0];
  const propOf = (name) => (arg !== undefined && ts.isObjectLiteralExpression(arg)
    ? (arg.properties ?? []).find((q) => ts.isPropertyAssignment(q) && q.name.getText() === name)?.initializer : null);
  /** A page that does not declare a property answers null, and the checks below grade a missing declaration as a
   * missing declaration — not as a crash that hides every clause underneath it. `canonicalPath` is a page, so only
   * a plain string settles it; `sharePath` ends in the token, so its static part is the head before the first `${`,
   * which is exactly what "under its own route" means. */
  const textOf = (node) => (node !== null && node !== undefined && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? node.text : null);
  const headOf = (node) => (textOf(node) ?? (node !== null && node !== undefined && ts.isTemplateExpression(node) ? node.head.text : null));
  const spans = (node) => (node !== null && node !== undefined && ts.isTemplateExpression(node) ? node.templateSpans.length : 0);
  const share = propOf("sharePath");
  return {
    rel: relOf(file),
    diags: (sf.parseDiagnostics ?? []).length,
    imported: siteBinding(sf, "sharedMetadata"),
    usesHelper: call !== null,
    declaresOwnOpenGraph,
    shareHead: headOf(share),
    shareTail: spans(share),
    canonicalPath: textOf(propOf("canonicalPath")),
  };
});

/* ---- the checks ---- */
let passed = 0;
let checks = 0;
const failed = [];
const check = (label, ok, detail) => {
  checks += 1;
  if (ok) { passed += 1; return; }
  failed.push(label);
  console.log(`FAIL ${label}${detail ? ` — ${detail}` : ""}`);
};

check(`1 the walk reads the share population (>= ${FLOOR_SHARE_PAGES} pages under a shared/ segment of ${relOf(APP)}/)`,
  sharePages.length >= FLOOR_SHARE_PAGES, `found ${sharePages.length}: ${rows.map((r) => r.rel).join(", ")}`);
check("1b every share page parsed with no diagnostic", rows.every((r) => r.diags === 0),
  rows.filter((r) => r.diags).map((r) => `${r.rel}(${r.diags})`).join(", "));

for (const r of rows) {
  check(`2 ${r.rel} builds its metadata with sharedMetadata imported from lib/site.ts`,
    r.usesHelper && r.imported && !r.declaresOwnOpenGraph,
    `call=${r.usesHelper} import=${r.imported} hand-written-openGraph=${r.declaresOwnOpenGraph}`);
}

const og = built.openGraph ?? {};
const alt = built.alternates ?? {};
check("3 the card names the page: og title/description are the caller's, not the site's",
  og.title === sample.title && og.description === sample.description,
  `og.title=${JSON.stringify(og.title)} og.description=${JSON.stringify(og.description)}`);
check("3b the card points at the share URL and the canonical at the parent, and the two differ",
  og.url === absolute("/tactics/shared/abc123") && alt.canonical === absolute("/tactics") && og.url !== alt.canonical,
  `og.url=${og.url} canonical=${alt.canonical}`);
check("3c the site is still named on the card, as siteName rather than as the page's title",
  og.siteName === SITE_NAME && og.title !== SITE_NAME,
  `siteName=${JSON.stringify(og.siteName)} og.title=${JSON.stringify(og.title)}`);

check("4 the helper decides noindex/nofollow itself, so a caller cannot forget it",
  built.robots?.index === false && built.robots?.follow === false,
  `robots=${JSON.stringify(built.robots)}`);

const imagesOf = (block) => (block?.images ?? []);
const shapeOf = (list) => list.length === 1 && list[0].url === absolute(OG_IMAGE_PATH)
  && list[0].width === OG_IMAGE_WIDTH && list[0].height === OG_IMAGE_HEIGHT
  && typeof list[0].alt === "string" && list[0].alt.length > 0;
check(`5 openGraph.images carries the card at the declared ${OG_IMAGE_WIDTH}x${OG_IMAGE_HEIGHT}`,
  shapeOf(imagesOf(og)), JSON.stringify(og.images));
check("5b twitter.images carries it too — a scraper reads one tag or the other",
  shapeOf(imagesOf(built.twitter)), JSON.stringify(built.twitter.images));

/* Every promise of the large-image card in the shipped bytes: the two helpers, graded by calling them, and any
 * hand-written `twitter` block in app/, graded structurally. The graded count is printed so a rule that found
 * nothing cannot read as a rule that passed. */
const handWritten = [];
for (const file of pages) {
  const src = readFileSync(file, "utf8");
  if (!src.includes("summary_large_image")) continue;
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.ESNext, true, ts.ScriptKind.TSX);
  visit(sf, (node) => {
    if (!ts.isPropertyAssignment(node) || node.name.getText() !== "twitter") return;
    if (!ts.isObjectLiteralExpression(node.initializer)) { handWritten.push({ rel: relOf(file), paid: false }); return; }
    const images = (node.initializer.properties ?? []).find((q) => q.name?.getText() === "images");
    handWritten.push({ rel: relOf(file), paid: images !== undefined });
  });
}
const promises = [
  { where: "lib/site.ts:pageMetadata", paid: (indexed.twitter?.images ?? []).length > 0 },
  { where: "lib/site.ts:sharedMetadata", paid: (built.twitter?.images ?? []).length > 0 },
  ...handWritten,
];
check(`6 every summary_large_image card is paid for with an image (${promises.length} graded, ${handWritten.length} hand-written)`,
  promises.length >= 2 && promises.every((p) => p.paid),
  promises.filter((p) => !p.paid).map((p) => p.where).join(", "));

const asset = join(WEB, "public", OG_IMAGE_PATH.replace(/^\//, ""));
const ihdr = (() => {
  if (!existsSync(asset)) return null;
  const bytes = readFileSync(asset);
  if (bytes.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") return { notPng: true, bytes: bytes.length };
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20), bytes: bytes.length };
})();
check(`7 the card the metadata points at answers: ${relOf(asset)} is a PNG`,
  ihdr !== null && ihdr.notPng !== true, ihdr === null ? "no such file" : "not a PNG signature");
check(`7b its IHDR says ${OG_IMAGE_WIDTH}x${OG_IMAGE_HEIGHT}, the size lib/site.ts declares`,
  ihdr?.width === OG_IMAGE_WIDTH && ihdr?.height === OG_IMAGE_HEIGHT,
  ihdr ? `IHDR=${ihdr.width}x${ihdr.height}` : "no file");
check(`7c and it is a real card, not a flat placeholder (>= ${FLOOR_ASSET_BYTES} bytes)`,
  (ihdr?.bytes ?? 0) >= FLOOR_ASSET_BYTES, ihdr ? `${ihdr.bytes} bytes` : "no file");

const gen = readFileSync(GENERATOR, "utf8");
/** The card's own markup, sliced out of the generator. Grading the whole file would refuse a comment that merely
 * names the brand; the claim is about what the picture is built from. */
const markupOf = (src) => {
  const start = src.indexOf("const html = `");
  if (start < 0) die(`${GENERATOR}: no \`const html = …\` card markup to grade — the card is built where this gate cannot see`);
  const stop = src.indexOf("`;", start);
  if (stop < 0) die(`${GENERATOR}: the card markup never closes`);
  return src.slice(start, stop);
};
const markup = markupOf(gen);
check(`8 the card sizes itself from the declaration (no literal ${OG_IMAGE_WIDTH} or ${OG_IMAGE_HEIGHT} in its markup)`,
  markup.includes("${OG_IMAGE_WIDTH}") && markup.includes("${OG_IMAGE_HEIGHT}")
    && !markup.includes(String(OG_IMAGE_WIDTH)) && !markup.includes(String(OG_IMAGE_HEIGHT)),
  "it spells a size of its own");
check("8b it interpolates the module's wordmark and tagline and copies neither",
  markup.includes("${SITE_NAME}") && markup.includes("${SITE_TAGLINE}")
    && !markup.includes(SITE_NAME) && !markup.includes(SITE_TAGLINE),
  `wordmark-copied=${markup.includes(SITE_NAME)} tagline-copied=${markup.includes(SITE_TAGLINE)}`);
check("8c and its colours come from the stylesheet's tokens, not from hex typed into the card",
  !/#[0-9a-f]{6}/i.test(markup) && markup.includes("${tokens.bg}") && markup.includes("${tokens.accent}"),
  (markup.match(/#[0-9a-f]{6}/gi) ?? []).join(", ") || "no token read");

const staticPageExists = (path) => existsSync(join(APP, path.replace(/^\//, ""), "page.tsx"));
/** `app/<area>/shared/[token]/page.tsx` is the route `/…/shared`, so the page's own route is everything between
 * `app/` and the dynamic segment — derived once and read by both clauses that need it. */
const ownRoute = (rel) => `/${rel.split("/").slice(1, -2).join("/")}`;
for (const r of rows) {
  check(`9 ${r.rel} canonicalises to a page the app answers`,
    typeof r.canonicalPath === "string" && !r.canonicalPath.includes("[") && staticPageExists(r.canonicalPath),
    `canonicalPath=${JSON.stringify(r.canonicalPath)}`);
  check(`9b ${r.rel} declares a share path under its own route, and leaves the token half to interpolate`,
    typeof r.shareHead === "string" && r.shareTail >= 1 && r.shareHead.startsWith(ownRoute(r.rel)),
    `sharePath head=${JSON.stringify(r.shareHead)} interpolated=${r.shareTail} page=${r.rel}`);
}
const sitemapSrc = readFileSync(join(APP, "sitemap.ts"), "utf8");
/** A share route can be advertised three ways: the parent of the token, a token itself, or a trailing-slash prefix.
 * A byte check for `/shared/` alone misses `"/tactics/shared"`, which is the spelling a hand-edited entry takes —
 * so the prefixes come from the walked pages and a new share surface is refused in its own spelling. */
const sharePrefixes = [...new Set(rows.map((r) => ownRoute(r.rel)))];
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const advertisedShare = sharePrefixes.filter((p) => new RegExp(`["'\`]${escapeRe(p)}(/|["'\`])`).test(sitemapSrc));
check(`9c no share path is advertised to a crawler in the sitemap (${sharePrefixes.join(", ")})`,
  advertisedShare.length === 0, advertisedShare.join(", ") || "none of them named");

console.log(`CHECKS passed=${passed} total=${checks} failed=${checks - passed}`);
console.log(`  share pages=${rows.length} [${rows.map((r) => `${r.rel}${r.usesHelper && r.imported ? ":wired" : ":BARE"}`).join(" ")}]`);
console.log(`  card=${OG_IMAGE_PATH} ${OG_IMAGE_WIDTH}x${OG_IMAGE_HEIGHT} declared, asset=${ihdr ? `${ihdr.width ?? "-"}x${ihdr.height ?? "-"} ${ihdr.bytes}B` : "missing"}`);
if (failed.length) process.exitCode = 1;
