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

import { readFileSync } from 'node:fs';
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

// §81 2c: the two catalogues the locale checks compare the painted page against, read off disk rather than
// off the page — a value read back out of the page would only ever agree with itself.
const catalogue = (locale) => JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), 'utf8'));
const english = catalogue('en');
const chinese = catalogue('zh');

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

/**
 * The buying board, read the way a reader reads it: a figure lives under the header printed above it.
 *
 * This helper used to pick the asking, clause, wage and fit out by column number and to report a row's shape as
 * a count of thirteen cells. The board has since grown a column, and the copied count went red while every
 * figure it named stayed exactly right — a position is a fact about the day the component was written, not about
 * the offer. The labels therefore come from the same catalogue the page renders its headers from, and each row is
 * read against **its own table's** headers. A header the board stops printing now yields an empty cell and a zero
 * figure, and the check above the first read says which header went missing by name.
 *
 * The badges the stylesheet sets in capitals (the rival marker, the answers-the-need marker) are compared
 * case-folded; every figure is compared exactly as printed.
 */
const BOARD_COLUMNS = {
  player: english.market.buyThPlayer,
  from: english.market.buyThFrom,
  asking: english.market.buyThAsking,
  price: english.market.buyThNow,
  clause: english.market.buyThClause,
  wage: english.market.buyThWage,
  fit: english.market.buyThFit,
  offers: english.market.buyThOffers,
};

function board(page) {
  return page.$$eval(
    'tr[data-listing]',
    (list, columns) =>
      list.map((row) => {
        const cells = [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim());
        const headers = [...(row.closest('table')?.querySelectorAll('thead th') ?? [])].map((head) => head.innerText.replace(/\s+/g, ' ').trim());
        const buttons = [...row.querySelectorAll('button[data-act]')].map((button) => ({ act: button.dataset.act, label: button.innerText.trim(), disabled: button.disabled }));
        const cellOf = (name) => cells[headers.findIndex((header) => header.toLowerCase() === name.toLowerCase())] ?? '';
        const figure = (name) => Number(cellOf(name).replace(/[^\d]/g, '')) || 0;
        return {
          id: row.dataset.listing,
          cells,
          headers,
          buttons,
          player: cellOf(columns.player).replace(/\s*answers the need$/i, '').trim(),
          fillsNeed: cellOf(columns.player).toUpperCase().includes('ANSWERS THE NEED'),
          rival: cellOf(columns.from).toUpperCase().includes('RIVAL'),
          asking: figure(columns.asking),
          price: figure(columns.price),
          clause: figure(columns.clause),
          wage: figure(columns.wage),
          fit: Number(cellOf(columns.fit)) || 0,
          offersCell: cellOf(columns.offers),
        };
      }),
    BOARD_COLUMNS,
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

/** The ledger, read as a reader reads it: one row per thing the career did or owed, in the order printed.
 * The cells come back as text and are parsed here, because a helper defined in Node does not exist inside
 * the page. */
async function ledgerRows(page) {
  const cells = await page.$$eval('[data-testid="ledger"] tbody tr', (list) =>
    list.map((row) => [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim())),
  );
  return cells.map((row) => ({
    round: Number((row[0] ?? '0').replace(/[^\d]/g, '')),
    kind: (row[1] ?? '').toUpperCase(),
    player: row[2] ?? '',
    fee: amount(row[4]),
    paid: (row[4] ?? '').startsWith('−') || (row[4] ?? '').startsWith('-'),
    after: Number((row[5] ?? '0').replace(/[^\d]/g, '')),
  }));
}

/** A button with no hook of its own is found by the words on it, which is what a visitor has. */
function clickText(page, want) {
  return page.evaluate((label) => {
    const button = [...document.querySelectorAll('button')].find((node) => node.innerText.replace(/\s+/g, ' ').trim() === label);
    if (!button) return 'missing';
    if (button.disabled) return 'disabled';
    button.click();
    return 'clicked';
  }, want);
}

/**
 * The wage sentence, read the way a reader reads it:
 * `… {rate} {units} a week across {players} deals stands charged; {paid} {units} has left the balance over {rows} rounds …`
 *
 * Matched as a sentence rather than scraped for every `[\d,]+` run: the note's own punctuation contains
 * commas, and a comma parsed as a figure is a zero that looks like a number. `parsed: false` is how the
 * walk says the sentence moved, so the checks that read it can fail loudly instead of reading silence.
 */
function wageFigures(line) {
  const found = String(line).match(/([\d,]+) [a-z ]+ a week across (\d+) deals? stands charged; ([\d,]+) [a-z ]+ has left the balance over (\d+) rounds?/);
  return { parsed: Boolean(found), rate: amount(found?.[1]), players: Number(found?.[2] ?? -1), paid: amount(found?.[3]), rows: Number(found?.[4] ?? -1) };
}

/** The line the page printed for the last thing it did. */
async function lineWith(page, needle) {
  const body = await text(page);
  return body.split('\n').find((line) => line.includes(needle)) ?? '';
}

/** Pages carry their copy in headings and definition lists the stylesheet sets in capitals, so a check
 * that quotes a sentence compares it case-folded. The figures are matched exactly, never folded. */
const has = (body, needle) => String(body).toLowerCase().includes(String(needle).toLowerCase());

/** Whitespace taken out, twice over: a long expression soft-wraps in a narrow column, and a row of the grid
 * wraps too. `squeeze` compares a figure-bearing sentence, `flatten` compares prose a reader hears as one
 * sentence however the column broke it. */
const squeeze = (value) => String(value).replace(/\s+/g, '');
const flatten = (value) => String(value).replace(/\s+/g, ' ').trim();

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

/**
 * The key/value rows of one panel, in the order that panel prints them.
 *
 * `gridValues` folds every grid on the page into a single object keyed by label, which is fine while each label
 * appears once and silently wrong the moment two panels share one — the rules grid prints its keys in English
 * (`budget`, `window`) and the window grid prints translated labels, so a collision would drop a row rather than
 * report it. A panel hook is the only way to read a grid as the panel that holds it.
 */
function panelGrid(page, testId) {
  return page.$$eval(
    `[data-testid="${testId}"] .world-kv__row`,
    (rows) =>
      rows.map((row) => ({
        key: (row.querySelector('dt')?.innerText ?? '').replace(/\s+/g, ' ').trim(),
        value: (row.querySelector('dd')?.innerText ?? '').replace(/\s+/g, ' ').trim(),
      })),
  );
}

/**
 * The catalogue's own sentence with its placeholders filled — the walk prints what the page prints.
 *
 * Named holes first, then the plural forms the catalogue carries (`{count, plural, one {# round} other {# rounds}}`),
 * because a check that compared a translated sentence had otherwise to spell the English out here in the walk —
 * which is the copy the §81 landing took off the page precisely so that a page cannot own its own wording.
 */
function interpolate(message, values) {
  const pluralised = String(message).replace(/\{(\w+), plural, one \{([^}]*)\} other \{([^}]*)\}\}/g, (_all, name, one, other) => {
    const count = Number(values[name]);
    return (count === 1 ? one : other).split('#').join(String(count));
  });
  return Object.entries(values).reduce((text, [name, value]) => String(text).split(`{${name}}`).join(String(value)), pluralised);
}

/**
 * A season's ranges, drawn from the two figures the view publishes with them.
 *
 * The same clipping and merging the service documents: the opening window reaches round `early`, the mid-season
 * window is `half` rounds either side of the season's halfway round, a range clipped past itself is dropped, and
 * a range that touches the one before it joins it — so the walk can refuse a board whose ranges the published
 * constants do not produce.
 */
function seasonWindows(seasonRounds, early, half) {
  const raw = [
    [1, Math.min(early, seasonRounds)],
    [Math.max(1, Math.floor(seasonRounds / 2) - half), Math.min(seasonRounds, Math.floor(seasonRounds / 2) + half)],
  ];
  const merged = [];
  for (const [low, high] of raw) {
    if (low > high) continue;
    const last = merged[merged.length - 1];
    if (last && low <= last.to_round + 1) last.to_round = Math.max(last.to_round, high);
    else merged.push({ from_round: low, to_round: high });
  }
  return merged;
}

/** The whole window block a career's round should produce, arithmetic only — the labels ride from the wire. */
function deriveWindow(signing, early, half) {
  const round = Number(signing.round);
  const seasonRounds = Number(signing.season_rounds);
  if (!(seasonRounds > 0)) {
    return {
      round,
      round_in_season: 0,
      season_index: 0,
      season_rounds: 0,
      state: 'open',
      windows: [],
      window_from_round: null,
      window_to_round: null,
      played_in_window: 0,
      signing_rounds_left: 0,
      opens_at_round: null,
      opens_at_season: null,
      opens_in_rounds: 0,
    };
  }
  const season_index = Math.floor((round - 1) / seasonRounds) + 1;
  const round_in_season = ((round - 1) % seasonRounds) + 1;
  const windows = seasonWindows(seasonRounds, early, half);
  const holding = windows.find((range) => round_in_season >= range.from_round && round_in_season <= range.to_round);
  const forward = windows.find((range) => range.from_round > round_in_season);
  const opens_at_round = holding ? null : forward ? forward.from_round : windows.length ? windows[0].from_round : null;
  const opens_at_season = holding ? null : forward ? season_index : windows.length ? season_index + 1 : null;
  const opens_in_rounds =
    opens_at_round === null || opens_at_season === null ? 0 : (opens_at_season - 1) * seasonRounds + opens_at_round - round;
  // The service counts the window it is standing in against the career's own stored rounds: the range's first
  // round is lifetime round `(season_index − 1) × season_rounds + from_round`, so the rounds already played
  // inside it are the gap to `rounds_played` (= this round − 1), capped at the range's own length.
  const window_from_round = holding ? holding.from_round : null;
  const window_to_round = holding ? holding.to_round : null;
  const played_in_window = holding
    ? Math.min(Math.max(0, round - 1 - ((season_index - 1) * seasonRounds + holding.from_round) + 1), holding.to_round - holding.from_round + 1)
    : 0;
  const signing_rounds_left = holding ? holding.to_round - round_in_season + 1 : 0;
  return {
    round,
    round_in_season,
    season_index,
    season_rounds: seasonRounds,
    state: holding ? 'open' : 'closed',
    windows,
    window_from_round,
    window_to_round,
    played_in_window,
    signing_rounds_left,
    opens_at_round,
    opens_at_season,
    opens_in_rounds,
  };
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });

  // --- the walk's own account, minted through the same proxy the login form uses --------------------
  const page = await browser.newPage();
  await page.setViewport(DESKTOP);
  watch(page, 'owner');
  // Pin the walk's own locale before the first navigation. `middleware.ts` picks the locale from the
  // `fo_locale` cookie, then `Accept-Language`, then English — and a zh-CN host makes the browser
  // negotiate Chinese, which every English label this walk reads would then miss (measured: the whole
  // empty-state block read a Chinese page and failed 8 checks on four clubs). The §81 2c block at the
  // end flips to zh and back deliberately; everything before it must start from a known English.
  await page.setCookie({ name: 'fo_locale', value: 'en', url: BASE });
  await open(page, '/login');
  const registered = await call(page, 'POST', '/api/v1/auth/register', { email: EMAIL, password: PASSWORD, display_name: 'Market QA', role: 'player', accepts_data_policy: true });
  check('a fresh account registers through the cookie proxy', registered.status === 201, `HTTP ${registered.status}`);
  const me = await call(page, 'GET', '/api/v1/auth/me');
  check('the session the proxy minted authenticates', me.status === 200 && me.json?.email === EMAIL, `HTTP ${me.status}`);

  const options = await call(page, 'GET', '/api/v1/careers/options');
  check('the clubs on offer come from the generated world', options.status === 200 && options.json?.clubs?.length > 0, `${options.json?.clubs?.length ?? 0} clubs`);
  const rules = await call(page, 'GET', '/api/v1/transfers/rules');
  const publicRules = Object.keys(rules.json?.rules ?? {});
  check('the market publishes its arithmetic to anyone, no session required', rules.status === 200 && publicRules.length > 0, `${publicRules.length} expressions`);
  check('the public rules are labelled fictional', rules.json?.data_origin === 'simulation' && rules.json?.is_demo_data === true, String(rules.json?.disclaimer).slice(0, 60));

  const weakest = [...(options.json?.clubs ?? [])].sort((a, b) => a.overall - b.overall || String(a.slug).localeCompare(String(b.slug)));
  const opened = [];
  let target = null;
  // The board's own constants come off the career door, not off the rules answer. `/transfers/rules` sends the
  // rule book and the move effects and nothing else, so `rules.json?.constants?.market_size ?? 12` read a field
  // that door does not publish and fell back to a number the walk invented — the board would have been checked
  // against the walk's own arithmetic, and reported as the site's.
  let wire = null;
  let size = 0;
  let loanShare = 0;

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
    // This career's own door answer, read before the page is asked to show it. Everything below compares the
    // painted page with what that door published beside it — the rule book, the constants the board is priced
    // against, and the signing window — so a figure the walk measures with is a figure the site sent.
    const fetched = await call(page, 'GET', `/api/v1/transfers/${encodeURIComponent(slug)}`);
    const view = fetched.json;
    check(
      `the career door answers the career the page is showing (${club.slug})`,
      fetched.status === 200 && Object.keys(view?.constants ?? {}).length >= 5 && Object.keys(view?.rules ?? {}).length > 0 && view?.window !== undefined,
      `HTTP ${fetched.status}, ${Object.keys(view?.constants ?? {}).length} constants, ${Object.keys(view?.rules ?? {}).length} rules, window ${view?.window ? 'published' : 'absent'}`,
    );
    if (view?.constants) {
      wire = wire ?? view;
      size = Number(wire.constants.market_size);
      loanShare = Number(wire.constants.loan_fee_share);
    }
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
      check('the wage rule says a round is charged, and an empty ledger has charged nothing', has(empty, 'charged every round') && has(empty, 'has left the balance over 0 rounds'), await lineWith(page, 'stands charged'));
      check('the weakest band is named with its four indices', /attack\s*[\d.]+/.test(empty) && /midfield\s*[\d.]+/.test(empty), await lineWith(page, 'attack'));
      check('the need says what it judged on and which squad it read', has(empty, 'Judged on') && has(empty, 'Squad the reading used'));
      // --- the rule book: the two doors first, then the panel that prints what they answered ------------------
      const publicBook = Object.entries(rules.json?.rules ?? {});
      const careerBook = Object.entries(view?.rules ?? {});
      const sorted = (keys) => keys.map((key) => key.toLowerCase()).sort().join(',');
      check(
        'the two doors answer the same rule book',
        publicBook.length > 0 && sorted(publicBook.map(([key]) => key)) === sorted(careerBook.map(([key]) => key)),
        `public ${publicBook.length}, career ${careerBook.length}${publicBook.length !== careerBook.length ? ` — ${publicBook.map(([key]) => key).join(', ')} | ${careerBook.map(([key]) => key).join(', ')}` : ''}`,
      );
      const printedRules = await panelGrid(page, 'market-rules');
      const printedNames = printedRules.map((row) => row.key.toLowerCase());
      const book = new Map(careerBook.map(([key, expression]) => [key.toLowerCase(), expression]));
      const rowNamed = (key) => printedRules.find((row) => row.key.toLowerCase() === key);
      const unprinted = [...book.keys()].filter((key) => !printedNames.includes(key));
      const unpublished = printedNames.filter((key) => !book.has(key));
      const paraphrased = printedNames.filter((key) => book.has(key) && squeeze(rowNamed(key).value) !== squeeze(book.get(key)));
      check(
        'the rules panel prints the book the doors published, name by name and sentence by sentence',
        printedRules.length > 0 && unprinted.length === 0 && unpublished.length === 0 && paraphrased.length === 0,
        `${book.size} published, ${printedRules.length} printed${unprinted.length ? ` — no row for ${unprinted.join(', ')}` : ''}${unpublished.length ? ` — rows no door published: ${unpublished.join(', ')}` : ''}${paraphrased.length ? ` — sentence differs: ${paraphrased.join(', ')}` : ''}`,
      );
      // The count this walk used to pin at a copied `11` is not what makes the census worth running. The two names
      // it reads by hand further down are `budget` — the balance quotes the rule — and `window`, the block below:
      // if the book ever loses one of them, the walk would be measuring with a sentence it never got.
      check('the book still holds the two rules this walk quotes by name', ['budget', 'window'].every((key) => printedNames.includes(key)), printedNames.join(', ') || '(the panel printed no rows)');
      const curve = (view?.constants?.age_curve ?? []).map((band) => `${band.ages}→×${band.weight}`).join('  ');
      check('the age curve is printed as the bands the constants publish', (view?.constants?.age_curve ?? []).length > 0 && squeeze(empty).includes(squeeze(curve)), await lineWith(page, '32-99'));

      // --- the signing window: the block the page was handed, and the arithmetic that drew it -----------------
      const signing = view?.window;
      const early = Number(view?.constants?.early_window_last_round);
      const half = Number(view?.constants?.mid_window_half_width);
      const pairs = (list) => (list ?? []).map((range) => `${range.from_round}-${range.to_round}`).join(' ');
      const expected = signing ? deriveWindow(signing, early, half) : null;
      const off = expected ? Object.entries(expected).filter(([field, value]) => field !== 'windows' && String(signing[field]) !== String(value)).map(([field, value]) => `${field}=${signing[field]}, not ${value}`) : ['no window block on the wire'];
      check(
        `the window block is the arithmetic its own published constants produce (round ${signing?.round} of a ${signing?.season_rounds}-round season)`,
        expected !== null && Number.isFinite(early) && Number.isFinite(half) && off.length === 0 && pairs(signing.windows) === pairs(expected.windows),
        `${off.length ? off.join(', ') : 'every field agrees'}${expected && pairs(signing.windows) !== pairs(expected.windows) ? ` | ranges ${pairs(signing.windows) || '(none)'} not ${pairs(expected.windows) || '(none)'}` : ''} | early=${early} half=${half}`,
      );
      const holding = expected?.windows.find((range) => Number(signing.round_in_season) >= range.from_round && Number(signing.round_in_season) <= range.to_round);
      check(
        'the range the block says holds this round is one of its own ranges, and does hold it',
        expected !== null && (holding ? (signing.windows ?? []).some((range) => range.label === signing.in_window && range.from_round === holding.from_round && range.to_round === holding.to_round) : signing.in_window === ''),
        `in_window=${JSON.stringify(signing?.in_window)} · round ${signing?.round_in_season} of season ${signing?.season_index} (${signing?.season_rounds} rounds, source ${signing?.season_source}) · holding=${holding ? `${holding.from_round}-${holding.to_round}` : 'nothing'}`,
      );
      const copy = english.market;
      const windowRows = await panelGrid(page, 'market-window');
      const rowFor = (label) => (windowRows.find((row) => row.key.toLowerCase() === String(label).toLowerCase()) ?? {}).value ?? null;
      const expectedRanges = (signing?.windows ?? []).map((range) => `${interpolate(copy.windowRange, { from: range.from_round, to: range.to_round })} ${range.label}`).join(' · ');
      // Which rows this panel must print is not a number copied off the page — it is every `kvWindow*` label the
      // market catalogue holds. Each is priced the way the page prices it, so a row whose arithmetic or shape moves
      // goes red here, and a label the catalogue grows without the walk learning to price it is named rather than
      // silently left out of the count.
      const windowRowValue = {
        kvWindowState: () => String(signing.state),
        kvWindowSeason: () => interpolate(copy.windowSeason, { index: signing.season_index, roundInSeason: signing.round_in_season, of: signing.season_rounds }),
        kvWindowSource: () => String(signing.season_source),
        kvWindowRanges: () => expectedRanges,
        kvWindowHeld: () => signing.in_window || copy.windowHeldNone,
        kvWindowPlayed: () =>
          signing.window_from_round === null || signing.window_to_round === null
            ? copy.windowHeldNone
            : interpolate(copy.windowPlayed, { played: signing.played_in_window, from: signing.window_from_round, to: signing.window_to_round }),
        kvWindowSigningLeft: () => interpolate(copy.windowSigningLeft, { count: signing.signing_rounds_left }),
        kvWindowNext: () =>
          signing.opens_at_round === null
            ? copy.windowNextOpen
            : interpolate(copy.windowNextAt, { round: signing.opens_at_round, season: signing.opens_at_season ?? 0, count: signing.opens_in_rounds }),
      };
      const kvLabels = Object.keys(copy).filter((key) => key.startsWith('kvWindow')).sort();
      const unpriced = kvLabels.filter((key) => !(key in windowRowValue));
      const rowPresent = (key) => windowRows.some((row) => row.key.toLowerCase() === copy[key].toLowerCase());
      const notPrinted = kvLabels.filter((key) => !rowPresent(key));
      const mispriced = kvLabels.filter((key) => rowPresent(key) && rowFor(copy[key]) !== windowRowValue[key]());
      const unlabelled = windowRows.filter((row) => !kvLabels.some((key) => copy[key].toLowerCase() === row.key.toLowerCase()));
      check(
        `the window panel prints the rows the catalogue labels, and only those (${kvLabels.length} labels, ${windowRows.length} rows)`,
        kvLabels.length > 0 && windowRows.length === kvLabels.length && unpriced.length === 0 && notPrinted.length === 0 && unlabelled.length === 0,
        windowRows.map((row) => `${row.key}=${row.value}`).join(' | ') +
          (unpriced.length ? ` — the walk cannot price ${unpriced.join(', ')}` : '') +
          (notPrinted.length ? ` — labelled but not printed: ${notPrinted.join(', ')}` : '') +
          (unlabelled.length ? ` — rows no label holds: ${unlabelled.map((row) => row.key).join(', ')}` : ''),
      );
      check(
        'every window row says what the window block says',
        mispriced.length === 0,
        mispriced.length
          ? mispriced.map((key) => `${copy[key]}: ${JSON.stringify(rowFor(copy[key]))}, not ${JSON.stringify(windowRowValue[key]())}`).join(' | ')
          : kvLabels.map((key) => `${key}=${JSON.stringify(windowRowValue[key]())}`).join(' | '),
      );
      check(
        'the notice says what the round falls inside, and the constants sentence names the two figures that drew the ranges',
        flatten(empty).includes(flatten(signing.state === 'open' ? interpolate(copy.windowOpen, { round: signing.round, range: signing.in_window }) : interpolate(copy.windowClosed, { round: signing.round, count: signing.opens_in_rounds }))) &&
          squeeze(empty).includes(squeeze(interpolate(copy.windowConstants, { early, width: 2 * half + 1, half }))) &&
          squeeze(empty).includes(squeeze(signing.formula)),
        `${signing.state} · ${await lineWith(page, 'deal could be struck') || await lineWith(page, 'No deal can be struck')}`,
      );
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
  const careerView = (await call(page, 'GET', `/api/v1/transfers/${ident}`)).json;
  const clauseShare = Number(careerView?.constants?.release_clause_share);
  const floorShare = Number(careerView?.constants?.negotiation_floor_share);
  let body = await text(page);
  check('opening a board from the page prints what the round did', /priced: \d+ offers/.test(body), await lineWith(page, 'priced:'));
  let rows = await board(page);
  const printedHeaders = rows[0]?.headers ?? [];
  const missingHeaders = Object.entries(BOARD_COLUMNS).filter(([, label]) => !printedHeaders.some((header) => header.toLowerCase() === label.toLowerCase()));
  check(
    'the board prints a header for every column this walk reads a figure from',
    printedHeaders.length > 0 && missingHeaders.length === 0,
    missingHeaders.length
      ? `nothing prints: ${missingHeaders.map(([name, label]) => `${name} (${label})`).join(", ")} — the row reads would be blank`
      : `${printedHeaders.length} headers: ${printedHeaders.join(" | ")}`,
  );
  check(
    'every offer carries one cell under every header the board prints',
    rows.length > 0 && rows.every((row) => row.cells.length === row.headers.length),
    `${rows[0]?.cells.length ?? 0} cells against ${rows[0]?.headers.length ?? 0} headers, across ${rows.length} row(s)`,
  );
  check('the clause is the published rounding of the share the constants publish', Number.isFinite(clauseShare) && rows.every((row) => Math.abs(row.clause - row.asking * clauseShare) <= 2.5), rows.slice(0, 3).map((row) => `${row.asking}→${row.clause}`).join(' ') + ` ×${clauseShare}`);
  check('the wage is the published rounding of the asking divided by 500', rows.every((row) => Math.abs(row.wage - row.asking / 500) <= 2.5), rows.slice(0, 3).map((row) => `${row.asking}/${row.wage}`).join(' '));
  check('the fit is a number the published formula can produce', rows.every((row) => row.fit >= 0 && row.fit <= 1), rows.slice(0, 4).map((row) => row.fit).join(' '));
  check('the board marks the players that fill the band the club is short in', rows.some((row) => row.fillsNeed), `${rows.filter((row) => row.fillsNeed).length} of ${rows.length} rows`);
  check('the board says which band it was picked against', has(body, `need: ${careerView?.need?.needed_band}`), await lineWith(page, 'priced offers'));
  check('no offer is priced above the balance and left buyable', rows.every((row) => row.rival || row.price <= BUDGET || row.buttons.find((item) => item.act === 'sign')?.disabled !== false), 'affordability is the server’s');

  // --- the seller answers an offer -------------------------------------------------------------------
  const negotiable = rows.find((row) => row.buttons.find((button) => button.act === 'offer' && !button.disabled));
  check('an offer can be put to a seller from its own row', Boolean(negotiable), negotiable?.player);
  if (negotiable) {
    const asking = negotiable.asking;
    const before = negotiable.price;
    const floor = Math.round((asking * floorShare) / 5) * 5;
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
    // The figure beside the word, not just the word: the floor is the asking times the published share, rounded
    // the way the rule says, so a page that narrated a floor the constants do not produce is refused here.
    const printedFloor = amount(answered.match(/floor ([\d,]+)/)?.[1] ?? '');
    check('the printed floor is the published share of the asking', Number.isFinite(floorShare) && printedFloor === floor, `${gb(printedFloor)} against ${gb(floor)} = ${gb(asking)}×${floorShare}`);
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
    check('the offer counter ticks down on the row', /2 left/.test(afterRow.offersCell), afterRow.offersCell);
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

  // --- the wage bill: play a round on the season page, then come back and read what it cost --------------
  // The rate is read off the market page *before* the round and the charge off the ledger *after* it, so the
  // walk is asking whether the page charged what it had promised, not whether two readings of one response
  // agree with each other.
  await open(page, marketPath);
  await until(page, 'stands charged');
  const standing = wageFigures(await lineWith(page, 'stands charged'));
  const remainingBefore = await stat(page, 'Remaining');
  const ledgerBefore = await ledgerRows(page);
  check('the standing wage rate is a sentence the walk can read before it plays', standing.parsed, await lineWith(page, 'stands charged'));
  check('the round the walk plays is one its deals cost something in', standing.rate > 0 && standing.players > 0, `${gb(standing.rate)} a week across ${standing.players} deal(s), ${gb(standing.paid)} paid over ${standing.rows} round(s)`);

  await open(page, `/career/${encodeURIComponent(ident)}`);
  await until(page, 'Play the next round');
  const played = await clickText(page, 'Play the next round');
  check('the season page’s own button plays a round', played === 'clicked', played);
  const roundLanded = await until(page, 'Round 1 played:');
  check('the round arrives on the page that asked for it', roundLanded, await lineWith(page, 'Round 1 played'));

  await open(page, marketPath);
  await until(page, 'stands charged');
  body = await text(page);
  const afterRound = wageFigures(await lineWith(page, 'stands charged'));
  const ledger = await ledgerRows(page);
  const charges = ledger.filter((row) => row.kind === 'WAGE');
  const remainingAfter = await stat(page, 'Remaining');
  check('a played round is a row in the ledger, not a sentence about one', charges.length === 1 && ledger.length === ledgerBefore.length + 1, `${charges.length} wage row(s) of ${ledger.length} ledger rows`);
  check('the wage row is stamped for the round that was played', charges[0]?.round === 1, `round ${charges[0]?.round ?? '—'}`);
  check('the round charged exactly the rate printed before it', afterRound.parsed && charges[0]?.fee === standing.rate && standing.rate > 0, `${gb(standing.rate)} agreed · ${gb(charges[0]?.fee ?? 0)} charged`);
  check('the wage row takes money out and names nobody', charges[0]?.paid === true && /^\d+ players? on wages/.test(charges[0]?.player ?? ''), (charges[0]?.player ?? '').slice(0, 60));
  check('the wage row spells out the deals it was raised on', /[A-Z][a-z]+ [A-Z][a-z]+ [\d,]+/.test(charges[0]?.player ?? ''), (charges[0]?.player ?? '').slice(-90));
  check('the balance falls by the wage and by nothing else', remainingBefore - remainingAfter === standing.rate, `${gb(remainingBefore)} − ${gb(standing.rate)} = ${gb(remainingAfter)}`);
  check('the wage row prints the balance the round left', charges[0]?.after === remainingAfter, `${gb(charges[0]?.after ?? 0)} beside a Remaining of ${gb(remainingAfter)}`);
  check(
    'the paid-in-wages figure is the sum of the wage rows',
    afterRound.parsed && afterRound.paid === standing.paid + (charges[0]?.fee ?? 0) && afterRound.paid === charges.reduce((total, row) => total + row.fee, 0),
    `${gb(standing.paid)} + ${gb(charges[0]?.fee ?? 0)} = ${gb(afterRound.paid)}`,
  );
  check('the rate the round cost is still the rate standing after it', afterRound.rate === standing.rate && afterRound.rows === standing.rows + 1, `${gb(standing.rate)} a week over ${standing.rows} round(s) before · ${gb(afterRound.rate)} over ${afterRound.rows} after`);
  // The reader's arithmetic, done in the browser: the column adds up from the stated budget to the last row.
  let running = await stat(page, 'Stated budget');
  const brokeAt = ledger.find((row) => {
    running += row.paid ? -row.fee : row.fee;
    return row.after !== running;
  });
  check('every row of the ledger prints the standing its predecessors left', !brokeAt, brokeAt ? `${brokeAt.kind} at round ${brokeAt.round} says ${gb(brokeAt.after)}, adding up gives ${gb(running)}` : `${ledger.length} rows, one running total`);
  const sumLine = (await lineWith(page, 'stated')).replace(/\s+/g, ' ');
  // The sentence is the whole budget as a reader is told to check it, so the walk checks it that way: the
  // figures it prints, added by hand, have to land on the balance it prints.
  const sum = sumLine.match(/([\d,]+) stated(?: \+ ([\d,]+) received)?(?: \+ ([\d,]+) in board grants)?(?: \+ ([\d,]+) in objective bonuses)?(?: − ([\d,]+) spent)?(?: − ([\d,]+) in wages)? = ([\d,]+)/);
  const credits = (figure) => Number(String(figure ?? 0).replace(/,/g, ''));
  check(
    'the balance sentence names the wages it netted and adds up to its own answer',
    Boolean(sum) && credits(sum?.[1]) + credits(sum?.[2]) + credits(sum?.[3]) + credits(sum?.[4]) - credits(sum?.[5]) - credits(sum?.[6]) === credits(sum?.[7]) && credits(sum?.[6]) === afterRound.paid,
    sumLine.slice(0, 170),
  );
  check('the rule that charged the round is on the page', has(body, 'wage charge for a round'), await lineWith(page, 'wage charge for a round'));
  await shot(page, 'market-after-round');

  // --- §81 2c: the route reads its catalogue (2026-10-15, `4f5c284`) ------------------------------------
  // The same three reads every wired page gets: the Chinese catalogue's own strings are what the page
  // paints, the English labels they replaced are gone, and switching back leaves it English. Two things
  // this page needs that `/career` did not. First, the English-absent half has to name **long** labels and
  // only catalogue-owned ones: this route also prints the door's own prose — the rule expressions,
  // `budget.wage_note`, `fielding.rule`, `market.note` — which is English in every locale by design, so a
  // body-level "no English here" assertion would be measuring the API, not the wiring. `Buying` and
  // `Balance after` are short enough to collide with that prose, so the four sentences below are the ones
  // asserted. Second, the heading is the club's name plus a catalogue suffix, so it is compared by suffix:
  // the club name is the world's data and does not translate.
  await page.setCookie({ name: 'fo_locale', value: 'zh', url: BASE });
  await open(page, marketPath);
  await until(page, chinese.market.buyingTitle);
  const marketZh = await page.evaluate(() => ({
    h1: document.querySelector('h1')?.textContent.trim() ?? '',
    body: document.body.innerText.replace(/\s+/gu, ' '),
  }));
  check(
    'the transfer market in Chinese renders the catalogue: the panel titles and the ledger headers come from messages/zh.json',
    marketZh.h1.endsWith(chinese.market.titleSuffix) &&
      marketZh.body.includes(chinese.market.buyingTitle) &&
      marketZh.body.includes(chinese.market.needTitle) &&
      marketZh.body.includes(chinese.market.squadTitle) &&
      marketZh.body.includes(chinese.market.ledgerTitle) &&
      marketZh.body.includes(chinese.market.thBalanceAfter),
    `h1 ${marketZh.h1} · buying ${marketZh.body.includes(chinese.market.buyingTitle)} · need ${marketZh.body.includes(chinese.market.needTitle)} · squad ${marketZh.body.includes(chinese.market.squadTitle)} · ledger ${marketZh.body.includes(chinese.market.ledgerTitle)} · th ${marketZh.body.includes(chinese.market.thBalanceAfter)}`,
  );
  check(
    'and the English labels are gone from the Chinese market',
    !marketZh.body.includes(english.market.needTitle) &&
      !marketZh.body.includes(english.market.squadTitle) &&
      !marketZh.body.includes(english.market.ledgerTitle) &&
      !marketZh.body.includes(english.market.rulesTitle),
    `en need present ${marketZh.body.includes(english.market.needTitle)} · en squad ${marketZh.body.includes(english.market.squadTitle)} · en ledger ${marketZh.body.includes(english.market.ledgerTitle)} · en rules ${marketZh.body.includes(english.market.rulesTitle)}`,
  );
  await shot(page, 'market-chinese');
  await page.setCookie({ name: 'fo_locale', value: 'en', url: BASE });
  await open(page, marketPath);
  await until(page, english.market.buyingTitle);
  const marketBackEn = await page.evaluate(() => ({
    h1: document.querySelector('h1')?.textContent.trim() ?? '',
    body: document.body.innerText.replace(/\s+/gu, ' '),
  }));
  check(
    'switching back leaves the market in English',
    marketBackEn.h1.endsWith(english.market.titleSuffix) &&
      marketBackEn.body.includes(english.market.ledgerTitle) &&
      !marketBackEn.body.includes(chinese.market.ledgerTitle),
    `h1 ${marketBackEn.h1} · en ledger ${marketBackEn.body.includes(english.market.ledgerTitle)} · zh ledger still present ${marketBackEn.body.includes(chinese.market.ledgerTitle)}`,
  );

  // The walk allows one browser habit in its console gate, and this is the check that pays for it: the icon
  // the document declares is really served, so a legacy `/favicon.ico` probe missing is not an asset lost.
  const iconHref = await page.evaluate(() => document.querySelector('link[rel="icon"]')?.getAttribute('href') ?? '');
  const icon = iconHref ? await call(page, 'GET', iconHref.split('?')[0]) : { status: 0 };
  check('the icon the page declares is the icon the server answers', iconHref.includes('icon.svg') && icon.status === 200, `${iconHref || '(none declared)'} → HTTP ${icon.status}`);

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
    // Chrome asks for the legacy `/favicon.ico` beside the icon this app declares, whatever the answer is.
    // The allowance above is paid for by the check that the declared icon is really served — without that
    // check this line would be hiding a missing asset rather than naming a browser habit.
    /\/favicon\.ico: Failed to load resource: the server responded with a status of 404/,
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
