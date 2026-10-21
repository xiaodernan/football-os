#!/usr/bin/env node
/*
#77 — every invocable script in this directory is accounted for: a gate this project recognises names it, or the
file is exempt for a reason its own bytes prove, re-measured on every run.

Measured on plane `git archive HEAD` + this file (see docs/ERROR_SHAPE_WEB_VERIFICATION.md's successor record):
population **14** invocable scripts — 12 `.mjs` and 1 `.sh` — of which **1** was named by a runner before this file
landed (`qa-error-shape.mjs`, #76) and 0 were named before #76 landed. Restricting the population to `.mjs` hides
`verify-production.sh`, which is the most consequential file here: it type-checks, lints, builds, serves the fresh
build, proves the port answers before it walks, and exits 1/3 — and nothing invokes it.

The claim this gate protects is not "run more scripts"; it is *"the browser walks are verified"*, which ten files
nothing invokes currently carry. So an exemption is a **predicate over the file's behaviour**, never a bare name:
`live-tier` requires the script to need a browser *and* a live server, `report-only` requires it to never set an
exit status at all. Add a name to the ledger and the ledger's own proof clause (check 3) reads the file.

Checks (the population is `readdirSync` of this directory, so a new script is classified automatically):
  1  scan non-empty and at least FLOOR invocable scripts — a parse that finds nothing must not read as "all accounted"
  1b every runner file was readable                      — an unread gate reads as "nothing is gated"
  2  a file is not both named and exempt                 — two accounts is one hiding place
  3  a claimed reason holds on that file's bytes         — the anti-hiding-place clause
  4  a file with no gate and no proven reason is RED      — the clause that is red on today's tree
  5  a runner may not name a script that does not exist   — a gate that invokes a phantom gates nothing
  5b same, for the package manifest
  5c same, for a script this directory's own files delegate to — a wrapper inherits its reason from the child it runs
  6  a print-only report may never be named as a gate     — the ceiling on a file that cannot fail a build
  7  a script needing neither browser nor server must be named — why #76's gate had to enter check.sh
  8  this census names itself in a runner and holds no ledger entry — see the note under check 8

Known limitation, named rather than engineered away: check 7 cannot see this file's own tier-freeness, because a
`.mjs` census must contain the browser/server tokens it looks for, so this file's bytes match its own `live-tier`
predicate. That is exactly why check 8 exists and keys on identity instead of behaviour: without it, a census could
exempt itself by citing a reason its own pattern source "proves" (arm A9).

Predictions, written into `.scratch/r77_predictions.md` before the first run and re-derived for the shipped
mechanism; the full witness is 16 runs (12 arms + the A5b/A5c reach pair + control) at
`.scratch/r77_arms.py` -> `SUMMARY runs=16 matched=16 not-matched=0`, every red judged by its label
(check id + the script it names), never by a count alone:

  control on the plane, this file present and named by both runners: CHECKS passed=39 total=39 failed=0, rc 0.
  The 39 decomposes as 1 + 1b (2) + 2 + 3 over 14 rows (28) + 4 check-5 firings + 1 (5b) + 1 (5c) + 1 (6) + 1 (7)
  + 1 (8).
  P1 pre-#76 reverse control (`e07fcfb`, working copy, `.mjs`-only population): failed=2 — checks 4 and 7 on
     `qa-error-shape.mjs`.
  P2 post-#76, this file not yet present: failed=0, **total=31**. The first written prediction said the total would
     stay 30 because "the two reds are conditional clauses"; wrong arithmetic, corrected by the run — naming a
     script deletes its check-4 firing (−1) and adds one check-5 firing per runner that names it (+2). A census over
     a population that contains the counter does not keep a constant denominator either, and the arms table had to
     predict `total` as well as `failed` for that reason.
  A1b and A12 are designed GREEN controls, and each green is a finding: deleting the invocation from ONE of the two
     runners leaves the script gated (check 5 keys on any runner, so no single carrier is decisive), and a comment
     that mentions `scripts/qa-carry.mjs` does not gate it (only a `node …scripts/…` call does).

*/

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// What counts as a runner *invoking* a script. Anchored on the call, not on the substring: a step that merely
// mentions `scripts/qa-carry.mjs` in a comment would otherwise mark that file gated while running nothing, and the
// census would certify a hiding place. Arm A12 in the record is exactly that sentence written into check.sh.
const INVOKES = /node\s+[\w./\\-]*scripts\/([\w-]+\.(?:mjs|sh))/g;
const invoked = (text) => [...(text ?? "").matchAll(INVOKES)].map((m) => m[1]);

const HERE = process.env.INVENTORY_DIR ? resolve(process.env.INVENTORY_DIR)
  : dirname(fileURLToPath(import.meta.url));
const WEB = resolve(HERE, "..");
const REPO = resolve(WEB, "../..");
const SELF = basename(fileURLToPath(import.meta.url));
const FLOOR = 15;

const GATES = [
  { label: "scripts/check.sh", file: resolve(REPO, "scripts/check.sh") },
  { label: ".github/workflows/ci.yml", file: resolve(REPO, ".github/workflows/ci.yml") },
].map((g) => ({ ...g, text: existsSync(g.file) ? readFileSync(g.file, "utf8") : null, missing: !existsSync(g.file) }));

const PACKAGE_JSON = resolve(WEB, "package.json");
// A delegation can target this directory or the repository's own launcher directory; both roots are real.
const ROOTS = [HERE, resolve(REPO, "scripts")];
const resolveScript = (name) => ROOTS.map((r) => resolve(r, name)).find(existsSync) ?? null;

// Exemptions are reasons, not names. A name in the ledger only claims a reason; check 3 proves it holds.
// The keys below are the fact names `direct()` builds — a reason that reads a name the row does not carry evaluates
// to `undefined`, which is falsy, so the miss shows up as twelve unexplained files rather than as a crash. That is
// the shape of the bug this line had on its first run (it read `needsBrowser` where the row says `browser`).
const REASONS = [
  { id: "live-tier", text: "needs a browser and a live web+API tier, so it cannot run in a static gate",
    holds: (f) => f.browser && f.server },
  { id: "report-only", text: "prints a reading and never sets an exit status, so it is a report, not a gate",
    holds: (f) => !f.setsExit },
];

const LEDGER = {
  "probe-hydration.mjs": ["report-only"],
  "qa-carry.mjs": ["live-tier"], "qa-club.mjs": ["live-tier"], "qa-community.mjs": ["live-tier"],
  "qa-creator.mjs": ["live-tier"], "qa-ledger.mjs": ["live-tier"], "qa-market.mjs": ["live-tier"],
  "qa-portfolio.mjs": ["live-tier"], "qa-scout.mjs": ["live-tier"], "qa-timeline.mjs": ["live-tier"],
  "verify-production.sh": ["live-tier"], "visual-qa.mjs": ["live-tier"],
};

const reads = (name) => readFileSync(resolve(HERE, name), "utf8");

// Direct evidence only: a file proves a tier need by naming a driver, binding a base URL, or reading a base URL.
const direct = (name) => {
  const text = reads(name);
  return {
    name,
    lines: text.split(/\r?\n/).length,
    browser: /puppeteer|playwright/.test(text),
    server: /QA_BASE|API_BASE|127\.0\.0\.1|localhost|fetch\(/.test(text),
    setsExit: /process\.exitCode\s*=|process\.exit\(\s*[^0)]|exit [1-9]/.test(text),
    refs: [...new Set(invoked(text))].filter((r) => r !== name),
  };
};

// A wrapper inherits a tier need from the script it delegates to: `verify-production.sh` starts the server itself
// and drives the browser through its child, so a browser claim that is false of its bytes is true of its behaviour.
const facts = () => {
  const rows = new Map();
  for (const name of readdirSync(HERE).filter((f) => /\.(mjs|sh)$/.test(f)).sort()) rows.set(name, direct(name));
  for (let pass = 0; pass < rows.size; pass += 1) {
    let stable = true;
    for (const row of rows.values()) {
      for (const ref of row.refs) {
        const child = rows.get(ref);
        if (!child) continue;
        if (child.browser && !row.browser) { row.browser = true; stable = false; }
        if (child.server && !row.server) { row.server = true; stable = false; }
      }
    }
    if (stable) break;
  }
  return [...rows.values()];
};

const run = () => {
  const tally = new Map();
  let passed = 0;
  let checks = 0;
  const check = (label, ok, detail) => {
    checks += 1;
    const id = label.split(" ")[0];
    tally.set(id, (tally.get(id) ?? 0) + 1);
    if (ok) { passed += 1; return; }
    console.log(`FAIL ${label}${detail ? ` — ${detail}` : ""}`);
  };

  const rows = facts();
  check(`1 scan finds the population (>= ${FLOOR} invocable scripts here)`,
        rows.length >= FLOOR, `found ${rows.length}`);
  check("1b every gate file was readable", GATES.every((g) => !g.missing),
        GATES.filter((g) => g.missing).map((g) => g.label).join(", "));

  const namedBy = (name) => GATES.filter((g) => g.text && invoked(g.text).includes(name)).map((g) => g.label);

  for (const row of rows) {
    const gates = namedBy(row.name);
    const claimed = LEDGER[row.name] ?? [];
    const proven = claimed.filter((id) => REASONS.find((r) => r.id === id).holds(row));
    // Exactly once = not both (this check) and not neither (check 4). Charging one defect twice would make a single
    // unaccounted script look like two findings and break the prediction written for it.
    check(`2 ${row.name} is not both gated and exempt`,
          !(gates.length > 0 && proven.length > 0),
          `gates=[${gates.join(",")}] proven-reasons=[${proven.join(",")}]`);
    check(`3 ${row.name}'s claimed reasons hold on its own bytes`,
          claimed.length === proven.length,
          `claimed ${claimed.join(",")} but the file is browser=${row.browser} server=${row.server} exit=${row.setsExit}`);
    if (gates.length === 0 && proven.length === 0) {
      check(`4 ${row.name} is neither gated nor explained`, false,
            `no gate names it and no reason in the ledger holds: browser=${row.browser} server=${row.server} setsExit=${row.setsExit}`);
    }
    if (!row.browser && !row.server) {
      check(`7 ${row.name} needs no tier, so a gate must name it`, gates.length > 0,
            `nothing in ${GATES.map((g) => g.label).join(" / ")} invokes it`);
    }
    if (!row.setsExit) {
      check(`6 ${row.name} never sets an exit status, so no gate may name it`, gates.length === 0,
            `named by ${gates.join(", ")}`);
    }
    for (const ref of row.refs) {
      check(`5c ${row.name} delegates to a script that exists (${ref})`, resolveScript(ref) !== null,
            `not in ${ROOTS.join(" nor ")}`);
    }
  }

  for (const g of GATES) {
    for (const ref of invoked(g.text)) {
      check(`5 ${g.label} invokes a script that exists (${ref})`, resolveScript(ref) !== null, "no such file");
    }
  }

  const pkg = existsSync(PACKAGE_JSON) ? readFileSync(PACKAGE_JSON, "utf8") : "";
  for (const ref of invoked(pkg)) {
    check(`5b package.json invokes a script that exists (${ref})`, resolveScript(ref) !== null, "no such file");
  }

  const selfRow = rows.find((r) => r.name === SELF);
  const selfGates = selfRow ? namedBy(SELF) : [];
  check(`8 the census ${SELF} is named by a runner and holds no ledger entry`,
        selfRow !== undefined && selfGates.length > 0 && (LEDGER[SELF] ?? []).length === 0,
        selfRow === undefined ? "the census file is not in its own population"
          : `gates=[${selfGates.join(",")}] ledger=[${(LEDGER[SELF] ?? []).join(",")}]`);

  if (process.env.INVENTORY_TALLY) {
    console.log(`TALLY ${[...tally.entries()].sort().map(([k, v]) => `${k}=${v}`).join(" ")}`);
  }
  console.log(`CHECKS passed=${passed} total=${checks} failed=${checks - passed}`);
  for (const row of rows) {
    console.log(`  ${row.name} lines=${row.lines} browser=${row.browser} server=${row.server} `
      + `exit=${row.setsExit} refs=[${row.refs.join(",")}] gates=[${namedBy(row.name).join(",")}] `
      + `ledger=[${(LEDGER[row.name] ?? []).join(",")}]`);
  }
  return passed === checks ? 0 : 1;
};

process.exitCode = run();
console.log(`ran ${SELF} against ${HERE}`);
