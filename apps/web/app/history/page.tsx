import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AiBadge, DataUnavailable, Empty, Panel } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { serverFetch } from "@/lib/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("history");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

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
  const t = await getTranslations("history");

  const sessionsResult = await serverFetch<SessionList>("/trainings/sessions", {
    query: { status: "completed", page, page_size: PAGE_SIZE },
  });
  if (!sessionsResult.ok) {
    if (sessionsResult.status === 401) redirect("/login");
    if (sessionsResult.status === 409 && sessionsResult.error.code === "no_player") redirect("/onboarding");
    return (
      <div className="page container">
        <div className="stack">
          <h1 className="h1">{t("metaTitle")}</h1>
          <div className="notice notice--warn">
            {errorMessage(sessionsResult.error, t("unavailable"))}
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
            <span className="eyebrow">{t("eyebrow")}</span>
            <h1 className="h1">{t("title")}</h1>
            <p className="lede">{t("lede")}</p>
          </div>
          <div className="stack-sm" style={{ alignItems: "flex-end" }}>
            <AiBadge demo_mode={sessions.demo_data || Boolean(timeline?.demo_data)} />
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("onFile", { total: sessions.total, page: sessions.page })}
            </span>
          </div>
        </div>

        <Panel
          eyebrow={t("sessionsEyebrow")}
          title={t("sessionsTitle", { page: sessions.page })}
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
              {t("sessionsFooter", { size: PAGE_SIZE, shown: sessions.items.length, total: sessions.total })}
            </span>
          }
        >
          {sessions.items.length === 0 ? (
            <Empty
              title={sessions.page > 1 ? t("emptyPageTitle") : t("emptyLogTitle")}
              body={sessions.page > 1 ? t("emptyPageBody") : t("emptyLogBody")}
              href="/training"
              cta={t("goToAcademy")}
            />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("colDate")}</th>
                    <th scope="col">{t("colDrill")}</th>
                    <th scope="col">{t("colCategory")}</th>
                    <th scope="col">{t("colMin")}</th>
                    <th scope="col">{t("colDiff")}</th>
                    <th scope="col">{t("colXp")}</th>
                    <th scope="col">{t("colExec")}</th>
                    <th scope="col">{t("colNotes")}</th>
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
                        {typeof item.xp_awarded === "number" ? item.xp_awarded : <DataUnavailable metric={t("metricXp")} />}
                      </td>
                      <td className="num">
                        {typeof item.execution_rating === "number"
                          ? `${item.execution_rating}/10`
                          : <DataUnavailable metric={t("metricExec")} />}
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
            eyebrow={t("daysEyebrow", { days })}
            title={t("daysTitle")}
            action={
              <div className="row wrap" style={{ gap: "0.4rem" }}>
                {[7, 30, 90, 180].map((option) => (
                  <Link
                    className={`btn btn--sm ${option === days ? "btn--primary" : "btn--ghost"}`}
                    href={`/history?page=1&days=${option}${playerId ? `&player_id=${encodeURIComponent(playerId)}` : ""}`}
                    key={option}
                  >
                    {t("dayButton", { days: option })}
                  </Link>
                ))}
              </div>
            }
            footer={
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {timeline
                  ? t("daysFooter")
                  : errorMessage(timelineResult.ok ? undefined : timelineResult.error, t("timelineUnavailable"))}
              </span>
            }
          >
            {!timeline ? (
              <DataUnavailable metric={t("metricDailyTimeline")} />
            ) : orderedDays.length === 0 ? (
              <Empty
                title={t("emptyWindowTitle")}
                body={t("emptyWindowBody")}
                href="/training"
                cta={t("goToTraining")}
              />
            ) : (
              <div className="timeline">
                {orderedDays.map(([date, bucket]) => (
                  <div className="timeline__row" key={date}>
                    <span className="mono">{formatDay(date).slice(0, 6)}</span>
                    <div className="stack-sm" style={{ gap: "0.15rem" }}>
                      <span className="upper" style={{ fontWeight: 600 }}>
                        {bucket.drills.length === 1 ? bucket.drills[0] : t("sessionCount", { count: bucket.drills.length })}
                      </span>
                      <span className="muted" style={{ fontSize: "0.82rem" }}>
                        {bucket.executions.length > 0
                          ? t("avgExecution", { value: (bucket.executions.reduce((sum, v) => sum + v, 0) / bucket.executions.length).toFixed(1) })
                          : t("executionMissing")}
                      </span>
                    </div>
                    <span className="num mono">
                      {bucket.xpCount > 0 ? t("xpPlus", { value: bucket.xp }) : <DataUnavailable metric={t("metricXp")} />}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel
            eyebrow={t("ledgerEyebrow")}
            title={t("ledgerTitle")}
            footer={
              <span className="muted" style={{ fontSize: "0.82rem" }}>
                {xpEvents.length > ledger.length
                  ? t("ledgerFooterRecent", { shown: ledger.length, total: xpEvents.length })
                  : t("ledgerFooterAll")}
              </span>
            }
          >
            {!timeline ? (
              <DataUnavailable metric={t("metricXpEvents")} />
            ) : ledger.length === 0 ? (
              <Empty
                title={t("emptyLedgerTitle")}
                body={t("emptyLedgerBody")}
                href="/training"
                cta={t("startSession")}
              />
            ) : (
              <div className="list">
                {ledger.map((event, index) => (
                  <div className="list__item" key={`${event.at}-${index}`}>
                    <div className="grow stack-sm" style={{ gap: "0.2rem" }}>
                      <div className="between wrap" style={{ gap: "0.5rem" }}>
                        <span className="mono">{formatDay(event.at)}</span>
                        <span className="num mono" style={{ color: "var(--accent)" }}>
                          {t("xpAmount", { value: event.amount > 0 ? `+${event.amount}` : event.amount })}
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
