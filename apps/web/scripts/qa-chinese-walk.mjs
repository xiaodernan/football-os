/**
 * LTR walk — the production build, Simplified or Traditional Chinese, six public pages.
 * Simplified (zh) and Traditional (zh-TW) are written as separate authored catalogues, not
 * conversions of one another, so both deserve their own walk. The assertions mirror the
 * French walk: <html dir="ltr">, zero MISSING_MESSAGE, zero console errors, and CJK glyphs
 * in the served body text — a Chinese page that paints none of them is a page the catalogue
 * never reached.
 * Writes screenshots to docs/screenshots/ and prints one line per page.
 *
 * Locale is chosen with QA_ZH_LOCALE (default zh; zh-TW for Traditional).
 *
 * Authenticated leg (opt-in, QA_AUTH_WALK=1): signs in through the API as the seeded
 * demo account (defaults demo@footballos.local / demo-password-123, against a disposable
 * database) and walks the pages that only exist behind a session — same assertions:
 * dir=ltr, zero MISSING_MESSAGE, zero console errors, Chinese glyphs in the body.
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
const LOCALE = process.env.QA_ZH_LOCALE ?? 'zh';
const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 12);
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
const results = [];

if (!['zh', 'zh-TW'].includes(LOCALE)) {
  console.error(`QA_ZH_LOCALE must be zh or zh-TW, got ${LOCALE}`);
  process.exit(2);
}

const catalogue = (locale) => JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), 'utf8'));
const own = catalogue(LOCALE);
const en = catalogue('en');
const enLatinNav = [String(en.nav.signIn ?? '').trim(), String(en.nav.world ?? '').trim(), String(en.nav.knowledge ?? '').trim()].filter(Boolean);

// CJK unified ideographs are the script floor for both Chinese catalogues.
const CJK = /[\u4e00-\u9fff\u3400-\u4dbf]/;
const hasChineseGlyphs = (s) => CJK.test(String(s ?? ''));

(async () => {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1440,900'],
    defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 },
  });
  const page = await browser.newPage();
  await page.setCookie({ name: 'fo_locale', value: LOCALE, url: BASE });

  const prefix = LOCALE === 'zh-TW' ? 'chinese-tw' : 'chinese';
  const pages = [
    { path: '/', name: 'home', shot: `${prefix}-home.png` },
    { path: '/world', name: 'world', shot: `${prefix}-world.png` },
    { path: '/knowledge', name: 'knowledge', shot: `${prefix}-knowledge.png` },
    { path: '/login', name: 'login', shot: `${prefix}-login.png` },
    { path: '/challenges', name: 'challenges', shot: `${prefix}-challenges.png` },
    { path: '/club/rules', name: 'club rules', shot: `${prefix}-club-rules.png` },
    { path: '/leaderboard', name: 'leaderboard', shot: `${prefix}-leaderboard.png` },
  ];

  const authPages = AUTH_WALK
    ? [
        { path: '/my-football', name: 'authenticated my-football', shot: `${prefix}-my-football.png` },
        { path: '/simulate', name: 'authenticated simulator', shot: `${prefix}-simulate.png` },
        { path: '/challenges', name: 'authenticated challenges', shot: `${prefix}-challenges-authed.png` },
        { path: '/leaderboard', name: 'authenticated leaderboard', shot: `${prefix}-leaderboard-authed.png` },
        { path: '/career', name: 'authenticated career create', shot: `${prefix}-career.png` },
        ...(CAREER_SLUG
          ? [
              { path: `/career/${encodeURIComponent(CAREER_SLUG)}`, name: 'authenticated career detail', shot: `${prefix}-career-detail.png` },
              { path: `/career/${encodeURIComponent(CAREER_SLUG)}/market`, name: 'authenticated market ledger', shot: `${prefix}-market.png` },
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
    const hasChinese = hasChineseGlyphs(bodyText);
    const file = join(OUT_DIR, `${stamp}-${shot}`);
    await page.screenshot({ path: file, fullPage: true, captureBeyondViewport: false });

    const ok = dir === 'ltr' && missing.length === 0 && hasChinese && consoleErrors.length === 0;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${name} — dir=${dir} · chinese=${hasChinese} · missingMessage=${missing.length} · consoleErrors=${consoleErrors.length} · shot=${shot}`);
    if (seenLatin.length) console.log(`    english residue: ${JSON.stringify(seenLatin)}`);

    results.push({ name, ok, dir, hasChinese, missing: missing.length, consoleErrors: consoleErrors.length, seenLatin });
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
      const hasChinese = hasChineseGlyphs(bodyText);
      const file = join(OUT_DIR, `${stamp}-${shot}`);
      await page.screenshot({ path: file, fullPage: true, captureBeyondViewport: false });

      const ok = dir === 'ltr' && missing.length === 0 && hasChinese && consoleErrors.length === 0;
      console.log(`${ok ? 'PASS' : 'FAIL'} ${name} — dir=${dir} · chinese=${hasChinese} · missingMessage=${missing.length} · consoleErrors=${consoleErrors.length} · shot=${shot}`);
      if (seenLatin.length) console.log(`    english residue: ${JSON.stringify(seenLatin)}`);

      results.push({ name, ok, dir, hasChinese, missing: missing.length, consoleErrors: consoleErrors.length, seenLatin });
    }
  }

  await browser.close();
  const allOk = results.every((r) => r.ok);
  console.log(`\n${LOCALE === 'zh-TW' ? 'TRADITIONAL CHINESE' : 'SIMPLIFIED CHINESE'} WALK ${allOk ? 'ALL GREEN' : 'REDS PRESENT'} — ${results.filter(r => r.ok).length}/${results.length} pages`);
  process.exit(allOk ? 0 : 1);
})();
