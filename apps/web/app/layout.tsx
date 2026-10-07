import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { getTranslations } from "next-intl/server";
import { Nav } from "@/components/Nav";
import { LocaleProvider } from "@/components/LocaleProvider";
import { SITE_NAME, absolute, siteOrigin } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { CapabilitiesResponse } from "@/lib/types";
import { locales, defaultLocale } from "@/i18n/request";
import enMessages from "@/messages/en.json";
import zhMessages from "@/messages/zh.json";
import zhTWMessages from "@/messages/zh-TW.json";
import "../styles/globals.css";

const messagesMap = {
  en: enMessages,
  zh: zhMessages,
  'zh-TW': zhTWMessages,
} as const;

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  metadataBase: new URL(siteOrigin()),
  title: { default: "FOOTBALL OS", template: "%s · FOOTBALL OS" },
  description: "Watch. Understand. Train. Play. Manage. Become. — a football operating system for fans, players and coaches.",
  applicationName: SITE_NAME,
  openGraph: {
    siteName: SITE_NAME,
    type: "website",
    title: SITE_NAME,
    description: "Watch. Understand. Train. Play. Manage. Become. — a football operating system for fans, players and coaches.",
  },
};

export const viewport: Viewport = {
  themeColor: "#06090f",
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const headersList = await headers();
  const localeHeader = headersList.get("x-next-intl-locale") ?? headersList.get("next-intl-locale");
  const locale = (locales as readonly string[]).includes(localeHeader ?? "") ? (localeHeader as typeof locales[number]) : defaultLocale;

  const [user, capabilities, t] = await Promise.all([
    currentUser().catch(() => null),
    serverFetch<CapabilitiesResponse>("/capabilities").then((result) => (result.ok ? result.data : null)),
    getTranslations("disclaimer"),
  ]);
  const messages = messagesMap[locale];
  const demoMode = capabilities?.demo_mode ?? true;

  return (
    <html lang={locale}>
      <body>
        <LocaleProvider locale={locale} messages={messages}>
          <Nav user={user} demoMode={demoMode} />
          <main>{children}</main>
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify({
                "@context": "https://schema.org",
                "@type": "WebSite",
                name: SITE_NAME,
                url: absolute("/"),
                description: "Watch. Understand. Train. Play. Manage. Become.",
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