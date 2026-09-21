import type { Metadata, Viewport } from "next";

import { Nav } from "@/components/Nav";
import { currentUser, serverFetch } from "@/lib/server";
import type { UserOut } from "@/lib/types";
import "../styles/globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "FOOTBALL OS", template: "%s · FOOTBALL OS" },
  description: "Watch. Understand. Train. Play. Manage. Become. — a football operating system for fans, players and coaches.",
};

export const viewport: Viewport = {
  themeColor: "#06090f",
  width: "device-width",
  initialScale: 1,
};

type Capabilities = {
  demo_mode: boolean;
  m1_player_ai_coach: boolean;
  m3_football_world: boolean;
  m4_tactical_lab: boolean;
  m6_simulation: boolean;
  m7_scouting: boolean;
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [user, capabilities] = await Promise.all([
    currentUser().catch(() => null),
    serverFetch<Capabilities>("/capabilities").then((result) => (result.ok ? result.data : null)),
  ]);
  const demoMode = capabilities?.demo_mode ?? true;

  return (
    <html lang="en">
      <body>
        <Nav user={user as UserOut | null} demoMode={demoMode} />
        <main>{children}</main>
        <footer className="container" style={{ padding: "2rem 0 3rem", borderTop: "1px solid var(--line-soft)" }}>
          <div className="between wrap" style={{ gap: "0.75rem" }}>
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              FOOTBALL OS — synthetic demo data only. No club, league or player imagery is licensed here.
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
