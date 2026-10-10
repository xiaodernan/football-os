import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { BoardEditor } from "@/components/BoardEditor";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser } from "@/lib/server";
import { absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { BoardDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("tactics");
  return {
    title: t("editMetaTitle"),
    description: t("editMetaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/tactics/boards") },
  };
}

export default async function BoardEditPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Ftactics%2Fboards");

  const { slug } = await params;
  const tn = await getTranslations("nav");
  const t = await getTranslations("tactics");
  const result = await readWorld<BoardDetail>(`/boards/${encodeURIComponent(slug)}`);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable eyebrow={tn("tactics")} message={result.message} title={t("editUnavailableTitle")} />;
  }

  const board = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics/boards", label: tn("myBoards") }}
        eyebrow={t("editEyebrow", { visibility: board.visibility === "shared" ? t("boardLinkLive") : t("boardPrivate") })}
        lede={board.note || t("editNoNote")}
        provenance={board}
        title={board.name}
      />

      <Panel eyebrow={t("editorEyebrow")} title={t("editorTitle")}>
        <div className="stack-sm">
          <BoardEditor board={board} />
          {board.origin_system && (
            <p className="muted world-section-note">
              {t.rich("copiedFromNote", { system: board.origin_system, link: (chunks) => (
                <Link className="world-link" href={`/tactics/${board.origin_system}`}>
                  {chunks}
                </Link>
              ) })}
            </p>
          )}
        </div>
      </Panel>

      <Provenance provenance={board} extra={<span className="chip">{t("recomputedChip")}</span>} />
    </div>
  );
}
