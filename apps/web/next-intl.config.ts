/**
 * Tooling defaults for the next-intl plugin (message extraction, editor support).
 *
 * `localePrefix: "never"` is a fact about this app, not a preference: its pages live at `/world`, `/creator`
 * and so on, with no `[locale]` segment to match a prefixed URL. The middleware therefore decides the locale
 * from a cookie and `Accept-Language` and never rewrites a path (`apps/web/middleware.ts`).
 */
const config = {
  locales: ["en", "zh", "zh-TW"],
  defaultLocale: "en",
  localePrefix: "never",
};

export default config;
