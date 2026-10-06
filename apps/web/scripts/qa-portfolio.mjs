/**
 * §38's portfolio walk: one account, a production build, and the claim that a CV stores nothing.
 *
 *   api tier:  http://127.0.0.1:8743   (DATABASE_URL=<scratch file> uvicorn app.main:app --port 8743)
 *   web tier:  http://127.0.0.1:3218   (API_INTERNAL_URL=http://127.0.0.1:8743 next start -p 3218)
 *   QA_BASE=http://127.0.0.1:3218 node scripts/qa-portfolio.mjs
 *
 * What this walk is willing to fail on:
 *
 * * **the painted cell is compared with the door that sent it**, section by section and figure by figure. A page
 *   that re-labelled a figure, dropped one, or invented a value the door never answered is a defect no API test
 *   can see, because the API is right in all of them;
 * * a section the build cannot fill earns **its reason**, not a zero and not an omission. `Matches` and `Stats`
 *   are knocked on specifically: after the account gains a player row they must still be unavailable, still
 *   carry the door's own sentence and the tables they would need, and must hold no figure cell at all;
 * * nothing is cached. The account is read, given a player through §7 door, and read again: the filled count the
 *   page repaints must equal the count the second read answers with, and must have moved;
 * * a figure is compared **cell for cell** with the door value the section answered with, so a `null` the tier
 *   sends — its way of saying the formula had no rows to fold — can only be painted as `null`; a page that turned
 *   it into `0` disagrees with the door and turns this walk red;
 * * no number in this walk is invented here. The ten titles, the fillable flags, the reasons, the ceilings-free
 *   vocabulary and the door list all come out of `GET /api/v1/portfolio/rules`, the same door the page reads;
 * * every answer is recorded, so "this tier answers 401 before it reads a row and never 403" is a census over the
 *   walk's own knocks rather than a sentence.
 *
 * Env overrides: QA_BASE, CHROME_PATH.
 */

import { mkdir, readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import puppeteer from 'puppeteer-core';

const BASE = (process.env.QA_BASE ?? 'http://127.0.0.1:3218').trim();
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };
const PASSWORD = 'portfolio-qa-password';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const OWNER = `qa-cv-${stamp}@footballos.test`;

/** §38 names its ten sections in an order; the walk holds the payload against the spec, not against the page. */
const SPEC_SECTIONS = ['position', 'archetype', 'skills', 'matches', 'stats', 'training', 'videos', 'achievements', 'ai_reports', 'development'];
const SPEC_TITLES = ['Position', 'Archetype', 'Skills', 'Matches', 'Stats', 'Training', 'Videos', 'Achievements', 'AI Reports', 'Development History'];

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
const shouts = (body, needle) => squeeze(body).toUpperCase().includes(squeeze(needle).toUpperCase());

/** The page renders a figure with `figureText` from `lib/portfolio.ts`; the walk mirrors it to compare cells. */
function figureText(value) {
  if (Array.isArray(value)) return value.map((entry) => String(entry)).join(', ');
  if (value !== null && typeof value === 'object') {
    return Object.entries(value).map(([key, inner]) => `${key} ${String(inner)}`).join(' · ');
  }
  return String(value);
}

async function shot(page, name) {
  const file = `${stamp}-portfolio-${name}.png`;
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
      where = '(unreadable location)';
    }
    consoleErrors.push({ label, where, text: message.text().slice(0, 200) });
  });
  page.on('pageerror', (error) => consoleErrors.push({ label, where: 'page', text: String(error?.message ?? error).slice(0, 200) }));
}

async function open(page, path, want = '') {
  await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle2', timeout: 90_000 });
  if (want) {
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      if (has(await page.content(), want)) return true;
      await new Promise((done) => setTimeout(done, 400));
    }
    return false;
  }
  return true;
}

const pageText = (page) => page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').trim());

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

async function register(page, email, displayName) {
  let last = null;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    last = await call(page, 'POST', '/api/v1/auth/register', {accepts_data_policy: true, display_name: displayName, email, password: PASSWORD, role: 'player'});
    if (last.status !== 429) return last;
    await new Promise((done) => setTimeout(done, 25_000));
  }
  return last;
}

/** The ten section blocks the page painted, in document order, with the cells read the way a person reads them. */
function sectionsOf(page) {
  return page.$$eval('div[data-section]', (nodes) =>
    nodes.map((node) => ({
      key: node.getAttribute('data-section'),
      available: node.getAttribute('data-available'),
      text: node.innerText.replace(/\s+/g, ' ').trim(),
      figures: [...node.querySelectorAll('tr[data-figure]')].map((row) => [...row.querySelectorAll('td')].map((cell) => cell.innerText.replace(/\s+/g, ' ').trim())),
      items: [...node.querySelectorAll('tr[data-item]')].length,
    })),
  );
}

/** Every key a JSON answer holds, at any depth — the census a no-money claim has to be measured over. */
function keysOf(value, out = []) {
  if (Array.isArray(value)) {
    for (const entry of value) keysOf(entry, out);
    return out;
  }
  if (value !== null && typeof value === 'object') {
    for (const [key, inner] of Object.entries(value)) {
      out.push(key);
      keysOf(inner, out);
    }
  }
  return out;
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  // ------------------------------------------------------------------ the rulebook door, with no cookie at all
  const rulesResponse = await fetch(`${BASE}/api/v1/portfolio/rules`, {headers: {accept: 'application/json'}});
  const rules = rulesResponse.ok ? await rulesResponse.json() : null;
  check('the rules door answers a caller with no session', rulesResponse.status === 200, `HTTP ${rulesResponse.status}`);
  check('and declares the seven doors it owns, including the share and PDF outputs', (rules?.routes ?? []).length === 7 && (rules?.routes ?? []).every((row) => row.method && row.path) && (rules?.routes ?? []).some((row) => row.path === '/portfolio/share') && (rules?.routes ?? []).some((row) => row.method === 'GET' && row.path === '/portfolio/cv.pdf'), `${(rules?.routes ?? []).length} route(s) published`);

  const vocabulary = rules?.sections ?? [];
  check("§38's ten sections arrive in the spec order", vocabulary.map((row) => row.section).join(' → ') === SPEC_SECTIONS.join(' → '), vocabulary.map((row) => row.section).join(' → '));
  check('and each one carries the spec word for itself', vocabulary.map((row) => row.title).join(' | ') === SPEC_TITLES.join(' | '), vocabulary.map((row) => row.title).join(' | '));
  const notFillable = vocabulary.filter((row) => row.fillable === false).map((row) => row.section);
  check('exactly two of the ten are marked as this build cannot fill them', notFillable.length === 2 && notFillable.includes('matches') && notFillable.includes('stats'), notFillable.join(', ') || '(none)');
  check('and each unfilled one names the tables it would read from', Object.keys(rules?.unfilled ?? {}).length === 2 && Object.keys(rules?.would_read_from ?? {}).length >= 2, `${Object.keys(rules?.unfilled ?? {}).length} reasons, ${Object.keys(rules?.would_read_from ?? {}).length} sources`);
  const outputs = rules?.public_outputs ?? {};
  const declared = (rules?.routes ?? []).map((row) => String(row.path));
  const namesADoor = (key) => declared.some((path) => String(outputs[key] ?? '').includes(path));
  check('all three outputs §38 permits now name a door this tier declares', Object.keys(outputs).length === 3 && ['public_player_profile', 'share_link', 'pdf'].every(namesADoor), Object.keys(outputs).map((key) => `${key}=${namesADoor(key) ? 'built' : 'absent'}`).join(', '));
  const shareCodes = ['no_such_share', 'section_unknown', 'minor_section_blocked', 'share_already_revoked'];
  check('and every refusal code this tier answers with arrives with its status, none of them a 400 or a 403', shareCodes.every((code) => [404, 422, 409].includes(rules?.refusal_answers?.[code])) && !Object.values(rules?.refusal_answers ?? {}).includes(400) && !Object.values(rules?.refusal_answers ?? {}).includes(403), JSON.stringify(rules?.refusal_answers ?? {}));

  const anonymous = await fetch(`${BASE}/api/v1/portfolio/cv`, {headers: {accept: 'application/json'}});
  const anonymousBody = await anonymous.json().catch(() => null);
  knocks.push({method: 'GET', path: '/api/v1/portfolio/cv', status: anonymous.status});
  check('the CV door answers 401 before it reads a row', anonymous.status === 401 && String(anonymousBody?.detail?.code ?? anonymousBody?.code ?? '') === 'unauthenticated', `HTTP ${anonymous.status} · ${JSON.stringify(anonymousBody).slice(0, 90)}`);
  const unrouted = await fetch(`${BASE}/api/v1/portfolio/nope`, {headers: {accept: 'application/json'}});
  knocks.push({method: 'GET', path: '/api/v1/portfolio/nope', status: unrouted.status});
  check('a path this tier does not own is not answered as a code it does publish', unrouted.status === 404, `HTTP ${unrouted.status}`);

  const buildId = (await readFile(resolve(dirname(fileURLToPath(import.meta.url)), '../.next/BUILD_ID'), 'utf8')).trim();
  const servedHtml = await (await fetch(`${BASE}/`)).text();
  check('the page this walk drives is the build it just compiled, by its own BUILD_ID', has(servedHtml, buildId), `BUILD_ID ${buildId}`);

  const browser = await puppeteer.launch({executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const context = await browser.createBrowserContext();
  const page = await context.newPage();
  await page.setViewport({width: 1440, height: 1000});
  watch(page, 'desktop');

  try {
    // ---------------------------------------------------------------- a signed-out visit is a redirect, not a page
    await open(page, '/portfolio');
    const signedOut = new URL(page.url()).pathname;
    check('a signed-out visitor is sent to the login door with a way back', signedOut.startsWith('/login') && has(page.url(), 'next=%2Fportfolio'), signedOut);

    const registered = await register(page, OWNER, 'QA CV Owner');
    check('a fresh account registers through the same proxy the page uses', registered.status === 201, `HTTP ${registered.status} · ${JSON.stringify(registered.json).slice(0, 90)}`);

    // ---------------------------------------------------------------- the empty CV, before any player row exists
    await open(page, '/portfolio');
    const firstDoor = await call(page, 'GET', '/api/v1/portfolio/cv');
    const firstPainted = await sectionsOf(page);
    const firstBody = firstDoor.json ?? {};
    check('the CV page paints all ten sections, in the order the rules door publishes', firstPainted.map((row) => row.key).join(' → ') === SPEC_SECTIONS.join(' → '), `${firstPainted.length} section(s) painted`);
    check('and every painted section is the door section under the same key', firstPainted.every((row) => (firstBody.sections ?? []).some((section) => section.section === row.key)), `${firstPainted.length} painted against ${(firstBody.sections ?? []).length} answered`);
    check("a brand-new account has no player row, and the page says so in the door's own words", firstBody.has_player === false && has(squeeze(await pageText(page)), squeeze(firstPainted.find((row) => row.key === 'position')?.text ?? 'no player row')), `has_player=${firstBody.has_player}, filled ${firstBody.counts?.filled} of ${firstBody.counts?.sections}`);
    const availableCount = firstPainted.filter((row) => row.available === 'true').length;
    check('the filled count the eyebrow prints is the count of blocks painted available', availableCount === firstBody.counts?.filled, `${availableCount} painted against ${firstBody.counts?.filled} answered`);

    // ---------------------------------------------------------------- the painted cells against the door that sent them
    const mismatches = [];
    for (const row of firstPainted) {
      const section = (firstBody.sections ?? []).find((item) => item.section === row.key);
      if (!section) continue;
      if (row.available === 'true') {
        for (const cell of row.figures) {
          const [name, painted] = cell;
          const answered = figureText(section.figures?.[name]);
          if (painted !== answered) mismatches.push(`${row.key}.${name} painted ${JSON.stringify(painted)} but the door answered ${JSON.stringify(answered)}`);
        }
        if (row.items !== (section.items ?? []).length) mismatches.push(`${row.key} painted ${row.items} item row(s) where the door sent ${(section.items ?? []).length}`);
      } else {
        if (row.figures.length !== 0) mismatches.push(`${row.key} is not available yet still paints ${row.figures.length} figure cell(s)`);
        if (!has(row.text, section.missing_because ?? '(the door sent no reason)')) mismatches.push(`${row.key} does not print the reason the door sent`);
      }
    }
    check('every figure cell on the page is the value the door answered with', mismatches.length === 0, mismatches.slice(0, 3).join(' | ') || `${firstPainted.filter((row) => row.available === 'true').length} section(s) compared, ${mismatches.length} cell(s) disagreed`);

    // ---------------------------------------------------------------- the two sections the build cannot fill
    const matchesBlock = firstPainted.find((row) => row.key === 'matches');
    const statsBlock = firstPainted.find((row) => row.key === 'stats');
    check('Matches and Stats are painted as unavailable rather than dropped or zeroed', matchesBlock?.available === 'false' && statsBlock?.available === 'false', `matches=${matchesBlock?.available} stats=${statsBlock?.available}`);
    const unfilledReasons = firstBody.unfilled_reasons ?? {};
    check('and each prints the reason the CV door carries, with the tables it would need', Object.keys(unfilledReasons).length === 2 && has(matchesBlock?.text ?? '', unfilledReasons.matches ?? '(none)') && has(statsBlock?.text ?? '', unfilledReasons.stats ?? '(none)'), Object.keys(unfilledReasons).join(', '));
    check('the two unfilled blocks name no rows of their own', (matchesBlock?.items ?? 0) === 0 && (statsBlock?.items ?? 0) === 0 && (matchesBlock?.figures.length ?? 0) === 0 && (statsBlock?.figures.length ?? 0) === 0, `${matchesBlock?.figures.length}/${statsBlock?.figures.length} figure cell(s)`);

    // ---------------------------------------------------------------- the panels below the ten
    const painted = await pageText(page);
    check('the formulas panel prints every expression the CV door publishes', Object.keys(firstBody.formulas ?? {}).every((name) => has(painted, name)), `${Object.keys(firstBody.formulas ?? {}).length} expression(s)`);
    check('the outputs panel prints the three §38 permits with their state', Object.keys(outputs).every((name) => has(painted, name)), Object.keys(outputs).join(', '));
    check('the doors panel lists every door the rules door declares, and none of them is an empty list', (rules?.routes ?? []).length === 7 && (rules?.routes ?? []).every((route) => has(painted, route.path)), `${(rules?.routes ?? []).length} door(s)`);
    check('and the tier limitation travels with the page', has(painted, String(firstBody.limitation ?? '(no limitation sent)').slice(0, 60)), String(firstBody.limitation ?? '').slice(0, 90));
    const moneyKeys = keysOf(firstBody).filter((key) => /price|currency|amount|checkout|payment|provider|stripe|invoice/i.test(key));
    check('no money-shaped key is anywhere in the CV payload', moneyKeys.length === 0, moneyKeys.join(', ') || `${keysOf(firstBody).length} key(s) walked`);
    check('and the page prints no price word either', !/\bprice\b/i.test(painted), `${painted.length} char(s) of body text scanned`);
    await shot(page, 'cv-empty');

    // ---------------------------------------------------------------- the write that moves a count, not a column
    const created = await call(page, 'POST', '/api/v1/players', {age: 24, goal: 'become_box_to_box', level: 'intermediate', name: `QA CV Player ${stamp}`, position: 'CM', preferred_foot: 'right'});
    check("§7's own door gives this account a player row", created.status === 201, `HTTP ${created.status} · ${JSON.stringify(created.json).slice(0, 90)}`);

    await open(page, '/portfolio');
    const secondDoor = await call(page, 'GET', '/api/v1/portfolio/cv');
    const secondPainted = await sectionsOf(page);
    const secondBody = secondDoor.json ?? {};
    check('the page re-reads the CV from the rows, so the filled count moved', (secondBody.counts?.filled ?? 0) > (firstBody.counts?.filled ?? 0), `${firstBody.counts?.filled} → ${secondBody.counts?.filled}`);
    const repaintedAvailable = secondPainted.filter((row) => row.available === 'true').length;
    check("and the count the eyebrow paints is the second read's own count, not the first", repaintedAvailable === secondBody.counts?.filled, `${repaintedAvailable} painted against ${secondBody.counts?.filled} answered`);
    const positionBlock = secondPainted.find((row) => row.key === 'position');
    check('the Position section is filled now, and prints the row the door read', positionBlock?.available === 'true' && has(positionBlock?.text ?? '', 'CM'), String(positionBlock?.text ?? '').slice(0, 120));
    const stillUnfilled = secondPainted.filter((row) => row.available === 'false').map((row) => row.key);
    check('while Matches and Stats stay unfilled for a player that exists', stillUnfilled.includes('matches') && stillUnfilled.includes('stats'), stillUnfilled.join(', '));

    const secondMismatches = [];
    for (const row of secondPainted) {
      const section = (secondBody.sections ?? []).find((item) => item.section === row.key);
      if (!section || row.available !== 'true') continue;
      for (const cell of row.figures) {
        const [name, value] = cell;
        if (value !== figureText(section.figures?.[name])) secondMismatches.push(`${row.key}.${name} painted ${JSON.stringify(value)} against ${JSON.stringify(figureText(section.figures?.[name]))}`);
      }
    }
    check('and every figure of the second read is still the door value, cell for cell', secondMismatches.length === 0, secondMismatches.slice(0, 3).join(' | ') || `${secondPainted.filter((row) => row.available === 'true').length} section(s) re-compared`);

    const pdfControl = await page.$eval('[data-portfolio-cv-pdf]', (node) => ({href: node.getAttribute('href'), downloads: node.hasAttribute('download')}));
    check('the page offers the owner-authenticated PDF as a download', pdfControl.href === '/api/v1/portfolio/cv.pdf' && pdfControl.downloads, JSON.stringify(pdfControl));
    const pdf = await page.evaluate(async (titles) => {
      const response = await fetch('/api/v1/portfolio/cv.pdf', {credentials: 'same-origin'});
      const bytes = new Uint8Array(await response.arrayBuffer());
      const text = new TextDecoder('latin1').decode(bytes);
      return {
        status: response.status,
        type: response.headers.get('content-type') ?? '',
        disposition: response.headers.get('content-disposition') ?? '',
        cache: response.headers.get('cache-control') ?? '',
        size: bytes.length,
        magic: text.startsWith('%PDF-'),
        eof: text.trimEnd().endsWith('%%EOF'),
        titles: titles.filter((title) => text.includes(title)),
      };
    }, SPEC_TITLES);
    knocks.push({method: 'GET', path: '/api/v1/portfolio/cv.pdf', status: pdf.status});
    check('and the PDF door returns a non-cached document rendered from all ten live sections', pdf.status === 200 && pdf.magic && pdf.eof && pdf.size > 5_000 && pdf.type.startsWith('application/pdf') && pdf.disposition.includes('football-cv.pdf') && pdf.cache === 'private, no-store' && pdf.titles.length === SPEC_TITLES.length, `HTTP ${pdf.status} · ${pdf.size} bytes · ${pdf.titles.length}/${SPEC_TITLES.length} titles`);
    await shot(page, 'cv-with-player');

    // ---------------------------------------------------------------- the public link, opened and taken back
    const shareBoxes = await page.$$eval('input[data-portfolio-share-section]', (nodes) =>
      nodes.map((node) => ({key: node.getAttribute('data-portfolio-share-section'), checked: node.checked})),
    );
    check('the CV page offers one checkbox for every section the rules door permits a link to carry', shareBoxes.map((row) => row.key).join(' → ') === SPEC_SECTIONS.join(' → '), shareBoxes.map((row) => row.key).join(', '));
    check('and the safer default withholds the section a minor may not publish', !shareBoxes.find((row) => row.key === 'videos')?.checked, shareBoxes.filter((row) => row.checked).map((row) => row.key).join(', '));

    const wanted = ['position', 'training'];
    await page.$$eval(
      'input[data-portfolio-share-section]',
      (nodes, keep) => {
        for (const node of nodes) {
          const key = node.getAttribute('data-portfolio-share-section');
          if (node.checked !== keep.includes(key)) node.click();
        }
      },
      wanted,
    );
    await page.click('[data-portfolio-share-open]');
    await page.waitForFunction(() => document.querySelectorAll('[data-portfolio-share-row]').length > 0, { timeout: 30_000 });

    const ledger = await call(page, 'GET', '/api/v1/portfolio/shares');
    const live = (ledger.json?.shares ?? []).find((row) => row.live);
    check('opening a link writes one live ledger row', ledger.status === 200 && ledger.json?.counts?.live === 1 && typeof live?.token === 'string', `HTTP ${ledger.status} · ${JSON.stringify(ledger.json?.counts ?? {})}`);
    check('and the live row carries only the two sections that were selected, in §38 order', live?.sections?.join(' → ') === wanted.join(' → '), (live?.sections ?? []).join(', '));
    check('the page names the live link and offers the controls that act on it', await page.$('[data-portfolio-share-view]') !== null && await page.$('[data-portfolio-share-copy]') !== null && await page.$('[data-portfolio-share-revoke]') !== null, String(live?.token ?? '').slice(0, 8));

    const publicPath = `/portfolio/shared/${encodeURIComponent(live.token)}`;
    const publicApi = await fetch(`${BASE}/api/v1/portfolio/share/${encodeURIComponent(live.token)}`, {headers: {accept: 'application/json'}});
    const publicBody = await publicApi.json().catch(() => null);
    knocks.push({method: 'GET', path: `/api/v1/portfolio/share/${live.token}`, status: publicApi.status});
    const leakedKeys = ['user_id', 'email', 'display_name', 'account', 'id', 'visibility'].filter((key) => keysOf(publicBody ?? {}).includes(key));
    check('the public JSON answers without a session and carries no identifying key', publicApi.status === 200 && leakedKeys.length === 0, `HTTP ${publicApi.status} · leaked ${leakedKeys.join(', ') || 'none'}`);
    check('and its projection carries exactly the published sections', (publicBody?.sections ?? []).map((row) => row.section).join(' → ') === wanted.join(' → ') && publicBody?.counts?.sections === wanted.length, `${(publicBody?.sections ?? []).length} section(s)`);
    check('while every other section is named only as withheld', (publicBody?.withheld ?? []).length === SPEC_SECTIONS.length - wanted.length, `${(publicBody?.withheld ?? []).length} withheld`);

    const publicContext = await browser.createBrowserContext();
    const publicPage = await publicContext.newPage();
    await publicPage.setViewport({width: 1440, height: 1000});
    watch(publicPage, 'public-cv');
    const publicResponse = await publicPage.goto(`${BASE}${publicPath}`, {waitUntil: 'networkidle2', timeout: 90_000});
    const publicPainted = await sectionsOf(publicPage);
    const publicText = await pageText(publicPage);
    check('a browser with no session opens the shared page', publicResponse?.status() === 200 && publicPainted.map((row) => row.key).join(' → ') === wanted.join(' → '), `HTTP ${publicResponse?.status()} · ${publicPainted.length} painted`);
    check('the public page does not name the account behind the link', !has(publicText, 'QA CV Owner'), publicText.slice(0, 120));
    check('and its painted sections are exactly the sections the public JSON answered', publicPainted.every((row) => (publicBody?.sections ?? []).some((section) => section.section === row.key)), `${publicPainted.length} painted against ${(publicBody?.sections ?? []).length} answered`);
    await shot(publicPage, 'shared-cv');

    await open(page, '/portfolio');
    await page.click('[data-portfolio-share-revoke]');
    await page.waitForFunction(() => !document.querySelector('[data-portfolio-share-view]'), { timeout: 30_000 });
    const revoked = await call(page, 'GET', '/api/v1/portfolio/shares');
    check('closing the link leaves one revoked row and no live row', revoked.json?.counts?.live === 0 && revoked.json?.counts?.revoked === 1, JSON.stringify(revoked.json?.counts ?? {}));
    const closedApi = await fetch(`${BASE}/api/v1/portfolio/share/${encodeURIComponent(live.token)}`, {headers: {accept: 'application/json'}});
    knocks.push({method: 'GET', path: `/api/v1/portfolio/share/${live.token}`, status: closedApi.status});
    check('the revoked token answers the same 404 a stranger gets', closedApi.status === 404, `HTTP ${closedApi.status}`);
    const revokedPage = await publicContext.newPage();
    const closedPage = await revokedPage.goto(`${BASE}${publicPath}`, {waitUntil: 'networkidle2', timeout: 90_000});
    const closedSections = await revokedPage.$$eval('div[data-section]', (nodes) => nodes.length);
    check('and the public page stops rendering once the token is closed', closedPage?.status() === 404 && closedSections === 0, `HTTP ${closedPage?.status()} · ${closedSections} section(s)`);
    await publicContext.close();

    // ---------------------------------------------------------------- mobile, and the census over the knocks
    await page.setViewport(MOBILE);
    await open(page, '/portfolio');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check('the CV fits a phone without a sideways scroll', overflow <= 4, `scrollWidth - innerWidth = ${overflow}px`);
    await shot(page, 'cv-mobile');

    const statuses = [...new Set(knocks.map((knock) => knock.status))].sort((a, b) => a - b);
    check('no knock this walk made earned 403, 400 or a server error', statuses.every((status) => [200, 201, 401, 404].includes(status)), `statuses ${statuses.join(', ')} over ${knocks.length} knock(s)`);
    check('and the tier answered 401 for a caller with no session, from the browser too', knocks.some((knock) => knock.status === 401), `${knocks.filter((knock) => knock.status === 401).length} unauthenticated answer(s)`);
  } finally {
    await browser.close();
  }

  check('the walk left no console error behind it', consoleErrors.length === 0, consoleErrors.slice(0, 3).map((entry) => `${entry.label} ${entry.where} ${entry.text}`).join(' | '));

  const failed = results.filter((entry) => !entry.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed · ${shots.length} screenshot(s) · ${knocks.length} door knock(s) recorded`);
  if (failed.length > 0) {
    console.log(failed.map((entry) => `FAIL  ${entry.name} — ${entry.detail}`).join('\n'));
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(`walk crashed: ${error?.stack ?? error}`);
  process.exitCode = 1;
});
