import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { PortfolioSectionPanel } from "@/components/PortfolioSection";
import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import type { PortfolioPublicCv } from "@/lib/portfolio";
import { sharedMetadata } from "@/lib/site";
import { serverFetch } from "@/lib/server";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ token: string }> };

/**
 * A link is handed to a person, not advertised to a crawler, and the token is still the credential — so noindex,
 * and the canonical belongs to `/portfolio`. What this page did not have until §109 was an `openGraph` of its own:
 * with none it inherited the root layout's site-level block, so the card a reader saw before clicking said
 * "FOOTBALL OS" and the site's tagline rather than naming the CV they had been sent to.
 */
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params;
  const td = await getTranslations("portfolio");
  return sharedMetadata({
    title: td("sharedMetaTitle"),
    description: td("sharedMetaDescription"),
    sharePath: `/portfolio/shared/${encodeURIComponent(token)}`,
    canonicalPath: "/portfolio",
  });
}

export default async function SharedPortfolioPage({ params }: Props) {
  const { token } = await params;
  const tn = await getTranslations("nav");
  const td = await getTranslations("portfolio");
  const result = await serverFetch<PortfolioPublicCv>(`/portfolio/share/${encodeURIComponent(token)}`);

  if (!result.ok) {
    if (result.status === 404) notFound();
    return (
      <WorldUnavailable
        detail={result.error.message}
        message={td("sharedUnavailable")}
        title={td("sharedUnavailableTitle")}
      />
    );
  }

  const cv = result.data;
  const playerLine = cv.player
    ? [cv.player.name, cv.player.position, cv.player.data_origin].filter(Boolean).join(" · ")
    : td("sharedNoPlayer");

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={td("sharedEyebrow", {
          sections: cv.counts.sections,
          filled: cv.counts.filled,
        })}
        lede={td("sharedLede")}
        title={td("sharedTitle")}
      />

      <Panel eyebrow={playerLine} title={td("whoTitle")}>
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            <li className="muted" style={{ fontSize: "0.86rem" }}>
              {td("publishedSections", { sections: cv.published_sections.join(" → ") || "(none)" })}
            </li>
            <li className="muted" style={{ fontSize: "0.86rem" }}>
              {td("linkOpened", { opened: cv.opened_at?.slice(0, 16) ?? "unknown" })}
            </li>
            <li className="muted" style={{ fontSize: "0.86rem" }}>{td("omittedNote")}</li>
        </ul>
      </Panel>

      {cv.withheld.length > 0 && (
        <Panel
          eyebrow={td("withheldEyebrow", { count: cv.withheld.length })}
          title={td("withheldTitle")}
        >
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {cv.withheld.map((row) => (
              <li className="muted" key={row.section} style={{ fontSize: "0.86rem" }}>
                <span className="mono">{row.section}</span> · {row.title} · {row.reason}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {cv.sections.map((section) => (
        <PortfolioSectionPanel key={section.section} section={section} />
      ))}

      {Object.keys(cv.formulas).length > 0 && (
        <Panel
          eyebrow={td("sharedFormulasEyebrow", { count: Object.keys(cv.formulas).length })}
          title={td("sharedFormulasTitle")}
        >
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {Object.entries(cv.formulas).map(([name, expression]) => (
              <li className="muted" key={name} style={{ fontSize: "0.85rem" }}>
                <span className="mono">{name}</span> · {expression}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <p className="muted" style={{ fontSize: "0.84rem" }}>{cv.limitation}</p>
      <p className="muted" style={{ fontSize: "0.84rem" }}>
        {td("needOwn")} <Link className="world-link" href="/portfolio">{td("openOwnCv")}</Link>.
      </p>
    </div>
  );
}
