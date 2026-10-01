import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Panel } from "@/components/ui";
import { JsonLd, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { serverFetch } from "@/lib/server";
import type { VideoReport } from "@/lib/types";

import "../../../../styles/video.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ token: string }> };

export const metadata: Metadata = {
  title: "Shared clip",
  description: "A shared video clip from FOOTBALL OS — no account required to view.",
  robots: { index: false, follow: false },
};

export default async function SharedClipPage({ params }: Props) {
  const { token } = await params;
  const result = await serverFetch<VideoReport>(`/video/shared/${encodeURIComponent(token)}`);
  if (!result.ok) {
    if (result.status === 404 || result.error.code === "not_found") notFound();
    return <WorldUnavailable eyebrow="Shared clip" message={result.error.message} title="Shared clip" />;
  }

  const report = result.data;
  const asset = report.asset;
  const analysis = report.analysis;
  const frames = Array.from({ length: asset.frame_count }, (_, index) => index);
  const green = analysis?.green_fraction_mean;

  const interval = asset.frame_interval_s || 0;
  const overlays = new Map<number, typeof report.detections>();
  if (interval > 0) {
    for (const detection of report.detections) {
      const index = Math.min(asset.frame_count - 1, Math.max(0, Math.round(detection.t_s / interval)));
      const bucket = overlays.get(index);
      if (bucket) bucket.push(detection);
      else overlays.set(index, [detection]);
    }
  }

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: "Home" }}
        eyebrow={`${asset.status} · ${asset.duration_s.toFixed(2)} s · ${asset.width}×${asset.height} · ${asset.codec}`}
        lede="This clip was shared with a revocable link. No account is required to view it, and no owner identity is disclosed."
        title={asset.title || asset.filename}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title="Shared via a revocable link; the owner can revoke it at any time.">
            shared clip
          </span>
          <span className="chip num">{asset.frame_count} frames sampled</span>
          <span className="chip num">{report.detections.length} detections</span>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CreativeWork",
          name: asset.title || asset.filename,
          url: absolute(`/video/shared/${token}`),
          license: "Shared by a FOOTBALL OS account via revocable link",
          isAccessibleForFree: true,
          mentions: analysis ? { "@type": "SoftwareApplication", name: analysis.provider, applicationCategory: "analysis" } : undefined,
        }}
      />

      <div className="tac-boards">
        <Panel eyebrow="Shared stream" title="The clip">
          <div className="stack-sm">
            <video
              className="video-player"
              controls
              height={asset.height || undefined}
              preload="metadata"
              src={`/api/v1/video/${encodeURIComponent(asset.id)}/file`}
              width={asset.width || undefined}
            >
              This browser cannot play the file.
            </video>
            <p className="muted world-section-note">
              Served through the shared link. {asset.size_bytes.toLocaleString("en-GB")} bytes,
              {" "}
              {asset.bitrate_kbps.toFixed(1)} kbit/s.
            </p>
          </div>
        </Panel>

        <Panel eyebrow={analysis ? `${analysis.provider} · demo_mode ${String(analysis.demo_mode)}` : "not analysed yet"} title="What was measured">
          {analysis ? (
            <div className="stack-sm" data-testid="video-measured">
              <dl className="world-kv">
                <div className="world-kv__row">
                  <dt>frames read</dt>
                  <dd className="mono">{analysis.frames_seen}</dd>
                </div>
                <div className="world-kv__row">
                  <dt>task</dt>
                  <dd className="mono">{analysis.task}</dd>
                </div>
                <div className="world-kv__row">
                  <dt>pitch-green mean</dt>
                  <dd className="mono">{typeof green === "number" ? `${(green * 100).toFixed(1)}%` : "—"}</dd>
                </div>
                <div className="world-kv__row">
                  <dt>grid</dt>
                  <dd className="mono">{analysis.grid ? `${analysis.grid[0]} × ${analysis.grid[1]}` : "—"}</dd>
                </div>
                <div className="world-kv__row">
                  <dt>model</dt>
                  <dd className="mono">{analysis.model}</dd>
                </div>
              </dl>
              {analysis.thresholds && (
                <p className="muted world-section-note">
                  thresholds:{" "}
                  <span className="mono">
                    {Object.entries(analysis.thresholds)
                      .map(([key, value]) => `${key}=${value}`)
                      .join(" · ")}
                  </span>
                </p>
              )}
              <p className="notice notice--warn">{analysis.limitations}</p>
            </div>
          ) : (
            <div className="stack-sm">
              <span className="unavailable">No analysis stored for this clip yet.</span>
              <p className="muted world-section-note">Uploading alone does not measure anything — the pipeline runs when you ask it to.</p>
            </div>
          )}
        </Panel>
      </div>

      {report.detections.length > 0 && (
        <Panel eyebrow={`${report.detections.length} events · ${asset.frame_interval_s.toFixed(2)} s between samples`} title="Detection timeline">
          <div className="stack-sm">
            <div className="video-track" data-testid="video-track">
              {report.detections.map((detection) => (
                <span
                  className="video-track__mark"
                  key={detection.id}
                  style={{ left: `${Math.min(100, (detection.t_s / Math.max(asset.duration_s, 0.001)) * 100)}%` }}
                  title={`${detection.t_s.toFixed(2)}s — ${detection.why}`}
                />
              ))}
            </div>
            <div className="world-tablewrap">
              <table className="table" data-testid="video-detections">
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Position</th>
                    <th scope="col">Confidence</th>
                    <th scope="col">Why it was called</th>
                    <th scope="col">Provider</th>
                  </tr>
                </thead>
                <tbody>
                  {report.detections.map((detection) => (
                    <tr key={detection.id}>
                      <td className="num mono">{detection.t_s.toFixed(2)} s</td>
                      <td className="num mono">
                        x {detection.x.toFixed(3)} · y {detection.y.toFixed(3)}
                      </td>
                      <td className="num">{(detection.confidence * 100).toFixed(0)}%</td>
                      <td className="muted">{detection.why}</td>
                      <td className="mono muted">
                        {detection.provider}
                        {detection.demo_mode ? " · demo" : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted world-section-note">{report.disclaimer}</p>
          </div>
        </Panel>
      )}

      {frames.length > 0 && (
        <Panel eyebrow="The frames the measurements came from" title="Sampled frames">
          <div className="video-frames" data-testid="video-frames">
            {frames.map((index) => (
              <figure className="video-frames__item" key={index}>
                <span className="video-frames__frame">
                  {/* Not next/image on purpose: the QA gate proves the pixels on screen are the bytes the
                      pipeline decoded, so nothing may re-encode, resize or cache-transform them. */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img alt={`Sampled frame ${index}`} height={asset.height} src={`/api/v1/video/${encodeURIComponent(asset.id)}/frames/${index}`} width={asset.width} />
                  {(overlays.get(index) ?? []).map((detection) => (
                    <span
                      className="video-frame__mark"
                      data-detection={detection.id}
                      data-frame={index}
                      data-testid="video-frame-overlay"
                      data-x={detection.x}
                      data-y={detection.y}
                      key={detection.id}
                      style={{ left: `${detection.x * 100}%`, top: `${detection.y * 100}%` }}
                      title={`${detection.t_s.toFixed(2)}s · ${detection.kind} · ${(detection.confidence * 100).toFixed(0)}% — ${detection.why}`}
                    />
                  ))}
                </span>
                <figcaption className="mono">{(index * (asset.frame_interval_s || 0)).toFixed(2)} s</figcaption>
              </figure>
            ))}
          </div>
          <p className="muted world-section-note">
            These are the same samples the provider read, converted to PNG for display only. Positions above are fractions of the frame
            width and height, so they line up with what you see here. Each ring marks one detection&apos;s (x, y) on the sample its
            timestamp falls on — the centre of the non-pitch pixels that provider measured, not a player or a ball — and hovering it
            prints the timestamp, the confidence and the sentence the measurement was called with.
          </p>
        </Panel>
      )}

      {report.stages.length > 0 && (
        <Panel eyebrow={report.job ? `${report.job.type} · ${report.job.status} · ${report.job.progress}%` : "no job"} title="Stages of the last run">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Stage</th>
                  <th scope="col">State</th>
                  <th scope="col">Time</th>
                  <th scope="col">What it recorded</th>
                </tr>
              </thead>
              <tbody>
                {report.stages.map((stage) => (
                  <tr key={stage.name}>
                    <td className="mono">{stage.name}</td>
                    <td>{stage.status}</td>
                    <td className="num mono">{stage.ms} ms</td>
                    <td className="tac-formula">{JSON.stringify(stage.detail).slice(0, 180)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.job?.error && <p className="notice notice--warn">{report.job.error}</p>}
        </Panel>
      )}

      <Provenance
        provenance={{ data_origin: asset.data_origin, is_demo_data: asset.is_demo_data, disclaimer: report.disclaimer }}
        extra={<span className="chip">shared via revocable link; the clip is the uploader&apos;s; detections are a demo provider&apos;s measurements</span>}
      />
    </div>
  );
}