/**
 * M9's community walk: two accounts, a production build, and the claim that a post is a pointer while every
 * figure beside it is counted from rows.
 *
 *   api tier:  http://127.0.0.1:8740   (DATABASE_URL=<scratch file> uvicorn app.main:app --port 8740)
 *   web tier:  http://127.0.0.1:3217   (API_INTERNAL_URL=http://127.0.0.1:8740 next start -p 3217)
 *   QA_BASE=http://127.0.0.1:3217 node scripts/qa-community.mjs
 *
 * What this walk is willing to fail on:
 *
 * * the page's own controls must move the door's figures. A publish that writes nothing, a like that writes two
 *   rows, or an unfollow that leaves a `followers` post reachable is a defect a green API suite cannot see, so
 *   each verb is pressed and then re-read through the door rather than trusted from the painted note alone;
 * * every figure is re-read, never kept. The walk compares the cell the page painted with the same door's JSON
 *   after each press, so a number cached on the browser side shows up as a mismatch;
 * * reach is answered as **absence**. A post the caller cannot reach earns a 404 whose code is `no_such_post`,
 *   never a 403 and never a 400 — and the walk records the status of every knock it made and refuses the run if
 *   a 403 or a 400 turns up anywhere in this tier;
 * * no number in the walk is invented here. The ceilings, the kinds, the prefixes and the statuses all come out
 *   of `GET /api/v1/community/rules`, the same door the page reads.
 *
 * Env overrides: QA_BASE, CHROME_PATH.
 *
 * The page answers in the browser's language (§81), so this walk **pins the locale** to English with the
 * `fo_locale` cookie: a walk whose needles are English must measure the English surface, and a host whose
 * browser asks for Chinese would otherwise fail every one of them for a reason that has nothing to do with
 * the tier. The cookie is written before the first page is opened.
 */

import { mkdir, readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import puppeteer from 'puppeteer-core';

const BASE = (process.env.QA_BASE ?? 'http://127.0.0.1:3217').trim();
const DIST = (process.env.QA_DIST ?? '.next').trim();
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };
const PASSWORD = 'community-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const AUTHOR = `qa-author-${stamp}@footballos.test`;
const READER = `qa-reader-${stamp}@footballos.test`;

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

async function shot(page, name) {
  const file = `${stamp}-community-${name}.png`;
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

async function untilTrue(read, timeout = 60_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if ((await read()) === true) return true;
    await new Promise((done) => setTimeout(done, 600));
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
  if (value) await page.type(selector, String(value), { delay: 8 });
}

async function clearField(page, selector) {
  await page.waitForSelector(selector, { visible: true, timeout: 20_000 });
  await page.click(selector, { clickCount: 3 });
  await page.keyboard.press('Backspace');
}

const selectorOf = (testid) => (testid.startsWith('[') ? testid : `[data-testid="${testid}"]`);

function press(page, testid) {
  return page.evaluate((sel) => {
    const button = document.querySelector(sel);
    if (!button) return 'missing';
    if (button.disabled) return 'disabled';
    button.click();
    return 'clicked';
  }, selectorOf(testid));
}

/**
 * Press a write control and read the note *that* component paints, waiting the tier rate door out.
 *
 * Each note carries a `data-note` identity chosen by the component that owns it, because a walk that compares
 * note nodes by position cannot see a repeated identical answer: publishing two notes in a row paints the same
 * sentence twice. The note therefore carries the facts the door answered with (its own id, `recorded_now`), so a
 * press that repeats a verb is still a new sentence, and a check cannot be satisfied by the note an earlier
 * press left behind.
 */
function noteFor(page, action) {
  return page.$eval(`[data-note="${action}"]`, (node) => node.innerText.replace(/\s+/g, ' ').trim()).catch(() => '');
}

async function pressWrite(page, button, action, want = '', tries = 4) {
  for (let attempt = 1; attempt <= tries; attempt += 1) {
    const before = await noteFor(page, action);
    const pressed = await press(page, button);
    if (pressed !== 'clicked') return {ok: false, pressed, note: `(the button ${pressed})`, attempts: attempt, changed: false};
    let note = '';
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      note = await noteFor(page, action);
      if (note.length > 0 && note !== before && squeeze(want).length > 0 && squeeze(note).toUpperCase().includes(squeeze(want).toUpperCase()) && !/429/.test(note)) {
        return {ok: true, pressed, note, attempts: attempt, changed: note !== before};
      }
      await new Promise((done) => setTimeout(done, 300));
    }
    if (!/429/.test(note)) return {ok: false, pressed, note: note === '' ? '(no note painted there)' : note, attempts: attempt, changed: note !== before};
    await new Promise((done) => setTimeout(done, 25_000));
  }
  return {ok: false, pressed: 'limited', note: '(every attempt was answered 429 by the rate door)', attempts: tries, changed: false};
}

/** A figure cell repaints on the refresh clock too, so a count check waits for the number, not the row. */
async function waitForCell(page, postId, index, want, timeout = 45_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const cell = (await rowsOf(page, 'post')).find(row => row.key === postId)?.cells?.[index] ?? '';
    if (squeeze(cell) === squeeze(want)) return true;
    await new Promise((done) => setTimeout(done, 500));
  }
  return false;
}

/** The page re-reads its own wall after a write, on the refresh clock, so a row check waits for the paint. */
async function waitForRows(page, want, timeout = 45_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if ((await rowsOf(page, 'post')).length === want) return true;
    await new Promise((done) => setTimeout(done, 500));
  }
  return false;
}

/** The `[data-post]` rows of the wall, with their cells read the way a person reads them. */
function rowsOf(page, attribute) {
  return page.$$eval(`tr[data-${attribute}]`, (rows, name) => rows.map((row) => ({key: row.getAttribute(`data-${name}`), cells: [...row.querySelectorAll('td')].map(cell => cell.innerText.replace(/\s+/g, ' ').trim())})), attribute);
}

async function register(page, email, displayName) {
  let last = null;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    last = await call(page, 'POST', '/api/v1/auth/register', {accepts_data_policy: true, display_name: displayName, email, password: PASSWORD, role: 'player'});
    if (last.status !== 429) return last;
    await new Promise((done) => setTimeout(done, 25_000));
  }
  return last;
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  // ---------------------------------------------------------------- the vocabulary door, with no cookie at all
  const rulesResponse = await fetch(`${BASE}/api/v1/community/rules`, {headers: {accept: 'application/json'}});
  const rules = rulesResponse.ok ? await rulesResponse.json() : null;
  const caps = rules?.caps ?? {};
  const answers = rules?.refusal_answers ?? {};
  check('the rules door answers a caller with no session and prints the twelve doors it declares', rulesResponse.status === 200 && (rules?.routes ?? []).length === 12, `HTTP ${rulesResponse.status}; ${(rules?.routes ?? []).length} route(s) published`);
  check('and the code list it answers with is the list it publishes', Object.keys(answers).length === (rules?.refusals ?? []).length && (rules?.refusals ?? []).every(code => code in answers), `${Object.keys(answers).length} answers for ${(rules?.refusals ?? []).length} codes`);
  const statuses = [...new Set(Object.values(answers))];
  check('every published code earns 404, 422 or 409 — no 403 without a matrix, and no 400 fall-through', statuses.every(value => [404, 409, 422].includes(value)), `statuses ${statuses.sort().join(', ')}`);
  const anonymousFeed = await fetch(`${BASE}/api/v1/community/posts`, {headers: {accept: 'application/json'}});
  check('a stranger may not read anybody feed', anonymousFeed.status === 401, `HTTP ${anonymousFeed.status}`);

  const buildId = (await readFile(resolve(dirname(fileURLToPath(import.meta.url)), `../${DIST}/BUILD_ID`), 'utf8')).trim();
  const servedHtml = await (await fetch(`${BASE}/`)).text();
  check('the page this walk drives is the build it just compiled, by its own BUILD_ID', has(servedHtml, buildId), `BUILD_ID ${buildId}`);

  const browser = await puppeteer.launch({executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage']});

  const authorPage = await browser.newPage();
  await authorPage.setCookie({ name: 'fo_locale', value: 'en', url: BASE });
  await authorPage.setViewport({width: 1440, height: 900, deviceScaleFactor: 1});
  watch(authorPage, 'author');
  await open(authorPage, '/');
  check('the community page sends a caller with no session to the login screen, and says where it was headed', await (async () => {
    await open(authorPage, '/community');
    return authorPage.url().includes('/login') && authorPage.url().includes('community');
  })(), authorPage.url());

  const signed = await register(authorPage, AUTHOR, 'QA Author');
  check('an account registers through the proxy the page itself uses', signed.status === 201, `HTTP ${signed.status}`);
  const me = await call(authorPage, 'GET', '/api/v1/auth/me');
  const authorId = String(me.json?.id ?? '');

  await open(authorPage, '/community');
  const wall = await text(authorPage);
  check('the wall paints its own head and the empty feed says so in the tier words', shouts(wall, 'Community wall') && shouts(wall, 'Nothing reaches you yet'), wall.slice(0, 120));
  check('the page prints the rulebook it is reading, including the one sentence about what it does not store', shouts(wall, caps.visibility_rule ?? 'no visibility rule published') && shouts(wall, rules.limitation ?? 'no limitation published'), `visibility rule and limitation both on screen`);

  // ---------------------------------------------------------------- publish, and the pointer is a link
  await open(authorPage, '/community');
  const first = 'a press that never lands is a dead form';
  await typeInto(authorPage, 'textarea[aria-label="Post body"]', first);
  const posted = await pressWrite(authorPage, 'community-publish', 'composer', 'posted');
  check('the page publishes a note from its own controls', posted.ok, `the button ${posted.pressed} after ${posted.attempts} attempt(s); note: ${posted.note.slice(0, 120)}`);
  const paintedOne = await waitForRows(authorPage, 1);
  let feed = await call(authorPage, 'GET', '/api/v1/community/posts');
  check('the refresh repaints the wall: the row the door counts is the row on screen', paintedOne === true && (await rowsOf(authorPage, 'post')).length === 1, `painted: ${paintedOne}`);
  check('one reachable post, one painted row, and the door total is the number of rows the page printed', feed.json?.total === 1 && (await rowsOf(authorPage, 'post')).length === 1 && shouts(await text(authorPage), 'the door total is the number of rows it printed'), `door ${feed.json?.total} · page ${(await rowsOf(authorPage, 'post')).length} row(s)`);
  const noteRow = (await rowsOf(authorPage, 'post'))[0] ?? {};
  check('a note points at nothing and says so, rather than carrying an empty link', has(noteRow.key, 'post') && shouts(noteRow.cells.join(' '), 'points at nothing'), (noteRow.cells ?? [])[0]);

  // a `my_tactic` post carries its kind's own prefix, chosen from the published vocabulary
  await chooseKind(authorPage, 'my_tactic');
  await typeInto(authorPage, 'textarea[aria-label="Post body"]', 'high press, five seconds');
  await typeInto(authorPage, 'input[aria-label="Post pointer tail"]', `qa-board-${stamp.slice(-4)}`);
  const shared = await pressWrite(authorPage, 'community-publish', 'composer', 'posted');
  feed = await call(authorPage, 'GET', '/api/v1/community/posts');
  const tactic = (feed.json?.items ?? []).find(item => item.kind === 'my_tactic') ?? {};
  check('the page shares a board by address: the pointer it sent is the prefix the rules printed plus the tail typed here', shared.ok && tactic.pointer === `${caps.pointer_prefixes?.my_tactic ?? 'no-prefix'}qa-board-${stamp.slice(-4)}`, `pointer ${tactic.pointer}`);
  await open(authorPage, '/community');
  const paintedTwo = await waitForRows(authorPage, 2);
  const tacticCells = (await rowsOf(authorPage, 'post')).find(row => row.key === tactic.id)?.cells?.join(' ') ?? '';
  check('and the row renders that address as a link, with no figure copied from the board beside it', paintedTwo === true && has(tacticCells, tactic.pointer) && !shouts(tacticCells, 'possession') && shouts(await text(authorPage), 'every row pointer sits under its own kind prefix'), tacticCells.slice(0, 160));

  const strangerPointer = await call(authorPage, 'POST', '/api/v1/community/posts', {body: 'pointing elsewhere', kind: 'my_tactic', pointer: `${caps.pointer_prefixes?.my_training ?? '/training/'}elsewhere`});
  check('a kind that points at another kind page is refused with the prefix it expected, and wrote nothing', strangerPointer.status === answers.post_pointer && strangerPointer.json?.detail?.expected === caps.pointer_prefixes?.my_tactic && (await call(authorPage, 'GET', '/api/v1/community/posts')).json?.total === 2, `HTTP ${strangerPointer.status} · expected ${JSON.stringify(strangerPointer.json?.detail?.expected)}`);

  // ---------------------------------------------------------------- a blank is the tier refusal, not a schema list
  await clearField(authorPage, 'textarea[aria-label="Post body"]');
  const blank = await pressWrite(authorPage, 'community-publish', 'composer', 'post_body');
  check('a blank body is refused by the tier, with the ceiling beside the sentence, and is not a write', blank.ok && has(blank.note, `max ${caps.post_body_max}`) && (await call(authorPage, 'GET', '/api/v1/community/posts')).json?.total === 2, blank.note.slice(0, 160));

  // ---------------------------------------------------------------- a like is one row per account
  const likedId = tactic.id;
  const firstLike = await pressWrite(authorPage, `community-like-${likedId}`, `row-${likedId}`, 'recorded');
  let detail = await call(authorPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(likedId)}`);
  check('the page records the reaction from its own control and the door counts one', firstLike.ok && detail.json?.likes === 1, `note ${firstLike.note.slice(0, 60)} · door likes ${detail.json?.likes}`);
  await open(authorPage, '/community');
  const secondLike = await pressWrite(authorPage, `community-like-${likedId}`, `row-${likedId}`, 'already one row');
  detail = await call(authorPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(likedId)}`);
  check('pressing it again is the same row: the note says so, the figure does not move, and the painted cell agrees', secondLike.ok && detail.json?.likes === 1 && (await pageCellFor(authorPage, likedId, 1)) === '1', `note ${secondLike.note.slice(0, 60)} · door ${detail.json?.likes} · cell ${(await pageCellFor(authorPage, likedId, 1))}`);

  // ---------------------------------------------------------------- reach is a predicate over follows
  await chooseVisibility(authorPage, 'followers');
  await chooseKind(authorPage, 'note');
  await typeInto(authorPage, 'textarea[aria-label="Post body"]', 'only for the accounts that follow me');
  const walled = await pressWrite(authorPage, 'community-publish', 'composer', 'posted');
  await open(authorPage, '/community');
  const paintedThree = await waitForRows(authorPage, 3);
  feed = await call(authorPage, 'GET', '/api/v1/community/posts');
  const secret = (feed.json?.items ?? []).find(item => item.visibility === 'followers') ?? {};
  check('a followers post is the author own and appears in their feed', walled.ok && paintedThree === true && typeof secret.id === 'string' && secret.body.includes('only for the accounts'), `${feed.json?.total} reachable for the author`);

  const readerPage = await (await browser.createBrowserContext()).newPage();
  await readerPage.setCookie({ name: 'fo_locale', value: 'en', url: BASE });
  await readerPage.setViewport({width: 1440, height: 900, deviceScaleFactor: 1});
  watch(readerPage, 'reader');
  await open(readerPage, '/');
  const readerSigned = await register(readerPage, READER, 'QA Reader');
  check('a second account registers in its own browser context', readerSigned.status === 201, `HTTP ${readerSigned.status}`);
  const readerMe = await call(readerPage, 'GET', '/api/v1/auth/me');
  const readerId = String(readerMe.json?.id ?? '');

  await open(readerPage, '/community');
  const readerRows = await rowsOf(readerPage, 'post');
  check('a stranger reads none of it: the wall is empty for them and the door counts zero', (await call(readerPage, 'GET', '/api/v1/community/posts')).json?.total === 0 && readerRows.length === 0, `${readerRows.length} painted row(s)`);
  const closedDoor = await call(readerPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(secret.id)}`);
  check('knocking on the followers post by its address answers absence, not refusal: the code is the one a row never written earns', closedDoor.status === answers.no_such_post && closedDoor.json?.detail?.code === 'no_such_post', `HTTP ${closedDoor.status} · ${JSON.stringify(closedDoor.json?.detail?.code)}`);
  const notYours = await call(readerPage, 'DELETE', `/api/v1/community/posts/${encodeURIComponent(secret.id)}`);
  check('and somebody else post is not confirmed to exist by an erase door either', notYours.status === answers.no_such_post && notYours.json?.detail?.code === 'no_such_post', `HTTP ${notYours.status} · ${JSON.stringify(notYours.json?.detail?.code)}`);

  const followed = await call(readerPage, 'POST', `/api/v1/community/follows/${encodeURIComponent(authorId)}`);
  const authorProfile = await call(readerPage, 'GET', `/api/v1/community/members/${encodeURIComponent(authorId)}`);
  check('a follow is one row that decides reach: the profile counts it and nothing about the posts was copied', followed.status === 200 && followed.json?.recorded_now === true && authorProfile.json?.followers === 1, `recorded ${JSON.stringify(followed.json?.recorded_now)} · followers ${authorProfile.json?.followers}`);
  const openedRows = await untilTrue(async () => {
    await open(readerPage, '/community');
    return (await rowsOf(readerPage, 'post')).length === 3;
  }, 90_000);
  const readerFeed = await call(readerPage, 'GET', '/api/v1/community/posts');
  check('after the follow the reader feed carries all three of the authors posts, and the page paints them', openedRows === true && readerFeed.json?.total === 3 && (await rowsOf(readerPage, 'post')).length === 3, `door ${readerFeed.json?.total} · rows ${(await rowsOf(readerPage, 'post')).length}`);
  const openDoor = await call(readerPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(secret.id)}`);
  check('the same address that answered absence now answers the post, because reach was recomputed on the read', openDoor.status === 200 && openDoor.json?.id === secret.id, `HTTP ${openDoor.status}`);

  // ---------------------------------------------------------------- repost and reply, both counted
  const reposted = await pressWrite(readerPage, `community-repost-${likedId}`, `row-${likedId}`, 'carried');
  detail = await call(readerPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(likedId)}`);
  check('a reader carries the post to their own followers and the door counts the repost row', reposted.ok && detail.json?.reposts === 1, `note ${reposted.note.slice(0, 60)} · door reposts ${detail.json?.reposts}`);
  await open(readerPage, '/community');
  const againRepost = await pressWrite(readerPage, `community-repost-${likedId}`, `row-${likedId}`, 'carried');
  check('a second carry is the same row', againRepost.ok && (await call(readerPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(likedId)}`)).json?.reposts === 1, `door reposts ${(await call(readerPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(likedId)}`)).json?.reposts}`);

  const toggled = await press(readerPage, `community-replies-toggle-${likedId}`);
  const emptied = await until(readerPage, 'no reply has been written on this post');
  check('the reply reader asks the door rather than guessing: an empty list is painted as empty', toggled === 'clicked' && emptied === true, `the button ${toggled}; the empty sentence painted: ${emptied}`);
  await typeInto(readerPage, `textarea[aria-label^="Reply on the post"]`, 'agreed, the trap is the point');
  const replied = await pressWrite(readerPage, `community-reply-send-${likedId}`, `reply-${likedId}`, 'answered');
  const repainted = await waitForCell(readerPage, likedId, 2, String(detail?.json?.comments ?? 1));
  detail = await call(readerPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(likedId)}`);
  check('the reply lands as a row beside the post, and the count printed beside it is the door second count', replied.ok && detail.json?.comments === 1 && repainted === true && (await pageCellFor(readerPage, likedId, 2)) === '1', `note ${replied.note.slice(0, 60)} · door ${detail.json?.comments} · cell ${(await pageCellFor(readerPage, likedId, 2))}`);

  // ---------------------------------------------------------------- unfollow withdraws, erase takes down
  const unfollowed = await pressWrite(readerPage, `community-follow-${authorId}`, 'wall', 'reach withdrawn');
  const backToNone = await untilTrue(async () => (await call(readerPage, 'GET', '/api/v1/community/posts')).json?.total === 0, 90_000);
  check('the page unfollows from its own control and the reach goes with the row: no post was deleted, nothing is left readable', unfollowed.ok && backToNone === true && (await call(readerPage, 'GET', `/api/v1/community/posts/${encodeURIComponent(secret.id)}`)).status === answers.no_such_post, `note ${unfollowed.note.slice(0, 60)}`);
  const authorAfter = await call(readerPage, 'GET', `/api/v1/community/members/${encodeURIComponent(authorId)}`);
  check('and the author wall is still there for them to read: three posts, one fewer follower', authorAfter.json?.posts === 3 && authorAfter.json?.followers === 0, `posts ${authorAfter.json?.posts} · followers ${authorAfter.json?.followers}`);

  const erased = await pressWrite(authorPage, `community-erase-${secret.id}`, 'wall', 'erased');
  const afterErase = await call(authorPage, 'GET', '/api/v1/community/posts');
  check('the erase door answers how many rows went with the post, and the wall loses them too', erased.ok && afterErase.json?.total === 2, `note ${erased.note.slice(0, 80)} · ${afterErase.json?.total} left`);

  // ---------------------------------------------------------------- the ceiling the tier publishes
  const held = Number(afterErase.json?.total ?? 0);
  check('the badge beside the composer is the published ceiling minus the rows the door counts, not a number typed here', shouts(await text(authorPage), `${caps.post_max - held} of ${caps.post_max} posts left`), `${caps.post_max} minus ${held}`);

  await authorPage.setViewport(MOBILE);
  await open(authorPage, '/community');
  const narrow = await rowsOf(authorPage, 'post');
  check('the wall survives a phone viewport with its five columns', narrow.length === 2 && narrow[0]?.cells?.length === 5, `${narrow.length} row(s), ${narrow[0]?.cells?.length} column(s)`);
  await shot(authorPage, 'wall-mobile');

  await readerPage.setViewport({width: 1440, height: 900, deviceScaleFactor: 1});
  await open(readerPage, '/community');
  await shot(readerPage, 'reader-after-unfollow');
  await authorPage.setViewport({width: 1440, height: 900, deviceScaleFactor: 1});
  await open(authorPage, '/community');
  await shot(authorPage, 'author-wall');

  const wrongStatuses = knocks.filter(knock => [400, 403].includes(knock.status));
  check(`none of the ${knocks.length} knocks this walk made earned a 400 or a 403 at a community door`, wrongStatuses.length === 0, wrongStatuses.map(knock => `${knock.method} ${knock.path} ${knock.status}`).join(' | ').slice(0, 180));
  const serverFaults = consoleErrors.filter(line => /status of 5\d\d/.test(line));
  const unasked = consoleErrors.filter(line => !/status of 4\d\d/.test(line));
  check('every console line left behind is a 4xx the walk knocked for itself — no 5xx, no page exception', serverFaults.length === 0 && unasked.length === 0, `${consoleErrors.length} lines: ${consoleErrors.slice(0, 2).join(' | ')}`.slice(0, 190));

  await browser.close();
  finish();
}

/** Set the kind select and wait for the pointer field the tier only ever shows for a pointing kind. */
async function chooseKind(page, kind) {
  await page.select('select[aria-label="Post kind"]', kind);
  if (kind !== 'note') await page.waitForSelector('input[aria-label="Post pointer tail"]', {visible: true, timeout: 20_000});
  return page.$eval('select[aria-label="Post kind"]', (node) => node.value);
}

async function chooseVisibility(page, visibility) {
  await page.select('select[aria-label="Post visibility"]', visibility);
  return page.$eval('select[aria-label="Post visibility"]', (node) => node.value);
}

/** One column of the painted row, so a figure is read the way a person reads it. */
async function pageCellFor(page, postId, index) {
  const rows = await rowsOf(page, 'post');
  return (rows.find(row => row.key === postId)?.cells ?? [])[index] ?? '(row not painted)';
}

function finish() {
  const failed = results.filter((entry) => !entry.ok);
  console.log(`\n${results.length - failed.length}/${results.length} community walk checks passed`);
  for (const entry of failed) console.log(`  FAIL  ${entry.name} — ${entry.detail}`);
  console.log(`screenshots: ${shots.join(', ')}`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((error) => {
  console.log(`the walk itself threw: ${error?.stack ?? error}`);
  process.exit(2);
});
