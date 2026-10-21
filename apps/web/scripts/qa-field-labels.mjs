#!/usr/bin/env node
/*
 * §81 2c, continued — the name a field carries is part of the page, and two fields on one page may not
 * carry one name.
 *
 * Why this file exists. The copy arc wired every panel to the catalogues, and it gave two *different*
 * fields on the scout's screen the same accessible name: the shortlist's career link and the transfer
 * panel's career to simulate for both read `careerAria` — "Career to simulate for" — where before the arc
 * they read "Career to read the list against" and "Career to simulate for". A script that filled a
 * field by name then filled the wrong one: the browser walk typed the projection's career into the
 * *list's* field, the projection's own career stayed empty, the button stayed server-rendered
 * `disabled`, and seventeen of the walk's checks went red over a transfer projection that never ran.
 *
 * The copy gate cannot see that class. It counts English literals in the source, and a catalogue key used
 * for the wrong field is not a literal — it is a key, correctly spelled, in the wrong place. A gate that
 * counts cannot grade *meaning*, so this one grades *reachability* instead: for every page, which
 * components it renders, and which constant name each of them gives its fields.
 *
 * What is measured. For every `.tsx` under `app/` and `components/`: the constant `aria-label` keys it
 * declares, and the components it imports. For every page: the transitive closure of that graph, and the
 * keys each component in it declares. Two **different** components on one page that declare the same
 * constant key are two fields on one page with one name.
 *
 * Why "constant" matters. A label built with an interpolation — `aria-label={t("takeOffAria", { name })}`
 * — is a different name on every row, so two of them cannot be confused with one another. A label with no
 * interpolation is the same name everywhere it appears, and that is the one that can be ambiguous: a
 * screen-reader user hears two fields with one name, and a script that addresses a field by name cannot
 * say which one it meant.
 *
 * Checks, each able to refuse on its own:
 *   1  the walk finds the population — the file count, the page count and the key count each have a
 *      floor, and every import the graph reads resolves to a file that exists, because a graph that
 *      quietly dropped a component would pass check 2 by not looking at it
 *   2  no two panels on one page give a field the same name — the collisions are named, with the page
 *      and both components
 *
 * Files only: no server, no browser, no port — which is why it belongs with the other file-only gates in
 * `scripts/check.sh` and in CI.
 */

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const WEB = resolve(process.env.QA_LABELS_WEB ? process.env.QA_LABELS_WEB : fileURLToPath(new URL("..", import.meta.url)));
const APP = join(WEB, "app");
const COMPONENTS = join(WEB, "components");

/** The floors. Each one is a population this gate must find, so a scan that narrows itself cannot pass. */
const FLOOR_FILES = 70;
const FLOOR_PAGES = 40;
const FLOOR_KEYS = 50;

/** The population is every `.tsx` under `app/` **and** under `components/`: a page is only as addressable as the panels it renders. */
const files = [];
const walk = (dir) => {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (entry.name.endsWith(".tsx")) files.push(p);
  }
};
walk(APP);
walk(COMPONENTS);

const relOf = (p) => p.slice(WEB.length + 1).split(sep).join("/");
const existsIn = (rel) => existsSync(join(WEB, rel));

/** file -> the components it imports, and the constant aria-label keys it declares. */
const imports = new Map();
const declared = new Map();
const unresolved = [];
let parsed = 0;
let diagnostics = 0;

for (const file of files) {
  const text = readFileSync(file, "utf8");
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  if (source.parseDiagnostics?.length) diagnostics += source.parseDiagnostics.length;
  parsed += 1;
  const rel = relOf(file);
  const edges = new Set();
  const keys = new Set();

  const visit = (node) => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const spec = node.moduleSpecifier.text;
      const candidates = [];
      if (spec.startsWith("@/components/") || spec.startsWith("@/app/")) {
        candidates.push(`${spec.replace(/^@\//, "")}.tsx`);
      } else if (spec.startsWith(".")) {
        const dir = rel.slice(0, rel.lastIndexOf("/"));
        const target = resolve(join(WEB, dir), spec).slice(WEB.length + 1).split(sep).join("/");
        candidates.push(`${target}.tsx`, `${target}/index.tsx`, `${target}/page.tsx`);
      } else {
        ts.forEachChild(node, visit);
        return;
      }
      // A component is a PascalCase file in this project and a module is a lower-case one, so a specifier
      // that names a capitalised thing must resolve to a file that exists — a graph that quietly dropped a
      // panel would pass check 2 by not looking at it. A lower-case specifier is a module (`./api`,
      // `./types`) and carries no fields.
      const named = candidates[0].split("/").pop().replace(/\.tsx$/, "");
      const component = /^[A-Z]/.test(named);
      let resolved = false;
      for (const candidate of candidates) {
        if (existsIn(candidate)) {
          edges.add(candidate);
          resolved = true;
          break;
        }
      }
      if (!resolved && component) unresolved.push(`${rel} -> ${spec}`);
    }
    if (ts.isJsxAttribute(node) && node.name.text === "aria-label" && node.initializer) {
      const init = node.initializer;
      if (ts.isJsxExpression(init) && init.expression && ts.isCallExpression(init.expression)) {
        const call = init.expression;
        const first = call.arguments[0];
        // A label with no interpolation is the same name everywhere; one with an interpolation is not.
        const constant = call.arguments.length === 1 && ts.isStringLiteral(first);
        const callee = ts.isIdentifier(call.expression) ? call.expression.text : "";
        if (constant && /^t[a-z]{0,2}$/.test(callee)) keys.add(first.text);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  imports.set(rel, [...edges]);
  declared.set(rel, [...keys]);
}

const pages = files.map(relOf).filter((rel) => rel.endsWith("/page.tsx"));
const keyCount = new Set([...declared.values()].flat()).size;

/** Every component a page renders, transitively. */
const rendered = (page) => {
  const seen = new Set();
  const queue = [page];
  while (queue.length) {
    const current = queue.pop();
    if (seen.has(current)) continue;
    seen.add(current);
    for (const next of imports.get(current) ?? []) queue.push(next);
  }
  return seen;
};

const collisions = [];
for (const page of pages) {
  const owners = new Map();
  for (const component of rendered(page)) {
    for (const key of declared.get(component) ?? []) {
      const list = owners.get(key) ?? [];
      list.push(component);
      owners.set(key, list);
    }
  }
  for (const [key, list] of owners) {
    const distinct = [...new Set(list)];
    if (distinct.length > 1) collisions.push({ page, key, components: distinct });
  }
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

check(
  "the walk finds the population",
  files.length >= FLOOR_FILES && pages.length >= FLOOR_PAGES && keyCount >= FLOOR_KEYS && diagnostics === 0 && unresolved.length === 0,
  `${files.length} .tsx files, ${pages.length} pages, ${keyCount} constant aria-label keys, ${diagnostics} parse diagnostics, ${unresolved.length} unresolved import(s)`,
);

check(
  "no two panels on one page give a field the same name",
  collisions.length === 0,
  collisions.length === 0 ? "0 collision(s) over every page's own component graph" : `${collisions.length} collision(s)`,
);

for (const collision of collisions) {
  console.log(`  ${collision.page}: "${collision.key}" is declared by ${collision.components.join(", ")}`);
}

const failed = checks.filter((c) => !c.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  console.log("Two fields on one page may not carry one name: a reader who cannot tell them apart is a reader who fills the wrong one.");
  process.exitCode = 1;
}
