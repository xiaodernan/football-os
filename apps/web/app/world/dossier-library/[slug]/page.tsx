import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { Provenance, WorldHead } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/dossier-library.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

type Volume = WorldEnvelope & {
  slug: string;
  focus: string;
  depth: string;
  seed: number;
  locale: string;
  chapter: string;
  source_count: number;
  estimated_input_tokens: number;
  input_tokens: number;
  cached_input_tokens: number;
  verified: boolean;
  view_count: number;
  created_at: string | null;
  path: string;
};

async function load(slug: string, countView = true) {
  return readWorld<Volume>(`/world/deep-dossier/volumes/${encodeURIComponent(slug)}`, {
    count_view: countView ? undefined : "false",
  });
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  // Metadata is read on every crawl and on every navigation that resolves it; it must not
  // count as a reader opening the volume, or one visit would print as two.
  const result = await load(slug, false);
  const t = await getTranslations("worldDossierLibrary");
  const focus = result.ok ? result.data.focus : slug.replace(/-/g, " ");
  return pageMetadata({
    title: t("detailMetaTitle", { focus }),
    description: result.ok ? result.data.chapter.slice(0, 200) : t("metaDescription"),
    path: `/world/dossier-library/${slug}`,
  });
}

export default async function DossierVolumePage({ params }: Props) {
  const { slug } = await params;
  const t = await getTranslations("worldDossierLibrary");
  const result = await load(slug);
  if (!result.ok) {
    if (result.notFound) notFound();
    return (
      <div className="container page stack">
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} back={{ href: "/world/dossier-library", label: t("backLibrary") }} />
        <p className="muted">{result.message}</p>
      </div>
    );
  }

  const volume = result.data;
  const paragraphs = volume.chapter.split(/\n{2,}/).map((paragraph) => paragraph.trim()).filter(Boolean);
  const hit = volume.input_tokens > 0 ? Math.round((volume.cached_input_tokens / volume.input_tokens) * 1000) / 10 : null;
  const depthLabel =
    volume.depth === "standard" ? t("depth_standard") : volume.depth === "epic" ? t("depth_epic") : t("depth_deep");

  return (
    <div className="container page stack">
      <WorldHead
        eyebrow={`${t("eyebrow")} · ${depthLabel}`}
        title={volume.focus}
        lede={t("detailLede", { count: volume.source_count })}
        provenance={volume}
        back={{ href: "/world/dossier-library", label: t("backLibrary") }}
      />

      <article className="library-volume">
        {paragraphs.map((paragraph, index) => (
          <p key={index} className={index === 0 ? "library-volume__first" : undefined}>{paragraph}</p>
        ))}
      </article>

      <Panel eyebrow={t("receiptEyebrow")} title={t("receiptTitle")}>
        <dl className="library-receipt">
          <div><dt>{t("statSources")}</dt><dd className="num">{volume.source_count}</dd></div>
          <div><dt>{t("statEstimated")}</dt><dd className="num">{volume.estimated_input_tokens.toLocaleString()}</dd></div>
          <div><dt>{t("statInput")}</dt><dd className="num">{volume.input_tokens.toLocaleString()}</dd></div>
          <div><dt>{t("statCached")}</dt><dd className="num">{volume.cached_input_tokens.toLocaleString()}</dd></div>
          <div><dt>{t("statHit")}</dt><dd className="num">{hit === null ? "—" : `${hit}%`}</dd></div>
          <div><dt>{t("statViews")}</dt><dd className="num">{volume.view_count}</dd></div>
          <div><dt>{t("statBound")}</dt><dd className="num">{(volume.created_at ?? "").slice(0, 10)}</dd></div>
          <div><dt>{t("statVerified")}</dt><dd>{volume.verified ? t("verifiedYes") : t("verifiedNo")}</dd></div>
        </dl>
        <p className="muted mono library-seed">{t("seedLabel", { seed: volume.seed, locale: volume.locale })}</p>
        <div className="library-actions">
          <Link className="btn btn--primary" href="/world/deep-dossier">{t("composeCta")}</Link>
          <Link className="btn" href="/world/dossier-library">{t("shelfCta")}</Link>
        </div>
      </Panel>

      <Provenance provenance={volume} />
    </div>
  );
}
