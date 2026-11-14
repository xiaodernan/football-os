import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { DuelRadar } from "@/components/DuelRadar";
import type { RadarAxis } from "@/components/DuelRadar";
import { Panel } from "@/components/ui";
import { EntityLink, Provenance, WorldUnavailable } from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { DuelResult } from "@/lib/types";

import "@/styles/duel.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ left: string; right: string }> };

async function load(left: string, right: string) {
  return readWorld<DuelResult>("/world/duel", { left, right });
}

/** Whole numbers print whole; a rating of 7.1 must not print as 7.10, and 7.25 must not print as 7. */
function figure(value: number | null): string {
  if (value === null) return "—";
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { left, right } = await params;
  const t = await getTranslations("duel");
  const result = await load(left, right);
  if (!result.ok) {
    return pageMetadata({
      title: t("metaTitleFallback"),
      description: t("metaDescriptionFallback"),
      path: `/world/duel/${left}/${right}`,
      images: [{ url: absolute(`/world/duel/${left}/${right}/opengraph-image`), width: 1200, height: 630, alt: t("metaTitleFallback") }],
    });
  }
  const { left: a, right: b, verdict } = result.data;
  const sharePath = `/world/duel/${a.player.slug}/${b.player.slug}/opengraph-image`;
  const images = [{ url: absolute(sharePath), width: 1200, height: 630, alt: t("metaTitle", { left: a.player.name, right: b.player.name }) }];
  return pageMetadata({
    title: t("metaTitle", { left: a.player.name, right: b.player.name }),
    description: t("metaDescription", {
      left: a.player.name,
      right: b.player.name,
      leftWins: verdict.left_wins,
      rightWins: verdict.right_wins,
    }),
    path: `/world/duel/${a.player.slug}/${b.player.slug}`,
    images,
  });
}

export default async function DuelPage({ params }: Props) {
  const { left, right } = await params;
  const t = await getTranslations("duel");
  const tw = await getTranslations("world");
  const result = await load(left, right);
  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable message={result.message} />;
  }

  const { left: a, right: b, categories, verdict, method } = result.data;

  // Static calls, dynamic lookup: a template key (`t(`cat_${key}`)`) is invisible to the i18n gates, which is how
  // a catalogue key ships that no page reads and no gate misses.
  const disciplineHint = t("hintDiscipline", { redWeight: method.red_weight });
  const copy = {
    goals: { label: t("catGoals"), hint: t("hintGoals") },
    assists: { label: t("catAssists"), hint: t("hintAssists") },
    involvement_per_90: { label: t("catInvolvement"), hint: t("hintInvolvement") },
    rating: { label: t("catRating"), hint: t("hintRating") },
    minutes: { label: t("catMinutes"), hint: t("hintMinutes") },
    overall: { label: t("catOverall"), hint: t("hintOverall") },
    discipline: { label: t("catDiscipline"), hint: disciplineHint },
  } as const;
  const basis = {
    season_total: t("basisSeasonTotal"),
    per_90: t("basisPer90"),
    season_mean: t("basisSeasonMean"),
    coach_rating: t("basisCoachRating"),
    weighted_cards: t("basisWeightedCards"),
  } as Record<string, string>;

  const axes: RadarAxis[] = Array.from(new Set([...Object.keys(a.attributes), ...Object.keys(b.attributes)]))
    .map((key) => ({
      key,
      label: key.replace(/_/g, " "),
      left: a.attributes[key] ?? 0,
      right: b.attributes[key] ?? 0,
    }))
    .sort((one, two) => Math.max(two.left, two.right) - Math.max(one.left, one.right))
    .slice(0, 6);

  const winnerName = verdict.winner === "left" ? a.player.name : verdict.winner === "right" ? b.player.name : null;
  const verdictLine =
    verdict.winner === "draw" ? t("verdictDraw") : t("verdictWin", { name: winnerName ?? "" });

  return (
    <div className="container page stack duel">
      <h1 className="duel__h1">{t("pageTitle", { left: a.player.name, right: b.player.name })}</h1>
      <div className="duel__arena">
        {(["left", "right"] as const).map((side) => {
          const player = side === "left" ? a : b;
          const won = verdict.winner === side;
          return (
            <div className={`duel__corner duel__corner--${side}${won ? " is-winner" : ""}`} key={side}>
              <p className="eyebrow">
                {player.player.position}
                {player.player.club ? ` · ${player.player.club.name}` : ""}
              </p>
              <h2 className="duel__name">
                <EntityLink href={player.player.path} label={player.player.name} />
              </h2>
              <div className="duel__figures">
                <span className="num duel__ovr">{player.player.overall}</span>
                <span className="duel__figures-label">{t("overallShort")}</span>
                <span className="duel__dot" aria-hidden="true">
                  ·
                </span>
                <span className="num">{figure(player.player.rating)}</span>
                <span className="duel__figures-label">{t("ratingShort")}</span>
              </div>
              <p className="muted duel__meta">
                {t("metaLine", {
                  age: player.player.age,
                  nation: player.player.nation || t("nationUnknown"),
                  season: player.player.season,
                })}
              </p>
              {won && <span className="duel__ribbon">{t("winnerRibbon")}</span>}
            </div>
          );
        })}

        <div className={`duel__middle${verdict.winner === "draw" ? " is-draw" : ""}`}>
          <span className="duel__vs">{t("versus")}</span>
          <div className="duel__tally num">
            <span className={verdict.winner === "left" ? "is-win" : ""}>{verdict.left_wins}</span>
            <span className="duel__tally-dash">–</span>
            <span className={verdict.winner === "right" ? "is-win" : ""}>{verdict.right_wins}</span>
          </div>
          <p className="duel__verdict">{verdictLine}</p>
          <p className="duel__counted muted">
            {t("countedLine", { counted: verdict.counted, total: categories.length, levelled: verdict.levelled })}
          </p>
        </div>
      </div>

      <div className="grid grid-2 duel__panels">
        <Panel eyebrow={t("radarEyebrow")} title={t("radarTitle")}>
          <div className="duel__radar">
            <DuelRadar axes={axes} />
            <ul className="duel__legend">
              <li>
                <span className="duel__swatch duel__swatch--left" aria-hidden="true" />
                {a.player.name}
              </li>
              <li>
                <span className="duel__swatch duel__swatch--right" aria-hidden="true" />
                {b.player.name}
              </li>
            </ul>
            <p className="field__hint">{t("radarNote")}</p>
          </div>
        </Panel>

        <Panel eyebrow={t("per90Eyebrow")} title={t("per90Title")}>
          <div className="table-wrap">
          <table className="table duel__per90">
            <thead>
              <tr>
                <th scope="col">{t("columnMetric")}</th>
                <th scope="col" className="num">
                  {a.player.name}
                </th>
                <th scope="col" className="num">
                  {b.player.name}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">{t("per90Goals")}</th>
                <td className="num">{figure(a.per_90.goals)}</td>
                <td className="num">{figure(b.per_90.goals)}</td>
              </tr>
              <tr>
                <th scope="row">{t("per90Assists")}</th>
                <td className="num">{figure(a.per_90.assists)}</td>
                <td className="num">{figure(b.per_90.assists)}</td>
              </tr>
              <tr>
                <th scope="row">{t("per90Involvement")}</th>
                <td className="num">{figure(a.per_90.involvement)}</td>
                <td className="num">{figure(b.per_90.involvement)}</td>
              </tr>
              <tr>
                <th scope="row">{t("per90MinutesPerAppearance")}</th>
                <td className="num">{figure(a.per_90.minutes_per_appearance)}</td>
                <td className="num">{figure(b.per_90.minutes_per_appearance)}</td>
              </tr>
            </tbody>
          </table>
          </div>
          <p className="field__hint">{t("per90Note", { minutes: method.per90_floor_minutes })}</p>
        </Panel>
      </div>

      <Panel
        eyebrow={t("ledgerEyebrow")}
        title={t("ledgerTitle")}
        action={
          <Link className="btn btn--ghost btn--sm" href="/world/duel">
            {t("pickAnother")}
          </Link>
        }
      >
        <div className="table-wrap">
          <table className="table duel__ledger">
          <caption className="duel__caption">{t("ledgerCaption")}</caption>
          <thead>
            <tr>
              <th scope="col" className="num">
                {a.player.name}
              </th>
              <th scope="col">{t("columnCategory")}</th>
              <th scope="col" className="num">
                {b.player.name}
              </th>
            </tr>
          </thead>
          <tbody>
            {categories.map((row) => {
              const text = copy[row.key];
              return (
                <tr key={row.key} className={row.winner === "unavailable" ? "is-unavailable" : undefined}>
                  <td className={`num duel__value${row.winner === "left" ? " is-win" : ""}`}>{figure(row.left)}</td>
                  <th scope="row" className="duel__category">
                    <span>{text.label}</span>
                    <span className="duel__basis">
                      {text.hint} · {basis[row.basis] ?? row.basis}
                    </span>
                  </th>
                  <td className={`num duel__value${row.winner === "right" ? " is-win" : ""}`}>{figure(row.right)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
          </div>
        <p className="field__hint">{t("ledgerFootnote", { redWeight: method.red_weight })}</p>
      </Panel>

      <Panel eyebrow={t("verdictEyebrow")} title={t("verdictTitle")}>
        <div className="duel__reading">
          <p className="duel__reading-line">{verdictLine}</p>
          {verdict.decided_by.length > 0 && (
            <p>
              {t("tookCategories", {
                name: winnerName ?? "",
                categories: verdict.decided_by.map((key) => copy[key as keyof typeof copy]?.label ?? key).join(" · "),
              })}
            </p>
          )}
          {verdict.unavailable > 0 && <p className="muted">{t("unavailableNote", { minutes: method.per90_floor_minutes })}</p>}
          <p className="muted duel__method">{t("methodNote", { counted: verdict.counted, total: categories.length })}</p>
        </div>
      </Panel>

      <div className="row between wrap">
        <Link className="btn btn--ghost btn--sm" href={a.player.path}>
          {t("backToPlayer", { name: a.player.name })}
        </Link>
        <Link className="btn btn--ghost btn--sm" href={b.player.path}>
          {t("backToPlayer", { name: b.player.name })}
        </Link>
      </div>

      <Provenance provenance={result.data} extra={<span className="chip mono">{tw("sectionPlayersLabel")}</span>} />
    </div>
  );
}
