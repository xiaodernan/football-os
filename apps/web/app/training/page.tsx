import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { DrillMeta, Empty, Panel } from "@/components/ui";
import { SessionLogger } from "@/app/training/SessionLogger";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { Drill, SessionListPage } from "@/lib/types";

import "./training.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("training");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

export default async function TrainingPage({ searchParams }: { searchParams: Promise<{ category?: string }> }) {
  const user = await currentUser();
  if (!user) redirect("/login");

  const { category } = await searchParams;
  const tc = await getTranslations("common");
  const t = await getTranslations("training");

  const [drillsResult, sessionsResult] = await Promise.all([
    serverFetch<Drill[]>("/trainings/drills"),
    serverFetch<SessionListPage>("/trainings/sessions", { query: { status: "planned" } }),
  ]);

  if (!drillsResult.ok) {
    if (drillsResult.status === 401) redirect("/login");
    if (drillsResult.status === 409 && drillsResult.error.code === "no_player") redirect("/onboarding");
    return (
      <div className="container page stack">
        <h1 className="h1">{t("metaTitle")}</h1>
        <div className="notice notice--warn">{errorMessage(drillsResult.error, t("catalogueUnavailable"))}</div>
      </div>
    );
  }

  const drills = drillsResult.data;
  const byCategory = new Map<string, Drill[]>();
  for (const drill of drills) {
    const list = byCategory.get(drill.category) ?? [];
    list.push(drill);
    byCategory.set(drill.category, list);
  }
  const categories = [...byCategory.keys()].sort();
  const activeCategory = category && byCategory.has(category) ? category : null;

  const planned = sessionsResult.ok ? sessionsResult.data.items : [];

  return (
    <div className="container page stack">
      <div className="between wrap" style={{ gap: "0.6rem" }}>
        <div>
          <p className="eyebrow">{t("eyebrow")}</p>
          <h1 className="h1">{t("title")}</h1>
        </div>
        <span className="badge badge--demo" title={t("demoBadgeTitle")}>
          {t("demoBadge", { count: drills.length })}
        </span>
      </div>
      <p className="lede">{t("lede", { count: drills.length })}</p>

      <Panel eyebrow={t("todayEyebrow")} title={t("plannedTitle", { count: planned.length })} action={<Link className="btn btn--ghost btn--sm" href="/coach">{t("askCoach")}</Link>}>
        {!sessionsResult.ok ? (
          <div className="notice notice--warn">{errorMessage(sessionsResult.error, t("plannedUnavailable"))}</div>
        ) : planned.length === 0 ? (
          <Empty title={t("nothingPlannedTitle")} body={t("nothingPlannedBody")} href="#catalogue" cta={t("browseDrills")} />
        ) : (
          <div className="stack">
            {planned.map((session) => (
              <SessionLogger key={session.id} session={session} />
            ))}
          </div>
        )}
      </Panel>

      <div id="catalogue" className="stack">
        <div className="between wrap" style={{ gap: "0.6rem" }}>
          <h2 className="h2">{t("catalogueTitle")}</h2>
          <div className="row wrap" style={{ gap: "0.4rem" }}>
            <Link className={`chip ${!activeCategory ? "chip--accent" : ""}`} href="/training">
              {tc("all")}
            </Link>
            {categories.map((name) => (
              <Link key={name} className={`chip ${activeCategory === name ? "chip--accent" : ""}`} href={`/training?category=${encodeURIComponent(name)}`}>
                {name.replace(/_/g, " ")}
              </Link>
            ))}
          </div>
        </div>

        {activeCategory ? (
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            {t("filteredTo")} <strong>{activeCategory.replace(/_/g, " ")}</strong>.{" "}
            <Link href="/training" style={{ textDecoration: "underline" }}>
              {t("clearFilter")}
            </Link>
          </p>
        ) : null}

        {(activeCategory ? [activeCategory] : categories).map((name) => (
          <section key={name} className="stack-sm">
            <h3 className="eyebrow">{name.replace(/_/g, " ")}</h3>
            <div className="grid-3">
              {(byCategory.get(name) ?? []).map((drill) => (
                <Link key={drill.id} href={`/training/${drill.slug}`} className="drill-card">
                  <div className="between">
                    <span className="h3">{drill.title}</span>
                  </div>
                  <p className="muted drill-card__objective">{drill.objective}</p>
                  <DrillMeta drill={drill} />
                  {drill.coaching_points[0] && <p className="drill-card__point">{t("keyPoint", { point: drill.coaching_points[0] })}</p>}
                  <span className="badge badge--demo">{t("demoSynthetic")}</span>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
