"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

/**
 * The upload form. It posts multipart straight at the API proxy because `browserFetch` speaks JSON
 * only, and it reports the server's own refusal codes rather than re-deciding what a valid file is:
 * the container is judged from the bytes on the server, so a client-side extension check would be a
 * second, weaker opinion about the same question.
 */

const MAX_LABEL = "64 MiB";

export function VideoUpload({ limitPerUser, current }: { limitPerUser: number; current: number }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const full = current >= limitPerUser;

  async function submit() {
    const file = input.current?.files?.[0];
    if (!file) {
      setError("Choose a file first.");
      return;
    }
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.append("file", file, file.name);
    try {
      const response = await fetch(`/api/v1/video/upload?title=${encodeURIComponent(file.name.replace(/\.[^.]+$/, "").slice(0, 60))}`, {
        method: "POST",
        body,
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = (payload as { detail?: { code?: string; message?: string } } | null)?.detail;
        setError(detail?.message ? `${detail.code ?? "rejected"}: ${detail.message}` : `Upload failed (${response.status}).`);
        setBusy(false);
        return;
      }
      const asset = (payload as { asset?: { id?: string } } | null)?.asset;
      if (asset?.id) {
        if (input.current) input.current.value = "";
        router.push(`/video/${asset.id}`);
        router.refresh();
        return;
      }
      setError("The server accepted the file but returned no clip id.");
    } catch (cause) {
      setError(`The upload could not be sent: ${String(cause).slice(0, 120)}`);
    }
    setBusy(false);
  }

  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <input
          ref={input}
          accept="video/mp4,video/quicktime,video/webm"
          aria-label="Choose a clip to upload"
          className="input grow"
          style={{ maxWidth: 360 }}
          type="file"
        />
        <button className="btn btn--primary" disabled={busy || full} onClick={submit} type="button">
          {busy ? "Uploading…" : "Upload clip"}
        </button>
      </div>
      <p className="muted world-section-note">
        Accepted: mp4, MOV and webm, checked from the file&apos;s own bytes — a renamed file of another kind is refused, not renamed back.
        Up to {MAX_LABEL} per clip, {limitPerUser} clips per account ({current} used). Nothing is published: only this account can read a
        clip, its frames or its report.
      </p>
      {full && <p className="notice notice--warn">This account holds {limitPerUser} clips, which is the ceiling. Delete one to add another.</p>}
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
