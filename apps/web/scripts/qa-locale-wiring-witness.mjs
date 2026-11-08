#!/usr/bin/env node
/*
 * The locale-wiring gate's verdicts, on scratch planes.
 *
 * `qa-locale-wiring.mjs` answers one question — can every consumer the reader meets still see every
 * catalogue the directory ships? — and the Arabic milestone proved that question has an answer nobody
 * was checking (Arabic shipped with the switcher showing the raw tag, all other gates green). A gate that
 * only ever reads the real tree is a gate whose red path has never run; this file plants one defect per
 * arm on a scratch copy and asks which checks fire.
 *
 * Plane: a temp directory whose `web/` holds apps/web minus node_modules/.next, and whose `api/tests/`
 * holds the locale-claims test (the only API file the gate reads). `QA_WIRING_WEB` points the gate at it.
 * Files only; no server, no browser, no port.
 *
 * Arms:
 *   0  the real tree, untouched — 8/8
 *   A  he dropped from LocaleSwitcher NAMES — check 6 reds alone (the Arabic milestone's defect)
 *   B  he dropped from i18n/request.ts messagesMap — check 5 reds alone
 *   C  he dropped from app/layout.tsx messagesMap — check 6 reds alone
 *   D  he dropped from i18n/locales.ts locales list — check 1 reds (the catalogue is on disk and unwired)
 *   E  he dropped from middleware's branch — check 2 reds alone
 *   F  he dropped from README_FLOORS — check 8 reds alone
 *   G  a fr.json on disk, wired nowhere — the directory discovery charges it by filename
 *   H  the real tree after the arms ran — still 8/8 (the arms hit scratch copies, not this tree)
 */

import { cpSync, mkdtempSync, rmSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const GATE = resolve(HERE, "qa-locale-wiring.mjs");
const REPO = resolve(HERE, "..", "..", "..");
const REAL_WEB = join(REPO, "apps", "web");
const CLAIMS = join(REPO, "apps", "api", "tests", "test_locale_claims.py");

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const root = mkdtempSync(join(tmpdir(), "qa-locale-wiring-witness-"));
const plane = (name, mutate) => {
  const dir = join(root, name);
  cpSync(REAL_WEB, join(dir, "web"), {
    recursive: true,
    filter: (source) => !/node_modules|\.next/.test(source),
  });
  cpSync(CLAIMS, join(dir, "api", "tests", "test_locale_claims.py"), { recursive: false });
  if (mutate) mutate(dir);
  return dir;
};
const run = (dir) => {
  const result = spawnSync(process.execPath, [GATE], {
    env: { ...process.env, QA_WIRING_WEB: join(dir, "web") },
    encoding: "utf8",
  });
  const out = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  const tally = /CHECKS passed=(\d+) total=(\d+) failed=(\d+)/.exec(out);
  return { status: result.status, out, failed: tally ? Number(tally[3]) : null, total: tally ? Number(tally[2]) : null };
};
const red = (out, name) => out.includes(`FAIL  ${name}`);
const green = (out, name) => out.includes(`PASS  ${name}`);
const tally = (r) => `rc=${r.status} failed=${r.failed} total=${r.total}`;
const setText = (dir, rel, transform) => {
  const path = join(dir, "web", rel);
  writeFileSync(path, transform(readFileSync(path, "utf8")));
};
const replaceOnce = (text, needle, replacement) => {
  const next = text.replace(needle, replacement);
  if (next === text) throw new Error(`the needle ${JSON.stringify(needle.slice(0, 60))} matched nothing, so this arm would judge nothing`);
  return next;
};

/* 0 — the shipped tree, judged by the shipped gate, through the same override. */
const zero = run(plane("zero-baseline", null));
check(
  "0 the shipped tree reads 8/8 through the same override the arms use",
  zero.status === 0 && zero.failed === 0 && zero.total === 8,
  tally(zero),
);

/* A — the Arabic milestone's defect, planted: he quits the switcher's NAMES. */
const a = run(plane("a-switcher-drops-he", (dir) => {
  setText(dir, "components/LocaleSwitcher.tsx", (s) => replaceOnce(s, '  he: "עברית",\n', ""));
}));
check(
  "A a locale missing from the switcher's NAMES reds check 6 alone",
  a.status === 1 && a.failed === 1 && red(a.out, "LocaleSwitcher's NAMES renders every shipped locale in its own language"),
  `${tally(a)}; switch=${red(a.out, "LocaleSwitcher's NAMES renders every shipped locale in its own language")}`,
);

/* B — he quits the request bundle. */
const b = run(plane("b-request-drops-he", (dir) => {
  setText(dir, "i18n/request.ts", (s) => replaceOnce(s, "  he: heMessages,\n", ""));
}));
check(
  "B a locale missing from the request bundle reds check 4 alone",
  b.status === 1 && b.failed === 1 && red(b.out, "i18n/request.ts maps every shipped catalogue in its messagesMap"),
  `${tally(b)}; request=${red(b.out, "i18n/request.ts maps every shipped catalogue in its messagesMap")}`,
);

/* C — he quits the layout bundle. */
const c = run(plane("c-layout-drops-he", (dir) => {
  setText(dir, "app/layout.tsx", (s) => replaceOnce(s, "  he: heMessages,\n", ""));
}));
check(
  "C a locale missing from the layout bundle reds check 5 alone",
  c.status === 1 && c.failed === 1 && red(c.out, "app/layout.tsx maps every shipped catalogue in its messagesMap"),
  `${tally(c)}; layout=${red(c.out, "app/layout.tsx maps every shipped catalogue in its messagesMap")}`,
);

/* D — he quits the locales list; the catalogue still sits in messages/. */
const d = run(plane("d-locales-drop-he", (dir) => {
  setText(dir, "i18n/locales.ts", (s) => replaceOnce(s, '"ar", "he"', '"ar"'));
}));
check(
  "D a catalogue on disk with no entry in the locales list reds check 1",
  d.status === 1 && d.failed >= 1 && red(d.out, "the shipped locales list is exactly the catalogue directory"),
  `${tally(d)}; locales=${red(d.out, "the shipped locales list is exactly the catalogue directory")}`,
);

/* E — the middleware loses its Hebrew branch. */
const e = run(plane("e-middleware-drops-he", (dir) => {
  setText(dir, "middleware.ts", (s) => replaceOnce(s, '    if (base === "he") return "he";\n', ""));
}));
check(
  "E a locale the middleware has no branch for reds check 2",
  e.status === 1 && e.failed >= 1 && red(e.out, "middleware has an Accept-Language branch for every shipped locale's base script"),
  `${tally(e)}; middleware=${red(e.out, "middleware has an Accept-Language branch for every shipped locale's base script")}`,
);

/* F — the floors lose `he` — the pin the API-side test holds to. */
const fPlane = plane("f-floors-drop-he", null);
{
  const path = join(fPlane, "api", "tests", "test_locale_claims.py");
  writeFileSync(path, replaceOnce(readFileSync(path, "utf8"), ', "he": 4224}', "}"));
}
const f = run(fPlane);
check(
  "F a README_FLOORS table without `he` reds check 8",
  f.status === 1 && f.failed === 1 && red(f.out, "apps/api/tests/test_locale_claims.py README_FLOORS pins every shipped non-fallback locale"),
  `${tally(f)}; floors=${red(f.out, "apps/api/tests/test_locale_claims.py README_FLOORS pins every shipped non-fallback locale")}`,
);

/* G — a catalogue lands that nothing wires; the directory discovery charges it. */
const g = run(plane("g-fr-lands-unwired", (dir) => {
  writeFileSync(join(dir, "web", "messages", "fr.json"), JSON.stringify({ nav: { home: "Accueil" } }));
}));
const gFailed = (g.out.match(/^FAIL/gm) ?? []).length;
check(
  "G an unwired fr.json reds every catalogue-dependent check",
  g.status === 1 && red(g.out, "the shipped locales list is exactly the catalogue directory") && gFailed >= 5,
  `${tally(g)}; failing checks: ${gFailed}`,
);

/* H — the arms never touched this tree. */
const h = run(plane("h-real-tree", null));
check(
  "H the real tree still reads 8/8 after the arms",
  h.status === 0 && h.failed === 0,
  tally(h),
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log(`fixture kept for inspection: ${root}`);
  process.exitCode = 1;
} else {
  rmSync(root, { recursive: true, force: true });
}
