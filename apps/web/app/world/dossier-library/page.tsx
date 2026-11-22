import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/dossier-library.css";

export const dynamic = "force-dynamic";

type ShelfEntry = {
  slug: string;
  focus: string;
  depth: string;
  locale: string;
  source_count: number;
  verified: boolean;
  view_count: number;
  created_at: string | null;
  path: string;
  excerpt: string;
};

type Shelf = WorldEnvelope & {
  available: boolean;
  total: number;
  limit: number;
  offset: number;
  volumes: ShelfEntry[];
};

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldDossierLibrary");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/dossier-library",
  });
}

export default async function DossierLibraryPage() {
  const t = await getTranslations("worldDossierLibrary");
  const result = await readWorld<Shelf>("/world/deep-dossier/volumes", { limit: 48 });

  if (!result.ok) {
    return (
      <div className="container page stack">
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} back={{ href: "/world", label: t("backWorld") }} />
        <WorldUnavailable message={result.message} />
        <p className="muted">{result.message}</p>
      </div>
    );
  }

  const shelf = result.data;
  const deepest = shelf.volumes.filter((volume) => volume.depth === "epic").length;
  const depthLabel = (depth: string): string => {
    if (depth === "standard") return t("depth_standard");
    if (depth === "epic") return t("depth_epic");
    return t("depth_deep");
  };

  return (
    <div className="container page stack">
      <WorldHead
        eyebrow={t("eyebrow")}
        title={t("title")}
        lede={t("lede")}
        provenance={shelf}
        back={{ href: "/world", label: t("backWorld") }}
      />

      <div className="library-stats">
        <div><span className="library-stats__num num">{shelf.total}</span><span className="library-stats__label">{t("statVolumes")}</span></div>
        <div><span className="library-stats__num num">{deepest}</span><span className="library-stats__label">{t("statEpic")}</span></div>
        <div><span className="library-stats__num num">{shelf.volumes.reduce((sum, volume) => sum + volume.source_count, 0)}</span><span className="library-stats__label">{t("statSources")}</span></div>
      </div>

      {shelf.volumes.length === 0 ? (
        <Panel eyebrow={t("emptyEyebrow")} title={t("emptyTitle")}>
          <p className="muted">{t("emptyBody")}</p>
          <Link className="btn btn--primary" href="/world/deep-dossier">{t("emptyCta")}</Link>
        </Panel>
      ) : (
        <ul className="library-shelf">
          {shelf.volumes.map((volume) => (
            <li key={volume.slug}>
              <Link className="library-card" href={volume.path}>
                <span className="library-card__top">
                  <span className={`library-card__depth library-card__depth--${volume.depth}`}>{depthLabel(volume.depth)}</span>
                  <span className="library-card__date mono">{(volume.created_at ?? "").slice(0, 10)}</span>
                </span>
                <strong className="library-card__focus">{volume.focus}</strong>
                <span className="library-card__excerpt">{volume.excerpt}</span>
                <span className="library-card__meta mono">
                  {t("cardMeta", { sources: volume.source_count, views: volume.view_count })}
                  {volume.verified ? ` · ${t("cardVerified")}` : ""}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <p className="muted library-foot">{t("foot")}</p>
    </div>
  );
}
