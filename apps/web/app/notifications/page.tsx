import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { MarkAllButton, MarkReadButton } from "@/components/NotificationActions";
import { Panel } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { pageMetadata } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { NotificationList } from "@/lib/types";

export const dynamic = "force-dynamic";

/** A tray is the account's own correspondence: never indexed, never shared. */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("notifications");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/notifications",
  });
}

function rowLine(kind: string, payload: NotificationList["items"][number]["payload"], t: (key: string, values?: Record<string, string>) => string): string {
  if (kind === "follower") return t("lineFollower", { name: payload.follower_name ?? "" });
  if (kind === "comment") return t("lineComment", { name: payload.actor_name ?? "", excerpt: payload.excerpt ?? "" });
  if (kind === "reaction") return t("lineReaction", { name: payload.actor_name ?? "" });
  return kind;
}

function KindIcon({ kind }: { kind: string }) {
  const common = { "aria-hidden": true } as const;
  if (kind === "reaction") {
    return (
      <span className="notice-row__icon notice-row__icon--reaction" aria-hidden="true">
        <svg viewBox="0 0 24 24" {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M8.5 14.5s1.4 1.8 3.5 1.8 3.5-1.8 3.5-1.8" />
          <circle cx="9.2" cy="9.6" r="0.4" fill="currentColor" />
          <circle cx="14.8" cy="9.6" r="0.4" fill="currentColor" />
        </svg>
      </span>
    );
  }
  if (kind === "comment") {
    return (
      <span className="notice-row__icon notice-row__icon--comment" aria-hidden="true">
        <svg viewBox="0 0 24 24" {...common}>
          <path d="M20 12a8 8 0 0 0-4.7-7.3L8 6a8 8 0 0 0-.4 15c.9.5 2 .8 3.4.8a8.8 8.8 0 0 0 4.9-1.4L20 21l-1.3-5.3A8 8 0 0 0 20 12z" />
          <path d="M9.5 12h.01M12.5 12h.01" />
        </svg>
      </span>
    );
  }
  return (
    <span className="notice-row__icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" {...common}>
        <path d="M12 12a4 4 0 1 0-4-4" />
        <path d="M4.5 19a6 6 0 0 1 10-4.5" />
        <path d="M14.5 8.5l4.5 1.5-3.5 3.5" />
      </svg>
    </span>
  );
}

export default async function NotificationsPage() {
  const t = await getTranslations("notifications");
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fnotifications");

  const result = await serverFetch<NotificationList>("/notifications?page=1");

  return (
    <div className="container page stack">
      <div>
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1 className="h1">{t("title")}</h1>
        <p className="lede">{t("lede")}</p>
      </div>

      <Panel
        eyebrow={result.ok ? t("trayEyebrow", { unread: result.data.unread_total, total: result.data.total }) : t("eyebrow")}
        title={t("trayTitle")}
        action={result.ok ? <MarkAllButton unreadTotal={result.data.unread_total} /> : null}
      >
        {result.ok ? (
          result.data.items.length === 0 ? (
            <div className="empty">
              <strong>{t("emptyTitle")}</strong>
              <span className="muted">{t("emptyNote")}</span>
            </div>
          ) : (
            <ul className="notice-list">
              {result.data.items.map((row) => (
                <li className={`notice-row${row.read_at ? " notice-row--read" : ""}`} key={row.id}>
                  <KindIcon kind={row.kind} />
                  <div className="notice-row__body">
                    <span className="notice-row__line">{rowLine(row.kind, row.payload, t)}</span>
                    <span className="notice-row__time mono">
                      {row.created_at?.slice(0, 16).replace("T", " ") ?? ""}
                    </span>
                  </div>
                  <div className="notice-row__meta">
                    {!row.read_at && <MarkReadButton id={row.id} />}
                    {row.payload.post_id && (
                      <Link className="world-link" href={`/community`}>
                        {t("openWall")}
                      </Link>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )
        ) : (
          <div className="notice notice--warn">{errorMessage(result.error, t("trayTitle"))}</div>
        )}
      </Panel>

      <p className="muted world-section-note">{result.ok ? result.data.formula : ""}</p>
    </div>
  );
}
