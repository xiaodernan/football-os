import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AttributeRadar } from "@/components/AttributeRadar";
import { AiBadge, DrillMeta, Empty, Meter, Panel, ReasonList, Stat } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { ProgressOverview, TodayRecommendation } from "@/lib/types";

import "./my-football.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const tn = await getTranslations("nav");
  const td = await getTranslations("myFootball");
  return {
    title: tn("myFootball"),
    description: td("metaDescription"),
  };
}

/** Turns a snake_case attribute key into a short radar label without inventing data. */
function shortLabel(key: string): string {
  const words = key.split("_");
  return words.map((word) => (word.length <= 3 ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1))).join(" ");
}

function DemoMarker({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <span className="badge badge--demo" title="Synthetic demo data — not measured from a real match or club.">
      DEMO DATA
    </span>
  );
}

export default async function MyFootballPage() {
  const user = await currentUser();
  if (!user) redirect("/login");

  const tn = await getTranslations("nav");

  const [overviewResult, todayResult] = await Promise.all([
    serverFetch<ProgressOverview>("/progress/overview"),
    serverFetch<TodayRecommendation>("/coach/today", { query: { available_minutes: 25, has_pitch: "true" } }),
  ]);

  if (!overviewResult.ok) {
    if (overviewResult.status === 401) redirect("/login");
    if (overviewResult.status === 409 && overviewResult.error.code === "no_player") redirect("/onboarding");
    return (
      <div className="container page stack">
        <h1 className="h1">{tn("myFootball")}</h1>
        <div className="notice notice--warn">{errorMessage(overviewResult.error, "We could not load your overview right now.")}</div>
      </div>
    );
  }

  const overview = overviewResult.data;
  const player = overview.player;

  const flattened = Object.entries(overview.attribute_groups).flatMap(([group, attrs]) =>
    Object.entries(attrs).map(([key, value]) => ({ key: `${group}:${key}`, attr: key, value, group })),
  );
  const ascending = [...flattened].sort((a, b) => a.value - b.value);
  const radarValues = ascending.slice(0, 6).map((item) => ({ key: item.key, label: shortLabel(item.attr), value: item.value }));
  const weakestThree = ascending.slice(0, 3);

  const xpPct = Math.round(Math.max(0, Math.min(1, overview.xp.progress_in_level)) * 100);

  return (
    <div className="container page stack">
      <div className="between wrap" style={{ gap: "0.6rem" }}>
        <div>
          <p className="eyebrow">{tn("myFootball")}</p>
          <h1 className="h1">{player.name}</h1>
        </div>
        <div className="row wrap" style={{ gap: "0.5rem" }}>
          <DemoMarker show={overview.demo_data} />
          <span className="chip">{player.goal.replace(/_/g, " ")}</span>
        </div>
      </div>

      {overview.empty_state && (
        <Empty
          title="No sessions logged yet"
          body="Add your first training session and this page will fill in with your real progress."
          href="/training"
          cta="Browse the training academy"
        />
      )}

      <Panel eyebrow="Player card" title="Overall profile" className="mp-hero">
        <div className="mp-hero__top">
          <div className="ovr" aria-label={`Overall ${player.overall}`}>{player.overall}</div>
          <div className="grow stack-sm">
            <div className="row wrap" style={{ gap: "0.4rem" }}>
              <span className="chip chip--accent">{player.position}</span>
              <span className="chip">{player.archetype}</span>
              <span className="muted" style={{ fontSize: "0.82rem" }}>archetype fit {Math.round(player.archetype_match * 100)}%</span>
            </div>
            <span className="muted" style={{ fontSize: "0.85rem" }}>
              Age {player.age} · {player.preferred_foot} foot · potential {player.potential}
            </span>
          </div>
        </div>

        <div className="stack-sm" style={{ marginTop: "1.1rem" }}>
          <div className="between" style={{ fontSize: "0.85rem" }}>
            <span className="muted">Level {overview.xp.level} · {overview.xp.total} XP total</span>
            <span className="mono">{xpPct}% to next level</span>
          </div>
          <div className="bar" role="progressbar" aria-valuenow={xpPct} aria-valuemin={0} aria-valuemax={100}>
            <div className="bar__fill" style={{ width: `${xpPct}%` }} />
          </div>
        </div>

        <div className="grid-3 mp-hero__stats">
          <Stat label="Form" value={player.form} hint="Tracked from completed sessions" />
          <Stat label="Streak" value={`${overview.training.streak_days} d`} hint={overview.training.last_session_at ? `Last: ${overview.training.last_session_at.slice(0, 10)}` : "No sessions yet"} />
          <Stat label="This week" value={overview.training.sessions_this_week} hint={`${overview.training.sessions_completed} completed in total`} />
        </div>
      </Panel>

      <Panel eyebrow="Coach message" title="Recommended for today" action={<Link className="btn btn--primary btn--sm" href="/training">Add to today</Link>}>
        {todayResult.ok ? (
          <div className="stack">
            <AiBadge demo_mode={todayResult.data.demo_mode} provider={todayResult.data.provider} model={todayResult.data.model} confidence={todayResult.data.confidence} />
            {todayResult.data.message && <p className="lede">{todayResult.data.message}</p>}
            {todayResult.data.recommendation ? (
              <div className="mp-drill">
                <div className="between wrap">
                  <h3 className="h3">{todayResult.data.recommendation.title}</h3>
                  <Link className="btn btn--ghost btn--sm" href={`/training/${todayResult.data.recommendation.slug}`}>Open drill</Link>
                </div>
                <p className="muted">{todayResult.data.recommendation.objective}</p>
                <DrillMeta drill={todayResult.data.recommendation} />
              </div>
            ) : null}
            {todayResult.data.focus_attributes && todayResult.data.focus_attributes.length > 0 && (
              <div className="tag-list">
                {todayResult.data.focus_attributes.map((focus) => (
                  <span className="chip" key={focus}>{shortLabel(focus)}</span>
                ))}
              </div>
            )}
            <ReasonList items={todayResult.data.reasons} title="Why this was chosen" />
            <p className="muted mp-disclaimer">{todayResult.data.disclaimer}</p>
          </div>
        ) : todayResult.status === 401 ? (
          <div className="notice notice--warn">Your session expired. Sign in again to see the coach message.</div>
        ) : (
          <div className="notice notice--warn">{errorMessage(todayResult.error, "The coach recommendation is unavailable right now.")}</div>
        )}
      </Panel>

      <Panel eyebrow="Skill progress" title="Attribute profile">
        {radarValues.length >= 3 ? (
          <div className="mp-skill">
            <div className="mp-skill__radar">
              <AttributeRadar values={radarValues} label="Six weakest attributes from your profile" />
            </div>
            <div className="mp-skill__meters">
              <p className="eyebrow">Priority attributes</p>
              <div className="grid-3">
                {weakestThree.map((item) => (
                  <Meter key={item.key} label={shortLabel(item.attr)} value={item.value} max={99} />
                ))}
              </div>
              <p className="muted" style={{ fontSize: "0.82rem" }}>
                These are your three lowest-rated attributes from the stored profile. Ratings come from your onboarding estimate and completed-session deltas.
              </p>
            </div>
          </div>
        ) : (
          <div className="notice notice--warn">Not enough attribute data is stored yet to draw the profile.</div>
        )}
      </Panel>

      <Panel eyebrow="Achievements" title={`${overview.achievements.length} earned`}>
        {overview.achievements.length > 0 ? (
          <div className="grid-3">
            {overview.achievements.map((achievement) => (
              <div className="mp-achievement" key={achievement.slug}>
                <span className="badge badge--live">{achievement.awarded_at.slice(0, 10)}</span>
                <span className="h3">{achievement.title}</span>
                <span className="muted" style={{ fontSize: "0.85rem" }}>{achievement.description}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">No achievements earned yet — complete a training session to unlock your first one.</p>
        )}
      </Panel>
    </div>
  );
}
