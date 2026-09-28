/**
 * M10's creator walk: two accounts, a production build, and the claim that a guide is an address while every
 * figure beside it is counted from rows.
 *
 *   api tier:  http://127.0.0.1:8741   (DATABASE_URL=<scratch file> uvicorn app.main:app --port 8741)
 *   web tier:  http://127.0.0.1:3218   (API_INTERNAL_URL=http://127.0.0.1:8741 next start -p 3218)
 *   QA_BASE=http://127.0.0.1:3218 node scripts/qa-creator.mjs
 *
 * What this walk is willing to fail on:
 *
 * * **the page's own controls must move the door's figures.** A profile the page says it amended has to be amended
 *   at the door, a guide it says it published has to be a row, and a citation it says it recorded has to resolve to
 *   a chunk — every press is re-read through the door rather than trusted from the note it painted;
 * * **the panel that owns the press answers it.** Three panels write here, so a refused guide or citation has to be
 *   answered beside the form that asked: this page shipped with one runner for the whole workbench, which put every
 *   note in the profile panel, and the walk reads each note out of the panel whose control was pressed;
 * * **the shelf is this account's.** The door's unscoped listing is everybody's public shelf while the panel is
 *   titled "your shelf" beside an Erase button, so the walk has a second account publish a guide and refuses to let
 *   it appear here;
 * * **reach is answered as absence.** A `followers` guide — and the citations on it — earn `no_such_guide`/404 for a
 *   reader with no follow row, and are reachable the moment §35's own follow door writes one; and no door in this
 *   tier answers 403 or 400 anywhere in the walk, because there is no permission matrix here to consult;
 * * **no number in this walk is invented here.** The ceilings, the sections, the visibilities, the refusal codes and
 *   their statuses all come out of `GET /api/v1/creator/rules`, the same door the page reads.
 *
 * Env overrides: QA_BASE, QA_DIST, CHROME_PATH.
 */

import { mkdir, readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import puppeteer from 'puppeteer-core';

const BASE = (process.env.QA_BASE ?? 'http://127.0.0.1:3218').trim();
const DIST = (process.env.QA_DIST ?? '.next-ci').trim();
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };
const PASSWORD = 'creator-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const AUTHOR = `qa-creator-${stamp}@footballos.test`;
const READER = `qa-stranger-${stamp}@footballos.test`;
const results = [];
const consoleErrors = [];
const knocks = [];
const shots = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail: String(detail) });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${String(detail).slice(0, 190)}` : ''}`);
}

const has = (body, needle) => String(body).includes(String(needle));
const squeeze = (value) => String(value).replace(/\s+/g, '');
/** Eyebrows and headers shout in CSS, so a needle matched against them sheds its case. */
const shouts = (body, needle) => squeeze(body).toUpperCase().includes(squeeze(needle).toUpperCase());

/** A creator control, by the attribute the page gives it. */
const C = (name) => `[data-creator-${name}]`;
const rowOf = (guideId) => `tr[data-creator-guide="${guideId}"]`;
const citationOf = (id) => `tr[data-creator-citation="${id}"]`;

async function shot(page, name) {
  const file = `${stamp}-creator-${name}.png`;
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
  const want = squeeze(needle).toUpperCase();
  try {
    await page.waitForFunction((target) => (document.body?.innerText ?? '').replace(/\s+/g, '').toUpperCase().includes(target), { timeout, polling: 400 }, want);
    return true;
  } catch {
    return false;
  }
}

async function untilTrue(read, timeout = 60_000, step = 500) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if ((await read()) === true) return true;
    await new Promise((done) => setTimeout(done, step));
  }
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

/** Every door answer is recorded, so "this tier never answers 403 or 400" is a census over the walk's own knocks. */
async function call(page, method, path, body) {
  let last = null;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    last = await askOnce(page, method, path, body);
    knocks.push({ method, path: String(path).split('?')[0], status: last.status });
    if (last.status !== 429) return last;
    await new Promise((done) => setTimeout(done, Math.min(Math.max(last.retry ?? 2, 2), 20) * 1000));
  }
  return last;
}

async function typeInto(page, selector, value) {
  await page.waitForSelector(selector, { visible: true, timeout: 20_000 });
  await page.click(selector);
  if (value) await page.type(selector, String(value), { delay: 4 });
}

async function clearField(page, selector) {
  await page.waitForSelector(selector, { visible: true, timeout: 20_000 });
  await page.click(selector, { clickCount: 3 });
  await page.keyboard.press('Backspace');
}

function press(page, selector) {
  return page.evaluate((sel) => {
    const button = document.querySelector(sel);
    if (!button) return 'missing';
    if (button.disabled) return 'disabled';
    button.click();
    return 'clicked';
  }, selector);
}

function noteFor(page, action) {
  return page.$eval(`[data-note="${action}"]`, (node) => node.innerText.replace(/\s+/g, ' ').trim()).catch(() => '');
}

/**
 * Press a write control and read the note *that panel* paints, waiting the tier's rate door out.
 *
 * The note is looked up by the action the runner recorded, and each panel now owns its own runner — so a check on
 * the guide's note cannot be satisfied by the profile panel's, which is exactly the defect this walk is here to
 * catch. A refused press is held to the same standard as an accepted one: the note must have changed and must name
 * the code the door answered with.
 */
async function pressWrite(page, selector, action, want = '', tries = 4) {
  for (let attempt = 1; attempt <= tries; attempt += 1) {
    const before = await noteFor(page, action);
    const pressed = await press(page, selector);
    if (pressed !== 'clicked') return { ok: false, pressed, note: `(the control ${pressed})`, attempts: attempt, changed: false };
    let note = '';
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      note = await noteFor(page, action);
      const wantMatched = squeeze(want).length === 0 || squeeze(note).toUpperCase().includes(squeeze(want).toUpperCase());
      if (note.length > 0 && note !== before && wantMatched && !/429/.test(note)) return { ok: true, pressed, note, attempts: attempt, changed: true };
      await new Promise((done) => setTimeout(done, 300));
    }
    if (!/429/.test(note)) return { ok: false, pressed, note: note === '' ? '(no note painted there)' : note, attempts: attempt, changed: note !== before };
    await new Promise((done) => setTimeout(done, 25_000));
  }
  return { ok: false, pressed: 'limited', note: '(every attempt was answered 429 by the rate door)', attempts: tries, changed: false };
}

/** The `[data-creator-guide]` rows of the shelf, with their cells read the way a person reads them. */
function rowsOf(page, attribute) {
  return page.$$eval(`tr[data-${attribute}]`, (rows, name) => rows.map((row) => ({ key: row.getAttribute(`data-${name}`), cells: [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim()) })), attribute);
}

/** The page re-reads its own shelf after a write, so a row check waits for the paint rather than the press. */
async function waitForRows(page, attribute, want, timeout = 45_000) {
  return untilTrue(async () => (await rowsOf(page, attribute)).length === want, timeout);
}

/**
 * Re-open the studio, and wait until it is the published panel with `rows` guides painted.
 *
 * The reload is not decoration: a runner paints the same sentence for the same outcome, so a walk that pressed
 * "publish" and then "amend" would be comparing two identical notes and could not tell a fresh answer from the one
 * still standing. Opening the page again clears the panel's note, which makes the next note provably this press's.
 */
async function openStudio(page, rows = null, timeout = 60_000) {
  await open(page, '/creator');
  await untilTrue(async () => (await page.$eval(C('profile'), (node) => node.getAttribute('data-creator-profile')).catch(() => '')) === 'published', timeout);
  if (rows !== null) await waitForRows(page, 'creator-guide', rows, timeout);
}

function metaRobots(page) {
  return page.$eval('meta[name="robots"]', (node) => node.getAttribute('content') ?? '').catch(() => '');
}

async function register(page, email, displayName) {
  let last = null;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    last = await call(page, 'POST', '/api/v1/auth/register', { accepts_data_policy: true, display_name: displayName, email, password: PASSWORD, role: 'player' });
    if (last.status !== 429) return last;
    await new Promise((done) => setTimeout(done, 25_000));
  }
  return last;
}
async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  // ------------------------------------------------------------- the vocabulary door, with no cookie at all
  const rulesResponse = await fetch(`${BASE}/api/v1/creator/rules`, { headers: { accept: 'application/json' } });
  const rules = rulesResponse.ok ? await rulesResponse.json() : null;
  const caps = rules?.caps ?? {};
  const answers = rules?.refusal_answers ?? {};
  check('the rules door answers a caller with no session and publishes the eleven doors it declares', rulesResponse.status === 200 && (rules?.routes ?? []).length === 11, `HTTP ${rulesResponse.status}; ${(rules?.routes ?? []).length} route(s) published`);
  check('and the code list it answers with is the list it publishes', Object.keys(answers).length === (rules?.refusals ?? []).length && (rules?.refusals ?? []).every((code) => code in answers), `${Object.keys(answers).length} answers for ${(rules?.refusals ?? []).length} codes`);
  const statuses = [...new Set(Object.values(answers))];
  check('every published code earns 404, 409 or 422 — no 403 without a matrix, and no 400 fall-through', statuses.every((value) => [404, 409, 422].includes(value)), `statuses ${statuses.sort().join(', ')}`);
  const anonymousProfile = await fetch(`${BASE}/api/v1/creator/profile`, { headers: { accept: 'application/json' } });
  check('a private door answers a stranger 401 before any service code runs, rather than 404', anonymousProfile.status === 401, `HTTP ${anonymousProfile.status}`);

  const buildId = (await readFile(resolve(dirname(fileURLToPath(import.meta.url)), `../${DIST}/BUILD_ID`), 'utf8')).trim();
  const servedHtml = await (await fetch(`${BASE}/world`)).text();
  check('the page this walk drives is the build it just compiled, by its own BUILD_ID', has(servedHtml, buildId), `BUILD_ID ${buildId}`);

  const robots = await (await fetch(`${BASE}/robots.txt`)).text();
  const sitemap = await (await fetch(`${BASE}/sitemap.xml`)).text();
  check('robots.txt served by this build keeps /creator out of the crawl', has(robots, 'Disallow: /creator'), robots.split('\n').filter((line) => /creator|community/.test(line)).join(' | '));
  check('and the sitemap does not offer it', !has(sitemap, '/creator'), `${(sitemap.match(/<loc>/g) ?? []).length} loc(s), none of them /creator`);

  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const authorPage = await browser.newPage();
  await authorPage.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  watch(authorPage, 'author');

  await open(authorPage, '/creator');
  check('/creator sends a caller with no session to the login screen, naming where they were headed', authorPage.url().includes('/login') && authorPage.url().includes('creator'), authorPage.url());

  const signed = await register(authorPage, AUTHOR, 'QA Creator');
  check('an account registers through the proxy the page itself uses', signed.status === 201, `HTTP ${signed.status}`);
  const me = await call(authorPage, 'GET', '/api/v1/auth/me');
  const authorId = String(me.json?.id ?? '');
  check('and the session that lands belongs to the account the walk just made', authorId.startsWith('usr_'), `account ${authorId}`);

  await open(authorPage, '/creator');
  check('the page paints its own head and calls itself the creator studio', shouts(await text(authorPage), 'Creator Studio'));
  const noindex = await metaRobots(authorPage);
  check('and carries noindex, nofollow of its own, as robots.txt already said', /noindex/.test(noindex) && /nofollow/.test(noindex), noindex || '(no robots meta)');
  const studio = await text(authorPage);
  check('the vocabulary panel prints the ceilings the door publishes rather than a copy typed into the page', shouts(studio, `${caps.guide_max} per creator`) && shouts(studio, `${caps.citation_note_max}-character notes`) && shouts(studio, caps.visibility_rule ?? 'no visibility rule published'), `guide_max ${caps.guide_max}, note_max ${caps.citation_note_max}`);
  const painted = await authorPage.$$eval('tr[data-refusal]', (rows) => rows.map((row) => ({ code: row.getAttribute('data-refusal'), cells: [...row.querySelectorAll('td')].map((cell) => cell.innerText.trim()) })));
  check('the refusal table on the page is the table the door published, code for code and status for status', painted.length === Object.keys(answers).length && painted.every((row) => String(answers[row.code]) === row.cells[1]), `${painted.length} row(s) painted for ${Object.keys(answers).length} published code(s)`);
  check('and the page says which §42 features this tier names, and that no door refuses on them yet', shouts(studio, (rules?.entitlement_features ?? []).join(', ')) && shouts(studio, 'no door refuses on yet'), `${(rules?.entitlement_features ?? []).length} feature(s) named`);
  await shot(authorPage, 'studio');
  // ------------------------------------------------------------------------------- the profile, written from here
  const empty = await authorPage.$eval(C('profile'), (node) => node.getAttribute('data-creator-profile')).catch(() => '(no panel)');
  check('the profile panel says nothing is published yet, which is the door\'s own answer for an account that has written none', empty === 'none', `data-creator-profile=${empty}`);

  await typeInto(authorPage, C('slug'), `qa-creator-${stamp}`);
  await typeInto(authorPage, C('headline'), 'writes about pressing');
  await typeInto(authorPage, C('bio'), 'a coach who writes things down');
  const published = await pressWrite(authorPage, C('publish-profile'), 'profile', 'answered');
  check('the page publishes the profile from its own controls, and the door is what answered', published.ok, `the control ${published.pressed} after ${published.attempts} attempt(s); note: ${published.note.slice(0, 140)}`);
  const profileAtDoor = (await call(authorPage, 'GET', '/api/v1/creator/profile')).json ?? {};
  check('the door holds the profile the page pressed for, slug and headline and all', profileAtDoor.slug === `qa-creator-${stamp}` && profileAtDoor.headline === 'writes about pressing', `slug ${profileAtDoor.slug}`);
  check('and the panel repaints as a published one, naming the slug the door answered with', (await untilTrue(async () => (await authorPage.$eval(C('profile'), (node) => node.getAttribute('data-creator-profile')).catch(() => '')) === 'published')) && shouts(await text(authorPage), `Published as qa-creator-${stamp}`), 'data-creator-profile=published');

  await openStudio(authorPage, 0);
  await clearField(authorPage, C('headline'));
  await typeInto(authorPage, C('headline'), 'now amended');
  const amended = await pressWrite(authorPage, C('publish-profile'), 'profile', 'answered');
  const afterAmend = (await call(authorPage, 'GET', '/api/v1/creator/profile')).json ?? {};
  check('the amend the page offers really amends: the headline moves at the door', amended.ok && afterAmend.headline === 'now amended', `headline now ${JSON.stringify(afterAmend.headline)}`);
  check('and the field the page never touched keeps its value instead of being blanked by the amendment', afterAmend.bio === 'a coach who writes things down', `bio ${JSON.stringify(afterAmend.bio)}`);
  check('and the address did not move, so a link a reader already holds still resolves', afterAmend.slug === profileAtDoor.slug, `slug ${afterAmend.slug}`);

  // The page caps its own inputs, so a past-the-ceiling headline cannot be typed into it: the refusal is knocked on
  // at the door, whose answer is the one the panel would print if a form without the cap ever reached it.
  const tooLong = 'x'.repeat(Number(caps.profile_headline_max) + 1);
  const headlineRefusal = await call(authorPage, 'POST', '/api/v1/creator/profile', { headline: tooLong });
  const refusalDetail = headlineRefusal.json?.detail ?? {};
  check('a headline past the ceiling is refused with the ceiling and the length beside the sentence', headlineRefusal.status === 422 && refusalDetail.code === 'profile_headline' && refusalDetail.max === caps.profile_headline_max && refusalDetail.length === tooLong.length, `HTTP ${headlineRefusal.status} · ${refusalDetail.code} max=${refusalDetail.max} length=${refusalDetail.length}`);
  check('and that refused press wrote nothing: the door still holds the amended headline', ((await call(authorPage, 'GET', '/api/v1/creator/profile')).json ?? {}).headline === 'now amended');
  // --------------------------------------------------------------------------- the shelf, and whose shelf it is
  await typeInto(authorPage, C('guide-title'), 'defending a low block');
  await authorPage.select(C('guide-section'), 'plan');
  await authorPage.select(C('guide-visibility'), 'public');
  const framed = await pressWrite(authorPage, C('publish-guide'), 'guide', 'answered');
  check('the page frames a guide from its own controls, and the guide panel is where the answer lands', framed.ok, `the control ${framed.pressed} after ${framed.attempts} attempt(s); note: ${framed.note.slice(0, 140)}`);
  const shelfOne = (await call(authorPage, 'GET', `/api/v1/creator/guides?creator=${authorId}`)).json ?? {};
  check('the door holds the guide the page pressed for, authored by the account that pressed', (shelfOne.items ?? []).length === 1 && (shelfOne.items ?? [])[0]?.author?.id === authorId, `${(shelfOne.items ?? []).length} item(s) on the door's own shelf`);
  check('and the shelf panel repaints with one row, on the read that follows the write', await waitForRows(authorPage, 'creator-guide', 1));
  const first = (shelfOne.items ?? [])[0] ?? {};
  const cells = (await rowsOf(authorPage, 'creator-guide'))[0]?.cells ?? [];
  check('every figure in the painted row is the door\'s own, cell for cell', cells[1] === first.section && cells[2] === first.visibility && cells[3] === String(first.citations) && cells[4] === String(first.moved) && cells[5] === String(first.tokens) && has(cells[0], first.title) && has(cells[0], first.slug), `painted ${JSON.stringify(cells.slice(0, 6))}`);

  await openStudio(authorPage, 1);
  await typeInto(authorPage, C('guide-title'), 'pressing traps, and where they fail');
  await authorPage.select(C('guide-section'), 'tactic');
  await authorPage.select(C('guide-visibility'), 'followers');
  const framedTwo = await pressWrite(authorPage, C('publish-guide'), 'guide', 'answered');
  const shelfTwo = (await call(authorPage, 'GET', `/api/v1/creator/guides?creator=${authorId}`)).json ?? {};
  const followersGuide = (shelfTwo.items ?? []).find((item) => item.visibility === 'followers') ?? {};
  const publicGuide = (shelfTwo.items ?? []).find((item) => item.visibility === 'public') ?? {};
  check('a second guide publishes at a visibility a stranger will have to be kept out of', framedTwo.ok && !!followersGuide.id && !!publicGuide.id, `${(shelfTwo.items ?? []).map((item) => item.visibility).join(', ') || 'no items'}`);
  check('and the author\'s own shelf holds both, the followers-only one included', await waitForRows(authorPage, 'creator-guide', 2) && shouts(await text(authorPage), '2 guides on your shelf'), 'two rows, both visibilities');

  // A browser context of its own. `browser.newPage()` puts the second account in the default jar, which is the
  // first account's: registering the stranger there replaces the author's session cookies, and every read of
  // `/creator` after that answers as the stranger while the walk still believes it is reading the author's page.
  const readerContext = await browser.createBrowserContext();
  const readerPage = await readerContext.newPage();
  await readerPage.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  watch(readerPage, 'reader');
  await open(readerPage, '/');
  const readerSigned = await register(readerPage, READER, 'QA Stranger');
  check('a second account registers in a browser context of its own', readerSigned.status === 201, `HTTP ${readerSigned.status}`);
  await call(readerPage, 'POST', '/api/v1/creator/profile', { slug: `qa-stranger-${stamp}` });
  const strangerGuide = await call(readerPage, 'POST', '/api/v1/creator/guides', { section: 'scout', title: 'a stranger\'s own public guide', visibility: 'public' });
  const strangerGuideId = String(strangerGuide.json?.guide?.id ?? '');
  check('and writes a public guide of its own', strangerGuide.status === 200 && strangerGuide.json?.guide?.visibility === 'public' && strangerGuideId.length > 0, `HTTP ${strangerGuide.status} · ${strangerGuideId}`);

  await open(authorPage, '/creator');
  await untilTrue(async () => (await authorPage.$eval(C('shelf'), (node) => node.getAttribute('data-creator-shelf')).catch(() => 'unread')) === '2');
  const shelfAfter = await rowsOf(authorPage, 'creator-guide');
  check('the shelf the page paints is this account\'s own, and not everybody\'s public shelf', shelfAfter.length === 2 && !shelfAfter.some((row) => row.key === strangerGuideId), `${shelfAfter.length} row(s) painted; the stranger\'s guide is ${shelfAfter.some((row) => row.key === strangerGuideId) ? 'on it' : 'not on it'}`);
  const unscoped = (await call(authorPage, 'GET', '/api/v1/creator/guides')).json ?? {};
  check('and the door\'s unscoped listing does hold that guide, so the panel is what keeps it off the page', (unscoped.items ?? []).some((item) => item.id === strangerGuideId), `${(unscoped.items ?? []).length} item(s) in the unscoped listing`);
  // ------------------------------------------------------------------- the citations, and the address they travel as
  await press(authorPage, `${rowOf(publicGuide.id)} [data-creator-guide-open]`);
  check('opening a guide from its row paints the citation panel for that guide', await untilTrue(async () => (await authorPage.$eval(C('citations'), (node) => node.getAttribute('data-creator-citations')).catch(() => '')) === publicGuide.id), `panel for ${publicGuide.id}`);

  const corpus = (await call(authorPage, 'GET', '/api/v1/knowledge/documents')).json ?? {};
  const passageDoc = (corpus.items ?? []).find((item) => Number(item.chunk_count ?? 0) > 0) ?? {};
  check('the corpus the guide cites is a real one, holding a document with passages to point at', !!passageDoc.slug, `${(corpus.items ?? []).length} document(s); the walk cites ${passageDoc.slug}`);

  await typeInto(authorPage, C('cite-document'), 'a-document-the-corpus-does-not-hold');
  await clearField(authorPage, C('cite-ordinal'));
  await typeInto(authorPage, C('cite-ordinal'), '0');
  const unknownDocument = await pressWrite(authorPage, C('cite'), 'cite', 'no_such_document');
  check('citing a document the corpus does not hold is refused by name, in the panel that asked', unknownDocument.ok && has(unknownDocument.note, 'no_such_document'), unknownDocument.note.slice(0, 150));
  check('and that refusal wrote nothing, so a guide cannot point at a passage that is not there', ((await call(authorPage, 'GET', `/api/v1/creator/guides/${publicGuide.id}`)).json ?? {}).citations === 0);

  await clearField(authorPage, C('cite-document'));
  await typeInto(authorPage, C('cite-document'), passageDoc.slug);
  await clearField(authorPage, C('cite-ordinal'));
  await typeInto(authorPage, C('cite-ordinal'), '9999');
  const ghostOrdinal = await pressWrite(authorPage, C('cite'), 'cite', 'citation_ordinal');
  check('and a passage number the document does not hold is refused with the document and the number beside it', ghostOrdinal.ok && has(ghostOrdinal.note, 'citation_ordinal') && has(ghostOrdinal.note, '9999'), ghostOrdinal.note.slice(0, 160));

  await clearField(authorPage, C('cite-ordinal'));
  await typeInto(authorPage, C('cite-ordinal'), '0');
  await typeInto(authorPage, C('cite-note'), 'the passage this guide is built on');
  const cited = await pressWrite(authorPage, C('cite'), 'cite', 'answered');
  check('and an address that is there is recorded from the page', cited.ok, `the control ${cited.pressed} after ${cited.attempts} attempt(s); note: ${cited.note.slice(0, 140)}`);
  const openGuide = (await call(authorPage, 'GET', `/api/v1/creator/guides/${publicGuide.id}`)).json ?? {};
  const recorded = (openGuide.passages ?? [])[0] ?? {};
  check('the door resolves that address to the passage it names, and stores none of its words', openGuide.citations === 1 && recorded.document === passageDoc.slug && recorded.ordinal === 0 && recorded.moved === false, `citations ${openGuide.citations}, moved ${openGuide.moved}, tokens ${openGuide.tokens}`);
  check('the painted citation row shows the address, the heading read now, and that nothing has moved', (await waitForRows(authorPage, 'creator-citation', 1)) && ((await rowsOf(authorPage, 'creator-citation'))[0]?.cells ?? [])[3] === 'NO' && ((await rowsOf(authorPage, 'creator-citation'))[0]?.cells ?? [])[0] === passageDoc.slug, JSON.stringify(((await rowsOf(authorPage, 'creator-citation'))[0]?.cells ?? []).slice(0, 4)));
  check('and the panel prints the formula the door publishes for that count rather than one of its own', shouts(await text(authorPage), (rules?.formulas ?? {}).citations ?? 'no formula published'), 'the citation formula, on the page');

  const uncited = await pressWrite(authorPage, `${citationOf(String(recorded.id ?? ''))} [data-creator-citation-remove]`, 'uncite', 'answered');
  check('un-citing from the row takes the citation off the guide at the door, not only off the page', uncited.ok && ((await call(authorPage, 'GET', `/api/v1/creator/guides/${publicGuide.id}`)).json ?? {}).citations === 0, uncited.note.slice(0, 140));
  // ----------------------------------------------------------- reach is a predicate, and absence is what it answers
  const readFollowers = await call(readerPage, 'GET', `/api/v1/creator/guides/${followersGuide.id}`);
  const readItsCitations = await call(readerPage, 'GET', `/api/v1/creator/guides/${followersGuide.id}/citations`);
  check('a followers-only guide answers a stranger as absence, never with a refusal that confirms it exists', readFollowers.status === 404 && readFollowers.json?.detail?.code === 'no_such_guide', `HTTP ${readFollowers.status} · ${readFollowers.json?.detail?.code}`);
  check('and the citations on it are kept out by that same predicate, address for address', readItsCitations.status === 404 && readItsCitations.json?.detail?.code === 'no_such_guide', `HTTP ${readItsCitations.status} · ${readItsCitations.json?.detail?.code}`);
  check('while the public guide beside it is readable at its own address by that stranger', (await call(readerPage, 'GET', `/api/v1/creator/guides/${publicGuide.id}`)).status === 200);
  const strangerShelf = (await call(readerPage, 'GET', `/api/v1/creator/guides?creator=${authorId}`)).json ?? {};
  check('and this author\'s shelf reaches the stranger exactly as far as the public guide', (strangerShelf.items ?? []).some((item) => item.id === publicGuide.id) && !(strangerShelf.items ?? []).some((item) => item.id === followersGuide.id), `${(strangerShelf.items ?? []).map((item) => item.visibility).join(', ') || 'nothing'} reachable`);

  const followed = await call(readerPage, 'POST', `/api/v1/community/follows/${authorId}`);
  check('§35\'s own follow door is what opens it — no second follow table and no creator-side switch', [200, 201].includes(followed.status) && (await call(readerPage, 'GET', `/api/v1/creator/guides/${followersGuide.id}`)).status === 200, `follow HTTP ${followed.status}`);
  check('and the shelf of the reader that follows now carries it', ((await call(readerPage, 'GET', `/api/v1/creator/guides?creator=${authorId}`)).json?.items ?? []).some((item) => item.id === followersGuide.id));
  const unfollowed = await call(readerPage, 'DELETE', `/api/v1/community/follows/${authorId}`);
  check('and an unfollow withdraws it again, deleting nothing the guide holds', [200, 204].includes(unfollowed.status) && (await call(readerPage, 'GET', `/api/v1/creator/guides/${followersGuide.id}`)).status === 404, `unfollow HTTP ${unfollowed.status}`);

  // ------------------------------------------------------------------------------------------ erasing, and the census
  authorPage.on('dialog', (dialog) => void dialog.accept());
  await openStudio(authorPage, 2);
  const erased = await pressWrite(authorPage, `${rowOf(followersGuide.id)} [data-creator-guide-erase]`, 'erase', 'answered');
  check('erasing a guide from its own row is answered by the door, and the shelf drops the row', erased.ok && await waitForRows(authorPage, 'creator-guide', 1), erased.note.slice(0, 140));
  const afterErase = await call(authorPage, 'GET', `/api/v1/creator/guides/${followersGuide.id}`);
  check('and the guide is absent for everybody afterwards, its author included', afterErase.status === 404 && afterErase.json?.detail?.code === 'no_such_guide', `HTTP ${afterErase.status} · ${afterErase.json?.detail?.code}`);

  await authorPage.setViewport(MOBILE);
  await open(authorPage, '/creator');
  const narrow = await rowsOf(authorPage, 'creator-guide');
  check('the shelf survives a phone viewport with its nine columns', narrow.length === 1 && narrow[0]?.cells?.length === 9, `${narrow.length} row(s), ${narrow[0]?.cells?.length} column(s)`);
  await shot(authorPage, 'shelf-mobile');
  await authorPage.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await open(authorPage, '/creator');
  await shot(authorPage, 'studio-final');
  await open(readerPage, '/creator');
  await shot(readerPage, 'stranger-studio');

  const wrongStatuses = knocks.filter((knock) => [400, 403].includes(knock.status));
  check(`none of the ${knocks.length} knocks this walk made earned a 400 or a 403 at a creator door`, wrongStatuses.length === 0, wrongStatuses.map((knock) => `${knock.method} ${knock.path} ${knock.status}`).join(' | ').slice(0, 180));
  const serverFaults = consoleErrors.filter((line) => /status of 5\d\d/.test(line));
  const unasked = consoleErrors.filter((line) => !/status of 4\d\d/.test(line));
  check('every console line left behind is a 4xx the walk knocked for itself — no 5xx, no page exception', serverFaults.length === 0 && unasked.length === 0, `${consoleErrors.length} lines: ${consoleErrors.slice(0, 2).join(' | ')}`.slice(0, 190));

  await readerContext.close();
  await browser.close();
  finish();
}

function finish() {
  const failed = results.filter((entry) => !entry.ok);
  console.log(`\n${results.length - failed.length}/${results.length} creator walk checks passed`);
  for (const entry of failed) console.log(`  FAIL  ${entry.name} — ${entry.detail}`);
  console.log(`screenshots: ${shots.join(', ')}`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((error) => {
  console.log(`the walk itself threw: ${error?.stack ?? error}`);
  process.exit(2);
});
