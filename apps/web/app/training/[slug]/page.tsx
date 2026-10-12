import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { DataUnavailable, DrillMeta, Meter, Panel } from "@/components/ui";
import { AddSession } from "@/app/training/AddSession";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { Drill } from "@/lib/types";

import "../training.css";

export const dynamic = "force-dynamic";

type DrillKnowledge = Omit<Drill, "id" | "positions" | "xp_base"> & { video: string };

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const t = await getTranslations("training");
  const result = await serverFetch<DrillKnowledge>(`/coach/drills/${encodeURIComponent(slug)}/knowledge`);
  const title = result.ok ? result.data.title : slug.replace(/-/g, " ");
  return {
    title,
    description: result.ok ? result.data.objective : t("syntheticDrill"),
  };
}

function PointList({ title, empty, items }: { title: string; empty: string; items: string[] }) {
  return (
    <div className="stack-sm">
      <p className="eyebrow">{title}</p>
      {items.length > 0 ? (
        <ul className="reasons">
          {items.map((item, index) => (
            <li className="reasons__item" key={`${title}-${index}`}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          {empty}
        </span>
      )}
    </div>
  );
}

export default async function DrillDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const user = await currentUser();
  if (!user) redirect("/login");

  const { slug } = await params;
  const t = await getTranslations("training");

  const [knowledgeResult, listResult] = await Promise.all([
    serverFetch<DrillKnowledge>(`/coach/drills/${encodeURIComponent(slug)}/knowledge`),
    serverFetch<Drill[]>("/trainings/drills"),
  ]);

  if (knowledgeResult.status === 401 || listResult.status === 401) redirect("/login");
  if (
    (!knowledgeResult.ok && knowledgeResult.status === 409 && knowledgeResult.error.code === "no_player") ||
    (!listResult.ok && listResult.status === 409 && listResult.error.code === "no_player")
  ) {
    redirect("/onboarding");
  }

  const knowledge = knowledgeResult.ok ? knowledgeResult.data : null;
  const listDrill = listResult.ok ? listResult.data.find((drill) => drill.slug === slug) ?? null : null;

  if (!knowledge && !listDrill) {
    if (!listResult.ok && !knowledgeResult.ok) {
      return (
        <div className="container page stack">
          <h1 className="h1">{t("drillFallbackTitle")}</h1>
          <div className="notice notice--warn">{errorMessage(knowledgeResult.ok ? listResult.error : knowledgeResult.error, t("drillUnavailable"))}</div>
        </div>
      );
    }
    notFound();
  }

  const title = knowledge?.title ?? listDrill?.title ?? "";
  const objective = knowledge?.objective ?? listDrill?.objective ?? "";
  const category = knowledge?.category ?? listDrill?.category ?? "";
  const difficulty = knowledge?.difficulty ?? listDrill?.difficulty ?? 0;
  const durationMin = knowledge?.duration_min ?? listDrill?.duration_min ?? 0;
  const equipment = knowledge?.equipment ?? listDrill?.equipment ?? [];
  const setup = knowledge?.setup ?? listDrill?.setup ?? "";
  const instructions = knowledge?.instructions ?? listDrill?.instructions ?? [];
  const coachingPoints = knowledge?.coaching_points ?? listDrill?.coaching_points ?? [];
  const mistakes = knowledge?.common_mistakes ?? listDrill?.common_mistakes ?? [];
  const progressions = knowledge?.progressions ?? listDrill?.progressions ?? [];
  const regression = knowledge?.regression ?? listDrill?.regression ?? "";
  const testPrompt = knowledge?.test_prompt ?? listDrill?.test_prompt ?? "";
  const testTarget = knowledge?.test_target ?? listDrill?.test_target ?? "";
  const targetAttributes = knowledge?.target_attributes ?? listDrill?.target_attributes ?? {};
  const isDemo = knowledge?.is_demo_data ?? listDrill?.is_demo_data ?? true;
  const video = knowledge?.video ?? t("dataUnavailable");

  const weights = Object.values(targetAttributes);
  const maxWeight = weights.length > 0 ? Math.max(...weights) : 1;

  return (
    <div className="container page stack">
      <div>
        <Link href="/training" className="muted" style={{ fontSize: "0.85rem" }}>
          {t("backToAcademy")}
        </Link>
        <div className="between wrap" style={{ gap: "0.6rem", marginTop: "0.5rem" }}>
          <div>
            <p className="eyebrow">{category.replace(/_/g, " ")}</p>
            <h1 className="h1">{title}</h1>
          </div>
          {isDemo && (
            <span className="badge badge--demo" title={t("demoSyntheticTitle")}>
              {t("demoSyntheticUpper")}
            </span>
          )}
        </div>
        <p className="lede">{objective}</p>
        {listDrill ? (
          <div style={{ marginTop: "0.6rem" }}>
            <DrillMeta drill={listDrill} />
          </div>
        ) : (
          <div className="tag-list" style={{ marginTop: "0.6rem" }}>
            <span className="chip">{t("durationChip", { minutes: durationMin })}</span>
            <span className="chip">{t("difficultyChip", { difficulty })}</span>
          </div>
        )}
      </div>

      <Panel eyebrow={t("getStartedEyebrow")} title={t("addToTodayTitle")}>
        {listDrill ? (
          <AddSession drillId={listDrill.id} title={title} durationMin={durationMin} />
        ) : (
          <p className="muted">{t("missingCatalogueId")}</p>
        )}
      </Panel>

      <Panel eyebrow={t("howToRunEyebrow")} title={t("setupTitle")}>
        <div className="stack">
          <div className="stack-sm">
            <p className="eyebrow">{t("setupEyebrow")}</p>
            <p className="muted">{setup || t("notProvided")}</p>
          </div>
          <div className="stack-sm">
            <p className="eyebrow">{t("equipmentEyebrow")}</p>
            {equipment.length > 0 ? (
              <div className="tag-list">
                {equipment.map((item) => (
                  <span className="chip" key={item}>
                    {item}
                  </span>
                ))}
              </div>
            ) : (
              <span className="muted" style={{ fontSize: "0.85rem" }}>
                {t("noEquipment")}
              </span>
            )}
          </div>
          <PointList title={t("instructions")} empty={t("notProvided")} items={instructions} />
          <PointList title={t("coachingPoints")} empty={t("notProvided")} items={coachingPoints} />
        </div>
      </Panel>

      <div className="grid-2">
        <Panel eyebrow={t("watchOutEyebrow")} title={t("mistakesTitle")}>
          <PointList title={t("mistakesToAvoid")} empty={t("notProvided")} items={mistakes} />
        </Panel>
        <Panel eyebrow={t("adjustEyebrow")} title={t("progressionsTitle")}>
          <div className="stack">
            <PointList title={t("progressions")} empty={t("notProvided")} items={progressions} />
            <div className="stack-sm">
              <p className="eyebrow">{t("regressionEyebrow")}</p>
              <p className="muted" style={{ fontSize: "0.9rem" }}>
                {regression || t("notProvided")}
              </p>
            </div>
          </div>
        </Panel>
      </div>

      <Panel eyebrow={t("selfTestEyebrow")} title={t("testTitle")}>
        <div className="stack-sm">
          <p className="muted">{testPrompt || t("noTestPrompt")}</p>
          {testTarget && (
            <div className="notice">
              <span className="eyebrow">{t("targetEyebrow")}</span>
              <p>{testTarget}</p>
            </div>
          )}
        </div>
      </Panel>

      <Panel eyebrow={t("trainsEyebrow")} title={t("targetAttributesTitle")}>
        {weights.length > 0 ? (
          <div className="grid-2">
            {Object.entries(targetAttributes).map(([attr, weight]) => (
              <Meter key={attr} label={t("emphasis", { attribute: attr.replace(/_/g, " ") })} value={weight} max={maxWeight} />
            ))}
          </div>
        ) : (
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            {t("noTargetAttributes")}
          </span>
        )}
      </Panel>

      <Panel eyebrow={t("videoEyebrow")} title={t("demonstrationTitle")}>
        {video && video !== t("dataUnavailable") ? (
          <p className="muted">{video}</p>
        ) : (
          <div className="stack-sm">
            <DataUnavailable metric={t("metricVideo")} />
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              {t("noVideoPipeline")}
            </p>
          </div>
        )}
      </Panel>
    </div>
  );
}
