import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { PortfolioSectionPanel } from "@/components/PortfolioSection";
import { PortfolioSharePanel } from "@/components/PortfolioSharePanel";
import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import type { PortfolioCv, PortfolioRules, PortfolioShareLedger } from "@/lib/portfolio";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";

import "../../styles/tactics.css";

export const dynamic = "force-dynamic";

/**
 * §38's Football CV: ten sections, each one a read of rows another tier owns.
 *
 * Private for the plain reason — a CV is a person's record — while the vocabulary it is assembled from is
 * published at the rules door, which needs no account and is fetched here anyway so the page can hold its own
 * order against the order the tier publishes.
 *
 * Three things this page refuses to invent:
 *
 * * a section the build cannot fill is printed with **the reason the door sent**, plus the tables it would have
 *   to hold the rows. No `0`, no blank table, no omission — dropping `Matches` and `Stats` would make the CV look
 *   complete, and zero would make it look measured;
 * * a figure is the door's value at the moment of the read. `null` stays `null`, because that is the tier saying
 *   the formula had no rows to fold, and the page re-reads both doors on every request (`force-dynamic`), so a
 *   number cannot go stale here — there is nothing to cache it in;
 * * the three outputs §38 permits publicly are listed with the state the rules door publishes. Each now names the
 *   door that serves it, including the owner-authenticated PDF rendered from this same live read.
 */
export async function generateMetadata(): Promise<Metadata> {
  const tn = await getTranslations("nav");
  const td = await getTranslations("portfolio");
  return {
    title: tn("footballCv"),
    description: td("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/portfolio") },
  };
}

export default async function PortfolioPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fportfolio");

  const tn = await getTranslations("nav");
  const td = await getTranslations("portfolio");
  const [rules, cv, shares] = await Promise.all([
    serverFetch<PortfolioRules>("/portfolio/rules"),
    serverFetch<PortfolioCv>("/portfolio/cv"),
    serverFetch<PortfolioShareLedger>("/portfolio/shares"),
  ]);
  if (!rules.ok) return <WorldUnavailable detail={rules.error.message} message={td("rulesUnavailable")} title={tn("footballCv")} />;
  if (!cv.ok) return <WorldUnavailable detail={cv.error.message} message={td("cvUnavailable")} title={tn("footballCv")} />;

  const publishedOrder = rules.data.sections.map(row => row.section).join(" → ");
  const paintedOrder = cv.data.sections.map(row => row.section).join(" → ");
  const orderAgrees = publishedOrder === paintedOrder;
  const origins = [...new Set(cv.data.sections.map(row => row.data_origin))].sort();

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: tn("home") }}
        eyebrow={td("eyebrow", {
          name: cv.data.account.display_name,
          filled: cv.data.counts.filled,
          total: cv.data.counts.sections,
        })}
        lede={td("lede")}
        title={tn("footballCv")}
      />

      <Panel
        eyebrow={
          cv.data.has_player
            ? td("playerRow", { id: cv.data.player?.id ?? "", visibility: cv.data.player?.visibility ?? "" })
            : td("noPlayerRow")
        }
        title={td("whoseTitle")}
      >
        {cv.data.has_player ? (
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            <li className="muted" style={{ fontSize: "0.86rem" }}>{td("rowName", { value: cv.data.player?.name ?? "" })}</li>
            <li className="muted" style={{ fontSize: "0.86rem" }}>{td("rowPosition", { value: cv.data.player?.position ?? "" })}</li>
            <li className="muted" style={{ fontSize: "0.86rem" }}>{td("rowOrigin", { value: cv.data.player?.data_origin ?? "" })}</li>
          </ul>
        ) : (
          <p className="muted" style={{ fontSize: "0.86rem" }}>
            {cv.data.sections.find(row => row.section === "position")?.missing_because ?? ""}{" "}
            <Link className="world-link" href="/my-football">
              {td("openPlayerIdentity")}
            </Link>
            .
          </p>
        )}
      </Panel>

      <PortfolioSharePanel
        initialFault={shares.ok ? "" : `${shares.error.code}: ${shares.error.message}`}
        initialLedger={shares.ok ? shares.data : null}
        rules={rules.data}
      />

      <Panel eyebrow={td("pdfEyebrow")} title={td("pdfTitle")}>
        <div className="row wrap" style={{ alignItems: "center", gap: "0.75rem" }}>
          <a className="btn btn--primary" data-portfolio-cv-pdf download href="/api/v1/portfolio/cv.pdf">
            {td("downloadCv")}
          </a>
          <span className="muted" style={{ fontSize: "0.84rem" }}>
            {td("pdfNote")}
          </span>
        </div>
      </Panel>

      <Panel
        eyebrow={td("orderEyebrow", {
          sections: cv.data.counts.sections,
          filled: cv.data.counts.filled,
          unfilled: cv.data.counts.unfilled.length,
          origins: origins.join(" · "),
        })}
        title={td("orderTitle")}
      >
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {orderAgrees ? td("orderAgrees") : td("orderDiffers")}
          <span className="mono">{paintedOrder}</span>
        </p>
        {cv.data.counts.unfilled.length > 0 && (
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            {td("notFilled", { sections: cv.data.counts.unfilled.join(", ") })}
          </p>
        )}
      </Panel>

      {cv.data.sections.map(section => (
        <PortfolioSectionPanel key={section.section} section={section} />
      ))}

      <Panel
        eyebrow={td("publicEyebrow", {
          count: Object.keys(rules.data.public_outputs).length,
          absent: Object.values(rules.data.public_outputs).filter(line => line.startsWith("not in this build")).length,
        })}
        title={td("publicTitle")}
      >
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{td("thOutput")}</th>
                <th scope="col">{td("thState")}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(rules.data.public_outputs).map(([name, state]) => (
                <tr data-output={name} key={name}>
                  <td className="mono">{name}</td>
                  <td className="muted">{state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel
        eyebrow={td("formulasEyebrow", { count: Object.keys(cv.data.formulas).length })}
        title={td("formulasTitle")}
      >
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {Object.entries(cv.data.formulas).map(([name, expression]) => (
            <li className="muted" data-formula={name} key={name} style={{ fontSize: "0.85rem" }}>
              <span className="mono">{name}</span> · {expression}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel
        eyebrow={td("refusalsEyebrow", {
          count: Object.keys(rules.data.refusal_answers).length,
          doors: rules.data.routes.length,
        })}
        title={td("refusalsTitle")}
      >
        <p className="muted" style={{ fontSize: "0.86rem" }}>
          {Object.keys(rules.data.refusal_answers).length === 0
            ? td("noRefusalCodes")
            : td("refusalCodes")}
        </p>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{td("thMethod")}</th>
                <th scope="col">{td("thPath")}</th>
                <th scope="col">{td("thDoor")}</th>
              </tr>
            </thead>
            <tbody>
              {rules.data.routes.map(route => (
                <tr data-door={route.path} key={`${route.method} ${route.path}`}>
                  <td className="mono">{route.method}</td>
                  <td className="mono">{route.path}</td>
                  <td className="muted">{route.door}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <p className="muted" style={{ fontSize: "0.84rem" }}>{cv.data.limitation}</p>
    </div>
  );
}
