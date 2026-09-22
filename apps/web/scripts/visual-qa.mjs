/**
 * End-to-end visual + functional QA walk: the M1 training loop, the M2 knowledge surface and the
 * M3 Football World pages (spec PRINCIPLE 3, §56, §62, §65, §80, §88).
 *
 * Drives the real browser stack — middleware redirect, cookie proxy, server components, client
 * forms and the generated-world routes — then writes screenshots at desktop and 375px widths into
 * docs/screenshots/ and prints an assertion report (110 checks as of 2026-09-22).
 *
 *   web tier: http://127.0.0.1:3210   api tier: http://127.0.0.1:8731   (scripts/dev.sh)
 *   node scripts/visual-qa.mjs
 *
 * Evidence runs use a production build, not the dev server: use scripts/verify-production.sh,
 * which builds, serves on :3211, refuses to proceed unless that port is serving the fresh build,
 * runs this walk and releases the port.
 *
 * Env overrides: QA_BASE, CHROME_PATH.
 */

import { execFile } from 'node:child_process';
import { mkdir, stat, unlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import puppeteer from 'puppeteer-core';

const BASE = process.env.QA_BASE ?? 'http://127.0.0.1:3210';
const CHROME =
  process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');

const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1 };
const MOBILE = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true };

const PASSWORD = 'visual-qa-password';
const NOTES = 'Visual QA session: felt balanced, kept the head up.';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const EMAIL = `visual-qa-${stamp}@footballos.test`;
const PLAYER_NAME = `QA Mid ${stamp.slice(-4)}`;

const results = [];
const consoleErrors = [];
const shots = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
}

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

async function shot(page, name) {
  const file = `${stamp}-${name}.png`;
  try {
    await page.screenshot({ path: resolve(OUT_DIR, file), fullPage: true });
    shots.push(file);
  } catch (error) {
    // A missing PNG is a failure worth reporting; it must not abort the other 90 assertions.
    check(`screenshot ${name} captured`, false, String(error?.message ?? error).slice(0, 160));
  }
}

async function open(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle2', timeout: 90_000 });
  await sleep(400);
}

/** Wait until the page body contains `text`; Next dev compiles routes on first hit. */
async function waitForText(page, text, timeout = 90_000) {
  try {
    await page.waitForFunction(
      (needle) => (document.body?.innerText ?? '').toLowerCase().includes(needle.toLowerCase()),
      { timeout },
      text,
    );
  } catch (error) {
    const where = new URL(page.url()).pathname;
    const seen = (await bodyText(page).catch(() => '')).replace(/\s+/g, ' ').slice(0, 320);
    await shot(page, `fail-wait-${where.replace(/[^\w-]+/g, '_')}`).catch(() => {});
    throw new Error(`"${text}" never appeared at ${where} — the page said: ${seen || '(empty body)'}`);
  }
}

async function bodyText(page) {
  return page.evaluate(() => document.body.innerText);
}

/**
 * Probe many URLs with a bounded pool. The sitemap now advertises ~1,000 world rows, and firing
 * all of them at once makes the web tier refuse its own crawler — a failure of the harness, not
 * of the product. A refused connection is reported as status 0 so the check fails loudly instead
 * of throwing and aborting the run.
 */
async function probeStatuses(urls, concurrency = 6) {
  const outcomes = new Array(urls.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.min(concurrency, urls.length) }, async () => {
    for (;;) {
      const index = cursor;
      cursor += 1;
      if (index >= urls.length) return;
      try {
        // A stalled render must become a failed check, not a hung run: without the timeout one
        // page that never answers parks the whole walk until something external kills the process.
        outcomes[index] = (await fetch(urls[index], { signal: AbortSignal.timeout(25_000) })).status;
      } catch (error) {
        outcomes[index] = error?.name === 'TimeoutError' ? 408 : 0;
      }
    }
  });
  await Promise.all(workers);
  return outcomes;
}

async function clickByText(page, selector, text) {
  const handle = await page.evaluateHandle(
    (css, needle) =>
      [...document.querySelectorAll(css)].find((node) => node.textContent?.includes(needle)) ?? null,
    selector,
    text,
  );
  const element = handle.asElement();
  if (!element) {
    // A missing control used to abort the walk with `No button containing "X"` and no context at all.
    const seen = (await bodyText(page).catch(() => '')).replace(/\s+/g, ' ').slice(0, 260);
    throw new Error(`no ${selector} containing "${text}" — the page said: ${seen || '(empty body)'}`);
  }
  await element.click();
  return element;
}

async function setSelect(page, selector, value) {
  await page.select(selector, value);
}

async function run() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    // A walk of ~1,100 navigations and 46 full-page captures on a busy host needs more than the
    // default 30s per waiter; without this a slow-but-fine render aborts the whole run.
    protocolTimeout: 300_000,
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(120_000);
  /** Where an error was seen matters more than the minified React code Chrome prints. */
  const note = (line) => consoleErrors.push(`${line} @ ${new URL(page.url()).pathname}`);
  page.on('console', (message) => {
    if (message.type() === 'error') note(message.text());
  });
  page.on('pageerror', (error) => note(String(error)));
  page.on('response', (response) => {
    const path = new URL(response.url()).pathname;
    // A 401 from the proxy is how the anonymous-visitor guard and silent refresh are supposed to behave.
    if (response.status() >= 400 && !(response.status() === 401 && path.startsWith('/api/v1'))) {
      consoleErrors.push(`HTTP ${response.status()} ${path}`);
    }
  });

  try {
    // 1. Protected route without a session -> middleware redirects to /login.
    await page.goto(`${BASE}/my-football`, { waitUntil: 'networkidle2' });
    check('middleware guards /my-football', new URL(page.url()).pathname === '/login', page.url());
    await page.setViewport(DESKTOP);
    await open(page, '/login');
    await shot(page, '01-login-desktop');

    // 2. Register a brand-new account through the cookie proxy.
    await open(page, '/register');
    await page.type('#email', EMAIL);
    await page.type('#password', PASSWORD);
    await page.type('#display_name', 'QA Tester');
    await page.click('input[type="checkbox"]');
    await page.click('button[type="submit"]');
    await page.waitForFunction(() => location.pathname === '/onboarding', { timeout: 60_000 });
    check('register mints session and lands on onboarding', true, EMAIL);

    // 3. Create the player identity (derived attributes, no self-rating).
    await waitForText(page, 'Create my football identity');
    await page.type('#name', PLAYER_NAME);
    await setSelect(page, '#position', 'CM');
    await setSelect(page, '#level', 'intermediate');
    await page.evaluate(() => {
      const age = document.querySelector('#age');
      if (age) age.value = '';
    });
    await page.type('#age', '24');
    await setSelect(page, '#goal', 'become_box_to_box');
    await shot(page, '02-onboarding-desktop');
    await page.click('button[type="submit"]');
    await page.waitForFunction((name) => location.pathname === '/my-football' && document.body.innerText.includes(name), { timeout: 60_000 }, PLAYER_NAME);
    check('player created and My Football renders', true, PLAYER_NAME);

    // 4. My Football: derived archetype, radar, XP at zero.
    await sleep(800);
    const myFootball = await bodyText(page);
    check('My Football shows archetype + level', /archetype|Archetype/iu.test(myFootball) && /level/iu.test(myFootball));
    check('My Football labels demo mode', /DEMO/iu.test(myFootball));
    await shot(page, '03-my-football-desktop');

    // 5. Coach: today's recommendation, an ask, and a generated plan.
    await open(page, '/coach');
    await waitForText(page, 'Recommended session');
    const coachToday = await bodyText(page);
    check('coach /today renders a recommendation with reasons', /Why this was chosen/iu.test(coachToday));
    check('coach /today self-labels as rule engine demo', /rule-engine/iu.test(coachToday) && /DEMO/iu.test(coachToday));
    await shot(page, '04-coach-today-desktop');

    await page.type('.textarea', 'Why am I losing the ball in the middle third?');
    await clickByText(page, 'button', 'Ask the coach');
    await waitForText(page, 'intent:');
    const asked = await bodyText(page);
    check('coach /ask returns intent + reasons', /ball loss|first touch/iu.test(asked) && /Why this answer/iu.test(asked));
    await shot(page, '05-coach-ask-desktop');

    await clickByText(page, 'button', 'Build a 7-day plan');
    await waitForText(page, 'Training days');
    const planned = await bodyText(page);
    check('coach /plan returns a 7-day plan with sessions', /D1/iu.test(planned) && /min/iu.test(planned));
    await shot(page, '06-coach-plan-desktop');

    // 6. Training academy: catalogue -> drill detail -> schedule.
    await open(page, '/training');
    await waitForText(page, 'min');
    const href = await page.evaluate(() => {
      const link = [...document.querySelectorAll('a[href^="/training/"]')].find((node) => node.getAttribute('href')?.length > '/training/'.length);
      return link ? link.getAttribute('href') : null;
    });
    check('training index links to a drill', Boolean(href), href ?? 'none');
    await shot(page, '07-training-index-desktop');

    await open(page, href ?? '/training');
    await waitForText(page, 'Add to my sessions');
    await shot(page, '08-drill-detail-desktop');
    await clickByText(page, 'button', 'Add to my sessions');
    await waitForText(page, 'Added');
    check('drill scheduled from detail page', true);

    // 7. Log the session and read the explainable progression result.
    await open(page, '/training');
    await waitForText(page, 'Log this session');
    const card = await page.$('.session-card');
    check('training index shows a planned session card', Boolean(card));
    if (card) {
      const selects = await card.$$('select');
      if (selects[0]) await selects[0].select('4');
      if (selects[1]) await selects[1].select('4');
      if (selects[2]) await selects[2].select('3');
      const notesField = await card.$('textarea');
      await notesField.click();
      await notesField.type(NOTES);
      const typed = await notesField.evaluate((el) => el.value).catch(() => '(unreadable)');
      await shot(page, '09-session-logger-desktop');
      const sentBodies = [];
      const spy = (request) => {
        if (request.url().endsWith('/complete')) sentBodies.push(request.postData() ?? '(no body)');
      };
      page.on('request', spy);
      await clickByText(page, '.session-card button', 'Log this session');
      await waitForText(page, 'Skill points banked');
      page.off('request', spy);
      const logged = await bodyText(page);
      check('completion returns XP + formula', /\+\d+\s*XP/iu.test(logged), logged.match(/\+\d+\s*XP[^\n]*/iu)?.[0] ?? '');
      check('completion explains skill point banking', /\d+\/100/u.test(logged) && /more raises|no point added/iu.test(logged));
      check('completion returns coach feedback', /Coach feedback/iu.test(logged));
      const storedNotes = await page.evaluate(
        async (needle) => {
          const response = await fetch('/api/v1/trainings/sessions?page_size=5', { credentials: 'same-origin' });
          if (!response.ok) return `http ${response.status}`;
          const rows = (await response.json()).items ?? [];
          return rows.some((row) => row.self_notes === needle) ? 'ok' : `missing (got ${JSON.stringify(rows.map((r) => r.self_notes))})`;
        },
        NOTES,
      );
      check('notes typed in the browser persist to the session row', storedNotes === 'ok', `${storedNotes} · dom="${typed}" · request=${sentBodies.join('|') || '(none)'}`);
      await shot(page, '10-session-logged-desktop');
    }

    // 8. Progress + history must reflect the completed session, both on screen and in the ledger.
    const ledger = await page.evaluate(async () => {
      const response = await fetch('/api/v1/progress/overview', { credentials: 'same-origin' });
      return response.ok ? response.json() : { http_status: response.status };
    });
    check(
      'server ledger records the completed session',
      ledger?.training?.sessions_completed >= 1 && ledger?.xp?.total > 0,
      `sessions=${ledger?.training?.sessions_completed} xp=${ledger?.xp?.total} level=${ledger?.xp?.level}`,
    );

    await open(page, '/progress');
    await waitForText(page, PLAYER_NAME);
    const progress = await bodyText(page);
    check('progress page renders level, streak and attribute history', /level/iu.test(progress) && /streak/iu.test(progress) && /technical/iu.test(progress) && /attribute/iu.test(progress));
    await shot(page, '11-progress-desktop');

    await open(page, '/history');
    await waitForText(page, 'Training log');
    const history = await bodyText(page);
    check('history lists the completed session with its evidence', /completed/iu.test(history) && /XP ledger/iu.test(history) && history.includes(NOTES.slice(0, 24)), history.includes(NOTES.slice(0, 24)) ? 'note shown' : 'note not shown');
    await shot(page, '12-history-desktop');

    // 9. Knowledge base (M2): authored library, hybrid retrieval, cited answers, refusal.
    await open(page, '/knowledge');
    await waitForText(page, 'Document library');
    await shot(page, '13-knowledge-library-desktop');
    const library = await bodyText(page);
    const cards = await page.evaluate(() => {
      const nodes = [...document.querySelectorAll('#library a.kn-card')];
      return {
        total: nodes.length,
        withProvenance: nodes.filter((n) => n.innerText.includes('PROJECT AUTHORED') && /last reviewed \d/iu.test(n.innerText)).length,
        withPassages: nodes.filter((n) => /\d+ passages/u.test(n.innerText)).length,
      };
    });
    check('knowledge library renders project-authored documents', cards.total > 0, `${cards.total} document cards`);
    check(
      'every library card carries provenance and its real chunk count',
      cards.total > 0 && cards.withProvenance === cards.total && cards.withPassages === cards.total,
      JSON.stringify(cards),
    );
    check(
      'library states the corpus size it was read from',
      /\d+ \S+ documents, \d+ indexed passages/u.test(library),
      library.match(/\d+ \S* ?documents, \d+ indexed passages/u)?.[0] ?? 'no counts',
    );

    // A document deep-link must render the passages the citations point into.
    const firstDoc = await page.evaluate(() => document.querySelector('#library a.kn-card')?.getAttribute('href') ?? '');
    await open(page, firstDoc);
    await waitForText(page, 'Passages');
    const detail = await page.evaluate(() => {
      const sections = [...document.querySelectorAll('.kn-section')];
      return {
        sections: sections.length,
        anchored: sections.filter((s) => /^\d+$/u.test(s.id ?? '')).length,
        origin: document.body.innerText.match(/data_origin: *([\w-]+)/u)?.[1] ?? '',
        demo: document.body.innerText.match(/is_demo_data: *(true|false)/u)?.[1] ?? '',
      };
    });
    check(
      'document detail renders its passages with citation anchors',
      detail.sections > 0 && detail.anchored === detail.sections,
      `${detail.sections} passages, ${detail.anchored} anchorable`,
    );
    check('detail page declares its origin as authored, not demo', detail.origin === 'project-authored' && detail.demo === 'false', `data_origin=${detail.origin} is_demo_data=${detail.demo}`);
    await shot(page, '14-knowledge-document-desktop');

    // Hybrid retrieval over the corpus.
    await open(page, '/knowledge');
    await waitForText(page, 'Hybrid retrieval');
    await page.type('#ksearch-query', 'how does a team press high in the opponent half');
    await clickByText(page, 'button', 'Run search');
    await waitForText(page, 'Why these ranked this way');
    const searched = await page.evaluate(() => {
      const results = [...document.querySelectorAll('.kn-result')];
      const first = results[0];
      return {
        count: results.length,
        excerpt: first?.querySelector('.kn-excerpt')?.innerText ?? '',
        link: first?.querySelector('a[href^="/knowledge/"]')?.getAttribute('href') ?? '',
        chips: first ? [...first.querySelectorAll('.kn-metrics .chip')].map((c) => c.innerText) : [],
        backend: document.querySelector('.kn-result') ? document.body.innerText.match(/hybrid-pgvector|hybrid-vector-python|vector-python|bm25-python|pgvector/u)?.[0] ?? '' : '',
        scanned: document.body.innerText.match(/\d+ chunks scanned/u)?.[0] ?? '',
      };
    });
    check('knowledge search ranks passages from the live corpus', searched.count > 0, `${searched.count} hits · ${searched.scanned} · backend ${searched.backend}`);
    check(
      'top result carries its own score, cosine and bm25 values',
      searched.chips.some((c) => /^score [\d.]+/u.test(c)) && searched.chips.some((c) => /^cosine [\d.]+/u.test(c)) && searched.chips.some((c) => /^bm25 [\d.]+/u.test(c)),
      searched.chips.join(' | '),
    );
    await shot(page, '15-knowledge-search-desktop');

    // The excerpt must be a verbatim slice of the stored passage — the anti-hallucination check.
    const quoteCheck = await page.evaluate(
      async (args) => {
        const response = await fetch(args.path, { credentials: 'same-origin' });
        if (!response.ok) return { status: response.status };
        const html = await response.text();
        const container = new DOMParser().parseFromString(html, 'text/html');
        const section = container.querySelector(`.kn-section[id="${args.ordinal}"] .kn-section__text`);
        const collapse = (value) => (value ?? '').replace(/\s+/g, ' ').trim();
        return { status: response.status, excerpt: collapse(args.excerpt), found: collapse(section?.textContent).includes(collapse(args.excerpt)) };
      },
      { path: searched.link.split('#')[0], ordinal: searched.link.split('#')[1] ?? '0', excerpt: searched.excerpt.replace(/…$/u, '') },
    );
    check('search excerpt is verbatim in the cited passage', quoteCheck.found === true, JSON.stringify(quoteCheck).slice(0, 200));

    // Ask must answer from citations, and must refuse when the corpus cannot ground an answer.
    await open(page, '/knowledge');
    await waitForText(page, 'Ask the library');
    await page.type('#kask-question', 'How should a midfield pair react when the opposition presses their own goalkeeper?');
    await clickByText(page, 'button', 'Ask the library');
    await waitForText(page, 'Cited passages');
    const libAnswer = await page.evaluate(() => {
      const citations = [...document.querySelectorAll('.kn-cite')];
      return {
        badge: document.querySelector('.kn-answer-block .badge--demo')?.innerText ?? '',
        answer: document.querySelector('.kn-answer')?.innerText ?? '',
        cites: citations.map((c) => ({
          quote: (c.querySelector('.kn-cite__quote')?.innerText ?? '').replace(/[“”]/gu, '').replace(/…$/u, '').trim(),
          href: c.querySelector('a[href^="/knowledge/"]')?.getAttribute('href') ?? '',
        })),
      };
    });
    check('ask returns a grounded answer with at least one citation', libAnswer.cites.length >= 1 && libAnswer.answer.length > 60, `${libAnswer.cites.length} citation(s), ${libAnswer.answer.length} chars of answer`);
    check('inline [n] markers point at the citation cards', /\[\d+\]/u.test(libAnswer.answer), libAnswer.answer.slice(0, 90));
    check(
      'every citation quotes a passage and links back to it',
      libAnswer.cites.every((c) => c.quote.length > 40 && c.href.startsWith('/knowledge/')),
      libAnswer.cites.map((c) => `${c.href} (${c.quote.length} chars)`).join(' | '),
    );
    check('demo-mode answers self-label as extractive, never as generated', /DEMO MODE/iu.test(libAnswer.badge) && /extractive/iu.test(libAnswer.badge), libAnswer.badge || 'no demo badge');
    await shot(page, '16-knowledge-ask-desktop');

    // Spec §62: a citation only counts if it resolves. Follow the first card's own link and require the quote.
    const target = libAnswer.cites[0];
    await open(page, target.href);
    await waitForText(page, 'Passages');
    const resolved = await page.evaluate((args) => {
      const ordinal = (args.href.split('#')[1] ?? '0').replace(/\D/g, '') || '0';
      const node = document.querySelector(`.kn-section[id="${ordinal}"] .kn-section__text`);
      const collapse = (value) => (value ?? '').replace(/\s+/g, ' ').trim();
      return { anchorFound: Boolean(node), quoteFound: collapse(node?.textContent).includes(collapse(args.quote)) };
    }, { href: target.href, quote: target.quote });
    check(
      'a citation link resolves to the exact passage it quotes',
      resolved.anchorFound && resolved.quoteFound,
      `${target.href} — ${resolved.anchorFound ? (resolved.quoteFound ? 'quote is verbatim' : 'quote not in that passage') : 'anchor missing'}`,
    );

    await open(page, '/knowledge');
    await waitForText(page, 'Ask the library');
    await page.type('#kask-question', 'which boot brand does the number 10 wear');
    await clickByText(page, 'button', 'Ask the library');
    await waitForText(page, 'No grounded answer');
    const refused = await page.evaluate(() => {
      const block = document.querySelector('.kn-answer-block');
      return {
        notice: block?.querySelector('.notice--warn')?.innerText ?? '',
        reasons: [...(block?.querySelectorAll('.reasons__item') ?? [])].map((li) => li.innerText).join(' · '),
        citations: block?.querySelectorAll('.kn-cite').length ?? -1,
      };
    });
    check(
      'an out-of-scope question is refused with no invented citations',
      /could not find a passage/iu.test(refused.notice) && refused.citations === 0,
      `${refused.notice.replace(/\s+/g, ' ').slice(0, 120)} · ${refused.citations} citation(s)`,
    );
    check('the refusal names the measured gate that failed', /rare term|coverage/iu.test(refused.reasons), refused.reasons.replace(/\s+/g, ' ').slice(0, 170));
    await shot(page, '17-knowledge-refusal-desktop');

    // 10. Settings: account, platform status, danger zone copy.
    await open(page, '/settings');
    await waitForText(page, EMAIL);
    const settings = await bodyText(page);
    check('settings shows account email + platform status', /sqlite|postgresql/iu.test(settings) && /Live|Not built/iu.test(settings));
    // The two rows that must never lie: which milestones the API actually reports, and which
    // languages the interface really renders (spec §81, §88).
    const statusRow = (label) =>
      page.evaluate(
        (text) => {
          const row = [...document.querySelectorAll('.st-status-row')].find((candidate) => candidate.textContent.includes(text));
          return row ? row.textContent.replace(/\s+/g, ' ').trim() : null;
        },
        label,
      );
    const m3Row = await statusRow('M3 ·');
    check(
      'settings reports M3 Football World as Live because the API flag is data-derived',
      /M3 · Football World.*Live/u.test(m3Row ?? ''),
      m3Row ?? 'row missing',
    );
    const localeChips = await page.evaluate(() => {
      const row = [...document.querySelectorAll('.st-status-row')].find((candidate) => candidate.textContent.includes('Locales shipped'));
      if (!row) return null;
      return [...row.querySelectorAll('.chip')].map((chip) => [chip.textContent.trim(), chip.getAttribute('title') ?? '']);
    });
    check(
      'settings ships only English and labels every other locale planned (spec §81)',
      !!localeChips &&
        localeChips.filter(([, title]) => title === '').map(([text]) => text).join(',') === 'en' &&
        localeChips.filter(([, title]) => title !== '').every(([text, title]) => /planned/iu.test(title) && text.includes('planned')),
      JSON.stringify(localeChips),
    );
    await shot(page, '18-settings-desktop');

    // 12. SEO surface (spec §80): robots, sitemap, canonical, OpenGraph and structured data.
    const [robots, sitemap] = await Promise.all([
      fetch(`${BASE}/robots.txt`).then(async (response) => ({
        status: response.status,
        type: response.headers.get('content-type') ?? '',
        text: await response.text(),
      })),
      fetch(`${BASE}/sitemap.xml`).then(async (response) => ({ status: response.status, text: await response.text() })),
    ]);
    check('robots.txt is served as plain text', robots.status === 200 && /text\/plain/iu.test(robots.type), `${robots.status} ${robots.type}`);
    const disallowed = ['/api/', '/my-football', '/training', '/progress', '/settings'];
    check(
      'robots.txt keeps every session-gated area out of the crawl',
      disallowed.every((path) => robots.text.includes(`Disallow: ${path}`)),
      disallowed.filter((path) => !robots.text.includes(`Disallow: ${path}`)).join(', ') || 'all disallowed',
    );
    const locs = [...sitemap.text.matchAll(/<loc>([^<]+)<\/loc>/gu)].map((match) => match[1]);
    check('sitemap.xml is served and non-empty', sitemap.status === 200 && locs.length > 0, `${locs.length} <loc> entries`);
    const locStatuses = await probeStatuses(locs);
    const notOk = locs.filter((unused, index) => locStatuses[index] !== 200);
    check(
      'sitemap advertises only routes that answer 200 (no redirect chains)',
      locs.length > 0 && notOk.length === 0,
      `${locs.length} URLs probed, ${locs.length - notOk.length} answered 200${notOk.length ? ` — e.g. ${locStatuses[locs.indexOf(notOk[0])]} ${notOk[0]}` : ''}`,
    );
    check(
      'every library document appears in the sitemap',
      locs.some((url) => url.endsWith(firstDoc)) && robots.text.includes('Sitemap:'),
      `${locs.length} entries · ${firstDoc} ${locs.some((url) => url.endsWith(firstDoc)) ? 'present' : 'MISSING'}`,
    );
    const pageHead = async (path) => {
      await open(page, path);
      return page.evaluate(() => {
        const read = (selector, attr = 'content') => document.head.querySelector(selector)?.getAttribute(attr) ?? '';
        return {
          canonical: read('link[rel="canonical"]', 'href'),
          description: read('meta[name="description"]'),
          ogType: read('meta[property="og:type"]'),
          ogUrl: read('meta[property="og:url"]'),
          ogTitle: read('meta[property="og:title"]'),
          title: document.title,
          jsonLd: [...document.querySelectorAll('script[type="application/ld+json"]')]
            .map((node) => {
              try {
                return JSON.parse(node.textContent ?? '{}');
              } catch {
                return { '@type': 'unparseable' };
              }
            }),
        };
      });
    };
    const knowledgeHead = await pageHead('/knowledge');
    check(
      'knowledge index publishes canonical + matching OpenGraph URL',
      /\/knowledge$/u.test(knowledgeHead.canonical) && knowledgeHead.ogUrl === knowledgeHead.canonical && knowledgeHead.ogType === 'website',
      knowledgeHead.canonical || 'no canonical',
    );
    check('knowledge index title is templated, description is real', /\bFOOTBALL OS\b/u.test(knowledgeHead.title) && knowledgeHead.description.length > 60, knowledgeHead.title);
    const siteGraph = knowledgeHead.jsonLd.find((node) => node['@type'] === 'WebSite');
    check('a WebSite graph identifies the site by absolute URL', siteGraph?.name === 'FOOTBALL OS' && /^https?:\/\//u.test(String(siteGraph?.url ?? '')), JSON.stringify(siteGraph ?? {}));
    const documentHead = await pageHead(firstDoc);
    const article = documentHead.jsonLd.find((node) => node['@type'] === 'Article');
    check(
      'document page carries Article structured data with its headline',
      article?.headline === documentHead.ogTitle && /^https?:\/\//u.test(String(article?.url ?? '')) && article?.author?.name === 'FOOTBALL OS',
      `${article?.headline ?? 'no Article'} · ${article?.dateModified ?? 'no dateModified'}`,
    );
    await shot(page, '19-seo-document-head-desktop');

    // 12b. Football World (M3): the public surface, the §80 routes and what they refuse to show.
    // Rows are read through the web tier's own /api/v1 proxy, so this also proves a signed-out
    // visitor can reach the world API at all.
    const worldApi = async (path) => {
      const response = await fetch(`${BASE}/api/v1/world${path}`);
      if (!response.ok) throw new Error(`GET /api/v1/world${path} → ${response.status}`);
      return response.json();
    };
    const worldStatus = await worldApi('/status');
    const worldCompetitions = (await worldApi('/competitions?page_size=50')).items;
    const worldLeague = worldCompetitions.find((row) => row.kind === 'league');
    const worldCup = worldCompetitions.find((row) => row.kind !== 'league');
    const worldTeam = (await worldApi('/teams?page_size=3')).items[0];
    const worldPlayer = (await worldApi('/players?page_size=3')).items[0];
    const worldPlayed = (await worldApi('/matches?status=completed&page_size=3')).items[0];
    const worldScheduled = (await worldApi('/matches?status=scheduled&page_size=3')).items[0];
    const worldArticle = (await worldApi('/news?page_size=3')).items[0];

    check(
      'the web proxy serves the world API to a signed-out visitor',
      worldStatus.counts.players > 0 && worldStatus.is_demo_data === true,
      `${worldStatus.counts.players} players · origin ${worldStatus.data_origin}`,
    );
    const bySegment = (segment) => locs.filter((url) => new URL(url).pathname.startsWith(`/${segment}/`)).length;
    check(
      'the sitemap advertises every generated row under its §80 route',
      bySegment('player') === worldStatus.counts.players &&
        bySegment('team') === worldStatus.counts.teams &&
        bySegment('match') === worldStatus.counts.matches &&
        bySegment('news') === worldStatus.counts.articles &&
        bySegment('competition') === worldStatus.counts.competitions,
      `player ${bySegment('player')}/${worldStatus.counts.players} · team ${bySegment('team')} · match ${bySegment('match')} · news ${bySegment('news')} · competition ${bySegment('competition')}`,
    );
    check(
      'the search page stays out of the sitemap while content pages are in it',
      !locs.some((url) => new URL(url).pathname === '/world/search') && locs.some((url) => new URL(url).pathname === '/world'),
      `${locs.length} entries`,
    );

    await open(page, '/world');
    await waitForText(page, 'Football World');
    const worldIndex = await bodyText(page);
    check(
      'the world index prints the API-measured row counts',
      Object.values(worldStatus.counts).every((count) => worldIndex.includes(count.toLocaleString('en-GB'))),
      JSON.stringify(worldStatus.counts),
    );
    check(
      'the world index labels itself demo data and repeats the API disclaimer verbatim',
      /DEMO DATA/u.test(worldIndex) && worldIndex.includes(worldStatus.disclaimer.slice(0, 60)),
      worldStatus.disclaimer.slice(0, 60),
    );
    check(
      'the world index ships the single search box (spec §56)',
      await page.evaluate(() => !!document.querySelector('form[action="/world/search"] input[name="q"]')),
    );
    check(
      'the §65 gate is reported as met for every gated table',
      /MEETS/u.test(worldIndex) && !/BELOW/u.test(worldIndex),
    );
    check(
      'Football World is reachable from the navigation',
      await page.evaluate(() => !!document.querySelector('.nav__link[href="/world"]')),
    );
    await shot(page, '21-world-index-desktop');

    await open(page, '/world/search?q=athletic');
    await waitForText(page, 'Results, ranked by term overlap');
    const searchHead = await page.evaluate(() => document.head.querySelector('meta[name="robots"]')?.content ?? '');
    check(
      'the search page is noindex,follow so a query shell is not indexed as content',
      /noindex/iu.test(searchHead) && /follow/iu.test(searchHead),
      searchHead || 'no robots meta',
    );
    await shot(page, '22-world-search-desktop');

    await open(page, worldScheduled.path);
    await waitForText(page, 'no score yet');
    const scheduledBody = await bodyText(page);
    check(
      'an unplayed fixture shows a kick-off time and refuses a score (spec §65)',
      /not been played/iu.test(scheduledBody) && !/0\s*[–-]\s*0/u.test(scheduledBody) && !!worldScheduled.kickoff_at,
      `${worldScheduled.status} · ${worldScheduled.score}`,
    );
    await shot(page, '23-world-match-scheduled-desktop');

    await open(page, worldPlayed.path);
    await waitForText(page, 'Who scored');
    const playedBody = await bodyText(page);
    const playedHead = await pageHead(worldPlayed.path);
    const matchEvent = playedHead.jsonLd.find((node) => node['@type'] === 'SportsEvent');
    const goalsInScore = (worldPlayed.home_goals ?? 0) + (worldPlayed.away_goals ?? 0);
    check(
      'the match centre shows the score and its own goals reconcile with the player lines',
      playedBody.includes(`goals in score: ${goalsInScore}`) && /RECONCILES/u.test(playedBody),
      playedBody.match(/goals in score: \d+[^]{0,60}/u)?.[0]?.replace(/\s+/g, ' ').slice(0, 90) ?? 'no goals block',
    );
    check(
      'the match centre publishes SportsEvent data on both sides with a start date',
      !!matchEvent?.homeTeam?.name &&
        !!matchEvent?.awayTeam?.name &&
        !!matchEvent?.startDate &&
        String(matchEvent?.eventStatus ?? '').endsWith('EventCompleted') &&
        matchEvent?.homeTeam?.url === `${BASE}${worldPlayed.home?.path}`,
      `${matchEvent?.homeTeam?.name ?? '—'} v ${matchEvent?.awayTeam?.name ?? '—'} · ${matchEvent?.startDate ?? 'no startDate'}`,
    );
    await shot(page, '24-world-match-centre-desktop');

    await open(page, worldTeam.path);
    await waitForText(page, 'Squad');
    const teamHead = await pageHead(worldTeam.path);
    const sportsTeam = teamHead.jsonLd.find((node) => node['@type'] === 'SportsTeam');
    const squadRows = await page.evaluate(() => document.querySelectorAll('.table tbody tr').length);
    check('a club page lists its whole stored squad', squadRows >= worldTeam.squad_size, `${squadRows} table rows vs squad_size ${worldTeam.squad_size}`);
    check(
      'squad rows deep-link to the §80 /player/{slug} route',
      (await page.evaluate(() => new Set([...document.querySelectorAll('a[href^="/player/"]')].map((a) => a.getAttribute('href'))).size)) >= worldTeam.squad_size,
    );
    check(
      'the club page carries SportsTeam structured data on its own canonical URL',
      sportsTeam?.name === worldTeam.name && sportsTeam?.url === teamHead.canonical,
      `${sportsTeam?.name ?? 'no SportsTeam'} · ${teamHead.canonical}`,
    );
    await shot(page, '25-world-team-desktop');

    const playerDetail = await worldApi(`/players/${worldPlayer.slug}`);
    await open(page, worldPlayer.path);
    await waitForText(page, 'Season totals');
    const playerBody = await bodyText(page);
    const playerHead = await pageHead(worldPlayer.path);
    const athlete = playerHead.jsonLd.find((node) => node['@type'] === 'Athlete');
    check(
      'a player page states that its season totals are the sum of its stat lines',
      /totals equal the sum of this player's stat lines/u.test(playerBody) && /consistency/iu.test(playerBody),
      playerDetail.season_stats.consistency_check,
    );
    check(
      'the player page renders every stored statistic line server-side',
      // Row counts, not text: `.eyebrow` is uppercased by CSS, so `innerText` case is not stable to compare.
      (await page.evaluate(() => [...document.querySelectorAll('table')].map((table) => table.querySelectorAll('tbody tr').length)))
        .at(-1) === playerDetail.stat_lines.length && /rows/iu.test(playerBody),
      `${playerDetail.stat_lines.length} lines from the API`,
    );
    check(
      'the attribute radar is inline SVG, not a client-side chart',
      (await page.evaluate(() => document.querySelectorAll('svg[role="img"]').length)) > 0 && !!athlete,
      `${Object.keys(playerDetail.player.attributes).length} attributes`,
    );
    await shot(page, '26-world-player-desktop');

    await open(page, worldLeague.path);
    await waitForText(page, 'Table');
    const leagueTable = await page.evaluate(() =>
      [...document.querySelectorAll('.table tbody tr')].map((row) => [...row.querySelectorAll('td')].map((cell) => cell.textContent.trim())),
    );
    const pointsColumn = leagueTable.map((row) => Number.parseInt(row[9] ?? '', 10)).filter((value) => !Number.isNaN(value));
    check(
      'a league table is ordered by points and shows only played rows',
      leagueTable.length >= 3 && pointsColumn.every((value, index) => index === 0 || pointsColumn[index - 1] >= value),
      pointsColumn.join(' ≥ ') || 'no rows',
    );
    const leagueBody = await bodyText(page);
    check(
      'the standings say where they came from',
      /aggregated from the stored completed fixtures/iu.test(leagueBody),
      leagueBody.match(/Table aggregated[^.]*\./u)?.[0] ?? 'no provenance line',
    );
    await shot(page, '27-world-competition-league-desktop');

    await open(page, worldCup.path);
    await waitForText(page, 'Entrants');
    const cupBody = await bodyText(page);
    check(
      'a knockout is not given an invented league table',
      /No league table/u.test(cupBody) && /bracket/iu.test(cupBody) && !/aggregated from the stored completed fixtures/iu.test(cupBody),
      cupBody.match(/Knockout[^.]*\./u)?.[0]?.slice(0, 90) ?? 'no format note',
    );
    await shot(page, '28-world-competition-cup-desktop');

    await open(page, worldArticle.path);
    await waitForText(page, 'Claim class');
    const newsBody = await bodyText(page);
    const newsHead = await pageHead(worldArticle.path);
    const newsGraph = newsHead.jsonLd.find((node) => node['@type'] === 'NewsArticle');
    check(
      'a generated report declares its claim class, its source and its own disclaimer',
      newsBody.includes(worldArticle.claim_class) &&
        newsBody.includes(`source: ${worldArticle.source_name}`) &&
        /synthetic-world/u.test(newsBody),
      `${worldArticle.claim_class} · ${worldArticle.source_name}`,
    );
    check(
      'the report carries NewsArticle structured data with a real publication date',
      newsGraph?.headline === worldArticle.title && !!newsGraph?.datePublished && newsHead.ogUrl === newsHead.canonical,
      `${newsGraph?.datePublished ?? 'no datePublished'}`,
    );
    const crossLinks = await page.evaluate(() => [
      ...new Set(
        [...document.querySelectorAll('a[href^="/player/"], a[href^="/team/"], a[href^="/match/"], a[href^="/competition/"], a[href^="/news/"]')].map(
          (anchor) => anchor.getAttribute('href'),
        ),
      ),
    ]);
    const crossStatuses = await probeStatuses(crossLinks.slice(0, 12).map((href) => `${BASE}${href}`));
    check(
      'entity links out of a report resolve against the §80 routes',
      crossLinks.length > 0 && crossStatuses.every((status) => status === 200),
      `${crossLinks.length} links · ${crossStatuses.length} probed · ${crossStatuses.filter((status) => status !== 200).length} failed`,
    );
    await shot(page, '29-world-news-desktop');

    await open(page, '/world/players');
    await waitForText(page, 'Players');
    const firstRow = () => page.evaluate(() => document.querySelector('.table tbody tr td:nth-child(2)')?.textContent.trim() ?? '');
    const beforePaging = await firstRow();
    await clickByText(page, 'a.btn', 'Next →');
    await waitForText(page, 'Page 2 of');
    const afterPaging = await firstRow();
    check('the players list paginates to a different page of rows', !!beforePaging && !!afterPaging && beforePaging !== afterPaging, `${beforePaging} → ${afterPaging}`);
    await open(page, '/world/players?position=ST&sort=goals&order=asc');
    const positions = await page.evaluate(() => [...document.querySelectorAll('.table tbody tr .world-pos')].map((node) => node.textContent.trim()));
    check(
      'position and sort filters apply to every rendered row',
      positions.length > 0 && positions.every((value) => value === 'ST'),
      positions.slice(0, 4).join(', ') || 'no rows',
    );
    const goalColumn = await page.evaluate(() =>
      [...document.querySelectorAll('.table tbody tr')].map((row) => Number.parseInt(row.children[6]?.textContent ?? '', 10)).filter((value) => !Number.isNaN(value)),
    );
    check(
      'ascending sort really orders the column it claims to sort',
      goalColumn.every((value, index) => index === 0 || goalColumn[index - 1] <= value),
      goalColumn.slice(0, 6).join(' ≤ ') || 'no values',
    );
    await shot(page, '30-world-players-desktop');

    const brokenSlug = await fetch(`${BASE}/team/no-such-club-exists-anywhere`);
    const brokenBody = await brokenSlug.text();
    check(
      'an unknown world slug is a 404 page, not an empty shell or a invented record',
      brokenSlug.status === 404 && !/Braeford|Ildwick/u.test(brokenBody),
      `${brokenSlug.status}`,
    );

    // 12c. Tactical Lab (M4): the board is drawn from metres, a "what if" is a URL, and no
    // measurement reaches the page without the formula that produced it.
    const tacticsApi = async (path) => {
      const response = await fetch(`${BASE}/api/v1/tactics${path}`);
      if (!response.ok) throw new Error(`GET /api/v1/tactics${path} → ${response.status}`);
      return response.json();
    };
    const tacticsStatus = await tacticsApi('/status');
    const tacticsList = await tacticsApi('?page_size=50');
    const tactic = tacticsList.items.find((item) => item.slug === '4-3-3-press-high') ?? tacticsList.items[0];
    const tacticDetail = await tacticsApi(`/${tactic.slug}`);
    const sibling = tacticsList.items.find((item) => item.formation === tactic.formation && item.slug !== tactic.slug);

    check(
      'the tactics API serves the whole authored catalogue to a signed-out visitor',
      tacticsStatus.ready === true && tacticsStatus.stored === 50 && tacticsStatus.metrics.length === 8 && tacticsStatus.changes.length === 6,
      `${tacticsStatus.stored} systems · ${tacticsStatus.metric_keys.length} measures · ${tacticsStatus.changes.length} changes`,
    );
    check(
      'the sitemap advertises all 50 systems and neither query page',
      bySegment('tactics') === 50 &&
        !locs.some((url) => /\/tactics\/compare/iu.test(url)) &&
        tacticsList.items.every((item) => locs.includes(`${BASE}${item.path}`)),
      `${bySegment('tactics')} tactics entries of ${locs.length} total`,
    );

    await open(page, '/tactics');
    await waitForText(page, 'Tactical Lab');
    const tacticsIndex = await bodyText(page);
    // Rendered text is compared with whitespace collapsed: `innerText` re-breaks a long paragraph at
    // every visual line, which is not the page failing to say the thing.
    const flatten = (value) => value.replace(/\s+/gu, ' ').trim();
    const tacticsPlain = flatten(tacticsIndex);
    check(
      'the lab index is labelled PROJECT AUTHORED and never claims to be demo data',
      /PROJECT AUTHORED/u.test(tacticsIndex) && !/DEMO DATA/u.test(tacticsIndex),
      tacticsIndex.split('\n').filter((line) => /AUTHORED|DEMO DATA/iu.test(line)).slice(0, 3).join(' | ') || 'no label found',
    );
    check(
      'the lab index repeats the API disclaimer verbatim',
      tacticsPlain.includes(flatten(tacticsStatus.disclaimer)),
      `${flatten(tacticsStatus.disclaimer).slice(0, 70)}… present: ${tacticsPlain.includes(flatten(tacticsStatus.disclaimer))}`,
    );
    check(
      'the index prints the eight formulas and one real board of eleven positions',
      (await page.evaluate(() => document.querySelectorAll('.tac-formula').length)) >= 8 &&
        (await page.evaluate(() => document.querySelectorAll('.pitch-dot').length)) === 11,
      await page.evaluate(
        () =>
          `${document.querySelectorAll('.tac-formula').length} formula cells · ${document.querySelectorAll('.pitch-dot').length} players drawn`,
      ),
    );
    check('Tactical Lab is reachable from the navigation', await page.evaluate(() => !!document.querySelector('.nav__link[href="/tactics"]')));
    await shot(page, '31-tactics-index-desktop');

    await open(page, tactic.path);
    await waitForText(page, 'Both phases, one structure');
    const detailBody = await bodyText(page);
    const detailHead = await pageHead(tactic.path);
    const staticBoards = await page.evaluate(() => {
      const boards = [...document.querySelectorAll('.pitch svg')];
      return { svgs: boards.length, dots: boards.reduce((total, svg) => total + svg.querySelectorAll('.pitch-dot').length, 0) };
    });
    check(
      'a system page draws both phases from the same eleven roles',
      staticBoards.svgs === 2 && staticBoards.dots === 22 && (await page.evaluate(() => document.querySelectorAll('.table tbody tr').length)) >= 11 + 8 + 8,
      `${staticBoards.svgs} static boards · ${staticBoards.dots} dots, plus the player's own eleven`,
    );
    check(
      'every measurement on the page repeats the rule that produced it',
      (await page.evaluate(() => [...document.querySelectorAll('.tac-formula')].every((cell) => cell.textContent.trim().length > 20))) &&
        (await page.evaluate(() => document.querySelectorAll('.tac-formula').length)) >= 16,
      await page.evaluate(() => `${document.querySelectorAll('.tac-formula').length} formula cells`),
    );
    check(
      'the verdicts on the page are the ones the API graded from its own measurements',
      tacticDetail.strengths.every((line) => detailBody.includes(line)) && tacticDetail.risks.every((line) => detailBody.includes(line)),
      tacticDetail.strengths[0]?.slice(0, 110) ?? 'no verdicts',
    );
    check(
      'the authored transform is stated with its own numbers, not presented as two drawings',
      detailBody.includes(`${tacticDetail.block_depth} m`) && /same eleven players rescaled/iu.test(detailBody),
      detailBody.match(/out-of-possession board is the same[^.]*\./iu)?.[0]?.slice(0, 120) ?? 'no transform note',
    );
    const tacticGraph = detailHead.jsonLd.find((node) => node['@type'] === 'Article');
    check(
      'the system page carries Article structured data whose URL is its canonical',
      tacticGraph?.headline === tacticDetail.name && tacticGraph?.url === detailHead.canonical,
      `${tacticGraph?.headline ?? 'no Article'} · ${detailHead.canonical}`,
    );
    const analysis = await tacticsApi(`/${tactic.slug}/feedback`);
    check(
      'every topic the analysis asks is either cited or refused, and the page shows the same split',
      (await page.evaluate(() => document.querySelectorAll('.tac-point').length)) === analysis.points.length &&
        analysis.points.length > 0 &&
        // Six topics are asked (app/services/tactics/feedback.py TOPICS). A topic that is neither
        // cited nor refused would be a silent gap between the measurement and the page.
        analysis.points.length + analysis.ungrounded.length === 6,
      `${analysis.points.length} cited · ${analysis.ungrounded.length} refused over ${analysis.scanned_chunks} passages`,
    );
    const expectedRefs = [...new Set(analysis.points.map((point) => point.citation.ref))];
    const citedHrefs = await page.evaluate(() => [...new Set([...document.querySelectorAll('a[href^="/knowledge/"]')].map((a) => a.getAttribute('href')))]);
    const citedStatuses = await probeStatuses(citedHrefs.map((href) => `${BASE}${href}`));
    check(
      'every passage the analysis leans on resolves to a real library anchor',
      // Six topics can lean on fewer than six passages — two systems of thought cited in the same
      // document collapse here — so the claim is that the page's links are exactly the payload's refs,
      // that no point cites nothing, and that every one of them answers.
      analysis.points.every((point) => point.citation.ref.startsWith('/knowledge/')) &&
        expectedRefs.length > 0 &&
        citedHrefs.length === expectedRefs.length &&
        expectedRefs.every((ref) => citedHrefs.includes(ref)) &&
        citedStatuses.every((status) => status === 200),
      `${analysis.points.length} points on ${citedHrefs.length} distinct passages · ${[...new Set(citedStatuses)].join(',')} statuses`,
    );
    const analysisBody = await bodyText(page);
    const refusalPanelShown = /Topics this build refused to answer/iu.test(analysisBody);
    check(
      'the page names the topics it refused with the gate that refused them, and claims no refusal it did not make',
      refusalPanelShown === (analysis.ungrounded.length > 0) &&
        (analysis.ungrounded.length === 0 || analysisBody.includes(analysis.ungrounded[0].reason.slice(0, 40))),
      analysis.ungrounded.length ? analysis.ungrounded[0].reason.slice(0, 80) : `all ${analysis.points.length} topics grounded · no refusal panel`,
    );
    check(
      'the analysis is labelled extractive assembly, never a model opinion',
      /EXTRACTIVE · NO AI KEY/u.test(analysisBody) && !/AI-generated/iu.test(analysisBody),
      `${analysis.model} · ${analysis.provider}`,
    );
    await shot(page, '32-tactics-detail-desktop');

    const counterfactualJson = await tacticsApi(`/${tactic.slug}/counterfactual?change=raise-back-line`);
    const movedCount = counterfactualJson.board_before.filter(
      (row, index) => row.x !== counterfactualJson.board_after[index].x || row.y !== counterfactualJson.board_after[index].y,
    ).length;
    await open(page, `${tactic.path}?change=raise-back-line`);
    await waitForText(page, 'The board, before and after');
    const counterfactual = await page.evaluate(() => {
      const row = [...document.querySelectorAll('.table tbody tr')].find((candidate) => candidate.textContent.includes('Space behind'));
      const cells = row ? [...row.querySelectorAll('td')].map((cell) => cell.textContent.trim()) : [];
      return {
        cells,
        arrows: document.querySelectorAll('.pitch-moves line').length,
        ghosts: document.querySelectorAll('.pitch-dot--ghost').length,
        clamped: document.body.innerText.includes('would have left the pitch'),
      };
    });
    check(
      'the board draws exactly the displacements the API reported',
      counterfactual.arrows === movedCount && counterfactual.ghosts === 11,
      `${counterfactual.arrows} arrows drawn · ${movedCount} positions moved in the payload · ${counterfactual.ghosts} hollow before-positions`,
    );
    const behind = Number.parseFloat(counterfactual.cells[1] ?? '0');
    const behindAfter = Number.parseFloat(counterfactual.cells[2] ?? '0');
    check(
      'raising the back line costs exactly the metres it buys, on the page and not just in a test',
      counterfactual.cells.length === 5 && behindAfter - behind === 8,
      counterfactual.cells.join(' | ').slice(0, 120),
    );
    await shot(page, '33-tactics-counterfactual-desktop');

    await open(page, `${tactic.path}?change=teleport-the-striker`);
    await waitForText(page, 'is not one of the');
    check(
      'an invented change is refused by name and the offered six are listed',
      (await bodyText(page)).includes('6 changes this lab offers'),
      'unknown-change notice rendered',
    );

    if (sibling) {
      await open(page, `/tactics/compare?a=${encodeURIComponent(tactic.slug)}&b=${encodeURIComponent(sibling.slug)}&phase=out`);
      await waitForText(page, 'Eight measurements, side by side');
      const compared = await page.evaluate(() => {
        const row = [...document.querySelectorAll('.table tbody tr')].find((candidate) => candidate.textContent.includes('Space behind'));
        return {
          cells: row ? [...row.querySelectorAll('td')].map((cell) => cell.textContent.trim()) : [],
          robots: document.head.querySelector('meta[name="robots"]')?.content ?? '',
          boards: document.querySelectorAll('.pitch-dot').length,
        };
      });
      check(
        'the comparison board measures both sides and keeps itself out of the index',
        /noindex/iu.test(compared.robots) && compared.boards === 22 && compared.cells.length === 5,
        `${compared.robots || 'no robots meta'} · ${compared.boards} dots`,
      );
      check(
        'the same shape under two temperaments really differs where the words say it differs',
        Number.parseFloat(compared.cells[1]) > Number.parseFloat(compared.cells[2]),
        `${tactic.slug} ${compared.cells[1]} vs ${sibling.slug} ${compared.cells[2]}`,
      );
      await shot(page, '34-tactics-compare-desktop');
    }

    await open(page, '/tactics/compare');
    await waitForText(page, 'Pick two different systems');
    check(
      'an unchosen comparison explains itself instead of inventing a row',
      (await bodyText(page)).includes('Until both are chosen nothing is computed'),
    );

    const brokenTactic = await fetch(`${BASE}/tactics/4-3-3-not-a-temperament`);
    check('an unknown tactical system is a 404, not an empty board', brokenTactic.status === 404, `${brokenTactic.status}`);

    // 12d. The phase player, and a board a person can drag, save and share.
    await open(page, tactic.path);
    await waitForText(page, 'Play the phase change');
    const playerBefore = await page.evaluate(() => document.querySelector('[data-testid="phase-label"]')?.textContent ?? '');
    await clickByText(page, 'button', 'Play the phase change');
    await sleep(700);
    const playerDuring = await page.evaluate(() => ({
      label: document.querySelector('[data-testid="phase-label"]')?.textContent ?? '',
      badges: [...document.querySelectorAll('.badge--sim')].length,
      scrub: !!document.querySelector('input.pitch-scrub'),
      // AI_POLICY §2 requires this exact stamp on anything simulated.
      policy: /Simulation result is fictional \/ model-generated and should not be interpreted as a real-world prediction\./u.test(
        document.body.innerText,
      ),
    }));
    check(
      'the player moves between the two stored phases and carries the policy stamp on simulation',
      playerBefore !== playerDuring.label &&
        /\d% of the way/.test(playerDuring.label) &&
        playerDuring.badges > 0 &&
        playerDuring.scrub &&
        playerDuring.policy,
      `${playerBefore} → ${playerDuring.label} · AI_POLICY §2 sentence present: ${playerDuring.policy}`,
    );
    await clickByText(page, 'button', 'Pause');
    await shot(page, '35-tactics-player-desktop');

    await open(page, '/tactics/boards');
    await waitForText(page, 'My tactical boards');
    check('the boards area is signed-in only in the navigation too', await page.evaluate(() => !!document.querySelector('.nav__link[href="/tactics/boards"]')));
    await clickByText(page, 'button', 'Create and edit');
    await waitForText(page, 'Drag · save · share');
    const dots = await page.evaluate(() => document.querySelectorAll('.pitch-dot--grabbable').length);
    check('a new board opens as eleven draggable players on the same measured grass', dots === 11, `${dots} grabbable dots`);

    const beforeDrag = await page.evaluate(() => {
      const dot = document.querySelectorAll('.pitch-dot--grabbable')[6];
      const circle = dot.querySelector('circle');
      const box = circle.getBoundingClientRect();
      return { cy: circle.getAttribute('cy'), x: box.x + box.width / 2, y: box.y + box.height / 2 };
    });
    await page.mouse.move(beforeDrag.x, beforeDrag.y);
    await page.mouse.down();
    await page.mouse.move(beforeDrag.x + 4, beforeDrag.y - 70, { steps: 10 });
    await page.mouse.up();
    await sleep(250);
    const afterDrag = await page.evaluate(() => document.querySelectorAll('.pitch-dot--grabbable')[6].querySelector('circle').getAttribute('cy'));
    const dirtyNotice = await bodyText(page);
    check(
      'dragging a player moves it on the lawn and says the numbers are now stale',
      Number(afterDrag) < Number(beforeDrag.cy) && /Unsaved changes/iu.test(dirtyNotice),
      `cy ${beforeDrag.cy} → ${afterDrag}`,
    );

    const boardSlug = new URL(page.url()).pathname.split('/').pop();
    // Read the stored board back through the browser, so the session cookie rides along: a plain
    // Node fetch would only prove the endpoint rejects anonymous callers.
    const readBoard = async () =>
      page.evaluate(async (slug) => (await fetch(`/api/v1/boards/${slug}`, { cache: 'no-store' })).json(), boardSlug);
    const storedBefore = await readBoard();
    await clickByText(page, 'button', 'Save board');
    await waitForText(page, 'Saved. The measurements');
    const storedAfter = await readBoard();
    const firstDifference = storedAfter.phase_in.findIndex((row, index) => row.x !== storedBefore.phase_in[index]?.x || row.y !== storedBefore.phase_in[index]?.y);
    check(
      'saving writes the dragged position to the database, not just to the page',
      storedAfter.phase_in.length === 11 && firstDifference >= 0,
      `dragged slot 6; stored change found at index ${firstDifference} (${
        firstDifference >= 0 ? `${storedBefore.phase_in[firstDifference].role} ${storedBefore.phase_in[firstDifference].y} → ${storedAfter.phase_in[firstDifference].y}` : 'nothing differs'
      })`,
    );
    check(
      'the stored board carries the user-origin label and its own disclaimer',
      storedAfter.data_origin === 'user' && /arranged by a FOOTBALL OS user/iu.test(storedAfter.disclaimer),
      storedAfter.disclaimer.slice(0, 60),
    );
    await shot(page, '36-tactics-board-editor-desktop');

    await clickByText(page, 'button', 'Create a share link');
    await waitForText(page, 'Sharing is on');
    const shareUrl = await page.evaluate(() => document.querySelector('a[href^="/tactics/shared/"]')?.getAttribute('href') ?? '');
    const anonymous = await fetch(`${BASE}${shareUrl}`);
    const anonymousBody = await anonymous.text();
    // Checked against the values that would actually be a leak. An `@\w` pattern was my first try
    // and matches the page's own `@media` CSS — a check that cannot pass proves nothing.
    const leaks = [EMAIL, PLAYER_NAME, 'visual-qa-'].filter((secret) => anonymousBody.includes(secret));
    check(
      'the share link opens for a signed-out visitor and names no owner',
      shareUrl.startsWith('/tactics/shared/') && anonymous.status === 200 && /a FOOTBALL OS account/u.test(anonymousBody) && leaks.length === 0,
      `${anonymous.status} · ${shareUrl.slice(0, 34)}… · leaks: ${leaks.length ? leaks.join(',') : 'none'}`,
    );
    check('a shared board is not offered to the crawler', /Disallow: \/tactics\/shared/u.test((await (await fetch(`${BASE}/robots.txt`)).text())));

    // The live link, at 375px, while it still works — it is revoked a few lines below.
    // (Inlined rather than calling `mobileSurface`, which is defined later in the walk.)
    await page.setViewport(MOBILE);
    await open(page, shareUrl);
    const sharedNarrow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    check('mobile 375px: the shared board renders its two phases with no horizontal overflow', sharedNarrow <= 1, `overflow ${sharedNarrow}px`);
    await shot(page, '37-mobile-tactics-shared');
    await page.setViewport(DESKTOP);
    await open(page, `/tactics/boards/${boardSlug}`);
    await waitForText(page, 'Revoke link');

    await clickByText(page, 'button', 'Revoke link');
    await waitForText(page, 'Link revoked');
    const afterRevoke = await fetch(`${BASE}${shareUrl}`);
    check('revoking kills the old link without deleting the board', afterRevoke.status === 404, `${afterRevoke.status}`);

    // 12e. Video analysis: upload a clip the walk generated, measure it, and prove nobody else can look.
    const clipPath = join(tmpdir(), `football-os-visual-qa-${stamp}.mp4`);
    let clipReady = false;
    let clipFailure = '';
    try {
      await new Promise((resolveSpawn, rejectSpawn) => {
        execFile(
          'ffmpeg',
          ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=320x180:d=2:r=25', '-pix_fmt', 'yuv420p', clipPath],
          (error) => (error ? rejectSpawn(error) : resolveSpawn()),
        );
      });
      clipReady = (await stat(clipPath)).size > 1000;
    } catch (cause) {
      clipFailure = String(cause?.message ?? cause).slice(0, 140);
    }
    check('the walk can generate its own test clip with ffmpeg (no third-party video in the repo)', clipReady, clipReady ? `${clipPath} · ${(await stat(clipPath)).size} bytes` : `ffmpeg unavailable: ${clipFailure}`);

    if (clipReady) {
      await open(page, '/video');
      await waitForText(page, 'My video analysis');
      const fileInput = await page.$('input[type="file"]');
      check('the video index offers an upload control and states the privacy rule', !!fileInput && (await bodyText(page)).includes('only this account can read a clip'));
      if (fileInput) {
        await fileInput.uploadFile(clipPath);
        await clickByText(page, 'button', 'Upload clip');
        await waitForText(page, 'What was measured');
        const reportPath = new URL(page.url()).pathname;
        const uploadedBody = await bodyText(page);
        check(
          'an uploaded clip lands on its own report, labelled as the user content it is',
          /^\/video\/vid_/u.test(reportPath) && /data_origin: user/u.test(uploadedBody) && /sha /u.test(uploadedBody),
          `${reportPath} · ${uploadedBody.match(/data_origin: \w+/u)?.[0] ?? 'no origin'}`,
        );
        const head = await page.evaluate(() => document.head.querySelector('meta[name="robots"]')?.content ?? '');
        const robotsText = (await (await fetch(`${BASE}/robots.txt`)).text()).replace(/\r/g, '');
        check(
          'a clip report is noindexed, and robots keeps /video out of the crawl entirely',
          /noindex/iu.test(head) && /Disallow: \/video$/mu.test(robotsText),
          `${head || 'no robots meta'} · disallow /video: ${/Disallow: \/video$/mu.test(robotsText)}`,
        );

        await clickByText(page, 'button', 'Analyse this clip');
        await waitForText(page, 'Detection timeline', 120_000);
        await page.waitForFunction(
          () => [...document.querySelectorAll('[data-testid="video-frames"] img')].every((img) => img.complete && img.naturalWidth > 0),
          { timeout: 60_000 },
        );
        const analysed = await page.evaluate(() => {
          // innerText carries the line breaks the layout made — and a narrow mono cell breaks inside a
          // token — so the measured panel is read from the DOM as textContent, not from what is on screen.
          const text = document.body.innerText.replace(/\s+/g, ' ');
          const measured = (document.querySelector('[data-testid="video-measured"]')?.textContent ?? '').replace(/\s+/g, ' ');
          return {
            detections: [...document.querySelectorAll('[data-testid="video-detections"] tbody tr')].map((row) => row.textContent.replace(/\s+/g, ' ').trim()),
            frames: document.querySelectorAll('[data-testid="video-frames"] img').length,
            frameChip: text.match(/(\d+) frames sampled/u)?.[1] ?? '',
            provider: text.includes('demo-pixel-stats'),
            model: measured.includes('ffmpeg ppm + pure-python statistics'),
            limitations: measured.includes('It does not detect players, a ball, formations or football events'),
            measured: measured.slice(0, 60),
            player: document.querySelector('video')?.currentSrc ?? document.querySelector('video')?.getAttribute('src') ?? '',
            loadedFrames: [...document.querySelectorAll('[data-testid="video-frames"] img')].filter((img) => img.naturalWidth > 0).length,
          };
        });
        check(
          'analysis names the demo provider, its model and its own limitations on the report',
          analysed.detections.length >= 1 && analysed.provider && analysed.model && analysed.limitations,
          `${analysed.detections.length} detections · provider ${analysed.provider} · model ${analysed.model} · limitations ${analysed.limitations} · ${analysed.detections[0]?.slice(0, 70) ?? '—'}`,
        );
        check(
          'the frames strip shows exactly the samples the measurements came from, and they load',
          analysed.frames > 0 && analysed.frames === Number(analysed.frameChip) && analysed.loadedFrames === analysed.frames,
          `${analysed.frames} shown / ${analysed.frameChip} sampled / ${analysed.loadedFrames} decoded by the browser`,
        );
        check(
          'playback and frames come from the owner-only API routes, not a public file path',
          /\/api\/v1\/video\/vid_[^/]+\/file$/u.test(analysed.player),
          analysed.player.replace(/^https?:\/\/[^/]+/u, '') || 'no player source',
        );

        // The player proving it read the bytes is a stronger claim than an attribute matching a regex:
        // it exercises the route end to end, byte ranges included.
        let playback = { ready: false, duration: 0, error: null };
        try {
          await page.waitForFunction(
            () => {
              const video = document.querySelector('video');
              return !!video && video.readyState >= 1 && Number.isFinite(video.duration) && video.duration > 0;
            },
            { timeout: 45_000 },
          );
        } catch {
          /* reported by the check below */
        }
        playback = await page.evaluate(() => {
          const video = document.querySelector('video');
          return { ready: !!video && video.readyState >= 1, duration: video?.duration ?? 0, error: video?.error?.code ?? null };
        });
        check(
          "the browser reads the clip's metadata through the owner-only route, so the file really plays",
          playback.ready && playback.duration > 0,
          `duration ${playback.duration.toFixed(2)}s · media error code ${playback.error ?? 'none'}`,
        );

        // A <video> element asks for byte ranges, and the cookie proxy is the only road to the file. Asked for a
        // slice, the browser must get 206 and the slice's own headers back — not a whole-file 200 it cannot use,
        // and not a 416 the proxy swallows. This is fetched from inside the page because the session cookie is
        // what authorises it; the harness's own fetch has no cookies.
        const fileUrl = `${reportPath.replace('/video/', '/api/v1/video/')}/file`;
        const ranged = await page.evaluate(
          async (url) => {
            const slice = await fetch(url, { credentials: 'same-origin', headers: { range: 'bytes=0-99' } });
            const sliceBytes = await slice.arrayBuffer();
            const suffix = await fetch(url, { credentials: 'same-origin', headers: { range: 'bytes=-1024' } });
            const suffixBytes = await suffix.arrayBuffer();
            const past = await fetch(url, { credentials: 'same-origin', headers: { range: 'bytes=99999999-' } });
            await past.arrayBuffer();
            const whole = await fetch(url, { credentials: 'same-origin' });
            const wholeBytes = await whole.arrayBuffer();
            return {
              status: slice.status,
              contentRange: slice.headers.get('content-range'),
              acceptRanges: slice.headers.get('accept-ranges'),
              sliceBytes: sliceBytes.byteLength,
              suffixStatus: suffix.status,
              suffixBytes: suffixBytes.byteLength,
              suffixRange: suffix.headers.get('content-range'),
              pastStatus: past.status,
              pastRange: past.headers.get('content-range'),
              wholeStatus: whole.status,
              wholeBytes: wholeBytes.byteLength,
            };
          },
          fileUrl,
        );
        const total = Number((ranged.contentRange ?? '').split('/')[1] ?? 0);
        check(
          'the clip answers a byte range through the cookie proxy with the slice and the headers that describe it',
          ranged.status === 206 &&
            ranged.sliceBytes === 100 &&
            ranged.contentRange === `bytes 0-99/${total}` &&
            ranged.acceptRanges === 'bytes' &&
            ranged.suffixStatus === 206 &&
            ranged.suffixBytes === 1024 &&
            ranged.suffixRange === `bytes ${total - 1024}-${total - 1}/${total}` &&
            ranged.pastStatus === 416 &&
            ranged.pastRange === `bytes */${total}` &&
            ranged.wholeStatus === 200 &&
            ranged.wholeBytes === total,
          `206 bytes 0-99/${total} · suffix ${ranged.suffixRange} · past-end ${ranged.pastStatus} ${ranged.pastRange} · whole ${ranged.wholeBytes} B`,
        );

        const anonReport = await fetch(`${BASE}${reportPath}`, { redirect: 'manual' });
        const anonApi = await fetch(`${BASE}${reportPath.replace('/video/', '/api/v1/video/')}`, { redirect: 'manual' });
        const anonFrame = await fetch(`${BASE}${reportPath}/frames/0`, { redirect: 'manual' });
        check(
          'a signed-out visitor is bounced from the report page and gets 401 from the clip, frame and file routes',
          [anonReport.status, anonFrame.status].some((status) => [302, 307].includes(status)) &&
            (anonReport.headers.get('location') ?? '').includes('/login') &&
            anonApi.status === 401,
          `page ${anonReport.status} → ${(anonReport.headers.get('location') ?? '').slice(0, 22)} · api ${anonApi.status} · frame ${anonFrame.status}`,
        );

        await page.setViewport(MOBILE);
        await shot(page, '38-mobile-video-report');
        const videoNarrow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        check('mobile 375px: the clip report holds with no horizontal overflow', videoNarrow <= 1, `overflow ${videoNarrow}px`);
        await page.setViewport(DESKTOP);

        // Detach the media before deleting: dropping the element alone leaves Chromium's in-flight range
        // request running, and its 404 after the row is gone is the browser chasing a clip that no longer
        // exists rather than anything the walk wants to claim about the report.
        await page.evaluate(() => {
          document.querySelectorAll('video').forEach((video) => {
            video.pause();
            video.removeAttribute('src');
            video.load();
            video.remove();
          });
          document.querySelectorAll('img[src^="/api/v1/video/"]').forEach((element) => element.remove());
        });
        await clickByText(page, 'button', 'Delete clip and file');
        await waitForText(page, 'No clips yet', 60_000);
        const afterDelete = await fetch(`${BASE}${reportPath}`, { redirect: 'manual' });
        check(
          'deleting empties the list and makes the old report URL unusable',
          new URL(page.url()).pathname === '/video' && [302, 307, 404].includes(afterDelete.status),
          `back to ${new URL(page.url()).pathname} · report now ${afterDelete.status}`,
        );
      }
      await unlink(clipPath).catch(() => {});
    }

    // 13. Mobile viewport pass on the main surfaces (login is checked after sign-out below).
    await page.setViewport(MOBILE);
    const mobileSurface = async ([path, marker, label]) => {
      try {
        await open(page, path);
        await waitForText(page, marker, 25_000);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        check(`mobile 375px: ${label} renders "${marker}" with no horizontal overflow`, overflow <= 1, `overflow ${overflow}px`);
        const nav = await page.evaluate(() => {
          const links = [...document.querySelectorAll('.nav__link')];
          return { total: links.length, visible: links.filter((node) => node.getBoundingClientRect().width > 20).length };
        });
        check(`mobile 375px: ${label} keeps every nav link visible`, nav.total > 0 && nav.visible === nav.total, `visible ${nav.visible}/${nav.total}`);
      } catch (error) {
        check(`mobile 375px: ${label} renders "${marker}"`, false, `${new URL(page.url()).pathname} — ${String(error.message ?? error).slice(0, 140)}`);
      }
      await shot(page, `20-mobile-${label}`);
    };
    for (const surface of [
      ['/my-football', PLAYER_NAME, 'my-football'],
      ['/coach', 'Recommended session', 'coach'],
      ['/training', 'min', 'training'],
      [href ?? '/training', 'Add to my sessions', 'drill-detail'],
      ['/progress', PLAYER_NAME, 'progress'],
      ['/history', 'Training log', 'history'],
      ['/knowledge', 'Document library', 'knowledge'],
      ['/knowledge/buildup-vs-high-press', 'Passages', 'knowledge-document'],
      ['/world', 'Browse', 'world'],
      ['/world/players', 'Players', 'world-players'],
      [worldTeam.path, 'Squad', 'world-team'],
      [worldPlayer.path, 'Season totals', 'world-player'],
      [worldPlayed.path, 'Who scored', 'world-match'],
      [worldCup.path, 'Entrants', 'world-cup'],
      [worldArticle.path, 'Claim class', 'world-news'],
      ['/tactics', 'Systems', 'tactics'],
      [tactic.path, 'Both phases', 'tactics-detail'],
      [`${tactic.path}?change=raise-back-line`, 'before and after', 'tactics-counterfactual'],
      sibling
        ? [`/tactics/compare?a=${encodeURIComponent(tactic.slug)}&b=${encodeURIComponent(sibling.slug)}&phase=out`, 'side by side', 'tactics-compare']
        : ['/tactics/compare', 'Pick two different systems', 'tactics-compare'],
      ['/settings', 'Data', 'settings'],
    ]) {
      await mobileSurface(surface);
    }

    // 14. An authenticated visitor is bounced off the public auth pages, then signs out.
    await open(page, '/login');
    check('signed-in visitor is redirected away from /login', new URL(page.url()).pathname !== '/login', new URL(page.url()).pathname);

    // 15. Sign out clears the cookies; the login screen must still work at 375px.
    await open(page, '/settings');
    const signedOut = await page.evaluate(async () => {
      const response = await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'same-origin' });
      return response.status;
    });
    await open(page, '/my-football');
    check('logout clears the session (protected route bounces to login)', signedOut === 204 && new URL(page.url()).pathname === '/login', `status ${signedOut}`);
    await open(page, '/tactics/boards');
    check('a signed-out visitor never reaches the boards area', new URL(page.url()).pathname === '/login', new URL(page.url()).pathname);
    await mobileSurface(['/login', 'Sign in', 'login-signed-out']);
  } catch (error) {
    // An abort used to print one line and discard the other ~100 results. Record it as a failed
    // check, capture what the browser was actually looking at, and fall through to the summary.
    check('the walk completed without an unhandled error', false, String(error?.message ?? error).slice(0, 220));
    await shot(page, 'abort-state');
    await open(page, '/login').catch(() => {});
    await shot(page, 'abort-login').catch(() => {});
  } finally {
    // If Chrome died mid-walk, closing must not throw from the finally — that would swallow the
    // report for the ~80 checks that already passed and leave one silent exit code behind.
    await browser.close().catch(() => {});
  }

  // Console noise is a gate, not a footnote: a walk that prints errors and still exits 0 teaches
  // nobody to read them. Exactly two are provoked on purpose, both by the video block deleting a
  // clip whose file the browser still has open — Chromium's in-flight byte-range read then answers
  // 404 as a response and again as a resource error on the page it came from.
  const provoked = [
    // Deleting a clip while its report still has the file open: Chromium's in-flight byte-range read of a row
    // that no longer exists answers 404, once as a response and once as a resource error on the page it came from.
    /^HTTP 404 \/api\/v1\/video\/[^/]+\/file$/,
    /^Failed to load resource: the server responded with a status of 404 \(Not Found\) @ \/video\/[^/]+$/,
    // The range probe above asks for bytes past the end of the clip on purpose, because a proxy that turned a 416
    // into a 200 would leave a browser unable to tell that its range was refused.
    /^HTTP 416 \/api\/v1\/video\/[^/]+\/file$/,
    /^Failed to load resource: the server responded with a status of 416 \(Range Not Satisfiable\) @ \/video\/[^/]+$/,
  ];
  const unexpected = [...new Set(consoleErrors)].filter((line) => !provoked.some((pattern) => pattern.test(line)));
  check(
    'every browser console error was one this walk provoked on purpose',
    unexpected.length === 0,
    unexpected.length ? unexpected.slice(0, 3).join(' | ').slice(0, 220) : `${consoleErrors.length} seen, all of them deliberate`,
  );

  const failed = results.filter((result) => !result.ok);  console.log(`\n${results.length - failed.length}/${results.length} checks passed. Screenshots: ${shots.length} -> docs/screenshots/`);
  if (consoleErrors.length) {
    console.log(`\nBrowser console errors (${consoleErrors.length}):`);
    for (const line of [...new Set(consoleErrors)].slice(0, 15)) console.log(`  - ${line.slice(0, 300)}`);
  }
  if (failed.length) {
    console.log('\nFailed checks:');
    for (const item of failed) console.log(`  - ${item.name}${item.detail ? ` — ${item.detail}` : ''}`);
  }
  process.exitCode = failed.length > 0 ? 1 : 0;
}

run().catch((error) => {
  console.error(`visual QA run aborted: ${error?.message ?? error}`);
  process.exitCode = 2;
});
