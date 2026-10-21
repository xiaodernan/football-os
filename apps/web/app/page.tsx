import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Empty, Panel, Stat } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { CapabilitiesResponse, Player, ProgressOverview } from "@/lib/types";

export const dynamic = "force-dynamic";

// `generateMetadata` rather than a constant — the tab follows the reader's locale instead of
// staying the one string that never moves.
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("home");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

export default async function HomePage() {
  const [user, capabilitiesResult, t, td, ta, tn, tc] = await Promise.all([
    currentUser(),
    serverFetch<CapabilitiesResponse>("/capabilities"),
    getTranslations("home"),
    getTranslations("disclaimer"),
    getTranslations("auth"),
    getTranslations("nav"),
    getTranslations("common"),
  ]);
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
      myFootballNotice = errorMessage(overviewResult.error, tc("progressUnavailable"));
    }
  }

  return (
    <div className="container page">
      {/* Hero */}
      <section className="pitch-backdrop" style={{ padding: "clamp(2rem, 5vw, 3.5rem)" }}>
        <div className="stack" style={{ gap: "1.1rem" }}>
          <span className="eyebrow">FOOTBALL OS</span>
          <h1 className="h1" style={{ textTransform: "uppercase", lineHeight: 1.1 }}>
            {t("heroLine1")}
            <br />
            {t("heroLine2")}
          </h1>
          <p className="lede">{t("heroLede")}</p>
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            {user ? (
              <Link className="btn btn--primary" href="/my-football">
                {tc("goTo")} {tn("myFootball")}
              </Link>
            ) : (
              <Link className="btn btn--primary" href="/register">
                {ta("createTitle")}
              </Link>
            )}
            <Link className="btn btn--ghost" href="/training">
              {t("heroExploreTraining")}
            </Link>
          </div>
        </div>
      </section>

      {/* Modules: three honest 'not built' columns + a real My Football column */}
      <section className="section grid grid-2">
        <NotBuiltPanel
          title={t("moduleLiveTitle")}
          eyebrow={t("moduleLiveEyebrow")}
          body={t("moduleLiveBody")}
          badge={t("notBuiltBadge")}
          hint={t("notBuiltHint")}
          emptyTitle={t("notBuiltTitle")}
        />
        <NotBuiltPanel
          title={t("moduleWorldTitle")}
          eyebrow={t("moduleWorldEyebrow")}
          body={
            capabilities
              ? t("moduleWorldBodyOn", {
                  status: capabilities.m3_football_world ? tc("statusOn") : tc("statusNotBuilt"),
                })
              : t("moduleWorldBodyOff")
          }
          badge={t("notBuiltBadge")}
          hint={t("notBuiltHint")}
          emptyTitle={t("notBuiltTitle")}
        />
        <NotBuiltPanel
          title={t("moduleNewsTitle")}
          eyebrow={t("moduleNewsEyebrow")}
          body={t("moduleNewsBody")}
          badge={t("notBuiltBadge")}
          hint={t("notBuiltHint")}
          emptyTitle={t("notBuiltTitle")}
        />

        <Panel title={t("myFootballTitle")} eyebrow={t("myFootballEyebrow")}>
          {!user ? (
            <Empty
              title={t("signInTitle")}
              body={t("signInBody")}
              href="/login"
              cta={ta("signIn")}
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
                    {players?.[0]?.is_demo_data ? t("demoDataSuffix") : ""}
                  </span>
                </div>
              </div>
              <div className="grid grid-3">
                <Stat
                  label="OVR"
                  value={<span className="num">{overview.player.overall}</span>}
                  hint={t("statPotential", { value: overview.player.potential })}
                />
                <Stat
                  label={t("statStreak")}
                  value={<span className="num">{overview.training.streak_days}</span>}
                  hint={t("statStreakHint")}
                />
                <Stat
                  label={t("statSessions")}
                  value={<span className="num">{overview.training.sessions_completed}</span>}
                  hint={t("statSessionsHint")}
                />
              </div>
              <Link className="btn btn--sm" href="/my-football">
                {tc("open")} {tn("myFootball")}
              </Link>
            </div>
          ) : (
            <Empty
              title={t("noPlayerTitle")}
              body={t("noPlayerBody")}
              href="/onboarding"
              cta={t("noPlayerCta")}
            />
          )}
        </Panel>
      </section>

      {/* What works today */}
      <section className="section">
        <p className="eyebrow">{t("availableNow")}</p>
        <h2 className="h2">{t("whatWorksTitle")}</h2>
        <p className="lede" style={{ marginTop: "0.5rem" }}>
          {t("whatWorksLede")}
        </p>
        <div className="grid grid-2 section">
          <FeaturePanel
            title={t("featureTrainingTitle")}
            body={t("featureTrainingBody")}
            href="/training"
            cta={t("featureTrainingCta")}
          />
          <FeaturePanel
            title={t("featureCoachTitle")}
            body={t("featureCoachBody")}
            href="/coach"
            cta={t("featureCoachCta")}
          />
          <FeaturePanel
            title={t("featureProgressTitle")}
            body={t("featureProgressBody")}
            href="/progress"
            cta={t("featureProgressCta")}
          />
          <FeaturePanel
            title={t("featureDataTitle")}
            body={t("featureDataBody")}
            href="/settings"
            cta={t("featureDataCta")}
          />
        </div>
      </section>

      {/* How we treat data */}
      <section className="section">
        <p className="eyebrow">{t("policyEyebrow")}</p>
        <h2 className="h2">{t("policyTitle")}</h2>
        <div className="grid grid-3 section">
          <Panel title={t("policySyntheticTitle")}>
            <p className="muted">{t("policySyntheticBody")}</p>
          </Panel>
          <Panel title={t("policyLicensedTitle")}>
            <p className="muted">{t("policyLicensedBody")}</p>
          </Panel>
          <Panel title={t("policyAiTitle")}>
            <p className="muted">{td("aiEstimate")}</p>
          </Panel>
        </div>
      </section>
    </div>
  );
}

function NotBuiltPanel({
  title,
  eyebrow,
  body,
  badge,
  hint,
  emptyTitle,
}: {
  title: string;
  eyebrow: string;
  body: string;
  badge: string;
  hint: string;
  emptyTitle: string;
}) {
  return (
    <Panel
      title={title}
      eyebrow={eyebrow}
      action={
        <span className="badge badge--demo" title={hint}>
          {badge}
        </span>
      }
    >
      <Empty title={emptyTitle} body={body} />
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
