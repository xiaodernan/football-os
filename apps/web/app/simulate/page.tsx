import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { SimulatorForm } from "@/components/SimulatorForm";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimList, SimOptions } from "@/lib/types";

import "../../styles/tactics.css";
import "../../styles/simulate.css";

export const dynamic = "force-dynamic";

/**
 * A simulation is model output about fictional clubs, and which fixtures an account chooses to play
 * is the account's own, so this page is not published: `robots: noindex`, disallowed in robots.ts, and
 * absent from the sitemap. The clubs and systems it offers are already public under `/world` and
 * `/tactics`; nothing new is exposed by the picker, and nothing here can be indexed as a fact.
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("simulate");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/simulate") },
  };
}

export default async function SimulateIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fsimulate");

  const t = await getTranslations("simulate");
  const tn = await getTranslations("nav");
  const [choices, played] = await Promise.all([
    serverFetch<SimOptions>("/simulate/options"),
    serverFetch<SimList>("/simulate"),
  ]);
  if (!choices.ok) {
    return <WorldUnavailable eyebrow={t("metaTitle")} message={choices.error.message} title={t("metaTitle")} />;
  }
  const options = choices.data;
  if (!options.ready) {
    return (
      <WorldUnavailable
        eyebrow={t("metaTitle")}
        message={t("worldNotReady")}
        title={t("metaTitle")}
      />
    );
  }

  const engine = options.engine;
  const listing = played.ok ? played.data : null;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/my-football", label: tn("myFootball") }}
        eyebrow={t("headEyebrow", { name: user.display_name })}
        lede={t("headLede")}
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: options.disclaimer }}
        title={t("metaTitle")}
      />

      <Panel eyebrow={t("playEyebrow", { teams: options.teams.length, systems: options.systems.length })} title={t("playTitle")}>
        <SimulatorForm options={options} />
      </Panel>

      <Panel eyebrow={engine.version} title={t("modelTitle")}>
        <div className="stack">
          <p className="notice">{engine.calibration}</p>
          <div className="grid grid-2">
            <KeyValueGrid
              rows={[
                [t("kvEngine"), <span className="mono" key="engine">{engine.name}</span>],
                [t("kvBlockLength"), `${engine.block_minutes}'`],
                [t("kvLengths"), engine.minute_choices.map((choice) => `${choice}'`).join(" · ")],
                [t("kvInputsFrom"), <span className="mono" key="inputs">{engine.inputs_are_from.join(", ")}</span>],
              ]}
            />
            <KeyValueGrid
              rows={[
                [t("kvSystems"), String(options.systems.length)],
                [t("kvClubs"), String(options.teams.length)],
                [t("kvRates"), String(engine.factors.length)],
                [
                  t("kvKept"),
                  listing ? `${listing.total} of ${listing.limit_per_user}` : t("notRead"),
                ],
              ]}
            />
          </div>
          <div className="stack-sm">
            <span className="eyebrow">{t("ratesEyebrow")}</span>
            <div className="world-tablewrap">
              <table className="table" data-testid="sim-rates">
                <thead>
                  <tr>
                    <th scope="col">{t("thRate")}</th>
                    <th scope="col">{t("thExpression")}</th>
                    <th scope="col">{t("thReads")}</th>
                  </tr>
                </thead>
                <tbody>
                  {engine.factors.map((factor) => (
                    <tr key={factor.key}>
                      <td className="mono">{factor.key}</td>
                      <td className="tac-formula">{factor.expression}</td>
                      <td className="muted">{factor.reads}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="muted world-section-note">
            {t.rich("scorelineNote", { link: (chunks) => <Link className="world-link" href="/knowledge">{chunks}</Link> })}
          </p>
        </div>
      </Panel>

      <Panel
        action={
          <Link className="btn btn--ghost btn--sm" href="/career">
            {t("runSeason")}
          </Link>
        }
        eyebrow={listing ? t("keptEyebrow", { total: listing.total, limit: listing.limit_per_user }) : t("notRead")}
        title={t("matchesTitle")}
      >
        {!listing ? (
          <p className="notice notice--warn">
            {t("listError", { detail: played.ok ? t("reportNoList") : `${played.error.code}: ${played.error.message}` })}
          </p>
        ) : listing.items.length === 0 ? (
          <div className="empty">
            <strong>{t("emptyTitle")}</strong>
            <span className="muted">{t("emptyBody")}</span>
          </div>
        ) : (
          <section className="tac-cards">
            {listing.items.map((match) => (
              <Link className="tac-card" href={match.path} key={match.id}>
                <span className="tac-card__name">
                  {match.home_summary.short_name} {match.score.home} – {match.score.away} {match.away_summary.short_name}
                </span>
                <span className="tac-card__meta">
                  {t("matchMeta", { minutes: match.minutes, home: match.home_summary.name, away: match.away_summary.name })}
                </span>
                <div className="tac-card__metrics">
                  <span className="chip num">{t("xgLine", { home: match.home_summary.expected_goals, away: match.away_summary.expected_goals })}</span>
                  <span className="chip num">{t("shotsLine", { home: match.home_summary.shots, away: match.away_summary.shots })}</span>
                  <span className="chip mono" title={t("seedTitle")}>
                    {t("seedChip", { seed: match.seed })}
                  </span>
                  <span className="chip mono">{match.digest}</span>
                </div>
              </Link>
            ))}
          </section>
        )}
      </Panel>

      <Provenance
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: options.disclaimer }}
        extra={<span className="chip">{t("provenanceExtra")}</span>}
      />
    </div>
  );
}
