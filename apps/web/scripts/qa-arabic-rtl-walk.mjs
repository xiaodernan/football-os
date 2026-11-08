/**
 * RTL walk — the production build, fo_locale=ar, four pages, desktop width.
 * Writes screenshots to docs/screenshots/ and prints one line per page:
 *   html@dir=... (rtl expected) · <arabic spot-check> · <named catalogues> · no MISSING_MESSAGE.
 */
import { readFileSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

const BASE = process.env.QA_BASE ?? 'http://127.0.0.1:3212';
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
  ];

  for (const { path, name, shot } of pages) {
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
    await page.screenshot({ path: file, fullPage: true });

    const ok = dir === 'rtl' && missing.length === 0 && hasArabic && consoleErrors.length === 0;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${name} — dir=${dir} · arabic=${hasArabic} · missingMessage=${missing.length} · consoleErrors=${consoleErrors.length} · shot=${shot}`);
    if (seenLatin.length) console.log(`    latin-language residue: ${JSON.stringify(seenLatin)}`);

    results.push({ name, ok, dir, hasArabic, missing: missing.length, consoleErrors: consoleErrors.length, seenLatin });
  }

  await browser.close();
  const allOk = results.every((r) => r.ok);
  console.log(`\nRTL WALK ${allOk ? 'ALL GREEN' : 'REDS PRESENT'} — ${results.filter(r => r.ok).length}/${results.length} pages`);
  process.exit(allOk ? 0 : 1);
})();
