import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AttributeRadar } from "@/components/AttributeRadar";
import { AiBadge, DataUnavailable, Empty, Meter, Panel, Stat } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { serverFetch } from "@/lib/server";

import "./progress.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("progress");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

type SearchParams = Record<string, string | string[] | undefined>;

/**
 * Shapes of `GET /progress/overview` and `GET /progress/timeline`, declared for this route.
 * `lib/types.ts` is being rewritten by concurrent work, so the page keeps its own mirror of
 * the wire contract instead of importing a name that may not exist this second.
 */
type Overview = {
  player: {
    id: string;
    name: string;
    position: string;
    age: number;
    goal: string;
    overall: number;
    potential: number;
    form: number;
    archetype: string;
    archetype_match: number;
    preferred_foot: string;
  };
  attributes: Record<string, number>;
  attribute_groups: Record<string, Record<string, number>>;
  xp: { total: number; level: number; next_level_at: number; progress_in_level: number };
  training: {
    sessions_completed: number;
    sessions_this_week: number;
    streak_days: number;
    last_session_at: string | null;
  };
  achievements: { slug: string; title: string; description: string; awarded_at: string }[];
  empty_state: boolean;
  demo_data: boolean;
};

type Timeline = {
  sessions: { date: string; status: string; xp: number | null; execution: number | null; drill: string; category: string }[];
  attribute_series: Record<string, { at: string; after: number; delta: number; reason: string }[]>;
  xp_events: { at: string; amount: number; reason: string; formula: string }[];
  level_estimate: number;
  demo_data: boolean;
};

/** Group order shown on the page; unknown groups from the API still render, after these. */
const GROUP_KEYS: Record<string, string> = {
  technical: "groupTechnical",
  physical: "groupPhysical",
  mental: "groupMental",
  tactical: "groupTactical",
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function attributeLabel(key: string): string {
  return key.split("_").join(" ");
}

function formatDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const stamp = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(stamp.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(stamp);
}

function signed(delta: number): string {
  return delta > 0 ? `+${delta}` : `${delta}`;
}

function clampDays(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? "", 10);
  if (Number.isNaN(parsed)) return 30;
  return Math.max(7, Math.min(180, parsed));
}

export default async function ProgressPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const t = await getTranslations("progress");
  const params = await searchParams;
  const playerId = first(params.player_id);
  const days = clampDays(first(params.days));

  const overviewResult = await serverFetch<Overview>("/progress/overview", { query: { player_id: playerId } });
  if (!overviewResult.ok) {
    if (overviewResult.status === 401) redirect("/login");
    if (overviewResult.status === 409 && overviewResult.error.code === "no_player") redirect("/onboarding");
    return (
      <div className="page container">
        <div className="stack">
          <h1 className="h1">{t("metaTitle")}</h1>
          <div className="notice notice--warn">
            {errorMessage(overviewResult.error, t("unavailable"))}
          </div>
        </div>
      </div>
    );
  }
  const overview = overviewResult.data;

  // The timeline is a second, independent read: if it fails the panels that need it
  // fall back to <DataUnavailable /> rather than showing invented history.
  const timelineResult = await serverFetch<Timeline>("/progress/timeline", {
    query: { player_id: overview.player.id || playerId, days },
  });
  const timeline = timelineResult.ok ? timelineResult.data : null;

  const attributeEntries = Object.entries(overview.attributes ?? {});
  const radarValues = [...attributeEntries]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 6)
    .map(([key, value]) => ({ key, label: attributeLabel(key), value }));

  const groups = Object.entries(overview.attribute_groups ?? {});
  const xpPct = Math.max(0, Math.min(100, Math.round((overview.xp.progress_in_level ?? 0) * 100)));
  const seriesEntries = Object.entries(timeline?.attribute_series ?? {}).sort((a, b) => a[0].localeCompare(b[0]));
  const hasAttributeHistory = seriesEntries.some(([, points]) => points.length > 0);

  return (
    <div className="page container">
      <div className="stack">
        <div className="pg-head">
          <div className="stack-sm">
            <span className="eyebrow">{t("eyebrow")}</span>
            <h1 className="h1">{overview.player.name}</h1>
            <p className="lede">
              {t("lede", { position: overview.player.position, age: overview.player.age, goal: attributeLabel(overview.player.goal) })}
            </p>
            <div className="row wrap" style={{ gap: "0.4rem" }}>
              <span className="chip upper">{overview.player.archetype}</span>
              <span className="chip">{t("archetypeFit", { percent: Math.round(overview.player.archetype_match * 100) })}</span>
              <span className="chip">{t("strongFoot", { foot: overview.player.preferred_foot })}</span>
            </div>
          </div>
          <AiBadge demo_mode={overview.demo_data} />
        </div>

        {overview.training.sessions_completed === 0 && (
          <div className="notice notice--warn">{t("noSessions")}</div>
        )}

        <Panel
          eyebrow={t("profileEyebrow")}
          title={t("profileTitle")}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("profileFooter")}
            </span>
          }
        >
          <div className="pg-hero-grid">
            <Stat
              label={t("statOverall")}
              value={<span className="num">{overview.player.overall}</span>}
              hint={t("statOverallHint", { value: overview.player.potential })}
            />
            <Stat
              label={t("statLevel")}
              value={<span className="num">{overview.xp.level}</span>}
              hint={t("statLevelHint", { value: overview.xp.total })}
            />
            <Stat
              label={t("statForm")}
              value={<span className="num">{overview.player.form}</span>}
              hint={t("statFormHint")}
            />
            <Stat
              label={t("statStreak")}
              value={<span className="num">{overview.training.streak_days}</span>}
              hint={overview.training.last_session_at ? t("statStreakHint", { date: formatDay(overview.training.last_session_at) }) : t("statStreakNone")}
            />
            <Stat
              label={t("statSessions")}
              value={<span className="num">{overview.training.sessions_completed}</span>}
              hint={t("statSessionsHint", { value: overview.training.sessions_this_week })}
            />
          </div>
          <div className="pg-xp">
            <div className="pg-xp__meta">
              <span>
                {t("levelTo", { from: overview.xp.level, to: overview.xp.level + 1 })}
              </span>
              <span className="num">
                {t("levelProgress", { percent: Math.round(xpPct), xp: overview.xp.next_level_at })}
              </span>
            </div>
            <div className="bar" role="img" aria-label={t("levelBarLabel", { percent: xpPct })}>
              <div className="bar__fill" style={{ width: `${xpPct}%` }} />
            </div>
          </div>
        </Panel>

        <div className="grid grid-2">
          <Panel
            eyebrow={t("attributesEyebrow")}
            title={t("attributesTitle")}
            footer={
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {t("attributesFooter")}
              </span>
            }
          >
            {radarValues.length >= 3 ? (
              <div className="pg-radar">
                <AttributeRadar values={radarValues} label={`Attribute profile for ${overview.player.name}`} />
                <div className="pg-radar__list">
                  {radarValues.map((item) => (
                    <span key={item.key}>
                      <span className="upper">{item.label}</span>
                      <span className="num mono">{item.value}</span>
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <DataUnavailable metric={t("metricAttributeProfile")} />
            )}
          </Panel>

          <Panel
            eyebrow={t("changesEyebrow", { days })}
            title={t("changesTitle")}
            action={
              <div className="row" style={{ gap: "0.4rem" }}>
                {[7, 30, 90, 180].map((option) => (
                  <a
                    className={`btn btn--sm ${option === days ? "btn--primary" : "btn--ghost"}`}
                    href={`/progress?days=${option}${playerId ? `&player_id=${encodeURIComponent(playerId)}` : ""}`}
                    key={option}
                  >
                    {t("dayButton", { days: option })}
                  </a>
                ))}
              </div>
            }
            footer={
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {timeline
                  ? t("changesFooter")
                  : errorMessage(timelineResult.ok ? undefined : timelineResult.error, t("timelineUnavailable"))}
              </span>
            }
          >
            {!timeline ? (
              <DataUnavailable metric={t("metricAttributeHistory")} />
            ) : !hasAttributeHistory ? (
              <Empty
                title={t("emptyChangesTitle")}
                body={t("emptyChangesBody")}
                href="/training"
                cta={t("goToTraining")}
              />
            ) : (
              <div className="stack" style={{ gap: "0.9rem" }}>
                {seriesEntries.map(([attribute, points]) =>
                  points.length === 0 ? null : (
                    <div className="attr-block" key={attribute}>
                      <div className="attr-block__title">
                        <span className="upper">{attributeLabel(attribute)}</span>
                        <span className="chip num">{points.length === 1 ? t("changeOne", { count: points.length }) : t("changeMany", { count: points.length })}</span>
                      </div>
                      {[...points]
                        .sort((a, b) => a.at.localeCompare(b.at))
                        .map((point) => {
                          const before = point.after - point.delta;
                          const tone = point.delta > 0 ? "up" : point.delta < 0 ? "down" : "flat";
                          return (
                            <div className="attr-change" key={`${attribute}-${point.at}`}>
                              <span className="attr-change__when">{formatDay(point.at)}</span>
                              <span className="attr-change__what">{point.reason}</span>
                              <span className="attr-change__value">
                                <span className={`attr-change__delta--${tone}`}>{signed(point.delta)}</span>
                                {"  "}
                                {before} → {point.after}
                              </span>
                            </div>
                          );
                        })}
                    </div>
                  ),
                )}
              </div>
            )}
          </Panel>
        </div>

        <div className="section stack" style={{ gap: "0.75rem" }}>
          <span className="eyebrow">{t("groupsEyebrow")}</span>
          {groups.length === 0 ? (
            <DataUnavailable metric={t("metricAttributeGroups")} />
          ) : (
            <div className="grid grid-4">
              {groups.map(([group, values]) => {
                const entries = Object.entries(values ?? {});
                const groupKey = GROUP_KEYS[group];
                const groupLabel = groupKey ? t(groupKey) : attributeLabel(group);
                return (
                  <Panel eyebrow={t("groupEyebrow")} title={groupLabel} key={group}>
                    {entries.length === 0 ? (
                      <DataUnavailable metric={groupLabel} />
                    ) : (
                      <div className="pg-group__body">
                        {entries.map(([key, value]) => (
                          <Meter key={key} value={value} label={<span className="upper">{attributeLabel(key)}</span>} />
                        ))}
                      </div>
                    )}
                  </Panel>
                );
              })}
            </div>
          )}
        </div>

        <Panel
          eyebrow={t("milestonesEyebrow")}
          title={t("achievementsTitle")}
          footer={
            <div className="pg-note">
              <AiBadge demo_mode={overview.demo_data || Boolean(timeline?.demo_data)} />
            </div>
          }
        >
          {overview.achievements.length === 0 ? (
            <Empty
              title={t("emptyAchievementsTitle")}
              body={t("emptyAchievementsBody")}
              href="/training"
              cta={t("logSession")}
            />
          ) : (
            <div className="list">
              {overview.achievements.map((achievement) => (
                <div className="list__item" key={achievement.slug}>
                  <div className="grow stack-sm" style={{ gap: "0.15rem" }}>
                    <span className="h3">{achievement.title}</span>
                    <span className="muted" style={{ fontSize: "0.88rem" }}>
                      {achievement.description}
                    </span>
                  </div>
                  <span className="muted mono">{formatDay(achievement.awarded_at)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <div className="notice pg-note">
          <strong>{t("howNumbersMove")}</strong>
          <span className="muted">{t("howNumbersMoveBody")}</span>
          {overview.demo_data && (
            <span>
              <AiBadge demo_mode={overview.demo_data} />
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
