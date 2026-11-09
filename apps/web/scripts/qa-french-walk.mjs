/**
 * LTR walk — the production build, fo_locale=fr, six pages, desktop width.
 * French is Latin script and LTR, so this is the LTR counterpart of the Arabic/Hebrew walks:
 * the same assertions under the French cookie — <html dir="ltr">, zero MISSING_MESSAGE,
 * zero console errors, and French glyphs (accented Latin) in the served body text.
 * Writes screenshots to docs/screenshots/ and prints one line per page.
 *
 * Authenticated leg (opt-in, QA_AUTH_WALK=1): signs in through the API as the seeded
 * demo account (defaults are the seeded scratch credentials demo@footballos.local /
 * demo-password-123, against a disposable database) and walks the pages that only exist
 * behind a session — the reader's football home, the simulator, the challenges shelf, the
 * career create form, the career detail and the career's market ledger (the last two
 * only when QA_CAREER_SLUG names a career that the seed left behind, e.g. `walk-manager-braa`).
 * The same assertions hold for every page: dir=ltr, zero MISSING_MESSAGE, zero console
 * errors, and French accented glyphs in the served body.
 */
import { readFileSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

const BASE = process.env.QA_BASE ?? 'http://127.0.0.1:3212';
const API_BASE = process.env.QA_API_INTERNAL_URL ?? 'http://127.0.0.1:8760';
const AUTH_WALK = process.env.QA_AUTH_WALK === '1';
const AUTH_EMAIL = process.env.QA_AUTH_EMAIL ?? 'demo@footballos.local';
const AUTH_PASSWORD = process.env.QA_AUTH_PASSWORD ?? 'demo-password-123';
const CAREER_SLUG = process.env.QA_CAREER_SLUG ?? '';
const CHROME = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const results = [];

const catalogue = (locale) => JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), 'utf8'));
const fr = catalogue('fr');
const en = catalogue('en');
const enLatinNav = [String(en.nav.signIn ?? '').trim(), String(en.nav.world ?? '').trim(), String(en.nav.knowledge ?? '').trim()].filter(Boolean);

// French carries Latin script plus its accented inventory; a French page that never paints one is a
// page the catalogue did not reach (the fr fallback ships zero untranslated non-token keys today).
const FRENCH_ACCENTS = /[ÀÂÄÇÈÉÊËÎÏÔÛÙàâçèéêëîïôûùüœ]/;
const isFrench = (s) => FRENCH_ACCENTS.test(String(s ?? ''));

(async () => {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1440,900'],
    defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 },
  });
  const page = await browser.newPage();
  await page.setCookie({ name: 'fo_locale', value: 'fr', url: BASE });

  const pages = [
    { path: '/', name: 'home', shot: 'french-home.png' },
    { path: '/world', name: 'world', shot: 'french-world.png' },
    { path: '/knowledge', name: 'knowledge', shot: 'french-knowledge.png' },
    { path: '/login', name: 'login', shot: 'french-login.png' },
    { path: '/challenges', name: 'challenges', shot: 'french-challenges.png' },
    { path: '/club/rules', name: 'club rules', shot: 'french-club-rules.png' },
  ];

  const authPages = AUTH_WALK
    ? [
        { path: '/my-football', name: 'authenticated my-football', shot: 'french-my-football.png' },
        { path: '/simulate', name: 'authenticated simulator', shot: 'french-simulate.png' },
        { path: '/challenges', name: 'authenticated challenges', shot: 'french-challenges-authed.png' },
        { path: '/career', name: 'authenticated career create', shot: 'french-career.png' },
        ...(CAREER_SLUG
          ? [
              { path: `/career/${encodeURIComponent(CAREER_SLUG)}`, name: 'authenticated career detail', shot: 'french-career-detail.png' },
              { path: `/career/${encodeURIComponent(CAREER_SLUG)}/market`, name: 'authenticated market ledger', shot: 'french-market.png' },
            ]
          : []),
      ]
    : [];

  for (const { path, name, shot } of [...pages]) {
    const consoleErrors = [];
    page.removeAllListeners('console');
    page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle2', timeout: 90_000 });

    const dir = await page.evaluate(() => document.documentElement.dir);
    const bodyText = await page.evaluate(() => document.body?.innerText ?? '');
    const missing = await page.evaluate(() => (document.body?.innerText ?? '').match(/MISSING_MESSAGE/gi) || []);
    const seenLatin = await page.evaluate((probes) => {
      const text = document.body?.innerText ?? '';
      return probes.filter((p) => p && text.includes(p));
    }, enLatinNav);
    const hasFrench = isFrench(bodyText);
    const file = join(OUT_DIR, `${stamp}-${shot}`);
    await page.screenshot({ path: file, fullPage: true });

    const ok = dir === 'ltr' && missing.length === 0 && hasFrench && consoleErrors.length === 0;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${name} — dir=${dir} · french=${hasFrench} · missingMessage=${missing.length} · consoleErrors=${consoleErrors.length} · shot=${shot}`);
    if (seenLatin.length) console.log(`    english residue: ${JSON.stringify(seenLatin)}`);

    results.push({ name, ok, dir, hasFrench, missing: missing.length, consoleErrors: consoleErrors.length, seenLatin });
  }

  if (AUTH_WALK) {
    const loginRes = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ email: AUTH_EMAIL, password: AUTH_PASSWORD }),
    });
    if (!loginRes.ok) {
      console.log(`AUTH leg setup RED — login for ${AUTH_EMAIL} answered ${loginRes.status}; authenticated pages were not walked`);
      process.exit(results.every((r) => r.ok) ? 2 : 1);
    }
    const { access_token: accessToken } = await loginRes.json();
    await page.setCookie({ name: 'fo_access', value: accessToken, url: BASE });
    console.log('auth: fo_access cookie set from a live API login as the seeded demo account');

    for (const { path, name, shot } of authPages) {
      const consoleErrors = [];
      page.removeAllListeners('console');
      page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
      await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle2', timeout: 90_000 });

      const dir = await page.evaluate(() => document.documentElement.dir);
      const bodyText = await page.evaluate(() => document.body?.innerText ?? '');
      const missing = await page.evaluate(() => (document.body?.innerText ?? '').match(/MISSING_MESSAGE/gi) || []);
      const seenLatin = await page.evaluate((probes) => {
        const text = document.body?.innerText ?? '';
        return probes.filter((p) => p && text.includes(p));
      }, enLatinNav);
      const hasFrench = isFrench(bodyText);
      const file = join(OUT_DIR, `${stamp}-${shot}`);
      await page.screenshot({ path: file, fullPage: true });

      const ok = dir === 'ltr' && missing.length === 0 && hasFrench && consoleErrors.length === 0;
      console.log(`${ok ? 'PASS' : 'FAIL'} ${name} — dir=${dir} · french=${hasFrench} · missingMessage=${missing.length} · consoleErrors=${consoleErrors.length} · shot=${shot}`);
      if (seenLatin.length) console.log(`    english residue: ${JSON.stringify(seenLatin)}`);

      results.push({ name, ok, dir, hasFrench, missing: missing.length, consoleErrors: consoleErrors.length, seenLatin });
    }
  }

  await browser.close();
  const allOk = results.every((r) => r.ok);
  console.log(`\nFRENCH WALK ${allOk ? 'ALL GREEN' : 'REDS PRESENT'} — ${results.filter(r => r.ok).length}/${results.length} pages`);
  process.exit(allOk ? 0 : 1);
})();
