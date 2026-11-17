import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { EntityLink, JsonLd, Provenance, WorldHead, WorldUnavailable, formatDay } from "@/components/world";
import { XiCoachRead } from "@/components/XiCoachRead";
import { pageMetadata, absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { MatchdayXiResult, XISlot } from "@/lib/types";

import "@/styles/xi.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldMatchdayXi");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/matchday-xi",
    images: [{ url: absolute("/world/matchday-xi/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

export default async function MatchdayXiPage() {
  const t = await getTranslations("worldMatchdayXi");
  const ta = await getTranslations("almanac");
  const result = await readWorld<MatchdayXiResult>("/world/matchday-xi");

  if (!result.ok || !result.data.available) {
    return (
      <div className="container page stack">
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} />
        <p className="xi__unavailable">{t("unavailable")}</p>
      </div>
    );
  }

  const { slots, captain, formation, competition, season, next_fixture } = result.data;
  const line = (numbers: readonly number[]) => slots.filter((slot) => numbers.includes(slot.number));

  return (
    <div className="container page stack">
      <WorldHead
        eyebrow={t("eyebrow")}
        title={t("title")}
        lede={t("lede")}
        provenance={result.data}
        back={{ href: "/world", label: t("backWorld") }}
      />

      <div className="xi__strip">
        <span className="chip mono">{t("seasonLabel")}</span>
        <span className="chip mono">{formation}</span>
        {competition ? (
          <Link className="chip mono" href={`/competition/${competition.slug}`}>{competition.name}</Link>
        ) : null}
        {next_fixture ? (
          <Link className="chip mono" href={next_fixture.path}>
            {next_fixture.round_label}
            {next_fixture.kickoff_at ? ` · ${formatDay(next_fixture.kickoff_at)}` : null}
          </Link>
        ) : null}
      </div>

      <section className="xi__pitch" aria-label={t("title")}>
        <div className="xi__row xi__row--attack" aria-label={t("lineAttack")}>
          {line([7, 9, 11]).map((slot) => (
            <Shirt key={slot.number} slot={slot} captainPath={captain?.path ?? null} t={t} />
          ))}
        </div>
        <div className="xi__row xi__row--midfield" aria-label={t("lineMidfield")}>
          {line([6, 8, 10]).map((slot) => (
            <Shirt key={slot.number} slot={slot} captainPath={captain?.path ?? null} t={t} />
          ))}
        </div>
        <div className="xi__row xi__row--defense" aria-label={t("lineDefence")}>
          {line([2, 4, 5, 3]).map((slot) => (
            <Shirt key={slot.number} slot={slot} captainPath={captain?.path ?? null} t={t} />
          ))}
        </div>
        <div className="xi__row xi__row--keeper" aria-label={t("lineKeeper")}>
          {line([1]).map((slot) => (
            <Shirt key={slot.number} slot={slot} captainPath={captain?.path ?? null} t={t} />
          ))}
        </div>
      </section>

      <p className="muted xi__disclaimer">{t("noteFinePrint")}</p>

      <XiCoachRead />

      <Provenance provenance={result.data} />
    </div>
  );
}

function Shirt({ slot, captainPath, t }: { slot: XISlot; captainPath: string | null; t: (key: string, values?: Record<string, string | number>) => string }) {
  const isCaptain = captainPath !== null && slot.path === captainPath;
  return (
    <Link href={slot.path ?? "/world/matchday-xi"} className="xi__shirt" data-pos={slot.position}>
      <span className="xi__shirt-number">{slot.number}</span>
      {isCaptain && <span className="xi__captain" title={t("captainTag")} aria-hidden="true">{t("captainTag")}</span>}
      <span className="xi__shirt-name">{slot.name}</span>
      <span className="xi__shirt-role">{slot.position}</span>
      <span className="xi__shirt-ovr">{slot.overall}</span>
      {slot.substituted ? (
        <span className="xi__shirt-slack">{t("slackSub", { slack: slot.slack ?? "" })}</span>
      ) : null}
    </Link>
  );
}
