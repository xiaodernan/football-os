import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { PortfolioSectionPanel } from "@/components/PortfolioSection";
import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import type { PortfolioPublicCv } from "@/lib/portfolio";
import { absolute } from "@/lib/site";
import { serverFetch } from "@/lib/server";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ token: string }> };

/** A link is handed to a person, not advertised to a crawler. The token is still the credential. */
export const metadata: Metadata = {
  title: "Shared Football CV",
  description: "A live, read-only Football CV whose owner published a selected set of sections by link.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/portfolio") },
};

export default async function SharedPortfolioPage({ params }: Props) {
  const { token } = await params;
  const tn = await getTranslations("nav");
  const result = await serverFetch<PortfolioPublicCv>(`/portfolio/share/${encodeURIComponent(token)}`);

  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable detail={result.error.message} message="The shared CV door did not answer, so this link cannot be rendered." title="Shared Football CV" />;
  }

  const cv = result.data;
  const playerLine = cv.player
    ? [cv.player.name, cv.player.position, cv.player.data_origin].filter(Boolean).join(" · ")
    : "No player row was available when this CV was read.";

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={`${cv.counts.sections} published section${cv.counts.sections === 1 ? "" : "s"} · ${cv.counts.filled} filled · live read`}
        lede="This page is rebuilt from the owning account's rows every time it is opened. It is not a snapshot, and the sections the owner did not publish are not part of it."
        title="Shared Football CV"
      />

      <Panel eyebrow={playerLine} title="Who this CV describes">
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          <li className="muted" style={{ fontSize: "0.86rem" }}>published sections · <span className="mono">{cv.published_sections.join(" → ") || "(none)"}</span></li>
          <li className="muted" style={{ fontSize: "0.86rem" }}>link opened · <span className="mono">{cv.opened_at?.slice(0, 16) ?? "unknown"}</span></li>
          <li className="muted" style={{ fontSize: "0.86rem" }}>the account block and identifying player fields are omitted by the door, not hidden by this page.</li>
        </ul>
      </Panel>

      {cv.withheld.length > 0 && (
        <Panel eyebrow={`${cv.withheld.length} section${cv.withheld.length === 1 ? "" : "s"} withheld`} title="Not published on this link">
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
        <Panel eyebrow={`${Object.keys(cv.formulas).length} expressions · every published figure names one`} title="How each figure is folded">
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
        Need a CV of your own? <Link className="world-link" href="/portfolio">Open your Football CV</Link>.
      </p>
    </div>
  );
}
