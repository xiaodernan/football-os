#!/usr/bin/env node
/*
§109 — renders the share card the metadata promises, from bytes the repository already owns.

`lib/site.ts` declared `twitter.card = "summary_large_image"` for every page and there was no image anywhere to
point at; `docs/SEO_VERIFICATION.md` §3 recorded the reason honestly ("no licensed or project-authored image
asset"), and a `no-image` exclusion is still a card that previews as text. This file closes the exclusion by
authoring the asset instead of copying one: the wordmark and the tagline are read out of `lib/site.ts` through the
repo's own TypeScript, the mark is the committed `app/icon.svg`, and the palette is the `:root` block of
`globals.css`. Nothing here carries a copy of any of those, so a rebrand moves the card by moving the source — and
`apps/web/scripts/qa-share-preview.mjs` refuses a generator that starts carrying its own strings, a PNG whose IHDR
disagrees with the size the metadata declares, or a card URL that no file answers.

Run it from anywhere; it resolves its own repo. Chrome is the same knob the browser walks use (`CHROME_PATH`).

  node scripts/make_og_image.mjs            # writes apps/web/public/og.png, prints the reading it verified
*/

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join, resolve } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const REPO = resolve(fileURLToPath(new URL("..", import.meta.url)));
const WEB = join(REPO, "apps", "web");
// The repo's own TypeScript and puppeteer-core both live in the web tier's manifest.
const require = createRequire(join(WEB, "package.json"));
const ts = require("typescript");
const puppeteer = require("puppeteer-core");

const CHROME = process.env.CHROME_PATH ?? "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const SITE_TS = join(WEB, "lib", "site.ts");
const ICON = join(WEB, "app", "icon.svg");
const CSS = join(WEB, "styles", "globals.css");
const OUT = join(WEB, "public", "og.png");

const refuse = (m) => {
  throw new Error(`make_og_image: ${m}`);
};

/**
 * Evaluate the shipped module rather than reading words out of it. `import type { Metadata }` is erased by the
 * transpile step, so the file evaluates with nothing to resolve — and the values below are the same objects the
 * pages import, not a second spelling of them.
 */
const site = (() => {
  const compiled = ts.transpileModule(readFileSync(SITE_TS, "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
  }).outputText;
  return new Function("exports", `${compiled}\nreturn exports;`)({});
})();

const { SITE_NAME, SITE_TAGLINE, OG_IMAGE_PATH, OG_IMAGE_WIDTH, OG_IMAGE_HEIGHT } = site;
for (const [name, value] of Object.entries({ SITE_NAME, SITE_TAGLINE, OG_IMAGE_PATH, OG_IMAGE_WIDTH, OG_IMAGE_HEIGHT })) {
  if (value === undefined) refuse(`lib/site.ts exported no ${name} — the card and the metadata would drift on day one`);
}
if (!(OG_IMAGE_WIDTH > 0 && OG_IMAGE_HEIGHT > 0)) refuse(`declared card size is not positive: ${OG_IMAGE_WIDTH}x${OG_IMAGE_HEIGHT}`);

/** The palette, read from the `:root` block the app styles from, so the card cannot be a second owner of a colour. */
const tokens = (() => {
  const css = readFileSync(CSS, "utf8");
  const root = css.slice(css.indexOf(":root {"), css.indexOf("}", css.indexOf(":root {")));
  const out = {};
  for (const m of root.matchAll(/--([\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  for (const need of ["bg", "bg-panel", "accent", "info", "text", "text-2", "font"]) {
    if (!out[need]) refuse(`globals.css :root has no --${need}; the card would have to invent a colour`);
  }
  return out;
})();

/** The palette's own colour with an alpha, so the glow is a token at a strength rather than a number typed twice. */
const rgbaOf = (hex, alpha) => {
  const h = hex.trim();
  if (!/^#[0-9a-f]{6}$/i.test(h)) refuse(`cannot take an alpha from ${JSON.stringify(h)}: the card expects a 6-digit hex token`);
  return `rgba(${[1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)).join(", ")}, ${alpha})`;
};

const mark = readFileSync(ICON, "utf8");
if (!/^<svg/.test(mark.trim())) refuse(`${ICON} is not an inline-able SVG`);

/** The card's own margin. Text is measured against it rather than against the canvas edge: a sentence that
 * reaches the pixel border is a sentence that has already left the design. */
const PAD = 96;

const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><style>
  html, body { margin: 0; padding: 0; width: ${OG_IMAGE_WIDTH}px; height: ${OG_IMAGE_HEIGHT}px; overflow: hidden; }
  body {
    background:
      radial-gradient(${OG_IMAGE_WIDTH * 0.8}px ${OG_IMAGE_HEIGHT * 0.5}px at 82% -14%, ${rgbaOf(tokens.accent, 0.14)}, transparent 62%),
      radial-gradient(${OG_IMAGE_WIDTH * 0.7}px ${OG_IMAGE_HEIGHT * 0.45}px at 6% 6%, ${rgbaOf(tokens.info, 0.09)}, transparent 62%),
      ${tokens.bg};
    color: ${tokens.text};
    font-family: ${tokens.font};
    display: flex; align-items: center;
  }
  .frame { display: flex; align-items: center; gap: 56px; padding: 0 ${PAD}px; width: 100%; }
  .mark { width: 200px; height: 200px; flex: none; }
  .copy { display: flex; flex-direction: column; gap: 22px; min-width: 0; }
  .name { font-size: 88px; font-weight: 700; letter-spacing: -2px; line-height: 1; white-space: nowrap; }
  .rule { width: 132px; height: 5px; background: ${tokens.accent}; border-radius: 3px; }
  .lede { font-size: 32px; line-height: 1.3; color: ${tokens["text-2"]}; font-weight: 500; white-space: nowrap; }
  .panel { position: absolute; left: 0; right: 0; bottom: 0; height: 12px; background: ${tokens["bg-panel"]}; }
</style></head>
<body>
  <div class="frame">
    <div class="mark">${mark}</div>
    <div class="copy">
      <div class="name">${SITE_NAME}</div>
      <div class="rule"></div>
      <div class="lede">${SITE_TAGLINE}</div>
    </div>
  </div>
  <div class="panel"></div>
</body></html>`;

const pngSizeOf = (file) => {
  const bytes = readFileSync(file);
  if (bytes.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") refuse(`${file} is not a PNG`);
  // IHDR is the first chunk: 8-byte signature, 4-byte length, "IHDR", then big-endian width and height.
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20), bytes: bytes.length };
};

if (!existsSync(CHROME)) refuse(`no Chrome at ${CHROME} — set CHROME_PATH, the same knob the browser walks use`);

const browser = await puppeteer.launch({
  headless: true,
  executablePath: CHROME,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--force-device-scale-factor=1", "--hide-scrollbars", "--lang=en-US"],
});
let layout = [];
try {
  const page = await browser.newPage();
  await page.setViewport({ width: OG_IMAGE_WIDTH, height: OG_IMAGE_HEIGHT, deviceScaleFactor: 1 });
  await page.setContent(html, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  // `nowrap` can cut a sentence off, and a cropped card looks fine in a file listing. Measure the laid-out boxes
  // against the card's content edge and refuse, so the copy is proven present rather than assumed to fit.
  layout = await page.evaluate(() => [...document.querySelectorAll(".mark, .name, .rule, .lede")]
    .map((el) => { const r = el.getBoundingClientRect(); return { cls: el.className, right: Math.round(r.right), bottom: Math.round(r.bottom) }; }));
  for (const b of layout) {
    if (b.right > OG_IMAGE_WIDTH - PAD || b.bottom > OG_IMAGE_HEIGHT - PAD) {
      refuse(`${b.cls} lays out to right=${b.right} bottom=${b.bottom}, past the content edge `
        + `(${OG_IMAGE_WIDTH - PAD}x${OG_IMAGE_HEIGHT - PAD}) of the ${OG_IMAGE_WIDTH}x${OG_IMAGE_HEIGHT} card`);
    }
  }
  mkdirSync(join(OUT, ".."), { recursive: true });
  await page.screenshot({ path: OUT, clip: { x: 0, y: 0, width: OG_IMAGE_WIDTH, height: OG_IMAGE_HEIGHT } });
} finally {
  await browser.close();
}

const measured = pngSizeOf(OUT);
if (measured.width !== OG_IMAGE_WIDTH || measured.height !== OG_IMAGE_HEIGHT) {
  refuse(`wrote ${measured.width}x${measured.height} but the metadata declares ${OG_IMAGE_WIDTH}x${OG_IMAGE_HEIGHT}`);
}
const sha = createHash("sha256").update(readFileSync(OUT)).digest("hex").slice(0, 16);
console.log(`wrote ${OUT}`);
console.log(`  ${measured.width}x${measured.height} (declared ${OG_IMAGE_WIDTH}x${OG_IMAGE_HEIGHT}) `
  + `bytes=${measured.bytes} sha256=${sha} url=${OG_IMAGE_PATH}`);
console.log(`  laid out ${layout.map((b) => `${b.cls}@${b.right},${b.bottom}`).join(" ")}`);
