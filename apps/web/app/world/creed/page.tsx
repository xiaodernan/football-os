import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/records.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldCreed");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/creed",
  });
}

export default async function CreedPage() {
  const t = await getTranslations("worldCreed");
  const tw = await getTranslations("world");

  const world = await readWorld<WorldEnvelope>("/world/status");
  if (!world.ok) return <WorldUnavailable message={world.message} />;

  const articles = [
    { eyebrow: t("a1Eyebrow"), title: t("a1Title"), body: t("a1Body"), href: "/world", linkLabel: t("a1Link") },
    { eyebrow: t("a2Eyebrow"), title: t("a2Title"), body: t("a2Body"), href: "/world/real-book", linkLabel: t("a2Link") },
    { eyebrow: t("a3Eyebrow"), title: t("a3Title"), body: t("a3Body"), href: "/world/champions", linkLabel: t("a3Link") },
    { eyebrow: t("a4Eyebrow"), title: t("a4Title"), body: t("a4Body"), href: "/world/almanac", linkLabel: t("a4Link") },
    { eyebrow: t("a5Eyebrow"), title: t("a5Title"), body: t("a5Body"), href: "/manual", linkLabel: t("a5Link") },
    { eyebrow: t("a6Eyebrow"), title: t("a6Title"), body: t("a6Body"), href: "/settings", linkLabel: t("a6Link") },
  ];

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={world.data}
        title={t("title")}
      />

      {articles.map((article) => (
        <section className="records__panel" key={article.title}>
          <span className="records__panel-eyebrow">{article.eyebrow}</span>
          <h2>{article.title}</h2>
          <p className="records__lede muted">{article.body}</p>
          <p className="records__chip-row">
            <Link href={article.href} className="records__link">
              {article.linkLabel} <span aria-hidden="true">→</span>
            </Link>
          </p>
        </section>
      ))}

      <p className="records__ledger muted">{t("footerClaim")}</p>

      <Provenance provenance={world.data} />
    </div>
  );
}
