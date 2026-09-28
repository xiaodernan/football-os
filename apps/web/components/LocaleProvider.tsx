"use client";

import { NextIntlClientProvider } from "next-intl";
import type { Locale } from "@/i18n/request";

interface LocaleProviderProps {
  children: React.ReactNode;
  locale: Locale;
  messages: Record<string, unknown>;
}

export function LocaleProvider({ children, locale, messages }: LocaleProviderProps) {
  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}