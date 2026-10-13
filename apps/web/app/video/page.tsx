import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { VideoUpload } from "@/components/VideoUpload";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser, serverFetch } from "@/lib/server";
import { absolute } from "@/lib/site";
import type { VideoList } from "@/lib/types";

import "../../styles/video.css";

export const dynamic = "force-dynamic";

/** An account's clips are the most identifying files the platform can hold: nothing here is published. */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("video");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/video") },
  };
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
}

export default async function VideoIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fvideo");

  const tn = await getTranslations("nav");
  const t = await getTranslations("video");
  const result = await serverFetch<VideoList>("/video");
  if (!result.ok) {
    return <WorldUnavailable eyebrow={t("unavailableEyebrow")} message={result.error.message} title={t("unavailableTitle")} />;
  }

  const listing = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/my-football", label: tn("myFootball") }}
        eyebrow={t("eyebrow", { name: user.display_name })}
        lede={t("lede")}
        title={t("metaTitle")}
      />

      <Panel eyebrow={t("uploadEyebrow", { used: listing.total, limit: listing.limit_per_user })} title={t("uploadTitle")}>
        <VideoUpload current={listing.total} limitPerUser={listing.limit_per_user} />
      </Panel>

      {listing.items.length === 0 ? (
        <div className="empty">
          <strong>{t("emptyTitle")}</strong>
          <span className="muted">{t("emptyNote")}</span>
        </div>
      ) : (
        <section className="tac-cards">
          {listing.items.map((asset) => (
            <Link className="tac-card" href={`/video/${asset.id}`} key={asset.id}>
              <span className="tac-card__name">{asset.title || asset.filename}</span>
              <span className="tac-card__meta">
                {asset.duration_s.toFixed(2)}s · {asset.width}×{asset.height} · {asset.content_type} · {formatBytes(asset.size_bytes)}
              </span>
              <div className="tac-card__metrics">
                <span className={`chip ${asset.status === "analysed" ? "chip--accent" : ""}`}>{asset.status}</span>
                <span className="chip num">{t("chipFrames", { count: asset.frame_count })}</span>
                <span className="chip mono" title={t("chipOriginTitle")}>
                  data_origin: {asset.data_origin}
                </span>
              </div>
            </Link>
          ))}
        </section>
      )}

      <p className="muted world-section-note">{listing.privacy}</p>
      <Provenance
        provenance={{ data_origin: "user", is_demo_data: false }}
        extra={<span className="chip">{t("privacyChip")}</span>}
      />
    </div>
  );
}
