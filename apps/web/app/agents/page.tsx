import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AgentConsole } from "@/app/agents/AgentConsole";
import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { AgentsListResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

// `generateMetadata` rather than a constant — same shape as the auth pages and /coach, so the tab
// title follows the reader's locale instead of staying the one string that never moves.
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("agents");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

export default async function AgentsPage() {
  const t = await getTranslations("agents");
  const user = await currentUser();
  if (!user) redirect("/login");

  // The roster is the registry's own answer, not a copy of it in TS: an agent added on the API
  // appears here without a second list to drift from. A name the catalogue has no description for
  // still renders — the console falls back to the raw type.
  const roster = await serverFetch<AgentsListResponse>("/agents/list");

  return (
    <div className="container page stack">
      <div>
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1 className="h1">{t("title")}</h1>
        <p className="lede">{t("lede")}</p>
      </div>
      <AgentConsole
        agents={roster.ok ? roster.data.available_agents : []}
        rosterError={roster.ok ? null : errorMessage(roster.error, t("requestFailed"))}
      />
    </div>
  );
}
