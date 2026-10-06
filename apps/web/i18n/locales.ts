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
