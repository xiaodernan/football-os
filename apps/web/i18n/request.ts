import { notFound } from 'next/navigation';
import { getRequestConfig } from 'next-intl/server';

export const locales = ['en', 'zh', 'zh-TW'] as const;
export const defaultLocale = 'en' as const;

export type Locale = (typeof locales)[number];

import enMessages from '@/messages/en.json';
import zhMessages from '@/messages/zh.json';
import zhTWMessages from '@/messages/zh-TW.json';

const messagesMap = {
  en: enMessages,
  zh: zhMessages,
  'zh-TW': zhTWMessages,
} as const;

export default getRequestConfig(async ({ locale }) => {
  if (!locales.includes(locale as Locale)) notFound();
  return {
    locale: locale as string,
    messages: messagesMap[locale as Locale],
  };
});