import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { JsonLd, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
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

export const metadata: Metadata = {
  title: "Shared clip",
  description: "The record a FOOTBALL OS upload leaves behind, handed over by a revocable link — no account required.",
  robots: { index: false, follow: false },
};

export default async function SharedClipPage({ params }: Props) {
  const { token } = await params;
  const tn = await getTranslations("nav");
  const result = await serverFetch<SharedClip>(`/video/shared/${encodeURIComponent(token)}`);
  if (!result.ok) {
    if (result.status === 404 || result.error.code === "not_found") notFound();
    return <WorldUnavailable eyebrow="Shared clip" message={result.error.message} title="Shared clip" />;
  }

  const clip = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={`${clip.status} · ${clip.duration_s !== null ? `${clip.duration_s.toFixed(2)} s` : "no duration recorded"} · ${clip.width ?? "?"}×${clip.height ?? "?"}`}
        lede="This link was handed out by an account that uploaded a clip, and the account can revoke it at any time. It discloses the record the upload left behind; the footage itself is served to its owner."
        title={clip.title || clip.filename}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title="Shared via a revocable link; the owner can revoke it at any time.">
            shared clip
          </span>
          <span className="chip num">{clip.frame_count} frames sampled</span>
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
        <Panel eyebrow={`revocable link · ${token.slice(0, 8)}…`} title="What this link discloses">
          <div className="stack-sm" data-testid="shared-clip-disclosed">
            <dl className="world-kv">
              <div className="world-kv__row">
                <dt>title</dt>
                <dd className="mono">{clip.title || "(the file name stands in)"}</dd>
              </div>
              <div className="world-kv__row">
                <dt>file</dt>
                <dd className="mono">{clip.filename}</dd>
              </div>
              <div className="world-kv__row">
                <dt>status</dt>
                <dd className="mono">{clip.status}</dd>
              </div>
              <div className="world-kv__row">
                <dt>duration</dt>
                <dd className="mono">{clip.duration_s !== null ? `${clip.duration_s.toFixed(2)} s` : "—"}</dd>
              </div>
              <div className="world-kv__row">
                <dt>frame size</dt>
                <dd className="mono">{clip.width !== null && clip.height !== null ? `${clip.width} × ${clip.height}` : "—"}</dd>
              </div>
              <div className="world-kv__row">
                <dt>frames sampled</dt>
                <dd className="mono">{clip.frame_count}</dd>
              </div>
            </dl>
            <p className="muted world-section-note">
              The clip&apos;s bytes, its sampled frames and its detection timeline are served to the account that uploaded them, so a
              shared reader sees what the upload recorded rather than the footage. Playing a clip needs the owner&apos;s session.
            </p>
          </div>
        </Panel>
      </div>

      <Provenance
        provenance={{ data_origin: clip.data_origin, is_demo_data: clip.is_demo_data }}
        extra={<span className="chip">shared via revocable link; no owner identity is disclosed here</span>}
      />
    </div>
  );
}
