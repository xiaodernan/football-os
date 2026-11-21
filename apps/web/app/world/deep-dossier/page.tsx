import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead } from "@/components/world";
import { DeepDossierPanel } from "@/components/DeepDossierPanel";
import { pageMetadata } from "@/lib/site";
import type { RowProvenance } from "@/components/world";
import "@/styles/deep-dossier.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldDossier");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/deep-dossier",
  });
}

const PROVENANCE: RowProvenance = { data_origin: "synthetic", is_demo_data: true };

export default async function DeepDossierPage() {
  const t = await getTranslations("worldDossier");

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: t("backWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={PROVENANCE}
        title={t("title")}
      />

      <DeepDossierPanel />

      <Provenance
        provenance={PROVENANCE}
        extra={<Link className="chip mono world-link" href="/world">{t("backWorld")}</Link>}
      />
    </div>
  );
}
