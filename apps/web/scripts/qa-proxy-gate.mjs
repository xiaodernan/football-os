#!/usr/bin/env node
/*
 * The cookie proxy is the only door a browser may use.
 *
 * The web tier's session design is one sentence long: the access token is **httpOnly**, so no script can
 * read it, and every call a browser makes reaches the API through `app/api/v1/[...path]/route.ts`, which
 * reads the token from the cookie jar and hands it on. A client file that reached the API directly would
 * have to hold the token in JavaScript — which is the one thing the design says cannot happen — and it
 * would also bypass the proxy's refresh, so a session that had expired would answer 401 where it should
 * have answered a fresh one.
 *
 * Nothing held that. The tree happens to be clean: the only absolute `fetch` in the whole web tier is the
 * proxy's own, and this file is what says so on every run.
 *
 * Checks:
 *   1  the walk finds the population — the file count has a floor, and every file parsed, so a scan that
 *      narrows itself cannot pass by finding nothing
 *   2  no client file calls the API outside the proxy — the absolute calls, if there are any, are named
 *      with the file and the line
 *   3  the proxy is the one that calls it — the absolute calls live in the proxy, not in a page
 *
 * Files only: no server, no browser, no port.
 */

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const WEB = resolve(process.env.QA_PROXY_WEB ? process.env.QA_PROXY_WEB : fileURLToPath(new URL("..", import.meta.url)));

/** The population: every TypeScript file the web tier ships. */
const ROOTS = ["app", "components", "lib"];
const FILES = [];

const walk = (dir) => {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) FILES.push(p);
  }
};
for (const root of ROOTS) walk(join(WEB, root));

/** The floor on the population: a scan that finds nothing must not read as "nothing to hold". */
const FLOOR_FILES = 100;

/** The proxy: the one file allowed to reach the API absolutely. */
const PROXY = "app/api/v1/[...path]/route.ts";

const calls = [];
let parsed = 0;
let diagnostics = 0;

/**
 * The target of a fetch, when it is one a reader can judge: a string literal, or a template.
 *
 * `head` is the part that decides *where* the call goes (a template's head is its first piece of text),
 * and `shown` is the whole expression, so a finding can print what the author wrote.
 *
 * A target that is neither (a variable) cannot be judged from the bytes, so it is not judged: the rule
 * below is about the calls a person wrote down.
 */
const targetOf = (node, source) => {
  if (!node) return null;
  if (ts.isStringLiteral(node)) return { head: node.text, shown: node.text };
  if (ts.isTemplateExpression(node)) return { head: node.head.text, shown: node.getText(source) };
  return null;
};

for (const file of FILES) {
  const text = readFileSync(file, "utf8");
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  if (source.parseDiagnostics?.length) diagnostics += source.parseDiagnostics.length;
  parsed += 1;
  const rel = file.slice(WEB.length + 1).split(sep).join("/");
  const isClient = /^\s*["']use client["']/.test(text);
  const line = (node) => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;

  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "fetch") {
      const target = targetOf(node.arguments[0], source);
      if (target !== null) {
        calls.push({
          file: rel,
          line: line(node),
          client: isClient,
          target: target.shown.replace(/\s+/g, " ").slice(0, 100),
          throughProxy: target.head.startsWith("/api/"),
        });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

check(
  "the walk finds the population",
  FILES.length >= FLOOR_FILES && parsed === FILES.length && diagnostics === 0,
  `${FILES.length} files, ${parsed} parsed, ${diagnostics} parse diagnostics (floor ${FLOOR_FILES})`,
);

/**
 * A browser may only reach the API through the proxy, so every call that names its target must name a
 * path under `/api/`. A call that names an absolute URL — or a base it built from one — is a client that
 * would have to hold the token, which is the one thing the httpOnly design says cannot happen.
 */
const bypasses = calls.filter((call) => !call.throughProxy && call.file !== PROXY);
check(
  "no file calls the API outside the proxy",
  bypasses.length === 0,
  bypasses.length === 0 ? `${calls.length} call(s) with a named target, all through /api/` : `${bypasses.length} call(s) bypass it`,
);

const proxyCalls = calls.filter((call) => call.file === PROXY);
check(
  "the proxy is the one that reaches the API",
  proxyCalls.length === 1 && !proxyCalls[0].throughProxy,
  `${proxyCalls.length} call(s) in ${PROXY}${proxyCalls[0] ? ` — ${proxyCalls[0].target}` : ""}`,
);

for (const call of calls) {
  console.log(`  ${call.file}:${call.line} ${call.client ? "(client)" : "(server)"} ${call.target}`);
}

const failed = checks.filter((c) => !c.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  console.log("A browser may not hold the access token, so a browser may not reach the API except through the proxy.");
  process.exitCode = 1;
}
