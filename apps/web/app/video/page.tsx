import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { VideoUpload } from "@/components/VideoUpload";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser, serverFetch } from "@/lib/server";
import { absolute } from "@/lib/site";
import type { VideoList } from "@/lib/types";

import "../../styles/video.css";

export const dynamic = "force-dynamic";

/** An account's clips are the most identifying files the platform can hold: nothing here is published. */
export const metadata: Metadata = {
  title: "My video analysis",
  description: "Upload a clip, sample its frames, and read what the demo vision provider measured from its pixels.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/video") },
};

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
}

export default async function VideoIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fvideo");

  const result = await serverFetch<VideoList>("/video");
  if (!result.ok) {
    return <WorldUnavailable eyebrow="Video analysis" message={result.error.message} title="My video analysis" />;
  }

  const listing = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/my-football", label: "My Football" }}
        eyebrow={`${user.display_name} · private to this account`}
        lede="Upload a clip and the pipeline will read its container, sample frames at an even interval, and report where the non-pitch pixels moved. Every detection says which provider made it, and the provider says what it cannot see."
        title="My video analysis"
      />

      <Panel eyebrow={`Upload · ${listing.total} of ${listing.limit_per_user} clips used`} title="Add a clip">
        <VideoUpload current={listing.total} limitPerUser={listing.limit_per_user} />
      </Panel>

      {listing.items.length === 0 ? (
        <div className="empty">
          <strong>No clips yet</strong>
          <span className="muted">Nothing is analysed, and nothing is claimed, until a file arrives.</span>
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
                <span className="chip num">{asset.frame_count} frames sampled</span>
                <span className="chip mono" title="Uploaded by you; never shown to anyone else.">
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
        extra={<span className="chip">the clips are yours; the detections are a demo provider&apos;s pixel statistics</span>}
      />
    </div>
  );
}
