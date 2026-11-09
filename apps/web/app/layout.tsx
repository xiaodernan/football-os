import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { getTranslations } from "next-intl/server";
import { Nav } from "@/components/Nav";
import { LocaleProvider } from "@/components/LocaleProvider";
import { SITE_DESCRIPTION, SITE_NAME, SITE_TAGLINE, absolute, ogImages, siteOrigin } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { CapabilitiesResponse } from "@/lib/types";
import { locales, defaultLocale } from "@/i18n/request";
import { textDirection } from "@/i18n/locales";
import enMessages from "@/messages/en.json";
import zhMessages from "@/messages/zh.json";
import zhTWMessages from "@/messages/zh-TW.json";
import arMessages from "@/messages/ar.json";
import heMessages from "@/messages/he.json";
import frMessages from "@/messages/fr.json";
import "../styles/globals.css";

const messagesMap = {
  en: enMessages,
  zh: zhMessages,
  'zh-TW': zhTWMessages,
  ar: arMessages,
  he: heMessages,
  fr: frMessages,
} as const;

export const dynamic = "force-dynamic";

/** `og:locale` values for the six shipped catalogues, in OpenGraph's own `language_TERRITORY` form. */
const OG_LOCALE: Record<string, string> = {
  en: "en_US",
  zh: "zh_CN",
  "zh-TW": "zh_TW",
  ar: "ar_SA",
  he: "he_IL",
  fr: "fr_FR",
};

export async function generateMetadata(): Promise<Metadata> {
  const headersList = await headers();
  const localeHeader = headersList.get("x-next-intl-locale") ?? headersList.get("next-intl-locale");
  const locale = (locales as readonly string[]).includes(localeHeader ?? "")
    ? (localeHeader as typeof locales[number])
    : defaultLocale;
  const self = OG_LOCALE[locale];
  return {
    metadataBase: new URL(siteOrigin()),
    title: { default: SITE_NAME, template: `%s · ${SITE_NAME}` },
    description: SITE_DESCRIPTION,
    applicationName: SITE_NAME,
    openGraph: {
      siteName: SITE_NAME,
      type: "website",
      title: SITE_NAME,
      description: SITE_DESCRIPTION,
      images: ogImages(),
      locale: self,
      alternateLocale: Object.values(OG_LOCALE).filter((value) => value !== self),
    },
  };
}

export const viewport: Viewport = {
  themeColor: "#06090f",
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const headersList = await headers();
  const localeHeader = headersList.get("x-next-intl-locale") ?? headersList.get("next-intl-locale");
  const locale = (locales as readonly string[]).includes(localeHeader ?? "") ? (localeHeader as typeof locales[number]) : defaultLocale;

  const [user, capabilities, t, tNav] = await Promise.all([
    currentUser().catch(() => null),
    serverFetch<CapabilitiesResponse>("/capabilities").then((result) => (result.ok ? result.data : null)),
    getTranslations("disclaimer"),
    getTranslations("nav"),
  ]);
  const messages = messagesMap[locale];
  const demoMode = capabilities?.demo_mode ?? true;

  return (
    <html lang={locale} dir={textDirection(locale)}>
      <body>
        <LocaleProvider locale={locale} messages={messages}>
          {/* The nav is 11–18 links deep, so a keyboard reader who lands on the page would tab through every one of
              them on every page. The skip link is the first focusable thing in the document and moves the reader to
              `<main id="main">`, which carries `tabIndex={-1}` so the target can take focus at all. */}
          <a className="skip-link" href="#main">
            {tNav("skipToContent")}
          </a>
          <Nav user={user} demoMode={demoMode} />
          <main id="main" tabIndex={-1}>
            {children}
          </main>
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify({
                "@context": "https://schema.org",
                "@type": "WebSite",
                name: SITE_NAME,
                url: absolute("/"),
                description: SITE_TAGLINE,
                inLanguage: locale,
                publisher: { "@type": "Organization", name: SITE_NAME, url: absolute("/") },
              }),
            }}
          />
          <footer className="container" style={{ padding: "2rem 0 3rem", borderTop: "1px solid var(--line-soft)" }}>
            <div className="between wrap" style={{ gap: "0.75rem" }}>
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {t("demoData")}
              </span>
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {t("aiEstimate")}
              </span>
            </div>
          </footer>
        </LocaleProvider>
      </body>
    </html>
  );
}