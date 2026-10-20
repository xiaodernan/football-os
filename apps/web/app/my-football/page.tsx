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

function DemoMarker({ show, t }: { show: boolean; t: (key: string) => string }) {
  if (!show) return null;
  return (
    <span className="badge badge--demo" title={t("demoDataTitle")}>
      {t("demoDataBadge")}
    </span>
  );
}

export default async function MyFootballPage() {
  const user = await currentUser();
  if (!user) redirect("/login");

  const tn = await getTranslations("nav");
  const td = await getTranslations("myFootball");

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
        <div className="notice notice--warn">{errorMessage(overviewResult.error, td("overviewUnavailable"))}</div>
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
          <DemoMarker show={overview.demo_data} t={td} />
          <span className="chip">{player.goal.replace(/_/g, " ")}</span>
        </div>
      </div>

      {overview.empty_state && (
        <Empty
          title={td("emptyTitle")}
          body={td("emptyBody")}
          href="/training"
          cta={td("emptyCta")}
        />
      )}

      <Panel eyebrow={td("cardEyebrow")} title={td("cardTitle")} className="mp-hero">
        <div className="mp-hero__top">
            <div className="ovr" aria-label={td("ariaOverall", { value: player.overall })}>{player.overall}</div>
          <div className="grow stack-sm">
            <div className="row wrap" style={{ gap: "0.4rem" }}>
              <span className="chip chip--accent">{player.position}</span>
              <span className="chip">{player.archetype}</span>
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {td("archetypeFit", { value: `${Math.round(player.archetype_match * 100)}%` })}
              </span>
            </div>
            <span className="muted" style={{ fontSize: "0.85rem" }}>
              {td("ageFootPotential", {
                age: player.age,
                foot: player.preferred_foot,
                potential: player.potential,
              })}
            </span>
          </div>
        </div>

        <div className="stack-sm" style={{ marginTop: "1.1rem" }}>
          <div className="between" style={{ fontSize: "0.85rem" }}>
            <span className="muted">
              {td("levelXp", { level: overview.xp.level, total: overview.xp.total })}
            </span>
            <span className="mono">{td("pctToNext", { pct: xpPct })}</span>
          </div>
          <div className="bar" role="progressbar" aria-valuenow={xpPct} aria-valuemin={0} aria-valuemax={100}>
            <div className="bar__fill" style={{ width: `${xpPct}%` }} />
          </div>
        </div>

        <div className="grid-3 mp-hero__stats">
          <Stat label={td("statForm")} value={player.form} hint={td("statFormHint")} />
          <Stat
            label={td("statStreak")}
            value={`${overview.training.streak_days} d`}
            hint={
              overview.training.last_session_at
                ? td("statStreakLast", { date: overview.training.last_session_at.slice(0, 10) })
                : td("statStreakNone")
            }
          />
          <Stat
            label={td("statThisWeek")}
            value={overview.training.sessions_this_week}
            hint={td("statThisWeekHint", { count: overview.training.sessions_completed })}
          />
        </div>
      </Panel>

      <Panel
        eyebrow={td("coachEyebrow")}
        title={td("coachTitle")}
        action={
          <Link className="btn btn--primary btn--sm" href="/training">
            {td("addToToday")}
          </Link>
        }
      >
        {todayResult.ok ? (
          <div className="stack">
            <AiBadge demo_mode={todayResult.data.demo_mode} provider={todayResult.data.provider} model={todayResult.data.model} confidence={todayResult.data.confidence} />
            {todayResult.data.message && <p className="lede">{todayResult.data.message}</p>}
            {todayResult.data.recommendation ? (
              <div className="mp-drill">
                <div className="between wrap">
                  <h3 className="h3">{todayResult.data.recommendation.title}</h3>
                  <Link className="btn btn--ghost btn--sm" href={`/training/${todayResult.data.recommendation.slug}`}>
                    {td("openDrill")}
                  </Link>
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
            <ReasonList items={todayResult.data.reasons} title={td("reasonsTitle")} />
            <p className="muted mp-disclaimer">{todayResult.data.disclaimer}</p>
          </div>
        ) : todayResult.status === 401 ? (
          <div className="notice notice--warn">{td("sessionExpired")}</div>
        ) : (
          <div className="notice notice--warn">{errorMessage(todayResult.error, td("recommendationUnavailable"))}</div>
        )}
      </Panel>

      <Panel eyebrow={td("skillEyebrow")} title={td("skillTitle")}>
        {radarValues.length >= 3 ? (
          <div className="mp-skill">
            <div className="mp-skill__radar">
              <AttributeRadar values={radarValues} label={td("radarLabel")} />
            </div>
            <div className="mp-skill__meters">
              <p className="eyebrow">{td("priorityAttributes")}</p>
              <div className="grid-3">
                {weakestThree.map((item) => (
                  <Meter key={item.key} label={shortLabel(item.attr)} value={item.value} max={99} />
                ))}
              </div>
              <p className="muted" style={{ fontSize: "0.82rem" }}>
                {td("weakestNote")}
              </p>
            </div>
          </div>
        ) : (
          <div className="notice notice--warn">{td("notEnoughData")}</div>
        )}
      </Panel>

      <Panel
        eyebrow={td("achievementsEyebrow")}
        title={td("achievementsTitle", { count: overview.achievements.length })}
      >
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
          <p className="muted">{td("noAchievements")}</p>
        )}
      </Panel>
    </div>
  );
}
