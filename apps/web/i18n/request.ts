import { getRequestConfig } from "next-intl/server";

import { defaultLocale, locales, type Locale } from "@/i18n/locales";

// Re-exported so the existing importers (`middleware.ts`, the layout) keep working: the list itself now lives in
// a module with no server-only imports, because the language switcher is a client component and needs it.
export { defaultLocale, locales };
export type { Locale };

import enMessages from "@/messages/en.json";
import zhMessages from "@/messages/zh.json";
import zhTWMessages from "@/messages/zh-TW.json";

const messagesMap = {
  en: enMessages,
  zh: zhMessages,
  "zh-TW": zhTWMessages,
} as const;

/**
 * The message bundle for the locale `middleware.ts` decided from the `fo_locale` cookie and the caller's
 * `Accept-Language`. This file was the *routing* half of next-intl until 2026-09-28, when its sibling
 * `i18n/navigation.ts` fed a middleware that rewrote every path to `/{locale}/…` and 404'd the whole site.
 * A locale this file does not carry now falls back to English instead of `notFound()`: a lookup table is not
 * a route guard, and an unknown language must not take a page down with it.
 */
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = (await requestLocale) ?? defaultLocale;
  const locale = (locales as readonly string[]).includes(requested) ? (requested as Locale) : defaultLocale;
  return {
    locale,
    messages: messagesMap[locale],
  };
});
