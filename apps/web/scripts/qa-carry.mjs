/**
 * The §20 carry-over walk: a browser against a **production build**, playing rounds through the
 * season page's own button and reading the load those rounds left behind.
 *
 *   api tier:  http://127.0.0.1:8734        (uvicorn app.main:app --port 8734)
 *   web tier:  http://127.0.0.1:3214        (API_INTERNAL_URL=… next start -p 3214)
 *   QA_BASE=http://127.0.0.1:3214 node scripts/qa-carry.mjs
 *
 * What this refuses to do is take the panel's word for its own arithmetic. The four figures the
 * condition formula publishes (fatigue depth, the window's capacity, the reserve and the load that
 * completes it) are scraped out of the sentence the page prints, and every condition figure in the
 * load table is re-derived from them and from the row's own load. A page whose table agrees with a
 * formula the walk did not read from the code is a page that is doing what it says.
 *
 * Env overrides: QA_BASE, CHROME_PATH.
 */

import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import puppeteer from 'puppeteer-core';

const BASE = process.env.QA_BASE ?? 'http://127.0.0.1:3214';
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1 };
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };
const PASSWORD = 'carry-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const EMAIL = `carry-qa-${stamp}@footballos.test`;

const results = [];
const consoleErrors = [];
const shots = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${String(detail).slice(0, 190)}` : ''}`);
}

const has = (body, needle) => String(body).includes(String(needle));
const squeeze = (value) => String(value).replace(/\s+/g, '');
/**
 * Eyebrows and table headers are upper-cased in CSS, and `innerText` reports what is painted rather than
 * what was written, so a needle that has to match one of those is compared with the case taken out.
 */
const shouts = (body, needle) => squeeze(body).toUpperCase().includes(squeeze(needle).toUpperCase());

async function shot(page, name) {
  const file = `${stamp}-carry-${name}.png`;
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

async function until(page, needle, timeout = 60_000) {
  try {
    await page.waitForFunction((want) => (document.body?.innerText ?? '').includes(want), { timeout, polling: 400 }, needle);
    return true;
  } catch {
    return false;
  }
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

async function gridValue(page, label) {
  return page.evaluate(
    (want) => {
      // `dt` is upper-cased by the stylesheet, so the label has to be matched with its case taken out.
      const cell = [...document.querySelectorAll('.kv-grid dt, .kv dt, dt')].find((node) => node.innerText.trim().toUpperCase().startsWith(want.toUpperCase()));
      const value = cell?.nextElementSibling?.innerText ?? '';
      return value.replace(/\s+/g, ' ').trim();
    },
    label,
  );
}

/** The load table as printed: one row per player the career has traced, in the page's column order. */
function loadRows(page) {
  return page.$$eval('table tbody tr', (rows) =>
    rows
      .map((row) => [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim()))
      .filter((cells) => cells.length === 7)
      .map((cells) => ({
        player: cells[0],
        position: cells[1],
        rounds: Number(cells[2]),
        // The minutes column carries its unit after the figure ("90 match minutes"), so the walk reads the
        // figure off the front and keeps the unit as a separate fact rather than a parse failure.
        minutes: Number(cells[3].match(/^[\d.]+/)?.[0]),
        minutesUnit: cells[3].replace(/^[\d.]+\s*/, ''),
        load: Number(cells[4]),
        training: Number(cells[5]),
        condition: Number(cells[6]),
        atFloor: cells[6].includes('floor'),
      })),
  );
}

/** The first number after a phrase, read out of the sentence the page itself prints. */
function figure(body, phrase, offset) {
  const match = new RegExp(`${phrase}[^\\d]*([\\d.]+)`).exec(body);
  if (!match) return Number.NaN;
  return Number(match[1]) + (offset ?? 0);
}

/**
 * Press the page's own button and wait for two signals in order: the round line the response renders,
 * then the sentence only a **server re-render** produces. `router.refresh()` lands *after* the response,
 * so scraping at the first signal reads the pre-round panels — and "the table shows load" is a different
 * claim from "the table says it shows load", which is the whole thing this walk is checking.
 */
async function playRound(page, round) {
  const clicked = await page.evaluate(() => {
    const button = [...document.querySelectorAll('button')].find((node) => node.innerText.includes('Play the next round'));
    if (!button || button.disabled) return 'unavailable';
    button.click();
    return 'clicked';
  });
  if (clicked !== 'clicked') return false;
  const announced = await until(page, `Round ${round} played:`, 120_000);
  const refreshed = await until(page, `Next up: round ${round + 1}`, 60_000);
  return announced && refreshed;
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });

  const page = await browser.newPage();
  await page.setViewport(DESKTOP);
  watch(page, 'owner');
  await open(page, '/login');
  const registered = await call(page, 'POST', '/api/v1/auth/register', {
    email: EMAIL,
    password: PASSWORD,
    display_name: 'Carry QA',
    role: 'player',
    accepts_data_policy: true,
  });
  check('a fresh account registers through the cookie proxy', registered.status === 201, `HTTP ${registered.status}`);

  const options = await call(page, 'GET', '/api/v1/careers/options');
  // `options` publishes no competition field on a club row, so the walk cannot tell which clubs have
  // fixtures to play. It asks the career view instead, working up from the weakest club until one reports
  // a scheduled round — and it stays under the per-user career cap while doing so.
  const clubs = (options.json?.clubs ?? []).slice().sort((a, b) => a.overall - b.overall || String(a.slug).localeCompare(String(b.slug)));
  check('the clubs on offer are the generated world’s', clubs.length > 0 && clubs[0]?.data_origin === 'synthetic', `${clubs.length} clubs, cheapest ${clubs[0]?.overall}`);
  const budget = options.json?.budget_ceiling ?? 10_000_000;
  const cap = options.json?.max_careers_per_user ?? 5;
  check('the ceiling the options publish is a number a career can be opened with', Number.isFinite(budget) && budget > 0, `${budget.toLocaleString('en-GB')} ${options.json?.budget_units ?? 'credits'}`);

  let slug = null;
  let view0 = null;
  const stalled = [];
  for (const club of clubs.slice(0, Math.max(1, cap - 1))) {
    const created = await call(page, 'POST', '/api/v1/careers', {
      club: club.slug,
      manager_name: `Carry QA ${stamp.slice(-4)}`,
      philosophy: 'balanced',
      budget,
      objectives: [{ kind: 'wins', target: 1, label: 'win once' }],
    });
    if (created.status !== 200) {
      stalled.push(`${club.slug}: HTTP ${created.status} ${JSON.stringify(created.json)?.slice(0, 80)}`);
      continue;
    }
    const read = await call(page, 'GET', `/api/v1/careers/${encodeURIComponent(created.json.career.slug)}`);
    if (!read.json?.next_fixture?.available) {
      stalled.push(`${club.slug}: ${read.json?.next_fixture?.reason ?? 'the view scheduled no round'}`);
      continue;
    }
    slug = created.json.career.slug;
    view0 = read.json;
    break;
  }
  check('a career opens at a club whose competition can supply a round', Boolean(slug), stalled.join(' | ') || clubs[0]?.slug);
  const path = `/career/${encodeURIComponent(slug)}`;

  const carry0 = view0.carry_over;
  check('the career read returns a carry-over block before any round is played', carry0 && carry0.appearances === 0, JSON.stringify(carry0?.rounds_played ?? null));
  check('a career with no rounds reports no window and no trace', carry0?.rounds_traced === 0 && carry0?.carrying_load === 0 && carry0?.last_traced_round === 0, `next round ${carry0?.next_round}`);

  await open(page, path);
  const before = await text(page);
  check('the season page prints the load panel from the first visit', has(before, 'What the played rounds left on the players'));
  check('with nothing played it says so instead of showing an empty table', has(before, 'No load to carry yet'));
  check('the empty state still publishes the form rule it will apply', has(squeeze(before), squeeze(carry0.form_formula)), String(carry0.form_formula).slice(0, 70));
  check('rounds played and rounds traced are printed as a pair', has(before, '0 / 0'), await gridValue(page, 'Rounds played'));
  const meta = await page.evaluate(() => document.querySelector('meta[name="robots"]')?.content ?? '');
  check('the season page is noindex and nofollow', /noindex/.test(meta) && /nofollow/.test(meta), meta || '(no meta robots)');
  await shot(page, 'before-any-round');

  // --- round 1: the first trace, and the condition figures it will be read against ------------------
  check('round 1 plays from the page’s own button', await playRound(page, 1));
  const one = await text(page);
  const after1 = (await call(page, 'GET', `/api/v1/careers/${encodeURIComponent(slug)}`)).json?.carry_over;
  check('one played round leaves eleven trace rows', after1.appearances === 11 && after1.players_traced === 11, `${after1.appearances} rows, ${after1.players_traced} players`);
  check('the panel counts the round it just played', has(one, '1 / 1'), await gridValue(page, 'Rounds played'));
  check('the eleven that played comes into round 2 carrying load', after1.carrying_load === 11, `${after1.carrying_load} players carry load into round ${after1.next_round}`);
  check('the eyebrow says which round the load is measured for', shouts(one, 'carry load into round 2'), one.split('\n').find((line) => line.toUpperCase().includes('CARRY LOAD INTO')));
  check('nothing is reported as a hole when every round left a trace', after1.untraced_rounds.length === 0 && !has(one, 'left no trace at all'), JSON.stringify(after1.untraced_rounds));

  const depth = figure(one, 'condition = 1 −');
  const window = figure(one, 'load_units ÷');
  const reserve = figure(one, 'training_reserve =');
  const reserveLoad = figure(one, 'real_training_sessions ÷');
  const floor = figure(one, 'clipped to');
  check('the four figures the arithmetic needs are printed on the page', [depth, window, reserve, reserveLoad, floor].every((value) => Number.isFinite(value) && value > 0), `depth ${depth} · window ${window} · reserve ${reserve}/${reserveLoad} · floor ${floor}`);
  check('the window is the decayed three matches the load formula describes', Math.abs(window - 90 * (1 + 0.5 + 0.25)) < 0.001, `${window} load units`);

  const rows1 = await loadRows(page);
  // Every check below carries the row count in its own condition: a scrape that found nothing would make
  // `every(...)` true over an empty list, and a silent zero is how a broken table passes for an honest one.
  check('the load table holds one row per traced player of the eleven', rows1.length === 11, `${rows1.length} rows`);
  check('every traced player carries exactly one match of minutes', rows1.length === 11 && rows1.every((row) => row.minutes === 90 && row.rounds === 1), rows1.map((row) => `${row.player}:${row.minutes}`).slice(0, 3).join(' '));
  check('the minutes column labels itself with the unit the API publishes, not one the page invented', rows1.length === 11 && rows1.every((row) => row.minutesUnit === after1.rows[after1.rows.length - 1].minutes_units), rows1[0]?.minutesUnit ?? 'no rows');
  check('the load figures are ranked from most to least', rows1.length === 11 && rows1.every((row, index) => index === 0 || rows1[index - 1].load >= row.load), rows1.map((row) => row.load).join(' '));
  const derived1 = rows1.map((row) => Math.min(1, Math.max(floor, 1 - depth * (row.load / window) + reserve * Math.min(1, row.training / reserveLoad))));
  check('each printed condition is what the printed formula gives for the printed load', rows1.length === 11 && rows1.every((row, index) => Math.abs(row.condition - derived1[index]) < 0.001), rows1.map((row, index) => `${row.condition} vs ${derived1[index].toFixed(4)}`).slice(0, 3).join(' '));
  check('the mean condition of the last eleven is the table’s own mean', derived1.length === 11 && Math.abs(after1.mean_condition_of_last_xi - derived1.reduce((a, b) => a + b, 0) / derived1.length) < 0.001, `${after1.mean_condition_of_last_xi}`);
  check('nobody is at the floor after a single match', rows1.length === 11 && rows1.every((row) => !row.atFloor), rows1[0] ? `${rows1[0].player} at ${rows1[0].condition}` : 'no rows');
  await shot(page, 'after-one-round');

  // --- round 2: the decay arrives, and the report says so on the side that carries it ---------------
  check('round 2 plays from the page’s own button', await playRound(page, 2));
  const two = await text(page);
  const view2 = (await call(page, 'GET', `/api/v1/careers/${encodeURIComponent(slug)}`)).json;
  const after2 = view2?.carry_over;
  check('two played rounds leave twenty-two trace rows for eleven players', after2.appearances === 22 && after2.players_traced === 11, `${after2.appearances} rows`);
  const rows2 = await loadRows(page);
  check('the same eleven carry a window of two rounds', rows2.length === 11 && rows2.every((row) => row.rounds === 2), rows2.map((row) => row.rounds).join(' '));
  check('the older round still counts, at half its weight', rows2.length === 11 && rows2.every((row) => Math.abs(row.load - 135) < 0.001), rows2.map((row) => row.load).slice(0, 4).join(' '));
  const derived2 = rows2.map((row) => Math.min(1, Math.max(floor, 1 - depth * (row.load / window) + reserve * Math.min(1, row.training / reserveLoad))));
  check('condition falls as the window fills', rows2.length === 11 && derived1.length === 11 && rows2.every((row, index) => Math.abs(row.condition - derived2[index]) < 0.001) && derived2[0] < derived1[0], `${derived1[0]?.toFixed(4)} → ${rows2[0]?.condition}`);
  check('the panel prints the trace rows it is summing', has(two, '2 / 2'), await gridValue(page, 'Rounds played'));
  await shot(page, 'after-two-rounds');

  // --- the match report carries the two factors the load produced -----------------------------------
  const fixture = view2?.fixtures?.at(-1);
  check('the played round links to a report', Boolean(fixture?.match_path), JSON.stringify(fixture?.match_path ?? null));
  const report = await open(page, fixture.match_path);
  check('the round’s own report page answers', report.status() === 200, `${fixture.match_path} → HTTP ${report.status()}`);
  const printed = await text(page);
  check('the report prints the condition index of the side that carried load', has(printed, 'Condition index'), printed.split('\n').find((line) => line.includes('Condition index')));
  check('and the count of selected players the trace reached', has(printed, 'Selected players with a trace'), printed.split('\n').find((line) => line.includes('Selected players with a trace')));
  check('the report’s condition sentence is the same expression the season page printed', has(squeeze(printed), squeeze(after2.condition_formula)), String(after2.condition_formula).slice(0, 70));
  check('the load sentence names the decayed window it summed', has(squeeze(printed), squeeze(after2.load_formula)), String(after2.load_formula).slice(0, 70));
  await shot(page, 'match-report');

  // --- the honest limits, on the page and in the viewport a manager actually uses --------------------
  const season = await open(page, path);
  check('the season page still answers after the rounds', season.status() === 200, `HTTP ${season.status()}`);
  const full = await text(page);
  check('the panel carries the §20 limit in its own words', has(full, 'What does not carry is growth'), full.split('\n').find((line) => line.includes('does not carry')));
  check('and says a club nobody manages is untouched', has(full, 'a club nobody manages has no trace'));
  check('the condition disclaimer is printed beside the figures', has(full, String(after2.disclaimer).slice(0, 40)), String(after2.disclaimer).slice(0, 60));
  check('the page prints the fixture re-check the server computed', has(squeeze(full), squeeze(view2.consistency)), view2.consistency);

  await page.setViewport(MOBILE);
  await open(page, path);
  const narrow = await text(page);
  const narrowRows = await loadRows(page);
  check('the load table survives a phone viewport', narrowRows.length === 11 && shouts(narrow, 'Load units'), `${narrowRows.length} rows, headers ${shouts(narrow, 'Load units') ? 'printed' : 'missing'}`);
  await shot(page, 'mobile');

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
  finish();
});
