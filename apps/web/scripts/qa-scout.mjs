/**
 * The §23/§24/§27 scouting screen's own evidence walk: a browser against a **production build**, doing the
 * four things the page claims to do — read a sentence without searching it, search the stored pool, ask for
 * one player's report, and set two players side by side — and reading back the arithmetic each one leaves.
 *
 *   api tier:  http://127.0.0.1:8734        (uvicorn app.main:app --port 8734)
 *   web tier:  http://127.0.0.1:3213        (API_INTERNAL_URL=… next start -p 3213)
 *   QA_BASE=http://127.0.0.1:3213 node scripts/qa-scout.mjs
 *
 * A separate script from `visual-qa.mjs` on purpose: that walk is another milestone's live working copy, and
 * a page cannot be folded into it without editing underneath its author.
 *
 * What the walk refuses to do is trust the page's own prose. Every figure it checks is read out of the DOM a
 * visitor sees and re-computed there; the buttons are pressed, not bypassed; and the comparison is checked for
 * the arithmetic it prints *and* for the single score it must not print.
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

const BASE = process.env.QA_BASE ?? 'http://127.0.0.1:3213';
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1 };
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };
const PASSWORD = 'scout-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const EMAIL = `scout-qa-${stamp}@footballos.test`;

/** One sentence that filters three things, assumes one unit and refuses one phrase — the whole honesty surface. */
const QUERY = '找一个 22 岁以下、左脚、擅长推进、预算 2000 万以下的中场';
const REFUSED_PHRASE = '擅长推进';
const REFUSED_MESSAGE = 'is not a position, band, role, foot, age, fee or attribute floor this parser knows';
const ROLE = 'CM';

const results = [];
const consoleErrors = [];
const shots = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${String(detail).slice(0, 190)}` : ''}`);
}

const amount = (text) => Number(String(text).replace(/[^\d]/g, '')) || 0;
const decimal = (text) => Number(String(text).replace(/[^\d.\-]/g, '')) || 0;
/** The stylesheet sets eyebrows and badges in capitals, so copy is compared case-folded. Figures are not. */
const has = (body, needle) => String(body).toLowerCase().includes(String(needle).toLowerCase());

async function shot(page, name) {
  const file = `${stamp}-scout-${name}.png`;
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

/** Headings and badges are set in capitals by the stylesheet, so a wait compares case-folded text.
 * Figures are never folded: they are matched exactly as printed. */
async function untilText(page, needle, timeout = 60_000) {
  try {
    await page.waitForFunction(
      (want) => (document.body?.innerText ?? '').toLowerCase().includes(String(want).toLowerCase()),
      { timeout, polling: 400 },
      needle,
    );
    return true;
  } catch {
    return false;
  }
}

/** Wait until a named button exists and is enabled — the page's own signal that its re-read has finished. */
async function waitEnabled(page, label, timeout = 30_000) {
  try {
    await page.waitForFunction(
      (want) => {
        const button = [...document.querySelectorAll('button')].find((node) => node.innerText.replace(/\s+/g, ' ').trim() === want);
        return Boolean(button) && !button.disabled;
      },
      { timeout, polling: 250 },
      label,
    );
    return true;
  } catch {
    return false;
  }
}

async function untilDom(page, predicate, arg, timeout = 30_000) {
  try {
    await page.waitForFunction(predicate, { timeout, polling: 250 }, arg);
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
      return { status: response.status, json, robots: url.endsWith('.txt') || url.endsWith('.xml') ? String(payload ?? '') : '' };
    },
    method,
    path,
    body ?? null,
  );
}

/** Fetch a plain-text route (robots.txt, sitemap.xml) the same way a crawler would: no session needed. */
function fetchText(page, path) {
  return page.evaluate(async (url) => {
    const response = await fetch(url, { credentials: 'same-origin' });
    return { status: response.status, body: await response.text() };
  }, path);
}

/** A React-controlled input needs the native setter plus an `input` event; CJK cannot be typed key by key. */
function setInput(page, selector, value) {
  return page.evaluate(
    (needle, want) => {
      const node = document.querySelector(needle);
      if (!node) return 'missing';
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(node, want);
      node.dispatchEvent(new Event('input', { bubbles: true }));
      return 'set';
    },
    selector,
    value,
  );
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

function clickSelector(page, selector) {
  return page.evaluate((needle) => {
    const button = document.querySelector(needle);
    if (!button) return 'missing';
    if (button.disabled) return 'disabled';
    button.click();
    return 'clicked';
  }, selector);
}

/** Every key/value the report prints, keyed by the label a visitor sees and scoped to the report itself. */
function reportGrid(page) {
  return page.$$eval('[data-testid="scout-report"] .world-kv__row', (rows) =>
    Object.fromEntries(
      rows.map((row) => [
        (row.querySelector('dt')?.innerText ?? '').replace(/\s+/g, ' ').trim().toLowerCase(),
        (row.querySelector('dd')?.innerText ?? '').replace(/\s+/g, ' ').trim(),
      ]),
    ),
  );
}

/** The candidate table, read in the page's own column order. */
function candidateRows(page) {
  return page.$$eval('tr[data-candidate]', (list) =>
    list.map((row) => ({
      slug: row.dataset.candidate,
      cells: [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim()),
    })),
  );
}

/** The waterfall, as printed: kind, phrase, rows in, cut, rows out, rule. A helper defined in Node does not
 * exist inside the page, so the cell reader is written again here rather than imported. */
function waterfallRows(page) {
  return page.$$eval('tr[data-cut-row]', (list) => {
    const digits = (value) => Number(String(value).replace(/[^\d]/g, '')) || 0;
    return list.map((row) => {
      const cell = [...row.querySelectorAll('td')].map((node) => node.innerText.replace(/\s+/g, ' ').trim());
      return { kind: cell[0] ?? '', phrase: cell[1] ?? '', in: digits(cell[2]), cut: digits(cell[3]), out: digits(cell[4]), rule: cell[5] ?? '' };
    });
  });
}

/** A table inside the report, found by the first word of its own header — the cell reader is written again
 * here because a Node helper does not cross into the page. */
function reportTable(page, header) {
  return page.$$eval('[data-testid="scout-report"] table', (tables, want) => {
    const cellText = (row) => [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim());
    const table = tables.find((node) => (node.querySelector('th')?.innerText ?? '').trim().toLowerCase() === want);
    if (!table) return [];
    return [...table.querySelectorAll('tbody tr')].map(cellText);
  }, header);
}

/** The four attribute-group rows: group, mean, `measured of total`, strongest, weakest, missing. */
function groupRows(page) {
  return reportTable(page, 'group');
}

/** The role-fit rows: attribute, demanded, have, gap, verdict. */
function roleFitRows(page) {
  return reportTable(page, 'attribute');
}

/** Every measure row the comparison prints, in document order, with the block it belongs to. */
function measureRows(page) {
  return page.$$eval('[data-dimension]', (blocks) =>
    blocks.flatMap((block) =>
      [...block.querySelectorAll('tr[data-measure]')].map((row) => ({
        dimension: block.dataset.dimension,
        leader: (block.querySelector('summary .badge')?.innerText ?? '').replace(/\s+/g, ' ').trim(),
        cells: [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim()),
      })),
    ),
  );
}

function dimensionBlocks(page) {
  return page.$$eval('[data-dimension]', (blocks) =>
    blocks.map((block) => ({
      dimension: block.dataset.dimension,
      leader: (block.querySelector('summary .badge')?.innerText ?? '').replace(/\s+/g, ' ').trim().toUpperCase(),
      scorable: block.querySelectorAll('tr[data-measure]').length,
    })),
  );
}

async function lineWith(page, needle) {
  const body = await text(page);
  return body.split('\n').find((line) => line.toLowerCase().includes(String(needle).toLowerCase())) ?? '';
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage'] });

  // --- the walk's own account, minted through the same proxy the login form uses ---------------------
  const page = await browser.newPage();
  await page.setCookie({ name: 'fo_locale', value: 'en', url: BASE });
  await page.setViewport(DESKTOP);
  watch(page, 'scout');
  await open(page, '/login');
  const registered = await call(page, 'POST', '/api/v1/auth/register', {
    email: EMAIL,
    password: PASSWORD,
    display_name: 'Scout QA',
    role: 'player',
    accepts_data_policy: true,
  });
  check('a fresh account registers through the cookie proxy', registered.status === 201, `HTTP ${registered.status}`);
  const me = await call(page, 'GET', '/api/v1/auth/me');
  check('the session the proxy minted authenticates', me.status === 200 && me.json?.email === EMAIL, `HTTP ${me.status}`);

  // --- a session-gated screen says so in three places -------------------------------------------------
  const robots = await fetchText(page, '/robots.txt');
  check('robots.txt disallows the scouting screen', robots.status === 200 && robots.body.includes('Disallow: /scout'), `HTTP ${robots.status}`);
  const sitemap = await fetchText(page, '/sitemap.xml');
  check('the sitemap does not advertise a page a visitor cannot reach', sitemap.status === 200 && !sitemap.body.includes('/scout'), `${sitemap.body.split('<loc>').length - 1} urls`);
  const rules = await call(page, 'GET', '/api/v1/scout/rules');
  check('the scout publishes its own vocabulary and integrity report', rules.status === 200 && rules.json?.integrity?.clean === true, `${Object.keys(rules.json?.roles ?? {}).length} roles · ${rules.json?.attributes?.length ?? 0} attributes`);
  const pool = Number(rules.json?.integrity?.counts?.players_stored ?? 0);
  const listRules = rules.json?.shortlists ?? {};
  check('the published rules carry the attribute vocabulary §24 averages over', rules.json?.attributes?.length === 27 && Array.isArray(rules.json?.fields), `${rules.json?.attributes?.length} attributes · ${rules.json?.fields?.length ?? 0} fields`);

  const anonymous = await browser.createBrowserContext();
  const anonPage = await anonymous.newPage();
  await anonPage.setCookie({ name: 'fo_locale', value: 'en', url: BASE });
  await anonPage.goto(`${BASE}/scout`, { waitUntil: 'networkidle2', timeout: 90_000 });
  check('an anonymous visitor is sent to the login screen', new URL(anonPage.url()).pathname.startsWith('/login'), new URL(anonPage.url()).pathname + new URL(anonPage.url()).search);
  await anonymous.close();

  await open(page, '/scout');
  await untilText(page, 'Ask the scout in your own words');
  const meta = await page.evaluate(() => document.querySelector('meta[name="robots"]')?.content ?? '');
  check('the page tells a crawler not to index or follow it', meta.toLowerCase().includes('noindex'), meta);
  const body = await text(page);
  check('the page announces the pool it searches', has(body, `${pool} stored players`), (await lineWith(page, 'stored players')).slice(0, 120));
  check('the nav offers the scouting screen', has(body, 'Scouting'), 'nav label');
  check('the page prints the comparison rule before a pair exists', has(body, 'no overall rating'), (await lineWith(page, 'no overall rating')).slice(0, 140));
  await shot(page, 'scout-page');

  // --- words are checked before they are spent --------------------------------------------------------
  check('the request field takes the sentence', (await setInput(page, 'input[aria-label="Scouting request"]', QUERY)) === 'set');
  check('the role field takes the role the fit is judged against', (await setInput(page, 'input[aria-label="Role to judge the fit against"]', ROLE)) === 'set');
  check('checking the words is a button the page offers', (await clickText(page, 'Check my words first')) === 'clicked');
  check('the parse answer arrives', await untilText(page, 'What your sentence would filter'));
  const parsedEmpty = await page.evaluate(() => document.querySelectorAll('tr[data-candidate]').length);
  check('checking the words read no rows, and says so', parsedEmpty === 0, `${parsedEmpty} candidate rows after a parse`);
  const parsedText = await page.evaluate(() => document.querySelector('[data-testid="scout-parse"]')?.innerText ?? '');
  check('a phrase outside the vocabulary is refused with its own sentence', parsedText.includes(REFUSED_PHRASE) && parsedText.includes(REFUSED_MESSAGE), parsedText.replace(/\s+/g, ' ').slice(0, 160));
  check('the fee assumption prints the number it read', parsedText.includes('20,000,000'), (parsedText.match(/was read as [\d,]+/) ?? [''])[0]);
  check('nothing was left unaccounted for', !parsedText.includes('neither parsed nor refused'), 'the unaccounted warning is absent');
  await shot(page, 'scout-parse');

  // --- the search, and the waterfall that proves it ---------------------------------------------------
  check('searching is a separate button', (await clickText(page, 'Search the world')) === 'clicked');
  check('the candidate table arrives', await untilDom(page, () => document.querySelectorAll('tr[data-candidate]').length > 0));
  check('the waterfall arrives with it', await untilText(page, 'How the pool was cut'));
  const searchHead = await lineWith(page, 'rows examined');
  const cuts = await waterfallRows(page);
  check('every stated filter shows up as a cut', cuts.length >= 3, `${cuts.length} cuts: ${cuts.map((row) => row.kind).join(', ')}`);
  const arithmetic = cuts.map((row) => `${row.in}−${row.cut}=${row.out}${row.in - row.cut === row.out ? '' : ' WRONG'}`);
  check('every cut closes: rows in minus cut equals rows out', arithmetic.every((line) => !line.includes('WRONG')), arithmetic.join(' · '));
  const chained = cuts.slice(1).every((row, index) => row.in === cuts[index].out);
  check('each cut starts where the previous one ended', chained, cuts.map((row) => row.in).join(' → '));
  check('the waterfall starts from the stored pool the page announced', cuts[0]?.in === pool, `first rows in ${cuts[0]?.in} vs ${pool} stored`);
  check('the pool the header examined is the pool the waterfall entered', searchHead.includes(String(pool)), searchHead.slice(0, 90));
  const printedMatches = Number(amount((searchHead.match(/(\d+)\s*match/i) ?? [])[1]));
  check('the last cut leaves exactly the number of matches printed', cuts[cuts.length - 1]?.out === printedMatches, `${cuts[cuts.length - 1]?.out} out vs ${printedMatches} in the header`);
  check('a refused phrase never became a filter', !cuts.some((row) => row.phrase.includes(REFUSED_PHRASE)), cuts.map((row) => row.phrase).join(' | '));
  const searchText = await text(page);
  check('the refusal is still printed above the results', searchText.includes(REFUSED_MESSAGE), 'the search panel repeats what was refused');
  const printed = await candidateRows(page);
  const truncLine = ((await text(page)).split('\n').find((line) => /only the first \d+ of \d+/i.test(line)) ?? '').trim();
  const truncation = truncLine.match(/only the first (\d+) of (\d+)/i);
  const expectedRows = truncation ? Number(truncation[1]) : printedMatches;
  check('the table prints as many rows as the page says it returned', printed.length === expectedRows && expectedRows > 0, `${printed.length} rows · the page says ${expectedRows}${truncation ? ' (truncated, and says so)' : ' (whole match set)'}`);
  check('a truncated answer is labelled with the number it withheld', truncation ? Number(truncation[2]) === printedMatches : true, truncLine.slice(0, 120) || `no truncation notice and ${printedMatches} matches`);
  const agesOk = printed.every((row) => Number(row.cells[1]) <= 22);
  const feetOk = printed.every((row) => (row.cells[3] ?? '').toLowerCase() === 'left');
  check('every candidate honours the stated age ceiling', agesOk, printed.map((row) => row.cells[1]).join(','));
  check('every candidate honours the stated foot', feetOk, printed.map((row) => row.cells[3]).join(','));
  const headroomOk = printed.every((row) => Number(row.cells[5]) - Number(row.cells[4]) === Number(row.cells[6]));
  check('headroom is printed as potential minus overall for every row', headroomOk, printed.slice(0, 3).map((row) => `${row.cells[4]}/${row.cells[5]}/${row.cells[6]}`).join(' · '));
  await shot(page, 'scout-search');

  // --- one report, and the arithmetic it claims --------------------------------------------------------
  const firstSlug = printed[0]?.slug;
  check('a candidate row offers its own report button', Boolean(firstSlug) && (await clickSelector(page, `button[data-report="${firstSlug}"]`)) === 'clicked', `button[data-report="${firstSlug}"]`);
  check('the report arrives', await untilDom(page, () => document.querySelectorAll('[data-testid="scout-report"]').length === 1));
  const grid = await reportGrid(page);
  check('the report prints its thirteen fields', has(await text(page), '13 fields'), (await lineWith(page, '/scout/report')).slice(0, 110));
  const overall = decimal(grid['overall']);
  const recomputedLine = grid['recomputed'] ?? '';
  check('the recomputed overall agrees with the stored column', recomputedLine.includes('agrees with the stored column') && decimal(recomputedLine) === overall, `stored ${overall} · recomputed ${recomputedLine.slice(0, 60)}`);
  const percentile = (grid['percentile'] ?? '').match(/([\d.]+)% of (\d+) rows · ([\d.]+)% inside (\w+) \((\d+) rows\)/);
  check('both percentile shares are printed against a row count', Boolean(percentile) && Number(percentile[2]) === pool, (grid['percentile'] ?? '').slice(0, 120));
  check('the band share is a share of a band no larger than the pool', Boolean(percentile) && Number(percentile[5]) <= Number(percentile[2]), (grid['percentile'] ?? '').slice(0, 120));
  const ceiling = decimal(grid['ceiling']);
  const headroom = decimal(grid['headroom']);
  check('the report keeps the two ratings the search sorted on', ceiling >= overall && headroom === ceiling - overall, `ceiling ${ceiling} − overall ${overall} = headroom ${headroom}`);
  const weekly = amount(grid['weekly wage']);
  const season = amount(grid['season wage']);
  check('a season of wages is fifty-two printed weeks', season === weekly * 52, `${weekly} × 52 = ${season}`);
  const asking = amount(grid['asking fee']);
  const value = decimal(grid['value for money']);
  check('value for money is overall per printed million of the asking fee', asking > 0 && Math.abs(value - (overall * 1_000_000) / asking) <= 0.1, `${value} vs ${(overall * 1_000_000) / asking}`);
  const groups = await groupRows(page);
  const denominators = groups.map((row) => Number((row[2] ?? '').split('of')[1] ?? '0'));
  const numerators = groups.map((row) => Number((row[2] ?? '').split('of')[0] ?? '0'));
  check('a report reads every attribute group it averages over', groups.length === 4, groups.map((row) => row[0]).join(', '));
  check('the groups add up to the twenty-seven keys a stored row carries', denominators.reduce((a, b) => a + b, 0) === 27, denominators.join(' + '));
  check('a generated row leaves no key unmeasured', numerators.every((n, index) => n === denominators[index]), `${numerators.join('/')} of ${denominators.join('/')}`);
  const fits = await roleFitRows(page);
  const gapOk = fits.every((row) => decimal(row[3]) === Number(row[2]) - Number(row[1]));
  check('a role gap is printed as what the player has minus what the role demands', fits.length > 0 && gapOk, `${fits.length} attributes · ${fits.slice(0, 3).map((row) => `${row[2]}−${row[1]}=${row[3]}`).join(' · ')}`);
  const reportText = await page.evaluate(() => document.querySelector('[data-testid="scout-report"]')?.innerText ?? '');
  check('an unanswered field is printed as null, not as a number', reportText.includes('team_fit: null'), 'no career was named, so no club need was judged');
  check('the verdict names the figures that decided it', /decided by/.test(reportText), (reportText.match(/decided by[^\n]*/) ?? [''])[0].slice(0, 120));
  check('no risk is reported as no risk, not as safety', /No factor matched|risk factor/i.test(reportText), (reportText.match(/[^\n]*factor[^\n]*/i) ?? [''])[0].slice(0, 120));
  await shot(page, 'scout-report');

  // --- the pair, which must never become a ranking ------------------------------------------------------
  const secondSlug = printed[1]?.slug;
  check('the first candidate takes slot A', (await clickSelector(page, `button[data-slot="${firstSlug}"]`)) === 'clicked', firstSlug);
  check('the second candidate takes slot B', (await clickSelector(page, `button[data-slot="${secondSlug}"]`)) === 'clicked', secondSlug);
  const slotLabels = await page.$$eval('button[data-slot]', (list) => list.filter((node) => node.innerText.trim() === 'A' || node.innerText.trim() === 'B').map((node) => `${node.dataset.slot}:${node.innerText.trim()}`));
  check('two candidates are held as A and B', slotLabels.length === 2, slotLabels.join(' · '));
  check('comparing is a button the page offers', (await clickText(page, 'Compare the pair')) === 'clicked');
  check('the comparison arrives', await untilDom(page, () => document.querySelectorAll('[data-testid="scout-compare"]').length === 1));
  // A closed `<details>` prints nothing at all, so every block is opened before it is read: the walk checks
  // the seven dimensions the page folds away, not only the three it leaves open.
  await page.evaluate(() => {
    for (const node of document.querySelectorAll('[data-testid="scout-compare"] details')) node.open = true;
  });
  const compareText = await page.evaluate(() => document.querySelector('[data-testid="scout-compare"]')?.innerText ?? '');
  const blocks = await dimensionBlocks(page);
  check('the comparison answers ten dimensions', blocks.length === 10, blocks.map((row) => row.dimension).join(', '));
  const chip = compareText.match(/(\d+) dimensions · (\d+) measures/);
  const measured = await measureRows(page);
  check('the counts the panel prints are the rows it prints', Boolean(chip) && Number(chip[1]) === blocks.length && Number(chip[2]) === measured.length, `${chip?.[1]}/${chip?.[2]} vs ${blocks.length} blocks · ${measured.length} measures`);
  const vocabulary = new Set(['A AHEAD', 'B AHEAD', 'EVEN', 'SPLIT', 'UNRESOLVED', 'UNKNOWN', 'NOT SCORABLE']);
  check('every dimension answers with a side or an honest tie', blocks.every((row) => vocabulary.has(row.leader)), blocks.map((row) => `${row.dimension}:${row.leader}`).join(' · '));
  const deltaWrong = measured
    .map((row) => ({ key: row.cells[0], a: row.cells[1], b: row.cells[2], d: row.cells[3] }))
    .filter((row) => /^-?[\d.]+$/.test(row.a.replace(/,/g, '')) && /^-?[\d.]+$/.test(row.b.replace(/,/g, '')) && /^[-+][\d.]+$|^-?[\d.]+$/.test(row.d))
    .filter((row) => Math.abs(Number(row.d.replace('+', '')) - (Number(row.a.replace(/,/g, '')) - Number(row.b.replace(/,/g, '')))) > 0.011);
  check('every measure delta is printed as A minus B', deltaWrong.length === 0, deltaWrong.slice(0, 4).map((row) => `${row.key}: ${row.a}/${row.b}/${row.d}`).join(' · ') || `${measured.length} measures checked`);
  // §27's own words for a direction: which side of `left minus right` counts as ahead, and `none` for the two
  // measures that are printed as context rather than as a win.
  const directionWords = new Set(['higher_is_greater', 'lower_is_greater', 'none']);
  const directions = new Set(measured.map((row) => (row.cells[4] ?? '').toLowerCase()));
  check('every measure names the direction it was judged in', [...directions].every((word) => directionWords.has(word)) && directions.size >= 2, [...directions].join(', '));
  check('the panel prints the stored totals beside the lines behind the rates', /AGREE/i.test(compareText), (compareText.match(/[^\n]*AGREE[^\n]*/) ?? [''])[0].slice(0, 100));
  const agreeCells = await page.$$eval('[data-testid="scout-compare"] table', (tables) => {
    const cellText = (row) => [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim());
    const table = tables.find((node) => (node.querySelector('th')?.innerText ?? '').trim().toLowerCase() === 'side');
    if (!table) return [];
    return [...table.querySelectorAll('tbody tr')].map((row) => (cellText(row)[7] ?? '').toUpperCase());
  });
  check('both sides agree with themselves', agreeCells.length === 2 && agreeCells.every((cell) => cell.toUpperCase().includes('AGREE')), agreeCells.join(' · '));
  check('the comparison refuses to rank the pair as a whole', compareText.includes('no overall rating') && compareText.includes('no winner score'), (compareText.match(/this payload[^\n]*/) ?? [''])[0].slice(0, 150));
  check('nothing in the panel adds the score the payload withheld', !/composite|winner score[:\s]|overall verdict/i.test(compareText.replace(/no winner score/g, '')), 'no composite figure in the printed panel');
  check('the two sides are the two candidates that were chosen', compareText.includes(String(printed[0]?.cells[0]).split(' ')[0]) || compareText.includes(firstSlug ?? '—'), `${firstSlug} against ${secondSlug}`);
  await shot(page, 'scout-compare');

  // --- §23's shortlist: a list that stores membership and re-borrows every figure -------------------
  const listName = `QA list ${stamp.slice(-6)}`;
  check('the list panel is on the page under the search', has(await text(page), 'Your shortlists'), 'panel title');
  check(
    'the list panel publishes the API limits rather than its own',
    has(await text(page), `of ${listRules.max_shortlists_per_user} lists`),
    `cap ${listRules.max_shortlists_per_user} lists · ${listRules.max_items_per_shortlist} players each`,
  );
  check('the shortlist name field takes a name', (await setInput(page, 'input[aria-label="Shortlist name"]', listName)) === 'set');
  check('opening a list is a button the page offers', (await clickText(page, 'Open a list')) === 'clicked');
  check('the new list opens straight away', await untilText(page, `Shortlist · ${listName}`));
  const openedLine = await lineWith(page, 'room left');
  check('an empty list says zero rows stored and prints the room it has', /0 membership rows stored/i.test(openedLine) && /30 room left/i.test(openedLine), openedLine.slice(0, 150));
  check(
    'the sentence searched is the sentence stored on the list',
    await page.evaluate((want) => (document.querySelector('tr[data-list]')?.innerText ?? '').includes(want), QUERY),
    'the search box text appears in the list row',
  );

  await page.select('select[aria-label="Player to add"]', printed[0].slug);
  await setInput(page, 'input[aria-label="Note about this player"]', 'walk note: kept from the first search');
  check('adding a player is a button the page offers', (await clickText(page, 'Add to the list')) === 'clicked');
  check('the player appears on the list', await untilDom(page, (slug) => document.querySelectorAll(`tr[data-listed="${slug}"]`).length === 1, printed[0].slug));

  const rowCells = (selector) =>
    page.$$eval(selector, (rows) => rows.map((row) => [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim())));
  const digits = (value) => Number(String(value).replace(/[^\d]/g, '')) || 0;
  const onList = (await rowCells(`tr[data-listed="${printed[0].slug}"]`))[0] ?? [];
  const fromSearch = (await rowCells(`tr[data-candidate="${printed[0].slug}"]`))[0] ?? [];
  // The list table carries one column more than the search table (# and Off at the ends), so the pairs below
  // are read from the two header rows rather than assumed to line up by index.
  const LIST_TO_SEARCH = { 2: 1, 5: 4, 6: 5, 7: 6, 8: 7 };
  const compared = Object.entries(LIST_TO_SEARCH).map(([from, to]) => `${from}:${digits(onList[from])}/${digits(fromSearch[to])}`);
  check(
    'the list prints the search’s age, overall, potential, headroom and asking fee unchanged',
    onList.length > 10 && Object.entries(LIST_TO_SEARCH).every(([from, to]) => digits(onList[from]) === digits(fromSearch[to]) && digits(onList[from]) > 0),
    compared.join(' '),
  );
  check('the list prints the search’s foot as the same word, not as a number', (onList[4] ?? '').toLowerCase() === (fromSearch[3] ?? '').toLowerCase() && /[a-z]/.test(onList[4] ?? ''), `list "${onList[4]}" vs search "${fromSearch[3]}"`);
  check('the position on the list is the order it was added in', digits(onList[0]) === 1, onList[0]);
  check('the note the walk typed is the note printed back', (onList[10] ?? '').includes('kept from the first search'), onList[10]);
  const recheckText = await page.evaluate(() => document.querySelector('tr[data-listed]')?.innerText ?? '');
  check(
    'the stored sentence is re-applied to the member it found',
    recheckText.includes('22') && !recheckText.includes('LOST'),
    recheckText.replace(/\s+/g, ' ').slice(40, 190),
  );
  const figuresFrom = await lineWith(page, 'read again on this request');
  check('the panel says where its numbers came from', figuresFrom.includes('real_players') && figuresFrom.includes('search'), figuresFrom.slice(0, 150));
  check('the panel says what a list does not store', has(await text(page), 'not stored:'), (await lineWith(page, 'not stored')).slice(0, 130));

  check('the list settles before the walk asks it for the same player again', await waitEnabled(page, 'Add to the list'));
  await page.select('select[aria-label="Player to add"]', printed[0].slug);
  check('adding the same player twice is refused on the page', (await clickText(page, 'Add to the list')) === 'clicked');
  check('the refusal names the code and the player', await untilDom(page, () => /already_listed/.test(document.body?.innerText ?? '')));
  const refusalLine = await lineWith(page, 'already_listed');
  check('the refusal carries the figures behind it', /player|held|limit/.test(refusalLine), refusalLine.slice(0, 170));

  check('the refusal leaves the list usable', await waitEnabled(page, 'Add to the list'));
  await page.select('select[aria-label="Player to add"]', printed[1].slug);
  await clickText(page, 'Add to the list');
  check('a second player joins the list at position two', await untilDom(page, (slug) => document.querySelectorAll(`tr[data-listed="${slug}"]`).length === 1, printed[1].slug));
  const positions = await page.$$eval('tr[data-listed]', (rows) => rows.map((row) => Number((row.querySelectorAll('td')[0]?.innerText ?? '0').replace(/[^\d]/g, ''))));
  check('the two rows sit at positions 1 and 2', positions.length === 2 && positions[0] === 1 && positions[1] === 2, positions.join(','));
  check('the room left the list reports is the cap minus what it holds', /28 room left/i.test(await lineWith(page, 'room left')), (await lineWith(page, 'room left')).slice(0, 150));

  check(
    'the row the walk is about to take off is sitting on an enabled button',
    await untilDom(page, (slug) => {
      const button = document.querySelector(`tr[data-listed="${slug}"] button[data-act="remove"]`);
      return Boolean(button) && !button.disabled;
    }, printed[0].slug),
  );
  const removed = await page.evaluate((slug) => {
    const button = document.querySelector(`tr[data-listed="${slug}"] button[data-act="remove"]`);
    if (!button) return 'missing';
    if (button.disabled) return 'disabled';
    button.click();
    return 'clicked';
  }, printed[0].slug);
  check('a listed player can be taken off the list', removed === 'clicked', removed);
  await new Promise((resolve) => setTimeout(resolve, 2000));
  const stillThere = await page.$$eval('tr[data-listed]', (rows) => rows.map((row) => row.dataset.listed));
  check('the removed player is gone and the other keeps his slot', !stillThere.includes(printed[0].slug) && stillThere.includes(printed[1].slug), stillThere.join(','));

  const deleted = await page.evaluate((want) => {
    const row = [...document.querySelectorAll('tr[data-list]')].find((node) => node.innerText.includes(want));
    const button = row?.querySelector('button[data-act="delete"]');
    if (!button) return 'missing';
    button.click();
    return 'clicked';
  }, listName);
  check('the walk deletes the list it opened', deleted === 'clicked', deleted);
  await new Promise((resolve) => setTimeout(resolve, 2000));
  check('after the delete the account holds no list of that name', !(await page.evaluate((want) => (document.body?.innerText ?? '').includes(want), listName)), listName);
  await shot(page, 'scout-shortlist');

  // --- M7's transfer simulation: a projection the page cannot cheat at ---------------------------
  const clubs = await call(page, "GET", "/api/v1/careers/options");
  check("a club exists to open a career against", clubs.status === 200 && (clubs.json?.clubs?.length ?? 0) > 0, `${clubs.json?.clubs?.length ?? 0} clubs`);
  const opened = await call(page, "POST", "/api/v1/careers", {
    // The options route names its clubs by `team_id`; the career route accepts that id or the slug.
    club: clubs.json.clubs[0].team_id,
    manager_name: `Sim QA ${stamp.slice(-4)}`,
    philosophy: "balanced",
    budget: 6_000_000,
    objectives: [{ kind: "wins", target: 1, label: "win once" }],
  });
  check("the walk opens a career of its own to simulate against", opened.status === 200, `HTTP ${opened.status}`);
  const simCareer = String(opened.json?.career?.slug ?? "");
  check("the career the walk opened is addressable by its slug", simCareer.length > 0, simCareer);

  check("the simulation panel is on the page", has(await text(page), "What if this career signed him?"), "panel title");
  check("the simulation panel publishes the engine's own seed rule", has(await text(page), "the only thing that differs between the two scorelines is the eleven"), (await lineWith(page, "each future round is played twice")).slice(0, 160));
  check("the career field takes the slug", (await setInput(page, 'input[aria-label="Career to simulate for"]', simCareer)) === "set");
  await page.select('select[aria-label="Player to simulate signing"]', printed[0].slug);
  check("the fixtures field takes a number", (await setInput(page, 'input[aria-label="Fixtures to project"]', "2")) === "set");
  check("simulating is a button the page offers", (await clickText(page, "Simulate the signing")) === "clicked");
  check("the projection arrives with two rounds", await untilDom(page, () => document.querySelectorAll("[data-sim-round]").length === 2));

  const simGrid = await page.$$eval('[data-testid="scout-transfer"] .world-kv__row', (rows) =>
    Object.fromEntries(rows.map((row) => [(row.querySelector("dt")?.innerText ?? "").replace(/\s+/g, " ").trim().toLowerCase(), (row.querySelector("dd")?.innerText ?? "").replace(/\s+/g, " ").trim()])),
  );
  const simFee = amount(simGrid["asking fee"]);
  const simWeekly = amount(simGrid["weekly wage"]);
  const simSeason = amount(simGrid["season wage"]);
  check("the season wage printed is fifty-two printed weeks", simSeason === simWeekly * 52 && simWeekly > 0, `${simWeekly} × 52 = ${simSeason}`);
  const simLeftover = amount(simGrid["left in the budget"]);
  const headroomLine = simGrid["affordable by the fee"] ?? "";
  check("the headroom after the fee is the balance minus the fee", amount(headroomLine) === Math.abs(simLeftover - simFee) || headroomLine.includes(Math.abs(simLeftover - simFee).toLocaleString("en-GB")), `${simLeftover} − ${simFee} → ${headroomLine.slice(0, 80)}`);
  check("the rounds the leftovers pay for divide the leftovers by the wage", Number(simGrid["rounds the leftovers pay for"] ?? "-1") === Math.floor(Math.max(simLeftover - simFee, 0) / Math.max(simWeekly, 1)), simGrid["rounds the leftovers pay for"]);
  check("the fit figure is printed with the formula that made it", /÷|×|=|formula|0\.\d/.test(simGrid["tactical fit for that need"] ?? ""), simGrid["tactical fit for that need"]);
  check("the squad line says a row is added, not a player invented", /\d+ → \d+/.test(simGrid["squad"] ?? ""), simGrid["squad"]);

  const simRounds = await page.$$eval("[data-sim-round]", (rows) =>
    rows.map((row) => ({
      round: row.dataset.simRound,
      text: row.innerText.replace(/\s+/g, " ").trim(),
      oneSeed: (row.querySelector("td:last-child .badge")?.innerText ?? "").trim().toUpperCase(),
    })),
  );
  check("every projected round is played twice at one seed", simRounds.length === 2 && simRounds.every((row) => row.oneSeed === "ONE SEED"), simRounds.map((row) => `${row.round}:${row.oneSeed}`).join(" · "));
  check("each round names the opponent and the seed it used", simRounds.every((row) => /vs |at /.test(row.text) && /\b\d{6,}\b/.test(row.text)), simRounds[0]?.text.slice(0, 150));
  check("each line prints the digest the engine produced", simRounds.every((row) => /poss 0\.\d+ · [0-9a-f]{8}/.test(row.text)), simRounds[0]?.text.slice(-90));
  const totalsGrid = Object.entries(simGrid).filter(([label]) => /without him|with him|difference/.test(label));
  const pointsOf = (label) => Number((simGrid[label] ?? "").match(/(\d+) points/)?.[1] ?? NaN);
  check("the printed totals add up to the printed difference", pointsOf("with him") - pointsOf("without him") === Number((simGrid["difference"] ?? "").match(/points ([+-]?\d+)/)?.[1] ?? NaN), totalsGrid.map(([k, v]) => `${k}=${v}`).join(" · "));
  const elevenLine = await page.evaluate(() => document.querySelector('[data-sim="eleven"]')?.innerText ?? "");
  check("the panel states whether the eleven moved at all", /the eleven does not change|the eleven changes:/.test(elevenLine), elevenLine.slice(0, 150));
  if (/the eleven does not change/.test(elevenLine)) {
    check("a bench addition still grows the squad by one", /\b(\d+) rows become/.test(elevenLine.replace(/\s+/g, " ")), elevenLine.slice(0, 160));
  }
  const notDoing = await page.evaluate(() => document.body?.innerText ?? "");
  check("the panel prints what the simulation does not do", notDoing.includes("does not write a row") && notDoing.includes("is not called here"), "the five lines are on the page");
  check("the panel prints the limits it worked under", notDoing.includes("a fixture is one draw from a stochastic model"), "the one-sample notice");

  check("asking for too many fixtures is refused with its figures", (await setInput(page, 'input[aria-label="Fixtures to project"]', "99")) === "set");
  check("the button is clickable again", (await clickText(page, "Simulate the signing")) === "clicked");
  check("the refusal arrives", await untilDom(page, () => /bad_rounds/.test(document.querySelector('[data-sim="refusal"]')?.innerText ?? "")));
  const simRefusal = await page.evaluate(() => document.querySelector('[data-sim="refusal"]')?.innerText ?? "");
  check("the refusal carries the window it fell outside", /"max":\s*6/.test(simRefusal) && /99/.test(simRefusal), simRefusal.replace(/\s+/g, " ").slice(0, 160));
  check("the projection that worked is still on the page", (await page.$$eval("[data-sim-round]", (rows) => rows.length)) === 2, "a refusal does not erase the last good answer");

  const deletedCareer = await call(page, "DELETE", `/api/v1/careers/${simCareer}`);
  check("the walk deletes the career it opened", deletedCareer.status === 200 && deletedCareer.json?.deleted === true, `HTTP ${deletedCareer.status}`);
  await shot(page, "scout-transfer");

  // --- the same screen at 375px ---------------------------------------------------------------------------
  await page.setViewport(MOBILE);
  await untilText(page, 'Player A against Player B');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check('the scouting screen does not push the page sideways at 375px', overflow <= 2, `${overflow}px of horizontal overflow`);
  await shot(page, 'scout-mobile');
  await page.setViewport(DESKTOP);

  await page.close();
  await browser.close();

  const provoked = [
    // Chrome asks for the legacy `/favicon.ico` beside the icon this app declares, whatever the answer is.
    /\/favicon\.ico: Failed to load resource: the server responded with a status of 404/,
    // The shortlist walk posts the same player twice on purpose, so its 409 is expected twice over.
    /\/api\/v1\/scout\/shortlists\/[^/]+\/items: Failed to load resource: the server responded with a status of 409/,
    /\/api\/v1\/scout\/shortlists\/[^/]+\/items: HTTP 409/,
    // The projection's own refusal check asks for 99 fixtures on purpose.
    /\/api\/v1\/scout\/simulate-transfer: Failed to load resource: the server responded with a status of 422/,
    /\/api\/v1\/scout\/simulate-transfer: HTTP 422/,
    /\/api\/v1\/careers\/[^/]+: Failed to load resource: the server responded with a status of 40[39]/,
    /\/api\/v1\/careers: Failed to load resource/
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
  console.error(`scout walk aborted: ${error?.message ?? error}`);
  console.log(`\n${results.filter((row) => row.ok).length}/${results.length} checks passed before the abort.`);
  // The browser is still open when `main` throws, which would keep the event loop alive forever and leave the
  // caller waiting on a walk that already reported. The verdict is printed; the exit is what the caller waits on.
  process.exit(2);
});
