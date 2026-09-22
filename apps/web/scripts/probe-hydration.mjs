// Throwaway diagnostic: print React's readable hydration diff for one route (dev server).
import puppeteer from 'puppeteer-core';

const url = process.env.PROBE_URL ?? 'http://127.0.0.1:3210/tactics/4-3-3-press-high';
const browser = await puppeteer.launch({
  headless: 'new',
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage();
const lines = [];
page.on('console', (message) => lines.push(`[${message.type()}] ${message.text()}`));
page.on('pageerror', (error) => lines.push(`[pageerror] ${String(error)}`));
await page.goto(url, { waitUntil: 'networkidle2', timeout: 180_000 });
await new Promise((done) => setTimeout(done, 2500));
await browser.close();
const interesting = lines.filter((line) => /hydrat|did not match|cannot be|error/i.test(line));
console.log(`--- ${url}\n${interesting.length ? interesting.join('\n\n').slice(0, 6000) : lines.join('\n').slice(0, 3000)}`);
