import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Empty, Panel, Stat } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { CapabilitiesResponse, Player, ProgressOverview } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Watch. Understand. Train. Play. Manage. Become.",
  description:
    "FOOTBALL OS is a football operating system for fans, players and coaches. Today the AI player-coach vertical slice works end to end; the live football-world modules are still being built.",
};

export default async function HomePage() {
  const user = await currentUser();
  const capabilitiesResult = await serverFetch<CapabilitiesResponse>("/capabilities");
  const capabilities = capabilitiesResult.ok ? capabilitiesResult.data : null;

  let players: Player[] | null = null;
  let overview: ProgressOverview | null = null;
  let myFootballNotice: string | null = null;

  if (user) {
    const [playersResult, overviewResult] = await Promise.all([
      serverFetch<Player[]>("/players"),
      serverFetch<ProgressOverview>("/progress/overview"),
    ]);

    if (overviewResult.ok) {
      overview = overviewResult.data;
      players = playersResult.ok ? playersResult.data : null;
    } else if (overviewResult.status === 409 && overviewResult.error.code === "no_player") {
      redirect("/onboarding");
    } else if (overviewResult.status === 401) {
      redirect("/login");
    } else {
      myFootballNotice = errorMessage(overviewResult.error, "Progress is unavailable right now.");
    }
  }

  return (
    <div className="container page">
      {/* Hero */}
      <section className="pitch-backdrop" style={{ padding: "clamp(2rem, 5vw, 3.5rem)" }}>
        <div className="stack" style={{ gap: "1.1rem" }}>
          <span className="eyebrow">FOOTBALL OS</span>
          <h1 className="h1" style={{ textTransform: "uppercase", lineHeight: 1.1 }}>
            Watch. Understand. Train.
            <br />
            Play. Manage. Become.
          </h1>
          <p className="lede">
            One system for the whole football journey — follow the game, learn it, train against an
            explainable AI coach, and watch a player profile grow from real sessions.
          </p>
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            {user ? (
              <Link className="btn btn--primary" href="/my-football">
                Go to My Football
              </Link>
            ) : (
              <Link className="btn btn--primary" href="/register">
                Create your account
              </Link>
            )}
            <Link className="btn btn--ghost" href="/training">
              Explore training
            </Link>
          </div>
        </div>
      </section>

      {/* Modules: three honest 'not built' columns + a real My Football column */}
      <section className="section grid grid-2">
        <NotBuiltPanel
          title="Live now"
          eyebrow="Matchday"
          body="Live scores are not shown because no match feed is licensed yet. This module ships with M3 Football World."
        />
        <NotBuiltPanel
          title="Football world"
          eyebrow="M3 · Roadmap"
          body={
            capabilities
              ? `Football World ships with M3 (module status: ${capabilities.m3_football_world ? "on" : "not built"}). No fixtures, tables or transfers are displayed because no data source is connected.`
              : "Football World ships with M3. No fixtures or transfers are shown — the capabilities endpoint is currently unreachable."
          }
        />
        <NotBuiltPanel
          title="News"
          eyebrow="M3 · Roadmap"
          body="No news headlines are rendered because no provider is licensed. When it lands, every item will carry its source."
        />

        <Panel title="My football" eyebrow="M1 · Available today">
          {!user ? (
            <Empty
              title="Sign in to see your football"
              body="Your OVR, streak and completed sessions appear here once you have an account and a player profile."
              href="/login"
              cta="Sign in"
            />
          ) : myFootballNotice ? (
            <div className="notice notice--warn">{myFootballNotice}</div>
          ) : overview && !overview.empty_state ? (
            <div className="stack">
              <div className="player-card" style={{ padding: 0 }}>
                <span className="ovr">{overview.player.overall}</span>
                <div className="stack-sm grow">
                  <strong>{overview.player.name}</strong>
                  <span className="muted" style={{ fontSize: "0.85rem" }}>
                    {overview.player.position} · {overview.player.archetype}
                    {players?.[0]?.is_demo_data ? " · demo data" : ""}
                  </span>
                </div>
              </div>
              <div className="grid grid-3">
                <Stat label="OVR" value={<span className="num">{overview.player.overall}</span>} hint={`potential ${overview.player.potential}`} />
                <Stat label="Streak" value={<span className="num">{overview.training.streak_days}</span>} hint="days" />
                <Stat label="Sessions" value={<span className="num">{overview.training.sessions_completed}</span>} hint="completed" />
              </div>
              <Link className="btn btn--sm" href="/my-football">
                Open My Football
              </Link>
            </div>
          ) : (
            <Empty
              title="No player yet"
              body="Create your football identity to start earning XP and growing attributes."
              href="/onboarding"
              cta="Set up my player"
            />
          )}
        </Panel>
      </section>

      {/* What works today */}
      <section className="section">
        <p className="eyebrow">Available now</p>
        <h2 className="h2">What works today</h2>
        <p className="lede" style={{ marginTop: "0.5rem" }}>
          The M1 player &amp; AI-coach vertical slice runs end to end. Everything below uses real
          requests against the backend — nothing here is faked.
        </p>
        <div className="grid grid-2 section">
          <FeaturePanel
            title="Training academy"
            body="A library of drills with setup, instructions, coaching points, common mistakes and progressions."
            href="/training"
            cta="Browse drills"
          />
          <FeaturePanel
            title="Explainable AI coach"
            body="Ask for a recommendation and get the chosen drill plus the reasons behind it — every answer is labelled demo vs live."
            href="/coach"
            cta="Talk to the coach"
          />
          <FeaturePanel
            title="XP & attribute progression"
            body="Completing sessions awards XP and nudges the attributes a drill targets, so your OVR is earned, not invented."
            href="/progress"
            cta="See progress"
          />
          <FeaturePanel
            title="Own your data"
            body="Export your sessions and attributes, or delete everything you have stored, straight from settings."
            href="/settings"
            cta="Manage data"
          />
        </div>
      </section>

      {/* How we treat data */}
      <section className="section">
        <p className="eyebrow">Policy</p>
        <h2 className="h2">How we treat data</h2>
        <div className="grid grid-3 section">
          <Panel title="Synthetic demo only">
            <p className="muted">
              Player profiles, attributes and content in this build are synthetic demo data. They
              are not real athletes and are labelled as demo wherever they appear.
            </p>
          </Panel>
          <Panel title="No licensed assets">
            <p className="muted">
              No club, league, player imagery or broadcast assets are used or claimed. Anything that
              would need a licence simply is not shown yet.
            </p>
          </Panel>
          <Panel title="AI is an estimate">
            <p className="muted">
              Coach and AI output is an estimate produced by a labelled engine, not a performance,
              medical or scouting certification. Reasons and confidence always travel with it.
            </p>
          </Panel>
        </div>
      </section>
    </div>
  );
}

function NotBuiltPanel({ title, eyebrow, body }: { title: string; eyebrow: string; body: string }) {
  return (
    <Panel
      title={title}
      eyebrow={eyebrow}
      action={
        <span className="badge badge--demo" title="This module is on the roadmap and not implemented yet.">
          NOT BUILT
        </span>
      }
    >
      <Empty title="Not built yet" body={body} />
    </Panel>
  );
}

function FeaturePanel({ title, body, href, cta }: { title: string; body: string; href: string; cta: string }) {
  return (
    <Panel
      title={title}
      footer={
        <Link className="btn btn--sm btn--ghost" href={href}>
          {cta}
        </Link>
      }
    >
      <p className="muted">{body}</p>
    </Panel>
  );
}
