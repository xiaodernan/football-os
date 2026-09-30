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

const BASE = (process.env.QA_BASE ?? 'http://127.0.0.1:3214').trim();
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
function askOnce(page, method, path, body) {
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
      return { status: response.status, json, retry: Number(response.headers.get('retry-after')) || null };
    },
    method,
    path,
    body ?? null,
  );
}

/** A 429 is the per-minute limiter answering the walk's own polling rate — the walk drives a page faster than a
 *  person can, and every `router.refresh()` a write triggers re-reads the doors the page paints. So a call waits
 *  out the `Retry-After` the door printed and tries again, bounded: a server that limits forever still reports 429
 *  rather than hanging the walk.
 */
async function call(page, method, path, body) {
  let last = null;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    last = await askOnce(page, method, path, body);
    if (last.status !== 429) return last;
    await new Promise((done) => setTimeout(done, Math.min(Math.max(last.retry ?? 2, 2), 20) * 1000));
  }
  return last;
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

/**
 * Press a write control and read the note *that* press paints, waiting the tier's own rate door out.
 *
 * The walk drives a page faster than a person can, and the club writes are limited per minute, so a 429 here is
 * a fact about the walk's speed rather than about the feature: the press is retried after a wait. The note is
 * matched against the one painted *after* the press, because the component keeps the previous answer on screen
 * and a stale note would otherwise answer for a later call. `ok` is true only when a fresh note arrived *and it
 */
async function pressWrite(page, button, action, want = '', tries = 4) {
  const sel = `[data-note="${action}"]`;
  const read = () => page.$eval(sel, (node) => node.innerText.replace(/\s+/g, ' ').trim()).catch(() => '');
  for (let attempt = 1; attempt <= tries; attempt += 1) {
    const before = await read();
    const pressed = await press(page, button);
    if (pressed !== 'clicked') return { ok: false, pressed, note: `(the button ${pressed})`, attempts: attempt };
    let note = '';
    let changed = false;
    let matched = squeeze(want).length === 0;
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      note = await read();
      if (note.length > 0 && note !== before) {
        changed = true;
        matched = squeeze(want).length === 0 || squeeze(note).toUpperCase().includes(squeeze(want).toUpperCase());
        // A fresh note that is not the rate door is the answer either way — a refusal is not a pass, and
        // waiting the deadline out for a note that already arrived would only slow the red down.
        if (matched || !/429/.test(note)) break;
      }
      await new Promise((done) => setTimeout(done, 300));
    }
    if (!/429/.test(note)) return { ok: matched && changed, pressed, note: note === before ? '(no fresh note painted)' : note, attempts: attempt };
    await new Promise((done) => setTimeout(done, 25_000));
  }
  return { ok: false, pressed: 'limited', note: '(every attempt was answered 429 by the rate door)', attempts: tries };
}

/**
 * The "Plan and limits" table exactly as the page paints it: feature → the figures in its own columns.
 *
 * The columns are read positionally rather than by matching prose, because the point of the check is that the
 * arithmetic holds *across* the columns a reader sees: ceiling minus used, the remainder printed beside them.
 */
async function meterOf(page) {
  const rows = await page.$$eval('tr[data-entitlement]', (nodes) => nodes.map((node) => Array.from(node.querySelectorAll('td')).map((cell) => cell.innerText.trim())));
  return Object.fromEntries(rows.map((cells) => [cells[0], { limit: Number(cells[1]), used: Number(cells[2]), remaining: Number(cells[3]), period: cells[4], acts: Number(cells[5]), enforced: cells[6] }]));
}

/** Every key name a JSON payload carries, however deep — the shape a payment would have to live in. */
function keyNames(node) {
  if (Array.isArray(node)) return node.flatMap(keyNames);
  if (node && typeof node === 'object') return Object.keys(node).flatMap((key) => [key, ...keyNames(node[key])]);
  return [];
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
  const readyRule = squeeze(String(clubRules?.ready_rule ?? ''));
  check('the §39 capabilities door answers a caller with no session and prints the two conditions its ready flag stands on', rulesDoor.status === 200 && typeof clubRules?.ready === 'boolean' && shouts(readyRule, 'tables') && shouts(readyRule, 'at least one'), `HTTP ${rulesDoor.status}; rule ${readyRule.slice(0, 70)}`);
  const eduDoor = await (await fetch(`${BASE}/api/v1/club/academy/capabilities`, { headers: { accept: 'application/json' } })).json();
  check('the §40 door answers the same way, names the same threshold, and prints the one sentence rather than its own', eduDoor?.minor_age === 18 && typeof eduDoor?.ready === 'boolean' && squeeze(String(eduDoor?.ready_rule ?? '')) === readyRule, `minor_age ${eduDoor?.minor_age}; identical sentence: ${squeeze(String(eduDoor?.ready_rule ?? '')) === readyRule}`);
  // The flag is read from data, so the walk holds it from both sides: false on the empty database it provisions,
  // and true once its own first account exists. One-sided, this check would only ever prove the door answers.
  check('and on the empty database this walk just provisioned both doors answer false instead of implying a tenant layer is up', clubRules?.ready === false && eduDoor?.ready === false, `club ${JSON.stringify(clubRules?.ready)}, academy ${JSON.stringify(eduDoor?.ready)}`);
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
  check('and the rulebook page carries the ready rule as the door wrote it, so a flag on a page has the sentence beside it', shouts(rulesBody, readyRule), `${shouts(rulesBody, readyRule) ? 'printed' : 'absent'} · ${readyRule.slice(0, 60)}…`);
  await shot(page, 'rulebook-signed-out');

  // ----------------------------------------------------------- register and read the index
  await open(page, '/login');
  const registered = await register(page, OWNER, 'Club QA Owner', 'coach');
  check('an owner registers through the cookie proxy', registered.status === 201, `HTTP ${registered.status} ${JSON.stringify(registered.json ?? null).slice(0, 80)}`);
  // The other half of the flag the rulebook page prints: the same two doors, re-read now that this walk's own
  // first account exists in the database it provisioned. One-sided, the earlier check would only ever prove that
  // a door answers.
  const readyAfter = await (await fetch(`${BASE}/api/v1/club/capabilities`, { headers: { accept: 'application/json' } })).json();
  const readyAfterAcademy = await (await fetch(`${BASE}/api/v1/club/academy/capabilities`, { headers: { accept: 'application/json' } })).json();
  check('and both doors flip to true on that one account, which is all the printed rule asks for', readyAfter?.ready === true && readyAfterAcademy?.ready === true, `club ${JSON.stringify(readyAfter?.ready)}, academy ${JSON.stringify(readyAfterAcademy?.ready)}`);

  // ------------------------------------------------- the refresh cookie has to be reachable by its readers
  //
  // `fo_refresh` is the 30-day credential. Scoped to `/api/v1/auth` it was invisible to both things that
  // read it — the middleware on a page request and the proxy on `/api/v1/careers` — so a session ended at
  // the login screen the moment the 15-minute access token expired, with a perfectly good refresh token
  // sitting unread in the jar. Two facts pin that down, and the second is the one that would have failed:
  // the cookie's path, and a call made with no access token at all.
  const jar = await page.cookies();
  const refresh = jar.find((cookie) => cookie.name === 'fo_refresh');
  check(
    'the refresh credential is scoped to the whole site, so both readers can reach it',
    !!refresh && refresh.path === '/',
    refresh ? `path ${refresh.path} · httpOnly ${refresh.httpOnly} · sameSite ${refresh.sameSite}` : 'no fo_refresh in the jar',
  );
  await page.deleteCookie({ name: 'fo_access', url: BASE });
  const withoutAccess = await page.evaluate(async () => {
    const response = await fetch('/api/v1/club', { credentials: 'same-origin' });
    return { status: response.status, body: await response.text() };
  });
  const regranted = (await page.cookies()).find((cookie) => cookie.name === 'fo_access');
  check(
    'a door called with no access token is refreshed from that cookie rather than answered 401',
    withoutAccess.status === 200 && !!regranted && !/unauthor/i.test(withoutAccess.body.slice(0, 200)),
    `HTTP ${withoutAccess.status} · access token ${regranted ? 're-minted' : 'not re-minted'}`,
  );

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

  // ----------------------------------------------------------- §41's session log, written from the page
  await open(page, tenant.path);
  const sessionsPath = `/api/v1/club/academy/${encodeURIComponent(ident)}/sessions`;
  const reportsPath = `/api/v1/club/academy/${encodeURIComponent(ident)}/reports`;
  const firstLog = await call(page, 'GET', sessionsPath);
  // The day the write rule judges against, read from the door that owns the rule rather than from this host's
  // clock: a walk runs for minutes, and every figure below is the date the server says it is.
  const doorToday = firstLog.json?.today ?? '(the session door printed no today)';
  check('the sessions door publishes the day it refuses a future date against, in its own sentence', /^\d{4}-\d{2}-\d{2}$/.test(doorToday) && has(String(firstLog.json?.today_rule ?? ''), 'date_in_future'), `today ${doorToday}; rule ${String(firstLog.json?.today_rule ?? '(none)').slice(0, 60)}`);
  const paintedDate = await page.$eval('input[aria-label="Session date"]', (node) => node.value).catch(() => '(no field on the page)');
  check('and the form the page paints is open on that day, not on a day it worked out for itself', paintedDate === doorToday, `the field holds ${paintedDate}; the door says ${doorToday}`);
  check('the session door answers an empty log, with a zero and not a missing mean', firstLog.status === 200 && firstLog.json.total === 0 && firstLog.json.total_load_units === 0 && firstLog.json.mean_rpe === null, `${firstLog.json.total} row(s), load ${firstLog.json.total_load_units}, mean rpe ${JSON.stringify(firstLog.json.mean_rpe)}`);
  check('and the panel says the same thing instead of painting an empty table', (await page.$('[data-load-check]')) !== null && shouts(await text(page), '0 session(s)'), 'an empty log is a zero, not a refusal');
  check('the recorder prints the caps the door publishes rather than its own', shouts(await text(page), `(${eduDoor.session_limits.duration_range[0]}–${eduDoor.session_limits.duration_range[1]} minutes)`) && shouts(await text(page), `(${eduDoor.session_limits.rpe_range[0]}–${eduDoor.session_limits.rpe_range[1]})`) && shouts(await text(page), `at most ${eduDoor.session_limits.session_focus_max})`) && shouts(await text(page), `at most ${eduDoor.session_limits.attendance_max} may be`), JSON.stringify(eduDoor.session_limits).slice(0, 130));
  check('and the report form, for the window the tier enforces', shouts(await text(page), `at most ${eduDoor.report_limits.window_max_days} days after the start`), `window_max_days ${eduDoor.report_limits.window_max_days}`);

  const durationBox = 'input[aria-label="Session duration"]';
  const rpeBox = 'input[aria-label="Session RPE"]';
  await clearField(page, durationBox);
  await typeInto(page, durationBox, '75');
  await clearField(page, rpeBox);
  await typeInto(page, rpeBox, '6');
  await typeInto(page, 'input[aria-label="Session focus"]', 'pressing, transitions');
  await typeInto(page, 'input[aria-label="Session note"]', `QA session ${stamp.slice(-4)}.`);
  check('the attendance boxes are the players on that sheet, and nobody else', (await attributeValues(page, '[data-testid^="attendee-"]', 'data-testid')).join(',') === `attendee-${child.slug}`, `the sheet holds ${sheet.squad_size} row(s)`);
  check('and the page will not record a session with nobody named before it asks the door', (await page.$eval('[data-testid="session-record"]', (node) => node.disabled)) === true, 'the button is disabled until an attendee is ticked');
  check('ticking a player is what arms the write', (await press(page, `attendee-${child.slug}`)) === 'clicked' && (await page.$eval('[data-testid="session-record"]', (node) => !node.disabled)) === true);
  const written = await pressWrite(page, 'session-record', 'session-record', 'answered');
  check('the page records the session from its own controls', written.ok && (await untilTrue(async () => (await call(page, 'GET', sessionsPath)).json?.total === 1, 90_000)), `the button ${written.pressed} after ${written.attempts} attempt(s); the page's own note: ${written.note}`);

  const logged = await call(page, 'GET', sessionsPath);
  const session = (logged.json.items ?? [])[0] ?? {};
  const expectedLoad = Math.round((75 * 6) / 60 * 10) / 10;
  check('the row it wrote keeps the figures the form held', session.duration_min === 75 && session.rpe === 6 && session.slot === 1 && session.team?.id === team.id && (session.focus ?? []).join(',') === 'pressing,transitions', `${session.duration_min} min at rpe ${session.rpe}, slot ${session.slot}, focus ${(session.focus ?? []).join('/')}`);
  check('and the date is the day the door calls today, not one the page guessed for itself', session.scheduled_on === doorToday, `${session.scheduled_on} vs the door’s own ${doorToday} (the day this walk began, from the plan door, was ${serverToday})`);
  check('the attendee is the child the walk put on the sheet, read back from the world', (session.attendees ?? []).length === 1 && session.attendees[0].slug === child.slug && session.attendees[0].is_minor === true, JSON.stringify((session.attendees ?? []).map((row) => row.slug)));
  check('the load is the published formula over the row’s own two columns, and the total is the same arithmetic', session.load_units === expectedLoad && logged.json.total_load_units === expectedLoad && shouts(await text(page), logged.json.formulas?.total_load_units ?? 'no formula published'), `expected ${expectedLoad}; the door says ${session.load_units}`);
  const logRows = await waitRows(page, 'session');
  check('the printed row shows the minutes, the rpe and the load the door computed', logRows.length === 1 && logRows[0].cells[4]?.text === '75 min' && logRows[0].cells[5]?.text === '6' && Number(logRows[0].cells[6]?.text) === expectedLoad, logRows[0]?.cells.map((cell) => cell.text).join(' | ').slice(0, 150));
  const columnSum = logRows.reduce((sum, row) => sum + Number(row.cells[6]?.text ?? 0), 0);
  check('the page adds its own printed column up before believing the total beside it', (await page.$eval('[data-load-check]', (node) => node.getAttribute('data-load-check'))) === 'agrees' && Math.abs(columnSum - logged.json.total_load_units) < 0.05, `column ${columnSum.toFixed(2)} vs door ${logged.json.total_load_units}`);

  await press(page, `attendee-${child.slug}`);
  await clearField(page, durationBox);
  await typeInto(page, durationBox, String(eduDoor.session_limits.duration_range[1] + 1));
  const tooLong = await pressWrite(page, 'session-record', 'session-record', 'refused with');
  check('a duration outside the published range is refused with the figure it tripped over', tooLong.ok && /refused with 4\d\d/.test(tooLong.note) && has(tooLong.note, 'duration_range') && has(squeeze(tooLong.note), squeeze(String(eduDoor.session_limits.duration_range[1]))), `${tooLong.note.slice(0, 170)} (after ${tooLong.attempts} attempt(s), the button ${tooLong.pressed})`);
  await clearField(page, durationBox);
  await typeInto(page, durationBox, '60');
  const clashed = await pressWrite(page, 'session-record', 'session-record', 'refused with');
  check('a second session in the same date and slot is a conflict, not an overwrite', clashed.ok && /refused with 409/.test(clashed.note) && has(clashed.note, 'slot_taken'), `${clashed.note.slice(0, 170)} (the button ${clashed.pressed})`);
  const afterRefusals = await call(page, 'GET', sessionsPath);
  check('and neither refusal is a write: one row, still at 75 minutes', afterRefusals.json.total === 1 && afterRefusals.json.items[0].duration_min === 75, `${afterRefusals.json.total} row(s), ${afterRefusals.json.items[0]?.duration_min} min`);

  // ----------------------------------------------------------- §41's saved question, answered on read
  const reportsDoor = await call(page, 'GET', reportsPath);
  check('the report door answers an empty list of questions and names the kinds it can produce', reportsDoor.status === 200 && reportsDoor.json.total === 0 && reportsDoor.json.kinds.join(',') === eduDoor.report_kinds.join(','), `${reportsDoor.json.total} saved; kinds ${reportsDoor.json.kinds.join(', ')}`);
  check('and the form offers those kinds as a choice, not as free text', (await page.$$eval('select[aria-label="Report kind"] option', (nodes) => nodes.map((node) => node.value))).join(',') === eduDoor.report_kinds.join(','), eduDoor.report_kinds.join(', '));
  const windowStart = 'input[aria-label="Report window start"]';
  const windowEnd = 'input[aria-label="Report window end"]';
  await clearField(page, windowStart);
  await typeInto(page, windowStart, doorToday);
  await clearField(page, windowEnd);
  await typeInto(page, windowEnd, doorToday);
  const savedQuestion = await pressWrite(page, 'report-save', 'report-save', 'answered');
  check('the page saves the question from its own controls', savedQuestion.ok && (await untilTrue(async () => (await call(page, 'GET', reportsPath)).json?.total === 1, 90_000)), `the button ${savedQuestion.pressed} after ${savedQuestion.attempts} attempt(s); the page's own note: ${savedQuestion.note}`);
  const saved = await call(page, 'GET', reportsPath);
  const report = (saved.json.items ?? [])[0] ?? {};
  check('a report stores the question — a kind, a window and a sheet — and no figure at all', report.kind === 'squad_load' && report.window_from === doorToday && report.window_to === doorToday && report.team === null, `${report.kind} ${report.window_from}→${report.window_to}, team ${JSON.stringify(report.team)}`);
  check('the window length is arithmetic over the two dates it stored', report.window_days === 1, `${report.window_days} day(s)`);
  check('and the answer is the rows that exist now: the session the walk just recorded', report.body?.sessions === 1 && report.body.total_load_units === expectedLoad && report.body.mean_rpe === 6 && report.body.most_worked === child.slug, JSON.stringify({ sessions: report.body?.sessions, load: report.body?.total_load_units, mean: report.body?.mean_rpe, most: report.body?.most_worked }));
  const reportRows = await waitRows(page, 'report');
  check('the row prints the figures the door computed beside the question it keeps', reportRows.length === 1 && reportRows[0].cells[5]?.text === '1' && Number(reportRows[0].cells[6]?.text) === expectedLoad, reportRows[0]?.cells.map((cell) => cell.text).join(' | ').slice(0, 150));
  // ----------------------------------------------------------- §39's fixtures: arranged here, played by the engine
  const fixturesPath = `/api/v1/club/${encodeURIComponent(ident)}/fixtures`;
  const rulebook = (await call(page, 'GET', '/api/v1/club/capabilities')).json ?? {};
  const caps = rulebook.fixture_caps ?? {};
  const sideField = 'select[aria-label="Fixture side"]';
  const dateField = 'input[aria-label="Fixture date"]';
  const opponentField = 'input[aria-label="Fixture opponent"]';
  const competitionField = 'input[aria-label="Fixture competition"]';
  const calendar0 = await call(page, 'GET', fixturesPath);
  check('the fixtures door answers the owner with an empty calendar, its own ceiling and the day it compares against', calendar0.status === 200 && calendar0.json?.total === 0 && calendar0.json?.limit === caps.max_fixtures_per_organization && typeof calendar0.json?.today === 'string', `HTTP ${calendar0.status} · limit ${calendar0.json?.limit} · today ${calendar0.json?.today}`);
  check('the form offers exactly the sides the rulebook publishes, in its order', (await page.$$eval(`${sideField} option`, (nodes) => nodes.map((node) => node.value))).join(',') === (caps.sides ?? []).join(','), (caps.sides ?? []).join(', '));
  const openedOn = await page.$eval(dateField, (node) => node.value);
  check('and its date field opens on the door’s own today, not on a day the page guessed for itself', openedOn === calendar0.json?.today && (await page.$eval(dateField, (node) => node.getAttribute('data-fixture-date'))) === calendar0.json?.today, `the field holds ${openedOn}; the door says ${calendar0.json?.today}`);
  check('the panel prints the arithmetic it counted from, rather than a number it made up', has(await text(page), `fielded only while the sheet reaches ${caps.needs_players}`) && has(await text(page), `${caps.minute_choices.join(', ')}`), `needs_players ${caps.needs_players}, block lengths ${caps.minute_choices.join('/')}`);
  check('the arrange button waits for an opponent before it will write', (await page.$eval('[data-testid="fixture-arrange"]', (node) => node.disabled)) === true, 'no opponent typed yet');

  await typeInto(page, opponentField, 'united-of-nowhere');
  const ghost = await pressWrite(page, 'fixture-arrange', 'fixture-arrange', 'refused with');
  check('a club that is not in the generated world is answered 404, and the page prints the slug it was handed', ghost.ok && /refused with 404/.test(ghost.note) && has(ghost.note, 'no_such_world_club') && has(ghost.note, 'united-of-nowhere'), ghost.note.slice(0, 170));
  check('and a refusal is not a write: the calendar is still empty', (await call(page, 'GET', fixturesPath)).json?.total === 0, JSON.stringify((await call(page, 'GET', fixturesPath)).json?.total));

  await clearField(page, dateField);
  await typeInto(page, dateField, '2099-01-01');
  const future = await pressWrite(page, 'fixture-arrange', 'fixture-arrange', 'refused with');
  check('a day that has not happened is refused with the door’s own today beside the sentence', /refused with 422/.test(future.note) && has(future.note, 'date_in_future') && has(squeeze(future.note), squeeze(String(calendar0.json?.today))), future.note.slice(0, 170));

  const clubs = (await call(page, 'GET', '/api/v1/world/teams?page_size=8')).json?.items ?? [];
  const opponent = clubs.find((row) => row.slug !== (team.world_team?.slug ?? '')) ?? {};
  check('the walk has a real club in the ladder to arrange against', Boolean(opponent.slug), `${clubs.length} club(s) read from /world/teams`);
  const yesterday = new Date(Date.parse(`${calendar0.json?.today}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10);
  // The field still holds the slug from the refusal above: `typeInto` appends, so a walk that does not clear it
  // first arranges against `united-of-nowhere<slug>` and reads the door's correct 404 as a product defect.
  await clearField(page, opponentField);
  await typeInto(page, opponentField, opponent.slug ?? 'no-club-in-the-ladder');
  await clearField(page, dateField);
  await typeInto(page, dateField, yesterday);
  await clearField(page, competitionField);
  await typeInto(page, competitionField, `QA Riverside Cup ${stamp.slice(-4)}`);
  const arranged = await pressWrite(page, 'fixture-arrange', 'fixture-arrange', 'answered');
  check('the page arranges a fixture from its own controls', arranged.ok && (await untilTrue(async () => (await call(page, 'GET', fixturesPath)).json?.total === 1, 90_000)), `the button ${arranged.pressed} after ${arranged.attempts} attempt(s); note: ${arranged.note.slice(0, 120)}`);

  const calendar1 = await call(page, 'GET', fixturesPath);
  const row0 = (calendar1.json?.items ?? [])[0] ?? {};
  const named = row0.named ?? [];
  // The door answered the write long before the page paints it: the runner's `router.refresh()` re-read lands on
  // its own clock, so every control the next six checks press has to be waited for rather than assumed.
  const fxRows = await waitRows(page, 'fixture');
  check('and the page paints the row it was told about', fxRows.length === 1 && fxRows[0].key === row0.id, `${fxRows.length} painted row(s) against ${calendar1.json?.total} the door counts`);
  check('the arrangement is a promise: scheduled, unplayed, with no engine row behind it yet', row0.status === 'scheduled' && row0.match === null && row0.appearances === 0 && row0.scheduled_on === yesterday && row0.opponent?.slug === opponent.slug, `${row0.status} ${row0.scheduled_on} vs ${JSON.stringify(row0.opponent?.slug)} · match ${JSON.stringify(row0.match)}`);
  check('it keeps the side and the competition the form held, and the sheet the door named by default', row0.side === (caps.sides ?? [])[0] && row0.competition === `QA Riverside Cup ${stamp.slice(-4)}` && named.length === (team.squad_size ?? 0) + 1, `side ${row0.side}, ${named.length} named, ${(team.squad_size ?? 0) + 1} expected`);
  const printedTotals = await text(page);
  check('the panel prints the ceiling as one held of the door’s own maximum', shouts(printedTotals, `1 of ${calendar1.json?.limit} allowed`), `the door’s limit is ${calendar1.json?.limit}`);
  check('and the competition tally it prints is counted from the rows, not typed in', shouts(printedTotals, `QA Riverside Cup ${stamp.slice(-4)} 1`), JSON.stringify(calendar1.json?.by_competition));
  const agreeBadge = await page.$eval('[data-testid="fixture-count-agrees"]', (node) => node.innerText);
  check('the appearances column agrees with the total the door printed before either is believed', shouts(agreeBadge, 'adds up to the total'), `column and door over ${calendar1.json?.items?.length} row(s): ${agreeBadge.slice(0, 120)}`);

  const played = await pressWrite(page, `fixture-play-${row0.id}`, `fixture-play-${row0.id}`, 'refused with');
  const unplaced = !(team.world_team?.slug ?? '');
  check('the play button asks the engine, and the answer is the door’s own reason', played.ok && /refused with 4\d\d/.test(played.note) && has(played.note, unplaced ? 'no_world_side' : 'can_not_field'), `team placed in the world: ${unplaced ? 'no' : team.world_team.slug} · ${played.note.slice(0, 150)}`);
  const calendar2 = await call(page, 'GET', fixturesPath);
  check('a refused play leaves the fixture unplayed and stores no result', calendar2.json?.items?.[0]?.status === 'scheduled' && calendar2.json?.items?.[0]?.match === null && calendar2.json?.appearances === 0, `${JSON.stringify(calendar2.json?.items?.[0]?.status)} · ${calendar2.json?.appearances} appearance rows`);

  const erased = await pressWrite(page, `fixture-erase-${row0.id}`, `fixture-erase-${row0.id}`, 'answered');
  check('the page erases the arrangement from its own control', erased.ok && (await untilTrue(async () => (await call(page, 'GET', fixturesPath)).json?.total === 0, 90_000)), `the button ${erased.pressed}; note: ${erased.note.slice(0, 120)}`);
  const calendar3 = await call(page, 'GET', fixturesPath);
  const emptied = await untilTrue(async () => (await page.$$('[data-fixture]')).length === 0, 60_000);
  check('and the empty calendar says so in the page’s own words, with the door’s rule under it', calendar3.json?.total === 0 && emptied === true && shouts(await text(page), 'Nothing arranged yet'), `${calendar3.json?.total} row(s) server-side, the table repainted: ${emptied}`);
  check('the panel prints the tier’s own limitation sentence rather than a paraphrase of it', has(await text(page), String(rulebook.fixture_limitation ?? '<<no limitation published>>>').slice(0, 60)), String(rulebook.fixture_limitation ?? '').slice(0, 120));
  await shot(page, 'fixtures-after-the-erase');

  // ------------------------------------------------- §39's board: an audience selects, it never names a person
  const noticesPath = `/api/v1/club/${encodeURIComponent(ident)}/announcements`;
  const noticeCaps = rulebook.announcement_caps ?? {};
  const noticeAnswers = rulebook.announcement_refusals ?? {};
  const audienceField = 'select[aria-label="Notice audience"]';
  const titleField = 'input[aria-label="Notice title"]';
  const bodyField = 'textarea[aria-label="Notice body"]';
  const pinField = 'input[aria-label="Notice pinned"]';
  const board0 = await call(page, 'GET', noticesPath);
  check('the notices door answers the owner with an empty board, its own ceiling and the audiences it posts to', board0.status === 200 && board0.json?.total === 0 && board0.json?.limit === noticeCaps.announcement_max && board0.json?.caps?.audiences?.join(',') === (noticeCaps.audiences ?? []).join(','), `HTTP ${board0.status} · limit ${board0.json?.limit} against the cap ${noticeCaps.announcement_max} · audiences ${board0.json?.caps?.audiences?.join(', ')}`);
  check('each of the seven published notice refusals means one HTTP answer, and none of them is a 403', Object.keys(noticeAnswers).length === 7 && Object.values(noticeAnswers).every((status) => [404, 409, 422].includes(status)) && noticeAnswers.announcement_limit === 409 && noticeAnswers.not_an_audience === 422, JSON.stringify(noticeAnswers));
  // Painted before pressed: every selector below lives inside the panel, and a page that served `<Refused>` instead
  // would otherwise answer with one crash that costs the rest of the walk its remaining checks.
  const boardPainted = await untilTrue(async () => (await page.$$('[data-testid="notice-totals"]')).length === 1, 60_000);
  check('the tenant page paints the notice board itself, so the controls below have a panel to belong to', boardPainted === true, `the panel's own totals row ${boardPainted ? 'is painted' : 'is absent — the page answered the door without mounting the board'}`);
  check('the poster offers exactly the audiences the rulebook publishes, in its order', (await page.$$eval(`${audienceField} option`, (nodes) => nodes.map((node) => node.value))).join(',') === (noticeCaps.audiences ?? []).join(','), (noticeCaps.audiences ?? []).join(', '));
  check('and its two text fields carry the door’s ceilings rather than a length the page chose', (await page.$eval(titleField, (node) => node.maxLength)) === noticeCaps.title_max && (await page.$eval(bodyField, (node) => node.maxLength)) === noticeCaps.body_max, `title ${noticeCaps.title_max}, body ${noticeCaps.body_max}`);

  const blankTitle = await pressWrite(page, 'notice-post', 'notice-post', 'refused with');
  check('a notice with no title is refused with the rule that names the field it tripped over', blankTitle.ok && /refused with 422/.test(blankTitle.note) && has(blankTitle.note, 'announcement_title'), blankTitle.note.slice(0, 170));
  const wrongAudience = await call(page, 'GET', `${noticesPath}?audience=nobody`);
  check('a filter naming no audience is answered by the door, not by a page that quietly narrowed its own rows', wrongAudience.status === 422 && has(JSON.stringify(wrongAudience.json ?? ''), 'announcement_audience'), `HTTP ${wrongAudience.status} · ${JSON.stringify(wrongAudience.json ?? '').slice(0, 120)}`);
  check('and neither refusal is a write: the board is still empty', (await call(page, 'GET', noticesPath)).json?.total === 0, `${(await call(page, 'GET', noticesPath)).json?.total} row(s)`);

  // The denominator this panel prints is a predicate over the roster, so the walk counts the roster from the
  // tenant door and asks whether the notice board's figure means the same thing.
  const roster = (await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).json?.members ?? [];
  const staffActive = roster.filter((row) => row.status === 'active' && row.role !== 'parent').length;
  const parentActive = roster.filter((row) => row.status === 'active' && row.role === 'parent').length;
  check('the walk has the roster it thinks it has, before it judges a readership', roster.length > 0 && staffActive === roster.filter((row) => row.status === 'active').length - parentActive, `${roster.length} row(s): ${staffActive} staff-side active, ${parentActive} guardian(s)`);

  await typeInto(page, titleField, `QA training note ${stamp.slice(-4)}`);
  await page.select(audienceField, 'staff');
  const posted = await pressWrite(page, 'notice-post', 'notice-post', 'answered');
  check('the page posts a notice from its own controls', posted.ok && (await untilTrue(async () => (await call(page, 'GET', noticesPath)).json?.total === 1, 90_000)), `the button ${posted.pressed} after ${posted.attempts} attempt(s); note: ${posted.note.slice(0, 120)}`);
  const board1 = await call(page, 'GET', noticesPath);
  const staffNotice = (board1.json?.items ?? [])[0] ?? {};
  check('its readership is the roster the audience selects, counted now rather than stored at posting time', staffNotice.audience === 'staff' && staffNotice.recipients === staffActive && staffNotice.read_by === 0 && staffNotice.unread === staffNotice.recipients && staffNotice.receipts_on_row === 0, `recipients ${staffNotice.recipients} against ${staffActive} active non-guardian row(s) · read_by ${staffNotice.read_by} · ${staffNotice.receipts_on_row} receipt(s)`);
  check('the door marks the notice as one the caller’s own standing selects', (board1.json?.sees ?? []).includes(staffNotice.id) && staffNotice.read === false, `sees ${(board1.json?.sees ?? []).length} of ${board1.json?.total} listed · caller's receipt ${JSON.stringify(staffNotice.read)}`);
  const boardText1 = await text(page);
  check('the panel prints the door’s own rule sentence and its formula lines, not a paraphrase written here', has(boardText1, String(board1.json?.rule ?? '<<no rule published>>>').slice(0, 60)) && has(boardText1, String(board1.json?.formulas?.recipients ?? '<<no formula published>>>').slice(0, 60)), `${String(board1.json?.rule ?? '').slice(0, 90)} / ${String(board1.json?.formulas?.recipients ?? '').slice(0, 70)}`);
  check('the arithmetic badge subtracts the two figures it printed and finds the third holds', shouts(await page.$eval('[data-testid="notice-arithmetic-agrees"]', (node) => node.innerText), 'unread is recipients minus read_by'), await page.$eval('[data-testid="notice-arithmetic-agrees"]', (node) => node.innerText));
  check('and the listing badge counts its own rows before believing the door’s total', shouts(await page.$eval('[data-testid="notice-listed-agrees"]', (node) => node.innerText), 'total is the number of rows it printed'), await page.$eval('[data-testid="notice-listed-agrees"]', (node) => node.innerText));
  check('the notice stores no recipient anywhere in its answer', keyNames(board1.json ?? {}).filter((key) => /^recipient$|^user_id$|^to_user$|child_id|guardian/i.test(key)).length === 0, `${keyNames(board1.json ?? {}).length} key name(s) read, none of them a person`);

  // Painted before pressed: the door answers the write long before the page receives it back, and the three
  // checks below live inside a row the server component still has to deliver. An unpainted row would otherwise
  // read as `the button missing` — a red that names the walk's own assumption rather than the tier's behaviour.
  const noticeRows1 = await untilTrue(async () => (await page.$$('[data-notice]')).length === (board1.json?.total ?? 0), 60_000);
  check('the page repaints the notice it was told about before anything is pressed inside its row', noticeRows1 === true, `${(await page.$$('[data-notice]')).length} row(s) painted against the ${board1.json?.total} the door counts`);
  const readOnce = await pressWrite(page, `notice-read-${staffNotice.id}`, `notice-read-${staffNotice.id}`, 'answered');
  const afterRead = await call(page, 'GET', noticesPath);
  const readRow = (afterRead.json?.items ?? [])[0] ?? {};
  check('one receipt from the page moves exactly the two figures a receipt can move', readOnce.ok && readRow.read_by === 1 && readRow.receipts_on_row === 1 && readRow.unread === readRow.recipients - 1, `the button ${readOnce.pressed} · read_by ${readRow.read_by} · ${readRow.receipts_on_row} receipt row(s) · unread ${readRow.unread}`);
  const receiptCell = () => page.$eval(`tr[data-notice="${staffNotice.id}"]`, (node) => node.innerText).catch(() => '(the row is not on the page)');
  const receiptPainted = await untilTrue(async () => shouts(await receiptCell(), 'you have read it'), 60_000);
  check('and the row says the caller has read it, once the page has received its own receipt', receiptPainted === true, `notice ${staffNotice.id} · ${JSON.stringify((await receiptCell()).slice(0, 140))}`);
  const readTwice = await pressWrite(page, `notice-read-${staffNotice.id}`, `notice-read-${staffNotice.id}`, 'answered');
  const again = await call(page, 'POST', `${noticesPath}/${encodeURIComponent(staffNotice.id)}/read`);
  const afterSecond = await call(page, 'GET', noticesPath);
  const twiceRow = (afterSecond.json?.items ?? [])[0] ?? {};
  // The door's own word is in its answer, not in the page's note: a note only carries a refusal's figures, so
  // `already recorded` had one honest reader here and it is the door.
  check('reading it again is the same one row, and the door says which figure did not move', readTwice.pressed === 'clicked' && again.json?.receipt === 'already recorded' && again.json?.recorded_now === false && twiceRow.receipts_on_row === 1 && twiceRow.read_by === 1, `the button ${readTwice.pressed}; the door's word ${JSON.stringify(again.json?.receipt)} for recorded_now ${JSON.stringify(again.json?.recorded_now)} · ${twiceRow.receipts_on_row} receipt row(s), read_by ${twiceRow.read_by}`);

  const pinnedTitle = `QA pinned pitch closure ${stamp.slice(-4)}`;
  await clearField(page, titleField);
  await typeInto(page, titleField, pinnedTitle);
  await page.click(pinField);
  const pinnedPosted = await pressWrite(page, 'notice-post', 'notice-post', 'answered');
  const board2 = await call(page, 'GET', noticesPath);
  const pinnedRow = (board2.json?.items ?? []).find((row) => row.pinned) ?? {};
  // A second post through the same control answers with a note that is byte-identical to the first one, so the
  // fresh-note test pressWrite can offer is not evidence here; the row the door now holds, under the title typed
  // into this form, is.
  check('a pinned notice is pinned to its own audience, and the door counts them per audience', pinnedPosted.pressed === 'clicked' && pinnedRow.pinned === true && pinnedRow.title === pinnedTitle && board2.json?.pinned_by_audience?.staff === 1 && board2.json?.pinned_by_audience?.parents === 0, `the button ${pinnedPosted.pressed} · row ${JSON.stringify(pinnedRow.title)} pinned ${JSON.stringify(pinnedRow.pinned)} · pinned_by_audience ${JSON.stringify(board2.json?.pinned_by_audience)} of a ${noticeCaps.pinned_max} ceiling`);
  const pinnedPainted = await untilTrue(async () => (await page.$$(`tr[data-notice="${pinnedRow.id}"]`)).length === 1, 60_000);
  const pinnedCell = pinnedPainted === true ? await page.$eval(`tr[data-notice="${pinnedRow.id}"] td`, (node) => node.innerText) : '(the row the door pinned never painted)';
  check('the page prints a pinned badge on the row the door pinned, and the door’s per-audience count is the board’s own rows counted again', pinnedPainted === true && pinnedCell.toLowerCase().includes('pinned') && shouts(await page.$eval('[data-testid="notice-pinned-agrees"]', (node) => node.innerText), 'pinned counts per audience are the board'), `row ${pinnedRow.id} opens with ${JSON.stringify(pinnedCell.slice(0, 40))}`);

  const guardianTitle = `QA guardian notice ${stamp.slice(-4)}`;
  await clearField(page, titleField);
  await typeInto(page, titleField, guardianTitle);
  await page.select(audienceField, 'parents');
  const toGuardians = await pressWrite(page, 'notice-post', 'notice-post', 'answered');
  const board3 = await call(page, 'GET', noticesPath);
  const guardianRow = (board3.json?.items ?? []).find((row) => row.audience === 'parents') ?? {};
  check('a notice posted to guardians selects the roster’s guardian rows and nobody else', toGuardians.pressed === 'clicked' && guardianRow.title === guardianTitle && guardianRow.recipients === parentActive && !(board3.json?.sees ?? []).includes(guardianRow.id), `the button ${toGuardians.pressed} · ${guardianRow.recipients} recipient(s) over ${parentActive} active guardian row(s); the director is not among them`);
  const guardianPainted = await untilTrue(async () => (await page.$$(`tr[data-notice="${guardianRow.id}"]`)).length === 1, 60_000);
  check('and the row the guardians were selected into is on the page, refused or not', guardianPainted === true, `row ${guardianRow.id} painted: ${guardianPainted}`);
  const outside = await pressWrite(page, `notice-read-${guardianRow.id}`, `notice-read-${guardianRow.id}`, 'refused with');
  check('and the button a caller is not addressed by stays live, answering the refusal rather than hiding it', outside.ok && /refused with 422/.test(outside.note) && has(outside.note, 'not_an_audience') && has(outside.note, 'parents'), outside.note.slice(0, 170));
  check('the row is listed with its readership and says it was not addressed to this standing', shouts(await text(page), 'not addressed to your standing'), `notice ${guardianRow.id}`);
  check('so the panel prints the selection it made for the caller, not a count of the rows on the board', shouts(await page.$eval('[data-testid="notice-sees"]', (node) => node.innerText), `${board3.json?.sees?.length ?? '?'} of ${board3.json?.total ?? '?'} listed select you right now`), await page.$eval('[data-testid="notice-sees"]', (node) => node.innerText));

  const staffHeld = (board3.json?.items ?? []).filter((row) => row.audience === 'staff').length;
  const boardHeld = board3.json?.announcements_held ?? 0;
  await open(page, `${tenant.path}?audience=staff`);
  const filtered = await call(page, 'GET', `${noticesPath}?audience=staff`);
  check('the filter goes through the door: it narrows the rows, never what the tenant holds', filtered.status === 200 && filtered.json?.total === staffHeld && filtered.json?.announcements_held === boardHeld && shouts(await text(page), 'filtered to staff'), `${filtered.json?.total} listed against ${boardHeld} held, of which ${staffHeld} were posted to staff`);
  check('and a filtered board still prints the readership of the rows it kept', (filtered.json?.items ?? []).every((row) => row.audience === 'staff' && row.recipients === staffActive), `${(filtered.json?.items ?? []).length} row(s), each over ${staffActive} selected member(s)`);
  await open(page, tenant.path);
  await untilTrue(async () => (await page.$$('[data-notice]')).length === boardHeld, 60_000);

  const erasedNotice = await pressWrite(page, `notice-erase-${staffNotice.id}`, `notice-erase-${staffNotice.id}`, 'answered');
  const board4 = await call(page, 'GET', noticesPath);
  const erasedRead = await call(page, 'GET', `${noticesPath}/${encodeURIComponent(staffNotice.id)}`);
  check('erasing a notice takes it off the board and answers its own address as absence, not as somebody else’s notice', erasedNotice.ok && erasedRead.status === 404 && has(JSON.stringify(erasedRead.json ?? ''), 'no_such_announcement') && board4.json?.total === boardHeld - 1 && (board4.json?.items ?? []).every((row) => row.id !== staffNotice.id), `HTTP ${erasedRead.status} at its own address · ${board4.json?.total} notice(s) left of ${boardHeld}`);
  check('the panel prints the tier’s own limitation sentence rather than a paraphrase of it', has(await text(page), String(rulebook.announcement_limitation ?? '<<no limitation published>>>').slice(0, 60)), String(rulebook.announcement_limitation ?? '').slice(0, 120));
  await shot(page, 'notices-after-the-erase');

  // ----------------------------------------------------------- §42's meter, on the page that just spent it
  const meterPath = `/api/v1/club/${encodeURIComponent(ident)}/entitlements`;
  const meterDoor = await call(page, 'GET', meterPath);
  const capabilities = await call(page, 'GET', '/api/v1/entitlements/capabilities');
  const storedCeiling = capabilities.json?.matrix?.free?.reports_saved?.[0] ?? -1;
  check('the tenant’s own ceiling door answers the owner, names the plan it is metered against, and stores nothing of its own', meterDoor.status === 200 && meterDoor.json.plan === 'free' && meterDoor.json.organization === ident && typeof meterDoor.json.role === 'string', `HTTP ${meterDoor.status} plan ${JSON.stringify(meterDoor.json?.plan)} role ${JSON.stringify(meterDoor.json?.role)}`);
  await untilTrue(async () => {
    const spent = (await call(page, 'GET', meterPath)).json?.items?.find((row) => row.feature === 'reports_saved');
    return spent?.used === 1 && spent?.acts === 1;
  }, 90_000);
  const meter = await meterOf(page);
  const spentMeter = meter.reports_saved ?? {};
  check('the ceiling the page prints is the ceiling the matrix stores, read through the public door', spentMeter.limit === storedCeiling && storedCeiling > 0, `page ${spentMeter.limit}, matrix ${storedCeiling}`);
  check('one report saved from the page is one act on the meter, and the act row is named', spentMeter.used === 1 && spentMeter.acts === 1 && spentMeter.period === 'day', JSON.stringify(saved));
  check('the remainder is the subtraction the two printed columns imply, not a figure anybody stored', spentMeter.remaining === Math.max(0, spentMeter.limit - spentMeter.used) && (await page.$eval('[data-meter-check]', (node) => node.getAttribute('data-meter-check'))) === 'agrees', `limit ${spentMeter.limit} − used ${spentMeter.used} vs printed ${spentMeter.remaining}`);
  const refusedColumn = Object.entries(meter).filter(([, row]) => /^yes/.test(row.enforced ?? '')).map(([feature]) => feature);
  check('exactly one feature is refused on today, the table holds one row per item the door sent, and an account’s own ceiling is not among them', refusedColumn.join(',') === 'reports_saved' && Object.keys(meter).length === (meterDoor.json.items ?? []).length && !('organizations' in meter), `${refusedColumn.join(',')} of ${Object.keys(meter).length} row(s), door sent ${(meterDoor.json.items ?? []).length}`);
  const meterBody = await text(page);
  const paymentShaped = keyNames(meterDoor.json).filter((key) => /price|currency|amount|fee|billing|provider|checkout|trial/i.test(key));
  check('no payment-shaped field is in the door an account reads, and the panel prints the sentence that says so', paymentShaped.length === 0 && has(squeeze(meterBody), squeeze(meterDoor.json.no_payment)), `${paymentShaped.length} key(s): ${paymentShaped.slice(0, 3).join(',')}`);
  check('the account that owns the tenant is a separate subject, and the page says which one it is showing', (await page.$eval('[data-account-meter]', (node) => node.getAttribute('data-account-meter'))).split(',').includes('organizations'), `tenant rows: ${Object.keys(meter).join(', ')}`);

  const dayBefore = new Date(Date.parse(`${doorToday}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10);
  // Both ends, not just the one being moved: the board's filter navigations remount this form, so an assertion
  // that the *other* date still holds whatever an earlier section typed is the walk assuming a page state
  // instead of setting one. A reversed window has to be a reversed window on its own terms.
  await clearField(page, windowStart);
  await typeInto(page, windowStart, doorToday);
  await clearField(page, windowEnd);
  await typeInto(page, windowEnd, dayBefore);
  const reversed = await pressWrite(page, 'report-save', 'report-save', 'refused with');
  check('a window that ends before it starts is refused, and the sentence names both dates', reversed.ok && /refused with 4\d\d/.test(reversed.note) && has(reversed.note, 'window_reversed') && has(reversed.note, dayBefore) && has(reversed.note, doorToday), `${reversed.note.slice(0, 170)} (the button ${reversed.pressed})`);
  check('and a refused question is not a row: the list still holds one', (await call(page, 'GET', reportsPath)).json?.total === 1, 'one before and after the refusal');
  const afterRefusal = (await call(page, 'GET', meterPath)).json?.items?.find((row) => row.feature === 'reports_saved') ?? {};
  check('and it spends nothing on the meter either: the same act, the same used figure', afterRefusal.used === 1 && afterRefusal.acts === 1, JSON.stringify(afterRefusal));

  const familyLog = await call(pageB, 'GET', sessionsPath);
  check('a guardian reads the sessions their own child was at, through the right the door names', familyLog.status === 200 && familyLog.json.total === 1 && familyLog.json.read_through === 'plan.read_own_child', `${familyLog.json?.total} row(s) via ${familyLog.json?.read_through}`);
  check('while staff read the tenant’s whole log through the other right', logged.json.read_through === 'plan.read_all', logged.json.read_through);
  const familyMeter = await call(pageB, 'GET', meterPath);
  check('a guardian reads the tenant’s ceiling too, because it is the standing they hold rather than a staff right', familyMeter.status === 200 && familyMeter.json.role === 'parent' && has(String(familyMeter.json?.read_through ?? ''), 'standing'), `HTTP ${familyMeter.status}, role ${JSON.stringify(familyMeter.json?.role)}, through ${JSON.stringify(familyMeter.json?.read_through)}`);
  const familyReport = await call(pageB, 'GET', reportsPath);
  check('and the same saved question is cut to their child for them, on the row nobody rewrote', familyReport.status === 200 && familyReport.json.items[0].body.sessions === 1 && familyReport.json.items[0].body.appearances?.[child.slug] === 1 && Object.keys(familyReport.json.items[0].body.appearances ?? {}).join(',') === child.slug, JSON.stringify(familyReport.json?.items?.[0]?.body?.appearances ?? null));

  await open(page, tenant.path);
  const erasedQuestion = await pressWrite(page, '[data-act="report-erase"]', 'report-erase', 'erased');
  check('the page erases a question from the row control it printed', erasedQuestion.ok && (await untilTrue(async () => (await call(page, 'GET', reportsPath)).json?.total === 0, 90_000)), `${erasedQuestion.note.slice(0, 140)} (after ${erasedQuestion.attempts} attempt(s), the button ${erasedQuestion.pressed})`);
  const erasedSession = await pressWrite(page, '[data-act="session-erase"]', 'session-erase', 'erased');
  check('and the session row likewise', erasedSession.ok && (await untilTrue(async () => (await call(page, 'GET', sessionsPath)).json?.total === 0, 90_000)), `${erasedSession.note.slice(0, 140)} (after ${erasedSession.attempts} attempt(s), the button ${erasedSession.pressed})`);
  check('the door answers the erased session as an absence rather than an empty row', (await call(page, 'GET', `${sessionsPath}/${encodeURIComponent(session.id)}`)).status === 404, 'no_such_session');
  check('and erasing a session left the sheet and the child on it alone', (await call(page, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`)).json?.total === 1, 'the plan the walk opened is still the plan the walk opened');
  // The allowance a saved report spent comes back with the report: the act row is deleted beside the question,
  // so a tenant that erased its only report has tomorrow's ceiling today. Wait on the painted table itself, not on
  // the door — the refresh the erase triggers repaints later than the note lands, and a check that read the table
  // the moment the door agreed was measuring the walk's own race rather than the product's.
  await untilTrue(async () => {
    const painted = (await meterOf(page)).reports_saved;
    return painted?.used === 0 && painted?.acts === 0;
  }, 90_000);
  const refunded = await meterOf(page);
  const refundedDoor = (await call(page, 'GET', meterPath)).json?.items?.find((item) => item.feature === 'reports_saved') ?? {};
  check('erasing the question gives the ceiling back, on the page and on the door alike', (refunded.reports_saved ?? {}).used === 0 && (refunded.reports_saved ?? {}).acts === 0 && (refunded.reports_saved ?? {}).remaining === (refunded.reports_saved ?? {}).limit && refundedDoor.used === 0 && refundedDoor.acts === 0, JSON.stringify({ page: refunded.reports_saved ?? {}, door: { used: refundedDoor.used, acts: refundedDoor.acts, remaining: refundedDoor.remaining, limit: refundedDoor.limit } }));
  await shot(page, 'sessions-and-reports');

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
  check('and both doors behind those pages answer absent too, including the ceiling one nobody may read on somebody else’s tenant', (await call(pageC, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).status === 404 && (await call(pageC, 'GET', `/api/v1/club/academy/${encodeURIComponent(ident)}/plans`)).status === 404 && (await call(pageC, 'GET', meterPath)).status === 404, 'page, plan, tenant door, academy door, meter door');
  const parentRights = clubRules.matrix.matrix.parent;
  check('a guardian holds four rights, and the fourth of them is the board they were added to read', parentRights.length === 4 && parentRights.includes('consent.grant_own') && parentRights.includes('announce.read'), parentRights.join(', '));

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
  const memberGrant = asMember.json?.my_grant ?? null;
  check('the rights a guardian holds are printed from their own grant, not the owner’s', shouts(memberBody, `${memberGrant?.permissions?.length ?? '?'} of ${clubRules.matrix.permissions.length} rights`) && memberGrant?.role === 'parent' && memberGrant?.permissions?.length === parentRights.length, `door HTTP ${asMember.status}, parent holds ${JSON.stringify(memberGrant?.permissions?.length ?? null)} of ${clubRules.matrix.permissions.length}`);
  check('their grant says why, in the door’s sentence', memberGrant !== null && has(squeeze(memberBody), squeeze(memberGrant.why ?? '')), String(memberGrant?.why ?? '(none)').slice(0, 60));
  check('a page does not disable a write control by guessing their role', (await pageB.$$eval('[data-testid="consent-grant"],[data-testid="plan-open"]', (nodes) => [nodes.length, nodes.every((node) => !node.disabled)]))[0] === 2 && (await pageB.$$eval('[data-testid="consent-grant"],[data-testid="plan-open"]', (nodes) => nodes.every((node) => !node.disabled))) === true, 'both buttons are live for a member; the API decides what they may write');
  await open(page, tenant.path);
  const ownerView = await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`);
  check('the owner’s table re-reads two active members', ownerView.json.counts.active_members === 2 && ownerView.json.members.length === 2, `${ownerView.json.counts.active_members} active of ${ownerView.json.counts.member_limit}`);
  check('the new member is on the row list with the standing they accepted', ownerView.json.members.some((row) => row.email === INVITEE && row.role === 'parent'), 'parent');
  check('the tenant page prints the §39 limits the same response carries', (ownerView.json.limitations ?? []).length > 0 && shouts(await text(page), `${ownerView.json.limitations.length} limits the API states on this very response`), `${(ownerView.json.limitations ?? []).length} sentences`);
  const memberClose = await call(pageB, 'DELETE', `/api/v1/club/${encodeURIComponent(ident)}`, { confirm: TENANT });
  check('a member may not close the tenant: the page’s own door answers them', memberClose.status === (clubRules.refusal_answers.insufficient_role ?? 403), `HTTP ${memberClose.status} ${JSON.stringify(memberClose.json ?? null).slice(0, 70)}`);
  check('and the tenant is still there to be read afterwards', (await call(page, 'GET', `/api/v1/club/${encodeURIComponent(ident)}`)).status === 200);

  // ------------------------------------------------- §39's board, read by the standing the audience selects
  // The guardian accepted their invitation after the notices above were posted, so the readership a notice carries
  // is the figure that moved — which is the whole claim this tier makes about a predicate over the roster rather
  // than a stored distribution list.
  await open(pageB, tenant.path);
  await untilTrue(async () => (await pageB.$$('[data-notice]')).length > 0, 60_000);
  const guardianRowsNow = (ownerView.json?.members ?? []).filter((row) => row.status === 'active' && row.role === 'parent').length;
  const staffRowsNow = (ownerView.json?.members ?? []).filter((row) => row.status === 'active' && row.role !== 'parent').length;
  const ownerBoard = await call(page, 'GET', noticesPath);
  const guardianBoard = await call(pageB, 'GET', noticesPath);
  const addressedToGuardians = (guardianBoard.json?.items ?? []).find((row) => row.audience === 'parents') ?? {};
  check('a notice posted to guardians selects the guardian who joined after it was posted, because its readership is the roster as it stands', ownerBoard.status === 200 && guardianBoard.status === 200 && addressedToGuardians.recipients === guardianRowsNow && (guardianBoard.json?.sees ?? []).join(',') === addressedToGuardians.id, `recipients ${addressedToGuardians.recipients} over ${guardianRowsNow} active guardian row(s); the guardian is addressed by ${(guardianBoard.json?.sees ?? []).length} of ${guardianBoard.json?.total} listed`);
  check('both accounts are listed the same rows, and the only thing their standing changes is which of them select', (ownerBoard.json?.items ?? []).map((row) => row.id).join(',') === (guardianBoard.json?.items ?? []).map((row) => row.id).join(',') && (ownerBoard.json?.sees ?? []).length === (ownerBoard.json?.items ?? []).filter((row) => row.audience !== 'parents').length, `the director sees ${(ownerBoard.json?.sees ?? []).length} of ${(ownerBoard.json?.items ?? []).length} listed over ${staffRowsNow} staff-side row(s), the guardian sees ${(guardianBoard.json?.sees ?? []).length}`);
  const guardianReads = await pressWrite(pageB, `notice-read-${addressedToGuardians.id}`, `notice-read-${addressedToGuardians.id}`, 'answered');
  const readBack = await call(pageB, 'GET', `${noticesPath}/${encodeURIComponent(addressedToGuardians.id)}`);
  check('the guardian’s own receipt lands as one read of one, and the detail door says the notice was addressed to them', guardianReads.ok && readBack.json?.announcement?.read_by === 1 && readBack.json?.announcement?.unread === 0 && readBack.json?.addressed_to_caller === true, `read_by ${readBack.json?.announcement?.read_by} · unread ${readBack.json?.announcement?.unread} · addressed ${JSON.stringify(readBack.json?.addressed_to_caller)}`);
  const roleRefusal = clubRules.refusal_answers?.insufficient_role ?? 403;
  const guardianPosts = await pressWrite(pageB, 'notice-post', 'notice-post', 'refused with');
  check('a guardian who may read the board cannot post to it, and the answer comes from the matrix rather than a guess made here', guardianPosts.ok && has(guardianPosts.note, `refused with ${roleRefusal}`) && has(guardianPosts.note, 'insufficient_role'), `${guardianPosts.note.slice(0, 150)} (matrix answers ${roleRefusal})`);
  await shot(pageB, 'notices-as-a-guardian');

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
