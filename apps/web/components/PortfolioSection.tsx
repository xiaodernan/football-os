import { Panel } from "@/components/ui";
import { figureText, itemColumns, type PortfolioSection } from "@/lib/portfolio";

/** One §38 section, rendered from the shape the API sent rather than from a section-specific TSX branch. */
export function PortfolioSectionPanel({ section }: { section: PortfolioSection }) {
  const figures = section.figures ?? {};
  const names = Object.keys(figures);
  const formulas = section.formulas ?? {};
  const items = section.items ?? [];
  const columns = itemColumns(items);
  return (
    <Panel eyebrow={`${section.source || "no source published"} · origin ${section.data_origin}`} title={section.title}>
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
