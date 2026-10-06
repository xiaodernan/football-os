"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * The control that was missing from the whole chain.
 *
 * `middleware.ts` has read a `fo_locale` cookie since the i18n plumbing landed, and nothing in the application
 * ever wrote one — so the cookie was a mechanism with no way to reach it, and the only signal a reader had was
 * whatever their browser happened to send as `Accept-Language`. A preference nobody can set is not a preference.
 *
 * The names are written in their own language, which is the one piece of text here that is deliberately *not*
 * translated: a reader who has landed in a language they cannot read needs to find their own in the list, and
 * "Chinese" written in English is no help to them. That is why they are literals rather than catalogue keys.
 */
const NAMES: Record<string, string> = {
  en: "English",
  zh: "简体中文",
  "zh-TW": "繁體中文",
};

export function LocaleSwitcher({ locales }: { locales: string[] }) {
  const active = useLocale();
  const t = useTranslations("common");
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  function choose(next: string) {
    if (next === active) return;
    setBusy(true);
    // A year, path-wide, and readable by the client — the same shape the middleware expects to find, and the
    // only cookie in this app that is not httpOnly, because it carries no authority.
    document.cookie = `fo_locale=${encodeURIComponent(next)}; path=/; max-age=${365 * 86400}; samesite=lax`;
    router.refresh();
    setBusy(false);
  }

  return (
    <select
      aria-label={t("language")}
      className="nav__locale"
      disabled={busy}
      onChange={(event) => choose(event.target.value)}
      value={active}
    >
      {locales.map((locale) => (
        <option key={locale} value={locale}>
          {NAMES[locale] ?? locale}
        </option>
      ))}
    </select>
  );
}
