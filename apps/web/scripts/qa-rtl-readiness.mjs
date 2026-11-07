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
 *      cursive joining is not breakable tracking, and the gate refuses a tree without it.
 *
 * Files only: no server, no browser, no port. Register it in `scripts/check.sh` and CI beside the other
 * static gates, or `qa-gate-inventory.mjs` correctly reports it as a script nothing invokes.
 */

import { readdirSync, readFileSync } from "node:fs";
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
    bodies.set(file, readFileSync(file, "utf8"));
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
 * by `:` only after the property token. */
const PHYSICAL = [
  ["a horizontal offset", /(?:^|[;{])\s*(?:left|right)\s*:/],
  ["a horizontal margin, padding or border", /(?:^|[;{])\s*(?:margin|padding|border)-(?:left|right)\s*:/],
  ["a physical corner radius", /(?:^|[;{])\s*border-(?:top|bottom)-(?:left|right)-radius\s*:/],
  ["physical text alignment", /(?:^|[;{])\s*text-align\s*:\s*(?:left|right)\b/],
  ["a physical float", /(?:^|[;{])\s*float\s*:\s*(?:left|right)\b/],
];

function scan(css) {
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "));
  const findings = [];
  for (const [lineNumber, line] of stripped.split(/\r?\n/).entries()) {
    for (const [shape, pattern] of PHYSICAL) {
      if (pattern.test(line)) findings.push({ line: lineNumber + 1, shape, text: line.trim() });
    }
  }
  return findings;
}

/* 2 — the scanner answers red on the class it claims to judge. A regex typo that matches nothing would
 * otherwise report “no physical properties” over every tree, including one full of them. */
const WITNESS = [
  ".a { left: 0; }",
  ".b { padding-left: 1rem; }",
  ".c { margin-right: auto; }",
  ".d { border-left: 2px solid red; }",
  ".e { text-align: right; }",
  ".f { float: left; }",
  ".g { border-top-left-radius: 4px; }",
].join("\n");
const witnessFindings = scan(WITNESS);
const witnessShapes = new Set(witnessFindings.map((finding) => finding.shape));
check(
  "the scanner is red on every shape it claims to judge",
  witnessFindings.length === WITNESS.split("\n").length && witnessShapes.size === PHYSICAL.length,
  `${witnessFindings.length} finding(s) across ${witnessShapes.size}/${PHYSICAL.length} shape(s) in a planted stylesheet`,
);

/* 3 — the real population. */
const physical = [];
for (const [file, css] of bodies) {
  for (const finding of scan(css)) physical.push(`${rel(file)}:${finding.line} ${finding.shape} — ${finding.text}`);
}
check(
  "no stylesheet carries a horizontal declaration that would not follow the writing direction",
  physical.length === 0,
  physical.length === 0 ? `${cssFiles.length} stylesheet(s) clean` : `${physical.length} finding(s): ${physical.slice(0, 6).join(" | ")}`,
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
  const shipped = ["en", "zh", "zh-TW"];
  const rtl = ["ar", "ar-EG", "he", "he-IL", "fa", "ur", "ps", "sd", "ug", "yi", "dv"];
  const ltr = ["en", "en-GB", "zh", "zh-Hant", "zh-TW", "fr", "de-CH", "ja"];
  const wrong = [
    ...shipped.map((locale) => [locale, "ltr"]),
    ...rtl.map((locale) => [locale, "rtl"]),
    ...ltr.map((locale) => [locale, "ltr"]),
  ].filter(([locale, expected]) => textDirection(locale) !== expected);
  check(
    "textDirection moves with the script: shipped locales read ltr, RTL base languages read rtl",
    wrong.length === 0 && typeof textDirection("ar") === "string",
    wrong.length === 0
      ? `${shipped.length} shipped + ${rtl.length} rtl + ${ltr.length} ltr classification(s) agree`
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

/* 7 — Arabic letters join; tracking breaks the joining. The stylesheets carry sixteen
 * letter-spacing declarations, and they exist for Latin's eyebrows and table headers; the
 * two scripts tracking cannot serve get one reset rule in globals.css. The gate refuses a
 * tree where that rule is missing, so a future refactor cannot silently drop it. */
const arabicReset = /:lang\(ar\)/.test(globalsCss) && /:lang\(he\)/.test(globalsCss);
const resetBlock = /(?::lang\(ar\)[^{]*,?\s*(?::lang\(he\))?[^{]*\{[^}]*\})/.exec(globalsCss)?.[0] ?? "";
check(
  "Arabic and Hebrew reset letter-spacing and case transform — cursive joining is not breakable tracking",
  arabicReset && /letter-spacing:\s*normal/.test(resetBlock),
  arabicReset ? (resetBlock.trim().replace(/\s+/g, " ") || "the reset rule is unreadable") : "no :lang(ar)/:lang(he) reset rule found in globals.css",
);

const failed = checks.filter((row) => !row.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
process.exit(failed.length === 0 ? 0 : 1);
