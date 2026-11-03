/**
 * The locales, in a module a client component can import.
 *
 * These three lines used to live in `i18n/request.ts`, which also calls `getRequestConfig` from `next-intl/server`
 * and imports all three catalogues. A client component that wanted the list would have dragged the server
 * configuration and every bundle into the browser with it, which is why the list lives here and `request.ts`
 * re-exports it rather than owning it.
 */
export const locales = ["en", "zh", "zh-TW"] as const;
export const defaultLocale = "en" as const;

export type Locale = (typeof locales)[number];

/**
 * The scripts written right-to-left. None of them is a shipped locale yet, and that is the point: the
 * layout is prepared now, so adding `ar` to `locales` cannot silently render a right-to-left language
 * left-to-right. The base language is what decides, because a region subtag does not change direction
 * (`ar-EG`, `fa-IR`, `he-IL`); `az-Arab` and `pa-Arab` are the one shape where the script subtag matters,
 * and they are not offered. `textDirection` is read by the root layout's `<html dir>` and by
 * `qa-rtl-readiness.mjs`, which also refuses a physical CSS property that would not follow it.
 */
const RTL_BASE_LANGUAGES = new Set(["ar", "dv", "fa", "he", "ku", "ps", "sd", "ug", "ur", "yi"]);

export function textDirection(locale: string): "ltr" | "rtl" {
  return RTL_BASE_LANGUAGES.has(locale.toLowerCase().split("-")[0]) ? "rtl" : "ltr";
}
