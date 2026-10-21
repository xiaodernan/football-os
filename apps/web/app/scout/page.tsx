import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

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
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("scout");
  return {
    title: t("title"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/scout") },
  };
}

export default async function ScoutPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fscout");

  const rules = await serverFetch<ScoutRulesView>("/scout/rules");
  const t = await getTranslations("scout");
  if (!rules.ok) {
    return <WorldUnavailable eyebrow={t("title")} message={rules.error.message} title={t("title")} />;
  }
  const data = rules.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: t("backLabel") }}
        eyebrow={t("eyebrow", { name: user.display_name })}
        lede={t("lede")}
        provenance={{ data_origin: data.data_origin, is_demo_data: data.is_demo_data, disclaimer: data.disclaimer }}
        title={t("title")}
      />

      {data.integrity.clean ? (
        <p className="notice">
          {t("integrityNote")} <span className="mono">problems: {data.integrity.problems.length}</span>
        </p>
      ) : (
        <ul className="notice notice--warn">
          {data.integrity.problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}

      <ScoutWorkbench rules={data} />

      <Panel
        eyebrow={t("vocabularyEyebrow", {
          positions: Object.keys(data.positions).length,
          bands: Object.keys(data.bands).length,
          roles: Object.keys(data.roles).length,
          attributes: data.attributes.length,
        })}
        title={t("vocabularyTitle")}
      >
        <div className="stack-sm">
          <div className="tac-cards">
            <div className="tac-card">
              <strong>{t("positionsTitle")}</strong>
              <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
                {Object.entries(data.positions).map(([code, entry]) => (
                  <li key={code}>
                    <span className="chip mono">{code}</span> {entry.label} <span className="muted mono">{entry.band}</span>
                  </li>
                ))}
              </ul>
              {data.positions_the_engine_names_and_the_world_does_not_staff.length > 0 && (
          <p className="muted">
            {t("exampleNote", { example: JSON.stringify(data.example) })}
          </p>
              )}
            </div>
            <div className="tac-card">
              <strong>{t("bandsTitle")}</strong>
              {Object.entries(data.band_vocabularies).map(([vocabulary, entry]) => (
                <div key={vocabulary}>
                  <span className="chip mono">{vocabulary}</span>
                  <div className="muted mono">{entry.keys.join(" · ")}</div>
                  <div className="muted">{entry.meaning}</div>
                </div>
              ))}
              {data.roles_no_stored_position_occupies.length > 0 && (
                <p className="muted">
                  {t("rolesNote", {
                    roles: data.roles_no_stored_position_occupies.join(", "),
                  })}
                </p>
              )}
            </div>
          </div>
          <KeyValueGrid
            rows={[
              [t("rowStatedFields"), data.fields.join(" · ")],
              [t("rowSortings"), data.sorts.join(" · ")],
              [t("rowFeet"), data.feet.join(" · ")],
              [t("rowSearchLimits"), `${data.search.default_limit} by default, ${data.search.max_limit} at most`],
              [t("rowConnectorsIgnored"), `${data.connector_count} phrases (articles, fillers and conjunctions in six languages)`],
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
            {t("exampleNote", { example: JSON.stringify(data.example) })}
          </p>
        </div>
      </Panel>

      <Panel
        eyebrow={t("promiseEyebrow")}
        title={t("promiseTitle")}
      >
        <div className="stack-sm">
          <KeyValueGrid
            rows={[
              [t("rowShortlistCaps"), `${data.shortlists.max_shortlists_per_user} lists per account · ${data.shortlists.max_items_per_shortlist} players each · ${data.shortlists.name_max}-character names · ${data.shortlists.note_max}-character notes`],
              [t("rowListStores"), data.shortlists.stored],
              [t("rowListDoesNotStore"), data.shortlists.not_stored],
              [t("rowWhyNot"), data.shortlists.why_not],
              [t("rowReRead"), data.shortlists.rechecked_on_read],
              [t("rowReportFields"), data.report.fields.join(" · ")],
              [t("rowVerdicts"), data.report.verdicts.join(" · ")],
              [t("rowReportRefusals"), Object.entries(data.report.refusals).map(([code, sentence]) => `${code}: ${sentence}`).join(" · ")],
              [t("rowComparisonDimensions"), data.comparison.dimensions.join(" · ")],
              [t("rowMeasureLeaders"), data.comparison.measure_leaders.join(" · ")],
              [t("rowDimensionLeaders"), data.comparison.dimension_leaders.join(" · ")],
              [t("rowStatColumns"), data.comparison.stat_columns.join(" · ")],
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
