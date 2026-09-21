import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AttributeRadar } from "@/components/AttributeRadar";
import { AiBadge, DataUnavailable, Empty, Meter, Panel, Stat } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { serverFetch } from "@/lib/server";

import "./progress.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Development",
  description:
    "Your attribute profile, XP level, achievements and the exact reason behind every recorded change.",
};

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
const GROUP_LABELS: Record<string, string> = {
  technical: "Technical",
  physical: "Physical",
  mental: "Mental",
  tactical: "Tactical",
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
          <h1 className="h1">Development</h1>
          <div className="notice notice--warn">
            {errorMessage(overviewResult.error, "Progress data is unavailable right now.")}
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
            <span className="eyebrow">Development</span>
            <h1 className="h1">{overview.player.name}</h1>
            <p className="lede">
              {overview.player.position} · {overview.player.age} years · goal: {attributeLabel(overview.player.goal)}
            </p>
            <div className="row wrap" style={{ gap: "0.4rem" }}>
              <span className="chip upper">{overview.player.archetype}</span>
              <span className="chip">archetype fit {Math.round(overview.player.archetype_match * 100)}%</span>
              <span className="chip">strong foot: {overview.player.preferred_foot}</span>
            </div>
          </div>
          <AiBadge demo_mode={overview.demo_data} />
        </div>

        {overview.training.sessions_completed === 0 && (
          <div className="notice notice--warn">
            No completed sessions recorded yet. Every number below comes from your onboarding profile only — attributes
            cannot move until you log training yourself.
          </div>
        )}

        <Panel
          eyebrow="Profile"
          title="Where you are now"
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              All figures read from <span className="mono">GET /progress/overview</span>. No modelled or decorative data.
            </span>
          }
        >
          <div className="pg-hero-grid">
            <Stat
              label="Overall"
              value={<span className="num">{overview.player.overall}</span>}
              hint={`potential ${overview.player.potential}`}
            />
            <Stat
              label="Level"
              value={<span className="num">{overview.xp.level}</span>}
              hint={`${overview.xp.total} XP total`}
            />
            <Stat
              label="Form"
              value={<span className="num">{overview.player.form}</span>}
              hint="derived from recent completed sessions"
            />
            <Stat
              label="Streak"
              value={<span className="num">{overview.training.streak_days}</span>}
              hint={overview.training.last_session_at ? `last session ${formatDay(overview.training.last_session_at)}` : "no sessions logged"}
            />
            <Stat
              label="Sessions completed"
              value={<span className="num">{overview.training.sessions_completed}</span>}
              hint={`${overview.training.sessions_this_week} in the last 7 days`}
            />
          </div>
          <div className="pg-xp">
            <div className="pg-xp__meta">
              <span>
                Level {overview.xp.level} → {overview.xp.level + 1}
              </span>
              <span className="num">
                {Math.round(xpPct)}% · next level at {overview.xp.next_level_at} XP
              </span>
            </div>
            <div className="bar" role="img" aria-label={`Level progress ${xpPct}%`}>
              <div className="bar__fill" style={{ width: `${xpPct}%` }} />
            </div>
          </div>
        </Panel>

        <div className="grid grid-2">
          <Panel
            eyebrow="Attributes"
            title="Strongest six right now"
            footer={
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                Selected as the six highest current values in <span className="mono">attributes</span> — the API supplies
                the numbers, the chart adds none.
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
              <DataUnavailable metric="Attribute profile" />
            )}
          </Panel>

          <Panel
            eyebrow={`Last ${days} days`}
            title="Attribute changes, with the reason"
            action={
              <div className="row" style={{ gap: "0.4rem" }}>
                {[7, 30, 90, 180].map((option) => (
                  <a
                    className={`btn btn--sm ${option === days ? "btn--primary" : "btn--ghost"}`}
                    href={`/progress?days=${option}${playerId ? `&player_id=${encodeURIComponent(playerId)}` : ""}`}
                    key={option}
                  >
                    {option}d
                  </a>
                ))}
              </div>
            }
            footer={
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {timeline
                  ? "Read from GET /progress/timeline → attribute_series. Oldest first, newest last."
                  : errorMessage(timelineResult.ok ? undefined : timelineResult.error, "Timeline unavailable.")}
              </span>
            }
          >
            {!timeline ? (
              <DataUnavailable metric="Attribute history" />
            ) : !hasAttributeHistory ? (
              <Empty
                title="No attribute changes in this window"
                body="Attributes only move when a session is completed and self-rated. Widen the window or log a session."
                href="/training"
                cta="Go to training"
              />
            ) : (
              <div className="stack" style={{ gap: "0.9rem" }}>
                {seriesEntries.map(([attribute, points]) =>
                  points.length === 0 ? null : (
                    <div className="attr-block" key={attribute}>
                      <div className="attr-block__title">
                        <span className="upper">{attributeLabel(attribute)}</span>
                        <span className="chip num">{points.length} change{points.length === 1 ? "" : "s"}</span>
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
          <span className="eyebrow">Attribute groups</span>
          {groups.length === 0 ? (
            <DataUnavailable metric="Attribute groups" />
          ) : (
            <div className="grid grid-4">
              {groups.map(([group, values]) => {
                const entries = Object.entries(values ?? {});
                return (
                  <Panel eyebrow="Group" title={GROUP_LABELS[group] ?? attributeLabel(group)} key={group}>
                    {entries.length === 0 ? (
                      <DataUnavailable metric={GROUP_LABELS[group] ?? group} />
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
          eyebrow="Milestones"
          title="Achievements"
          footer={
            <div className="pg-note">
              <AiBadge demo_mode={overview.demo_data || Boolean(timeline?.demo_data)} />
            </div>
          }
        >
          {overview.achievements.length === 0 ? (
            <Empty
              title="No achievements unlocked yet"
              body="Achievements are written by the progression engine when a completed session crosses a stored threshold."
              href="/training"
              cta="Log a session"
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
          <strong>How these numbers move</strong>
          <span className="muted">
            This engine has no camera, no wearable and no club feed. An attribute only changes when you complete a
            session and report your own execution and focus; the recorded <span className="mono">reason</span> text above
            is the rule that fired. The AI layer explains and recommends — it never edits your attributes, and every XP
            award on the history page shows its stored formula.
          </span>
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
