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
 * The proxy also carries a caller's trace context. Its outgoing headers are an allowlist, so an upstream
 * caller's W3C `traceparent` (a load balancer, an edge worker) stopped at the tier and the API began a
 * second trace for one request. The API continues an incoming `traceparent`; `lib/trace-context.ts` is the
 * other end — it forwards a valid context unchanged, refuses to propagate an invalid one, and never mints
 * ids of its own. Checks 4–6 hold both ends of that contract.
 *
 * Checks:
 *   1  the walk finds the population — the file count has a floor, and every file parsed, so a scan that
 *      narrows itself cannot pass by finding nothing
 *   2  no client file calls the API outside the proxy — the absolute calls, if there are any, are named
 *      with the file and the line
 *   3  the proxy is the one that calls it — the absolute calls live in the proxy, not in a page
 *   4  a valid caller's trace context is forwarded unchanged — the shipped helper is compiled and called,
 *      for a bare traceparent, one with tracestate, and one from a future version
 *   5  an invalid or orphaned context is not propagated — nine malformed shapes, each named, plus a
 *      tracestate with no traceparent, which is the control that the tier starts no trace of its own
 *   6  the proxy passes it to the API — `handle` computes the context off the incoming request, every
 *      proxied call carries it, and `callApi` sends it; dropping any one of those three is red here even
 *      though the helper alone would still be green
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

/**
 * The trace-context helper is compiled and **called**: a check that retyped its rules would keep agreeing
 * with itself after the shipped copy changed. A module that will not load is a failed check, not a crash.
 */
const TRACE_CONTEXT = join(WEB, "lib", "trace-context.ts");
const loadExport = (file, name) => {
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const module = { exports: {} };
  new Function("exports", "module", "require", compiled)(module.exports, module, require);
  if (typeof module.exports[name] !== "function") throw new Error(`${file} does not export ${name}`);
  return module.exports[name];
};
let traceHeaders = null;
let traceLoadError = "";
try {
  traceHeaders = loadExport(TRACE_CONTEXT, "traceContextHeaders");
} catch (error) {
  traceLoadError = String(error && error.message ? error.message : error);
}

const incoming = (entries) => ({ get: (name) => entries[name.toLowerCase()] ?? null });
const shown = (value) => JSON.stringify(Object.entries(value).sort());

const parent = "4bf92f3577b34da6a3ce929d0e0e4736";
const span = "00f067aa0ba902b7";
const valid = `00-${parent}-${span}-01`;
const future = `cc-${parent}-${span}-01-a-field-this-version-does-not-know`;
const forwarded = traceHeaders === null ? [] : [
  ["a bare traceparent", incoming({ traceparent: valid }), { traceparent: valid }],
  ["a traceparent with tracestate", incoming({ traceparent: valid, tracestate: "vendor=abc,other=1" }), { traceparent: valid, tracestate: "vendor=abc,other=1" }],
  ["a future version", incoming({ traceparent: future }), { traceparent: future }],
].map(([label, headers, want]) => ({ label, got: traceHeaders(headers), want }));
const forwardMisses = forwarded.filter((row) => shown(row.got) !== shown(row.want));
check(
  "a valid caller's trace context is forwarded unchanged",
  traceHeaders !== null && forwarded.length === 3 && forwardMisses.length === 0,
  traceHeaders === null ? `the helper did not load: ${traceLoadError}`
    : forwardMisses.length === 0 ? `${forwarded.length}/${forwarded.length} shapes byte-identical`
      : forwardMisses.map((row) => `${row.label}: got ${shown(row.got)}, wanted ${shown(row.want)}`).join("; "),
);

const malformed = [
  ["uppercase trace id", `00-${parent.toUpperCase()}-${span}-01`],
  ["all-zero trace id", `00-${"0".repeat(32)}-${span}-01`],
  ["all-zero parent id", `00-${parent}-${"0".repeat(16)}-01`],
  ["version ff", `ff-${parent}-${span}-01`],
  ["version 00 with a trailing field", `${valid}-extra`],
  ["a 31-hex trace id", `00-${parent.slice(1)}-${span}-01`],
  ["no flags", `00-${parent}-${span}`],
  ["a non-hex version", `zz-${parent}-${span}-01`],
  ["tracestate with no traceparent", null],
];
const leaked = traceHeaders === null ? [] : malformed.filter(([, value]) =>
  shown(traceHeaders(incoming(value === null ? { tracestate: "vendor=abc" } : { traceparent: value }))) !== "[]");
check(
  "an invalid or orphaned trace context is not propagated",
  traceHeaders !== null && leaked.length === 0,
  traceHeaders === null ? `the helper did not load: ${traceLoadError}`
    : leaked.length === 0 ? `${malformed.length}/${malformed.length} shapes dropped, including the orphan tracestate`
      : `propagated ${leaked.map(([label]) => label).join(", ")}`,
);

/**
 * The helper can be perfect and never be called. Three seams are read from the route's own AST: `handle`
 * computes the context off the incoming request, both calls that forward `target` carry it, and `callApi`
 * puts it on the outgoing headers. Any one of them missing turns this red.
 */
const routeFile = join(WEB, PROXY);
const route = ts.createSourceFile(routeFile, readFileSync(routeFile, "utf8"), ts.ScriptTarget.ESNext, true, ts.ScriptKind.TSX);
let computesTrace = false;
let callApiSends = false;
const proxied = [];
const routeLine = (node) => route.getLineAndCharacterOfPosition(node.getStart(route)).line + 1;
const walkRoute = (node) => {
  if (ts.isFunctionDeclaration(node) && node.name && node.body) {
    if (node.name.text === "callApi") {
      const scan = (child) => {
        if (ts.isSpreadAssignment(child) && child.expression.getText(route) === "options.trace") callApiSends = true;
        ts.forEachChild(child, scan);
      };
      scan(node.body);
    }
    if (node.name.text === "handle") {
      const scan = (child) => {
        if (ts.isCallExpression(child) && ts.isIdentifier(child.expression) && child.expression.text === "traceContextHeaders") {
          const argument = child.arguments[0];
          if (argument && argument.getText(route) === "request.headers") computesTrace = true;
        }
        if (ts.isCallExpression(child) && ts.isIdentifier(child.expression) && child.expression.text === "callApi") {
          const targetArgument = child.arguments[1];
          if (targetArgument && targetArgument.getText(route) === "target") {
            const options = child.arguments[2];
            const carries = Boolean(options) && ts.isObjectLiteralExpression(options) && options.properties.some((property) =>
              (ts.isShorthandPropertyAssignment(property) && property.name.text === "trace")
              || (ts.isPropertyAssignment(property) && property.name.getText(route) === "trace"));
            proxied.push({ line: routeLine(child), carries });
          }
        }
        ts.forEachChild(child, scan);
      };
      scan(node.body);
    }
  }
  ts.forEachChild(node, walkRoute);
};
walkRoute(route);
const carrying = proxied.filter((call) => call.carries);
check(
  "the proxy passes the caller's context to the API",
  computesTrace && callApiSends && proxied.length >= 2 && carrying.length === proxied.length,
  `handle computes it=${computesTrace}, callApi sends it=${callApiSends}, `
    + `${carrying.length}/${proxied.length} proxied call(s) carry it`
    + (carrying.length === proxied.length ? "" : `; missing at ${proxied.filter((c) => !c.carries).map((c) => `line ${c.line}`).join(", ")}`),
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
