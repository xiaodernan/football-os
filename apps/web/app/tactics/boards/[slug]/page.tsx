import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { BoardEditor } from "@/components/BoardEditor";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { currentUser } from "@/lib/server";
import { absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { BoardDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export const metadata: Metadata = {
  title: "Edit tactical board",
  description: "Drag the eleven players, save the arrangement, and share a read-only link.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/tactics/boards") },
};

export default async function BoardEditPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Ftactics%2Fboards");

  const { slug } = await params;
  const result = await readWorld<BoardDetail>(`/boards/${encodeURIComponent(slug)}`);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable eyebrow="Tactical Lab" message={result.message} title="Edit tactical board" />;
  }

  const board = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics/boards", label: "My boards" }}
        eyebrow={`Your board · ${board.visibility === "shared" ? "link is live" : "private"}`}
        lede={board.note || "No note yet — this board only exists as positions and the measurements taken from them."}
        provenance={board}
        title={board.name}
      />

      <Panel eyebrow="Drag · save · share" title="The board">
        <div className="stack-sm">
          <BoardEditor board={board} />
          {board.origin_system && (
            <p className="muted world-section-note">
              Copied from{" "}
              <Link className="world-link" href={`/tactics/${board.origin_system}`}>
                {board.origin_system}
              </Link>
              . That system is unchanged: this is a separate row with your coordinates and `data_origin: user`.
            </p>
          )}
        </div>
      </Panel>

      <Provenance provenance={board} extra={<span className="chip">measurements recomputed on save</span>} />
    </div>
  );
}
