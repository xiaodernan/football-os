import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Pitch } from "@/components/pitch";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { GalleryList } from "@/lib/types";

import "../../../styles/tactics.css";

export const dynamic = "force-dynamic";

/**
 * The gallery is public but it is user content: indexed by no crawler, ever — the same
 * rule the clip report holds ("no clip of anyone's is crawlable"), applied to drawings.
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("gallery");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/tactics/gallery",
    // User content stays out of crawlers even when it is public — the clip report's rule,
    // applied to drawings. The consent shows work to visitors, not to an index.
    robots: { index: false, follow: true },
  });
}

export default async function GalleryPage() {
  const t = await getTranslations("gallery");
  const tn = await getTranslations("nav");
  const result = await readWorld<GalleryList>("/boards/gallery/public");

  if (!result.ok) {
    if (result.notFound) {
      return (
        <div className="container page stack">
          <WorldHead back={{ href: "/tactics", label: tn("tactics") }} eyebrow={t("eyebrow")} title={t("metaTitle")} lede={t("lede")} />
          <div className="empty">
            <strong>{t("emptyTitle")}</strong>
            <span className="muted">{t("emptyNote")}</span>
          </div>
        </div>
      );
    }
    return <WorldUnavailable eyebrow={t("eyebrow")} message={result.message} title={t("metaTitle")} />;
  }

  const gallery = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics", label: tn("tactics") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={gallery}
        title={t("metaTitle")}
      />

      {gallery.items.length === 0 ? (
        <div className="empty">
          <strong>{t("emptyTitle")}</strong>
          <span className="muted">{t("emptyNote")}</span>
          <Link className="btn btn--sm" href="/tactics/boards">
            {t("arrangeCta")}
          </Link>
        </div>
      ) : (
        <section className="stack">
          <h2 className="h2">{t("cardsHeading", { count: gallery.total })}</h2>
          <div className="tac-cards">
            {gallery.items.map((item) => (
              <Link className="tac-card" href={item.path} key={item.slug}>
                <span className="tac-card__name">{item.name}</span>
                <span className="tac-card__meta">
                  {t("arrangedBy", { name: item.owner.name })} · {item.origin_system ? t("fromSystem", { system: item.origin_system }) : t("fromScratch")}
                </span>
                <div className="tac-card__metrics">
                  <span className="chip num">
                    {item.metrics_in.find((metric) => metric.key === "width")?.value.toFixed(1)} {t("unitWide")}
                  </span>
                  <span className="chip num">
                    {item.metrics_in.find((metric) => metric.key === "space_behind")?.value.toFixed(1)} {t("unitBehind")}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {gallery.items[0] && (
        <Panel eyebrow={t("sampleEyebrow", { name: gallery.items[0].name })} title={t("sampleTitle")}>
          <div className="tac-boards">
            <Pitch
              caption={t("pitchCaption", { count: gallery.items[0].phase_in.length })}
              slots={gallery.items[0].phase_in}
              title={gallery.items[0].name}
            />
            <div className="stack-sm">
              <p className="muted" style={{ fontSize: "0.9rem" }}>
                {t("sampleNote")}
              </p>
              <Link className="btn btn--sm" href={gallery.items[0].path}>
                {t("openBoard", { name: gallery.items[0].name })}
              </Link>
            </div>
          </div>
        </Panel>
      )}

      <p className="muted world-section-note">{gallery.disclaimer}</p>
      <Provenance
        provenance={gallery}
        extra={<span className="chip">{t("consentChip")}</span>}
      />
    </div>
  );
}
