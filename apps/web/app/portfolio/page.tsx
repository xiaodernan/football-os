import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import { figureText, itemColumns, type PortfolioCv, type PortfolioRules, type PortfolioSection } from "@/lib/portfolio";
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
 * * the three outputs §38 permits publicly are listed with their state, which in this build is *absent* for all
 *   three. Nothing on this screen is a public profile, a share link or a PDF.
 */
export const metadata: Metadata = {
  title: "Football CV",
  description: "The ten sections of your football CV, each read from the rows that already exist, and the two this build cannot fill.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/portfolio") },
};

function SectionPanel({ section }: { section: PortfolioSection }) {
  const figures = section.figures ?? {};
  const names = Object.keys(figures);
  const formulas = section.formulas ?? {};
  const items = section.items ?? [];
  const columns = itemColumns(items);
  return (
    <Panel
      eyebrow={`${section.source || "no source published"} · origin ${section.data_origin}`}
      title={section.title}
    >
      <div data-available={String(section.available)} data-section={section.section}>
        {section.available ? (
          names.length === 0 && items.length === 0 ? (
            <p className="muted" style={{ fontSize: "0.85rem" }}>This section is filled and its source answers with no rows and no figure yet.</p>
          ) : (
            <>
              {names.length > 0 && (
                <div className="world-tablewrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th scope="col">Figure</th>
                        <th scope="col">Value</th>
                        <th scope="col">Formula</th>
                      </tr>
                    </thead>
                    <tbody>
                      {names.map(name => (
                        <tr data-figure={name} key={name}>
                          <td className="mono">{name}</td>
                          <td className="num">{figureText(figures[name])}</td>
                          <td className="muted">{formulas[name] ?? "printed by the CV door for the section as a whole"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {columns.length > 0 && (
                <div className="world-tablewrap">
                  <table className="table">
                    <thead>
                      <tr>
                        {columns.map(column => (
                          <th scope="col" key={column}>
                            {column}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((row, index) => (
                        <tr data-item={index} key={index}>
                          {columns.map(column => (
                            <td className="mono" key={column}>
                              {figureText(row[column])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )
        ) : (
          <div className="stack-sm">
            <p className="muted" style={{ fontSize: "0.86rem" }}>
              <strong>Not filled in this build.</strong> {section.missing_because ?? ""}
            </p>
            <p className="muted" style={{ fontSize: "0.84rem" }}>
              Would be read from: <span className="mono">{section.would_be_read_from ?? "no table published"}</span>
            </p>
          </div>
        )}
      </div>
    </Panel>
  );
}

export default async function PortfolioPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fportfolio");

  const [rules, cv] = await Promise.all([
    serverFetch<PortfolioRules>("/portfolio/rules"),
    serverFetch<PortfolioCv>("/portfolio/cv"),
  ]);
  if (!rules.ok) return <WorldUnavailable detail={rules.error.message} message="The CV rulebook door did not answer, so this page has no vocabulary to render against." title="Football CV" />;
  if (!cv.ok) return <WorldUnavailable detail={cv.error.message} message="The CV door did not answer, so there is nothing to print." title="Football CV" />;

  const publishedOrder = rules.data.sections.map(row => row.section).join(" → ");
  const paintedOrder = cv.data.sections.map(row => row.section).join(" → ");
  const orderAgrees = publishedOrder === paintedOrder;
  const origins = [...new Set(cv.data.sections.map(row => row.data_origin))].sort();

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/", label: "Home" }}
        eyebrow={`${cv.data.account.display_name} · ${cv.data.counts.filled} of ${cv.data.counts.sections} sections filled`}
        lede="A CV in this build stores nothing: each of the ten sections is a read of rows another tier already writes, counted from the formula printed beside it at the moment you ask. Two of the ten cannot be filled here, and they print the reason and the tables they would need rather than a zero."
        title="Football CV"
      />

      <Panel eyebrow={cv.data.has_player ? `player ${cv.data.player?.id} · visibility ${cv.data.player?.visibility}` : "no player row on this account yet"} title="Whose CV this is">
        {cv.data.has_player ? (
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
            <li className="muted" style={{ fontSize: "0.86rem" }}>name · {cv.data.player?.name}</li>
            <li className="muted" style={{ fontSize: "0.86rem" }}>position · {cv.data.player?.position}</li>
            <li className="muted" style={{ fontSize: "0.86rem" }}>origin of the rows · {cv.data.player?.data_origin}</li>
          </ul>
        ) : (
          <p className="muted" style={{ fontSize: "0.86rem" }}>
            {cv.data.sections.find(row => row.section === "position")?.missing_because ?? ""}{" "}
            <Link className="world-link" href="/my-football">
              Open your player identity
            </Link>
            .
          </p>
        )}
      </Panel>

      <Panel eyebrow={`${cv.data.counts.sections} sections · ${cv.data.counts.filled} filled · ${cv.data.counts.unfilled.length} not filled · ${origins.join(" · ")}`} title="Order, and what is missing">
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {orderAgrees
            ? "The CV arrives in the same order the rules door publishes its sections in: "
            : "The CV arrives in a different order than the rules door publishes: "}
          <span className="mono">{paintedOrder}</span>
        </p>
        {cv.data.counts.unfilled.length > 0 && (
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            Not filled: <span className="mono">{cv.data.counts.unfilled.join(", ")}</span>
          </p>
        )}
      </Panel>

      {cv.data.sections.map(section => (
        <SectionPanel key={section.section} section={section} />
      ))}

      <Panel eyebrow={`${Object.keys(rules.data.public_outputs).length} outputs §38 permits · ${Object.values(rules.data.public_outputs).filter(line => line.startsWith("not in this build")).length} absent from this build`} title="What §38 allows to be public">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Output</th>
                <th scope="col">State</th>
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

      <Panel eyebrow={`${Object.keys(cv.data.formulas).length} expressions · every counted figure names one`} title="How each figure is folded">
        <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {Object.entries(cv.data.formulas).map(([name, expression]) => (
            <li className="muted" data-formula={name} key={name} style={{ fontSize: "0.85rem" }}>
              <span className="mono">{name}</span> · {expression}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel eyebrow={`${Object.keys(rules.data.refusal_answers).length} refusal code(s) · ${rules.data.routes.length} doors`} title="What a door here refuses">
        <p className="muted" style={{ fontSize: "0.86rem" }}>
          {Object.keys(rules.data.refusal_answers).length === 0
            ? "This tier registers no refusal code in the project’s one answer table: the only question a door asks is whether the caller has a session, and a section with no rows behind it is an answer, not a refusal."
            : "Every code this tier publishes answers with the status the one table gives it."}
        </p>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Method</th>
                <th scope="col">Path</th>
                <th scope="col">Door</th>
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
