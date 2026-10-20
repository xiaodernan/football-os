import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { JsonLd, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute, sharedMetadata } from "@/lib/site";
import { serverFetch } from "@/lib/server";

import "../../../../styles/video.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ token: string }> };

/**
 * The wire shape of `GET /video/shared/{token}` — the ten fields that route's own `return` builds, and no others.
 *
 * This page used to type its read as `VideoReport`, the owner's shape, and then reach into `report.asset.frame_count`,
 * `report.detections`, `report.stages`. The shared door has never returned those: it answers a flat summary with no
 * `asset` key, so `asset` was `undefined` and the page died with `TypeError: Cannot read properties of undefined
 * (reading 'frame_count')` — a 500 for every anonymous reader, in every locale. The middleware bounced those readers
 * before they ever reached this line, so the crash stayed hidden until the share prefix was exempted.
 */
type SharedClip = {
  id: string;
  title: string;
  filename: string;
  duration_s: number | null;
  width: number | null;
  height: number | null;
  status: string;
  frame_count: number;
  data_origin: string;
  is_demo_data: boolean;
};

/**
 * The clip a share link carries is the most identifying file the platform holds, so this page is noindex and its
 * canonical belongs to `/video` — the same shape as the other two share surfaces (§109 gave it the canonical it
 * never had, and the card it should always have had: without an `openGraph` of its own the preview named the site
 * rather than the clip, which is exactly the difference between a link a reader opens and one they ignore.
 */
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params;
  const t = await getTranslations("video");
  return sharedMetadata({
    title: t("sharedMetaTitle"),
    description: t("sharedMetaDescription"),
    sharePath: `/video/shared/${encodeURIComponent(token)}`,
    canonicalPath: "/video",
  });
}

export default async function SharedClipPage({ params }: Props) {
  const { token } = await params;
  const tn = await getTranslations("nav");
  const t = await getTranslations("video");
  const result = await serverFetch<SharedClip>(`/video/shared/${encodeURIComponent(token)}`);
  if (!result.ok) {
    if (result.status === 404 || result.error.code === "not_found") notFound();
    return <WorldUnavailable eyebrow={t("sharedUnavailable")} message={result.error.message} title={t("sharedUnavailable")} />;
  }

  const clip = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={`${clip.status} · ${clip.duration_s !== null ? `${clip.duration_s.toFixed(2)} s` : "no duration recorded"} · ${clip.width ?? "?"}×${clip.height ?? "?"}`}
        lede={t("sharedLede")}
        title={clip.title || clip.filename}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title={t("chipSharedTitle")}>
            {t("chipShared")}
          </span>
          <span className="chip num">{t("chipFrames", { count: clip.frame_count })}</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CreativeWork",
          name: clip.title || clip.filename,
          url: absolute(`/video/shared/${token}`),
          license: "Shared by a FOOTBALL OS account via revocable link",
          isAccessibleForFree: true,
        }}
      />

      <div className="tac-boards">
        <Panel eyebrow={t("revocableLink", { token: `${token.slice(0, 8)}…` })} title={t("discloseTitle")}>
          <div className="stack-sm" data-testid="shared-clip-disclosed">
            <dl className="world-kv">
              <div className="world-kv__row">
                <dt>{t("labelTitle")}</dt>
                <dd className="mono">{clip.title || t("fallbackTitle")}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelFile")}</dt>
                <dd className="mono">{clip.filename}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelStatus")}</dt>
                <dd className="mono">{clip.status}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelDuration")}</dt>
                <dd className="mono">{clip.duration_s !== null ? `${clip.duration_s.toFixed(2)} s` : "—"}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelFrameSize")}</dt>
                <dd className="mono">{clip.width !== null && clip.height !== null ? `${clip.width} × ${clip.height}` : "—"}</dd>
              </div>
              <div className="world-kv__row">
                <dt>{t("labelFramesSampled")}</dt>
                <dd className="mono">{clip.frame_count}</dd>
              </div>
            </dl>
            <p className="muted world-section-note">{t("sharedNote")}</p>
          </div>
        </Panel>
      </div>

      <Provenance
        provenance={{ data_origin: clip.data_origin, is_demo_data: clip.is_demo_data }}
        extra={<span className="chip">{t("sharedProvenanceChip")}</span>}
      />
    </div>
  );
}
