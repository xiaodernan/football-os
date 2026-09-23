/**
 * The §22 transfer market's own evidence walk: a browser against a **production build**, doing the
 * things the page claims a manager can do — open the window for a round, offer a seller a number,
 * sign, loan, sell — and reading back the arithmetic each one left behind.
 *
 *   api tier:  http://127.0.0.1:8734        (uvicorn app.main:app --port 8734)
 *   web tier:  http://127.0.0.1:3212        (API_INTERNAL_URL=… next start -p 3212)
 *   QA_BASE=http://127.0.0.1:3212 node scripts/qa-market.mjs
 *
 * A separate script from `visual-qa.mjs` on purpose: that walk is another milestone's live working
 * copy, and a page cannot be folded into it without editing underneath its author. These checks are
 * written to merge into it once that run lands.
 *
 * What the walk refuses to do is trust the page's own prose. Every arithmetic assertion is computed
 * from the numbers printed in the DOM; the board is opened by clicking the page's button, not by a
 * call behind its back; and a refusal only counts when the figures behind it arrive in the browser.
 *
 * Env overrides: QA_BASE, CHROME_PATH.
 */

import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import puppeteer from 'puppeteer-core';

const BASE = process.env.QA_BASE ?? 'http://127.0.0.1:3212';
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1 };
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };
const PASSWORD = 'market-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const EMAIL = `market-qa-${stamp}@footballos.test`;
const BUDGET = 10_000_000;

const results = [];
const consoleErrors = [];
const shots = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${String(detail).slice(0, 190)}` : ''}`);
}

const amount = (text) => Number(String(text).replace(/[^\d]/g, '')) || 0;
const gb = (value) => Number(value).toLocaleString('en-GB');

async function shot(page, name) {
  const file = `${stamp}-market-${name}.png`;
  try {
    await page.screenshot({ path: resolve(OUT_DIR, file), fullPage: true });
    shots.push(file);
  } catch (error) {
    check(`screenshot ${name} captured`, false, String(error?.message ?? error).slice(0, 160));
  }
}

/** A console error is attributed by its own URL, which is what lets the walk name what it provoked. */
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

function clickIn(page, scope, selector) {
  return page.evaluate(
    (root, needle) => {
      const button = (root ? document.querySelector(root) : document)?.querySelector(needle);
      if (!button) return 'missing';
      if (button.disabled) return 'disabled';
      button.click();
      return 'clicked';
    },
    scope,
    selector,
  );
}

/** The buying board, read out of the table the reader sees, in the page's own column order.
 * The badges and the need-marker are set in capitals by the stylesheet, so the words that label a row
 * are compared case-folded while every figure is compared exactly as printed. */
function board(page) {
  return page.$$eval('tr[data-listing]', (list) =>
    list.map((row) => {
      const cells = [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim());
      const buttons = [...row.querySelectorAll('button[data-act]')].map((button) => ({ act: button.dataset.act, label: button.innerText.trim(), disabled: button.disabled }));
      const upper = cells.map((cell) => cell.toUpperCase());
      return {
        id: row.dataset.listing,
        cells,
        buttons,
        player: (cells[0] ?? '').replace(/\s*answers the need$/i, '').trim(),
        asking: Number((cells[6] ?? '0').replace(/[^\d]/g, '')),
        price: Number((cells[7] ?? '0').replace(/[^\d]/g, '')),
        clause: Number((cells[8] ?? '0').replace(/[^\d]/g, '')),
        wage: Number((cells[9] ?? '0').replace(/[^\d]/g, '')),
        fit: Number(cells[10] ?? '0'),
        rival: (upper[5] ?? '').includes('RIVAL'),
        fillsNeed: (upper[0] ?? '').includes('ANSWERS THE NEED'),
      };
    }),
  );
}

function stats(page) {
  return page.$$eval('.stat', (list) =>
    list.map((node) => ({ label: node.querySelector('.stat__label')?.innerText ?? '', value: node.querySelector('.stat__value')?.innerText ?? '' })),
  );
}

async function stat(page, label) {
  // The design system sets the stat labels in capitals, so the page's text and the code's label differ by case only.
  return amount((await stats(page)).find((row) => row.label.toLowerCase() === label.toLowerCase())?.value);
}

function squadRows(page) {
  return page.$$eval('tr[data-player]', (list) =>
    list.map((row) => ({
      id: row.dataset.player,
      // A row's own innerText separates cells with tabs, so the name is read from its cell, not from the
      // first line of the row.
      name: (row.querySelectorAll('td')[0]?.innerText ?? '').replace(/\s+/g, ' ').trim(),
      position: row.querySelectorAll('td')[1]?.innerText.replace(/\s+/g, ' ').trim() ?? '',
      proceeds: row.querySelectorAll('td')[7]?.innerText ?? '',
    })),
  );
}

/** The line the page printed for the last thing it did. */
async function lineWith(page, needle) {
  const body = await text(page);
  return body.split('\n').find((line) => line.includes(needle)) ?? '';
}

/** Pages carry their copy in headings and definition lists the stylesheet sets in capitals, so a check
 * that quotes a sentence compares it case-folded. The figures are matched exactly, never folded. */
const has = (body, needle) => String(body).toLowerCase().includes(String(needle).toLowerCase());

/**
 * Wait for the *table*, not the notice.
 *
 * Every action on this page ends with a re-read from the server, and the notice the button prints is
 * client state that can land a frame before the rows it explains. A check that reads the board in that
 * gap sees the page before it has been told anything, so the walk waits on the DOM condition it is
 * about to assert on instead of on a clock.
 */
async function untilDom(page, predicate, arg, timeout = 20_000) {
  try {
    await page.waitForFunction(predicate, { timeout, polling: 250 }, arg);
    return true;
  } catch {
    return false;
  }
}

/** Every key/value the page prints, keyed by the label a reader sees, case-folded because the stylesheet
 * sets those labels in capitals. A check that quotes a figure reads it from here rather than from prose. */
function gridValues(page) {
  return page.$$eval('.world-kv__row', (rows) =>
    Object.fromEntries(
      rows.map((row) => [
        (row.querySelector('dt')?.innerText ?? '').replace(/\s+/g, ' ').trim().toLowerCase(),
        (row.querySelector('dd')?.innerText ?? '').replace(/\s+/g, ' ').trim(),
      ]),
    ),
  );
}

async function gridValue(page, label) {
  return (await gridValues(page))[label.toLowerCase()] ?? null;
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });

  // --- the walk's own account, minted through the same proxy the login form uses --------------------
  const page = await browser.newPage();
  await page.setViewport(DESKTOP);
  watch(page, 'owner');
  await open(page, '/login');
  const registered = await call(page, 'POST', '/api/v1/auth/register', { email: EMAIL, password: PASSWORD, display_name: 'Market QA', role: 'player', accepts_data_policy: true });
  check('a fresh account registers through the cookie proxy', registered.status === 201, `HTTP ${registered.status}`);
  const me = await call(page, 'GET', '/api/v1/auth/me');
  check('the session the proxy minted authenticates', me.status === 200 && me.json?.email === EMAIL, `HTTP ${me.status}`);

  const options = await call(page, 'GET', '/api/v1/careers/options');
  check('the clubs on offer come from the generated world', options.status === 200 && options.json?.clubs?.length > 0, `${options.json?.clubs?.length ?? 0} clubs`);
  const rules = await call(page, 'GET', '/api/v1/transfers/rules');
  check('the market publishes its arithmetic to anyone, no session required', rules.status === 200 && Object.keys(rules.json?.rules ?? {}).length === 10, `${Object.keys(rules.json?.rules ?? {}).length} expressions`);
  check('the public rules are labelled fictional', rules.json?.data_origin === 'simulation' && rules.json?.is_demo_data === true, String(rules.json?.disclaimer).slice(0, 60));

  const weakest = [...(options.json?.clubs ?? [])].sort((a, b) => a.overall - b.overall || String(a.slug).localeCompare(String(b.slug)));
  const size = rules.json?.constants?.market_size ?? 12;
  const loanShare = rules.json?.constants?.loan_fee_share ?? 0.15;
  const opened = [];
  let target = null;

  // Work up from the weakest club until a board that was opened *by the page* holds both a rival and an
  // affordable offer, because those two are what let the clause rule and a signing both be demonstrated.
  for (const club of weakest.slice(0, 4)) {
    const created = await call(page, 'POST', '/api/v1/careers', {
      club: club.slug,
      manager_name: `Market QA ${stamp.slice(-4)}`,
      philosophy: 'balanced',
      budget: BUDGET,
      objectives: [{ kind: 'wins', target: 1, label: 'win once' }],
    });
    if (created.status !== 200) {
      check(`a career opens at ${club.slug}`, false, `HTTP ${created.status} ${JSON.stringify(created.json)?.slice(0, 110)}`);
      continue;
    }
    const slug = created.json.career.slug;
    const path = `/career/${encodeURIComponent(slug)}/market`;
    const response = await open(page, path);
    check(`the market page answers its owner with 200 (${club.slug})`, response.status() === 200, `HTTP ${response.status()}`);
    await until(page, 'transfer market');
    if (!target) {
      // The first visit is the empty state: a career that has never opened a market sees no rows.
      const empty = await text(page);
      check('an unopened market says so instead of showing an empty table', has(empty, 'No offers priced yet'));
      check('the empty state explains what the button will do', has(empty, 'the band this club is short in'));
      check('the page is titled for the club, not a generic market', has(empty, `${club.name} · transfer market`));
      check('the page says the board belongs to this account', has(empty, 'private to this account'));
      check('the round the board will be priced for is printed', has(empty, 'round 1'), empty.split('\n').find((line) => line.includes('· round')));
      const meta = await page.evaluate(() => document.querySelector('meta[name="robots"]')?.content ?? '');
      check('the market is noindex and nofollow', /noindex/.test(meta) && /nofollow/.test(meta), meta || '(no meta robots)');
      const canonical = await page.evaluate(() => document.querySelector('link[rel="canonical"]')?.href ?? '');
      check('the canonical points at the public career index, not a private URL', !canonical.includes('/market'), canonical);
      check('the page carries the market disclaimer verbatim', has(empty, String(rules.json?.disclaimer).slice(0, 40)), String(rules.json?.disclaimer).slice(0, 40));
      check('the provenance chips are on the page', has(empty, 'data_origin: simulation') && has(empty, 'is_demo_data: true'));
      const readout = await stats(page);
      check('the four balance figures are printed before anything is spent', readout.length === 4, readout.map((row) => `${row.label}=${row.value}`).join(' '));
      check('a career that has not traded still has everything it was given', (await stat(page, 'Stated budget')) === BUDGET && (await stat(page, 'Remaining')) === BUDGET && (await stat(page, 'Spent on arrivals')) === 0, gb(BUDGET));
      check('the balance names the arithmetic it is summed from', has(empty, rules.json?.rules?.budget), String(rules.json?.rules?.budget).slice(0, 70));
      check('the wage figure is published and says it is not deducted', has(empty, 'not deducted'), await lineWith(page, 'committed by the deals'));
      check('the weakest band is named with its four indices', /attack\s*[\d.]+/.test(empty) && /midfield\s*[\d.]+/.test(empty), await lineWith(page, 'attack'));
      check('the need says what it judged on and which squad it read', has(empty, 'Judged on') && has(empty, 'Squad the reading used'));
      const expressions = Object.entries(rules.json?.rules ?? {});
      // Compared with the whitespace taken out: a long expression soft-wraps in a narrow column, and the
      // walk is asking whether the page carries *this* sentence, not whether it kept the line breaks.
      const squeeze = (value) => String(value).replace(/\s+/g, '');
      const found = expressions.filter(([, expression]) => squeeze(empty).includes(squeeze(expression))).map(([key]) => key);
      const missing = expressions.map(([key]) => key).filter((key) => !found.includes(key));
      check(
        'the rules panel prints every published expression, none of them paraphrased',
        expressions.length === 10 && missing.length === 0,
        `${found.length}/${expressions.length} found${missing.length ? ` — missing ${missing.join(', ')}` : ''}`,
      );
      check('the age curve is stated as bands rather than fitted', empty.includes('16-20→×0.6'), await lineWith(page, '32-99'));
      await shot(page, 'market-before');
    }
    const button = await clickIn(page, '[data-testid="market-tools"]', 'button[data-testid="market-open"]');
    check(`the page's own button prices a board (${club.slug})`, button === 'clicked', button);
    const landed = await untilDom(page, () => document.querySelectorAll('tr[data-listing]').length > 0);
    check(`the board reaches the page after the open (${club.slug})`, landed, landed ? 'rows read' : 'the re-read never arrived');
    const rows = await board(page);
    check(`the board comes to the published size (${club.slug})`, rows.length > 0 && rows.length <= size, `${rows.length} rows of at most ${size}`);
    opened.push({ slug, club, rows });
    const rivalRow = rows.find((row) => row.rival);
    const buyable = rows.find((row) => !row.rival && row.buttons.find((item) => item.act === 'sign' && !item.disabled));
    if (rivalRow && buyable && !target) target = { slug, club, rivalRow, buyable };
    if (target) break;
  }

  check('a board turned up holding both a rival and an affordable offer', Boolean(target), opened.map((entry) => `${entry.club.slug}:${entry.rows.length}`).join(' '));
  if (!target) {
    check('the walk has a career to walk', false, 'no board in four clubs offered both a rival and something affordable');
    await browser.close();
    return finish();
  }

  const ident = target.slug;
  const marketPath = `/career/${encodeURIComponent(ident)}/market`;
  // The page's own figures are the server's, so the walk reads the same view over the API and compares the
  // two. A sentence on the page that the API does not print is a sentence the walk has to refuse.
  const view = (await call(page, 'GET', `/api/v1/transfers/${ident}`)).json;
  let body = await text(page);
  check('opening a board from the page prints what the round did', /priced: \d+ offers/.test(body), await lineWith(page, 'priced:'));
  let rows = await board(page);
  check('every offer carries asking, current, clause, wage and fit', rows.every((row) => row.cells.length === 13), `${rows[0]?.cells.length ?? 0} columns`);
  check('the clause is the published rounding of 1.5× the asking', rows.every((row) => Math.abs(row.clause - row.asking * 1.5) <= 2.5), rows.slice(0, 3).map((row) => `${row.asking}→${row.clause}`).join(' '));
  check('the wage is the published rounding of the asking divided by 500', rows.every((row) => Math.abs(row.wage - row.asking / 500) <= 2.5), rows.slice(0, 3).map((row) => `${row.asking}/${row.wage}`).join(' '));
  check('the fit is a number the published formula can produce', rows.every((row) => row.fit >= 0 && row.fit <= 1), rows.slice(0, 4).map((row) => row.fit).join(' '));
  check('the board marks the players that fill the band the club is short in', rows.some((row) => row.fillsNeed), `${rows.filter((row) => row.fillsNeed).length} of ${rows.length} rows`);
  check('the board says which band it was picked against', has(body, `need: ${view?.need?.needed_band}`), await lineWith(page, 'priced offers'));
  check('no offer is priced above the balance and left buyable', rows.every((row) => row.rival || row.price <= BUDGET || row.buttons.find((item) => item.act === 'sign')?.disabled !== false), 'affordability is the server’s');

  // --- the seller answers an offer -------------------------------------------------------------------
  const negotiable = rows.find((row) => row.buttons.find((button) => button.act === 'offer' && !button.disabled));
  check('an offer can be put to a seller from its own row', Boolean(negotiable), negotiable?.player);
  if (negotiable) {
    const asking = negotiable.asking;
    const before = negotiable.price;
    const floor = Math.round((asking * 0.8) / 5) * 5;
    await page.evaluate(
      (listing, value) => {
        const input = document.querySelector(`tr[data-listing="${listing}"]`)?.querySelector('input');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, String(value));
        input.dispatchEvent(new Event('input', { bubbles: true }));
      },
      negotiable.id,
      Math.round((before * 0.95) / 5) * 5,
    );
    await clickIn(page, `tr[data-listing="${negotiable.id}"]`, 'button[data-act="offer"]');
    await until(page, 'came back at');
    const answered = await lineWith(page, 'came back at');
    check('the seller answers an offer above the floor', answered.includes('came back at'), answered);
    check('the answer prints the floor the rule will not go under', /floor [\d,]+/.test(answered), answered);
    check('the answer counts the offers left to make', /offer(s)? left/.test(answered), answered);
    check('the answer carries the rule that produced it', answered.includes('round_5'), answered.slice(-120));
    // The counter on the row is the server's copy of the same fact, so waiting for it is waiting for the
    // re-read the notice only describes.
    const recounted = await untilDom(page, (listing) => (document.querySelector(`tr[data-listing="${listing}"]`)?.innerText ?? '').includes('2 left'), negotiable.id);
    check('the row itself is re-read with one offer spent', recounted, recounted ? 'the counter fell on the row' : 'no row answered within 20s');
    rows = await board(page);
    const afterRow = rows.find((row) => row.id === negotiable.id);
    check('a countered price is stored on the row, not just narrated', afterRow.price !== before && afterRow.price > floor, `${gb(before)} → ${gb(afterRow.price)} (floor ${gb(floor)})`);
    check('a negotiation leaves the asking price where the valuation put it', afterRow.asking === asking, `${gb(asking)}`);
    check('the offer counter ticks down on the row', /2 left/.test(afterRow.cells[11]), afterRow.cells[11]);
  }

  // --- a rival is refused, with the clause beside the refusal ----------------------------------------
  const rivalRow = rows.find((row) => row.rival);
  const rivalSign = rivalRow?.buttons.find((button) => button.act === 'sign');
  if (rivalRow && rivalSign && !rivalSign.disabled) {
    await clickIn(page, `tr[data-listing="${rivalRow.id}"]`, 'button[data-act="sign"]');
    await until(page, 'rival_will_not_sell');
    const refusal = await lineWith(page, 'rival_will_not_sell');
    check('a rival that will not sell says so on the page', refusal.includes('rival_will_not_sell'), refusal.slice(0, 150));
    check('the refusal carries the clause figure into the browser', /clause [\d,]+/.test(refusal), refusal.slice(-130));
    check('the refusal carries the rule it was refused by', /asking × 1.5/.test(refusal) || refusal.includes('release clause'), refusal.slice(-90));
    check('the clause button the refusal points at is on the row', Boolean(rivalRow.buttons.find((button) => button.act === 'clause')), rivalRow.buttons.map((button) => button.act).join(' '));
  } else {
    check('a rival that will not sell says so on the page', false, `the rival row on ${ident}'s board had no reachable Sign button (${rivalSign ? 'disabled' : 'absent'})`);
  }

  // --- signing a player ------------------------------------------------------------------------------
  rows = await board(page);
  const buyable = rows.find((row) => !row.rival && row.buttons.find((button) => button.act === 'sign' && !button.disabled));
  check('at least one offer is affordable and buyable', Boolean(buyable), buyable?.player);
  let signedFee = 0;
  let signedName = null;
  if (buyable) {
    signedName = buyable.player;
    signedFee = buyable.price;
    await clickIn(page, `tr[data-listing="${buyable.id}"]`, 'button[data-act="sign"]');
    await until(page, 'signed for');
    const done = await lineWith(page, 'signed for');
    check('the signing is confirmed with its fee', done.includes('signed for') && done.includes(gb(signedFee)), done.slice(0, 160));
    check('the signing states what it did to the eleven', done.includes(String(rules.json?.move_effects?.buy)), done.slice(-110));
    const rebound = await untilDom(page, (name) => [...document.querySelectorAll('tr[data-player]')].some((row) => row.innerText.includes(name)), signedName);
    check('the squad table the server re-reads holds the arrival', rebound, 'the squad table never showed the signed player');
    const remaining = await stat(page, 'Remaining');
    check('the balance left is the fee, to the credit', BUDGET - signedFee === remaining, `${gb(BUDGET)} − ${gb(signedFee)} = ${gb(remaining)}`);
    check('the spent column reads the same fee', (await stat(page, 'Spent on arrivals')) === signedFee, gb(signedFee));
    body = await text(page);
    const squadNames = (await squadRows(page)).map((row) => row.name);
    check('the signed player is in the squad the page reads back', squadNames.includes(signedName), signedName);
    check('a signed listing leaves the shelf', !(await board(page)).some((row) => row.id === buyable.id), buyable.id);
    check('the ledger row prints the balance it left behind', body.includes(gb(BUDGET - signedFee)), gb(BUDGET - signedFee));
    const arrivedHere = await gridValue(page, 'Fielded here because this career brought them');
    check('the account counts the arrival as a player this career fields', arrivedHere === '1', `the page reads ${arrivedHere}`);
    check('the squad the need is judged on is now labelled with the move', /signed in/.test(body), await lineWith(page, 'squad as of round'));
    await shot(page, 'market-after-signing');
  }

  // --- a loan is a temporary row ---------------------------------------------------------------------
  rows = await board(page);
  const loanable = rows.find((row) => row.buttons.find((button) => button.act === 'loan' && !button.disabled));
  check('an offer can be taken on loan from its own row', Boolean(loanable), loanable?.player);
  if (loanable) {
    const expected = Math.round((loanable.price * loanShare) / 5) * 5;
    await clickIn(page, `tr[data-listing="${loanable.id}"]`, 'button[data-act="loan"]');
    await until(page, 'arrives on loan');
    const line = await lineWith(page, 'arrives on loan');
    check('a loan is agreed for a stated number of rounds', /until round \d+/.test(line), line.slice(0, 150));
    check('the loan fee is the published share of the price', Math.abs((amount(line.match(/for ([\d,]+)/)?.[1] ?? 0) - expected) <= 5), `${line.match(/for ([\d,]+)/)?.[0]} against ${gb(expected)} = ${gb(loanable.price)}×${loanShare}`);
    const loaned = await untilDom(page, (name) => [...document.querySelectorAll('tr[data-player]')].some((row) => row.innerText.includes(name)), loanable.player);
    check('a loaned player is in the squad table', loaned, `${loaned ? 'row read' : `no ${loanable.player} row arrived`}`);
  }

  // --- selling, and the rule a sale has to leave standing --------------------------------------------
  const beforeSale = await stat(page, 'Remaining');
  const squadRowsNow = await squadRows(page);
  check('the squad table lists the players this career can sell', squadRowsNow.length >= 11, `${squadRowsNow.length} rows`);
  const keepers = squadRowsNow.filter((row) => (row.position || '').toUpperCase() === 'GK').length;
  const leavesSideStanding = (row) => (row.position || '').toUpperCase() !== 'GK' || keepers > 1;
  // Prefer the arrival this walk itself signed: selling it back is the round trip, and it is the case
  // where the ledger grows by two rows while the eleven ends up exactly where the world left it.
  const arrival = signedName ? squadRowsNow.find((row) => row.name === signedName && leavesSideStanding(row)) : null;
  const salable = arrival ?? squadRowsNow.find(leavesSideStanding);
  const soldAnArrival = Boolean(arrival && salable && salable.id === arrival.id);
  if (salable) {
    const proceeds = amount(salable.proceeds);
    await clickIn(page, `tr[data-player="${salable.id}"]`, 'button[data-act="sell"]');
    await until(page, 'sold to');
    const line = await lineWith(page, 'sold to');
    check('a sale names its buyer and its proceeds', line.includes('sold to') && /\d/.test(line), line.slice(0, 160));
    check('a sale states its own effect on the club', line.includes(String(rules.json?.move_effects?.sell)), line.slice(-110));
    const gone = await untilDom(page, (count) => document.querySelectorAll('tr[data-player]').length === count, squadRowsNow.length - 1);
    check('the sold player is out of the squad the page re-reads', gone, `${gone ? 'row count fell' : `still ${squadRowsNow.length} rows after the sale`}`);
    const afterSale = await stat(page, 'Remaining');
    check('the proceeds arrive at the published share', afterSale === beforeSale + proceeds, `${gb(beforeSale)} + ${gb(proceeds)} = ${gb(afterSale)}`);
    check('the ledger prints the sale as a plus against the same proceeds', (await text(page)).includes(`+${gb(proceeds)}`), `+${gb(proceeds)}`);
    // The page prints four squad figures; whatever was sold, they have to add up to the list beneath them.
    const kv = await gridValues(page);
    const fielded = (await squadRows(page)).length;
    const stored = Number(kv['stored by the world']);
    const signedIn = Number(kv['fielded here because this career brought them']);
    const letGo = Number(kv['the world stored them, this career let them go']);
    const sums = `${stored} stored + ${signedIn} in − ${letGo} out against ${fielded} rows listed`;
    check('the squad counts add up to the squad the page lists', fielded === stored + signedIn - letGo, sums);
    // The arrival count is reconciled against the deals this walk itself made, not against a number copied
    // out of the response: two deals in, one of them sold back on again, so one arrival is still fielded.
    const arrivalsInEffect = (buyable ? 1 : 0) + (loanable ? 1 : 0) - (soldAnArrival ? 1 : 0);
    check(
      'the arrival count is the deals the walk actually made',
      signedIn === arrivalsInEffect,
      `the page reads ${signedIn} in; the walk signed ${buyable ? 1 : 0}, loaned ${loanable ? 1 : 0}${soldAnArrival ? ' and sold one of those back' : ''}`,
    );
    if (soldAnArrival) {
      // Two rows in the ledger and a squad that owes the world nothing: a player who was never stored here
      // cannot leave a departure to count.
      check('a signing sold straight on leaves no departure behind', letGo === 0, `${letGo} out recorded for a player the world never stored at this club`);
    } else {
      check('selling a player the world stored counts exactly one departure', letGo === 1 && fielded === stored - 1, sums);
    }
  } else {
    check('a sale names its buyer and its proceeds', false, 'the squad table had no row a sale would leave a side standing');
  }
  body = await text(page);
  check('the rule that keeps a side on the pitch is printed beside the counts', /players and \d+ goalkeepers?/.test(body.replace(/\s+/g, ' ')), await lineWith(page, 'This squad reads'));
  await shot(page, 'market-traded');

  // --- the season page hands over to the market -------------------------------------------------------
  await open(page, `/career/${encodeURIComponent(ident)}`);
  await until(page, 'the market spends it');
  body = await text(page);
  check('the season page no longer calls the budget unspent', !/\(stated, unspent\)/i.test(body) && has(body, 'Budget (as it was stated)'));
  check('the season page links to the market', has(body, 'the market spends it'));
  const href = await page.evaluate((want) => [...document.querySelectorAll('a')].find((link) => link.innerText.replace(/\s+/g, ' ').trim() === want)?.getAttribute('href') ?? '', 'the market spends it');
  check('the link is this career’s market, not a generic page', href === `/career/${ident}/market`, href);

  // --- the wall ---------------------------------------------------------------------------------------
  const ownerContext = await browser.createBrowserContext();
  const rival = await ownerContext.newPage();
  await rival.setViewport(MOBILE);
  watch(rival, 'rival');
  await open(rival, '/login');
  await call(rival, 'POST', '/api/v1/auth/register', { email: `rival-${stamp}@footballos.test`, password: PASSWORD, display_name: 'Rival Manager', role: 'player', accepts_data_policy: true });
  const foreign = await open(rival, marketPath);
  check('another account gets 404 on this market, not 403', foreign.status() === 404, `HTTP ${foreign.status()}`);
  check('the 404 page shows no figures from the foreign career', !has(await text(rival), 'Spent on arrivals'));
  await ownerContext.close();

  const anonymousContext = await browser.createBrowserContext();
  const nobody = await anonymousContext.newPage();
  await nobody.setViewport(MOBILE);
  watch(nobody, 'anonymous');
  const redirected = await open(nobody, marketPath);
  check('a signed-out visitor is sent to the login page', redirected.url().includes('/login'), redirected.url());
  check('the redirect keeps the visitor out of the ledger', !has(await text(nobody), 'Spent on arrivals'));
  await anonymousContext.close();

  // --- robots, sitemap and the mobile shape ------------------------------------------------------------
  const robots = await (await fetch(`${BASE}/robots.txt`)).text();
  check('robots.txt disallows the career prefix the market lives under', robots.includes('/career'));
  const sitemap = await (await fetch(`${BASE}/sitemap.xml`)).text();
  check('the market is not advertised to crawlers', !sitemap.includes('/market'));
  await page.setViewport(MOBILE);
  await open(page, marketPath);
  await until(page, 'transfer market');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check('the market does not push the page sideways at 375px', overflow <= 2, `${overflow}px of horizontal overflow`);
  await shot(page, 'market-mobile');
  await page.setViewport(DESKTOP);

  // --- teardown: the walk deletes the careers it opened -------------------------------------------------
  for (const entry of opened) {
    const deleted = await call(page, 'DELETE', `/api/v1/careers/${entry.slug}`);
    check(`the walk deletes its own career at ${entry.club.slug}`, deleted.status === 200 && deleted.json?.deleted === true, `HTTP ${deleted.status} ${JSON.stringify(deleted.json)?.slice(0, 90)}`);
  }
  const afterDelete = await call(page, 'GET', `/api/v1/transfers/${ident}`);
  check("a deleted career's market answers 404 to its own owner", afterDelete.status === 404, `HTTP ${afterDelete.status}`);

  await page.close();
  await browser.close();

  const provoked = [
    /\/api\/v1\/transfers\/[^/]+\/buy: Failed to load resource: the server responded with a status of 409/,
    /\/api\/v1\/transfers\/[^/]+: Failed to load resource: the server responded with a status of 404/,
    /\/api\/v1\/transfers\/[^/]+\/buy: HTTP 409/,
    /\/career\/[^/]+\/market: Failed to load resource: the server responded with a status of 404/,
    /\/career\/[^/]+\/market: HTTP 404/,
  ];
  const unexpected = [...new Set(consoleErrors)].filter((line) => !provoked.some((pattern) => pattern.test(line)));
  check('every browser console error was one this walk provoked on purpose', unexpected.length === 0, unexpected.length ? unexpected.slice(0, 3).join(' | ') : `${consoleErrors.length} seen, all deliberate`);

  return finish();
}

function finish() {
  const failed = results.filter((row) => !row.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed. Screenshots: ${shots.length} -> docs/screenshots/`);
  if (consoleErrors.length) {
    console.log(`\nBrowser console errors (${consoleErrors.length}):`);
    for (const line of [...new Set(consoleErrors)].slice(0, 12)) console.log(`  - ${line.slice(0, 260)}`);
  }
  if (failed.length) {
    console.log('\nFailed checks:');
    for (const row of failed) console.log(`  - ${row.name}${row.detail ? ` — ${String(row.detail).slice(0, 200)}` : ''}`);
  }
  process.exitCode = failed.length ? 1 : 0;
}

main().catch((error) => {
  console.error(`market walk aborted: ${error?.message ?? error}`);
  console.log(`\n${results.filter((row) => row.ok).length}/${results.length} checks passed before the abort.`);
  process.exitCode = 2;
});
