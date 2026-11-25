#!/usr/bin/env node
/*
 * Right-to-left readiness: the layout is prepared before a right-to-left locale is offered.
 *
 * The catalogue layer is direction-agnostic — next-intl resolves a key whether the sentence is written in
 * Latin, Chinese or Arabic — but the layout is not. This project's stylesheet used physical properties
 * (`padding-left`, `text-align: right`, `left: 0`), so a right-to-left catalogue would have mirrored the
 * text and left the bullets, table headers, quote bands and the skip link on the wrong side. None of that is
 * visible today: all three shipped locales read left-to-right, so every gate that measures the rendered page
 * agrees the tree is correct. The defect is only reachable by adding a locale, which is exactly when it is
 * cheapest to have already refused.
 *
 * This gate does not ship an RTL locale. It holds the structure an RTL locale needs:
 *
 *   1  the population: every committed `.css` under `apps/web`, read from disk, never a typed list;
 *   2  the scanner is red on each shape it claims to judge — a scanner that cannot fail is not a judge;
 *   3  no physical horizontal declaration survives in that population: `left`/`right` offsets,
 *      `margin-*`/`padding-*`/`border-*-left/right`, physical corner radii, `text-align: left/right`,
 *      `float: left/right`. Logical equivalents (`inset-inline-start`, `margin-inline-end`,
 *      `text-align: start/end`, `border-start-end-radius`) move with `dir`;
 *   4  `textDirection` classifies the shipped locales as `ltr` and the RTL base languages as `rtl`, so the
 *      helper is called rather than assumed;
 *   5  the root layout passes that verdict to `<html dir>`, and a change to the attribute moves this check;
 *   6  both font stacks end in a generic family, so a script the stack does not name still gets a font;
 *   7  one `:lang(ar), :lang(he)` reset in globals.css zeroes `letter-spacing` and `text-transform` —
 *      cursive joining is not breakable tracking, and the gate refuses a tree without it;
 *   8  the three shapes whose *value* decides them — a box-shadow's X offset, an X-axis translate, a
 *      horizontal background position — are judged by their value, not by their name: a zero offset moves
 *      nothing in either direction, so it is exempt, and a value the bytes cannot resolve is refused
 *      rather than passed;
 *   9  every value the scanner judges is decidable from the bytes it reads, and every named exemption is
 *      still earned by the bytes at the place it names — a moved or rewritten declaration retires its own
 *      exemption;
 *  10  the scanner counts declarations, not lines: one line carrying two horizontal declarations is two
 *      findings, which is the unit a record quotes;
 *  11  a zero-valued declaration paints nothing and is not a finding — `box-shadow: none` and `transform: none`
 *      are proven exempt by planted bytes, not asserted;
 *  12  property and keyword spellings are read case-insensitively, because CSS is: `transform: TranslateX(9px)`
 *      in the witness is charged on the same terms as the lowercase form;
 *  13  an offset that is *meant* to mirror is answered by a `[dir="rtl"]` counterpart of the opposite sign, and
 *      both halves are charged by the bytes at the lines they name — a half-true mirror is refused.
 *
 * Files only: no server, no browser, no port. Register it in `scripts/check.sh` and CI beside the other
 * static gates, or `qa-gate-inventory.mjs` correctly reports it as a script nothing invokes.
 */

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

// `fileURLToPath`, never `URL.pathname`: the repository's own path is non-ASCII on this machine.
const WEB = fileURLToPath(new URL("..", import.meta.url));
const SKIP = new Set(["node_modules", ".git", ".next"]);

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/* 1 — the population: every CSS file under apps/web, minus build and dependency directories. */
const cssFiles = [];
(function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".next")) continue;
    if (SKIP.has(entry.name)) continue;
    const path = join(dir, entry.name);
    if (entry.isDirectory()) walk(path);
    else if (entry.name.endsWith(".css")) cssFiles.push(path);
  }
})(WEB);
cssFiles.sort();
const rel = (file) => relative(WEB, file).split(sep).join("/");

let unreadable = [];
const bodies = new Map();
for (const file of cssFiles) {
  try {
    // The checkout may carry CRLF (`core.autocrlf` is true and the repository has no `.gitattributes`), so
    // the CSS is judged from folded bytes: a value's last token must not depend on which tree the gate runs on.
    bodies.set(file, readFileSync(file, "utf8").replace(/\r\n/g, "\n"));
  } catch (err) {
    unreadable.push(`${rel(file)} (${err.code ?? err.message})`);
  }
}
check(
  "every stylesheet in the population was readable",
  cssFiles.length >= 10 && unreadable.length === 0,
  `${cssFiles.length} file(s)${unreadable.length ? `, unreadable: ${unreadable.join(", ")}` : ""}`,
);

/* The shapes. Each is a declaration whose meaning is “the left/right edge of the screen” rather than “the
 * start/end edge of the writing direction”. `left`/`right` inside a comment are not declarations, so comments
 * are removed first; a custom property whose *name* ends in `-left` is not a hit because the name is followed
 * by `:` only after the property token. Property and keyword names are ASCII case-insensitive in CSS, so every
 * pattern carries `i`: `transform: TranslateX(3px)` is the same declaration to a browser and to this scan, and
 * a judge that read only the lowercase spelling let six shipped `translateX` offsets go unjudged until Item 315
 * found them by grepping the tree rather than by trusting the gate.
 *
 * Each entry is [shape, a pattern whose group 1 is the declaration itself, an optional judge]. The pattern is
 * global and every match is one finding, so a line that declares the same shape twice is two findings — the
 * unit a reader counts when a record says "six declarations", not the line. */
const PHYSICAL = [
  ["a horizontal offset", /(?:^|[;{])\s*((?:left|right)\s*:\s*[^;{}]+)/gi],
  ["a horizontal margin, padding or border", /(?:^|[;{])\s*((?:margin|padding|border)-(?:left|right)\s*:\s*[^;{}]+)/gi],
  ["a physical corner radius", /(?:^|[;{])\s*(border-(?:top|bottom)-(?:left|right)-radius\s*:\s*[^;{}]+)/gi],
  ["physical text alignment", /(?:^|[;{])\s*(text-align\s*:\s*(?:left|right)\b[^;{}]*)/gi],
  ["a physical float", /(?:^|[;{])\s*(float\s*:\s*(?:left|right)\b[^;{}]*)/gi],
  ["a horizontal box-shadow offset", /(?:^|[;{])\s*(?:-webkit-)?(box-shadow\s*:\s*[^;{}]+)/gi, judgeShadow],
  ["an X-axis transform", /(?:^|[;{])\s*(transform\s*:\s*[^;{}]+)/gi, judgeTransform],
  ["a horizontal background position", /(?:^|[;{])\s*(background-position(?:-x)?\s*:\s*[^;{}]+)/gi, judgeBackground],
];

/* Zero is not a direction: an offset of nothing moves nothing in either. The rest is decided by the caller's
 * named exemptions, because "is this geometry meant to mirror?" is a question about the page, not the token. */
const LENGTH = /^[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:px|rem|em|%|vw|vh|ch|ex|pt|cm|mm|in)?$/;
const isZero = (token) => token !== null && /^[-+]?0(?:\.0+)?(?:px|rem|em|%|vw|vh|ch|ex|pt)?$/i.test(token);

const properties = new Map();
for (const css of bodies.values()) {
  for (const match of css.matchAll(/(--[A-Za-z0-9-]+)\s*:\s*([^;{}]+)/g)) {
    if (!properties.has(match[1])) properties.set(match[1], match[2].trim());
  }
}

function resolve(value, depth = 0) {
  if (depth > 4 || !value.includes("var(")) return value;
  const done = value.replace(/var\(\s*(--[A-Za-z0-9-]+)\s*(?:,\s*([^()]*))?\)/g, (_, name, fallback) => {
    const held = properties.get(name);
    return held !== undefined ? held : (fallback ?? "");
  });
  return done === value ? done : resolve(done, depth + 1);
}

function layers(value) {
  const out = [];
  let depth = 0;
  let current = "";
  for (const char of value) {
    if (char === "(") depth += 1;
    if (char === ")") depth -= 1;
    if (char === "," && depth === 0) {
      out.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  out.push(current);
  return out.filter((layer) => layer.trim().length > 0);
}

/** The first bare length of a value, with `inset` stepped over. Null when the leading token is not a length —
 *  a colour or a token no var() could resolve — which the undecidable check owns, never a silent pass. */
function firstLength(value) {
  const bare = value.replace(/\([^)]*\)/g, " ");
  for (const token of bare.split(/\s+/)) {
    if (!token || token.toLowerCase() === "inset") continue;
    return LENGTH.test(token) ? token : null;
  }
  return null;
}

function judgeShadow(declaration) {
  const value = resolve(declaration.replace(/^box-shadow\s*:\s*/i, ""));
  /* `none` declares no layer at all. There is nothing painted, so there is nothing that could fail to follow
   * the writing direction — the same reasoning that lets a transform naming no X-axis offset pass. */
  if (/^none$/i.test(value.trim())) return { none: true };
  const offsets = layers(value).map((layer) => firstLength(layer.trim()));
  if (offsets.length === 0 || offsets.some((token) => token === null)) return { undecidable: value.trim() || declaration };
  if (offsets.every(isZero)) return { exempt: "the horizontal offset is zero, so nothing moves in either direction" };
  return { note: offsets.filter((token) => !isZero(token)).join(", ") };
}

function judgeTransform(declaration) {
  const value = declaration.replace(/^transform\s*:\s*/i, "");
  /* `translate`, `translateX` and `translate3d` name an offset on the horizontal axis; `translateY` and
   * `translateZ` do not, and neither is swallowed here because the alternation is not a prefix match. The
   * spelling is case-insensitive because CSS says so — this judge read only lowercase until Item 315. */
  const hits = [...value.matchAll(/translate(?:3d|x)?\s*\(([^)]*)\)/gi)];
  if (hits.length === 0) return { none: true }; // a scale, a rotation or a translateY names no X-axis offset
  const offsets = hits.map((hit) => firstLength(hit[1].split(",")[0].trim()) ?? null);
  if (offsets.some((token) => token === null)) return { undecidable: value.trim() };
  if (offsets.every(isZero)) return { exempt: "the X-axis translate is zero, so nothing moves in either direction" };
  return { note: offsets.filter((token) => !isZero(token)).join(", ") };
}

function judgeBackground(declaration) {
  const value = resolve(declaration.replace(/^background-position(?:-x)?\s*:\s*/i, ""));
  const firsts = layers(value).map((layer) => layer.trim().split(/\s+/)[0] ?? "").filter((token) => token);
  if (firsts.length === 0) return { undecidable: value.trim() || declaration };
  if (firsts.some((token) => /^(left|right)$/i.test(token))) return { note: firsts.filter((token) => /^(left|right)$/i.test(token)).join(", ") };
  const offsets = firsts.filter((token) => !["center", "top", "bottom"].includes(token));
  if (offsets.length === 0) return { exempt: "the position is on the vertical axis, where direction has no effect" };
  if (offsets.every((token) => isZero(token))) return { exempt: "the horizontal offset is zero, so nothing moves in either direction" };
  if (offsets.some((token) => !LENGTH.test(token))) return { undecidable: value.trim() };
  return { note: offsets.join(", ") };
}

function scan(css, file) {
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "));
  const findings = [];
  const exempt = [];
  const undecidable = [];
  for (const [lineNumber, line] of stripped.split(/\r?\n/).entries()) {
    for (const [shape, pattern, judge] of PHYSICAL) {
      for (const match of line.matchAll(pattern)) {
        const text = match[1].trim().replace(/\s+/g, " ");
        const finding = { line: lineNumber + 1, shape, text, file };
        if (!judge) {
          findings.push(finding);
          continue;
        }
        const verdict = judge(text);
        if (verdict.none) continue;
        if (verdict.undecidable !== undefined) undecidable.push({ ...finding, value: verdict.undecidable });
        else if (verdict.exempt) exempt.push({ ...finding, reason: verdict.exempt });
        else findings.push({ ...finding, note: verdict.note });
      }
    }
  }
  return { findings, exempt, undecidable };
}

/* Named exemptions: the geometry that is *meant* to read the same in both directions. An exemption is earned
 * by the bytes at the place it names, so moving or rewriting the declaration retires it by itself; a reason
 * that no longer matches is refused, never trusted. */
const EXEMPT = [
  {
    file: "styles/video.css",
    line: 20,
    shape: "an X-axis transform",
    text: "transform: translate(-50%, -50%)",
    reason:
      "a symmetric 13 px ring centred on the point a detection measured: -50% of its own box on both axes, so " +
      "the offset is the element's half-width, not a direction. The coordinate that places it is an inline " +
      "style on the mark, outside a CSS scan — see the record's section on what this gate does not judge.",
  },
  {
    file: "app/progress/progress.css",
    line: 183,
    shape: "a horizontal background position",
    text: "background-position: 120% 0",
    reason:
      "one stop of a decorative skeleton shimmer, measured in the live route: background-position percentages " +
      "resolve against a negative free space (the image is 220% of the box), so the band travels left to right " +
      "and the 1.4 s track is identical byte for byte in dir=ltr and dir=rtl. The gradient is symmetric, so the " +
      "sweep carries no reading order to invert; `background-position-inline` would mirror it and Firefox has " +
      "no such property.",
  },
  {
    file: "app/progress/progress.css",
    line: 184,
    shape: "a horizontal background position",
    text: "background-position: -120% 0",
    reason: "the other stop of the same shimmer — see the exemption above it.",
  },
  {
    file: "styles/globals.css",
    line: 290,
    shape: "a horizontal background position",
    text: "background-position: 200% center",
    reason:
      "the empty-state pulse: a 56 px bar centred by `margin: 0 auto`, painted with a symmetric " +
      "transparent-accent-transparent gradient at background-size 200% 100%. Direction is not an input to " +
      "background-position, so the resolved offset is free space (0 − 1 box widths) times the percentage in both " +
      "writing modes — 200% answers −2 box widths either side of the split. Nothing here carries a reading order: " +
      "the bar has no text, and the sentence under it is laid out by the flow, which the document direction " +
      "already moves.",
  },
  {
    file: "styles/globals.css",
    line: 291,
    shape: "a horizontal background position",
    text: "background-position: -200% center",
    reason: "the other stop of the same pulse — see the exemption above it.",
  },
  {
    file: "styles/globals.css",
    line: 666,
    shape: "a horizontal background position",
    text: "background-position: 130% center",
    reason:
      "the skeleton's `fo-breathe` stop, on a block whose gradient is symmetric about its 50% light band and " +
      "whose background-size 240% 100% makes the free space negative (−1.4 box widths), so 130% resolves to " +
      "−1.82 box widths and −30% to +0.42. Both writing modes resolve the percentage against the same physical " +
      "padding box, so the pulse is byte-identical ltr and rtl — the property is physical, and here physical is " +
      "what the reader sees either way.",
  },
  {
    file: "styles/globals.css",
    line: 667,
    shape: "a horizontal background position",
    text: "background-position: -30% center",
    reason: "the other stop of the same skeleton pulse — see the exemption above it.",
  },
];

/* A mirror pair is not an exemption: it is the same geometry promised twice, once for each writing direction,
 * and the second half is scoped to `[dir="rtl"]`. The pair is earned by four bytes — the physical declaration
 * at its line, the counterpart at its line — and by the arithmetic between them: the two judged offsets have
 * to be exact opposites. A counterpart that drifts to the same sign, or to a different magnitude, is refused,
 * because a half-true mirror is worse than an open defect: it reads as cured. */
const MIRRORED = [
  {
    file: "styles/atlas.css",
    line: 73,
    shape: "an X-axis transform",
    text: "transform: translateX(3px)",
    mirrorLine: 81,
    mirrorText: "transform: translateX(-3px)",
    reason: "the atlas door steps into itself: +3 px from the reading edge, answered by −3 px under [dir=rtl]",
  },
  {
    file: "styles/atlas.css",
    line: 110,
    shape: "an X-axis transform",
    text: "transform: translateX(4px)",
    mirrorLine: 117,
    mirrorText: "transform: translateX(-4px)",
    reason: "the arrow inside the same door, composed with it: 7 px out of the reading edge in either direction",
  },
  {
    file: "styles/manual.css",
    line: 88,
    shape: "an X-axis transform",
    text: "transform: translateX(3px)",
    mirrorLine: 95,
    mirrorText: "transform: translateX(-3px)",
    reason: "the manual's door arrow, on the same terms as the atlas door's",
  },
  {
    file: "styles/globals.css",
    line: 582,
    shape: "an X-axis transform",
    text: "transform: translateX(-120%)",
    mirrorLine: 599,
    mirrorText: "transform: translateX(120%)",
    reason:
      "the card sheen parks off the reading-start edge: -120% of its own box in ltr, answered by +120% under " +
      "[dir=rtl], so the highlight never enters from the edge the text has already been read past",
  },
  {
    file: "styles/globals.css",
    line: 588,
    shape: "an X-axis transform",
    text: "transform: translateX(-120%)",
    mirrorLine: 602,
    mirrorText: "transform: translateX(120%)",
    keyframes: { forward: "fo-sheen", mirror: "fo-sheen-rtl" },
    reason:
      "the `from` endpoint of the sweep, re-minted rather than overridden: a percentage translate resolves " +
      "against the element's own box, so the direction has to be chosen by which keyframe is named",
  },
  {
    file: "styles/globals.css",
    line: 589,
    shape: "an X-axis transform",
    text: "transform: translateX(120%)",
    mirrorLine: 603,
    mirrorText: "transform: translateX(-120%)",
    keyframes: { forward: "fo-sheen", mirror: "fo-sheen-rtl" },
    reason: "the `to` endpoint of the same sweep, opposite to its `from` on the same terms",
  },
];

const judgeFor = new Map(PHYSICAL.map(([shape, , judge]) => [shape, judge]));
const offsetsOf = (shape, text) => {
  const judge = judgeFor.get(shape);
  if (!judge) return null;
  const verdict = judge(text);
  if (verdict.note === undefined) return null;
  return verdict.note.split(",").map((token) => Number.parseFloat(token.trim()));
};
/* A comma-separated selector list is one rule, so a mirror half written as
 * `:where([dir="rtl"]) .a:hover, :where([dir="ltr"]) .a:focus-visible` applies its offset in the *wrong*
 * direction for one of the two triggers. Every compound has to be scoped, not any of them. */
const selectorParts = (selector) => {
  const parts = [];
  let depth = 0;
  let current = "";
  for (const char of selector) {
    if (char === "(") depth += 1;
    if (char === ")") depth -= 1;
    if (char === "," && depth === 0) {
      parts.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }
  parts.push(current.trim());
  return parts.filter(Boolean);
};
const otherDirection = (selector) => selectorParts(selector).filter((part) => !part.includes('[dir="rtl"]'));

const named = new Map();
for (const exemption of EXEMPT) named.set(`${exemption.file}:${exemption.line}:${exemption.shape}`, exemption);

const isNamed = (finding) => named.has(`${finding.file}:${finding.line}:${finding.shape}`);

const mirrored = new Map();
for (const pair of MIRRORED) {
  for (const line of [pair.line, pair.mirrorLine]) mirrored.set(`${pair.file}:${line}:${pair.shape}`, pair);
}

const isMirrored = (finding) => mirrored.has(`${finding.file}:${finding.line}:${finding.shape}`);

/* 2 — the scanner answers red on the class it claims to judge. A regex typo that matches nothing would
 * otherwise report “no physical properties” over every tree, including one full of them. The witness plants
 * one declaration per shape on its own line, then a line that declares one shape twice: the count is the
 * number of declarations, which is what a record quotes, not the number of lines. */
const WITNESS = [
  ".a { left: 0; }",
  ".b { padding-left: 1rem; }",
  ".c { margin-right: auto; }",
  ".d { border-left: 2px solid red; }",
  ".e { text-align: right; }",
  ".f { float: left; }",
  ".g { border-top-left-radius: 4px; }",
  ".h { box-shadow: 0 0 0 1px red, 8px 0 0 0 blue; }",
  ".i { transform: translate(12px, 4px); }",
  ".j { background-position: right 12px; }",
  ".k { box-shadow: 6px 2px 8px rgba(0, 0, 0, 0.3); padding-left: 1rem; }",
  ".l { box-shadow: none; }",
  ".m { transform: none; }",
  ".n { transform: TranslateX(9px); }",
].join("\n");
const witness = scan(WITNESS, "planted.css");
const witnessShapes = new Set(witness.findings.map((finding) => finding.shape));
const onLine = (line) => witness.findings.filter((finding) => finding.line === line);
check(
  "the scanner is red on every shape it claims to judge",
  witnessShapes.size === PHYSICAL.length,
  `${witness.findings.length} finding(s) across ${witnessShapes.size}/${PHYSICAL.length} shape(s) in a planted stylesheet`,
);
check(
  "the scanner counts declarations, not lines: two on one line are two findings",
  onLine(11).length === 2 && witness.findings.length === 13,
  `line 11 of the witness answers ${onLine(11).length} finding(s); the planted geometry lines answer ${witness.findings.length}`,
);
check(
  "a declaration that paints nothing is not a finding: box-shadow none and transform none",
  onLine(12).length === 0 && onLine(13).length === 0 && witness.undecidable.length === 0,
  `the two planted "none" declarations answer ${onLine(12).length + onLine(13).length} finding(s) and ${witness.undecidable.length} undecidable`,
);
check(
  "the scanner reads CSS spellings, not one author's case: TranslateX is the property a browser applies",
  onLine(14).length === 1 && onLine(14)[0].text === "transform: TranslateX(9px)",
  `line 14 answers ${onLine(14).length} finding(s)${onLine(14)[0] ? ` — ${onLine(14)[0].text} (x = ${onLine(14)[0].note})` : ""}`,
);
check(
  "the scanner exempts by value, not by shape: a zero shadow offset is not a finding",
  witness.exempt.length === 0 && witness.undecidable.length === 0,
  `${witness.exempt.length} exempt and ${witness.undecidable.length} undecidable in a stylesheet planted only with non-zero geometry`,
);

/* 3 — the real population. */
const physical = [];
const valued = { exempt: [], undecidable: [] };
for (const [file, css] of bodies) {
  const result = scan(css, rel(file));
  for (const finding of result.findings) {
    if (!isNamed(finding) && !isMirrored(finding)) {
      physical.push(`${finding.file}:${finding.line} ${finding.shape} — ${finding.text}${finding.note ? ` (x = ${finding.note})` : ""}`);
    }
  }
  valued.exempt.push(...result.exempt.map((row) => ({ ...row, file: rel(file) })));
  valued.undecidable.push(...result.undecidable.map((row) => ({ ...row, file: rel(file) })));
}
check(
  "no stylesheet carries a horizontal declaration that would not follow the writing direction",
  physical.length === 0,
  physical.length === 0
    ? `${cssFiles.length} stylesheet(s) clean, ${valued.exempt.length} exempt by value, ${MIRRORED.length} answered by their [dir="rtl"] counterpart`
    : `${physical.length} finding(s): ${physical.join(" | ")}`,
);
const tally = (rows) => {
  const counts = new Map();
  for (const row of rows) counts.set(row.shape, (counts.get(row.shape) ?? 0) + 1);
  return [...counts].sort(([a], [b]) => a.localeCompare(b)).map(([shape, count]) => `${count} × ${shape}`).join(", ");
};

check(
  "every horizontal value the scanner judges is decidable from the bytes it reads",
  valued.undecidable.length === 0,
  valued.undecidable.length === 0
    ? `${valued.exempt.length} value-judged declaration(s), all decided and all exempt: ${tally(valued.exempt)}`
    : `undecidable: ${valued.undecidable.map((row) => `${row.file}:${row.line} ${row.value}`).join(" | ")}`,
);
check(
  "every named exemption is still earned by the bytes it names",
  EXEMPT.every((exemption) => {
    const body = bodies.get(join(WEB, ...exemption.file.split("/")));
    if (!body) return false;
    const line = body.replace(/\r\n/g, "\n").split(/\r?\n/)[exemption.line - 1] ?? "";
    return line.includes(exemption.text);
  }),
  `${EXEMPT.length} exemption(s): ${EXEMPT.map((exemption) => `${exemption.file}:${exemption.line} ${exemption.shape} — ${exemption.reason.split(". ")[0]}`).join(" | ")}`,
);

/* The chain of selectors that own a declaration line: comments blanked to their own newlines so they cannot
 * open or close a block, then a brace walk up to the declaration. One level of backtracking is not enough —
 * a keyframe endpoint sits inside `@keyframes … { from { … } }`, and the nearest brace on that path is the
 * stop keyword, not the at-rule. The offset lands just past the first brace *on the declaration's own line*,
 * which is what makes a single-line rule like `from { transform: … }` resolve to the inside of its block. */
function selectorStack(body, line) {
  const folded = body.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " ")).replace(/\r\n/g, "\n");
  const rows = folded.split("\n");
  let offset = 0;
  for (let i = 0; i < line - 1; i += 1) offset += rows[i].length + 1;
  const brace = rows[line - 1]?.indexOf("{") ?? -1;
  offset += Math.max(brace, 0) + (brace >= 0 ? 1 : 0);
  const stack = [];
  let current = "";
  for (let i = 0; i < offset; i += 1) {
    const char = folded[i];
    if (char === "{") {
      stack.push(current.replace(/\s+/g, " ").trim());
      current = "";
      continue;
    }
    if (char === "}") {
      stack.pop();
      current = "";
      continue;
    }
    current += char;
  }
  return stack;
}

/* 3b — a mirror pair is charged by four bytes and by the arithmetic between them. Two shapes of pair exist in
 * the tree. A rule pair is a direction-agnostic base rule answered later by a `[dir="rtl"]` half of equal
 * weight, so source order decides. A keyframe pair cannot be answered that way — a second declaration inside
 * one `@keyframes` block would be interpolated, not selected — so its counterpart lives in a second keyframe
 * whose name the RTL half of the `animation` shorthand has to actually reach. Either way the two offsets must
 * be exact opposites. */
const mirrorBytes = [];
const mirrorProblems = [];
for (const pair of MIRRORED) {
  const body = bodies.get(join(WEB, ...pair.file.split("/")));
  if (!body) {
    mirrorBytes.push(`${pair.file} is not in the population`);
    continue;
  }
  const lines = body.replace(/\r\n/g, "\n").split("\n");
  const at = (n) => (lines[n - 1] ?? "").replace(/\s+/g, " ").trim();
  if (!at(pair.line).includes(pair.text)) mirrorBytes.push(`${pair.file}:${pair.line} reads "${at(pair.line)}", not "${pair.text}"`);
  if (!at(pair.mirrorLine).includes(pair.mirrorText)) mirrorBytes.push(`${pair.file}:${pair.mirrorLine} reads "${at(pair.mirrorLine)}", not "${pair.mirrorText}"`);
  /* The arithmetic runs over the bytes the scanner read, not over this table: a counterpart flipped to the same
   * sign is refused because the tree says so, and the table's own honesty is already charged by the byte pins
   * above. A pair the scanner cannot judge at both lines is a problem, not a pass. */
  const judged = scan(body, pair.file).findings.filter((finding) => finding.shape === pair.shape);
  const declaration = (n) => judged.find((finding) => finding.line === n)?.text ?? null;
  const forwardOffsets = declaration(pair.line) === null ? null : offsetsOf(pair.shape, declaration(pair.line));
  const backOffsets = declaration(pair.mirrorLine) === null ? null : offsetsOf(pair.shape, declaration(pair.mirrorLine));
  if (!forwardOffsets || !backOffsets) {
    mirrorProblems.push(`${pair.file}:${forwardOffsets ? pair.mirrorLine : pair.line} no longer answers "${pair.shape}" judged from its own bytes`);
  } else if (forwardOffsets.length !== backOffsets.length || !forwardOffsets.every((value, i) => value + backOffsets[i] === 0)) {
    mirrorProblems.push(`${pair.file}:${pair.line} ${declaration(pair.line)} is not answered by the opposite of itself at :${pair.mirrorLine} (${declaration(pair.mirrorLine)})`);
  }
  const forwardStack = selectorStack(body, pair.line);
  const backStack = selectorStack(body, pair.mirrorLine);
  const inner = (stack) => stack.at(-1) ?? "";
  if (pair.keyframes) {
    const { forward: from, mirror: to } = pair.keyframes;
    if (forwardStack[0] !== `@keyframes ${from}`) mirrorBytes.push(`${pair.file}:${pair.line} is not inside @keyframes ${from}; its context reads "${forwardStack.join(" > ")}"`);
    if (backStack[0] !== `@keyframes ${to}`) mirrorBytes.push(`${pair.file}:${pair.line}↔${pair.mirrorLine} leaves @keyframes ${to}; its context reads "${backStack.join(" > ")}"`);
    if (forwardStack[1] !== backStack[1]) {
      mirrorProblems.push(`${pair.file}:${pair.line} is the "${forwardStack[1]}" endpoint but :${pair.mirrorLine} is the "${backStack[1]}" one — a pair answers the same instant`);
    }
    const handed = new RegExp(`\\[dir="rtl"\\][^{}]*\\{[^{}]*animation-name:\\s*${to}\\b`).exec(body.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/\s+/g, " "))?.[0] ?? "";
    if (!handed) mirrorBytes.push(`${pair.file} declares @keyframes ${to} but no [dir="rtl"] rule names it, so the mirror never runs`);
  } else {
    const unscoped = otherDirection(inner(backStack));
    if (unscoped.length > 0) {
      mirrorBytes.push(`${pair.file}:${pair.mirrorLine} is not scoped to [dir="rtl"] in every compound: ${unscoped.map((part) => `"${part}"`).join(", ")}`);
    }
    if (selectorParts(inner(forwardStack)).some((part) => part.includes("[dir="))) {
      mirrorBytes.push(`${pair.file}:${pair.line} is itself direction-scoped, so it mirrors nothing; its selector reads "${inner(forwardStack)}"`);
    }
    if (pair.mirrorLine <= pair.line) mirrorBytes.push(`${pair.file}:${pair.mirrorLine} answers ${pair.line} from before it — equal weight means the later rule wins`);
  }
}
check(
  "every mirror pair is earned by the bytes on both of its lines and by opposite offsets",
  mirrorProblems.length === 0 && mirrorBytes.length === 0,
  mirrorProblems.length + mirrorBytes.length === 0
    ? `${MIRRORED.length} pair(s) covering ${MIRRORED.length * 2} declaration(s): ${MIRRORED.map((pair) => `${pair.file}:${pair.line}↔${pair.mirrorLine} ${pair.text} / ${pair.mirrorText}`).join(" | ")}`
    : [...mirrorProblems, ...mirrorBytes].join(" | "),
);

/* 4 — call the shipped helper. The file is a module of constants and one function with no imports, so the
 * region below the type alias is self-contained; transpiling it and invoking the function means a reversed
 * condition or a dropped base language moves the verdict, which reading the source would not. */
const LOCALES = join(WEB, "i18n", "locales.ts");
let textDirection;
try {
  const src = readFileSync(LOCALES, "utf8");
  const start = src.indexOf("const RTL_BASE_LANGUAGES");
  if (start < 0) throw new Error("the RTL base-language set was not found");
  const region = src.slice(start).replace(/export\s+function/g, "function");
  const compiled = ts.transpileModule(region, { compilerOptions: { target: ts.ScriptTarget.ES2020 } }).outputText;
  textDirection = new Function(`${compiled}; return textDirection;`)();
} catch (err) {
  textDirection = null;
  check("the shipped textDirection helper compiled to a callable", false, err.message);
}
if (textDirection) {
  const shippedLtr = ["en", "zh", "zh-TW"];
  const shippedRtl = ["ar", "he"].filter((locale) =>
    existsSync(join(WEB, "messages", `${locale}.json`)));
  const rtl = ["ar", "ar-EG", "he", "he-IL", "fa", "ur", "ps", "sd", "ug", "yi", "dv"];
  const ltr = ["en", "en-GB", "zh", "zh-Hant", "zh-TW", "fr", "de-CH", "ja"];
  const wrong = [
    ...shippedLtr.map((locale) => [locale, "ltr"]),
    ...shippedRtl.map((locale) => [locale, "rtl"]),
    ...rtl.map((locale) => [locale, "rtl"]),
    ...ltr.map((locale) => [locale, "ltr"]),
  ].filter(([locale, expected]) => textDirection(locale) !== expected);
  check(
    "textDirection moves with the script: shipped locales read ltr, RTL base languages read rtl",
    wrong.length === 0 && typeof textDirection("ar") === "string",
    wrong.length === 0
      ? `${shippedLtr.length + shippedRtl.length} shipped + ${rtl.length} rtl + ${ltr.length} ltr classification(s) agree`
      : wrong.map(([locale, expected]) => `${locale} answered ${textDirection(locale)}, expected ${expected}`).join("; "),
  );
}

/* 5 — the root layout hands the verdict to the document. The tag is read as a tag, not as the whole file, so
 * a `dir` set on some inner element cannot satisfy it. */
const layout = readFileSync(join(WEB, "app", "layout.tsx"), "utf8");
const htmlTag = /<html\b[^>]*>/.exec(layout)?.[0] ?? "";
check(
  "the root layout sets dir from the locale's own direction",
  htmlTag.length > 0 && /\blang=\{locale\}/.test(htmlTag) && /\bdir=\{textDirection\(locale\)\}/.test(htmlTag),
  htmlTag || "no <html> tag found",
);
check(
  "the layout imports the helper it calls",
  /import\s*\{[^}]*\btextDirection\b[^}]*\}\s*from\s*["']@\/i18n\/locales["']/.test(layout),
  /from\s*["']@\/i18n\/locales["']/.exec(layout)?.[0] ?? "no import from @/i18n/locales",
);

/* 6 — a font stack that names only Latin faces leaves an Arabic or Hebrew reader to the browser's last
 * resort. Both stacks end in a generic family, so the fallback is a family rather than a guess. */
const globalsCss = bodies.get(join(WEB, "styles", "globals.css")) ?? "";
const font = /--font\s*:\s*([^;]+);/.exec(globalsCss)?.[1]?.trim() ?? "";
const mono = /--mono\s*:\s*([^;]+);/.exec(globalsCss)?.[1]?.trim() ?? "";
check(
  "both font stacks end in a generic family a script the stack does not name can still use",
  /\bsans-serif$/.test(font) && /\bmonospace$/.test(mono),
  `--font ends "${font.split(",").pop()?.trim()}", --mono ends "${mono.split(",").pop()?.trim()}"`,
);

/* 7 — Arabic letters join; tracking breaks the joining, and `text-transform` has no counterpart in either
 * script. The census counts the tracking the stylesheets actually carry. It matters that the number is in the
 * gate rather than in a paragraph: every one of those declarations sits on a class, so an html-level reset
 * loses to it twice over — as specificity and as inheritance — and the reset only answers them by carrying a
 * weight, which is the same reason the reduced-motion block in this file weights its four declarations. A
 * tracked `!important` that is not the reset would outweight the script again, so the census refuses it too. */
const tracked = [];
const competing = [];
const trackedFiles = new Set();
for (const [file, css] of bodies) {
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [lineNumber, line] of stripped.split(/\r?\n/).entries()) {
    for (const match of line.matchAll(/letter-spacing\s*:\s*([^;}]+)/g)) {
      const value = match[1].trim();
      if (/^(?:normal|0)(?:\s*!important)?$/.test(value)) continue;
      const row = `${rel(file)}:${lineNumber + 1} letter-spacing: ${value}`;
      tracked.push(row);
      trackedFiles.add(rel(file));
      if (/!important/.test(value)) competing.push(row);
    }
  }
}
const arabicReset = /:lang\(ar\)/.test(globalsCss) && /:lang\(he\)/.test(globalsCss);
const resetBlock = /(?::lang\(ar\)[^{]*,?\s*(?::lang\(he\))?[^{]*\{[^}]*\})/.exec(globalsCss)?.[0] ?? "";
const weighted = /letter-spacing:\s*normal\s*!important/.test(resetBlock) && /text-transform:\s*none\s*!important/.test(resetBlock);
check(
  "Arabic and Hebrew reset letter-spacing and case transform — cursive joining is not breakable tracking",
  arabicReset && weighted && competing.length === 0,
  competing.length > 0
    ? `${competing.length} tracking declaration(s) outweight the script reset: ${competing.join(" | ")}`
    : `${tracked.length} tracking declaration(s) in ${trackedFiles.size} stylesheet(s), answered by one weighted reset: ${resetBlock.trim().replace(/\s+/g, " ") || "no readable reset rule"}`,
);

const failed = checks.filter((row) => !row.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
process.exit(failed.length === 0 ? 0 : 1);
