import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead } from "@/components/world";
import { ManualAskPanel } from "@/components/ManualAskPanel";
import { pageMetadata } from "@/lib/site";
import type { RowProvenance } from "@/components/world";
import "@/styles/manual-ask.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("manual");
  return pageMetadata({
    title: t("askMetaTitle"),
    description: t("askMetaDescription"),
    path: "/manual/ask",
  });
}

const ROW_PROVENANCE: RowProvenance = { data_origin: "synthetic", is_demo_data: true };

export default async function ManualAskPage() {
  const t = await getTranslations("manual");

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/manual", label: t("askBackLabel") }}
        eyebrow={t("askEyebrow")}
        lede={t("askLede")}
        provenance={ROW_PROVENANCE}
        title={t("askTitle")}
      />

      <ManualAskPanel />

      <Provenance provenance={ROW_PROVENANCE} extra={<Link className="chip mono world-link" href="/manual">{t("askBackLabel")}</Link>} />
    </div>
  );
}
