/**
 * End-to-end visual + functional QA walk for the M1 loop (spec PRINCIPLE 3, §88).
 *
 * Drives the real browser stack — middleware redirect, cookie proxy, server components and
 * client forms — against a running dev server, then writes screenshots at desktop and
 * 375px widths into docs/screenshots/ and prints an assertion report.
 *
 *   web tier: http://127.0.0.1:3210   api tier: http://127.0.0.1:8731   (scripts/dev.sh)
 *   node scripts/visual-qa.mjs
 *
 * Env overrides: QA_BASE, CHROME_PATH.
 */

import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
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
  await page.screenshot({ path: resolve(OUT_DIR, file), fullPage: true });
  shots.push(file);
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

async function clickByText(page, selector, text) {
  const handle = await page.evaluateHandle(
    (css, needle) =>
      [...document.querySelectorAll(css)].find((node) => node.textContent?.includes(needle)) ?? null,
    selector,
    text,
  );
  const element = handle.asElement();
  if (!element) throw new Error(`No ${selector} containing "${text}"`);
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
  });
  const page = await browser.newPage();
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
    check(
      'sitemap advertises only routes that answer 200 (no redirect chains)',
      locs.length > 0 &&
        (await Promise.all(locs.map(async (url) => (await fetch(url)).status))).every((status) => status === 200),
      locs.length > 0 ? `${locs.length} URLs probed` : 'no URLs',
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
    await mobileSurface(['/login', 'Sign in', 'login-signed-out']);
  } finally {
    await browser.close();
  }

  const failed = results.filter((result) => !result.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed. Screenshots: ${shots.length} -> docs/screenshots/`);
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
