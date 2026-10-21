/**
 * The stored-timeline walk: a browser against a **production build**, checking that the match report page
 * reads its event list out of `sim_events` and says so in numbers the API also gives.
 *
 *   api tier:  http://127.0.0.1:8735        (uvicorn app.main:app --port 8735)
 *   web tier:  http://127.0.0.1:3215        (API_INTERNAL_URL=http://127.0.0.1:8735 next start -p 3215)
 *   QA_BASE=http://127.0.0.1:3215 node scripts/qa-timeline.mjs
 *
 * The point of this walk is not that a timeline renders — it rendered before this table existed. It is
 * that the figures the panel prints are the server's: the row count, the per-type split, the share of
 * events a name resolved to, and the agreement sentence are each scraped off the page and re-read from
 * the same API response the panel was built from. A page that hardcoded "one row per event" would pass a
 * screenshot and fail check 14.
 *
 * Env overrides: QA_BASE, CHROME_PATH.
 *
 * The page answers in the browser's language (§81), so this walk **pins the locale** to English with the
 * `fo_locale` cookie: a walk whose needles are English must measure the English surface, and a host whose
 * browser asks for Chinese would otherwise fail every one of them for a reason that has nothing to do with
 * the tier. The cookie is written before the first page is opened.
 */

import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import puppeteer from 'puppeteer-core';

const BASE = process.env.QA_BASE ?? 'http://127.0.0.1:3215';
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1 };
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };
const PASSWORD = 'timeline-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const EMAIL = `timeline-qa-${stamp}@footballos.test`;

const results = [];
const consoleErrors = [];
const shots = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${String(detail).slice(0, 190)}` : ''}`);
}

const has = (body, needle) => String(body).includes(String(needle));
const squeeze = (value) => String(value).replace(/\s+/g, '');
/** Eyebrows and table headers are upper-cased in CSS, so `innerText` never holds the written needle. */
const shouts = (body, needle) => squeeze(body).toUpperCase().includes(squeeze(needle).toUpperCase());

async function shot(page, name) {
  const file = `${stamp}-timeline-${name}.png`;
  try {
    await page.screenshot({ path: resolve(OUT_DIR, file), fullPage: true });
    shots.push(file);
  } catch (error) {
    check(`screenshot ${name} captured`, false, String(error?.message ?? error).slice(0, 160));
  }
}

function watch(page, label) {
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    let where = '';
    try {
      where = new URL(message.location()?.url ?? page.url()).pathname;
    } catch {
      where = page.url();
    }
    consoleErrors.push(`[${label}] ${where}: ${message.text()}`);
  });
  page.on('pageerror', (error) => consoleErrors.push(`[${label}] ${new URL(page.url()).pathname}: ${error.message}`));
}

function open(page, path) {
  return page.goto(`${BASE}${path}`, { waitUntil: 'networkidle2', timeout: 90_000 });
}

function text(page) {
  return page.evaluate(() => document.body?.innerText ?? '');
}

/** A call from inside the page, so the httpOnly cookie the proxy minted is the one being used. */
function call(page, method, path, body) {
  return page.evaluate(
    async (verb, url, payload) => {
      const response = await fetch(url, {
        method: verb,
        credentials: 'same-origin',
        headers: payload ? { 'content-type': 'application/json', accept: 'application/json' } : { accept: 'application/json' },
        body: payload ? JSON.stringify(payload) : undefined,
      });
      let json = null;
      try {
        json = await response.json();
      } catch {
        json = null;
      }
      return { status: response.status, json };
    },
    method,
    path,
    body ?? null,
  );
}

/** Every printed timeline row, in the order the page shows them. */
function printedRows(page) {
  return page.$$eval('.timeline__row', (rows) =>
    rows.map((row) => {
      const cells = [...row.children].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim());
      const [clock, event, tags] = cells;
      // The clock cell reads `12' · 1-0` for a goal and `12'` for everything else.
      const [minute, score] = String(clock).split('·').map((part) => part.trim());
      return {
        minute: Number(String(minute).replace(/[^0-9]/g, '')),
        score: score ?? '',
        event: String(event),
        tags: String(tags),
      };
    }),
  );
}

/** The number a printed chip carries, found by the words that follow it. */
function chipNumber(page, suffix) {
  const needle = squeeze(suffix).toLowerCase();
  return page.evaluate(
    (want) => {
      const chip = [...document.querySelectorAll('.chip')].find((node) => node.innerText.replace(/\s+/g, '').toLowerCase().endsWith(want));
      if (!chip) return null;
      const match = /([\d,.]+)/.exec(chip.innerText);
      return match ? Number(match[1].replace(/,/g, '')) : null;
    },
    needle,
  );
}

/** The per-type chips the panel prints, as a map the API's own `by_type` can be held against. */
function typeChips(page) {
  return page.$$eval('.timeline-provenance .chip, [data-testid="timeline-provenance"] .chip', (nodes) => {
    const found = {};
    for (const node of nodes) {
      const match = /^([a-z_]+)\s+([\d,]+)$/i.exec(node.innerText.replace(/\s+/g, ' ').trim());
      if (match) found[match[1].toLowerCase()] = Number(match[2].replace(/,/g, ''));
    }
    return found;
  });
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });

  const page = await browser.newPage();
  await page.setCookie({ name: 'fo_locale', value: 'en', url: BASE });
  await page.setViewport(DESKTOP);
  watch(page, 'owner');
  await open(page, '/login');
  const registered = await call(page, 'POST', '/api/v1/auth/register', {
    email: EMAIL,
    password: PASSWORD,
    display_name: 'Timeline QA',
    role: 'player',
    accepts_data_policy: true,
  });
  check('a fresh account registers through the cookie proxy', registered.status === 201, `HTTP ${registered.status}`);

  // --- the API the page is built from ---------------------------------------------------------------
  const options = await call(page, 'GET', '/api/v1/simulate/options');
  const teams = options.json?.teams ?? [];
  check('the simulator offers the generated world', teams.length >= 20 && teams[0]?.data_origin === 'synthetic', `${teams.length} clubs`);
  // A fixture the model never scores in would let every goal-specific check below pass by checking
  // nothing, so the walk plays until one goes in — the same reason the pytest fixture tries a seed range.
  let played = null;
  let goalsSeen = 0;
  const attempts = [];
  for (const seed of [20260925, 20260936, 20260947, 20260958, 20260969, 20260970, 20260981, 20260992]) {
    played = await call(page, 'POST', '/api/v1/simulate', { home_team: teams[0].team_id, away_team: teams[3].team_id, seed });
    goalsSeen = ((played.json?.report ?? {}).events ?? []).filter((event) => event.type === 'goal').length;
    if (goalsSeen > 0) break;
    attempts.push(`${seed}: ${((played.json?.report ?? {}).events ?? []).length} events, no goal`);
  }
  check('a fixture plays and comes back with a timeline that has a goal in it', played?.status === 201 && Boolean(played.json?.timeline) && goalsSeen > 0, attempts.join(' | ') || `HTTP ${played?.status}`);
  const report = played.json?.report ?? {};
  const timeline = played.json?.timeline ?? {};
  const events = report.events ?? [];
  check('the fixture produced events to store', events.length > 0, `${events.length} events`);
  check('one row was written per event the report printed', timeline.stored_rows === events.length && timeline.stored_rows > 0, `${timeline.stored_rows} rows for ${events.length} events`);
  check('the timeline says it came from the table, not the blob', timeline.source === 'sim_events rows', JSON.stringify(timeline.source));
  // Values, not serialisation order: `event_dict` writes a row's keys in its own order and the engine
  // writes its event keys in the engine's, and the backend's equality test — like this one — is on values.
  const mismatch = (timeline.events ?? []).reduce((found, event, index) => {
    if (found) return found;
    const onReport = events[index] ?? {};
    for (const key of new Set([...Object.keys(event), ...Object.keys(onReport)])) {
      if (JSON.stringify(event[key]) !== JSON.stringify(onReport[key])) return `event ${index} (${onReport.type}), ${key}: ${JSON.stringify(event[key])} against ${JSON.stringify(onReport[key])}`;
    }
    return '';
  }, '');
  check('the stored events hold the report’s values, key by key', mismatch === '' && (timeline.events ?? []).length === events.length, mismatch || `${events.length} events, ${Object.keys(events[0] ?? {}).length} keys each`);
  check('re-reading them agrees with the report', /all of them agree with the report/.test(String(timeline.consistency)), String(timeline.consistency).slice(0, 120));
  check('the count, the rows and the report events are one number', timeline.count === timeline.stored_rows && timeline.stored_rows === timeline.report_events, `${timeline.count}/${timeline.stored_rows}/${timeline.report_events}`);
  const goals = events.filter((event) => event.type === 'goal').length;
  const typed = Object.values(timeline.by_type ?? {}).reduce((total, value) => total + value, 0);
  check('the per-type split adds up to the whole timeline', typed === events.length && (timeline.by_type?.goal ?? 0) === goals, `${typed} across ${Object.keys(timeline.by_type ?? {}).length} types, ${goals} goals`);
  check('a name that resolves to a player is counted as one', timeline.identified === events.length && (timeline.ambiguous_names ?? []).length === 0, `${timeline.identified} of ${events.length} traced`);
  check('the table publishes how it was built and how far a name reaches', Boolean(timeline.formula) && /ordinal/.test(String(timeline.formula)) && /selected player/.test(String(timeline.attribution_formula)), String(timeline.attribution_formula).slice(0, 90));
  check('and it is labelled as what it is', /fictional/i.test(String(timeline.disclaimer)) && timeline.data_origin === 'simulation' && timeline.is_demo_data === true, timeline.data_origin);

  const list = await call(page, 'GET', '/api/v1/simulate');
  const row = (list.json?.items ?? []).find((item) => item.id === played.json?.id);
  check('a list row carries neither report nor timeline', Boolean(row) && row.report === undefined && row.timeline === undefined, JSON.stringify(Object.keys(row ?? {})).slice(0, 140));

  // --- the page a manager reads ---------------------------------------------------------------------
  const path = `/simulate/${encodeURIComponent(played.json.slug)}`;
  const shown = await open(page, path);
  check('the report page answers', shown.status() === 200, `${path} → HTTP ${shown.status()}`);
  const body = await text(page);
  check('the timeline panel says where its events came from', shouts(body, 'read from sim_events rows'), body.split('\n').find((line) => /READ FROM/i.test(line)));
  check('and prints the row count it read', (await chipNumber(page, 'stored rows')) === events.length, `${await chipNumber(page, 'stored rows')} stored rows`);
  const rows = await printedRows(page);
  check('every stored event is a printed row, in the report order', rows.length === events.length && rows.every((entry, index) => entry.minute === events[index].minute), `${rows.length} rows, first minute ${rows[0]?.minute}`);
  check('a printed goal carries the scoreline the model stamped', rows.filter((entry) => entry.score).length === goals, `${goals} goals in the report`);
  const firstGoal = events.findIndex((event) => event.type === 'goal');
  check('and it is the same scoreline, on the same minute', rows[firstGoal]?.score === events[firstGoal]?.score, `${rows[firstGoal]?.score} against ${events[firstGoal]?.score}`);
  const chips = await typeChips(page);
  check('the per-type chips are the server’s split, not a recount', Object.keys(chips).length === Object.keys(timeline.by_type ?? {}).length && Object.entries(chips).every(([type, count]) => timeline.by_type[type] === count), JSON.stringify(chips));
  check('the traced-player figure is the one the API returned', (await chipNumber(page, 'traced to a player')) === timeline.identified, `${await chipNumber(page, 'traced to a player')}`);
  check('the page prints the agreement sentence it was given', has(squeeze(body), squeeze(timeline.consistency)), String(timeline.consistency).slice(0, 90));
  check('and the attribution rule beside it', has(squeeze(body), squeeze(timeline.attribution_formula)), String(timeline.attribution_formula).slice(0, 90));
  check('no ambiguity warning is printed when nothing was ambiguous', !has(squeeze(body), squeeze('belong to two players')), (timeline.ambiguous_names ?? []).length === 0 ? 'none to warn about' : JSON.stringify(timeline.ambiguous_names));
  check('the report still shows the events it always showed', has(squeeze(body), squeeze(events[events.length - 1].detail)), String(events[events.length - 1].detail).slice(0, 70));
  await shot(page, 'report-desktop');

  const index = await open(page, '/simulate');
  const indexBody = await text(page);
  // The index has long carried a chip that begins with the words "stored rows", so the needle here is the
  // detail panel's own figure: a number of rows belongs to one match, and a list row has no timeline to count.
  check('the simulator index answers and claims no per-match timeline', index.status() === 200 && !/\d+\s*stored\s*rows/i.test(squeeze(indexBody).replace(/storedrows/g, 'stored rows')), `HTTP ${index.status()}`);

  // --- a season page's own match: the career path writes rows through the same call ------------------
  // Not walked here: this account has no career, and `test_a_career_round_gets_a_timeline_the_same_way`
  // pins that path in the suite. A check that could only ever report "nothing to open" is a red to
  // explain rather than a fact to learn, so the assertion lives where the fixture can be built.

  await page.setViewport(MOBILE);
  await open(page, path);
  const narrow = await text(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check('the timeline survives a phone viewport without sideways scroll', overflow <= 1 && shouts(narrow, 'stored rows'), `${overflow}px overflow`);
  await shot(page, 'report-mobile');

  check('no console error was provoked anywhere in the walk', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));

  await browser.close();
  finish();
}

function finish() {
  const failed = results.filter((entry) => !entry.ok);
  console.log(`\n${results.length - failed.length}/${results.length} walk checks passed`);
  for (const entry of failed) console.log(`  FAIL  ${entry.name} — ${entry.detail}`);
  console.log(`screenshots: ${shots.join(', ')}`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((error) => {
  console.log(`WALK CRASHED: ${error?.stack ?? error}`);
  // A walk that died halfway must not report the checks it managed to run as the whole story: the checks before
  // the crash are all green and `finish()` would exit 0 on them alone.
  check('the walk ran through to its last check', false, String(error?.message ?? error).slice(0, 160));
  finish();
});
