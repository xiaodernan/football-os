/**
 * The M8 web walk: a browser against a **production build**, opening a tenant from the page's own
 * form, putting a child on a sheet, being refused a plan for that child, answering for them, and
 * then reading the progress arithmetic back off the plan page and re-deriving it from the reviews
 * the page itself printed.
 *
 *   api tier:  http://127.0.0.1:8734        (uvicorn app.main:app --port 8734)
 *   web tier:  http://127.0.0.1:3214        (API_INTERNAL_URL=… next start -p 3214)
 *   QA_BASE=http://127.0.0.1:3214 node scripts/qa-club.mjs
 *
 * Three things make this walk different from a screenshot pass.
 *
 * It knocks on the doors a stranger knocks on: `/club` with no session, another tenant's address
 * with a session of their own, and a signed-out `/club/rules`. §39's claim is that those three
 * answers differ for the right reasons, and a page that collapses them — 404 painted as 403, an
 * empty table standing in for a refused read — breaks the claim in the tier the user actually reads.
 * The walk therefore compares each academy door's HTTP status with whether the page printed a
 * refusal, which is the same claim stated in two languages.
 *
 * It drives the page's own controls rather than posting JSON from the walk, so a button that never
 * fires, a select that offers nobody, or a refresh that never re-reads fails here instead of
 * passing beside a green API test as a dead form.
 *
 * And it refuses the page's arithmetic on its own terms: `overall_first / overall_last /
 * overall_change` are re-derived from the review table as printed, choosing the column by the
 * formula the API publishes; each axis change from that axis' two printed cells; the date figures
 * from the printed dates; the withheld count from the note rows. A figure that agrees with nothing
 * on screen cannot pass.
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
const PASSWORD = 'club-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const OWNER = `club-owner-${stamp}@footballos.test`;
const INVITEE = `club-invitee-${stamp}@footballos.test`;
const STRANGER = `club-stranger-${stamp}@footballos.test`;
const TENANT = `QA Riverside ${stamp.slice(-6)}`;
const TEAM = `U16 QA ${stamp.slice(-4)}`;

const results = [];
const consoleErrors = [];
const shots = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail: String(detail) });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${String(detail).slice(0, 190)}` : ''}`);
}

const has = (body, needle) => String(body).includes(String(needle));
const squeeze = (value) => String(value).replace(/\s+/g, '');
/** Eyebrows and `dt` labels are upper-cased in CSS, so a needle matched against one sheds its case. */
const shouts = (body, needle) => squeeze(body).toUpperCase().includes(squeeze(needle).toUpperCase());

async function shot(page, name) {
  const file = `${stamp}-club-${name}.png`;
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

/** Wait for a painted string. Case and runs of whitespace are ignored: eyebrows shout. */
async function until(page, needle, timeout = 60_000) {
  const want = squeeze(needle).toUpperCase();
  try {
    await page.waitForFunction(
      (target) => (document.body?.innerText ?? '').replace(/\s+/g, '').toUpperCase().includes(target),
      { timeout, polling: 400 },
      want,
    );
    return true;
  } catch {
    return false;
  }
}

/** Poll the note a page's own write is supposed to paint, so a stale note cannot answer for a later call. */
async function waitNote(page, action, needle, timeout = 45_000) {
  const sel = `[data-note="${action}"]`;
  await page
    .waitForFunction(
      ([s, target]) => {
        const node = document.querySelector(s);
        return node ? node.innerText.replace(/\s+/g, '').toUpperCase().includes(target) : false;
      },
      { timeout, polling: 300 },
      [sel, squeeze(needle).toUpperCase()],
    )
    .catch(() => null);
  return page.$eval(sel, (node) => node.innerText.replace(/\s+/g, ' ').trim()).catch(() => '(no note painted)');
}

/** Poll an out-of-page predicate — used for a re-read the refresh has to land first. */
async function untilTrue(read, timeout = 60_000) {
  const deadline = Date.now() + timeout;
  let last = null;
  while (Date.now() < deadline) {
    last = await read();
    if (last === true) return true;
    await new Promise((done) => setTimeout(done, 600));
  }
  void last;
  return false;
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

/** Real keystrokes: React only sees a value that arrived through an input event. */
async function typeInto(page, selector, value) {
  await page.waitForSelector(selector, { visible: true, timeout: 20_000 });
  await page.click(selector);
  if (value) await page.type(selector, String(value), { delay: 8 });
}

async function clearField(page, selector) {
  await page.waitForSelector(selector, { visible: true, timeout: 20_000 });
  await page.click(selector, { clickCount: 3 });
  await page.keyboard.press('Backspace');
}

function press(page, testid) {
  return page.evaluate((sel) => {
    const button = document.querySelector(sel);
    if (!button) return 'missing';
    if (button.disabled) return 'disabled';
    button.click();
    return 'clicked';
  }, selectorOf(testid));
}

const selectorOf = (testid) => (testid.startsWith('[') ? testid : `[data-testid="${testid}"]`);

/** The `[data-*]` rows of a table, with the column tooltips kept as a separate fact. */
function rowsOf(page, attribute) {
  return page.$$eval(`tr[data-${attribute}]`, (rows, name) =>
    rows.map((row) => ({
      key: row.getAttribute(`data-${name}`),
      cells: [...row.querySelectorAll('td')].map((cell) => ({
        text: cell.innerText.replace(/\s+/g, ' ').trim(),
        title: cell.getAttribute('title') ?? '',
      })),
    })),
    attribute,
  );
}

/** Wait for a table to paint its rows before reading it: the walk polled the door, and the page's own
 *  re-read lands on its own clock, so a row that exists server-side may not be on screen yet. */
async function waitRows(page, attribute, timeout = 45_000) {
  await page.waitForSelector(`tr[data-${attribute}]`, { timeout, visible: true }).catch(() => null);
  return rowsOf(page, attribute);
}

function attributeValues(page, selector, attribute) {
  return page.$$eval(selector, (nodes, name) => nodes.map((node) => node.getAttribute(name) ?? ''), attribute);
}

/** Register through the cookie proxy, waiting out the limiter rather than reporting it as a defect. */
async function register(page, email, displayName, role) {
  let last = null;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    last = await call(page, 'POST', '/api/v1/auth/register', { email, password: PASSWORD, display_name: displayName, role, accepts_data_policy: true });
    if (last.status !== 429) return last;
    await new Promise((done) => setTimeout(done, 25_000));
  }
  return last;
}

function metaRobots(page) {
  return page.evaluate(() => document.querySelector('meta[name="robots"]')?.content ?? '');
}

/** The `dd` beside the `dt` whose text begins with `label`, upper-cased in CSS so matched case-free. */
function kvValue(page, label) {
  return page.evaluate(
    (want) => {
      const cell = [...document.querySelectorAll('dt')].find((node) => node.innerText.trim().toUpperCase().startsWith(want.toUpperCase()));
      return (cell?.nextElementSibling?.innerText ?? '').replace(/\s+/g, ' ').trim();
    },
    label,
  );
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });

  // ----------------------------------------------------------- a stranger, with no cookie at all
  const rulesDoor = await fetch(`${BASE}/api/v1/club/capabilities`, { headers: { accept: 'application/json' } });
  const clubRules = rulesDoor.ok ? await rulesDoor.json() : null;
  check('the §39 capabilities door answers a caller with no session', rulesDoor.status === 200 && clubRules?.ready === true, `HTTP ${rulesDoor.status}`);
  const eduDoor = await (await fetch(`${BASE}/api/v1/club/academy/capabilities`, { headers: { accept: 'application/json' } })).json();
  check('the §40 door answers the same way and names the same threshold', eduDoor?.minor_age === 18 && eduDoor?.ready === true, `minor_age ${eduDoor?.minor_age}`);
  const anonymousList = await fetch(`${BASE}/api/v1/club`, { headers: { accept: 'application/json' } });
  check('but a stranger may not read a tenant list', anonymousList.status === 401, `HTTP ${anonymousList.status}`);

  const robots = await (await fetch(`${BASE}/robots.txt`)).text();
  check('robots.txt keeps /club out of the index', /^\s*Disallow:\s*\/club\s*$/m.test(robots), (robots.match(/^(Disallow|Allow):.*$/gm) ?? []).join(' | '));
  check('and lets the one public club page in beside it', /^\s*Allow:\s*\/club\/rules\s*$/m.test(robots), (robots.match(/^Allow:.*$/gm) ?? []).join(' | '));

  const sitemap = await (await fetch(`${BASE}/sitemap.xml`)).text();
  const clubUrls = sitemap.match(/<loc>[^<]*\/club[^<]*<\/loc>/g) ?? [];
  check('the sitemap advertises /club/rules', clubUrls.some((entry) => /\/club\/rules<\/loc>/.test(entry)), clubUrls.join(' '));
  check('and no private club address', clubUrls.every((entry) => /\/club\/rules<\/loc>/.test(entry)), `${clubUrls.length} club entries`);

  // ----------------------------------------------------------- the owner's browser
  const page = await browser.newPage();
  await page.setViewport(DESKTOP);
  watch(page, 'owner');

  const gone = await page.goto(`${BASE}/club`, { waitUntil: 'domcontentloaded' });
  const landed = new URL(page.url());
  check('signed-out /club is a redirect to sign-in that names where you were going', landed.pathname === '/login' && landed.search.includes('%2Fclub'), `${gone.status()} -> ${landed.pathname}${landed.search}`);
  check('signed-out /club/rules answers 200 instead of redirecting', (await open(page, '/club/rules')).status() === 200);
  const rulesBody = await text(page);
  const indexable = await metaRobots(page);
  check('the rulebook page carries no noindex', !/noindex/.test(indexable), indexable || '(no robots meta)');
  check('the rulebook prints both doors side by side', has(rulesBody, 'Club and academy rulebook'));
  const clubCodes = await attributeValues(page, 'tr[data-club-refusal]', 'data-club-refusal');
  const eduCodes = await attributeValues(page, 'tr[data-academy-refusal]', 'data-academy-refusal');
  const published = Object.keys(clubRules.refusal_answers ?? {});
  const eduPublished = Object.keys(eduDoor.refusal_answers ?? {});
  const shared = eduDoor.refusals_shared_with_club_tier ?? [];
  check('every §39 refusal code the door publishes is on the page', clubCodes.length === published.length && published.every((code) => clubCodes.includes(code)), `${clubCodes.length} printed of ${published.length} published`);
  check('§40 is printed without the codes §39 already answers for', eduCodes.length === eduPublished.length - shared.length && eduCodes.every((code) => !shared.includes(code)), `${eduCodes.length} printed, ${eduPublished.length} published, ${shared.length} shared`);
  check('and each printed code keeps its own status beside it', (await rowsOf(page, 'club-refusal')).every((row) => String(clubRules.refusal_answers[row.key]) === row.cells[1]?.text), JSON.stringify((await rowsOf(page, 'club-refusal')).slice(0, 2).map((row) => `${row.key}=${row.cells[1]?.text}`)));
  const stored = await attributeValues(page, 'tr[data-table]', 'data-table');
  const columns = Object.values(eduDoor.stored_fields ?? {}).reduce((sum, list) => sum + list.length, 0);
  check('the minimisation table is the column list itself, not a description of it', stored.length === Object.keys(eduDoor.stored_fields ?? {}).length && stored.every((table) => Object.keys(eduDoor.stored_fields).includes(table)), `${stored.length} tables, ${columns} columns`);
  check('it spells out every column of the note table', has(rulesBody, (eduDoor.stored_fields?.coach_feedback ?? ['§§']).join(', ')), (eduDoor.stored_fields?.coach_feedback ?? []).length + ' columns listed');
  const neverPrinted = await attributeValues(page, 'li[data-never]', 'data-never');
  check('the never-stored list is printed item by item, in the API’s own words', neverPrinted.length === (eduDoor.never_stored ?? []).length && (eduDoor.never_stored ?? []).every((line) => neverPrinted.includes(line)), `${neverPrinted.length} of ${(eduDoor.never_stored ?? []).length} fields`);
  check('the door lines both counts and the ready flag', shouts(rulesBody, `curricula ${eduDoor.counts?.curricula ?? '?'} · plans ${eduDoor.counts?.plans ?? '?'}`) || shouts(rulesBody, 'ready'), JSON.stringify(eduDoor.counts ?? null).slice(0, 90));
  await shot(page, 'rulebook-signed-out');

  // ----------------------------------------------------------- register and read the index
  await open(page, '/login');
  const registered = await register(page, OWNER, 'Club QA Owner', 'coach');
  check('an owner registers through the cookie proxy', registered.status === 201, `HTTP ${registered.status} ${JSON.stringify(registered.json ?? null).slice(0, 80)}`);

  await open(page, '/club');
  const indexRobots = await metaRobots(page);
  check('the club index is noindex and nofollow', /noindex/.test(indexRobots) && /nofollow/.test(indexRobots), indexRobots || '(none)');
  const owned0 = await call(page, 'GET', '/api/v1/club');
  const body0 = await text(page);
  check('a brand-new account stands in no organisation', owned0.status === 200 && owned0.json?.total === 0 && owned0.json?.items?.length === 0, `total ${owned0.json?.total}`);
  check('the index prints the seat arithmetic the list door reported', shouts(body0, `${owned0.json.total} of ${owned0.json.limit} used · ${owned0.json.room_left} seat(s) left`), `${owned0.json.total}/${owned0.json.limit} used, ${owned0.json.room_left} left`);
  check('the rulebook panel counts what the capabilities door counts', shouts(body0, `${clubRules.matrix.roles.length} standings · ${clubRules.matrix.permissions.length} rights · ${clubRules.routes.length} published`), `${clubRules.matrix.roles.length} standings, ${clubRules.matrix.permissions.length} rights, ${clubRules.routes.length} doors`);
  check('an empty index says so in its own sentence, and prints the door’s rule beside it', shouts(body0, 'You stand in no organisation yet') && has(squeeze(body0), squeeze(owned0.json.rule)), String(owned0.json.rule ?? '(no rule)').slice(0, 70));
  check('an empty name cannot be submitted: the button stays inert until the field has text', (await page.$eval('[data-testid="club-create"]', (node) => node.disabled)) === true, 'the guard is on the blank name only, not on a guessed role');

  // ----------------------------------------------------------- open a tenant from the form
  await typeInto(page, 'input[aria-label="Organisation name"]', TENANT);
  check('filling the name arms the button', (await page.$eval('[data-testid="club-create"]', (node) => !node.disabled)) === true);
  check('pressing the page’s own button opens the tenant', (await press(page, 'club-create')) === 'clicked');
  const createNote = await waitNote(page, 'create', 'answered 200');
  check('the note reports the status the API answered, and disclaims its own body', has(createNote, 'answered 200') && has(squeeze(createNote), squeeze('re-read from the server')), createNote.slice(0, 140));
  const owned1 = await call(page, 'GET', '/api/v1/club');
  const tenant = (owned1.json?.items ?? []).find((row) => row.name === TENANT);
  check('the seat line moved by exactly one after the refresh', owned1.json?.total === 1 && owned1.json.room_left === owned0.json.room_left - 1, `${owned0.json.room_left} -> ${owned1.json.room_left}`);
  check('the tenant appears in Where you stand at the path the API gave it', Boolean(tenant?.path), tenant?.path);
  const rowHref = await page.waitForSelector(`tr[data-organization="${tenant.slug}"] a.world-link`, { timeout: 45_000 }).then((node) => node.evaluate((el) => el.getAttribute('href'))).catch(() => null);
  const listedBody = await text(page);
  check('the standing the grant says they hold is printed on the row, linking at the path the API gave it', rowHref === tenant.path && shouts(listedBody, '1 listed') && has(listedBody, owned1.json.items[0].role), `href ${rowHref} · ${JSON.stringify(owned1.json.items[0] ?? null).slice(0, 90)}`);
  await shot(page, 'index-after-create');

  const ident = tenant.path.split('/')[2];
  check('the tenant page opens at the published path', (await open(page, tenant.path)).status() === 200, tenant.path);
  const view0 = await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`);
  const c0 = view0.json.counts;
  const tbody = await text(page);
  check('its counts panel agrees with the view door line by line', shouts(tbody, `${c0.active_members} active member(s) · ${c0.owners} owner(s) · ${c0.teams} of ${view0.json.rules.max_teams_per_organization} sheets · ${c0.players_on_sheets} squad rows`), JSON.stringify(c0));
  check('the head says what the caller may do, in the door’s own numbers', shouts(tbody, `${view0.json.my_grant.permissions.length} of ${clubRules.matrix.permissions.length} rights`), `${view0.json.my_grant.permissions.length} rights as ${view0.json.my_grant.role}`);
  check('and prints the API’s reason rather than a paraphrase of it', has(squeeze(tbody), squeeze(view0.json.my_grant.why)), String(view0.json.my_grant.why).slice(0, 60));
  check('the isolation sentence is printed rather than paraphrased', has(squeeze(tbody), squeeze(view0.json.isolation_rule)), String(view0.json.isolation_rule).slice(0, 60));
  check('the integrity notice says clean over the rows it names', has(tbody, 'Integrity check: clean') && Object.entries(view0.json.integrity.checked).every(([figure, value]) => has(tbody, `${value} ${figure}`)), JSON.stringify(view0.json.integrity.checked));
  check('an empty sheet set counts zero minors', (await kvValue(page, 'Members under 18 on a sheet')) === '0', await kvValue(page, 'Members under 18 on a sheet'));
  const consents0 = await call(page, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/consents`);
  check('and the consent door reports no child under the threshold', consents0.status === 200 && consents0.json?.under_18 === 0, `under_18 ${consents0.json?.under_18}`);

  // ----------------------------------------------------------- a sheet, then a child on it
  await typeInto(page, 'input[aria-label="Team name"]', TEAM);
  await typeInto(page, 'input[aria-label="Age group"]', 'U16');
  await typeInto(page, 'input[aria-label="Stage"]', 'development');
  check('a team sheet is created from the page', (await press(page, 'team-create')) === 'clicked' && (await untilTrue(async () => (await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).json?.counts?.teams === 1)));
  const withTeam = await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`);
  const team = (withTeam.json.teams ?? []).find((row) => row.name === TEAM);
  check('the view counts the sheet the page just wrote', withTeam.json.counts.teams === 1 && team?.squad_size === 0, `${withTeam.json.counts.teams} sheet, ${team?.squad_size} rows`);
  check('and the sheet reports the room it has left', team?.room_left === withTeam.json.rules.max_squad_per_team, `room_left ${team?.room_left} of ${withTeam.json.rules.max_squad_per_team}`);
  await page.reload({ waitUntil: 'networkidle2' });
  check('the page re-reads the sheet after the refresh', shouts(await text(page), TEAM), TEAM);

  const youngest = await call(page, 'GET', '/api/v1/world/players?sort=age&order=asc&page_size=60');
  const child = (youngest.json?.items ?? []).find((row) => Number(row.age) < eduDoor.minor_age);
  check('the generated world has a minor to put on a sheet', Boolean(child), `${youngest.json?.items?.length} rows read, youngest age ${youngest.json?.items?.[0]?.age}`);
  check('that player is not yet on the sheet', (withTeam.json.teams ?? []).every((row) => row.squad.every((squad) => squad.slug !== child.slug)), child.slug);
  await typeInto(page, `input[aria-label="Player for ${TEAM}"]`, child.slug);
  check('the roster control takes the world’s own slug', (await press(page, '[data-act="squad-add"]')) === 'clicked' && (await untilTrue(async () => (await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).json?.counts?.players_on_sheets === 1)));
  const withChild = await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`);
  const sheet = (withChild.json.teams ?? []).find((row) => row.name === TEAM);
  check('the sheet now holds one squad row and one minor', sheet?.squad_size === 1 && sheet?.minors_on_sheet === 1, `squad ${sheet?.squad_size}, minors ${sheet?.minors_on_sheet}`);
  check('the child on the sheet keeps the world’s own age', sheet?.squad?.[0]?.age === Number(child.age) && Number(child.age) < eduDoor.minor_age, `stored ${sheet?.squad?.[0]?.age}, world ${child.age}`);
  await page.reload({ waitUntil: 'networkidle2' });
  const rosterBody = await text(page);
  check('the page counts minors from the sheets into its own grid', (await kvValue(page, 'Members under 18 on a sheet')) === '1', await kvValue(page, 'Members under 18 on a sheet'));
  const squadCells = await page.$$eval(`tr[data-player="${child.slug}"]`, (rows) => {
    const row = rows[0];
    return row ? [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim()) : [];
  });
  const minorCell = squadCells.find((cell) => /minor/i.test(cell)) ?? '';
  check('and the roster row marks the child as a minor, with the world’s own age beside it', /minor/i.test(minorCell) && minorCell.replace(/[^0-9]/g, '') === String(child.age), minorCell || `no minor chip among ${squadCells.slice(0, 4).join(' | ')}`);
  check('the roster row links to the world’s own page for that player, at its own path', (await page.$eval(`tr[data-player="${child.slug}"] a`, (node) => node.getAttribute('href'))) === sheet.squad[0].path, sheet.squad[0].path);
  check('the seat arithmetic in the panel moved with the write', shouts(rosterBody, `${withChild.json.counts.players_on_sheets} squad rows`), `${withChild.json.counts.players_on_sheets} squad rows`);
  await shot(page, 'tenant-with-child');

  // ----------------------------------------------------------- §40's order: the refusal comes first
  check('the plan-open button is armed by the child on the sheet', (await page.$eval('[data-testid="plan-open"]', (node) => !node.disabled)) === true);
  const planNote = (await press(page, 'plan-open')) === 'clicked' ? await waitNote(page, 'plan', 'was refused with') : '(the button did not take the press)';
  check('opening a plan for a minor is refused before anybody has answered for them', /was refused with 4\d\d/.test(planNote) && has(planNote, 'consent_required'), planNote.slice(0, 150));
  const refusalBody = await text(page);
  check('and the page prints the refusal as a refusal, with its code', has(refusalBody, 'consent_required'), (refusalBody.split('\n').find((line) => /consent_required/.test(line)) ?? '(code not printed)').slice(0, 150));
  check('the refusal carries the figures the API sent beside the sentence', /minor_age \d+|player \S+/.test(refusalBody), (refusalBody.match(/(minor_age|player|teams) \S+/g) ?? ['(no figure printed)']).join(' · '));
  check('the plans table still holds nothing: a refusal is not a write', (await rowsOf(page, 'plan')).length === 0 && (await call(page, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`)).json?.total === 0);

  // ----------------------------------------- a guardian answers: the scoped right, witnessed from two browsers
  const guardianContext = await browser.createBrowserContext();
  const pageB = await guardianContext.newPage();
  await pageB.setViewport(DESKTOP);
  watch(pageB, 'parent');
  await open(pageB, '/login');
  const registerB = await register(pageB, INVITEE, 'Club QA Parent', 'fan');
  check('a second account registers in its own browser context', registerB.status === 201, `HTTP ${registerB.status} ${JSON.stringify(registerB.json ?? null).slice(0, 80)}`);
  const preInvite = await pageB.goto(`${BASE}${tenant.path}`, { waitUntil: 'domcontentloaded' });
  check('an account standing nowhere is answered 404 by another tenant’s page, never 403', preInvite.status() === 404 && !shouts(await text(pageB), 'forbidden'), `HTTP ${preInvite.status()}`);
  check('and by the door behind it', (await call(pageB, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).status === 404, 'page and door give the same answer');

  await open(page, tenant.path);
  const roles = await page.$$eval('select[aria-label="Invited role"] option', (nodes) => nodes.map((node) => node.value));
  await typeInto(page, 'input[aria-label="Invite email"]', INVITEE);
  await page.select('select[aria-label="Invited role"]', 'parent');
  check('the invite form offers every standing the matrix publishes', roles.join(',') === clubRules.matrix.roles.join(','), roles.join(', '));
  check('an owner can address an invitation to a real account', (await press(page, 'club-invite')) === 'clicked' && (await untilTrue(async () => (await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).json?.counts?.invited_members === 1)));
  const invited = await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`);
  check('the invited row waits, and is counted as invited rather than active', invited.json.counts.invited_members === 1 && invited.json.counts.active_members === 1, `invited ${invited.json.counts.invited_members}, active ${invited.json.counts.active_members}`);
  check('and the invitee cannot read the tenant yet: an unanswered row grants nothing', (await call(pageB, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).status === 404, 'the door answers 404 until they answer it');

  await open(pageB, '/club');
  check('the invitation appears on the invitee’s own index', shouts(await text(pageB), 'Invitations addressed to you') && has(await text(pageB), TENANT), TENANT);
  check('accepting it from their own page is what makes them a member', (await press(pageB, '[data-act="accept"]')) === 'clicked' && (await untilTrue(async () => (await call(pageB, 'GET', '/api/v1/club')).json?.items?.length === 1)));
  const invitesAfter = await call(pageB, 'GET', '/api/v1/club/invitations');
  check('the answered row leaves the invitation door: it is consumed, not stacked', invitesAfter.status === 200 && invitesAfter.json?.total === 0, `${invitesAfter.json?.total} outstanding`);
  await open(pageB, '/club');
  const answeredBody = await text(pageB);
  check('and leaves their page too: no Accept button survives an answered row', !has(answeredBody, 'Accept') && shouts(answeredBody, '1 listed'), `${has(answeredBody, 'Accept') ? 'Accept still printed' : 'no Accept'} / ${shouts(answeredBody, '1 listed') ? '1 listed' : 'list count wrong'}`);

  const grantNote = (await press(page, 'consent-grant')) === 'clicked' ? await waitNote(page, 'grant', 'refused with') : '(the button did not take the press)';
  check('the tenant’s own director may not mint the guardian’s yes', /refused with 4\d\d/.test(grantNote) && has(grantNote, 'insufficient_role'), grantNote.slice(0, 150));
  const coachRefusal = await text(page);
  check('and the refusal names the standing the right is scoped to', has(coachRefusal, 'insufficient_role') && /required_role\D*parent/.test(coachRefusal), (coachRefusal.match(/(insufficient_role|required_role \S+).*/) ?? ['(no code printed)'])[0].slice(0, 130));
  check('the director’s refusal is not a write: no consent row appeared', (await call(page, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/consents`)).json?.total === 0, 'the plans table stays gated by a yes nobody gave');

  check('as a member the tenant page opens for them', (await open(pageB, tenant.path)).status() === 200 && shouts(await text(pageB), TENANT));
  const scopesToGrant = eduDoor.consent_scopes.default_granted;
  const offeredScopes = await attributeValues(pageB, '[data-scope]', 'data-scope');
  check('the consent form offers exactly the purposes the door publishes', offeredScopes.length === (eduDoor.consent_scopes.scopes ?? []).length && eduDoor.consent_scopes.scopes.every((scope) => offeredScopes.includes(scope)), offeredScopes.join(', '));
  check('and it arrives pre-ticked with the default grant, not with everything', (await pageB.$$eval('[data-scope] input', (nodes) => nodes.filter((node) => node.checked).map((node) => node.value))).join(',') === scopesToGrant.join(','), `default: ${scopesToGrant.join(', ')}`);
  check('the child selector offers only the players on this tenant’s sheets', (await pageB.$$eval('select[aria-label="Child"] option', (nodes) => nodes.map((node) => node.value))).join(',') === child.slug, child.slug);
  check('a parent’s yes writes the row that gates their own child', (await press(pageB, 'consent-grant')) === 'clicked' && (await untilTrue(async () => (await call(pageB, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/consents`)).json?.total === 1)));
  const consents1 = await call(pageB, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/consents`);
  const consentRow = (consents1.json?.items ?? []).find((row) => row.player.slug === child.slug);
  check('the row is a grant, for the child, with the purposes agreed', consentRow?.state === 'granted' && consentRow?.scopes?.length === scopesToGrant.length, `${consentRow?.state} · ${(consentRow?.scopes ?? []).join(', ')}`);
  check('and it records which account answered, because a claim with no claimant is not a record', consentRow?.guardian?.email === INVITEE, JSON.stringify(consentRow?.guardian ?? null));
  const consentKeys = Object.keys(consentRow ?? {});
  check('and nothing outside the consent table could have been stored', consentKeys.every((key) => ['granted_at', 'guardian', 'id', 'plans_for_this_child', 'player', 'scopes', 'state', 'updated_at'].includes(key)), consentKeys.join(', '));
  const consentPainted = await waitRows(pageB, 'consent');
  check('the consent row is on screen, with the child named and no other column', consentPainted.length === 1 && has(await text(pageB), child.name), consentPainted[0]?.cells.map((cell) => cell.text).join(' | ') ?? '(no consent row painted)');
  check('the door says who it read the list as', has(squeeze(await text(pageB)), squeeze(consents1.json.rule)) || has(await text(pageB), consents1.json.seen_as), `seen_as ${consents1.json.seen_as}`);


  // ----------------------------------------------------------- the plan, and its published path
  check('the same button opens the plan once somebody has answered for the child', (await press(page, 'plan-open')) === 'clicked' && (await untilTrue(async () => (await call(page, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`)).json?.total === 1)));
  const plans1 = await call(page, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`);
  const plan = plans1.json.items[0];
  check('the plans table gains the row the door reports', plan?.assessments === 0 && plans1.json.total === 1, `${plans1.json.total} plan(s), ${plan?.assessments} reviews`);
  check('and counts the child under the published threshold', plans1.json.minors_in_list === 1 && plan.player.is_minor === true, `minors_in_list ${plans1.json.minors_in_list}`);
  const planRows = await waitRows(page, 'plan');
  check('the new row reads its own progress as "not yet", not as zero', planRows[0]?.cells[6]?.text === 'not yet' && plan.progress === null, `progress cell: ${planRows[0]?.cells[6]?.text}`);
  check('with the reason in that cell’s title, not in a footnote', has(planRows[0]?.cells[6]?.title ?? '', 'one review or none'), planRows[0]?.cells[6]?.title);
  check('the row links to the path the API publishes', (await page.$eval('tr[data-plan] a', (node) => node.getAttribute('href'))) === plan.path, plan.path);
  check('and no second plan opens for the same child while the first is live', (await call(page, 'POST', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`, { player: child.slug, review_weeks: 6 })).status === 409, 'the walk tried a raw duplicate as well as the button');
  await shot(page, 'plan-opened');

  // ----------------------------------------------------------- the plan page: one review is not a direction
  check('the plan page answers at that path', (await open(page, plan.path)).status() === 200, plan.path);
  const planDoor = `/api/v1/club/academy/${encodeURIComponent(ident)}/plans/${encodeURIComponent(plan.id)}`;
  const head = await call(page, 'GET', planDoor);
  const axes = eduDoor.axes;
  const pbody0 = await text(page);
  check('the page says who the plan belongs to, in the door’s words', has(pbody0, head.json.author.display_name) && shouts(pbody0, `your standing: ${head.json.your_standing.role}`), `${head.json.author.role} wrote it; you are ${head.json.your_standing.role}`);
  check('with no review filed it prints the empty state instead of a table of zeros', has(pbody0, 'No review yet'));
  check('and the reviews figure is the number of rows beneath it', (await rowsOf(page, 'assessment')).length === 0 && shouts(pbody0, '0 review(s) filed'));
  check('the axis table is the published axes, not a fixed five', (await attributeValues(page, 'tr[data-axis]', 'data-axis')).join(',') === axes.join(','), axes.join(', '));
  check('every formula the door publishes is printed beside its own name', (await attributeValues(page, '[data-formula]', 'data-formula')).join(',') === Object.keys(head.json.progress.formulas).join(','), `${Object.keys(head.json.progress.formulas).length} figures`);
  check('the write panel offers one field per axis and the published range', (await page.$$('[data-axis]')).length === 2 * axes.length && shouts(pbody0, `${eduDoor.rating_range[0]}–${eduDoor.rating_range[1]}`), `${axes.length} axes in two panels`);

  async function fileReview(ratings, want) {
    for (const axis of axes) {
      const selector = `input[aria-label="Rating for ${axis}"]`;
      await clearField(page, selector);
      if (ratings[axis] !== null) await typeInto(page, selector, ratings[axis]);
    }
    if ((await press(page, 'assessment-add')) !== 'clicked') return false;
    return untilTrue(async () => (await call(page, 'GET', planDoor)).json?.assessments?.length === want, 90_000);
  }

  const first = Object.fromEntries(axes.map((axis) => [axis, '40']));
  check('a first review files from the page', await fileReview(first, 1));
  const afterOne = await call(page, 'GET', planDoor);
  check('one review fills the table but is not a direction', afterOne.json.assessments.length === 1 && afterOne.json.progress.overall_change === null, `overall_change ${JSON.stringify(afterOne.json.progress.overall_change)}`);
  check('the page says so in the API’s own sentence', afterOne.json.progress.one_review_is_not_a_direction === true && (await until(page, 'a direction cannot be measured from one point')));
  check('every axis change stays empty rather than silently becoming zero', axes.every((axis) => (afterOne.json.progress.axis_change?.[axis] ?? null) === null), JSON.stringify(afterOne.json.progress.axis_change));
  check('the plan row on the tenant page still reads not yet', (await call(page, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`)).json.items[0].progress === null, 'one review: the door itself reports null progress');

  const second = { ...Object.fromEntries(axes.map((axis) => [axis, '70'])), [axes[axes.length - 1]]: null };
  check('a second review, with one axis deliberately left unrated, files too', await fileReview(second, 2));
  const afterTwo = await call(page, 'GET', planDoor);
  await untilTrue(async () => (await rowsOf(page, 'assessment')).length === 2, 60_000);
  const rows = await rowsOf(page, 'assessment');
  const unrated = axes[axes.length - 1];
  const gapRow = afterTwo.json.assessments.find((row) => !(unrated in (row.ratings ?? {})));
  check('the review table now holds two rows', rows.length === 2, `${rows.length} rows`);
  check('the axis nobody rated is missing, not zero, in the door’s own row', Boolean(gapRow?.axes_missing?.includes(unrated)) && !(unrated in (gapRow?.ratings ?? {})), `${gapRow?.axes_missing?.join(',') ?? '(no gap row)'}`);
  check('and the printed table shows a dash in that cell rather than a number', rows.some((row) => row.cells[1 + axes.indexOf(unrated)]?.text === '—'), `cell: ${rows.map((row) => row.cells[1 + axes.indexOf(unrated)]?.text).join(' / ')}`);
  const p2 = afterTwo.json.progress;
  check('with two reviews the arithmetic turns on', p2.assessments === 2 && typeof p2.overall_change === 'number', `overall_change ${p2.overall_change}`);
  // The printed review table is the evidence; the progress figures have to agree with it.
  const meanColumn = 1 + axes.length;
  const observedColumn = meanColumn + 1;
  const usesWorld = /overall_observed/.test(String(p2.formulas?.overall_change ?? ''));
  const expectedFirst = Number(rows[0].cells[usesWorld ? observedColumn : meanColumn].text);
  const expectedLast = Number(rows[1].cells[usesWorld ? observedColumn : meanColumn].text);
  check('the overall figures come from the column its own formula names', p2.overall_first === expectedFirst && p2.overall_last === expectedLast && p2.overall_change === expectedLast - expectedFirst, `formula names ${usesWorld ? 'overall_observed' : 'mean of rated axes'}: ${expectedFirst}->${expectedLast}; page: ${p2.overall_first}->${p2.overall_last}`);
  check('and the page prints those figures, not only the door', (await kvValue(page, 'Overall change')) === String(p2.overall_change) && shouts(await text(page), `${p2.overall_first} · ${p2.overall_last}`), await kvValue(page, 'Overall change'));
  const perAxis = axes.map((axis, index) => ({ axis, from: Number(rows[0].cells[1 + index].text), to: Number(rows[1].cells[1 + index].text), printed: p2.axis_change?.[axis] ?? null }));
  check('every axis change equals that axis’ last rating minus its first', perAxis.filter((row) => typeof row.printed === 'number').every((row) => row.printed === row.to - row.from), JSON.stringify(perAxis).slice(0, 170));
  check('an axis rated at one end only is excluded, by name, and its change stays empty', p2.axis_change_unrated_at_one_end.includes(unrated) && perAxis[axes.indexOf(unrated)].printed === null, `${p2.axis_change_unrated_at_one_end.join(',')} of ${axes.length}`);
  check('the page prints that exclusion rather than leaving the reader to spot the gap', has(squeeze(await text(page)), squeeze(`no change is claimed for: ${unrated}`)), unrated);
  const meanOfRated = (row) => {
    const rated = axes.map((axis, index) => row.cells[1 + index].text).filter((cell) => cell !== '' && cell !== '—').map(Number);
    return rated.reduce((sum, value) => sum + value, 0) / (rated.length || 1);
  };
  check('a review’s printed mean is the mean of the axes it rated', rows.every((row) => Math.abs(Number(row.cells[meanColumn].text) - meanOfRated(row)) < 0.51), rows.map((row) => `${row.cells[meanColumn].text} vs ${meanOfRated(row).toFixed(2)}`).join(' / '));
  const daySpan = (a, b) => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);
  const serverToday = new Date(Date.parse(`${p2.opened_on}T00:00:00Z`) + p2.plan_days_open * 86_400_000).toISOString().slice(0, 10);
  check('the three date figures are arithmetic over the dates printed', p2.span_days === daySpan(p2.first_assessed_on, p2.last_assessed_on) && p2.days_since_review === daySpan(p2.last_assessed_on, serverToday) && p2.plan_days_open === daySpan(p2.opened_on, serverToday), `span ${p2.span_days}, since ${p2.days_since_review}, open ${p2.plan_days_open} (server today ${serverToday})`);
  check('cadence arithmetic is stated with both of its figures', p2.reviews_behind === Math.max(0, p2.reviews_due_by_cadence - p2.assessments) && p2.due_in_days === plan.review_weeks * 7 - p2.days_since_review, `due ${p2.reviews_due_by_cadence}, behind ${p2.reviews_behind}, in ${p2.due_in_days} of ${plan.review_weeks * 7} days`);
  await shot(page, 'plan-two-reviews');

  // ----------------------------------------------------------- feedback, and what a guardian may not see
  await typeInto(page, 'input[aria-label="Feedback message"]', `Good session ${stamp.slice(-4)}.`);
  check('a note files from the page', (await press(page, 'feedback-add')) === 'clicked' && (await untilTrue(async () => (await call(page, 'GET', planDoor)).json?.feedback?.length === 1)));
  const sharedBox = 'input[aria-label="Share with guardian"]';
  check('the first note is shared by default', (await call(page, 'GET', planDoor)).json.withheld.coach_feedback === 0 && (await page.$eval(sharedBox, (node) => node.checked)) === true);
  await page.click(sharedBox);
  check('unticking the share box is what a withheld note needs', (await page.$eval(sharedBox, (node) => node.checked)) === false, 'the box reads unchecked before the note is filed');
  await typeInto(page, 'input[aria-label="Feedback message"]', 'A note the guardian is not shown.');
  check('a withheld note files too', (await press(page, 'feedback-add')) === 'clicked' && (await untilTrue(async () => (await call(page, 'GET', planDoor)).json?.feedback?.length === 2)));
  const afterNotes = await call(page, 'GET', planDoor);
  await until(page, '2 note(s) · 0 of them not shown to you');
  const fbody = await text(page);
  check('the author sees both notes and is told nothing is hidden from them, and the panel prints that figure', afterNotes.json.feedback.length === 2 && afterNotes.json.withheld.coach_feedback === 0 && shouts(fbody, '2 note(s) · 0 of them not shown to you'), `${afterNotes.json.feedback.length} notes, ${afterNotes.json.withheld.coach_feedback} not shown to the author`);
  const asFamily = await call(pageB, 'GET', planDoor);
  check('and the family’s read of the very same plan is the one that hides a note and says so', asFamily.status === 200 && asFamily.json.feedback.length === 1 && asFamily.json.withheld.coach_feedback === 1, `${asFamily.json.feedback?.length ?? '?'} of 2 shown, ${asFamily.json.withheld?.coach_feedback ?? '?'} withheld from the guardian`);
  check('the withheld note is named to its author and absent from the family’s copy', afterNotes.json.feedback.some((row) => row.message.includes('not shown')) && !asFamily.json.feedback.some((row) => row.message.includes('not shown')), asFamily.json.feedback.map((row) => row.message).join(' | '));
  check('and prints the rule that explains the difference', has(squeeze(fbody), squeeze(afterNotes.json.withheld.rule)), String(afterNotes.json.withheld.rule).slice(0, 60));
  check('a citation is a label and a window, not a way to watch', shouts(fbody, 'a citation is a label and a window, not a way to watch'));
  const citationRows = (await page.$$('[data-evidence]')).length;
  check('the walk filed no clip, so no citation row is painted and the door reports none', afterNotes.json.evidence.length === 0 && citationRows === 0, `${afterNotes.json.evidence.length} on the door, ${citationRows} on screen`);
  check('the integrity panel counts every row type the door names', Object.entries(afterNotes.json.integrity.checked).every(([figure, value]) => shouts(fbody, `${value} ${figure}`)), JSON.stringify(afterNotes.json.integrity.checked).slice(0, 150));
  check('the plan page is noindex like the rest of the private area', /noindex/.test(await metaRobots(page)), await metaRobots(page));
  check('and carries its own limits, not a copy of the tenant’s', (afterTwo.json.limitations ?? []).length > 0 && has(squeeze(fbody), squeeze(afterTwo.json.limitations[0])), `${(afterTwo.json.limitations ?? []).length} sentences`);
  check('it prints where the figures came from', has(squeeze(fbody), squeeze(afterTwo.json.progress.measured_from)), String(afterTwo.json.progress.measured_from).slice(0, 60));

  // ----------------------------------------------------------- an account that was never invited at all
  const strangerContext = await browser.createBrowserContext();
  const pageC = await strangerContext.newPage();
  await pageC.setViewport(DESKTOP);
  watch(pageC, 'stranger');
  await open(pageC, '/login');
  const registerC = await register(pageC, STRANGER, 'Club QA Stranger', 'coach');
  check('a third account registers and is invited to nothing', registerC.status === 201, `HTTP ${registerC.status} ${JSON.stringify(registerC.json ?? null).slice(0, 80)}`);
  check('the tenant page is a 404 for them, and never a 403', (await pageC.goto(`${BASE}${tenant.path}`, { waitUntil: 'domcontentloaded' })).status() === 404 && !shouts(await text(pageC), 'forbidden'), tenant.path);
  check('so is the child’s plan page — the address worth guessing, if any was', (await pageC.goto(`${BASE}${plan.path}`, { waitUntil: 'domcontentloaded' })).status() === 404, plan.path);
  check('and both doors behind those pages answer absent too', (await call(pageC, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).status === 404 && (await call(pageC, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`)).status === 404, 'page, plan, tenant door, academy door');
  const parentRights = clubRules.matrix.matrix.parent;
  check('a guardian holds three rights, and the matrix publishes those three', parentRights.length === 3 && parentRights.includes('consent.grant_own'), parentRights.join(', '));

  const doors = [
    ['consents', `/api/v1/club/academy/${encodeURIComponent(ident)}/consents`],
    ['curricula', `/api/v1/club/academy/${encodeURIComponent(ident)}/curricula`],
    ['plans', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`],
  ];
  for (const [label, path] of doors) {
    const read = await call(pageB, 'GET', path);
    const printed = await pageB.$(`[data-refused="${label}"]`);
    check(`the ${label} door and the ${label} panel agree: a 2xx is never painted as a refusal, and a refusal is never painted as an empty list`, read.status < 300 ? printed === null : printed !== null, `door HTTP ${read.status}, panel ${printed ? 'refused' : 'rendered'}`);
  }
  const asMember = await call(pageB, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`);
  const memberBody = await text(pageB);
  check('the rights a guardian holds are printed from their own grant, not the owner’s', shouts(memberBody, `${asMember.json.my_grant.permissions.length} of ${clubRules.matrix.permissions.length} rights`) && asMember.json.my_grant.role === 'parent' && asMember.json.my_grant.permissions.length === parentRights.length, `parent holds ${asMember.json?.my_grant?.permissions.length} of ${clubRules.matrix.permissions.length}`);
  check('their grant says why, in the door’s sentence', has(squeeze(memberBody), squeeze(asMember.json.my_grant.why)), String(asMember.json.my_grant.why ?? '(none)').slice(0, 60));
  check('a page does not disable a write control by guessing their role', (await pageB.$$eval('[data-testid="consent-grant"],[data-testid="plan-open"]', (nodes) => [nodes.length, nodes.every((node) => !node.disabled)]))[0] === 2 && (await pageB.$$eval('[data-testid="consent-grant"],[data-testid="plan-open"]', (nodes) => nodes.every((node) => !node.disabled))) === true, 'both buttons are live for a member; the API decides what they may write');
  await open(page, tenant.path);
  const ownerView = await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`);
  check('the owner’s table re-reads two active members', ownerView.json.counts.active_members === 2 && ownerView.json.members.length === 2, `${ownerView.json.counts.active_members} active of ${ownerView.json.counts.member_limit}`);
  check('the new member is on the row list with the standing they accepted', ownerView.json.members.some((row) => row.email === INVITEE && row.role === 'parent'), 'parent');
  check('the tenant page prints the §39 limits the same response carries', (ownerView.json.limitations ?? []).length > 0 && shouts(await text(page), `${ownerView.json.limitations.length} limits the API states on this very response`), `${(ownerView.json.limitations ?? []).length} sentences`);
  const memberClose = await call(pageB, 'DELETE', `/api/v1/club/${encodeURIComponent(ident)}`, { confirm: TENANT });
  check('a member may not close the tenant: the page’s own door answers them', memberClose.status === (clubRules.refusal_answers.insufficient_role ?? 403), `HTTP ${memberClose.status} ${JSON.stringify(memberClose.json ?? null).slice(0, 70)}`);
  check('and the tenant is still there to be read afterwards', (await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).status === 200);

  await page.setViewport(MOBILE);
  await open(page, plan.path);
  const narrow = await rowsOf(page, 'assessment');
  check('the review table survives a phone viewport', narrow.length === 2 && narrow[0].cells.length === axes.length + 5, `${narrow.length} rows, ${narrow[0]?.cells.length} columns`);
  check('and the progress formulas are still readable at 375px', (await page.$$('[data-formula]')).length === Object.keys(p2.formulas).length, `${(await page.$$('[data-formula]')).length} rows`);
  await shot(page, 'plan-mobile');

  const serverFaults = consoleErrors.filter((line) => /status of 5\d\d/.test(line));
  const unasked = consoleErrors.filter((line) => !/status of 4\d\d/.test(line));
  check('every console line left behind is a 4xx the walk knocked for itself — no 5xx, no page exception', serverFaults.length === 0 && unasked.length === 0, `${consoleErrors.length} lines: ${consoleErrors.slice(0, 2).join(' | ')}`.slice(0, 190));

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
  // A walk that died halfway must not report the checks it managed to run as the whole story.
  check('the walk ran through to its last check', false, String(error?.message ?? error).slice(0, 160));
  finish();
});
