#!/usr/bin/env node
/*
 * Behavioural witness for `qa-a11y.mjs`: every class of defect the gate claims to catch, planted in a scratch copy of
 * the shell and held red, and the untouched copy held green.
 *
 * Why a witness and not just the gate. A static gate is a predicate over text, and the expensive failure is a
 * predicate that reads a sentence in a comment, a selector that no longer means what its name says, or a regex that
 * quietly stops matching after a refactor — all of which report 33/33 on a tree that has lost the very thing the
 * gate exists for. Each arm below changes exactly one thing in a fresh copy of `app/layout.tsx`,
 * `styles/globals.css` and `components/Nav.tsx`, plus one extra component holding a scoped `<th>` and a described
 * `<img>`, and every arm asserts that the named check — by its label, not by a count — is the one that went red.
 *
 * Predictions, written before the first run: 16 checks (a green control plus fifteen red arms), all matching.
 *   control        rc 0, total=33, failed=0.
 *   no-skip        check 3 red: the layout has no skip link at all.
 *   anchor-first   check 4 red: an ordinary anchor is written before the skip link.
 *   no-main-id     check 7 red: `<main>` lost its id and tab stop.
 *   no-tab-stop    check 7 red: `<main id="main">` with no tabIndex, so the target cannot take focus.
 *   dim-text-3     check 16 red on `--text-3`: the token measures 4.20:1 on `--bg-panel-2`.
 *   no-focus-ring  check 10 red: no `:focus-visible` rule paints an outline.
 *   focus-first    check 12 red: the focus rule is declared before the `outline: none` rule it must override.
 *   skip-visible   check 13 red: the skip link is on-screen before focus, so it distracts a pointer reader.
 *   no-motion      check 14 red: nothing honours `prefers-reduced-motion`.
 *   no-nav-name    check 20 red: `<nav>` has no accessible name.
 *   no-current     check 21 red: the current page is marked by a class alone.
 *   img-bare       check 24 red: an `<img>` with no alt.
 *   th-bare        check 23 red: a `<th>` with no scope.
 *   colour-line    check 18 red: a text colour points at `--line`, which is a border token at 1.2:1.
 *   dim-control    check 17 red: `--line-control` is 1.7:1 against the field it draws.
 *
 * Files only: no server, no browser, no port. Each arm is a fresh `mkdtemp` tree, removed on the way out.
 */

import { mkdtempSync, mkdirSync, copyFileSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(HERE, "..");
const GATE = join(HERE, "qa-a11y.mjs");
const SOURCES = {
  layout: join(WEB, "app", "layout.tsx"),
  styles: join(WEB, "styles", "globals.css"),
  nav: join(WEB, "components", "Nav.tsx"),
};

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const EXTRA = `<table>
  <thead>
    <tr>
      <th scope="col">{t("one")}</th>
    </tr>
  </thead>
</table>
<img alt="a described image" src="/og.png" />
`;

const fixture = () => {
  const root = mkdtempSync(join(tmpdir(), "a11y-witness-"));
  mkdirSync(join(root, "app"), { recursive: true });
  mkdirSync(join(root, "components"), { recursive: true });
  mkdirSync(join(root, "styles"), { recursive: true });
  copyFileSync(SOURCES.layout, join(root, "app", "layout.tsx"));
  copyFileSync(SOURCES.nav, join(root, "components", "Nav.tsx"));
  copyFileSync(SOURCES.styles, join(root, "styles", "globals.css"));
  writeFileSync(join(root, "components", "Extra.tsx"), EXTRA);
  return root;
};

// A mutation must find its anchor. A rename in the shell that leaves an arm's `replace` matching nothing would
// otherwise turn that arm green for the wrong reason: the fixture would still hold a correct skip link and the gate
// would be right to pass it. Each edit below asserts the bytes changed.
const replace = (root, file, from, to) => {
  const path = join(root, file);
  const before = readFileSync(path, "utf8");
  const after = before.replace(from, to);
  if (after === before) throw new Error(`arm anchor not found in ${file}: ${from.slice(0, 60)}`);
  writeFileSync(path, after);
};

const append = (root, file, text) => writeFileSync(join(root, file), readFileSync(join(root, file), "utf8") + text);

const run = (root) => {
  const result = spawnSync(process.execPath, [GATE], { cwd: WEB, env: { ...process.env, QA_A11Y_WEB: root }, encoding: "utf8" });
  const out = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  const tally = /CHECKS passed=(\d+) total=(\d+) failed=(\d+)/u.exec(out);
  return {
    status: result.status,
    out,
    tally: tally ? { passed: Number(tally[1]), total: Number(tally[2]), failed: Number(tally[3]) } : null,
    red: out.split(/\r?\n/).filter((line) => line.startsWith("FAIL ")),
  };
};

// ── control ───────────────────────────────────────────────────────────────────────────────────────────────────────
let root = fixture();
let result = run(root);
check(
  "control an untouched copy of the shell is green (rc 0, 33 checks)",
  result.status === 0 && result.tally?.total === 33 && result.tally.failed === 0,
  `rc=${result.status} tally=${JSON.stringify(result.tally)}`,
);
rmSync(root, { recursive: true, force: true });

// ── arms ──────────────────────────────────────────────────────────────────────────────────────────────────────────
const arms = [
  ["no-skip", "3 the first landmark is a skip link", (dir) => replace(dir, "app/layout.tsx", `<a className="skip-link" href="#main">\n            {tNav("skipToContent")}\n          </a>\n          `, "")],
  ["anchor-first", "4 no focusable element is written", (dir) => replace(dir, "app/layout.tsx", `<a className="skip-link" href="#main">`, `<a href="/login">Sign in</a>\n          <a className="skip-link" href="#main">`)],
  ["no-main-id", "7 <main> carries the id", (dir) => replace(dir, "app/layout.tsx", `<main id="main" tabIndex={-1}>`, `<main>`)],
  ["no-tab-stop", "7 <main> carries the id", (dir) => replace(dir, "app/layout.tsx", `<main id="main" tabIndex={-1}>`, `<main id="main">`)],
  ["dim-text-3", "16 --text-3 reaches 4.5:1", (dir) => replace(dir, "styles/globals.css", "--text-3: #788aa1;", "--text-3: #6f8098;")],
  ["no-focus-ring", "10 a :focus-visible rule paints", (dir) => replace(dir, "styles/globals.css", `:where(a, button, input, select, textarea, summary, [tabindex]):focus-visible {\n  outline: 2px solid var(--accent);\n  outline-offset: 2px;\n}`, "")],
  ["focus-first", "12 the focus ring is declared after", (dir) => {
    const path = join(dir, "styles/globals.css");
    const rule = `:where(a, button, input, select, textarea, summary, [tabindex]):focus-visible {\n  outline: 2px solid var(--accent);\n  outline-offset: 2px;\n}`;
    const css = readFileSync(path, "utf8");
    const without = css.replace(rule, "");
    if (without === css) throw new Error("arm anchor not found: the focus rule");
    writeFileSync(path, without.replace("* { box-sizing: border-box; }", `* { box-sizing: border-box; }\n${rule}`));
  }],
  ["skip-visible", "13 the skip link is off-screen", (dir) => replace(dir, "styles/globals.css", "top: -3.5rem;", "top: 0.75rem;")],
  ["no-motion", "14 a prefers-reduced-motion block", (dir) => replace(dir, "styles/globals.css", `/* A reader who has asked their system for less motion gets no transitions at all: the theme animates on hover and on
   the skip link's slide, and both are decoration rather than information. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}`, "")],
  ["no-nav-name", "20 <nav> carries an accessible name", (dir) => replace(dir, "components/Nav.tsx", `<nav className="nav" aria-label={t("primaryNav")}>`, `<nav className="nav">`)],
  ["no-current", "21 the current page is announced", (dir) => replace(dir, "components/Nav.tsx", `aria-current={active ? "page" : undefined}\n                `, "")],
  ["img-bare", "24 every <img> carries an alt", (dir) => append(dir, "components/Extra.tsx", `<img src="/bare.png" />\n`)],
  ["th-bare", "23 every <th> declares its scope", (dir) => append(dir, "components/Extra.tsx", `<table><tr><th>{t("two")}</th></tr></table>\n`)],
  ["colour-line", "18 every `color: var(--token)`", (dir) => replace(dir, "styles/globals.css", "color: var(--text-2);", "color: var(--line);")],
  ["dim-control", "17 --line-control reaches 3:1", (dir) => replace(dir, "styles/globals.css", "--line-control: #556a86;", "--line-control: #2b3c56;")],
];

for (const [name, needle, mutate] of arms) {
  root = fixture();
  try {
    mutate(root);
    result = run(root);
    check(`${name} is red on ${needle} (rc 1)`, result.status === 1 && result.red.some((line) => line.includes(needle)), result.red.length ? result.red[0] : "no red line");
  } catch (error) {
    check(`${name} is red on ${needle}`, false, String(error.message ?? error));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  process.exitCode = 1;
}
