import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Pitch } from "@/components/pitch";
import { BandLegend } from "@/components/tactics";
import { MetricTable } from "@/components/tactics";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { GalleryRow } from "@/lib/types";

import "../../../../styles/tactics.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const t = await getTranslations("gallery");
  const result = await readWorld<GalleryRow>(`/boards/gallery/public/${encodeURIComponent(slug)}`);
  return pageMetadata({
    title: result.ok ? `${result.data.name} — ${t("boardMetaSuffix")}` : t("metaTitle"),
    description: t("boardMetaDescription", { name: result.ok ? result.data.name : "" }),
    path: `/tactics/gallery/${slug}`,
  });
}

export default async function GalleryBoardPage({ params }: Props) {
  const { slug } = await params;
  const t = await getTranslations("gallery");
  const tt = await getTranslations("tactics");
  const result = await readWorld<GalleryRow>(`/boards/gallery/public/${encodeURIComponent(slug)}`);

  if (!result.ok) {
    if (result.notFound) {
      // An unlisted or revoked board is absent — the same hard 404 a dead share link earns.
      // A soft 200 with apologetic copy would teach a crawler that the address is content.
      notFound();
    }
    return (
      <div className="container page stack">
        <WorldHead back={{ href: "/tactics/gallery", label: t("metaTitle") }} eyebrow={t("eyebrow")} title={t("metaTitle")} lede={result.message} />
      </div>
    );
  }

  const board = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics/gallery", label: t("metaTitle") }}
        eyebrow={t("boardEyebrow", { name: board.owner.name })}
        lede={t("boardLede")}
        provenance={board}
        title={board.name}
      />

      <Panel eyebrow={t("phaseIn")} title={t("boardTitle")}>
        <div className="tac-boards">
          <div className="stack-sm">
            <p className="eyebrow">{t("phaseIn")}</p>
            <Pitch
              axisOpponent={tt("pitchAxisOpponent")}
              axisOwn={tt("pitchAxisOwn")}
              caption={t("pitchCaption", { count: board.phase_in.length })}
              slots={board.phase_in}
              title={board.name}
            />
          </div>
        </div>
        <div style={{ marginTop: "0.7rem" }}>
          <BandLegend />
        </div>
      </Panel>

      <Panel eyebrow={t("measuredEyebrow")} title={t("measuredTitle")}>
        <MetricTable metrics={board.metrics_in} />
      </Panel>

      <p className="muted world-section-note">
        {t("noteNote")}{" "}
        <Link className="world-link" href="/tactics">
          {t("catalogueLink")}
        </Link>
      </p>

      <Provenance provenance={board} extra={<span className="chip">{t("consentChip")}</span>} />
    </div>
  );
}
