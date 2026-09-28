import { createNavigation } from 'next-intl/navigation';

export const routing = {
  locales: ['en', 'zh', 'zh-TW'] as const,
  defaultLocale: 'en' as const,
  localePrefix: 'as-needed' as const,
};

export type Locale = (typeof routing.locales)[number];

export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing);