import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

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
  const result = await serverFetch<DrillKnowledge>(`/coach/drills/${encodeURIComponent(slug)}/knowledge`);
  const title = result.ok ? result.data.title : slug.replace(/-/g, " ");
  return {
    title,
    description: result.ok ? result.data.objective : "Original synthetic training drill.",
  };
}

function PointList({ title, items }: { title: string; items: string[] }) {
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
          Not provided for this drill.
        </span>
      )}
    </div>
  );
}

export default async function DrillDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const user = await currentUser();
  if (!user) redirect("/login");

  const { slug } = await params;

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
          <h1 className="h1">Drill</h1>
          <div className="notice notice--warn">{errorMessage(knowledgeResult.ok ? listResult.error : knowledgeResult.error, "This drill could not be loaded.")}</div>
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
  const video = knowledge?.video ?? "Data unavailable";

  const weights = Object.values(targetAttributes);
  const maxWeight = weights.length > 0 ? Math.max(...weights) : 1;

  return (
    <div className="container page stack">
      <div>
        <Link href="/training" className="muted" style={{ fontSize: "0.85rem" }}>
          ← Back to Training Academy
        </Link>
        <div className="between wrap" style={{ gap: "0.6rem", marginTop: "0.5rem" }}>
          <div>
            <p className="eyebrow">{category.replace(/_/g, " ")}</p>
            <h1 className="h1">{title}</h1>
          </div>
          {isDemo && (
            <span className="badge badge--demo" title="Original synthetic demo content — not a real club's curriculum.">
              DEMO / SYNTHETIC
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
            <span className="chip">{durationMin} min</span>
            <span className="chip">difficulty {difficulty}/5</span>
          </div>
        )}
      </div>

      <Panel eyebrow="Get started" title="Add this drill to today">
        {listDrill ? (
          <AddSession drillId={listDrill.id} title={title} durationMin={durationMin} />
        ) : (
          <p className="muted">This drill record is missing its catalogue id, so it cannot be scheduled right now. Use the Training Academy index to add it.</p>
        )}
      </Panel>

      <Panel eyebrow="How to run it" title="Setup &amp; instructions">
        <div className="stack">
          <div className="stack-sm">
            <p className="eyebrow">Setup</p>
            <p className="muted">{setup || "Not provided for this drill."}</p>
          </div>
          <div className="stack-sm">
            <p className="eyebrow">Equipment</p>
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
                No specific equipment listed.
              </span>
            )}
          </div>
          <PointList title="Instructions" items={instructions} />
          <PointList title="Coaching points" items={coachingPoints} />
        </div>
      </Panel>

      <div className="grid-2">
        <Panel eyebrow="Watch out" title="Common mistakes">
          <PointList title="Mistakes to avoid" items={mistakes} />
        </Panel>
        <Panel eyebrow="Adjust" title="Progressions & regression">
          <div className="stack">
            <PointList title="Progressions" items={progressions} />
            <div className="stack-sm">
              <p className="eyebrow">Regression (make it easier)</p>
              <p className="muted" style={{ fontSize: "0.9rem" }}>
                {regression || "Not provided for this drill."}
              </p>
            </div>
          </div>
        </Panel>
      </div>

      <Panel eyebrow="Self-test" title="Test">
        <div className="stack-sm">
          <p className="muted">{testPrompt || "No test prompt provided."}</p>
          {testTarget && (
            <div className="notice">
              <span className="eyebrow">Target</span>
              <p>{testTarget}</p>
            </div>
          )}
        </div>
      </Panel>

      <Panel eyebrow="What it trains" title="Target attributes">
        {weights.length > 0 ? (
          <div className="grid-2">
            {Object.entries(targetAttributes).map(([attr, weight]) => (
              <Meter key={attr} label={`${attr.replace(/_/g, " ")} · emphasis`} value={weight} max={maxWeight} />
            ))}
          </div>
        ) : (
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            No target attributes recorded for this drill.
          </span>
        )}
      </Panel>

      <Panel eyebrow="Video" title="Demonstration">
        {video && video !== "Data unavailable" ? (
          <p className="muted">{video}</p>
        ) : (
          <div className="stack-sm">
            <DataUnavailable metric="Video" />
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              The video pipeline (M5) is not part of this build, so no demonstration clip is available for this drill.
            </p>
          </div>
        )}
      </Panel>
    </div>
  );
}
