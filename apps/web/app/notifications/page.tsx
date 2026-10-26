import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

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

const KIND_KEYS: Record<string, string> = {
  follower: "kindFollower",
  comment: "kindComment",
  reaction: "kindReaction",
};

function kindLabel(kind: string, t: (key: string) => string): string {
  const key = KIND_KEYS[kind];
  return key ? t(key) : kind;
}

function rowLine(kind: string, payload: NotificationList["items"][number]["payload"], t: (key: string, values?: Record<string, string>) => string): string {
  if (kind === "follower") return t("lineFollower", { name: payload.follower_name ?? "" });
  if (kind === "comment") return t("lineComment", { name: payload.actor_name ?? "", excerpt: payload.excerpt ?? "" });
  if (kind === "reaction") return t("lineReaction", { name: payload.actor_name ?? "" });
  return kind;
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
        action={
          result.ok && result.data.unread_total > 0 ? (
            <form action="/api/v1/notifications/read-all" method="POST">
              <button className="btn btn--ghost btn--sm" type="submit">
                {t("markAll")}
              </button>
            </form>
          ) : null
        }
      >
        {result.ok ? (
          result.data.items.length === 0 ? (
            <div className="empty">
              <strong>{t("emptyTitle")}</strong>
              <span className="muted">{t("emptyNote")}</span>
            </div>
          ) : (
            <ul className="list">
              {result.data.items.map((row) => (
                <li className={`list__item${row.read_at ? " muted" : ""}`} key={row.id}>
                  <span className={`chip${row.read_at ? "" : " chip--accent"}`}>{kindLabel(row.kind, t)}</span>
                  <div className="grow">
                    <span style={{ fontSize: "0.9rem" }}>{rowLine(row.kind, row.payload, t)}</span>
                    <span className="muted mono" style={{ fontSize: "0.78rem", display: "block" }}>
                      {row.created_at?.slice(0, 16).replace("T", " ") ?? ""}
                    </span>
                  </div>
                  {!row.read_at && (
                    <form action={`/api/v1/notifications/${row.id}/read`} method="POST">
                      <button className="btn btn--ghost btn--sm" type="submit">
                        {t("markRead")}
                      </button>
                    </form>
                  )}
                  {row.payload.post_id && (
                    <Link className="world-link" href={`/community`}>
                      {t("openWall")}
                    </Link>
                  )}
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
