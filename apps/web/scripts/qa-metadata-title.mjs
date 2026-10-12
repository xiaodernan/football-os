#!/usr/bin/env node
/*
§81 2c — a page's document tab and the page's own heading are one decision, and this gate reads that decision off
every page in the app instead of off the nine a slice happened to touch.

Why the change-time witness could not be the shipped one: `dmeta-check.mjs` grades each site by comparing the new
read against *HEAD's literal* — the only proof that no English copy was rewritten while wiring. That comparison stops
meaning anything the moment HEAD is the wired file, so it is an instrument for making a change, not for holding one.
This file states the rule permanently: **a tab may not be a load-time literal on a page whose heading already follows
the locale**, because the heading repaints in Chinese while the tab stays English; and where both are still literals,
**they must be the same bytes**, because a tab that names a different copy than its own heading is two authors talking
past each other inside one page.

Measured over the whole population at the ref this gate landed (59 `page.tsx`, 0 parse diagnostics): titles are
keyed 24 → 25, literal 25 → 24, dynamic 10; headings are keyed 25, dynamic 21, literal 13. The literal×keyed cell —
the drift this rule exists to refuse — held exactly one page, `app/knowledge/page.tsx`, whose tab was the literal
"Football Knowledge" while `knowledge.metaTitle` sat in the catalogue with *no reader at all* (7 `metaTitle` keys,
6 read, 1 orphan). That page is the slice attached to this gate; the counts below are its after-image.

Checks, each able to refuse on its own:
  1  the scan finds the population (>= FLOOR page.tsx) and every one parsed — a blind walk would grade an empty set
  2  every page declares a title, in one form only                      — both `metadata` and `generateMetadata` is two tabs
  3  a translator name is bound to one namespace per file               — `t` reading two catalogues makes the read ambiguous
  4  DRIFT: no literal tab on a page whose heading reads a key          — the class the rule refuses; must be 0, no ledger
  5  DISAGREE: a literal tab equals one of the page's literal headings  — unless the page is in the ledger and its proof re-holds
  6  a ledger entry that no longer describes its file is stale          — an exemption the bytes stopped earning is a hiding place
  7  every keyed read resolves in en, zh and zh-TW                      — a missing key is a silent fallback, not a translation
  8  a tab key differs from English in both Chinese catalogues          — an English-valued key means no locale read can see the wiring
  9  every <ns>.metaTitle in the catalogue is read by some page's tab   — the orphan shape: written for a title, read by nothing
  10 LITERAL ceiling: the count of literal-titled pages may not rise     — i18n work lowers this; a new page must not raise it

The two ledger rows are the pages whose tab and heading are two different copies in English today (`/club` prints
"My clubs" over "Club tenancies"; `/community` prints "Community" over "Community wall"). Choosing between them is a
sense decision about the product's copy, not a wiring, and inventing a key would be writing copy this arc has refused
to invent. Each row's proof is a predicate over that file's bytes, re-measured every run, so a name in the ledger buys
nothing unless the file still shows the disagreement.
*/

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, resolve, sep } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

// `fileURLToPath`, never `URL.pathname`: this repo's own path is non-ASCII and the pathname form comes back
// percent-encoded, which no filesystem call resolves. `QA_METADATA_WEB` points the same walk at an arm plane.
const WEB = resolve(process.env.QA_METADATA_WEB ? process.env.QA_METADATA_WEB : fileURLToPath(new URL("..", import.meta.url)));
const APP = join(WEB, "app");
const MESSAGES = join(WEB, "messages");
const LOCALES = ["en", "zh", "zh-TW"];
const FLOOR_PAGES = 59;
const FLOOR_CARRIERS = 45; // pages on which the walk finds at least one heading carrier
const dict = {};
for (const tag of LOCALES) {
  const file = join(MESSAGES, `${tag}.json`);
  dict[tag] = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : null;
}

const pages = [];
const walkApp = (dir) => {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walkApp(p);
    else if (entry.name === "page.tsx") pages.push(p);
  }
};
walkApp(APP);

const relOf = (p) => p.slice(WEB.length + 1).split(sep).join("/");
const visit = (node, fn) => { fn(node); ts.forEachChild(node, (c) => visit(c, fn)); };

// A translator binder: `const t = useTranslations("ns")` or `const tn = await getTranslations("nav")`. Bound twice to
// two namespaces in one file is check 3, not something this map gets to silently overwrite.
const binders = (sf) => {
  const map = new Map();
  const clashes = [];
  visit(sf, (node) => {
    if (!ts.isVariableDeclaration(node) || !ts.isIdentifier(node.name) || !node.initializer) return;
    const call = ts.isAwaitExpression(node.initializer) ? node.initializer.expression : node.initializer;
    if (!ts.isCallExpression(call) || !/^(use|get)Translations$/.test(call.expression.getText())) return;
    const arg = call.arguments[0];
    if (!arg || !ts.isStringLiteral(arg)) return;
    const name = node.name.getText();
    if (map.has(name) && map.get(name) !== arg.text) clashes.push(`${name}: ${map.get(name)} vs ${arg.text}`);
    map.set(name, arg.text);
  });
  return { map, clashes };
};

// What an expression WRITES as the page's copy: a key read, a string literal, or something derived from data. An
// identifier is followed into its local `const` because `{ title, description }` is how the two dynamic-title pages
// spell theirs — a walk that stops at the identifier reports those pages as declaring no title at all.
const classify = (node, ns, inits, seen = 0) => {
  if (!node) return null;
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return { kind: "literal", value: node.text };
  if (ts.isCallExpression(node)) {
    const base = node.expression.getText().split(".")[0];
    const arg = node.arguments[0];
    if (ns.has(base) && arg && ts.isStringLiteral(arg)) return { kind: "keyed", ns: ns.get(base), key: arg.text };
    return { kind: "dynamic", text: node.getText().replace(/\s+/g, " ").slice(0, 48) };
  }
  if (ts.isIdentifier(node) && seen < 3 && inits.has(node.getText()) && inits.get(node.getText()) !== node) {
    const inner = classify(inits.get(node.getText()), ns, inits, seen + 1);
    return inner ? { ...inner, via: node.getText() } : null;
  }
  return { kind: "dynamic", text: node.getText().replace(/\s+/g, " ").slice(0, 48) };
};

const titleOf = (obj, ns, inits) => {
  const p = (obj.properties ?? []).find((q) => q.name?.getText() === "title");
  if (!p) return null;
  if (ts.isShorthandPropertyAssignment(p)) return classify(p.name, ns, inits);
  if (ts.isPropertyAssignment(p)) return classify(p.initializer, ns, inits);
  return { kind: "dynamic", text: `spread:${p.getText().replace(/\s+/g, " ").slice(0, 40)}` };
};

// The heading carriers a page actually writes: `<h1>…</h1>` and `<WorldHead title=…>`. `Panel` and
// `WorldUnavailable` are excluded on purpose — a panel beside the heading and a refusal screen are not the page's
// heading, and an ownership claim that reads them reaches past the thing it is about.
const headingsOf = (sf, ns, inits) => {
  const out = [];
  visit(sf, (node) => {
    // Parsed `JsxElement` in this TypeScript build carries only [openingElement, children, closingElement]; the
    // interface's `tagName` is absent, so reading `node.tagName` alone sees no `<h1>` anywhere in the tree.
    const tag = (node.tagName ?? node.openingElement?.tagName)?.getText?.();
    if (!tag) return;
    if (tag === "h1" && ts.isJsxElement(node)) {
      const kids = node.children ?? [];
      const text = kids.filter((c) => c.kind === ts.SyntaxKind.JsxText).map((c) => c.getFullText().trim()).filter(Boolean).join(" ");
      const exprs = kids.filter((c) => ts.isJsxExpression(c) && c.expression);
      if (text) out.push({ tag, kind: "literal", value: text.replace(/\s+/g, " ") });
      else if (exprs.length === 1) out.push({ tag, ...classify(exprs[0].expression, ns, inits) });
      else out.push({ tag, kind: "dynamic", text: `children(${exprs.length})` });
    } else if (tag === "WorldHead") {
      const open = node.openingElement ?? node;
      const attr = (open.attributes?.properties ?? []).find((a) => a.name?.getText() === "title");
      if (!attr || !ts.isJsxAttribute(attr)) { out.push({ tag, kind: "dynamic", text: "no title attribute" }); return; }
      const init = attr.initializer;
      const node2 = init && ts.isJsxExpression(init) ? init.expression : init;
      out.push({ tag, ...classify(node2, ns, inits) });
    }
  });
  return out;
};

const rows = [];
for (const file of pages) {
  const src = readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.ESNext, true, ts.ScriptKind.TSX);
  const { map: ns, clashes } = binders(sf);
  const inits = new Map();
  visit(sf, (node) => {
    if (!ts.isVariableDeclaration(node) || !ts.isIdentifier(node.name) || !node.initializer) return;
    const key = node.name.getText();
    if (!inits.has(key)) inits.set(key, node.initializer);
  });
  const row = {
    rel: relOf(file),
    diags: (sf.parseDiagnostics ?? []).length,
    clashes,
    forms: [],
    title: null,
    heads: headingsOf(sf, ns, inits),
  };
  visit(sf, (node) => {
    if (ts.isVariableStatement(node) && (node.modifiers ?? []).some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) {
      const decl = node.declarationList.declarations[0];
      if (!decl || decl.name.getText() !== "metadata") return;
      row.forms.push("load-time");
      let init = decl.initializer;
      if (init && ts.isCallExpression(init) && init.expression.getText() === "pageMetadata") init = init.arguments[0];
      row.title = init && ts.isObjectLiteralExpression(init) ? titleOf(init, ns, inits) : { kind: "dynamic", text: "metadata is not an object literal" };
    }
    if (ts.isFunctionDeclaration(node) && (node.modifiers ?? []).some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
        && node.name?.getText() === "generateMetadata") {
      row.forms.push("generateMetadata");
      let obj = null;
      for (const st of node.body?.statements ?? []) {
        if (!ts.isReturnStatement(st) || !st.expression) continue;
        let e = st.expression;
        if (ts.isParenthesizedExpression(e)) e = e.expression;
        if (ts.isCallExpression(e) && e.expression.getText() === "pageMetadata") e = e.arguments[0];
        if (ts.isIdentifier(e) && inits.has(e.getText())) e = inits.get(e.getText());
        if (e && ts.isObjectLiteralExpression(e)) { obj = e; break; }
      }
      // A read inside generateMetadata may only use a translator bound inside that function.
      const local = new Map();
      visit(node.body ?? node, (n) => {
        if (!ts.isVariableDeclaration(n) || !ts.isIdentifier(n.name) || !n.initializer) return;
        const call = ts.isAwaitExpression(n.initializer) ? n.initializer.expression : n.initializer;
        if (ts.isCallExpression(call) && /^(use|get)Translations$/.test(call.expression.getText()) && ts.isStringLiteral(call.arguments[0])) {
          local.set(n.name.getText(), call.arguments[0].text);
        }
      });
      const scope = local.size ? local : ns;
      if (obj) {
        const t = titleOf(obj, scope, inits);
        // `title` may arrive as a reference to a `const` the function computed from data — that is a dynamic title,
        // and it is the page's own decision, not a drift.
        row.title = t ?? { kind: "absent", text: "generateMetadata returns an object with no title" };
      } else {
        row.title = row.title ?? { kind: "opaque", text: "generateMetadata returns something this walk cannot read" };
      }
    }
  });
  rows.push(row);
}

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

check(`1 the walk reads the page population (>= ${FLOOR_PAGES} page.tsx under ${relOf(APP)}/)`,
  pages.length >= FLOOR_PAGES, `found ${pages.length}`);
check(`1b every page parsed with no diagnostic`, rows.every((r) => r.diags === 0),
  rows.filter((r) => r.diags).map((r) => `${r.rel}(${r.diags})`).join(", "));
check(`1c at least ${FLOOR_CARRIERS} pages show a heading carrier`, rows.filter((r) => r.heads.length).length >= FLOOR_CARRIERS,
  `only ${rows.filter((r) => r.heads.length).length} of ${rows.length}`);

check("2 every page declares its tab exactly once",
  rows.every((r) => r.title !== null && r.title.kind !== "absent" && r.forms.length === 1),
  rows.filter((r) => !r.title || r.title.kind === "absent" || r.forms.length !== 1)
    .map((r) => `${r.rel} forms=[${r.forms.join("+")}] title=${r.title?.kind ?? "none"}`).join(", "));
check("3 no file binds one translator name to two namespaces", rows.every((r) => !r.clashes.length),
  rows.filter((r) => r.clashes.length).map((r) => `${r.rel} ${r.clashes.join("; ")}`).join(", "));

const drift = rows.filter((r) => r.title?.kind === "literal" && r.heads.some((h) => h.kind === "keyed"));
check("4 DRIFT — no literal tab on a page whose heading reads a key", drift.length === 0,
  drift.map((r) => `${r.rel} tab=${JSON.stringify(r.title.value)} heading=${r.heads.find((h) => h.kind === "keyed").ns}.${r.heads.find((h) => h.kind === "keyed").key}`).join(", "));

// A literal tab beside a literal heading must be that heading's bytes. The ledger buys time for the two pages whose
// English genuinely holds two copies; it buys it only while their bytes still show the disagreement (check 6).
const LEDGER = {
  "app/club/page.tsx": "the tab says \"My clubs\", the heading says \"Club tenancies\" — which copy names the page is a sense decision, not a wiring",
  "app/community/page.tsx": "the tab says \"Community\", the heading says \"Community wall\" — the same sense question, and no key holds either copy's bytes",
};
const disagree = rows.filter((r) => {
  if (r.title?.kind !== "literal") return false;
  const lits = r.heads.filter((h) => h.kind === "literal");
  if (!lits.length) return false;
  return !lits.some((h) => h.value === r.title.value);
});
for (const r of disagree) {
  const lits = r.heads.filter((h) => h.kind === "literal").map((h) => h.value);
  const proven = r.title.kind === "literal" && lits.length > 0 && !lits.includes(r.title.value);
  check(`5 DISAGREE ${r.rel}: a literal tab equals one of the page's literal headings`,
    LEDGER[r.rel] !== undefined && proven,
    `tab=${JSON.stringify(r.title.value)} heading=${JSON.stringify(lits.join(" | "))}${LEDGER[r.rel] ? ` — exempt: ${LEDGER[r.rel]}` : " — no ledger row"}`);
}
for (const [rel, reason] of Object.entries(LEDGER)) {
  const r = rows.find((x) => x.rel === rel);
  check(`6 ledger row ${rel} still describes its file`, r !== undefined && disagree.includes(r),
    r === undefined ? "no such page in the walk" : `tab=${JSON.stringify(r.title?.value)} headings=${JSON.stringify(r.heads.map((h) => h.value ?? `${h.ns}.${h.key}`))}`);
}

const keyed = [];
for (const r of rows) {
  for (const x of [r.title, ...r.heads]) if (x?.kind === "keyed") keyed.push({ rel: r.rel, x, isTitle: x === r.title });
}
for (const { rel, x } of keyed) {
  const present = LOCALES.every((tag) => typeof dict[tag]?.[x.ns]?.[x.key] === "string");
  check(`7 ${rel} read ${x.ns}.${x.key} resolves in ${LOCALES.join(", ")}`, present,
    LOCALES.filter((tag) => typeof dict[tag]?.[x.ns]?.[x.key] !== "string").join("/"));
}
for (const { rel, x, isTitle } of keyed.filter((k) => k.isTitle)) {
  const en = dict.en[x.ns]?.[x.key];
  const differs = ["zh", "zh-TW"].every((tag) => dict[tag][x.ns]?.[x.key] !== undefined && dict[tag][x.ns]?.[x.key] !== en);
  check(`8 the tab key ${x.ns}.${x.key} (${rel}) differs from English in zh and zh-TW`, differs,
    `en=${JSON.stringify(en)} zh=${JSON.stringify(dict.zh[x.ns]?.[x.key])} zh-TW=${JSON.stringify(dict["zh-TW"][x.ns]?.[x.key])}`);
}

// The orphan shape: a `metaTitle` written into a catalogue for a page's tab, read by no page. 7 exist, one had no
// reader, and that one was the drift page — the key and the defect were the same fact seen from two sides.
const titleKeys = new Set(rows.filter((r) => r.title?.kind === "keyed").map((r) => `${r.title.ns}.${r.title.key}`));
const orphans = [];
for (const [ns, o] of Object.entries(dict.en)) {
  if (!o || typeof o !== "object") continue;
  for (const k of Object.keys(o)) if (k === "metaTitle" && !titleKeys.has(`${ns}.${k}`)) orphans.push(`${ns}.metaTitle`);
}
check(`9 every <ns>.metaTitle in the catalogue is read by a page tab (${orphans.length} orphans)`, orphans.length === 0,
  orphans.join(", "));

const literalCount = rows.filter((r) => r.title?.kind === "literal").length;
const CEILING_LITERALS = 24; // measured at the ref this gate landed; wiring lowers it, a new page must not raise it
check(`10 LITERAL ceiling: pages still titling from a load-time literal <= ${CEILING_LITERALS}`,
  literalCount <= CEILING_LITERALS, `found ${literalCount}`);

console.log(`CHECKS passed=${passed} total=${checks} failed=${checks - passed}`);
console.log(`  population=${rows.length} titles: keyed=${rows.filter((r) => r.title?.kind === "keyed").length} `
  + `literal=${literalCount} dynamic=${rows.filter((r) => r.title && r.title.kind === "dynamic").length} | `
  + `headings: keyed=${rows.filter((r) => r.heads.some((h) => h.kind === "keyed")).length} `
  + `literal=${rows.filter((r) => r.heads.some((h) => h.kind === "literal")).length} `
  + `dynamic-only=${rows.filter((r) => r.heads.length && r.heads.every((h) => h.kind === "dynamic")).length} `
  + `no-carrier=${rows.filter((r) => !r.heads.length).length}`);
if (process.env.QA_METADATA_ROWS) {
  for (const r of rows) {
    console.log(`  ${r.rel} form=[${r.forms.join(",")}] tab=${r.title?.kind === "keyed" ? `${r.title.ns}.${r.title.key}`
      : r.title?.kind === "literal" ? JSON.stringify(r.title.value) : `${r.title?.kind}:${(r.title?.text ?? "").slice(0, 30)}`}`
      + ` heads=[${r.heads.map((h) => h.kind === "keyed" ? `${h.ns}.${h.key}<${h.tag}>` : h.kind === "literal" ? `"${h.value}"<${h.tag}>` : `dyn<${h.tag}>`).join(" | ") || "NONE"}]`);
  }
}
console.log(`ran qa-metadata-title against ${WEB}`);
process.exitCode = failed.length ? 1 : 0;
