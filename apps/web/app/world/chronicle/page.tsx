import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead } from "@/components/world";
import type { RowProvenance } from "@/components/world";
import { ChronicleReadPanel } from "@/components/ChronicleRead";
import { pageMetadata } from "@/lib/site";
import "@/styles/chronicle.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldChronicle");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/chronicle",
  });
}

const ROW_PROVENANCE: RowProvenance = { data_origin: "synthetic", is_demo_data: true };

export default async function ChroniclePage() {
  const t = await getTranslations("worldChronicle");
  const tw = await getTranslations("world");

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={ROW_PROVENANCE}
        title={t("title")}
      />

      <section className="chronicle__sources" aria-labelledby="chronicle-sources-title">
        <span className="eyebrow">{t("sourcesTitle")}</span>
        <p style={{ marginTop: "0.4rem" }}>{t("sourcesBody")}</p>
        <p className="mono" style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "var(--text-2)" }}>
          <Link className="world-link" href="/world/gazette">gazette</Link>
          {" · "}
          <Link className="world-link" href="/world/champions">champions</Link>
          {" · "}
          <Link className="world-link" href="/world/records">records</Link>
          {" · "}
          <Link className="world-link" href="/world/dynasties">dynasties</Link>
        </p>
      </section>

      <ChronicleReadPanel />

      <Provenance provenance={ROW_PROVENANCE} />
    </div>
  );
}
