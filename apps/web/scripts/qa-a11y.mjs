#!/usr/bin/env node
/*
 * The shell's accessibility floor, read from the files that decide it and re-measured on every run.
 *
 * Why this file exists. §17 of the roadmap says "lift the remaining contrast/focus/aria findings to green and keep
 * them green via a gate". The findings were real and none of them was visible to any gate the project held:
 *
 *   - the layout had no skip link, so a keyboard reader tabbed through 11–18 nav links on every page before reaching
 *     that page's own heading, and `<main>` had no id or tab stop, so there was nothing to skip *to*;
 *   - the stylesheet had no `:focus-visible` rule at all — every link and every ghost button took focus invisibly,
 *     which is the one failure a sighted keyboard reader meets on the first Tab press;
 *   - `--text-3`, the token behind every eyebrow, stat label, field label, table header and key/value key, measured
 *     4.20:1 on `--bg-panel-2`: small uppercase text at 0.7rem fails WCAG AA's 4.5:1 on the very surfaces it is
 *     printed on;
 *   - a form control was drawn with `--line`, which is 1.2–1.3:1 against its own field: WCAG 1.4.11 asks 3:1 of the
 *     boundary that tells a reader where the control is, and a reader on a dim screen could not see the field;
 *   - `<nav>` had no accessible name and the current page was marked by a class alone, so a screen reader announcing
 *     the landmark said "navigation" and never "you are here";
 *   - nothing honoured `prefers-reduced-motion`, though the theme animates on hover and the skip link slides.
 *
 * The checks below are the measurements, not a checklist of edits: contrast is recomputed from the token table in
 * `styles/globals.css` (so a later dimming of any token is red, not just of the one that was wrong today), every
 * `outline: none` must be answered by a focus rule that repaints the control, the focus rule must be declared after
 * the rule it overrides (equal specificity: source order decides), every `<th>` in the tree must carry a `scope`,
 * and every `<img>` must carry an `alt`.
 *
 * Files only: no server, no browser, no port. `QA_A11Y_WEB` points the gate at another tree, which is how the
 * witness in `qa-a11y-witness.mjs` proves each arm red without touching this one.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_A11Y_WEB ? process.env.QA_A11Y_WEB : fileURLToPath(new URL("..", import.meta.url)));
const LAYOUT = join(WEB, "app", "layout.tsx");
const STYLES = join(WEB, "styles", "globals.css");
const NAV = join(WEB, "components", "Nav.tsx");

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const read = (path) => readFileSync(path, "utf8");
const exists = (path) => {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
};

const layout = exists(LAYOUT) ? read(LAYOUT) : "";
// Comments talk about these tags (this file's own note in the layout names `<main id="main">`), and a scan that reads
// prose will certify markup nobody wrote: every tag check below reads the code with JSX comments removed.
const layoutCode = layout.replace(/\{\/\*[\s\S]*?\*\/\}/gu, "");
const styles = exists(STYLES) ? read(STYLES) : "";
const nav = exists(NAV) ? read(NAV) : "";
const navCode = nav.replace(/\{\/\*[\s\S]*?\*\/\}/gu, "");

// ── landmarks ─────────────────────────────────────────────────────────────────────────────────────────────────────
check("1 app/layout.tsx is readable", layout.length > 0, layout.length ? `${layout.split(/\r?\n/).length} lines` : "missing");

const htmlTag = /<html\b([^>]*)>/u.exec(layoutCode)?.[1] ?? "";
check(
  "2 the document declares the reader's language on <html>",
  /lang=\{locale\}/u.test(htmlTag) || /lang="/u.test(htmlTag),
  htmlTag || "no <html> tag",
);

const skipTag = /<a\b([^>]*\bclassName="skip-link"[^>]*)>/u.exec(layoutCode)?.[1] ?? "";
const skipHref = /\bhref="([^"]*)"/u.exec(skipTag)?.[1] ?? "";
check(
  "3 the first landmark is a skip link pointing at #main",
  skipTag.length > 0 && skipHref === "#main",
  skipTag ? `href=${skipHref || "missing"}` : "no <a className=\"skip-link\"> in the layout",
);

// The skip link is only a skip link if it is the first thing a Tab press reaches: any anchor or control written
// before it in the layout would sit in front of it in the document order.
const firstAnchor = /<a\b[^>]*>/u.exec(layoutCode);
const firstControl = /<(a|button|input|select|textarea)\b[^>]*>/u.exec(layoutCode);
check(
  "4 no focusable element is written before the skip link",
  firstAnchor !== null && /className="skip-link"/u.test(firstAnchor[0]) && firstControl !== null && firstControl.index === firstAnchor.index,
  firstControl ? `the first control is ${firstControl[0].slice(0, 40)}` : "no controls in the layout",
);
check(
  "5 the skip link is rendered before the nav",
  skipTag.length > 0 && layoutCode.indexOf('className="skip-link"') < layoutCode.indexOf("<Nav"),
  skipTag.length ? `${layoutCode.indexOf('className="skip-link"')} < ${layoutCode.indexOf("<Nav")}` : "no skip link",
);
check(
  "6 the skip link's text is a catalogue read, not an English literal",
  /\{tNav\(\s*["']skipToContent["']\s*\)\}/u.test(layoutCode),
  layoutCode.includes("skipToContent") ? "reads tNav(\"skipToContent\")" : "the anchor holds no catalogue read",
);

const mainElement = /<main\b[^>]*>/u.exec(layoutCode)?.[0] ?? "";
const mainTag = /<main\b([^>]*)>/u.exec(layoutCode)?.[1] ?? "";
const mainId = /\bid="([^"]*)"/u.exec(mainTag)?.[1] ?? "";
check(
  "7 <main> carries the id the skip link names, and can take focus",
  mainId === "main" && /\btabIndex=\{-1\}/u.test(mainTag),
  mainElement || "no <main> tag in the layout",
);
check(
  "8 the skip link's target is the <main> that wraps the page",
  skipHref !== "" && skipHref === `#${mainId}` && /\{children\}/u.test(layoutCode),
  `href=${skipHref || "missing"} main id=${mainId || "missing"}`,
);

// ── the stylesheet ────────────────────────────────────────────────────────────────────────────────────────────────
check("9 styles/globals.css is readable", styles.length > 0, styles.length ? `${styles.split(/\r?\n/).length} lines` : "missing");

const css = styles.replace(/\/\*[\s\S]*?\*\//gu, "");
const blocks = [];
for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/gu)) {
  blocks.push({ selector: match[1].trim().replace(/\s+/gu, " "), body: match[2], index: match.index ?? 0 });
}

const focusRule = blocks.find((block) => block.selector.includes(":focus-visible") && /outline:\s*[^;]*/u.test(block.body) && !/outline:\s*none/u.test(block.body));
check(
  "10 a :focus-visible rule paints a visible outline",
  focusRule !== undefined,
  focusRule ? `${focusRule.selector} { ${focusRule.body.trim().split(/\r?\n/)[0]} }` : "no :focus-visible rule sets an outline",
);

// Every rule that removes the browser's ring owes the reader another one. The answer may be a box-shadow, a border
// change or an outline, but it must be declared on the same selector's focus state.
const muted = blocks.filter((block) => /outline:\s*none/u.test(block.body));
let answered = 0;
for (const block of muted) {
  for (const base of block.selector.split(",").map((part) => part.trim()).filter(Boolean)) {
    const answer = blocks.find(
      (candidate) =>
        (candidate.selector.includes(`${base}:focus`) || candidate.selector.includes(`${base}:focus-visible`)) &&
        /(box-shadow|border-color|border:|outline):/u.test(candidate.body),
    );
    answered += answer ? 1 : 0;
    check(
      `11 ${base} removes the outline and declares its own focus state`,
      answer !== undefined,
      answer ? answer.selector : "outline: none with no :focus / :focus-visible rule",
    );
  }
}
check(
  "12 the focus ring is declared after the rules it overrides (source order decides at equal specificity)",
  focusRule !== undefined && muted.every((block) => focusRule.index > block.index),
  focusRule ? `focus at ${focusRule.index}, muted at [${muted.map((block) => block.index).join(",")}]` : "no focus rule",
);

const skipBase = blocks.find((block) => block.selector === ".skip-link");
const skipFocus = blocks.find((block) => block.selector === ".skip-link:focus");
const offScreen = /top:\s*-[\d.]+(?:rem|px)/u.test(skipBase?.body ?? "");
const revealed = /top:\s*[\d.]+(?:rem|px)/u.test(skipFocus?.body ?? "");
check(
  "13 the skip link is off-screen until focused, then visible",
  skipBase !== undefined && skipFocus !== undefined && offScreen && revealed,
  `${skipBase ? "base off-screen" : "no .skip-link rule"}, ${skipFocus ? "focus reveals" : "no .skip-link:focus rule"}`,
);

const reduced = /@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)\s*\{([\s\S]*?)\n\}/u.exec(css)?.[1] ?? "";
check(
  "14 a prefers-reduced-motion block zeroes animation and transition durations",
  /animation-duration:\s*0?\.0*1ms/u.test(reduced) && /transition-duration:\s*0?\.0*1ms/u.test(reduced),
  reduced ? reduced.trim().split(/\r?\n/)[0] : "no @media (prefers-reduced-motion: reduce) block",
);

// ── contrast, recomputed from the token table ────────────────────────────────────────────────────────────────────
const rootBlock = /:root\s*\{([\s\S]*?)\}/u.exec(css)?.[1] ?? "";
const tokens = new Map();
for (const match of rootBlock.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\b/gu)) tokens.set(match[1], match[2].toLowerCase());
check("15 the token table was readable (>= 12 hex tokens)", tokens.size >= 12, `${tokens.size} tokens`);

const SURFACES = ["bg", "bg-raised", "bg-panel", "bg-panel-2", "bg-input"];
const TEXT_TOKENS = ["text", "text-2", "text-3", "accent", "accent-dim", "warn", "danger", "info"];

const linear = (channel) => {
  const value = channel / 255;
  return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
};
const luminance = (hex) => {
  const raw = hex.replace("#", "");
  return 0.2126 * linear(parseInt(raw.slice(0, 2), 16)) + 0.7152 * linear(parseInt(raw.slice(2, 4), 16)) + 0.0722 * linear(parseInt(raw.slice(4, 6), 16));
};
const contrast = (foreground, background) => {
  const a = luminance(foreground);
  const b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
};

for (const name of TEXT_TOKENS) {
  const foreground = tokens.get(name);
  const readings = SURFACES.map((surface) => ({ surface, ratio: foreground && tokens.get(surface) ? contrast(foreground, tokens.get(surface)) : 0 }));
  const worst = readings.reduce((low, row) => (row.ratio < low.ratio ? row : low), readings[0]);
  check(
    `16 --${name} reaches 4.5:1 on every surface it is painted on`,
    foreground !== undefined && readings.every((row) => row.ratio >= 4.5),
    foreground ? `worst ${worst.ratio.toFixed(2)}:1 on --${worst.surface}` : "token missing",
  );
}

const control = tokens.get("line-control");
const controlReadings = ["bg-input", "bg-panel-2"].map((surface) => ({ surface, ratio: control && tokens.get(surface) ? contrast(control, tokens.get(surface)) : 0 }));
check(
  "17 --line-control reaches 3:1 against the field and the panel it is drawn on",
  control !== undefined && controlReadings.every((row) => row.ratio >= 3),
  control ? controlReadings.map((row) => `${row.ratio.toFixed(2)}:1 on --${row.surface}`).join(", ") : "no --line-control token",
);

// A colour may be written as `var(--token)` many times over; one of them pointing at a dim token is the whole bug
// that made the eyebrows unreadable, so every declaration is resolved instead of only the ones a class name suggests.
const passing = new Set(TEXT_TOKENS);
const offenders = [];
for (const block of blocks) {
  for (const match of block.body.matchAll(/color:\s*var\(--([\w-]+)\)/gu)) {
    if (!passing.has(match[1])) offenders.push(`${block.selector} -> --${match[1]}`);
  }
}
check(
  "18 every `color: var(--token)` resolves to a token that passes 4.5:1",
  offenders.length === 0,
  offenders.length ? offenders.join("; ") : "no colour declaration points outside the passing set",
);

// ── the nav ─────────────────────────────────────────────────────────────────────────────────────────────────────
check("19 components/Nav.tsx is readable", nav.length > 0, nav.length ? `${nav.split(/\r?\n/).length} lines` : "missing");
const navTag = /<nav\b([^>]*)>/u.exec(navCode)?.[1] ?? "";
check(
  "20 <nav> carries an accessible name from the catalogue",
  /\baria-label=\{t\(\s*["']primaryNav["']\s*\)\}/u.test(navTag),
  navTag || "no <nav> tag",
);
check(
  "21 the current page is announced with aria-current=\"page\", beside the class",
  /\baria-current=\{active\s*\?\s*"page"\s*:\s*undefined\}/u.test(navCode),
  navCode.includes("aria-current") ? "conditional on the same `active` the class uses" : "no aria-current in Nav.tsx",
);

// ── the tree: table headers, images, population ──────────────────────────────────────────────────────────────────
const walk = (dir) => {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...walk(path));
    else if (extname(entry.name) === ".tsx") found.push(path);
  }
  return found;
};
const tree = ["app", "components"].flatMap((dir) => (existsSync(join(WEB, dir)) ? walk(join(WEB, dir)) : []));
check("22 the page tree was scanned", tree.length > 0, `${tree.length} .tsx files`);

const unscoped = [];
const unalt = [];
for (const path of tree) {
  const source = read(path);
  for (const match of source.matchAll(/<th\b([^>]*)>/gu)) {
    if (!/\bscope=/u.test(match[1])) unscoped.push(`${path.replace(`${WEB}/`, "").replace(/\\/gu, "/")}: ${`<th${match[1]}>`.trim()}`);
  }
  for (const match of source.matchAll(/<img\b([^>]*)>/gu)) {
    if (!/\balt=/u.test(match[1]) && !/\baria-hidden=/u.test(match[1])) unalt.push(`${path.replace(`${WEB}/`, "").replace(/\\/gu, "/")}: ${`<img${match[1]}>`.trim()}`);
  }
}
check("23 every <th> declares its scope", unscoped.length === 0, unscoped.length ? unscoped.slice(0, 6).join("; ") : "all headers scoped");
check("24 every <img> carries an alt (or is hidden from the tree)", unalt.length === 0, unalt.length ? unalt.slice(0, 6).join("; ") : "all images described");

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
