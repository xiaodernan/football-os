import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { BoardsNew } from "@/components/BoardsNew";
import { Panel } from "@/components/ui";
import { OriginBadge, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser, serverFetch } from "@/lib/server";
import { absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { BoardList, SystemList } from "@/lib/types";

export const dynamic = "force-dynamic";

/** A person's own boards are private working material, not a publication. */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("tactics");
  return {
    title: t("boardsMetaTitle"),
    description: t("boardsMetaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/tactics/boards") },
  };
}

function formatStamp(iso: string | null): string {
  if (!iso) return "—";
  const stamp = new Date(iso);
  if (Number.isNaN(stamp.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(stamp);
}

export default async function BoardsIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Ftactics%2Fboards");
  const tn = await getTranslations("nav");
  const t = await getTranslations("tactics");

  const [boards, systems] = await Promise.all([serverFetch<BoardList>("/boards"), readWorld<SystemList>("/tactics", { page_size: 50 })]);

  if (!boards.ok) {
    return <WorldUnavailable eyebrow={tn("tactics")} message={boards.error.message} title={t("boardsUnavailableTitle")} />;
  }

  const list = boards.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics", label: tn("tactics") }}
        eyebrow={t("boardsEyebrow", { name: user.display_name })}
        lede={t("boardsLede")}
        provenance={list}
        title={t("boardsMetaTitle")}
      />

      <Panel eyebrow={t("createEyebrow", { used: list.total, limit: list.limit_per_user })} title={t("createTitle")}>
        {systems.ok ? <BoardsNew systems={systems.data.items.map((item) => ({ slug: item.slug, name: item.name }))} /> : <div className="notice notice--warn">{systems.message}</div>}
      </Panel>

      {list.items.length === 0 ? (
        <div className="empty">
          <strong>{t("boardsEmptyTitle")}</strong>
          <span className="muted">{t("boardsEmptyNote")}</span>
        </div>
      ) : (
        <section className="tac-cards">
          {list.items.map((board) => (
            <Link className="tac-card" href={`/tactics/boards/${board.slug}`} key={board.id}>
              <span className="row" style={{ gap: "0.5rem", justifyContent: "space-between" }}>
                <span className="tac-card__name">{board.name}</span>
                <OriginBadge provenance={board} />
              </span>
              <span className="tac-card__meta">
                {board.origin_system ? t("boardFromSystem", { system: board.origin_system }) : t("boardFromScratch")} · {board.visibility === "shared" ? t("boardLinkLive") : t("boardPrivate")}
              </span>
              <div className="tac-card__metrics">
                <span className="chip num">{board.metrics_in.find((metric) => metric.key === "width")?.value.toFixed(1)} m wide</span>
                <span className="chip num">{board.metrics_in.find((metric) => metric.key === "space_behind")?.value.toFixed(1)} m behind</span>
                <span className="chip">{formatStamp(board.updated_at)}</span>
              </div>
            </Link>
          ))}
        </section>
      )}

      <Provenance
        provenance={list}
        extra={<span className="chip">{t("boardsPrivacyChip")}</span>}
      />
    </div>
  );
}
