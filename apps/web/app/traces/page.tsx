import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";

import { KeyValue, Panel, Stat } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { TraceSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

/** The three windows the dashboard offers; the door itself accepts 1–1440 and clamps. */
const WINDOWS = [15, 60, 1440] as const;
const DEFAULT_WINDOW = 60;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("traces");
  return { title: t("metaTitle"), description: t("metaDescription"), robots: { index: false, follow: false } };
}

function chosenWindow(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  const parsed = Number.parseInt(raw ?? "", 10);
  return (WINDOWS as readonly number[]).includes(parsed) ? parsed : DEFAULT_WINDOW;
}

/**
 * The operator's panel over `GET /traces/summary` (M12's span store).
 *
 * The door asks for the operator's standing, and this page does not pre-judge it: it calls the door
 * with the account's own session and prints the answer. An admin reads the window, a non-admin reads
 * the refusal the door gave — one rendering, one source.
 *
 * Every figure is recomputed at read time from the rows the API returned: the totals are sums over
 * the route rows, and each row's failure share is its own errors ÷ count rather than a field copied
 * from the answer. The rows themselves are the API's read of the span store, which it recomputes on
 * every request; nothing here is a stored counter.
 */
export default async function TracesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const t = await getTranslations("traces");
  const locale = await getLocale();
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Ftraces");

  const minutes = chosenWindow((await searchParams).window);
  const result = await serverFetch<TraceSummary>("/traces/summary", { query: { window_minutes: minutes } });
  const percent = new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 2 });

  const data = result.ok ? result.data : null;
  const refused = !result.ok && result.status === 403;
  const refusal = refused ? errorMessage(result.ok ? undefined : result.error, t("unavailable")) : null;
  const failure = !result.ok && !refused ? errorMessage(result.error, t("unavailable")) : null;

  // The totals are sums over the rows on screen, not a summary line: every scanned span belongs to
  // exactly one group, so the two agree or the API is wrong.
  const errors = data ? data.routes.reduce((total, row) => total + row.errors, 0) : 0;
  const failureShare = data && data.spans_scanned > 0 ? errors / data.spans_scanned : 0;
  const windowText = minutes === 15 ? t("window15") : minutes === 1440 ? t("window1440") : t("window60");

  return (
    <div className="page container stack">
      <div>
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1 className="h1">{t("title")}</h1>
        <p className="lede">{t("lede")}</p>
      </div>

      <div className="stack-sm">
        <span className="eyebrow">{t("windowLabel")}</span>
        <div className="tag-list">
          {WINDOWS.map((window) => (
            <Link
              aria-current={window === minutes ? "page" : undefined}
              className={`chip${window === minutes ? " chip--accent" : ""}`}
              href={`/traces?window=${window}`}
              key={window}
            >
              {window === 15 ? t("window15") : window === 60 ? t("window60") : t("window1440")}
            </Link>
          ))}
        </div>
        <span className="muted" style={{ fontSize: "0.82rem" }}>
          {t("windowNote")}
        </span>
      </div>

      {refusal && (
        <Panel eyebrow={t("eyebrow")} title={t("title")}>
          <div className="notice notice--warn">{refusal}</div>
          <div className="stack-sm" style={{ marginTop: "0.8rem" }}>
            <p className="muted">{t("adminOnly")}</p>
            <p className="muted">{t("heldRole", { role: user.role })}</p>
          </div>
        </Panel>
      )}

      {failure && <div className="notice notice--warn">{failure}</div>}

      {data && (
        <>
          <div className="st-stats">
            <Stat label={t("statRoutes")} value={<span className="num">{data.routes.length}</span>} />
            <Stat
              hint={t("statSpansHint")}
              label={t("statSpans")}
              value={<span className="num">{data.spans_scanned}</span>}
            />
            <Stat hint={t("statErrorHint")} label={t("statErrors")} value={<span className="num">{errors}</span>} />
            <Stat
              label={t("statErrorRate")}
              value={<span className="num">{percent.format(failureShare)}</span>}
            />
          </div>

          <Panel eyebrow={t("tableEyebrow")} title={t("tableTitle")}>
            {data.truncated && <div className="notice notice--warn">{t("truncatedWarning")}</div>}
            {data.routes.length === 0 ? (
              <div className="empty">
                <strong>{t("emptyTitle")}</strong>
                <span className="muted">{t("emptyNote")}</span>
              </div>
            ) : (
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{t("thRoute")}</th>
                      <th scope="col">{t("thCount")}</th>
                      <th scope="col">{t("thErrors")}</th>
                      <th scope="col">{t("thRate")}</th>
                      <th scope="col">{t("thP50")}</th>
                      <th scope="col">{t("thP95")}</th>
                      <th scope="col">{t("thMax")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.routes.map((row, index) => (
                      <tr data-route={row.route} key={`${row.route}-${index}`}>
                        <td className="mono">{row.route || "—"}</td>
                        <td className="num">{row.count}</td>
                        <td className="num">{row.errors}</td>
                        <td className="num">{percent.format(row.count > 0 ? row.errors / row.count : 0)}</td>
                        <td className="num">{t("milliseconds", { value: row.p50_ms })}</td>
                        <td className="num">{t("milliseconds", { value: row.p95_ms })}</td>
                        <td className="num">{t("milliseconds", { value: row.max_ms })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel eyebrow={t("eyebrow")} title={t("formulaLabel")}>
            <KeyValue
              rows={[
                [t("windowLabel"), <span key="window">{windowText}</span>],
                [t("sinceLabel"), <span className="mono" key="since">{data.since}</span>],
                [t("scanLabel"), data.truncated ? t("truncatedYes") : t("truncatedNo")],
              ]}
            />
            <p className="muted mono" style={{ marginTop: "0.9rem" }}>
              {data.formula}
            </p>
          </Panel>
        </>
      )}
    </div>
  );
}
