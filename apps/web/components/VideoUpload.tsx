"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("video");
  const input = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const full = current >= limitPerUser;

  async function submit() {
    const file = input.current?.files?.[0];
    if (!file) {
      setError(t("errChoose"));
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
        setError(detail?.message ? `${detail.code ?? "rejected"}: ${detail.message}` : t("errUpload", { status: response.status }));
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
      setError(t("errNoId"));
    } catch (cause) {
      setError(t("errSend", { cause: String(cause).slice(0, 120) }));
    }
    setBusy(false);
  }

  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <input
          ref={input}
          accept="video/mp4,video/quicktime,video/webm"
          aria-label={t("chooseAria")}
          className="input grow"
          style={{ maxWidth: 360 }}
          type="file"
        />
        <button className="btn btn--primary" disabled={busy || full} onClick={submit} type="button">
          {busy ? t("uploading") : t("upload")}
        </button>
      </div>
      <p className="muted world-section-note">{t("acceptedNote", { max: MAX_LABEL, limit: limitPerUser, used: current })}</p>
      {full && <p className="notice notice--warn">{t("ceilingNote", { limit: limitPerUser })}</p>}
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
