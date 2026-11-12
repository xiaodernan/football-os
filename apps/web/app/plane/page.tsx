import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";

import { Empty, KeyValue, Meter, Panel, Stat } from "@/components/ui";
import { currentUser } from "@/lib/server";

export const dynamic = "force-dynamic";

/**
 * The operator's read of the service plane, on one page.
 *
 * <p>Three doors on the Spring Cloud edge answer about the edge itself: `/edge/breaker` (what the circuit
 * breaker thinks), `/edge/limits` (which rate-limit tier judged the last request, and how often it had to
 * degrade), and `/edge/lb` (the score the load balancer decides by, per core instance). Until this page they
 * were curl targets — readable by the person who already knew they existed, invisible to everyone else.
 *
 * <p>The page is a reader, not a monitor: every figure is fetched per request with a short timeout and
 * `no-store`, and a door that does not answer renders as unavailable in its own panel rather than failing the
 * page. That is the honest shape for a status surface — "the edge is down" and "the edge is fine but the
 * browser cannot see it" must not look the same, so each panel degrades alone.
 *
 * <p>`EDGE_URL` is the address the *web server* uses to reach the gateway (the compose network name in
 * deployment, `http://localhost:8080` for a local run). It is deliberately not a public URL: the edge's
 * `/edge/**` doors are internal, and a reader who wants them from outside should go through the product's
 * own surfaces.
 */
const EDGE = process.env.EDGE_URL ?? "http://localhost:8080";
const TIMEOUT_MS = 1500;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("plane");
  return { title: t("metaTitle"), description: t("metaDescription"), robots: { index: false, follow: false } };
}

/** One door on the edge, read with a deadline. A timeout and a refusal are the same answer here. */
async function readEdge<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(new URL(path, EDGE), {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { accept: "application/json" },
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

type InstanceRow = {
  score: number;
  ewmaMillis: number;
  failStreak: number;
  observations: number;
  failures: number;
  lastMillis: number;
  ageMillis: number;
};

/**
 * The report's own shape, including the two numbers that give the scores meaning.
 *
 * <p>`targetMillis` and `staleAfterMillis` are read from the edge rather than hardcoded here: they are the
 * running policy, and a console that printed its own guesses would be describing a gateway nobody deployed.
 * The `?` is honesty about an older edge that has not been upgraded yet — such a build reports no window,
 * and the page falls back to the documented defaults below.
 */
type LoadBalancer = {
  strategy: string;
  targetMillis?: number;
  staleAfterMillis?: number;
  instances: Record<string, InstanceRow>;
};

/** The edge's defaults, used only when a report does not carry them (an older gateway, or a stub). */
const DEFAULT_TARGET_MS = 60;
const DEFAULT_STALE_AFTER_MS = 30_000;

type Breaker = {
  name: string;
  present: boolean;
  state: string;
  slidingWindowSize: number;
  failureRateThreshold: number;
  minimumNumberOfCalls: number;
  permittedCallsInHalfOpenState: number;
  bufferedCalls: number;
  failedCalls: number;
  successfulCalls: number;
  notPermittedCalls: number;
  failureRate: number;
};

type Limits = {
  enabled: boolean;
  requestsPerSecond: number;
  burst: number;
  trackedClients: number;
  distributed: boolean;
  distributedChecks: number;
  distributedDegradations: number;
};

export default async function PlanePage() {
  const t = await getTranslations("plane");
  const locale = await getLocale();
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fplane");

  const [lb, breaker, limits] = await Promise.all([
    readEdge<LoadBalancer>("/edge/lb"),
    readEdge<Breaker>("/edge/breaker"),
    readEdge<Limits>("/edge/limits"),
  ]);

  const reachable = Boolean(lb || breaker || limits);
  const state = breaker?.state ?? "UNREACHABLE";
  const degraded = Boolean(limits && limits.distributedDegradations > 0) || state === "OPEN";
  // One badge, two colours: green only when a door answered *and* nothing is degrading. An unreachable edge
  // and a degrading one are different sentences, not different colours — the word carries which.
  const badge = reachable && !degraded ? "ok" : "warn";

  const ms = (value: number) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value) + " ms";
  const count = (value: number) => new Intl.NumberFormat(locale).format(value);
  const seconds = (millis: number) => t("secondsAgo", { value: Math.round(millis / 1000) });
  const duration = (millis: number) => t("duration", { value: Math.round(millis / 1000) });
  const percent = (value: number) =>
    value < 0 ? "—" : new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }).format(value / 100);

  const instances = Object.entries(lb?.instances ?? {});
  const ceiling = Math.max(100, ...instances.map(([, row]) => row.score)) * 1.15;
  const targetMillis = lb?.targetMillis ?? DEFAULT_TARGET_MS;
  const staleAfterMillis = lb?.staleAfterMillis ?? DEFAULT_STALE_AFTER_MS;
  // Mirrors the edge's rule exactly (`ageMillis <= staleAfterMillis` keeps full weight), so the chip and the
  // number beside it can never disagree about which side of the horizon a row is on.
  const isDecayed = (row: InstanceRow) => row.ageMillis > staleAfterMillis;

  return (
    <main className="page container stack">
      <header className="plane-head">
        <p className="eyebrow">{t("eyebrow")}</p>
        <div className="row between wrap plane-head__row">
          <div className="stack-sm">
            <h1 className="h1">{t("title")}</h1>
            <p className="lede">{t("lede")}</p>
          </div>
          <div className="plane-state">
            <span className={`badge badge--${badge}`}>
              {!reachable ? t("stateDown") : degraded ? t("stateDegraded") : t("stateOk")}
            </span>
            <span className="mono muted">{t("strategy", { value: lb?.strategy ?? "—" })}</span>
          </div>
        </div>
      </header>

      {!reachable ? (
        <Empty title={t("unreachableTitle")} body={t("unreachableBody", { timeout: TIMEOUT_MS })} />
      ) : (
        <>
          <div className="grid grid-4">
            <Stat
              label={t("statBreaker")}
              value={breaker ? state : "—"}
              hint={breaker ? t("statBreakerHint", { buffered: breaker.bufferedCalls, window: breaker.slidingWindowSize }) : t("noAnswer")}
            />
            <Stat
              label={t("statLimitScope")}
              value={limits ? (limits.distributed ? t("scopeCluster") : t("scopeProcess")) : "—"}
              hint={limits ? t("statLimitHint", { rps: limits.requestsPerSecond, burst: limits.burst }) : t("noAnswer")}
            />
            <Stat
              label={t("statInstances")}
              value={instances.length}
              hint={t("statInstancesHint")}
            />
            <Stat
              label={t("statTracked")}
              value={limits ? count(limits.trackedClients) : "—"}
              hint={limits ? t("statTrackedHint", { checks: count(limits.distributedChecks), degradations: count(limits.distributedDegradations) }) : t("noAnswer")}
            />
          </div>

          <Panel
            title={t("instancesTitle")}
            eyebrow={t("instancesEyebrow")}
            footer={t("instancesNote", { target: ms(targetMillis), window: duration(staleAfterMillis) })}
          >
            {instances.length === 0 ? (
              <p className="unavailable">{t("instancesEmpty")}</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{t("colInstance")}</th>
                      <th scope="col">{t("colScore")}</th>
                      <th scope="col">{t("colEwma")}</th>
                      <th scope="col">{t("colStreak")}</th>
                      <th scope="col">{t("colSamples")}</th>
                      <th scope="col">{t("colAge")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {instances.map(([key, row]) => (
                      <tr key={key}>
                        <td className="mono">{key}</td>
                        <td style={{ minWidth: "9rem" }}>
                          <Meter value={row.score} max={ceiling} display={ms(row.score)} />
                        </td>
                        <td className="num mono">{ms(row.ewmaMillis)}</td>
                        <td className="num mono">{row.failStreak}</td>
                        <td className="num mono">{t("samplesOf", { answers: count(row.observations), failures: count(row.failures) })}</td>
                        <td>
                          <div className="row wrap" style={{ gap: "0.4rem" }}>
                            <span className="muted">{seconds(row.ageMillis)}</span>
                            {isDecayed(row) && (
                              <span className="chip chip--warn" title={t("decayedHint")}>
                                {t("decayed")}
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <div className="grid grid-2">
            <Panel title={t("breakerTitle")} eyebrow={t("breakerEyebrow")}>
              {breaker ? (
                <KeyValue
                  rows={[
                    [t("breakerState"), breaker.present ? breaker.state : t("breakerAbsent")],
                    [t("breakerFailureRate"), percent(breaker.failureRate)],
                    [t("breakerThreshold"), percent(breaker.failureRateThreshold)],
                    [t("breakerWindow"), t("windowOf", { calls: breaker.bufferedCalls, size: breaker.slidingWindowSize })],
                    [t("breakerMinimum"), breaker.minimumNumberOfCalls],
                    [t("breakerHalfOpen"), breaker.permittedCallsInHalfOpenState],
                    [t("breakerNotPermitted"), count(breaker.notPermittedCalls)],
                  ]}
                />
              ) : (
                <p className="unavailable">{t("noAnswer")}</p>
              )}
            </Panel>

            <Panel title={t("limitsTitle")} eyebrow={t("limitsEyebrow")}>
              {limits ? (
                <KeyValue
                  rows={[
                    [t("limitsEnabled"), limits.enabled ? t("yes") : t("no")],
                    [t("limitsRps"), limits.requestsPerSecond],
                    [t("limitsBurst"), limits.burst],
                    [t("limitsScope"), limits.distributed ? t("scopeCluster") : t("scopeProcess")],
                    [t("limitsChecks"), count(limits.distributedChecks)],
                    [t("limitsDegradations"), count(limits.distributedDegradations)],
                    [t("limitsTracked"), count(limits.trackedClients)],
                  ]}
                />
              ) : (
                <p className="unavailable">{t("noAnswer")}</p>
              )}
            </Panel>
          </div>

          <p className="muted plane-foot">{t("footnote")}</p>
        </>
      )}
    </main>
  );
}
