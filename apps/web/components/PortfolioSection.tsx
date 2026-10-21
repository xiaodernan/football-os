import { Panel } from "@/components/ui";
import { useTranslations } from "next-intl";
import { figureText, itemColumns, type PortfolioSection } from "@/lib/portfolio";

/** One §38 section, rendered from the shape the API sent rather than from a section-specific TSX branch. */
export function PortfolioSectionPanel({ section }: { section: PortfolioSection }) {
const td = useTranslations("portfolio");
  const figures = section.figures ?? {};
  const names = Object.keys(figures);
  const formulas = section.formulas ?? {};
  const items = section.items ?? [];
  const columns = itemColumns(items);
  return (
    <Panel eyebrow={td("originLine", { source: section.source || td("noSourcePublished"), origin: section.data_origin })} title={section.title}>
      <div data-available={String(section.available)} data-section={section.section}>
        {section.available ? (
          names.length === 0 && items.length === 0 ? (
            <p className="muted" style={{ fontSize: "0.85rem" }}>{td("sectionFilledNoRows")}</p>
          ) : (
            <>
              {names.length > 0 && (
                <div className="world-tablewrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th scope="col">{td("thFigure")}</th>
                        <th scope="col">{td("thValue")}</th>
                        <th scope="col">{td("thFormula")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {names.map(name => (
                        <tr data-figure={name} key={name}>
                          <td className="mono">{name}</td>
                          <td className="num">{figureText(figures[name])}</td>
                          <td className="muted">{formulas[name] ?? td("printedForSection")}</td>
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
              <strong>{td("notFilledInBuild")}</strong> {section.missing_because ?? ""}
            </p>
            <p className="muted" style={{ fontSize: "0.84rem" }}>
              {td("wouldBeReadFrom")} <span className="mono">{section.would_be_read_from ?? td("noTablePublished")}</span>
            </p>
          </div>
        )}
      </div>
    </Panel>
  );
}
