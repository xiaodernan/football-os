import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AiBadge, DataUnavailable, Empty, Panel } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { serverFetch } from "@/lib/server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Training log",
  description: "Every completed session, the XP it awarded and the exact formula behind that award.",
};

type SearchParams = Record<string, string | string[] | undefined>;

/**
 * Wire shapes for `GET /trainings/sessions` and `GET /progress/timeline`, mirrored per route
 * because `lib/types.ts` is churning under concurrent work.
 */
type SessionItem = {
  id: string;
  status: "planned" | "in_progress" | "completed" | "skipped";
  planned_date: string;
  completed_at: string | null;
  xp_awarded: number | null;
  execution_rating: number | null;
  focus_quality: number | null;
  self_notes: string | null;
  recommendation_reasons: string[];
  drill: {
    id: string;
    slug: string | null;
    title: string;
    category: string;
    duration_min: number;
    difficulty: number;
    test_prompt: string;
    test_target: string;
  };
};

type SessionList = { items: SessionItem[]; page: number; page_size: number; total: number; demo_data: boolean };

type Timeline = {
  sessions: { date: string; status: string; xp: number | null; execution: number | null; drill: string; category: string }[];
  attribute_series: Record<string, { at: string; after: number; delta: number; reason: string }[]>;
  xp_events: { at: string; amount: number; reason: string; formula: string }[];
  level_estimate: number;
  demo_data: boolean;
};

const PAGE_SIZE = 50;
const LEDGER_PREVIEW = 25;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function clampPage(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? "", 10);
  if (Number.isNaN(parsed) || parsed < 1) return 1;
  return Math.min(parsed, 500);
}

function clampDays(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? "", 10);
  if (Number.isNaN(parsed)) return 30;
  return Math.max(7, Math.min(180, parsed));
}

function formatDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const stamp = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(stamp.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(stamp);
}

function truncate(text: string | null, max = 70): string {
  if (!text) return "—";
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export default async function HistoryPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const playerId = first(params.player_id);
  const page = clampPage(first(params.page));
  const days = clampDays(first(params.days));
  const tc = await getTranslations("common");

  const sessionsResult = await serverFetch<SessionList>("/trainings/sessions", {
    query: { status: "completed", page, page_size: PAGE_SIZE },
  });
  if (!sessionsResult.ok) {
    if (sessionsResult.status === 401) redirect("/login");
    if (sessionsResult.status === 409 && sessionsResult.error.code === "no_player") redirect("/onboarding");
    return (
      <div className="page container">
        <div className="stack">
          <h1 className="h1">Training log</h1>
          <div className="notice notice--warn">
            {errorMessage(sessionsResult.error, "Your training log is unavailable right now.")}
          </div>
        </div>
      </div>
    );
  }
  const sessions = sessionsResult.data;

  const timelineResult = await serverFetch<Timeline>("/progress/timeline", {
    query: { player_id: playerId, days },
  });
  const timeline = timelineResult.ok ? timelineResult.data : null;

  const hasNext = sessions.items.length === sessions.page_size;
  const hasPrev = sessions.page > 1;
  const query = (target: number) =>
    `/history?page=${target}&days=${days}${playerId ? `&player_id=${encodeURIComponent(playerId)}` : ""}`;

  const byDate = new Map<string, { xp: number; xpCount: number; executions: number[]; drills: string[] }>();
  for (const item of timeline?.sessions ?? []) {
    const bucket = byDate.get(item.date) ?? { xp: 0, xpCount: 0, executions: [], drills: [] };
    if (typeof item.xp === "number") {
      bucket.xp += item.xp;
      bucket.xpCount += 1;
    }
    if (typeof item.execution === "number") bucket.executions.push(item.execution);
    bucket.drills.push(item.drill);
    byDate.set(item.date, bucket);
  }
  const orderedDays = [...byDate.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  const xpEvents = timeline?.xp_events ?? [];
  const ledger = xpEvents.slice(-LEDGER_PREVIEW).reverse();

  return (
    <div className="page container">
      <div className="stack">
        <div className="between wrap" style={{ alignItems: "flex-start", gap: "1rem" }}>
          <div className="stack-sm">
            <span className="eyebrow">History</span>
            <h1 className="h1">Training log</h1>
            <p className="lede">
              Completed sessions, the day-by-day record and the XP ledger. Nothing here is estimated: each row is a stored
              row from the API.
            </p>
          </div>
          <div className="stack-sm" style={{ alignItems: "flex-end" }}>
            <AiBadge demo_mode={sessions.demo_data || Boolean(timeline?.demo_data)} />
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              <span className="num">{sessions.total}</span> sessions on file (all statuses) · page{" "}
              <span className="num">{sessions.page}</span>
            </span>
          </div>
        </div>

        <Panel
          eyebrow="Completed sessions"
          title={`Session table · page ${sessions.page}`}
          action={
            <div className="row" style={{ gap: "0.4rem" }}>
              {hasPrev ? (
                <Link className="btn btn--ghost btn--sm" href={query(sessions.page - 1)}>
                  ← {tc("previousPage")}
                </Link>
              ) : (
                <span className="btn btn--sm btn--ghost" aria-disabled="true" style={{ opacity: 0.45 }}>
                  ← {tc("previousPage")}
                </span>
              )}
              {hasNext ? (
                <Link className="btn btn--sm" href={query(sessions.page + 1)}>
                  {tc("nextPage")} →
                </Link>
              ) : (
                <span className="btn btn--sm btn--ghost" aria-disabled="true" style={{ opacity: 0.45 }}>
                  {tc("nextPage")} →
                </span>
              )}
            </div>
          }
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              <span className="mono">GET /trainings/sessions?status=completed</span> · {PAGE_SIZE} rows per page ·
              showing <span className="num">{sessions.items.length}</span> of{" "}
              <span className="num">{sessions.total}</span> stored sessions.
            </span>
          }
        >
          {sessions.items.length === 0 ? (
            <Empty
              title={sessions.page > 1 ? "Nothing on this page" : "No completed sessions yet"}
              body={
                sessions.page > 1
                  ? "Use the previous link to return to the most recent entries."
                  : "The log fills itself when you finish a drill and report how it went."
              }
              href="/training"
              cta="Go to the academy"
            />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Drill</th>
                    <th scope="col">Category</th>
                    <th scope="col">Min</th>
                    <th scope="col">Diff.</th>
                    <th scope="col">XP</th>
                    <th scope="col">Exec.</th>
                    <th scope="col">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.items.map((item) => (
                    <tr key={item.id}>
                      <td className="num" style={{ whiteSpace: "nowrap" }}>
                        {formatDay(item.completed_at ?? item.planned_date)}
                      </td>
                      <td>{item.drill.title}</td>
                      <td>
                        <span className="chip upper">{item.drill.category}</span>
                      </td>
                      <td className="num">{item.drill.duration_min}</td>
                      <td className="num">{item.drill.difficulty}/5</td>
                      <td className="num">
                        {typeof item.xp_awarded === "number" ? item.xp_awarded : <DataUnavailable metric="XP" />}
                      </td>
                      <td className="num">
                        {typeof item.execution_rating === "number"
                          ? `${item.execution_rating}/10`
                          : <DataUnavailable metric="Exec" />}
                      </td>
                      <td title={item.self_notes ?? undefined} style={{ maxWidth: 240 }}>
                        {truncate(item.self_notes)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <div className="grid grid-2">
          <Panel
            eyebrow={`Last ${days} days`}
            title="Day by day"
            action={
              <div className="row wrap" style={{ gap: "0.4rem" }}>
                {[7, 30, 90, 180].map((option) => (
                  <Link
                    className={`btn btn--sm ${option === days ? "btn--primary" : "btn--ghost"}`}
                    href={`/history?page=1&days=${option}${playerId ? `&player_id=${encodeURIComponent(playerId)}` : ""}`}
                    key={option}
                  >
                    {option}d
                  </Link>
                ))}
              </div>
            }
            footer={
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {timeline
                  ? "Per-day totals are summed from GET /progress/timeline → sessions."
                  : errorMessage(timelineResult.ok ? undefined : timelineResult.error, "Timeline unavailable.")}
              </span>
            }
          >
            {!timeline ? (
              <DataUnavailable metric="Daily timeline" />
            ) : orderedDays.length === 0 ? (
              <Empty
                title="No sessions in this window"
                body="Pick a longer window, or complete a drill to start the record."
                href="/training"
                cta="Go to training"
              />
            ) : (
              <div className="timeline">
                {orderedDays.map(([date, bucket]) => (
                  <div className="timeline__row" key={date}>
                    <span className="mono">{formatDay(date).slice(0, 6)}</span>
                    <div className="stack-sm" style={{ gap: "0.15rem" }}>
                      <span className="upper" style={{ fontWeight: 600 }}>
                        {bucket.drills.length === 1 ? bucket.drills[0] : `${bucket.drills.length} sessions`}
                      </span>
                      <span className="muted" style={{ fontSize: "0.82rem" }}>
                        {bucket.executions.length > 0
                          ? `avg execution ${(bucket.executions.reduce((sum, v) => sum + v, 0) / bucket.executions.length).toFixed(1)}/10`
                          : "execution not reported"}
                      </span>
                    </div>
                    <span className="num mono">
                      {bucket.xpCount > 0 ? `+${bucket.xp} XP` : <DataUnavailable metric="XP" />}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel
            eyebrow="XP ledger"
            title="Every XP award and its formula"
            footer={
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {xpEvents.length > ledger.length
                  ? `Showing the ${ledger.length} most recent of ${xpEvents.length} stored XP events.`
                  : "All stored XP events for this player are listed."}
              </span>
            }
          >
            {!timeline ? (
              <DataUnavailable metric="XP events" />
            ) : ledger.length === 0 ? (
              <Empty
                title="No XP awarded yet"
                body="XP is granted by the progression engine when a session is completed; the formula is stored with it."
                href="/training"
                cta="Start a session"
              />
            ) : (
              <div className="list">
                {ledger.map((event, index) => (
                  <div className="list__item" key={`${event.at}-${index}`}>
                    <div className="grow stack-sm" style={{ gap: "0.2rem" }}>
                      <div className="between wrap" style={{ gap: "0.5rem" }}>
                        <span className="mono">{formatDay(event.at)}</span>
                        <span className="num mono" style={{ color: "var(--accent)" }}>
                          {event.amount > 0 ? `+${event.amount}` : event.amount} XP
                        </span>
                      </div>
                      <span className="muted" style={{ fontSize: "0.88rem" }}>
                        {event.reason}
                      </span>
                      <span className="mono" style={{ color: "var(--text-3)" }}>
                        {event.formula}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
