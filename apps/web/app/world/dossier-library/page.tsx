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
  epic_total: number;
  sources_total: number;
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

type Props = { searchParams: Promise<{ page?: string }> };

export default async function DossierLibraryPage({ searchParams }: Props) {
  const t = await getTranslations("worldDossierLibrary");
  const raw = await searchParams;
  const page = Math.max(1, Number.parseInt(raw.page ?? "1", 10) || 1);
  const pageSize = 24;
  const result = await readWorld<Shelf>("/world/deep-dossier/volumes", {
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

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
  const pages = Math.max(1, Math.ceil(shelf.total / pageSize));
  const hasPrev = page > 1;
  const hasNext = page < pages;
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
        <div><span className="library-stats__num num">{shelf.epic_total}</span><span className="library-stats__label">{t("statEpic")}</span></div>
        <div><span className="library-stats__num num">{shelf.sources_total}</span><span className="library-stats__label">{t("statSources")}</span></div>
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
              <Link className="library-card" href={volume.path} prefetch={false}>
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

      {pages > 1 ? (
        <nav className="library-pager" aria-label={t("pagerAria")}>
          {hasPrev ? <Link className="btn" href={`/world/dossier-library?page=${page - 1}`}>{t("pagerPrev")}</Link> : <span />}
          <span className="muted mono">{t("pagerRange", { page, pages, total: shelf.total })}</span>
          {hasNext ? <Link className="btn" href={`/world/dossier-library?page=${page + 1}`}>{t("pagerNext")}</Link> : <span />}
        </nav>
      ) : null}

      <p className="muted library-foot">{t("foot")}</p>
    </div>
  );
}
