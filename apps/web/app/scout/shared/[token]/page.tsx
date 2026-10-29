import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ScoutReportPanel } from "@/components/ScoutReportPanel";
import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import type { ScoutSharedReport } from "@/lib/scout";
import { sharedMetadata } from "@/lib/site";
import { serverFetch } from "@/lib/server";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ token: string }> };

/**
 * §24's report handed to somebody without an account.
 *
 * The page is the same live read the scout's own report panel prints — the API rebuilds all thirteen fields from
 * the stored rows on every request — and adds only the question the link stores and the fact that its career, if
 * it named one, may since have been deleted. A link is a door, not a publication: noindex, and the canonical
 * belongs to `/scout`, the surface that mints the next one.
 */
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params;
  const ts = await getTranslations("scout");
  return sharedMetadata({
    title: ts("sharedMetaTitle"),
    description: ts("sharedMetaDescription"),
    sharePath: `/scout/shared/${encodeURIComponent(token)}`,
    canonicalPath: "/scout",
  });
}

export default async function SharedScoutReportPage({ params }: Props) {
  const { token } = await params;
  const tn = await getTranslations("nav");
  const ts = await getTranslations("scout");
  const result = await serverFetch<ScoutSharedReport>(`/scout/shared/${encodeURIComponent(token)}`);

  if (!result.ok) {
    if (result.status === 404) notFound();
    return (
      <WorldUnavailable
        detail={result.error.message}
        message={ts("sharedUnavailable")}
        title={ts("sharedUnavailableTitle")}
      />
    );
  }

  const report = result.data;
  const asked = report.asked_for;
  const opened = report.shared.opened_at?.slice(0, 16) ?? "—";

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={ts("sharedEyebrow", { player: report.player.name, opened })}
        lede={ts("sharedLede")}
        title={ts("sharedTitle")}
      />

      <Panel eyebrow={ts("sharedQuestionEyebrow", { fields: report.fields.length, player: report.player.name })} title={ts("sharedQuestionTitle")}>
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          <li className="muted mono" style={{ fontSize: "0.86rem" }}>{ts("sharedAskedPlayer", { value: asked.player })}</li>
          <li className="muted mono" style={{ fontSize: "0.86rem" }}>{ts("sharedAskedRole", { value: asked.role ?? "—" })}</li>
          <li className="muted mono" style={{ fontSize: "0.86rem" }}>{ts("sharedAskedCareer", { value: asked.career ?? "—" })}</li>
          <li className="muted mono" style={{ fontSize: "0.86rem" }}>{ts("sharedAskedCompare", { value: asked.compare_to ?? "—" })}</li>
          <li className="muted mono" style={{ fontSize: "0.86rem" }}>{ts("sharedAskedRound", { value: asked.round_index ?? "—" })}</li>
          <li className="muted" style={{ fontSize: "0.86rem" }}>{ts("sharedNoAccountNote")}</li>
          {report.shared.career_named && (
            <li className="muted" style={{ fontSize: "0.86rem" }}>
              {report.shared.career_available ? ts("sharedCareerAvailable") : ts("sharedCareerGone")}
            </li>
          )}
        </ul>
      </Panel>

      <Panel eyebrow={ts("reportEyebrow", { fields: report.fields.length, player: report.player.name })} title={ts("reportTitle")}>
        <div data-testid="scout-shared-report">
          <ScoutReportPanel report={report} />
        </div>
      </Panel>

      <p className="muted" style={{ fontSize: "0.84rem" }}>{report.shared.note}</p>
      <p className="muted" style={{ fontSize: "0.84rem" }}>
        {ts("sharedNeedOwn")} <Link className="world-link" href="/scout">{ts("sharedOpenScout")}</Link>.
      </p>
    </div>
  );
}
