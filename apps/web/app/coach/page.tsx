import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AiBadge, DrillMeta, Panel, ReasonList, Stat } from "@/components/ui";
import { CoachAsk } from "@/app/coach/CoachAsk";
import { PlanBuilder } from "@/app/coach/PlanBuilder";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { CoachHistory, TodayRecommendation } from "@/lib/types";

import "./coach.css";

export const dynamic = "force-dynamic";

// `generateMetadata` rather than a constant, so the tab title is read from the same catalogue as the page and a
// reader who chose Chinese does not keep the one string that never moves. Same shape as the auth pages.
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("coach");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

/** The backend stores recent_categories as a {category: count} map; older/mock shapes use a string array. */
function categoryEntries(raw: string[] | Record<string, number>): [string, number][] {
  if (Array.isArray(raw)) return raw.map((name) => [name, 1]);
  return Object.entries(raw ?? {})
    .map(([name, count]) => [name, Number(count) || 0] as [string, number])
    .sort((a, b) => b[1] - a[1]);
}

function label(value: string): string {
  return value.replace(/_/g, " ");
}

const SECTIONS = [
  { id: "today", key: "tabToday" },
  { id: "ask", key: "tabAsk" },
  { id: "plan", key: "tabPlan" },
  { id: "memory", key: "tabMemory" },
] as const;

export default async function CoachPage() {
  const t = await getTranslations("coach");
  const user = await currentUser();
  if (!user) redirect("/login");

  const [todayResult, historyResult] = await Promise.all([
    serverFetch<TodayRecommendation>("/coach/today", { query: { available_minutes: 25, has_pitch: "true" } }),
    serverFetch<CoachHistory>("/coach/history"),
  ]);

  const notice = (status: number, message: string) => (
    <div className="notice notice--warn">
      {status === 401 ? t("sessionExpired") : ""}
      {message}
    </div>
  );

  return (
    <div className="container page stack">
      <div>
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1 className="h1">{t("title")}</h1>
        <p className="lede">{t("lede")}</p>
      </div>

      <nav className="coach-tabs" aria-label={t("sectionsLabel")}>
        {SECTIONS.map((section) => (
          <a className="coach-tabs__link" href={`#${section.id}`} key={section.id}>
            {t(section.key)}
          </a>
        ))}
      </nav>

      <section id="today" className="stack">
        <Panel eyebrow={t("tabToday")} title={t("todayTitle")}>
          {todayResult.ok ? (
            <div className="stack">
              <AiBadge
                demo_mode={todayResult.data.demo_mode}
                provider={todayResult.data.provider}
                model={todayResult.data.model}
                confidence={todayResult.data.confidence}
              />
              {todayResult.data.message && <p className="lede">{todayResult.data.message}</p>}

              {todayResult.data.recommendation && (
                <div className="coach-rec">
                  <div className="between wrap">
                    <h3 className="h3">{todayResult.data.recommendation.title}</h3>
                    <Link className="btn btn--primary btn--sm" href={`/training/${todayResult.data.recommendation.slug}`}>
                      {t("openAndAdd")}
                    </Link>
                  </div>
                  <p className="muted">{todayResult.data.recommendation.objective}</p>
                  <DrillMeta drill={todayResult.data.recommendation} />
                </div>
              )}

              {todayResult.data.focus_attributes && todayResult.data.focus_attributes.length > 0 && (
                <div className="tag-list">
                  {todayResult.data.focus_attributes.map((focus) => (
                    <span className="chip chip--accent" key={focus}>
                      {label(focus)}
                    </span>
                  ))}
                </div>
              )}

              <ReasonList items={todayResult.data.reasons} title={t("whyChosen")} />

              {todayResult.data.alternatives && todayResult.data.alternatives.length > 0 && (
                <div className="stack-sm">
                  <p className="eyebrow">{t("alternatives")}</p>
                  <div className="grid-2">
                    {todayResult.data.alternatives.map((alt) => (
                      <Link className="coach-alt" href={`/training/${alt.slug}`} key={alt.slug}>
                        <span className="h3">{alt.title}</span>
                        <span className="muted coach-alt__meta">
                          {label(alt.category)} · {alt.duration_min} min
                        </span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              <p className="muted coach-disclaimer">{todayResult.data.disclaimer}</p>
            </div>
          ) : todayResult.status === 409 && todayResult.error.code === "no_player" ? (
            redirect("/onboarding")
          ) : (
            notice(todayResult.status, errorMessage(todayResult.error, t("todayUnavailable")))
          )}
        </Panel>
      </section>

      <section id="ask" className="stack">
        <Panel eyebrow={t("tabAsk")} title={t("askTitle")}>
          <CoachAsk />
        </Panel>
      </section>

      <section id="plan" className="stack">
        <Panel eyebrow={t("tabPlan")} title={t("planTitle")}>
          <PlanBuilder />
        </Panel>
      </section>

      <section id="memory" className="stack">
        <Panel eyebrow={t("tabMemory")} title={t("memoryTitle")}>
          {historyResult.ok ? (
            <div className="stack">
              {historyResult.data.disclaimer && <p className="muted coach-disclaimer">{historyResult.data.disclaimer}</p>}
              <div className="grid-4 coach-memory">
                <Stat label={t("statSessions")} value={historyResult.data.memory.sessions_total} hint={t("statSessionsHint")} />
                <Stat label={t("statXp")} value={historyResult.data.memory.xp_total} />
                <Stat label={t("statLevel")} value={historyResult.data.memory.level} />
                <Stat label={t("statTurns")} value={historyResult.data.items.length} hint={t("statTurnsHint")} />
              </div>

              <div className="stack-sm">
                <p className="eyebrow">{t("recentCategories")}</p>
                {(() => {
                  const entries = categoryEntries(historyResult.data.memory.recent_categories as unknown as string[]);
                  return entries.length > 0 ? (
                    <div className="tag-list">
                      {entries.map(([name, count]) => (
                        <span className="chip" key={name}>
                          {label(name)}
                          {count > 1 ? ` ×${count}` : ""}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="muted">{t("noRecentSessions")}</p>
                  );
                })()}
              </div>

              <div className="stack-sm">
                <p className="eyebrow">{t("attributeTrend")}</p>
                {historyResult.data.memory.attribute_trend.length > 0 ? (
                  <ul className="list coach-trend">
                    {historyResult.data.memory.attribute_trend.map((row, index) => (
                      <li className="list__item" key={`${row.attribute}-${index}`}>
                        <span className="chip">{label(row.attribute)}</span>
                        <span className="muted grow">{row.reason}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">{t("noAttributeChanges")}</p>
                )}
              </div>
            </div>
          ) : historyResult.status === 409 && historyResult.error.code === "no_player" ? (
            redirect("/onboarding")
          ) : (
            notice(historyResult.status, errorMessage(historyResult.error, t("memoryUnavailable")))
          )}
        </Panel>
      </section>
    </div>
  );
}
