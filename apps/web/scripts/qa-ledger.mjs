/**
 * The season-ledger walk: a browser against a **production build**, checking that the career page prints
 * the per-player counts the API derives from `sim_events`, and that those counts agree with a third
 * reading the walk itself makes — the stored report of each fixture this career played.
 *
 *   api tier:  http://127.0.0.1:8736        (uvicorn app.main:app --port 8736)
 *   web tier:  http://127.0.0.1:3216        (API_INTERNAL_URL=http://127.0.0.1:8736 next start -p 3216)
 *   QA_BASE=http://127.0.0.1:3216 node scripts/qa-ledger.mjs
 *
 * Three readings of one season, on purpose. The page's numbers come from the `ledger` block; the block is
 * a `GROUP BY` over `sim_events`; and the walk re-counts the stored report of every fixture this career
 * played, keeping only the side that belongs to the career's club — once by event type, and once again per
 * name so that a printed row can be held against the reports of that same player. If the ledger counted
 * the away side too, or lost a round, or grouped a name the rows never attributed, the third reading is the
 * one that notices — which is the whole reason the panel publishes `scope`, `source` and a `consistency`
 * sentence rather than a bare table of numbers.
 *
 * What this walk does not prove, and does not claim: a season in which two players of one club share a
 * name, and a career whose report was deleted after it was played. Both branches — the `ambiguous` share
 * and the gap-vs-disagreement sentence — need a fixture built to order, which a walk against a live world
 * cannot arrange; they are pinned in the API test suite instead.
 *
 * Three mutations were planted in `ledger.py` to check that this walk's green means something. Dropping the
 * club-side filter from the totals query turned five checks red, including the disagreement sentence the
 * panel then prints. Dropping one chance type from a row's attempts while leaving the club total alone
 * turned exactly one red — the per-name reading, which is the only one that can see it. Cutting the list at
 * 4 names instead of 40 was caught too, by the season-wide identity as it was first written; that catch was
 * the discovery, not the prize, because a cut the panel labels in its own eyebrow and its own sentence is
 * the cap working rather than failing, and the identity has since been written so it stays quiet on an
 * honest cut. A cap small enough to bite is pinned where the number itself can be read, not here.
 *
 * Env overrides: QA_BASE, CHROME_PATH.
 */

import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import puppeteer from 'puppeteer-core';

const BASE = process.env.QA_BASE ?? 'http://127.0.0.1:3216';
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1 };
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };
const PASSWORD = 'ledger-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const EMAIL = `ledger-qa-${stamp}@footballos.test`;

/** The event types the ledger counts as an attempt, mirroring `_CHANCE_TYPES` in `ledger.py`. */
const CHANCE = ['goal', 'shot_saved', 'shot_off_target'];
/** The six types the panel gives a row, mirroring `_LEDGER_TYPES`; its totals count every club-side event. */
const LEDGER_TYPES = [...CHANCE, 'yellow_card', 'red_card', 'injury'];
/** The panel's own column order, mirrored from `LEDGER_COLUMNS` in `lib/ledger.ts`. */
const COLUMNS = ['matches_with_events', 'goals', 'attempts', 'expected_goals', 'yellow_cards', 'red_cards', 'injuries'];
const PANEL_TITLE = 'counted off the event rows';

const results = [];
const consoleErrors = [];
const shots = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail: String(detail) });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${String(detail).slice(0, 190)}` : ''}`);
}

const has = (body, needle) => String(body).includes(String(needle));
const squeeze = (value) => String(value).replace(/\s+/g, '');
/** Eyebrows and table headers are upper-cased in CSS, so `innerText` never holds the written needle. */
const shouts = (body, needle) => squeeze(body).toUpperCase().includes(squeeze(needle).toUpperCase());

async function shot(page, name) {
  const file = `${stamp}-ledger-${name}.png`;
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

/** The ledger panel's own DOM subtree, found by the title it is the only panel to carry. */
function panelRoot(page) {
  return page.evaluate((needle) => {
    const panel = [...document.querySelectorAll('section.panel')].find((node) => node.innerText.includes(needle));
    if (!panel) return null;
    const header = panel.querySelector('.panel__head');
    return {
      eyebrow: header?.querySelector('.eyebrow')?.innerText.replace(/\s+/g, ' ').trim() ?? '',
      text: panel.innerText.replace(/\r/g, ''),
      kv: [...panel.querySelectorAll('.world-kv__row')].map((row) => ({
        // `dt`, `th` and `.eyebrow` are upper-cased in CSS and `innerText` reflects that, so every label
        // this walk reads is lower-cased before it is compared with the string the API actually sent.
        key: (row.querySelector('dt')?.innerText.trim() ?? '').toLowerCase(),
        value: row.querySelector('dd')?.innerText.replace(/\s+/g, ' ').trim() ?? '',
      })),
      rows: [...panel.querySelectorAll('table tbody tr')].map((row) =>
        [...row.children].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim()),
      ),
      headers: [...panel.querySelectorAll('table thead th')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim().toLowerCase()),
    };
  }, PANEL_TITLE);
}

/** Count one fixture's report events again, keeping only the side the career's club played on. */
function countReport(events, clubSide) {
  const mine = events.filter((event) => event.side === clubSide);
  const attempts = mine.filter((event) => CHANCE.includes(event.type));
  return {
    events: mine.length,
    goals: mine.filter((event) => event.type === 'goal').length,
    attempts: attempts.length,
    expected_goals: attempts.reduce((total, event) => total + Number(event.expected_goals ?? 0), 0),
    yellow_cards: mine.filter((event) => event.type === 'yellow_card').length,
    red_cards: mine.filter((event) => event.type === 'red_card').length,
    injuries: mine.filter((event) => event.type === 'injury').length,
    by_type: mine.reduce((found, event) => ({ ...found, [event.type]: (found[event.type] ?? 0) + 1 }), {}),
  };
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
    display_name: 'Ledger QA',
    role: 'player',
    accepts_data_policy: true,
  });
  check('a fresh account registers through the cookie proxy', registered.status === 201, `HTTP ${registered.status}`);

  // --- the career the ledger is drawn over ---------------------------------------------------------
  const options = await call(page, 'GET', '/api/v1/careers/options');
  const clubs = options.json?.clubs ?? [];
  const kinds = Object.keys(options.json?.objective_kinds ?? {});
  check('the career API offers the generated world and the objectives it judges', clubs.length >= 20 && kinds.length > 0, `${clubs.length} clubs, kinds ${kinds.join('/')}`);
  // The strongest club, for the same reason §20's fixture is not built on the weakest: a side that never
  // puts the ball in the net gives a ledger whose goal-specific checks each pass by measuring nothing.
  const club = clubs.reduce((best, row) => (row.overall > (best?.overall ?? -1) ? row : best), null);
  const opened = await call(page, 'POST', '/api/v1/careers', {
    club: club.slug,
    manager_name: 'Ledger QA',
    philosophy: 'balanced',
    budget: 5_000_000,
    objectives: [{ kind: kinds[0], target: 3 }],
  });
  const slug = opened.json?.career?.slug ?? '';
  check('a career opens at a club that can score', opened.status === 200 && Boolean(slug), `HTTP ${opened.status} at ${club.name} (overall ${club.overall})`);
  const empty = (await call(page, 'GET', `/api/v1/careers/${slug}`)).json ?? {};
  const emptyLedger = empty.ledger ?? {};
  check('before a round is played the ledger says there is nothing to sum', emptyLedger.fixtures_played === 0 && emptyLedger.totals?.events === 0 && /sum over no rows/.test(String(emptyLedger.consistency)), String(emptyLedger.consistency).slice(0, 110));

  let detail = empty;
  const refusals = [];
  for (let round = 0; round < 8; round += 1) {
    const response = await call(page, 'POST', `/api/v1/careers/${slug}/play`);
    if (response.status !== 200 || !response.json?.played) {
      refusals.push(`round ${round + 1}: HTTP ${response.status} ${JSON.stringify(response.json?.detail ?? '')}`.slice(0, 120));
      break;
    }
    detail = response.json;
    if ((detail.ledger?.totals?.goals ?? 0) > 0) break;
  }
  const ledger = detail.ledger ?? {};
  const fixtures = detail.fixtures ?? [];
  const players = ledger.players ?? [];
  const goalsOnRows = players.reduce((total, entry) => total + entry.goals, 0);
  check('the rounds played leave at least one goal event on this club’s rows', (ledger.totals?.goals ?? 0) > 0, refusals.join(' | ') || `${fixtures.length} round(s), ${ledger.totals?.goals ?? 0} goal(s) on the rows`);
  check('the ledger covers the season the fixture list shows', fixtures.length > 0 && ledger.fixtures_played === fixtures.length && ledger.fixtures_traced + ledger.fixtures_untraced === ledger.fixtures_played, `${ledger.fixtures_traced} traced of ${ledger.fixtures_played} played, ${ledger.fixtures_untraced} without rows`);

  // --- the third reading: the stored report of every fixture, counted again here --------------------
  const seen = { events: 0, goals: 0, attempts: 0, expected_goals: 0, yellow_cards: 0, red_cards: 0, injuries: 0, by_type: {} };
  /** The same reports counted a second way: per name, so a printed row can be held against its own name. */
  const byName = {};
  const skipped = [];
  for (const fixture of fixtures) {
    if (!fixture.match_still_stored || !fixture.match_slug) {
      skipped.push(`round ${fixture.round_index} (report gone)`);
      continue;
    }
    const match = await call(page, 'GET', `/api/v1/simulate/${encodeURIComponent(fixture.match_slug)}`);
    const events = (match.json?.report ?? {}).events ?? [];
    if (match.status !== 200 || events.length === 0) {
      skipped.push(`round ${fixture.round_index} (HTTP ${match.status}, ${events.length} events)`);
      continue;
    }
    const counts = countReport(events, fixture.side);
    for (const key of ['events', 'goals', 'attempts', 'yellow_cards', 'red_cards', 'injuries']) seen[key] += counts[key];
    seen.expected_goals += counts.expected_goals;
    for (const [type, count] of Object.entries(counts.by_type)) seen.by_type[type] = (seen.by_type[type] ?? 0) + count;
    for (const event of events) {
      if (event.side !== fixture.side || !LEDGER_TYPES.includes(event.type) || !event.player) continue;
      const row = (byName[event.player] ??= { matches: new Set(), goals: 0, attempts: 0, yellow_cards: 0, red_cards: 0, injuries: 0 });
      row.matches.add(fixture.round_index);
      if (event.type === 'goal') row.goals += 1;
      if (CHANCE.includes(event.type)) row.attempts += 1;
      if (event.type === 'yellow_card') row.yellow_cards += 1;
      if (event.type === 'red_card') row.red_cards += 1;
      if (event.type === 'injury') row.injuries += 1;
    }
  }
  check('every round this walk needed has a stored report behind it', skipped.length === 0, skipped.join(', ') || `${fixtures.length} fixture(s) read back`);
  const typeMismatch = ['events', 'goals', 'attempts', 'yellow_cards', 'red_cards', 'injuries'].find(
    (key) => seen[key] !== (ledger.totals?.[key] ?? -1),
  );
  check('the panel’s totals are the reports re-counted, type by type', typeMismatch === undefined, typeMismatch ? `${typeMismatch}: ${seen[typeMismatch]} on the reports against ${ledger.totals?.[typeMismatch]} in the ledger` : `${seen.events} club-side events, ${seen.goals} goals, ${seen.attempts} attempts`);
  check('the xG the ledger sums is the reports’ xG, to the thousandth it prints', Math.abs(seen.expected_goals - (ledger.totals?.expected_goals ?? -1)) <= 0.0015, `${seen.expected_goals.toFixed(6)} counted against ${(ledger.totals?.expected_goals ?? 0).toFixed(3)} published`);
  const splitMismatch = Object.keys(seen.by_type).find((type) => (seen.by_type[type] ?? 0) !== (ledger.by_type?.[type]?.events ?? 0));
  check('the per-type split matches too, not only the six headline figures', splitMismatch === undefined && Object.keys(ledger.by_type ?? {}).length === Object.keys(seen.by_type).length, splitMismatch ? `${splitMismatch}: ${seen.by_type[splitMismatch]} against ${ledger.by_type?.[splitMismatch]?.events}` : `${Object.keys(seen.by_type).length} type(s) on both readings`);
  check('a goal the club printed is either named in the rows or counted as unattributed, never both', goalsOnRows === (ledger.by_type?.goal?.identified ?? -1) && goalsOnRows <= (ledger.totals?.goals ?? 0), `${goalsOnRows} of ${ledger.totals?.goals} goal(s) carry a player_id, ${ledger.by_type?.goal?.ambiguous ?? 0} ambiguous and ${ledger.by_type?.goal?.unnamed ?? 0} naming nobody`);

  // --- the arithmetic the panel leans on -------------------------------------------------------------
  const eventsOnRows = players.reduce((total, entry) => total + Object.values(entry.events_by_type).reduce((a, b) => a + b, 0), 0);
  const unattributed = (ledger.unattributed?.events?.ambiguous ?? 0) + (ledger.unattributed?.events?.unnamed ?? 0);
  const identified = Object.values(ledger.by_type ?? {}).reduce((total, entry) => total + (entry.identified ?? 0), 0);
  const offLedger = Object.entries(ledger.by_type ?? {})
    .filter(([type]) => !LEDGER_TYPES.includes(type))
    .reduce((total, [, entry]) => total + (entry.identified ?? 0), 0);
  check('every club-side event is either given to a name or published as unattributed', identified + unattributed === (ledger.totals?.events ?? -1), `${identified} attributed + ${unattributed} without = ${ledger.totals?.events} for the club`);
  // Cut short at 40 names is the design working, not a defect: the panel says so in its own eyebrow and in
  // the cut sentence. So the whole-season identity is only claimed over the printed rows when nothing was
  // cut; when something was, what has to hold is that the count of rows is the count it claims.
  const identity = ledger.truncated ? players.length === ledger.players_shown && eventsOnRows <= identified : eventsOnRows + offLedger === identified && players.length === ledger.players_with_events;
  check('the table’s cells add up to the attributed rows, and an honest cut is labelled as one', identity, `${eventsOnRows} on the printed types + ${offLedger} on the types it does not row = ${identified} attributed over ${ledger.players_with_events} name(s), ${players.length} shown`);
  // Per name, the recount reaches past the cap: a row the panel prints must match the reports for that
  // same name, whether or not the season has more names below the cut.
  const ambiguous = new Set(ledger.unattributed?.ambiguous_names ?? []);
  const rowMismatch = players.reduce((found, entry) => {
    if (found) return found;
    if (ambiguous.has(entry.name)) return `${entry.name} is printed as a row although the rows call that name ambiguous`;
    const recount = byName[entry.name] ?? { matches: new Set(), goals: 0, attempts: 0, expected_goals: 0, yellow_cards: 0, red_cards: 0, injuries: 0 };
    const want = {
      matches_with_events: recount.matches.size,
      goals: recount.goals,
      attempts: recount.attempts,
      yellow_cards: recount.yellow_cards,
      red_cards: recount.red_cards,
      injuries: recount.injuries,
    };
    const key = Object.keys(want).find((stat) => want[stat] !== entry[stat]);
    return key ? `${entry.name} · ${key}: the row says ${entry[key]}, the reports of the same name say ${want[key]}` : '';
  }, '');
  check('each printed name’s row is what this club’s reports say about that name', rowMismatch === '' && players.length > 0, rowMismatch || `${players.length} name(s) held against the reports, ${ambiguous.size} ambiguous name(s) none of them is`);
  check('a printed name’s matches never exceed the rounds the ledger traced', players.every((entry) => entry.matches_with_events <= ledger.fixtures_traced), `most ${Math.max(0, ...players.map((entry) => entry.matches_with_events))} of ${ledger.fixtures_traced} traced`);
  check('the list is capped honestly, or not at all', ledger.truncated === (players.length < (ledger.players_with_events ?? 0)) && ledger.players_shown === players.length && players.length <= 40, `${players.length} shown of ${ledger.players_with_events}, truncated ${ledger.truncated}`);
  check('the panel says whose side it counted', /only/.test(String(ledger.scope)) && String(ledger.scope).includes(ledger.club?.short ?? '—'), String(ledger.scope).slice(0, 110));
  check('and how it built each figure', /grouped by/i.test(String(ledger.formula)) && /club_goals/.test(String(ledger.consistency_formula)) && /exactly one/.test(String(ledger.attribution_formula)), String(ledger.attribution_formula).slice(0, 90));
  const listGoals = fixtures.filter((f) => f.match_still_stored).reduce((total, f) => total + f.club_goals, 0);
  check('the fixture-list reading and the event-row reading are set beside each other', ledger.club_goals_traced === listGoals && (ledger.totals?.goals ?? -1) === listGoals && /agree/.test(String(ledger.consistency)), `${listGoals} on the fixture list, ${ledger.totals?.goals} on the rows — ${String(ledger.consistency).slice(-46)}`);
  check('a round whose report is gone is called a gap, not a zero', ledger.fixtures_untraced === 0 || ledger.consistency.includes(String(ledger.fixtures_untraced)), `${ledger.fixtures_untraced} untraced — ${String(ledger.consistency).slice(-70)}`);
  check('it is labelled as what it is', /fictional/i.test(String(ledger.disclaimer)) && ledger.data_origin === 'simulation' && ledger.is_demo_data === true, ledger.data_origin);

  const again = (await call(page, 'GET', `/api/v1/careers/${slug}`)).json ?? {};
  check('reading the ledger twice gives the same answer', JSON.stringify(again.ledger) === JSON.stringify(ledger), `${ledger.totals?.events} events, ${players.length} name(s) both times`);

  // --- the page a manager reads ---------------------------------------------------------------------
  const path = `/career/${encodeURIComponent(slug)}`;
  const shown = await open(page, path);
  check('the season page answers', shown.status() === 200, `${path} → HTTP ${shown.status()}`);
  const panel = await panelRoot(page);
  check('the ledger panel is on the page, and it is the only one', Boolean(panel), panel ? 'found' : `no panel carrying “${PANEL_TITLE}”`);
  const body = await text(page);
  const wantEyebrow = `${ledger.players_shown} of ${ledger.players_with_events} name(s) · ${ledger.fixtures_traced} of ${ledger.fixtures_played} round(s) traced`;
  check('its eyebrow is the server’s two counts of names', squeeze(panel?.eyebrow).toUpperCase() === squeeze(wantEyebrow).toUpperCase(), panel?.eyebrow);
  const kv = Object.fromEntries((panel?.kv ?? []).map((row) => [row.key, row.value]));
  check('the club’s goals, attempts and xG on the page are the totals it was given', kv['goals / attempts / xg for the club'] === `${ledger.totals?.goals} · ${ledger.totals?.attempts} · ${(ledger.totals?.expected_goals ?? 0).toFixed(3)}`, kv['goals / attempts / xg for the club']);
  check('and so are the cards and injuries', kv['booked / sent off / injured'] === `${ledger.totals?.yellow_cards} · ${ledger.totals?.red_cards} · ${ledger.totals?.injuries}`, kv['booked / sent off / injured']);
  const wantUnattributed = unattributed
    ? `${unattributed} (${ledger.unattributed.events.ambiguous} ambiguous, ${ledger.unattributed.events.unnamed} naming nobody) — ${ledger.unattributed.ambiguous_names.join(', ') || 'no repeated name'}`
    : 'none: every event the club printed found exactly one player';
  check('the events with no player behind the name are the server’s share, not an omission', kv['events with no player behind the name'] === wantUnattributed, kv['events with no player behind the name']);
  check('the reach of the count is printed in the server’s own words', kv['how far the count reaches'] === ledger.scope, String(kv['how far the count reaches']).slice(0, 90));
  check('the table’s headers are the seven published columns, in order', (panel?.headers ?? []).join('|') === 'player|position|matches|goals|attempts|xg|yellow|red|injury', (panel?.headers ?? []).join('|'));
  const cellMismatch = (panel?.rows ?? []).reduce((found, row, index) => {
    if (found) return found;
    const entry = players[index];
    if (!entry) return `the page printed row ${index + 1} with no ledger entry behind it`;
    if (row[0] !== entry.name) return `row ${index + 1} name: ${row[0]} against ${entry.name}`;
    for (let column = 0; column < COLUMNS.length; column += 1) {
      const key = COLUMNS[column];
      const want = key === 'expected_goals' ? entry[key].toFixed(3) : String(entry[key]);
      if (row[column + 2] !== want) return `${entry.name} · ${key}: ${row[column + 2]} against ${want}`;
    }
    return '';
  }, panel?.rows.length === players.length ? '' : `${panel?.rows.length} printed row(s) against ${players.length} ledger row(s)`);
  check('every printed player row is the server’s row, in the server’s order, cell by cell', cellMismatch === '', cellMismatch || `${players.length} name(s), top is ${players[0]?.name} with ${players[0]?.goals} goal(s)`);
  check('the top row really is the top name the rows give', players.length > 0 && Math.max(...players.map((entry) => entry.goals)) === players[0].goals, `${players[0]?.name} ${players[0]?.goals}, highest ${Math.max(0, ...players.map((entry) => entry.goals))}`);
  check('the agreement sentence is the one the API wrote', has(squeeze(body), squeeze(ledger.consistency)), String(ledger.consistency).slice(0, 90));
  check('and the three formulas beside it', [ledger.formula, ledger.consistency_formula, ledger.attribution_formula].every((line) => has(squeeze(body), squeeze(line))), String(ledger.formula).slice(0, 70));
  check('the cut-at-40 sentence appears only when the list really was cut', has(squeeze(body), squeeze('The list is cut at')) === Boolean(ledger.truncated), `${players.length} of ${ledger.players_with_events} shown, truncated=${ledger.truncated}`);
  check('a name the rows could not attribute is never given a row', (ledger.unattributed?.unnamed_names ?? []).every((name) => !(panel?.rows ?? []).some((row) => row[0] === name)), (ledger.unattributed?.unnamed_names ?? []).slice(0, 3).join(', ') || 'nothing unnamed on this season');
  await shot(page, 'season-desktop');

  const index = await open(page, '/career');
  const indexBody = await text(page);
  // The list view is built with `include_fixtures=false`, so it carries no ledger and must claim none.
  check('the careers index answers and claims no per-season ledger', index.status() === 200 && !has(squeeze(indexBody), squeeze(PANEL_TITLE)), `HTTP ${index.status()}`);

  await page.setViewport(MOBILE);
  await open(page, path);
  const narrowPanel = await panelRoot(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check('the ledger table stays inside a phone viewport', overflow <= 1 && Boolean(narrowPanel), `${overflow}px overflow, ${narrowPanel?.rows.length ?? 0} row(s)`);
  await shot(page, 'season-mobile');

  check('no console error was provoked anywhere in the walk', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));

  await browser.close();
  finish();
}

function finish() {
  const failed = results.filter((entry) => !entry.ok);
  console.log(`\n${results.length - failed.length}/${results.length} walk checks passed`);
  for (const entry of failed) console.log(`  FAIL  ${entry.name} — ${entry.detail}`);
  console.log(`screenshots: ${shots.join(', ')}`);
  // A run that checked nothing is not green: `0/0` would otherwise exit 0, which is how a walk that never
  // reached a single check can read as a pass.
  process.exit(failed.length || results.length === 0 ? 1 : 0);
}

main().catch((error) => {
  console.log(`WALK CRASHED: ${error?.stack ?? error}`);
  // A walk that died halfway must not report the checks it managed to run as the whole story: an earlier
  // crash here printed “10/10 walk checks passed” and exited 0.
  check('the walk ran through to its last check', false, String(error?.message ?? error).slice(0, 160));
  finish();
});
