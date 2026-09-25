import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { ScoutWorkbench } from "@/components/ScoutWorkbench";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { ScoutRulesView } from "@/lib/scout";

import "../../styles/tactics.css";
import "../../styles/world.css";

export const dynamic = "force-dynamic";

/**
 * The §23–§27 scouting screen. `/scout/rules` is public and this page reads it, but the same screen searches
 * the stored player table, builds a §24 report and forms a §27 pair, and all three need an account — so the
 * page is private and unpublished, exactly like `/career`, `/challenges` and `/market`.
 */
export const metadata: Metadata = {
  title: "AI Scout",
  description: "Search a generated world in your own words, read a report whose every line names its row, and compare a pair across ten dimensions with no overall score to hide behind.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/scout") },
};

export default async function ScoutPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fscout");

  const rules = await serverFetch<ScoutRulesView>("/scout/rules");
  if (!rules.ok) {
    return <WorldUnavailable eyebrow="AI Scout" message={rules.error.message} title="AI Scout" />;
  }
  const data = rules.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: "Football world" }}
        eyebrow={`${user.display_name} · searching, reporting and comparing are private to your account`}
        lede="A sentence in, a cut out. The parser tells you which phrases it understood and which it refused, the waterfall tells you how many rows each cut removed, the report answers thirteen fields with figures recomputed from the stored row, and a comparison answers ten dimensions without ever forming the one number the spec rules out."
        provenance={{ data_origin: data.data_origin, is_demo_data: data.is_demo_data, disclaimer: data.disclaimer }}
        title="AI Scout"
      />

      {data.integrity.clean ? (
        <p className="notice">
          The scout passes its own integrity check: the vocabulary agrees with itself, every requirement kind the parser emits is answered by the search, a report builds over the stored pool, and a pair of stored rows
          answers §27&rsquo;s ten dimensions. <span className="mono">problems: {data.integrity.problems.length}</span>
        </p>
      ) : (
        <ul className="notice notice--warn">
          {data.integrity.problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}

      <ScoutWorkbench rules={data} />

      <Panel eyebrow={`${Object.keys(data.positions).length} positions · ${Object.keys(data.bands).length} engine bands · ${Object.keys(data.roles).length} roles · ${data.attributes.length} attributes`} title="What this vocabulary understands">
        <div className="stack-sm">
          <div className="tac-cards">
            <div className="tac-card">
              <strong>Positions</strong>
              <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
                {Object.entries(data.positions).map(([code, entry]) => (
                  <li key={code}>
                    <span className="chip mono">{code}</span> {entry.label} <span className="muted mono">{entry.band}</span>
                  </li>
                ))}
              </ul>
              {data.positions_the_engine_names_and_the_world_does_not_staff.length > 0 && (
                <p className="muted">
                  The engine names <span className="mono">{data.positions_the_engine_names_and_the_world_does_not_staff.join(", ")}</span>, but no stored row is filed under them, so a search for those codes answers empty
                  rather than wrong.
                </p>
              )}
            </div>
            <div className="tac-card">
              <strong>Bands</strong>
              {Object.entries(data.band_vocabularies).map(([vocabulary, entry]) => (
                <div key={vocabulary}>
                  <span className="chip mono">{vocabulary}</span>
                  <div className="muted mono">{entry.keys.join(" · ")}</div>
                  <div className="muted">{entry.meaning}</div>
                </div>
              ))}
              {data.roles_no_stored_position_occupies.length > 0 && (
                <p className="muted">
                  Roles no stored position occupies: <span className="mono">{data.roles_no_stored_position_occupies.join(", ")}</span>
                </p>
              )}
            </div>
          </div>
          <KeyValueGrid
            rows={[
              ["Stated fields", data.fields.join(" · ")],
              ["Sortings", data.sorts.join(" · ")],
              ["Feet", data.feet.join(" · ")],
              ["Search limits", `${data.search.default_limit} by default, ${data.search.max_limit} at most`],
              ["Connectors ignored", `${data.connector_count} phrases (articles, fillers and conjunctions in six languages)`],
            ]}
          />
          <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
            {Object.entries(data.rules).map(([key, sentence]) => (
              <li className="muted" key={key}>
                <span className="mono">{key}</span> — {sentence}
              </li>
            ))}
          </ul>
          <p className="muted">
            Example: <span className="mono">{JSON.stringify(data.example)}</span>
          </p>
        </div>
      </Panel>

      <Panel eyebrow="§23 · a list that stores membership · §24 · thirteen fields · §27 · ten dimensions" title="What the shortlist, the report and the comparison promise">
        <div className="stack-sm">
          <KeyValueGrid
            rows={[
              ["Shortlist caps", `${data.shortlists.max_shortlists_per_user} lists per account · ${data.shortlists.max_items_per_shortlist} players each · ${data.shortlists.name_max}-character names · ${data.shortlists.note_max}-character notes`],
              ["A list stores", data.shortlists.stored],
              ["A list does not store", data.shortlists.not_stored],
              ["Why not", data.shortlists.why_not],
              ["Re-read on every visit", data.shortlists.rechecked_on_read],
              ["Report fields", data.report.fields.join(" · ")],
              ["Verdicts the ladder can produce", data.report.verdicts.join(" · ")],
              ["Report refusals", Object.entries(data.report.refusals).map(([code, sentence]) => `${code}: ${sentence}`).join(" · ")],
              ["Comparison dimensions", data.comparison.dimensions.join(" · ")],
              ["Measure leaders", data.comparison.measure_leaders.join(" · ")],
              ["Dimension leaders", data.comparison.dimension_leaders.join(" · ")],
              ["Stat columns summed for the rates", data.comparison.stat_columns.join(" · ")],
            ]}
          />
          <p className="notice">{data.comparison.no_single_score}</p>
          <p className="muted">{data.report.note}</p>
          <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
            {[...data.search.limits, ...data.shortlists.limitations, ...data.report.limitations, ...data.comparison.limitations].map((line) => (
              <li className="muted" key={line}>
                {line}
              </li>
            ))}
          </ul>
          <p className="muted mono">{JSON.stringify(data.routes)}</p>
        </div>
      </Panel>

      <Provenance provenance={{ data_origin: data.data_origin, is_demo_data: data.is_demo_data, disclaimer: data.disclaimer }} />
    </div>
  );
}
