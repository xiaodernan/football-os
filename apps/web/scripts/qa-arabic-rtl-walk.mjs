/**
 * RTL walk — the production build, fo_locale=ar, six pages, desktop width.
 * Writes screenshots to docs/screenshots/ and prints one line per page:
 *   html@dir=... (rtl expected) · <arabic spot-check> · <named catalogues> · no MISSING_MESSAGE.
 *
 * Authenticated leg (opt-in, QA_AUTH_WALK=1): signs in through the API as the seeded
 * demo account (defaults are the seeded scratch credentials demo@footballos.local /
 * demo-password-123, against a disposable database) and walks the pages that only exist
 * behind a session — the reader's football home, the simulator, the challenges shelf, the
 * career create form, the career detail and the career's market ledger (the last two
 * only when QA_CAREER_SLUG names a career that the seed left behind, e.g. `walk-manager-braa`).
 * The same assertions hold for every page: dir=rtl, zero MISSING_MESSAGE, zero console
 * errors, and Arabic script in the served body.
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
const ar = catalogue('ar');
const en = catalogue('en');
const enLatinNav = [String(en.nav.signIn ?? '').trim(), String(en.nav.world ?? '').trim(), String(en.nav.knowledge ?? '').trim()].filter(Boolean);

const isArabic = (s) => /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/.test(String(s ?? ''));

(async () => {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1440,900'],
    defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 },
  });
  const page = await browser.newPage();
  await page.setCookie({ name: 'fo_locale', value: 'ar', url: BASE });

  const pages = [
    { path: '/', name: 'home', shot: 'arabic-home.png' },
    { path: '/world', name: 'world', shot: 'arabic-world.png' },
    { path: '/knowledge', name: 'knowledge', shot: 'arabic-knowledge.png' },
    { path: '/login', name: 'login', shot: 'arabic-login.png' },
    { path: '/challenges', name: 'challenges', shot: 'arabic-challenges.png' },
    { path: '/club/rules', name: 'club rules', shot: 'arabic-club-rules.png' },
    { path: '/leaderboard', name: 'leaderboard', shot: 'arabic-leaderboard.png' },
  ];

  const authPages = AUTH_WALK
    ? [
        { path: '/my-football', name: 'authenticated my-football', shot: 'arabic-my-football.png' },
        { path: '/simulate', name: 'authenticated simulator', shot: 'arabic-simulate.png' },
        { path: '/challenges', name: 'authenticated challenges', shot: 'arabic-challenges-authed.png' },
        { path: '/leaderboard', name: 'authenticated leaderboard', shot: 'arabic-leaderboard-authed.png' },
        { path: '/career', name: 'authenticated career create', shot: 'arabic-career.png' },
        ...(CAREER_SLUG
          ? [
              { path: `/career/${encodeURIComponent(CAREER_SLUG)}`, name: 'authenticated career detail', shot: 'arabic-career-detail.png' },
              { path: `/career/${encodeURIComponent(CAREER_SLUG)}/market`, name: 'authenticated market ledger', shot: 'arabic-market.png' },
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
    const hasArabic = isArabic(bodyText);
    const file = join(OUT_DIR, `${stamp}-${shot}`);
    await page.screenshot({ path: file, fullPage: true, captureBeyondViewport: false });

    const ok = dir === 'rtl' && missing.length === 0 && hasArabic && consoleErrors.length === 0;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${name} — dir=${dir} · arabic=${hasArabic} · missingMessage=${missing.length} · consoleErrors=${consoleErrors.length} · shot=${shot}`);
    if (seenLatin.length) console.log(`    latin-language residue: ${JSON.stringify(seenLatin)}`);

    results.push({ name, ok, dir, hasArabic, missing: missing.length, consoleErrors: consoleErrors.length, seenLatin });
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
      const hasArabic = isArabic(bodyText);
      const file = join(OUT_DIR, `${stamp}-${shot}`);
      await page.screenshot({ path: file, fullPage: true, captureBeyondViewport: false });

      const ok = dir === 'rtl' && missing.length === 0 && hasArabic && consoleErrors.length === 0;
      console.log(`${ok ? 'PASS' : 'FAIL'} ${name} — dir=${dir} · arabic=${hasArabic} · missingMessage=${missing.length} · consoleErrors=${consoleErrors.length} · shot=${shot}`);
      if (seenLatin.length) console.log(`    latin-language residue: ${JSON.stringify(seenLatin)}`);

      results.push({ name, ok, dir, hasArabic, missing: missing.length, consoleErrors: consoleErrors.length, seenLatin });
    }
  }

  await browser.close();
  const allOk = results.every((r) => r.ok);
  console.log(`\nRTL WALK ${allOk ? 'ALL GREEN' : 'REDS PRESENT'} — ${results.filter(r => r.ok).length}/${results.length} pages`);
  process.exit(allOk ? 0 : 1);
})();
