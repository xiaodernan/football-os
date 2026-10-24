#!/usr/bin/env node
/*
 * The browser walks, one command.
 *
 * Five walks live in `apps/web/scripts/`: the scout's screen, the community wall, the stored timeline,
 * the carry-over panel and the season ledger. Each one needs three things the repository does not keep
 * running for it — an API tier, a production build of the web tier, and a **fresh** database (several
 * of the checks assume an empty one) — and each one has to be told which port its API is on and which
 * build it is measuring. That bookkeeping is where a re-measurement goes wrong: a walk pointed at a
 * build that was half written, or at a database a previous run had filled, measures a tree nobody
 * shipped.
 *
 * So this file does the bookkeeping, and it does it the way a person would:
 *
 *   * one API tier per walk, on its own port, over its own fresh SQLite file, with the world's
 *     auto-sync and the knowledge auto-ingest on (the walks read a generated world);
 *   * the production build named by `QA_DIST` — default `.next` — waited for until it carries a
 *     `BUILD_ID`, because `next start` refuses a directory with no build and a walk that starts before
 *     the build is finished measures a half-written tree;
 *   * the walk itself, with `QA_BASE` and `QA_DIST` pinned, and its exit code kept;
 *   * a pause between walks, because the tier's rate door trips on a back-to-back run and a walk that
 *     is refused by a rate limit measures the rate limit.
 *
 * Usage:
 *
 *   node scripts/run-walks.mjs                 # every walk, in order
 *   node scripts/run-walks.mjs scout ledger    # only those two
 *   QA_DIST=.next-walks3 node scripts/run-walks.mjs
 *
 * The walk's own output is the evidence: it prints every check it made, and the exit code says
 * whether the tree passed. This file prints the frame around it — which build, which port, which
 * database — and a summary at the end.
 *
 * It also reads the **tiers' own log** for one line: `MISSING_MESSAGE`, next-intl's answer to a page
 * that asked its catalogue for a key it does not hold. That error is raised on the server, so the browser
 * never sees it and the walk's console check cannot either — the page renders an exception where a
 * sentence should be, and nothing says so. A walk whose tier logged one is a walk that failed, whatever
 * its own checks said.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const WEB = join(REPO, "apps", "web");
const API_DIR = join(REPO, "apps", "api");
const SCRATCH = "D:\\football_os_scratch";
const DIST = process.env.QA_DIST ?? ".next";
const CHROME = process.env.CHROME_PATH ?? "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
/** The pause between walks, in milliseconds: the tier's rate door needs the clock to turn. */
const PAUSE = Number(process.env.QA_WALK_PAUSE ?? 75000);

/**
 * Each walk, the API port it is served on, the web port it is measured on, and the database it gets.
 *
 * The order is the order the tiers depend on nothing but the API: the scouting screen, the community wall,
 * the stored timeline, the carry-over panel, the season ledger, the academy tier, the creator tier, the
 * portfolio and the market.
 */
const WALKS = [
  { name: "scout", api: 8764, web: 3241 },
  { name: "community", api: 8765, web: 3242 },
  { name: "timeline", api: 8766, web: 3243 },
  { name: "carry", api: 8767, web: 3244 },
  { name: "ledger", api: 8768, web: 3245 },
  { name: "club", api: 8769, web: 3246 },
  { name: "creator", api: 8770, web: 3247 },
  { name: "portfolio", api: 8771, web: 3248 },
  { name: "market", api: 8772, web: 3249 },
  { name: "visual", script: "visual-qa.mjs", api: 8773, web: 3250 },
];

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

const start = (command, args, options) => {
  const child = spawn(command, args, { ...options, stdio: ["ignore", "pipe", "pipe"] });
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  return child;
};

/**
 * The API's own log, read for the one line that means a page asked its catalogue for something it does
 * not hold.
 *
 * next-intl answers a missing key with an error **on the server**, and the browser never sees it: the page
 * renders an exception where a sentence should be, the walk's own checks may not touch that cell, and the
 * walk's console check cannot see it either. The club walk's server log carried `MISSING_MESSAGE:
 * club.no (en)` for a day before anyone read it — the plan page asked the club catalogue for `yes` and
 * `no`, which live in common. A walk that reads the server's log for that line catches the class.
 */
const missingMessages = [];
const watchForMissingMessages = (child, label) => {
  const read = (chunk) => {
    const text = String(chunk);
    for (const line of text.split(/\r?\n/)) {
      if (line.includes("MISSING_MESSAGE")) missingMessages.push(`${label}: ${line.trim().slice(0, 160)}`);
    }
  };
  child.stdout.on("data", read);
  child.stderr.on("data", read);
};

const stop = async (child) => {
  if (!child || child.exitCode !== null) return;
  await new Promise((done) => {
    const killer = spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    killer.on("exit", done);
    setTimeout(done, 5000);
  });
};

/** The API answers before the web tier is asked to start: a walk against an API that is not up yet measures a refusal. */
const waitFor = async (url, child, timeout = 180000) => {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (child && child.exitCode !== null) throw new Error(`the tier exited with ${child.exitCode}`);
    try {
      const response = await fetch(url, { redirect: "manual" });
      if (response.status < 500) return;
    } catch {
      /* not up yet */
    }
    await sleep(1000);
  }
  throw new Error(`the tier never answered ${url}`);
};

async function runWalk(walk) {
  const database = join(SCRATCH, `walk_${walk.name}.db`);
  for (const suffix of ["", "-wal", "-shm"]) rmSync(`${database}${suffix}`, { force: true });

  const buildId = join(WEB, DIST, "BUILD_ID");
  if (!existsSync(buildId)) throw new Error(`there is no build in ${DIST} — run \`npm run build\` first`);
  console.log(`\n=== ${walk.name}: build ${readFileSync(buildId, "utf8").trim()} · API :${walk.api} · web :${walk.web}`);

  const api = start("python", ["-m", "uvicorn", "app.main:app", "--port", String(walk.api)], {
    cwd: API_DIR,
    env: {
      ...process.env,
      DATABASE_URL: `sqlite:///${database.replace(/\\/g, "/")}`,
      ENV: "development",
      KNOWLEDGE_AUTO_INGEST: "1",
      WORLD_AUTO_SYNC: "1",
    },
  });
  watchForMissingMessages(api, `api:${walk.api}`);
  let web;
  try {
    await waitFor(`http://127.0.0.1:${walk.api}/api/v1/healthz`, api);
    web = start("node", ["node_modules/next/dist/bin/next", "start", "-p", String(walk.web)], {
      cwd: WEB,
      env: {
        ...process.env,
        NEXT_DIST_DIR: DIST,
        API_INTERNAL_URL: `http://127.0.0.1:${walk.api}`,
        SITE_URL: `http://127.0.0.1:${walk.web}`,
      },
    });
    watchForMissingMessages(web, `web:${walk.web}`);
    await waitFor(`http://127.0.0.1:${walk.web}/`, web);

    const code = await new Promise((done) => {
      const child = start("node", [`scripts/${walk.script ?? `qa-${walk.name}.mjs`}`], {
        cwd: WEB,
        env: {
          ...process.env,
          QA_BASE: `http://127.0.0.1:${walk.web}`,
          QA_DIST: DIST,
          CHROME_PATH: CHROME,
        },
      });
      child.on("exit", (exitCode) => done(exitCode ?? 1));
    });
    console.log(`--- ${walk.name}: exit ${code}`);
    if (missingMessages.length > 0) {
      console.log(`--- ${walk.name}: ${missingMessages.length} MISSING_MESSAGE(s) in the tiers' own log`);
      for (const line of missingMessages.slice(0, 8)) console.log(`      ${line}`);
      missingMessages.length = 0;
      return code === 0 ? 1 : code;
    }
    return code;
  } finally {
    await stop(web);
    await stop(api);
  }
}

const wanted = process.argv.slice(2).filter(Boolean);
const list = wanted.length ? WALKS.filter((walk) => wanted.includes(walk.name)) : WALKS;
if (list.length === 0) {
  console.error(`no walk named ${wanted.join(", ")} — the walks are ${WALKS.map((walk) => walk.name).join(", ")}`);
  process.exit(2);
}

mkdirSync(SCRATCH, { recursive: true });
let failed = 0;
for (const walk of list) {
  try {
    const code = await runWalk(walk);
    if (code !== 0) failed += 1;
  } catch (error) {
    failed += 1;
    console.log(`--- ${walk.name}: ERROR ${error.message}`);
  }
  if (walk !== list[list.length - 1]) await sleep(PAUSE);
}
console.log(`\n${list.length - failed}/${list.length} walks green`);
process.exit(failed === 0 ? 0 : 1);
