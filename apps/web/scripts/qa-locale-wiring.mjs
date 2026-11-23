#!/usr/bin/env node
/*
 * Locale wiring gate: the five shipped catalogues must be wired everywhere a locale is named.
 *
 * Arabic shipped 2026-11-08 with `ar` absent from `components/LocaleSwitcher.tsx`'s NAMES map, so
 * the one control that promises a reader "pick your language" showed the raw tag `ar` while every
 * gate on the tree was green. Every gate that verifies catalogue content (parity, ICU, tokens,
 * script) held; every gate that verifies layout direction held; nothing anywhere read the *wiring*
 * — the list, the switcher's names, the proxy's map, the two message bundles. This gate is that
 * reader, and every check names the file it reads.
 *
 * Files only: no server, no browser, no port. The root is the web tier; `QA_WIRING_WEB` overrides
 * it so the witness can run the same checks over a scratch plane.
 */

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve, basename } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_WIRING_WEB ?? fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const read = (rel) => {
  try {
    return readFileSync(join(WEB, rel), "utf8");
  } catch {
    return null;
  }
};

/* The shipped population is the catalogue directory, not a list — the same discovery every other
 * catalogue gate uses. A `fr.json` that landed unwired would charge this gate by filename. */
const onDisk = existsSync(MESSAGES)
  ? readdirSync(MESSAGES).filter((file) => file.endsWith(".json")).map((file) => file.slice(0, -5)).sort()
  : [];

const localesFile = read("i18n/locales.ts");
const requestFile = read("i18n/request.ts");
const middlewareFile = read("middleware.ts");
const layoutFile = read("app/layout.tsx");
const switcherFile = read("components/LocaleSwitcher.tsx");
const readmeFile = read("messages/README.md");
const claimsTest = read("../api/tests/test_locale_claims.py");

/* 1 — the locales list names exactly the catalogues on disk. */
const localesMatch = localesFile && /export const locales\s*=\s*\[([^\]]*)\]/.exec(localesFile);
const listed = localesMatch
  ? [...localesMatch[1].matchAll(/"([A-Za-z-]+)"/g)].map((m) => m[1]).sort()
  : [];
check(
  "the shipped locales list is exactly the catalogue directory",
  localesMatch && onDisk.length > 0 && JSON.stringify(listed) === JSON.stringify(onDisk),
  localesMatch
    ? `locales.ts names [${listed.join(", ")}]; messages/ holds [${onDisk.join(", ")}]`
    : "no `export const locales = [...]` found in i18n/locales.ts",
);

/* The RTL classification of the shipped catalogues is qa-rtl-readiness's check 4 (it calls the shipped
 * `textDirection` helper); this gate deliberately owns none of it — a second assertion of the same fact
 * would red two files for one defect and let both go stale in lockstep. */

/* 2 — the middleware's Accept-Language base branches cover every shipped locale's base, and the
 *     zh-TW subtag rule is present (a `zh` tag with -tw/-hk/-mo must answer Traditional). */
const middlewareText = middlewareFile ?? "";
const missingBranches = onDisk.filter((locale) => {
  const base = locale.toLowerCase().split("-")[0];
  return !new RegExp(`base === "${base}"`).test(middlewareText);
});
const zhTwRule = /base === "zh"\s*\)\s*return\s*\/-\(tw\|hk\|mo\)/.test(middlewareText);
check(
  "middleware has an Accept-Language branch for every shipped locale's base script",
  missingBranches.length === 0 && (onDisk.includes("zh-TW") ? zhTwRule : true),
  missingBranches.length === 0 && (onDisk.includes("zh-TW") ? zhTwRule : true)
    ? `branches cover [${onDisk.join(", ")}]${onDisk.includes("zh-TW") ? " (zh-TW subtag rule present)" : ""}`
    : missingBranches.length
      ? `no branch for base(s): ${missingBranches.join(", ")}`
      : "the zh → zh-TW script-subtag rule is missing",
);

/* 2 — the cookie name the middleware writes is the one request.ts reads. A rename on one side
 *     without the other serves English to everyone who switched — silently. */
const cookieInMiddleware = /fo_locale/.test(middlewareText);
const cookieInRequest = requestFile !== null && /fo_locale/.test(requestFile);
check(
  "the locale cookie name is the same in the middleware and the request config",
  cookieInMiddleware && cookieInRequest,
  cookieInMiddleware && cookieInRequest
    ? "fo_locale on both sides"
    : [!cookieInMiddleware ? "middleware never names fo_locale" : null, !cookieInRequest ? "request.ts never names fo_locale" : null].filter(Boolean).join("; "),
);

/* 2 — the message bundle in request.ts carries every catalogue on disk. A locale missing from the
 *     map does not error loudly: `messagesMap[locale]` is undefined and every page throws. */
const bundleMatch = requestFile && /messagesMap\s*=\s*{([^}]*)}/.exec(requestFile);
const keyOf = (locale) => (locale === "en" ? /\ben\s*:/ : new RegExp(`['"]?${locale}['"]?\\s*:`));
const missingInRequest = onDisk.filter((locale) => {
  if (!bundleMatch) return true;
  return !keyOf(locale).test(bundleMatch[1]);
});
check(
  "i18n/request.ts maps every shipped catalogue in its messagesMap",
  bundleMatch && missingInRequest.length === 0,
  bundleMatch
    ? missingInRequest.length === 0
      ? `all ${onDisk.length} bundle(s) wired`
      : `missing from messagesMap: ${missingInRequest.join(", ")}`
    : "no messagesMap literal found in i18n/request.ts",
);

/* 2 — the message bundle in the root layout carries every catalogue too (same silent-500 class). */
const layoutBundleMatch = layoutFile && /messagesMap\s*=\s*{([^}]*)}/.exec(layoutFile);
const missingInLayout = onDisk.filter((locale) => {
  if (!layoutBundleMatch) return true;
  return !keyOf(locale).test(layoutBundleMatch[1]);
});
check(
  "app/layout.tsx maps every shipped catalogue in its messagesMap",
  layoutBundleMatch && missingInLayout.length === 0,
  layoutBundleMatch
    ? missingInLayout.length === 0
      ? `all ${onDisk.length} bundle(s) wired`
      : `missing from messagesMap: ${missingInLayout.join(", ")}`
    : "no messagesMap literal found in app/layout.tsx",
);

/* 2 — the language switcher names every shipped locale in its own language. This is the check
 *     the Arabic milestone escaped without a red anywhere: the catalogue was complete, the walk
 *     was green, and the one control that offers the language showed the raw tag. */
const switcherNamesMatch = switcherFile && /NAMES[^{]*{([^}]*)}/.exec(switcherFile);
const missingInSwitcher = onDisk.filter((locale) => {
  if (!switcherNamesMatch) return true;
  const key = new RegExp(`['"]?${locale}['"]?\\s*:`);
  return !key.test(switcherNamesMatch[1]);
});
check(
  "LocaleSwitcher's NAMES renders every shipped locale in its own language",
  switcherNamesMatch && missingInSwitcher.length === 0,
  switcherNamesMatch
    ? missingInSwitcher.length === 0
      ? `all ${onDisk.length} locale(s) named`
      : `missing from NAMES: ${missingInSwitcher.join(", ")}`
    : "no NAMES literal found in components/LocaleSwitcher.tsx",
);

/* 2 — every shipped locale keeps a README table row (the figure test reads it; a missing row is
 *     a red there, but this gate names it here too, as wiring). */
const missingReadmeRow = onDisk.filter((locale) => !new RegExp(`\\|\\s*\`?${locale}\\.json\`?\\s*\\|`).test(readmeFile ?? ""));
check(
  "messages/README.md carries a table row for every shipped locale",
  missingReadmeRow.length === 0,
  missingReadmeRow.length === 0
    ? `rows for [${onDisk.join(", ")}]`
    : `no README row for: ${missingReadmeRow.join(", ")}`,
);

/* 2 — README_FLOORS names every shipped locale (the pin the API-side test holds to). */
const floorsMatch = claimsTest && /README_FLOORS[^=]*=\s*{([^}]*)}/.exec(claimsTest);
const missingFloor = onDisk.filter((locale) => {
  if (locale === "en") return false; // the fallback needs no floor of its own
  if (!floorsMatch) return true;
  return !new RegExp(`['"]?${locale}['"]?\\s*:`).test(floorsMatch[1]);
});
check(
  "apps/api/tests/test_locale_claims.py README_FLOORS pins every shipped non-fallback locale",
  floorsMatch && missingFloor.length === 0,
  floorsMatch
    ? missingFloor.length === 0
      ? `floors pin [${onDisk.filter((l) => l !== "en").join(", ")}]`
      : `missing from README_FLOORS: ${missingFloor.join(", ")}`
    : "no README_FLOORS dict found in the locale claims test",
);

const failed = checks.filter((row) => !row.ok);
console.log(`\nCHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (failed.length) process.exitCode = 1;
