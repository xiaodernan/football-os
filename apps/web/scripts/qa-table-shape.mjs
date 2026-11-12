#!/usr/bin/env node
/*
Item 28 — a sheet is one object with one frame, and this gate reads that off every `<table>` in the app.

Three copies of the data wall were written by hand and landed looking like three products: `components/
CommunityTools.tsx`, `components/MatchTools.tsx` and `components/NoticeBoardTools.tsx` each wrapped their table in
the scroll frame but forgot `className="table"`, so 110 sheets carried the design system's rules and three fell back
to the browser's defaults — no uppercase head, no row rule, no hover, a different font size. Nothing in the suite
could see it: `tsc` does not read a class name, ESLint does not compare two files, and the browser walk checks that
the row is there, not that it is dressed like its neighbours. That is the class of defect a static walk owns.

The rule is two lines long and both halves matter:
  * every `<table>` names `.table` (a bare table is the browser's default, which is a different product),
  * every `<table>` sits inside a scroll frame (`.table-wrap` or `.world-tablewrap`), because a wide sheet with no
    frame makes the *page* scroll sideways and takes the nav with it.

The frame check walks the JSX tree rather than the file's text: a `table-wrap` three panels away in the same file
does not wrap this table, and a regex cannot tell the difference. A class name the walk cannot resolve (a computed
expression) is counted as `dynamic` and does not fail — guessing at a value would make this gate a coin toss — but
the count is printed so a population of dynamic names cannot hide behind the silence.

Files only: no server, no browser, which is why it runs with the other gates and not in the live tier.
*/

import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const WEB = resolve(process.env.QA_TABLE_WEB ? process.env.QA_TABLE_WEB : fileURLToPath(new URL("..", import.meta.url)));
const FLOOR = 60;
const FRAMES = ["table-wrap", "world-tablewrap"];
const problems = [];

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name.startsWith(".next")) continue;
      walk(path, out);
    } else if (entry.name.endsWith(".tsx")) {
      out.push(path);
    }
  }
  return out;
}

/** Reads a JSX className into {kind, value}: literal text when the walk can see it, dynamic when it cannot. */
function classOf(opening, source) {
  for (const attr of opening.attributes.properties) {
    if (!ts.isJsxAttribute(attr) || attr.name.getText(source) !== "className") continue;
    if (!attr.initializer) return { kind: "dynamic", value: "" };
    if (ts.isStringLiteral(attr.initializer)) return { kind: "literal", value: attr.initializer.text };
    if (ts.isJsxExpression(attr.initializer) && attr.initializer.expression) {
      const expression = attr.initializer.expression;
      if (ts.isStringLiteral(expression) || ts.isNoSubstitutionTemplateLiteral(expression)) {
        return { kind: "literal", value: expression.text };
      }
      return { kind: "dynamic", value: expression.getText(source) };
    }
    return { kind: "dynamic", value: "" };
  }
  return { kind: "none", value: "" };
}

/** True when any ancestor JSX element (within five levels) carries one of the frame classes. */
function sitsInFrame(node, source) {
  let cursor = node.parent;
  for (let depth = 0; cursor && depth < 5; depth += 1, cursor = cursor.parent) {
    const element = ts.isJsxElement(cursor) ? cursor.openingElement : ts.isJsxSelfClosingElement(cursor) ? cursor : null;
    if (!element) continue;
    const cls = classOf(element, source);
    if (cls.kind === "literal" && FRAMES.some((frame) => cls.value.split(/\s+/).includes(frame))) return true;
  }
  return false;
}

const files = [...walk(join(WEB, "app")), ...walk(join(WEB, "components"))];
const counts = { tables: 0, dressed: 0, framed: 0, dynamic: 0 };

for (const file of files) {
  const source = ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  if (source.parseDiagnostics && source.parseDiagnostics.length > 0) {
    problems.push(`${file}: ${source.parseDiagnostics.length} parse diagnostic(s) — the walk cannot judge an unparsable file`);
    continue;
  }
  const relative = file.slice(WEB.length + 1);
  const visit = (node) => {
    const opening = ts.isJsxElement(node)
      ? node.openingElement
      : ts.isJsxSelfClosingElement(node)
        ? node
        : null;
    if (opening && opening.tagName.getText(source) === "table") {
      counts.tables += 1;
      const cls = classOf(opening, source);
      if (cls.kind === "none") {
        problems.push(`${relative}: a <table> with no className — the browser's default sheet, not the product's`);
      } else if (cls.kind === "dynamic") {
        counts.dynamic += 1;
      } else if (cls.value.split(/\s+/).includes("table")) {
        counts.dressed += 1;
      } else {
        problems.push(`${relative}: <table className="${cls.value}"> — does not name .table`);
      }
      if (sitsInFrame(node, source)) {
        counts.framed += 1;
      } else {
        problems.push(`${relative}: a <table> outside .table-wrap — a wide sheet would scroll the page, not itself`);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
}

if (counts.tables < FLOOR) {
  problems.push(`the walk found ${counts.tables} tables, below the floor of ${FLOOR} — a blind scan grades an empty set`);
}

if (problems.length > 0) {
  console.error(`qa-table-shape: ${counts.tables - problems.length}/${counts.tables} tables shaped correctly`);
  for (const problem of problems) console.error(`  ${problem}`);
  process.exit(1);
}

console.log(
  `qa-table-shape: ${counts.tables}/${counts.tables} tables name .table and sit in a frame ` +
    `(${counts.dynamic} className expression(s) not statically resolvable; ${files.length} files walked)`,
);
