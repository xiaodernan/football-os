import type { Metadata, Viewport } from "next";

import { Nav } from "@/components/Nav";
import { SITE_NAME, absolute, siteOrigin } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { CapabilitiesResponse } from "@/lib/types";
import "../styles/globals.css";

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
  const [user, capabilities] = await Promise.all([
    currentUser().catch(() => null),
    serverFetch<CapabilitiesResponse>("/capabilities").then((result) => (result.ok ? result.data : null)),
  ]);
  const demoMode = capabilities?.demo_mode ?? true;

  return (
    <html lang="en">
      <body>
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
              inLanguage: "en",
              publisher: { "@type": "Organization", name: SITE_NAME, url: absolute("/") },
            }),
          }}
        />
        <footer className="container" style={{ padding: "2rem 0 3rem", borderTop: "1px solid var(--line-soft)" }}>
          <div className="between wrap" style={{ gap: "0.75rem" }}>
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              FOOTBALL OS — every figure is synthetic, project-authored or entered by you. No club, league or player
              imagery is licensed here.
            </span>
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              AI output is an estimate, not a performance, medical or scouting certification.
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
