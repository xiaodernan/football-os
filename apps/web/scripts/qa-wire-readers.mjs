#!/usr/bin/env node
/*
§22 — the market's answer is a published shape, and this gate holds that the web tier reads the whole of it.

The defect it was written for: `market.py` has answered `window` — the block holding the round a deal
would be made in, the season's signing ranges and when the next one opens — on every `GET /transfers/{career}`
since 2026-10-28, and nothing on the market page read it. No shipped gate could see it: the dead-key gate asks
whether a *catalogue key* is asked for, and this is an *API field*, so a page can lose a whole block of published
arithmetic and every gate in the suite still prints green. The roadmap named the gap itself ("Not yet surfaced as
its own panel"), and the claim survived because the census that could have refused it had not been written.

Scope, named because it is a boundary and not an accident: the career overview page has read this same block
under its own type (`CareerWindow` in `lib/types.ts`), so a manager who never opens the market still sees the
round a deal would be made in. This gate judges the *market's* copy — `MarketView`/`MarketWindow` in
`lib/market.ts` and the page that shows the board — and nothing yet reconciles the two typings of one
published block against each other, which is the gap that lets a second reader go stale while the first stays
green.

Five populations, each derived from the bytes on every run rather than copied here:
  - the **wire**: the keys `market_view()`, `transfer_window()` and `season_windows()` publish — the view's own,
    and the blocks inside it (`constants`, `totals`) — read out of `apps/api/app/services/simulation/market.py`
    with a depth-tracking scan that respects Python's strings; the bodies hold nested dicts, f-strings with
    braces in them and docstrings full of punctuation, and a regex that stops at the first bracket it likes is a
    scan that narrows itself;
  - the **type**: the properties `MarketView`, `MarketWindow`, `MarketView["constants"]`, `MarketView["totals"]`
    and `MarketWindow["windows"]` declare, read out of `lib/market.ts` through the repo's own TypeScript,
    following an inline object literal or a named alias as the field is written;
  - the **reader**: the property accesses the market page makes on the object it was handed, read out of
    `app/career/[slug]/market/page.tsx`. A name counts as read *for this block* only when the access is rooted at
    the page's own binding of `view.window` — `.state` and `.label` are words other objects answer to, and a census
    that confused them would certify a blind page as wired. One hop is followed: the row a `windows.map(...)`
    hands its callback is read the same way as the block itself. The totals block is read on a second plane:
    the page hands the whole block to `MarketTools`, and the component reads it under its own prop name — a
    seam that is a clause, re-measured on every run, not a convention the census takes on faith.
  - the **ledger**: a published key with no reader can be named, but only with a reason the bytes re-measure —
    a reason that stops being true must stop excusing the key the same run.
  - the **moves**: the ledger's row blocks (`move_row`, `wage_row`, `award_row`, `gate_row`) publish one shape
    each; their union is the move row's published key set, judged against the `Move` type the web tier declares,
    and every declared field must be read by the page's `view.moves.map(...)` callback.

Checks, each able to refuse on its own:
  1  every file the census needs was readable                                    — an unread file is not an empty one
  2  every scan found a population                                              — vacuity: a scan that finds nothing must not read as agreement
  3  a function that can return two shapes publishes the same keys in both       — a career with no horizon must not answer a smaller block
  4  the view's published keys are the keys the web tier says it holds           — both directions, by name
  5  the window block's published keys are the keys `MarketWindow` declares      — both directions, by name
  6  a signing range's published keys are the keys its element type declares      — the block's inner level, judged the same way
  7  every field the window block declares is read by the page that shows the market
  8  every field a signing range holds is read by that page
  9  every constant the view publishes is typed, and the window's own constants are read
  10 every published view key has a reader on the page, or is named with the reason
  11 an exemption the bytes stopped earning is stale                             — a ledger row is a predicate, re-measured every run
  12 the totals block's published keys are the keys `MarketView["totals"]` declares — the block inside the block, judged the same way
  13 every field the totals block declares is read on the page or through the seam, or named with a reason the bytes re-measure
  14 a totals exemption the bytes stopped earning is stale                       — the same discipline as 11, on the new ledger
  15 the moves element type's published keys are the keys `Move` declares        — the ledger row's shape, judged both directions
  16 every field `Move` declares is read by the page's moves-row callback, or named with a reason the bytes re-measure
  17 a moves exemption the bytes stopped earning is stale                        — the same discipline as 11, on the moves ledger

Files only: no server, no browser, no port. The arithmetic a live tier re-derives from these fields is
`scripts/qa-market.mjs`'s; this gate's job is to refuse a *missing reader*, which no browser can tell apart from a
field that was never published.
*/

import { readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

// `fileURLToPath`, never `URL.pathname`: this repo's own path is non-ASCII and the pathname form comes back
// percent-encoded, which no filesystem call resolves. The two overrides point the whole census at an arm plane.
const WEB = resolve(process.env.QA_WIRE_WEB ? process.env.QA_WIRE_WEB : fileURLToPath(new URL("..", import.meta.url)));
const API = resolve(process.env.QA_WIRE_API ? process.env.QA_WIRE_API : join(WEB, "..", "api"));

const MARKET_PY = join(API, "app/services/simulation/market.py");
const TYPES_TS = join(WEB, "lib/market.ts");
const PAGE_TSX = join(WEB, "app/career/[slug]/market/page.tsx");
const TOOLS_TSX = join(WEB, "components/MarketTools.tsx");

// Vacuity floors, not ratchets: the claim is the set equality, and these only refuse a scan that found nothing.
const FLOOR_VIEW_KEYS = 10;
const FLOOR_WINDOW_KEYS = 8;
const FLOOR_RANGE_KEYS = 3;
const FLOOR_CONSTANT_KEYS = 5;
const FLOOR_TOTALS_KEYS = 5;
const FLOOR_MOVE_KEYS = 10;

const checks = [];
const check = (name, ok, detail = "") => {
  checks.push({ name, ok, detail });
};

// --- the wire: the keys the API's dicts publish ---------------------------------------------------------------

/** The index just past a string literal that opens at `at`, recognising `"""`/`'''` first and then `"`/`'`,
 * with up to three prefix letters (f, r, b and their combinations) skipped. A line that runs out of quotes is a
 * line the scan walks past rather than a scan that stops. */
function pastString(source, at) {
  const prefix = /^[A-Za-z]{1,3}(?=["'])/.test(source.slice(at, at + 4)) ? source.slice(at, at + 4).match(/^[A-Za-z]+/)[0].length : 0;
  const quote = source[at + prefix];
  if (quote !== '"' && quote !== "'") return at;
  const run = quote.repeat(3);
  if (source.startsWith(run, at + prefix)) {
    const close = source.indexOf(run, at + prefix + 3);
    return close < 0 ? source.length : close + 3;
  }
  let j = at + prefix + 1;
  while (j < source.length && source[j] !== quote && source[j] !== "\n") j += source[j] === "\\" ? 2 : 1;
  return j + 1;
}

/**
 * The body of a module-level or nested `def`, found from its signature rather than its line number.
 *
 * The parameter list closes at the matching paren, found by depth: a signature ending `-> dict[str, Any]:`
 * contains no `):`, so a scan that looked for one read the *next* function's body and graded `transferable()`'s
 * keys as the window's. The body ends at the first non-blank line indented no deeper than the `def` itself.
 */
function functionBody(source, defAt) {
  const defLineStart = source.lastIndexOf("\n", defAt) + 1;
  const defIndent = source.slice(defLineStart, defAt).match(/^[\s]*/)[0].length;
  let depth = 0;
  let i = source.indexOf("(", defAt);
  if (i < 0) return null;
  for (; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === "(") depth += 1;
    else if (ch === ")") {
      depth -= 1;
      if (depth === 0) break;
    } else if (ch === '"' || ch === "'") i = pastString(source, i) - 1;
  }
  const bodyStart = source.indexOf("\n", i);
  if (bodyStart < 0) return null;
  let bodyEnd = source.length;
  let cursor = bodyStart + 1;
  while (cursor < source.length) {
    const newline = source.indexOf("\n", cursor);
    const lineEnd = newline < 0 ? source.length : newline;
    const line = source.slice(cursor, lineEnd);
    if (line.trim() !== "" && line.length - line.trimStart().length <= defIndent) {
      bodyEnd = cursor;
      break;
    }
    cursor = lineEnd + 1;
  }
  return { start: bodyStart + 1, end: bodyEnd };
}

/**
 * Every dict a Python function publishes — as a `return { … }` or as a `.append({ … })` — each one read to its
 * outermost keys, with the keys of the nested dicts kept beside the key that holds them.
 *
 * `.append` is not `return\s*\{`: a list built by `merged.append({...})` has the paren in the way, and a census
 * that read only bare returns would grade the signing ranges from an empty population.
 */
function pythonPublishedDicts(source, functionName) {
  const defAt = source.indexOf(`def ${functionName}(`);
  if (defAt < 0) return { error: `no function named ${functionName}`, shapes: [] };
  const body = functionBody(source, defAt);
  if (!body) return { error: `the body of ${functionName} could not be read`, shapes: [] };
  const text = source.slice(body.start, body.end);
  const shapes = [];
  for (const opener of [/\breturn\s*\{/g, /\.append\(\s*\{/g]) {
    let match;
    while ((match = opener.exec(text)) !== null) {
      shapes.push(scanDict(source, body.start + match.index + match[0].length - 1));
    }
  }
  return { shapes, body };
}

/**
 * One dict literal, from its `{`: its outermost keys, and the keys one level deeper grouped by the key holding
 * them — `constants` in the view, `career` and `market` too, so the nested populations come out of the same scan
 * that produced the outer one instead of a second search that could disagree with it.
 *
 * Only a string literal followed, after whitespace, by a colon *at that depth* is a key, which is what lets
 * prose in a docstring, a colon in an f-string and a subscript like `containing["label"]` all sit inside a
 * published dict without any of them being read as one.
 */
function scanDict(source, braceAt) {
  const keys = [];
  const children = {};
  const lastAtDepth = {};
  let depth = 0;
  let i = braceAt;
  while (i < source.length) {
    const ch = source[i];
    if (ch === "{" || ch === "[" || ch === "(") {
      depth += 1;
      i += 1;
      continue;
    }
    if (ch === "}" || ch === "]" || ch === ")") {
      depth -= 1;
      i += 1;
      if (depth === 0) break;
      continue;
    }
    if (ch === "#") {
      const newline = source.indexOf("\n", i);
      i = newline < 0 ? source.length : newline;
      continue;
    }
    if (source[i] === '"' || source[i] === "'" || /^[A-Za-z]{1,3}(?=["'])/.test(source.slice(i, i + 4))) {
      const at = i;
      const prefix = /^[A-Za-z]{1,3}(?=["'])/.test(source.slice(at, at + 4)) ? source.slice(at, at + 4).match(/^[A-Za-z]+/)[0].length : 0;
      const quote = source[at + prefix];
      if (quote !== '"' && quote !== "'") {
        i += 1;
        continue;
      }
      const run = quote.repeat(3);
      if (source.startsWith(run, at + prefix)) {
        i = pastString(source, at);
        continue;
      }
      let j = at + prefix + 1;
      while (j < source.length && source[j] !== quote && source[j] !== "\n") j += source[j] === "\\" ? 2 : 1;
      const literal = source.slice(at + prefix + 1, j);
      let after = j + 1;
      while (after < source.length && /\s/.test(source[after])) after += 1;
      if (source[after] === ":") {
        if (depth === 1) keys.push(literal);
        if (depth === 1 || depth === 2) lastAtDepth[depth] = literal;
        if (depth === 2) {
          const owner = lastAtDepth[1];
          if (owner) (children[owner] ||= []).push(literal);
        }
      }
      i = after;
      continue;
    }
    i += 1;
  }
  return { keys, children };
}

const union = (shapes) => [...new Set(shapes.map((shape) => shape.keys).flat())];

// --- the type: the properties the web tier declares, following inline literals and named aliases ---------------

const typeSource = (text, file) => ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

/** The object literal a `type X = { … }` alias declares. */
function membersOfAlias(source, typeName) {
  let found = null;
  const visit = (node) => {
    if (ts.isTypeAliasDeclaration(node) && node.name.text === typeName && ts.isTypeLiteralNode(node.type)) {
      found = node.type;
      return;
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return found;
}

/**
 * The object literal a type node stands for, however the field is written: an inline literal, an array of one, a
 * named alias in the same file, or an array of one. Anything else returns null, and the caller names the level it
 * could not follow rather than pretending the level does not exist.
 */
function literalNodeFor(source, node) {
  if (!node) return null;
  if (ts.isTypeLiteralNode(node)) return node;
  if (ts.isArrayTypeNode(node)) return literalNodeFor(source, node.elementType);
  if (ts.isTypeReferenceNode(node)) {
    const name = node.typeName.getText(source);
    if (name === "Array" && node.typeArguments?.length === 1) return literalNodeFor(source, node.typeArguments[0]);
    return membersOfAlias(source, name);
  }
  return null;
}

const propertyNames = (source, literal) => literal.members.filter(ts.isPropertySignature).map((m) => m.name.getText(source).replace(/^["']|["']$/g, ""));

/** The fields a type declares, stepping down through `fieldPath` one object level at a time. */
function declaredFields(source, typeName, fieldPath = []) {
  let current = membersOfAlias(source, typeName);
  if (!current) return { names: [], followed: false, note: `lib/market.ts declares no type ${typeName}` };
  for (const step of fieldPath) {
    const member = current.members.filter(ts.isPropertySignature).find((m) => m.name.getText(source) === step);
    if (!member) return { names: [], followed: false, note: `${typeName} declares no ${step}` };
    const next = literalNodeFor(source, member.type);
    if (!next) return { names: [], followed: false, note: `${typeName}.${step} is ${member.type.getText(source)} — an object literal this census cannot follow` };
    current = next;
  }
  return { names: propertyNames(source, current), followed: true };
}

// --- the reader: what the page actually asks of the object it was handed ---------------------------------------

/**
 * The property names the page reads off its own binding of the window block, and off the rows that binding hands
 * to a callback.
 *
 * A row variable is a row because of its *call site*: `signing.windows.map((range) => …)` hands `range` out only
 * when `signing` is the page's binding of the block and `windows` is one of the array fields being censused. The
 * callback's body is then walked with the row bound as its own root, so those reads never escape it and a `range`
 * declared somewhere else in the file is nobody's row — which is what makes the shape of the body (a template, a
 * JSX element, a sentence built by `t(…)` before the row is touched) irrelevant.
 *
 * Candidates are collected on the first walk and seeded after it: the walk reaches a callback's body before the
 * callback's own node, and the binding that hands the rows out can sit below the JSX that shows them, so no root
 * exists yet while the bodies go past. A callback whose owner never became a root is not followed, and its fields
 * then count as unread rather than escaping the census.
 */
function readFields(text, fileName, rootExpressionText, arrayFields) {
  const source = typeSource(text, fileName);
  const roots = new Set();
  const reads = new Set();
  const candidates = [];
  const readOff = (node, owner) => {
    if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === owner) reads.add(node.name.text);
    if (ts.isElementAccessExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === owner && node.argumentExpression && ts.isStringLiteral(node.argumentExpression)) reads.add(node.argumentExpression.text);
    ts.forEachChild(node, (child) => readOff(child, owner));
  };
  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && node.initializer && node.initializer.getText(source) === rootExpressionText && ts.isIdentifier(node.name)) {
      roots.add(node.name.text);
    }
    if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression) && roots.has(node.expression.text)) {
      reads.add(node.name.text);
    }
    if (ts.isElementAccessExpression(node) && ts.isIdentifier(node.expression) && roots.has(node.expression.text) && node.argumentExpression && ts.isStringLiteral(node.argumentExpression)) {
      reads.add(node.argumentExpression.text);
    }
    if ((ts.isArrowFunction(node) || ts.isFunctionExpression(node)) && node.parameters.length === 1 && ts.isIdentifier(node.parameters[0].name)) {
      const parent = node.parent;
      if (ts.isCallExpression(parent) && parent.arguments[parent.arguments.length - 1] === node && ts.isPropertyAccessExpression(parent.expression)) {
        // The array a callback is handed rows from is the call's *target*, not its name: `signing.windows.map` is
        // a PropertyAccess whose name is the verb `map` and whose target is `signing.windows` — one hop further
        // names `signing` as the owner and `windows` as the field the row came from.
        const array = ts.isPropertyAccessExpression(parent.expression) ? parent.expression.expression : parent.expression;
        const owner = ts.isPropertyAccessExpression(array) ? array.expression.getText(source) : array.getText(source);
        const field = ts.isPropertyAccessExpression(array) ? array.name.text : "";
        candidates.push({ body: node.body, param: node.parameters[0].name.text, owner, field });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  const rows = [];
  for (const candidate of candidates) {
    if (!roots.has(candidate.owner) || !arrayFields.includes(candidate.field)) continue;
    rows.push(`${candidate.param} ← ${candidate.owner}.${candidate.field}`);
    readOff(candidate.body, candidate.param);
  }
  return { reads, roots: [...roots], rows };
}

/** Every property read off one named local, whatever that local holds. */
function readsOfLocal(text, fileName, localText) {
  const source = typeSource(text, fileName);
  const reads = new Set();
  const visit = (node) => {
    if (ts.isPropertyAccessExpression(node) && node.expression.getText(source) === localText) reads.add(node.name.text);
    ts.forEachChild(node, visit);
  };
  visit(source);
  return reads;
}

/** Whether a JSX element passes `prop={expression}` with exactly the expression named. */
function passesProp(text, fileName, propName, expressionText) {
  const source = typeSource(text, fileName);
  let found = false;
  const visit = (node) => {
    if (
      ts.isJsxAttribute(node) &&
      node.name.getText(source) === propName &&
      node.initializer &&
      ts.isJsxExpression(node.initializer) &&
      node.initializer.expression &&
      node.initializer.expression.getText(source) === expressionText
    ) {
      found = true;
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return found;
}

// --- measure ---------------------------------------------------------------------------------------------

const marketSource = existsSync(MARKET_PY) ? readFileSync(MARKET_PY, "utf8") : null;
const typesText = existsSync(TYPES_TS) ? readFileSync(TYPES_TS, "utf8") : null;
const pageText = existsSync(PAGE_TSX) ? readFileSync(PAGE_TSX, "utf8") : null;
const toolsText = existsSync(TOOLS_TSX) ? readFileSync(TOOLS_TSX, "utf8") : null;
const unreadable = [[MARKET_PY, marketSource], [TYPES_TS, typesText], [PAGE_TSX, pageText], [TOOLS_TSX, toolsText]].filter(([, text]) => text === null).map(([p]) => p);

const viewScan = marketSource ? pythonPublishedDicts(marketSource, "market_view") : { shapes: [] };
const windowScan = marketSource ? pythonPublishedDicts(marketSource, "transfer_window") : { shapes: [] };
const rangeScan = marketSource ? pythonPublishedDicts(marketSource, "season_windows") : { shapes: [] };
// The ledger's move rows are built by seven row functions (`move_row`, `wage_row`, `award_row`, `gate_row`,
// `upkeep_ledger_row`, `season_ticket_ledger_row`, `training_ledger_row`), each publishing its own dict shape. The move row's published key set is the union of all seven — a row any one
// of them adds shows up on the ledger, and a key any one of them drops is invisible to readers.
const moveRowScan = marketSource ? pythonPublishedDicts(marketSource, "move_row") : { shapes: [] };
const wageRowScan = marketSource ? pythonPublishedDicts(marketSource, "wage_row") : { shapes: [] };
const awardRowScan = marketSource ? pythonPublishedDicts(marketSource, "award_row") : { shapes: [] };
const gateRowScan = marketSource ? pythonPublishedDicts(marketSource, "gate_row") : { shapes: [] };
const upkeepRowScan = marketSource ? pythonPublishedDicts(marketSource, "upkeep_ledger_row") : { shapes: [] };
const seasonTicketRowScan = marketSource ? pythonPublishedDicts(marketSource, "season_ticket_ledger_row") : { shapes: [] };
const trainingRowScan = marketSource ? pythonPublishedDicts(marketSource, "training_ledger_row") : { shapes: [] };
const moveKeys = union([
  ...moveRowScan.shapes,
  ...wageRowScan.shapes,
  ...awardRowScan.shapes,
  ...gateRowScan.shapes,
  ...upkeepRowScan.shapes,
  ...seasonTicketRowScan.shapes,
  ...trainingRowScan.shapes,
]);
const viewKeys = union(viewScan.shapes);
const windowKeys = union(windowScan.shapes);
const rangeKeys = union(rangeScan.shapes);
// The constants come out of the same dict the view-population census just read — `children.constants` — so the two
// can never disagree about where the block ends, and a `constants` key that moved out of the view moves the floor.
const publishedConstants = viewScan.shapes.flatMap((shape) => shape.children.constants ?? []);
// The totals block is read the same way: it is a nested dict of counts a page can lose without any type
// or catalogue gate noticing, which is exactly the defect the five-population docstring names.
const publishedTotals = viewScan.shapes.flatMap((shape) => shape.children.totals ?? []);

const typesFile = typesText !== null ? typeSource(typesText, TYPES_TS) : null;
const declaredView = typesFile ? declaredFields(typesFile, "MarketView") : { names: [], followed: false };
const declaredWindow = typesFile ? declaredFields(typesFile, "MarketWindow") : { names: [], followed: false };
const declaredRange = typesFile ? declaredFields(typesFile, "MarketWindow", ["windows"]) : { names: [], followed: false };
const declaredConstants = typesFile ? declaredFields(typesFile, "MarketView", ["constants"]) : { names: [], followed: false };
const declaredTotals = typesFile ? declaredFields(typesFile, "MarketView", ["totals"]) : { names: [], followed: false };
const declaredMove = typesFile ? declaredFields(typesFile, "Move") : { names: [], followed: false };

const windowReads = pageText !== null ? readFields(pageText, PAGE_TSX, "view.window", ["windows"]) : { reads: new Set(), roots: [] };
const constantReads = pageText !== null ? readsOfLocal(pageText, PAGE_TSX, "view.constants") : new Set();
const viewReads = pageText !== null ? readsOfLocal(pageText, PAGE_TSX, "view") : new Set();
const budgetReads = pageText !== null ? readsOfLocal(pageText, PAGE_TSX, "budget") : new Set();
// The totals block is read on two planes, as the docstring says: the page's own `view.totals.x`, and the
// component the page hands the whole block to (`totals.x` inside MarketTools). Neither plane alone is
// evidence that the other one still reads the field.
const totalsReads = pageText !== null ? readsOfLocal(pageText, PAGE_TSX, "view.totals") : new Set();
const totalsSeamReads = toolsText !== null ? readsOfLocal(toolsText, TOOLS_TSX, "totals") : new Set();
// A component can read a prop nobody hands it. The seam is not "the file mentions `totals`"; it is the
// page passing this block at the call site, and that is measured from the page's own JSX.
const totalsSeamWired = pageText !== null && passesProp(pageText, PAGE_TSX, "totals", "view.totals");
// The moves array is read by the page's `view.moves.map((move) => …)` callback — the row binding is `move`, and
// the array field is `moves` on `view`. One hop follows the row into its callback body, the same way the signing
// ranges are followed through `signing.windows.map(...)`.
const moveReads = pageText !== null ? readFields(pageText, PAGE_TSX, "result.data", ["moves"]) : { reads: new Set(), roots: [] };

// --- 1 and 2 the census can see anything at all --------------------------------------------------------------
check(
  "1 every file the census needs was readable",
  unreadable.length === 0,
  unreadable.join(", "),
);
check(
  "2 every scan found a population — a scan that finds nothing must not read as agreement",
  viewKeys.length >= FLOOR_VIEW_KEYS &&
    windowKeys.length >= FLOOR_WINDOW_KEYS &&
    rangeKeys.length >= FLOOR_RANGE_KEYS &&
    publishedConstants.length >= FLOOR_CONSTANT_KEYS &&
    publishedTotals.length >= FLOOR_TOTALS_KEYS &&
    declaredView.followed &&
    declaredConstants.followed &&
    declaredTotals.followed,
  `wire view=${viewKeys.length} window=${windowKeys.length} range=${rangeKeys.length} constants=${publishedConstants.length} totals=${publishedTotals.length} | type followed=${[declaredView.followed, declaredWindow.followed, declaredRange.followed, declaredConstants.followed, declaredTotals.followed].join(",")} (${[declaredView, declaredWindow, declaredRange, declaredConstants, declaredTotals].map((d) => (d.followed ? "" : d.note)).filter(Boolean).join("; ") || "all"})`,
);

// --- 3 one function, one shape -------------------------------------------------------------------------------
const keyListsOf = (shapes) => shapes.map((shape) => shape.keys);
const shapeDiff = (shapes) => {
  if (shapes.length < 2) return [];
  const first = new Set(shapes[0]);
  const out = [];
  shapes.slice(1).forEach((keys, index) => {
    const here = new Set(keys);
    for (const k of first) if (!here.has(k)) out.push(`${k} missing from shape ${index + 2}`);
    for (const k of here) if (!first.has(k)) out.push(`${k} only in shape ${index + 2}`);
  });
  return out;
};
check(
  `3 the window block publishes one shape in every branch (${windowScan.shapes.length} published)`,
  windowScan.shapes.length >= 2 && shapeDiff(keyListsOf(windowScan.shapes)).length === 0,
  windowScan.shapes.length < 2 ? `only ${windowScan.shapes.length} shape found — the no-horizon branch is not in the census` : shapeDiff(keyListsOf(windowScan.shapes)).join(", "),
);
check(
  `3b the signing ranges publish one shape in every branch (${rangeScan.shapes.length} published)`,
  rangeScan.shapes.length >= 1 && shapeDiff(keyListsOf(rangeScan.shapes)).length === 0,
  shapeDiff(keyListsOf(rangeScan.shapes)).join(", "),
);

// --- 4, 5, 6 the wire's keys are the keys the web tier says it holds ------------------------------------------
const bothWays = (wire, typed) => ({
  missing: wire.filter((k) => !typed.includes(k)),
  extra: typed.filter((k) => !wire.includes(k)),
});
const viewDiff = bothWays(viewKeys, declaredView.names);
check(
  "4 the market view's published keys are exactly the keys MarketView declares",
  viewDiff.missing.length === 0 && viewDiff.extra.length === 0,
  `wire ${viewKeys.length} vs type ${declaredView.names.length}${viewDiff.missing.length ? ` — published, typed by nothing: ${viewDiff.missing.join(", ")}` : ""}${viewDiff.extra.length ? ` — declared, published by nothing: ${viewDiff.extra.join(", ")}` : ""}`,
);
const windowDiff = bothWays(windowKeys, declaredWindow.names);
check(
  "5 the window block's published keys are exactly the keys MarketWindow declares",
  declaredWindow.followed && windowDiff.missing.length === 0 && windowDiff.extra.length === 0,
  declaredWindow.followed
    ? `wire ${windowKeys.length} vs type ${declaredWindow.names.length}${windowDiff.missing.length ? ` — published, typed by nothing: ${windowDiff.missing.join(", ")}` : ""}${windowDiff.extra.length ? ` — declared, published by nothing: ${windowDiff.extra.join(", ")}` : ""}`
    : `lib/market.ts declares no MarketWindow — the block the door answers with ${windowKeys.length} fields is untyped`,
);
const rangeDiff = bothWays(rangeKeys, declaredRange.names);
check(
  "6 a signing range's published keys are exactly the keys its element type declares",
  declaredRange.followed && rangeDiff.missing.length === 0 && rangeDiff.extra.length === 0,
  declaredRange.followed
    ? `wire ${rangeKeys.length} vs type ${declaredRange.names.length}${rangeDiff.missing.length ? ` — published, typed by nothing: ${rangeDiff.missing.join(", ")}` : ""}${rangeDiff.extra.length ? ` — declared, published by nothing: ${rangeDiff.extra.join(", ")}` : ""}`
    : `the windows field could not be followed: ${declaredRange.note}`,
);

// --- 7 and 8 every declared field is read by the page that shows the market -----------------------------------
const unreadWindow = declaredWindow.names.filter((k) => !windowReads.reads.has(k));
check(
  `7 every field MarketWindow declares is read by the market page (${declaredWindow.names.length} fields)`,
  declaredWindow.names.length > 0 && unreadWindow.length === 0,
  declaredWindow.names.length === 0
    ? "the type declares no fields, so there was nothing here for the page to be asked to read"
    : unreadWindow.length
      ? `nothing asks: ${unreadWindow.join(", ")}`
      : `reads rooted at ${windowReads.roots.join(", ")}`,
);
const unreadRange = declaredRange.names.filter((k) => !windowReads.reads.has(k));
check(
  `8 every field a signing range holds is read by the market page (${declaredRange.names.length} fields)`,
  declaredRange.names.length > 0 && unreadRange.length === 0,
  declaredRange.names.length === 0
    ? "the range element type declares no fields, so there was nothing here for the page to be asked to read"
    : unreadRange.length
      ? `nothing asks: ${unreadRange.join(", ")}`
      : "each range row is read",
);

// --- 9 the constants block, and the two the window's own formula is built from --------------------------------
const constantsDiff = bothWays(publishedConstants, declaredConstants.names);
const windowConstants = publishedConstants.filter((k) => k.includes("window"));
const unreadWindowConstants = windowConstants.filter((k) => !constantReads.has(k));
check(
  `9 every constant the view publishes is typed by the web tier (${publishedConstants.length} published)`,
  constantsDiff.missing.length === 0 && constantsDiff.extra.length === 0 && unreadWindowConstants.length === 0,
  `${constantsDiff.missing.length ? `published, typed by nothing: ${constantsDiff.missing.join(", ")}. ` : ""}${constantsDiff.extra.length ? `declared, published by nothing: ${constantsDiff.extra.join(", ")}. ` : ""}${unreadWindowConstants.length ? `typed, read by nothing: ${unreadWindowConstants.join(", ")}` : ""}`,
);

// --- 10 and 11 every published key has a reader, or names the gate that judges it ------------------------------
// One row, and its reason is a predicate the census re-measures: `demo_data` is published beside `is_demo_data`
// with the same value, so a reader that reads one has the fact. A ledger row whose pair stopped being read is the
// shape this clause exists to refuse — an exemption that outlives its own argument.
const LEDGER = [
  {
    key: "demo_data",
    reason: "a second name for the boolean the page reads as `is_demo_data`, published by the same dict",
    proof: () =>
      viewKeys.includes("demo_data") &&
      viewKeys.includes("is_demo_data") &&
      /"demo_data":\s*True/.test(marketSource ?? "") &&
      /"is_demo_data":\s*True/.test(marketSource ?? "") &&
      viewReads.has("is_demo_data"),
  },
];
const ledger = LEDGER.map((row) => ({ ...row, holds: row.proof() }));
const unheld = viewKeys.filter((k) => !viewReads.has(k) && !ledger.some((row) => row.key === k && row.holds));
check(
  `10 every published view key has a reader on the page, or is named with the reason (${ledger.filter((r) => r.holds).length} named)`,
  viewKeys.length >= FLOOR_VIEW_KEYS && unheld.length === 0,
  unheld.length ? `nothing asks: ${unheld.join(", ")}` : `${viewReads.size} of ${viewKeys.length} keys read by the page`,
);
const stale = ledger.filter((row) => !row.holds);
check(
  "11 an exemption the bytes stopped earning is stale",
  stale.length === 0,
  stale.map((row) => `${row.key} — ${row.reason}`).join(", "),
);

// --- 12, 13 and 14 the totals block, on the page and through the seam ----------------------------------------
const totalsDiff = bothWays(publishedTotals, declaredTotals.names);
check(
  `12 the totals block publishes exactly the keys \`MarketView["totals"]\` declares (${publishedTotals.length} published)`,
  declaredTotals.followed && totalsDiff.missing.length === 0 && totalsDiff.extra.length === 0,
  declaredTotals.followed
    ? `wire ${publishedTotals.length} vs type ${declaredTotals.names.length}${totalsDiff.missing.length ? ` — published, typed by nothing: ${totalsDiff.missing.join(", ")}` : ""}${totalsDiff.extra.length ? ` — declared, published by nothing: ${totalsDiff.extra.join(", ")}` : ""}`
    : `MarketView["totals"] could not be followed: ${declaredTotals.note}`,
);
const totalsReadsAll = new Set([...totalsReads, ...totalsSeamReads]);
// A count is not a second copy of the fact: `view.moves` is the ledger every one of these totals counts,
// and the page prints that array row by row. `wage_rows` is additionally printed on the budget block.
const TOTALS_LEDGER = [
  { key: "moves", reason: "the page prints the ledger rows themselves (`view.moves`); this is that array's length", proof: () => viewReads.has("moves") && publishedTotals.includes("moves") },
  { key: "wage_rows", reason: "the budget block prints `wage_rows`; this is the same charge count on the totals block", proof: () => budgetReads.has("wage_rows") && publishedTotals.includes("wage_rows") },
  { key: "grant_rows", reason: "grant rows are printed through `view.moves`; this is the count of that same ledger", proof: () => viewReads.has("moves") && publishedTotals.includes("grant_rows") },
  { key: "cup_prize_rows", reason: "cup prize rows are printed through `view.moves`; this is the count of that same ledger", proof: () => viewReads.has("moves") && publishedTotals.includes("cup_prize_rows") },
  { key: "bonus_rows", reason: "objective bonus rows are printed through `view.moves`; this is the count of that same ledger", proof: () => viewReads.has("moves") && publishedTotals.includes("bonus_rows") },
  { key: "gate_rows", reason: "gate rows are printed through `view.moves`; this is the count of that same ledger", proof: () => viewReads.has("moves") && publishedTotals.includes("gate_rows") },
  { key: "stadium_rows", reason: "stadium rows are printed through `view.moves`; this is the count of that same ledger", proof: () => viewReads.has("moves") && publishedTotals.includes("stadium_rows") },
];
const totalsLedger = TOTALS_LEDGER.map((row) => ({ ...row, holds: row.proof() }));
const unreadTotals = declaredTotals.names.filter((k) => !totalsReadsAll.has(k) && !totalsLedger.some((row) => row.key === k && row.holds));
check(
  `13 every field the totals block declares is read by the page or through the seam, or named with a reason (${totalsLedger.filter((r) => r.holds).length} named)`,
  declaredTotals.names.length > 0 && totalsSeamWired && unreadTotals.length === 0,
  !totalsSeamWired
    ? "the market page does not pass `totals={view.totals}` to MarketTools"
    : unreadTotals.length
      ? `nothing asks: ${unreadTotals.join(", ")}`
      : `${totalsReads.size} page read(s) rooted at view.totals, ${totalsSeamReads.size} seam read(s) rooted at totals`,
);
const totalsStale = totalsLedger.filter((row) => !row.holds);
check(
  "14 a totals exemption the bytes stopped earning is stale",
  totalsStale.length === 0,
  totalsStale.map((row) => `${row.key} — ${row.reason}`).join(", "),
);

// The moves row's LEDGER: published fields the page intentionally does not read per-row.
// Each reason is a predicate the bytes re-measure — a reason that stops being true stops excusing the key.
const MOVES_LEDGER = [
  {
    key: "player_id",
    reason: "internal database identifier, never displayed on the ledger row",
    proof: () => true,
  },
  {
    key: "player_slug",
    reason: "used to construct player_path in Python; the page reads player_path instead",
    proof: () => moveKeys.includes("player_slug") && moveKeys.includes("player_path"),
  },
  {
    key: "position",
    reason: "not displayed in the current ledger UI",
    proof: () => true,
  },
  {
    key: "expiry_round",
    reason: "internal term bookkeeping; the page displays loan_until_round instead",
    proof: () => true,
  },
  {
    key: "attendance",
    reason: "only a gate row carries this; not displayed per-row in the current UI",
    proof: () => moveKeys.includes("attendance"),
  },
  {
    key: "ticket_price",
    reason: "only a gate row carries this; not displayed per-row in the current UI",
    proof: () => moveKeys.includes("ticket_price"),
  },
  {
    key: "season_index",
    reason: "only a board grant row carries this; not displayed per-row in the current UI",
    proof: () => moveKeys.includes("season_index"),
  },
  {
    key: "promotion",
    reason: "only a board grant row carries this; not displayed per-row in the current UI",
    proof: () => moveKeys.includes("promotion"),
  },
  {
    key: "stage",
    reason: "only a cup prize row carries this; not displayed per-row in the current UI",
    proof: () => moveKeys.includes("stage"),
  },
  {
    key: "tie_id",
    reason: "only a gate row carries this; not displayed per-row in the current UI",
    proof: () => moveKeys.includes("tie_id"),
  },
  {
    key: "competition",
    reason: "only a gate row carries this; not displayed per-row in the current UI",
    proof: () => moveKeys.includes("competition"),
  },
  {
    key: "capacity",
    reason: "only an upkeep row carries this; the seats are stated in its detail sentence",
    proof: () => moveKeys.includes("capacity") && moveKeys.includes("seat_rate_pct"),
  },
  {
    key: "seat_rate_pct",
    reason: "only an upkeep row carries this; the rate is stated in its detail sentence",
    proof: () => moveKeys.includes("seat_rate_pct") && moveKeys.includes("capacity"),
  },
  {
    key: "created_at",
    reason: "not displayed in the current ledger UI",
    proof: () => true,
  },
];
// --- 15 and 16 the ledger's move rows, against the Move type ---------------------------------
const moveDiff = bothWays(moveKeys, declaredMove.names);
check(
  `15 the moves element type's published keys are the keys \`Move\` declares (${moveKeys.length} published)`,
  declaredMove.followed && moveDiff.missing.length === 0 && moveDiff.extra.length === 0,
  declaredMove.followed
    ? `wire ${moveKeys.length} vs type ${declaredMove.names.length}${moveDiff.missing.length ? ` — published, typed by nothing: ${moveDiff.missing.join(", ")}` : ""}${moveDiff.extra.length ? ` — declared, published by nothing: ${moveDiff.extra.join(", ")}` : ""}`
    : `lib/market.ts declares no \`Move\` type — the ledger row the wire answers with ${moveKeys.length} fields is untyped`,
);
const unreadMove = declaredMove.names.filter((k) => !moveReads.reads.has(k));
const movesLedger = MOVES_LEDGER.map((row) => ({ ...row, holds: row.proof() }));
const unreadMoveLedgered = unreadMove.filter((k) => !movesLedger.some((row) => row.key === k && row.holds));
check(
  `16 every field \`Move\` declares is read by the market page's moves-row callback, or named with a reason the bytes re-measure (${movesLedger.filter((r) => r.holds).length} named)`,
  declaredMove.names.length > 0 && unreadMoveLedgered.length === 0,
  unreadMoveLedgered.length ? `nothing asks: ${unreadMoveLedgered.join(", ")}` : `reads rooted at ${moveReads.roots.join(", ")}`,
);
const movesStale = movesLedger.filter((row) => !row.holds);
check(
  "17 a moves exemption the bytes stopped earning is stale",
  movesStale.length === 0,
  movesStale.map((row) => `${row.key} — ${row.reason}`).join(", "),
);

const failed = checks.filter((c) => !c.ok);
for (const c of checks) console.log(`${c.ok ? "PASS" : "FAIL"}  ${c.name}${c.detail ? ` — ${c.detail}` : ""}`);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
console.log(
  `  wire: view=${viewKeys.length} window=${windowKeys.length} range=${rangeKeys.length} constants=${publishedConstants.length} totals=${publishedTotals.length} moves=${moveKeys.length} | ` +
    `type: view=${declaredView.names.length} window=${declaredWindow.names.length} range=${declaredRange.names.length} constants=${declaredConstants.names.length} totals=${declaredTotals.names.length} move=${declaredMove.names.length} | ` +
    `page: ${windowReads.reads.size} window reads rooted at ${windowReads.roots.join(",") || "nothing"} (${windowReads.rows.join(", ") || "no row callback followed"}), ${viewReads.size} view reads, ${totalsReads.size} totals reads, ${totalsSeamReads.size} seam reads, ${moveReads.reads.size} move reads`,
);
console.log(`ran qa-wire-readers against ${WEB} and ${API}`);
process.exitCode = failed.length ? 1 : 0;
