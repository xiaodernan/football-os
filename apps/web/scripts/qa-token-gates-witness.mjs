#!/usr/bin/env node
/*
 * The two token gates' verdicts, on scratch catalogues.
 *
 * `qa-locale-tokens.mjs` (7 checks) defines the named technical tokens and owns the rules about them;
 * `qa-token-drift.mjs` (4 checks) reads that table and witnesses that the named values have not moved. Both
 * read files, so a green line from either says only what the one checkout on disk happens to hold. This file
 * builds a fixture per verdict and runs **both shipped gates** against it through `QA_I18N_WEB`, so what is
 * measured is behaviour: which check reddens, on which locale, naming which path.
 *
 * The catalogues come from `git show HEAD:` rather than from disk. The shared worktree held 4269 English
 * leaves against a table that states 4096 on 2026-11-08, because another lane had added keys and owed the
 * recompute — a red that belongs to their work, and a mixed basis for this one. Every plane is therefore built
 * from one committed basis (4096 leaves, 4051 translated in each Chinese catalogue, 45 named tokens) and only
 * the *scripts* are read off disk, which is what is under test. The one exception is arm 0, which runs the
 * real tree and tolerates exactly that attributed red; it says so in the open.
 *
 * Predictions, written before the first run (2026-11-08).
 *   0  the shipped gates on the real catalogues: drift 4/4, and every definer red is the table check saying
 *      the row counts a different population than the catalogue holds. Pre-fix this was 5/5 + 2/2 green on the
 *      same tree, because neither gate could see the uncommitted keys as a population.
 *   A  `ar.json` as a byte copy of `en.json`: 3 definer reds — shared values unnamed (4096 − 45 of them), the
 *      table with no `ar` row, the floors with no `ar` floor — and the drift gate's reverse check. Pre-fix:
 *      5/5 and 2/2 green, both with `zh, zh-TW` named in the source.
 *   B  `ar.json` holding two properly Arabic messages and nothing else: 3 definer reds — every named token
 *      missing from the file, no row, no floor — and the drift stability check. Nothing is charged for being
 *      untranslated, because a missing key is not an identical value.
 *   C  one message planted three levels deep in `en.json` and copied into `zh.json`: 1 definer red and 1 drift
 *      red, each naming `zh: witness.deep.inner`. Pre-fix both gates walked two levels and printed 5/5 + 2/2
 *      green beside the planted value.
 *   D  a Chinese sentence planted three levels deep in `en.json`: 1 definer red, the English-is-English check,
 *      naming the path — and drift green, because drift compares locales and this is the reference file.
 *      Pre-fix 5/5 green: this is the founding defect of the whole arc, invisible one level further down.
 *   E  a plane whose `messages/` holds only `en.json`: the definer reddens the population check alone and
 *      prints `NOT JUDGED` for the four comparison rules; drift reddens its population check *and* the two
 *      checks that would otherwise pass by comparing nothing. Pre-fix: 5/5 + 2/2 green, both by naming `zh`.
 *   F  a plane with no `qa-locale-tokens.mjs`: 3 drift reds — the table cannot be read, so the named-token
 *      comparison judges nothing, and the 45 values that were exempt become unnamed. Derived count, not 90.
 *   G  a planted second copy of the table, six entries as literals in a scratch script beside the gates: 1
 *      definer red, the one-file check, naming the file. Drift is untouched: it reads rather than restates.
 *   H  the reverse control: the same byte copy, with an `ar` row written and a floor on record. Only the
 *      unnamed-value rule is left standing — 1 definer red, 1 drift red — which is what proves A's other two
 *      reds were the row and the floor, not the copy.
 *   I  the real tree again after the fixture arms, with the same red sets as arm 0: no arm leaked into the
 *      checkout the gates ship from.
 * Checks: 10, all green on the cured gates.
 *
 * Revised after the first run, which red 6 of these 10 and taught four things. (1) A witness bug: both gates
 * print each refusal twice, once in its own line and once in the trailer that lists the failures, so my red set
 * had every member doubled and no arm could match a predicted set. `redSetOf` deduplicates now — an arm that
 * counted the trailer as a second finding was reading output, not verdicts. (2) A gate defect, and the one this
 * arc keeps meeting: on the arm-E plane the definer's population line printed `FAIL` beside the sentence it
 * prints when it passes, because the detail was keyed on `SHIPPED.includes("en")` rather than on the check's
 * own condition. Two refusal lines in the drift gate had the same shape. All three now key on the whole
 * condition and say `not judged —`, which is what a reader needs when the cause is the plane rather than the
 * copy. (3) Arm A's second expectation was mine, not the gate's: I predicted the drift gate would charge 4051
 * shared values, the strict rule's number, and it charged 3943, because this gate has always skipped shared
 * values of three characters or fewer and values holding no letters. The count is now derived from the plane
 * against that floor instead of copied from the other gate — and the lenient rule is stated in the gate's own
 * header, since two gates printing different numbers for one tree is only acceptable when a reader can see why.
 * (4) Arm D asked the gate to print the planted Chinese sentence; the check names paths, not values, so the
 * assertion now quotes the verdict phrase and the path it charges.
 *
 * Files only: no server, no browser, no port.
 */

import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(HERE, "..");
const REPO = resolve(WEB, "..", "..");
const REAL = join(WEB, "messages");
const DEFINER = "qa-locale-tokens.mjs";
const DRIFT = "qa-token-drift.mjs";
const BASE = ["en", "zh", "zh-TW"];

/** One committed basis for every plane. A fixture built from a dirty worktree inherits another lane's debt and
 *  then charges it to this unit. */
const committed = (name) => {
  const result = spawnSync("git", ["-C", REPO, "show", `HEAD:apps/web/messages/${name}`], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  if (result.status !== 0) throw new Error(`git show HEAD:apps/web/messages/${name} failed: ${result.stderr}`);
  return result.stdout;
};

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const root = mkdtempSync(join(tmpdir(), "qa-token-gates-witness-"));

const leaves = (node, prefix = "", out = new Map()) => {
  if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) leaves(value, prefix ? `${prefix}.${key}` : key, out);
    return out;
  }
  if (typeof node === "string") out.set(prefix, node);
  return out;
};
const planeLeaves = (dir, locale) => {
  const path = join(dir, "messages", `${locale}.json`);
  return existsSync(path) ? leaves(JSON.parse(readFileSync(path, "utf8"))) : new Map();
};

/** The table's paths, scraped from the shipped definer rather than copied here — arm F needs to know how many
 *  exemptions vanish when its file is gone, and a hand-written 45 rots the day an entry is added. */
const TABLE_PATHS = (() => {
  const source = readFileSync(join(WEB, "scripts", DEFINER), "utf8");
  const body = /const TOKENS = new Map\(\[([\s\S]*?)\]\);/.exec(source)[1];
  return [...body.matchAll(/\[\s*"([^"]+)"\s*,/g)].map((match) => match[1]);
})();

const PLANT = "Match report is ready for review";
const ARABIC = "تقرير المباراة جاهز للمراجعة الآن";
const CHINESE = "找一个能踢左后卫的年轻球员";

/**
 * A plane: HEAD's three catalogues and table, this checkout's two gate scripts, then the arm's mutation, then
 * the two README rows rewritten to the figures the plane's own bytes hold.
 *
 * The rewrite is the one place this file computes what the gate computes (population and translated count, from
 * the same leaves). It is fixture plumbing, not a verdict: no arm asserts on the table check because of it, and
 * an arm whose planted key moved a figure it did not expect goes red rather than quiet.
 */
function fixture(name, mutate = null, { withDefiner = true, normBase = BASE } = {}) {
  const dir = join(root, name);
  mkdirSync(join(dir, "messages"), { recursive: true });
  mkdirSync(join(dir, "scripts"), { recursive: true });
  for (const locale of BASE) writeFileSync(join(dir, "messages", `${locale}.json`), committed(`${locale}.json`));
  writeFileSync(join(dir, "messages", "README.md"), committed("README.md"));
  for (const script of [DEFINER, DRIFT]) {
    if (!withDefiner && script === DEFINER) continue;
    cpSync(join(WEB, "scripts", script), join(dir, "scripts", script));
  }
  if (mutate) mutate(dir);
  const population = planeLeaves(dir, "en").size;
  let readme = readFileSync(join(dir, "messages", "README.md"), "utf8");
  for (const locale of normBase) {
    if (locale === "en" || !existsSync(join(dir, "messages", `${locale}.json`))) continue;
    const other = planeLeaves(dir, locale);
    let translated = 0;
    for (const [path, value] of planeLeaves(dir, "en")) if (other.get(path) !== value) translated += 1;
    const row = new RegExp(`(\\|\\s*\`?${locale}\\.json\`?\\s*\\|\\s*)\\d+ of \\d+`, "u");
    if (!row.test(readme)) throw new Error(`no ${locale} row to normalise on this plane`);
    readme = readme.replace(row, `$1${translated} of ${population}`);
  }
  writeFileSync(join(dir, "messages", "README.md"), readme);
  return dir;
}

/** A message at a path of any depth, creating the levels it needs. */
function setPath(dir, locale, dottedPath, value) {
  const path = join(dir, "messages", `${locale}.json`);
  const catalogue = existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
  let node = catalogue;
  const steps = dottedPath.split(".");
  for (const step of steps.slice(0, -1)) node = (node[step] ??= {});
  node[steps.at(-1)] = value;
  writeFileSync(path, `${JSON.stringify(catalogue, null, 2)}\n`);
}

const tally = (out) => {
  const m = /CHECKS passed=(\d+) total=(\d+) failed=(\d+)/.exec(out);
  return m ? { passed: Number(m[1]), total: Number(m[2]), failed: Number(m[3]) } : { passed: null, total: null, failed: null };
};
/** A gate prints each refusal twice — once in its check line and once in the trailer that lists the failures —
 *  so the set is deduplicated before it is compared. An arm that charged the trailer's repeat as a second
 *  finding would be reading output, not verdicts. */
const redSetOf = (out) => [...new Set([...out.matchAll(/^FAIL\s{2}([^\n—]*?)\s+—/gm)].map((m) => m[1].trim()))].sort();
const verdictOf = (out, label) => (out.includes(`FAIL  ${label}`) ? "FAIL" : out.includes(`PASS  ${label}`) ? "PASS" : "absent");
const escapeRe = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const detailOf = (out, label) => (new RegExp(`^(?:PASS|FAIL)\\s{2}${escapeRe(label)}[^\\n]*? — ([^\\n]*)$`, "m").exec(out) ?? [])[1] ?? "";

function runOne(script, dir) {
  const file = join(dir, "scripts", script);
  if (!existsSync(file)) return { absent: true, out: "", ...{ passed: null, total: null, failed: null, reds: [] }, status: null };
  const result = spawnSync(process.execPath, [file], { env: { ...process.env, QA_I18N_WEB: dir }, encoding: "utf8" });
  const out = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  return { absent: false, out, status: result.status, crashed: /TypeError|SyntaxError|ReferenceError/.test(out), ...tally(out), reds: redSetOf(out) };
}
const run = (dir) => {
  const d = runOne(DEFINER, dir);
  const r = runOne(DRIFT, dir);
  return { d, r };
};

const D_ENGLISH = "the English catalogue holds no Chinese";
const D_POP = "the directory ships at least one catalogue beside the fallback";
const D_UNNAMED = "every value any catalogue shares with the English is a named technical token";
const D_STALE = "every named technical token is still a token";
const D_TABLE = "the catalogue's own table states the figures the catalogue holds";
const D_FLOORS = "a sentence held under two keys is worded the same way in every language";
const D_ONE = "this table is defined in one file and read by every gate that needs it";
const R_READ = "the named-token table is read from the gate that defines it";
const R_POP = "the fallback and at least one other catalogue are on this plane";
const R_STABLE = "every named technical token is still identical across all locales";
const R_UNNAMED = "no unnamed identical values that should be named tokens";

const summary = (arm, { dReds, rReds }) => {
  const ok =
    dReds.every((l) => arm.d.reds.includes(l)) && arm.d.reds.length === dReds.length &&
    rReds.every((l) => arm.r.reds.includes(l)) && arm.r.reds.length === rReds.length &&
    !arm.d.crashed && !arm.r.crashed;
  return { ok, detail: `definer rc=${arm.d.status} ${arm.d.passed}/${arm.d.total}; drift rc=${arm.r.status} ${arm.r.passed}/${arm.r.total}; definer reds [${arm.d.reds.join(" | ") || "none"}]; drift reds [${arm.r.reds.join(" | ") || "none"}]` };
};
/** The exact red set, both gates, every arm: a second red means the arm found something it did not predict,
 *  and a missing one means the rule is not armed. */
const reds = (arm, dReds, rReds) => summary(arm, { dReds: [...dReds].sort(), rReds: [...rReds].sort() });

/* 0 — the shipped gates against the real catalogues, with the one attributed red said out loud. */
const realWeb = { d: runOne(DEFINER, WEB), r: runOne(DRIFT, WEB) };
const realTableRed = verdictOf(realWeb.d.out, D_TABLE) === "FAIL";
const realTablePopulation = detailOf(realWeb.d.out, D_TABLE).includes("counts a population of");
check(
  "0 drift is clean on the real tree and the definer's only red is the table's population",
  realWeb.r.status === 0 && realWeb.r.total === 4 && realWeb.r.failed === 0 &&
    realWeb.d.total === 7 &&
    (realTableRed ? realWeb.d.failed === 1 && realTablePopulation : realWeb.d.failed === 0),
  `definer ${realWeb.d.passed}/${realWeb.d.total} reds [${realWeb.d.reds.join(" | ") || "none"}]; drift ${realWeb.r.passed}/${realWeb.r.total}; table says: ${detailOf(realWeb.d.out, D_TABLE).slice(0, 150)}`,
);

/* A — the hole: a fourth catalogue that is English by the byte. */
const byteCopy = fixture("A-arabic-byte-copy-of-english", (dir) => {
  cpSync(join(dir, "messages", "en.json"), join(dir, "messages", "ar.json"));
});
const a = run(byteCopy);
const aShared = planeLeaves(byteCopy, "en").size - TABLE_PATHS.length;
/** The drift gate's own lenient floor: a shared value of three characters or fewer, or one with no letters, is
 *  not charged there. The count is derived from the plane and the table, not copied from the printed line. */
const aEligible = [...planeLeaves(byteCopy, "en")].filter(([path, value]) => !TABLE_PATHS.includes(path) && value.length > 3 && /[a-zA-Z]/.test(value)).length;
const aCheck = reds(a, [D_UNNAMED, D_TABLE], [R_UNNAMED]);
check(
  "A a byte-copy ar.json reddens the shared-value rule and the table — the floor is on record at 0, so it does not bite",
  aCheck.ok && detailOf(a.d.out, D_UNNAMED).startsWith(`${aShared} identical value(s) that are not named: ar:`)
    && detailOf(a.d.out, D_TABLE).includes("the catalogue holds 0")
    && detailOf(a.r.out, R_UNNAMED).startsWith(`${aEligible} unnamed identical value(s): ar:`),
  `${aCheck.detail}; ar shared unnamed ${aShared}, of which ${aEligible} are eligible under the drift gate's lenient rule`,
);

/* A2 — the same byte copy without a recorded floor still reddens D_FLOORS. The splice removes the `ar: 0`
   entry wherever it sits, so a floor line that gained a sibling (`he: 0`) does not strand this arm. */
const loseArFloor = fixture("A2-arabic-byte-copy-without-recorded-floor", (dir) => {
  const definerPath = join(dir, "scripts", DEFINER);
  const source = readFileSync(definerPath, "utf8");
  const spliced = source.replace(/, "?ar"?: 0/, "").replace(/, "?ar"?: 0/, "");
  if (spliced === source) throw new Error("the records floor splice matched nothing, so this arm would judge nothing");
  writeFileSync(definerPath, spliced);
  cpSync(join(dir, "messages", "en.json"), join(dir, "messages", "ar.json"));
});
const a2 = run(loseArFloor);
const a2Check = reds(a2, [D_UNNAMED, D_TABLE, D_FLOORS], [R_UNNAMED]);
check(
  "A2 an ar.json byte copy with no recorded floor reds the floors too",
  a2Check.ok && detailOf(a2.d.out, D_FLOORS).includes("ar.json ships but no floor is on record"),
  `${a2Check.detail}; ${detailOf(a2.d.out, D_UNNAMED).slice(0, 120)}`,
);

/* B — a new locale that ships real copy but only two messages of it. */
const partial = fixture("B-arabic-partial-catalogue", (dir) => {
  setPath(dir, "ar", "witness.report", ARABIC);
  setPath(dir, "ar", "witness.deals", "{count} صفقة");
});
const b = run(partial);
const bCheck = reds(b, [D_STALE, D_TABLE], [R_STABLE]);
check(
  "B a partial ar.json is charged for the named tokens it lacks, and the missing table entry — the floor is on record at 0, so it does not bite",
  bCheck.ok && detailOf(b.d.out, D_STALE).includes("is named a token but the catalogue holds no such key")
    && detailOf(b.d.out, D_UNNAMED).includes("45 language-neutral") && detailOf(b.d.out, D_UNNAMED).includes("3 catalogue(s)")
    && detailOf(b.r.out, R_STABLE).startsWith("drift: ; missing: "),
  `${bCheck.detail}; table holds ${TABLE_PATHS.length} named path(s)`,
);

/* C — three levels deep, shared. The two-level walk never reached it. */
const deepShared = fixture("C-identical-leaf-three-levels-deep", (dir) => {
  setPath(dir, "en", "witness.deep.inner", PLANT);
  setPath(dir, "zh", "witness.deep.inner", PLANT);
});
const c = run(deepShared);
const cCheck = reds(c, [D_UNNAMED], [R_UNNAMED]);
check(
  "C one shared value three levels deep is charged at that depth by both gates",
  cCheck.ok && detailOf(c.d.out, D_UNNAMED).includes("zh: witness.deep.inner")
    && detailOf(c.r.out, R_UNNAMED).includes("zh: witness.deep.inner")
    && verdictOf(c.d.out, D_ENGLISH) === "PASS",
  `${cCheck.detail}; ${detailOf(c.d.out, D_UNNAMED).slice(0, 160)}`,
);

/* D — the founding defect, one level below where the census used to stop. */
const deepChinese = fixture("D-chinese-leaf-three-levels-deep-in-english", (dir) => {
  setPath(dir, "en", "witness.deep.inner", CHINESE);
});
const d = run(deepChinese);
const dCheck = reds(d, [D_ENGLISH], []);
check(
  "D a Chinese sentence three levels deep in en.json is charged, and drift has nothing to say",
  dCheck.ok && detailOf(d.d.out, D_ENGLISH).includes(`are Chinese: witness.deep.inner`)
    && d.r.status === 0 && d.r.reds.length === 0,
  `${dCheck.detail}; ${detailOf(d.d.out, D_ENGLISH).slice(0, 160)}`,
);

/* E — nothing to compare. */
const noLocales = fixture("E-only-the-fallback-ships", (dir) => {
  for (const locale of ["zh", "zh-TW"]) rmSync(join(dir, "messages", `${locale}.json`), { force: true });
}, { normBase: [] });
const e = run(noLocales);
const eCheck = reds(e, [D_POP], [R_POP, R_STABLE, R_UNNAMED]);
check(
  "E a plane with no catalogue beside the fallback says NOT JUDGED and reddens the comparisons that would pass on nothing",
  eCheck.ok && e.d.out.includes("NOT JUDGED") && detailOf(e.d.out, D_POP).includes("ships en.json alone")
    && detailOf(e.r.out, R_POP).includes("no catalogue beside en.json")
    && detailOf(e.r.out, R_STABLE).startsWith("not judged — messages/ ships en")
    && detailOf(e.r.out, R_UNNAMED).startsWith("not judged — messages/ ships en"),
  `${eCheck.detail}; definer trailer: ${(e.d.out.match(/NOT JUDGED[^\n]*/) ?? ["(absent)"])[0].slice(0, 120)}`,
);

/* F — the definer gone, so the exemption set cannot be read. */
const noTable = fixture("F-definer-absent", null, { withDefiner: false });
const f = run(noTable);
/** The named values become unnamed, so the count is what the plane's own bytes say about the table's paths —
 *  not a number copied from the gate. */
const eligibleNamed = (() => {
  const english = planeLeaves(noTable, "en");
  return TABLE_PATHS.filter((path) => {
    const value = english.get(path);
    return value !== undefined && value.length > 3 && /[a-zA-Z]/.test(value);
  }).length;
})();
const fCheck = reds({ d: { absent: true, crashed: false, reds: [], passed: null, total: null, status: null }, r: f.r }, [], [R_READ, R_STABLE, R_UNNAMED]);
check(
  "F with no definer on the plane, drift charges the unreadable table and refuses to call the comparisons clean",
  f.d.absent === true && fCheck.ok && detailOf(f.r.out, R_READ).includes("is not where this gate looks for it")
    && detailOf(f.r.out, R_UNNAMED).startsWith(`${eligibleNamed * 2} unnamed identical value(s):`)
    && verdictOf(f.r.out, R_POP) === "PASS" && !f.r.crashed,
  `drift rc=${f.r.status} ${f.r.passed}/${f.r.total} reds [${f.r.reds.join(" | ")}]; ${eligibleNamed} of ${TABLE_PATHS.length} named path(s) are eligible for the reverse rule, x 2 locales`,
);

/* G — a second copy of the table, which is how an exemption goes stale. */
const copier = fixture("G-second-copy-of-the-table", (dir) => {
  const entries = TABLE_PATHS.slice(0, 6).map((path) => `  ["${path}", "an API field name"],`).join("\n");
  writeFileSync(join(dir, "scripts", "qa-quoted-tokens.mjs"), `const NAMED = new Map([\n${entries}\n]);\nexport default NAMED;\n`);
});
const g = run(copier);
const gCheck = reds(g, [D_ONE], []);
check(
  "G a script beside the gates that re-states six entries is named by the one-file check",
  gCheck.ok && detailOf(g.d.out, D_ONE).includes("qa-quoted-tokens.mjs re-states 6 of the")
    && g.r.status === 0 && g.r.failed === 0,
  `${gCheck.detail}; ${detailOf(g.d.out, D_ONE).slice(0, 160)}`,
);

/* H — the reverse control: same copy, row written and floor on record. Only the value rule is left. */
const copyExcused = fixture("H-byte-copy-with-row-and-floor", (dir) => {
  cpSync(join(dir, "messages", "en.json"), join(dir, "messages", "ar.json"));
  const readmePath = join(dir, "messages", "README.md");
  const readme = readFileSync(readmePath, "utf8");
  const row = `| \`ar.json\` | 0 of ${planeLeaves(dir, "en").size} keys copied from English, byte for byte | **no** |\n`;
  const next = readme.replace(/(\| `zh-TW\.json`[^\n]*\n)/u, `$1${row}`);
  if (next === readme) throw new Error("no zh-TW row to append the ar row after, so this arm would judge nothing");
  writeFileSync(readmePath, next);
});
const h = run(copyExcused);
const hCheck = reds(h, [D_UNNAMED], [R_UNNAMED]);
check(
  "H the same copy with its row and floor on record leaves only the unnamed-value rule standing",
  hCheck.ok && verdictOf(h.d.out, D_TABLE) === "PASS" && verdictOf(h.d.out, D_FLOORS) === "PASS"
    && verdictOf(h.d.out, D_STALE) === "PASS" && verdictOf(h.r.out, R_STABLE) === "PASS",
  `${hCheck.detail}; table says: ${detailOf(h.d.out, D_TABLE).slice(0, 120)}`,
);

/* I — nothing leaked. */
const after = { d: runOne(DEFINER, WEB), r: runOne(DRIFT, WEB) };
check(
  "I the real tree reads the same both gates read before any fixture ran",
  after.d.status === realWeb.d.status && after.r.status === realWeb.r.status &&
    JSON.stringify(after.d.reds) === JSON.stringify(realWeb.d.reds) &&
    JSON.stringify(after.r.reds) === JSON.stringify(realWeb.r.reds) &&
    after.d.total === 7 && after.r.total === 4,
  `definer ${after.d.passed}/${after.d.total} reds [${after.d.reds.join(" | ") || "none"}]; drift ${after.r.passed}/${after.r.total}`,
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) {
  console.log("");
  for (const entry of failed) console.log(`FAIL  ${entry.name} — ${entry.detail}`);
  console.log(`\nfixture kept for inspection: ${root}`);
  process.exitCode = 1;
} else if (process.argv.includes("--keep")) {
  console.log(`\nfixtures kept for inspection: ${root}`);
} else {
  rmSync(root, { recursive: true, force: true });
}
