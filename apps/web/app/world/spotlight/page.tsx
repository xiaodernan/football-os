import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { Provenance, RefLink, WorldHead, WorldUnavailable } from "@/components/world";
import { SpotlightCoachRead } from "@/components/SpotlightCoachRead";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope, PlayerBrief, TeamBrief } from "@/lib/types";
import "@/styles/spotlight.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldSpotlight");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/spotlight",
  });
}

type SpotlightHitman = { key: "hitman"; available: boolean; player?: PlayerBrief & { stat: string }; per_90?: number; goals?: number; minutes?: number; competition?: string };
type SpotlightFortress = { key: "fortress"; available: boolean; team?: TeamBrief; clean_sheets?: number; played?: number; conceded?: number };
type SpotlightBlood = { key: "new_blood"; available: boolean; player?: PlayerBrief; age?: number; minutes?: number; position?: string; competition?: string };
type SpotlightPayload = WorldEnvelope & { season: { label: string }; spotlights: (SpotlightHitman | SpotlightFortress | SpotlightBlood)[] };

export default async function SpotlightPage() {
  const t = await getTranslations("worldSpotlight");
  const tw = await getTranslations("world");

  const result = await readWorld<SpotlightPayload>("/world/spotlight");

  if (!result.ok) return <WorldUnavailable message={result.message} />;

  const { spotlights } = result.data;
  const hit = spotlights.find((s) => s.key === "hitman") as SpotlightHitman | undefined;
  const fortress = spotlights.find((s) => s.key === "fortress") as SpotlightFortress | undefined;
  const blood = spotlights.find((s) => s.key === "new_blood") as SpotlightBlood | undefined;

  const hitman = (
    <>
      {hit?.available && hit.player ? (
        <>
          <p className="spotlight__figure"><span className="spotlight__big">{Number(hit.per_90 ?? 0).toFixed(2)}</span><span className="spotlight__unit">{t("hitmanUnit")}</span></p>
          <p className="spotlight__body"><strong>{hit.player.name}</strong></p>
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {hit.competition} · {hit.goals} {t("goalsUnit")} · {hit.minutes} {t("minutesUnit")}
          </p>
          <RefLink target={{ type: "player", slug: hit.player.slug, id: hit.player.id, path: hit.player.path }} />
        </>
      ) : <p className="muted">{t("unavailable")}</p>}
    </>
  );

  const fortressTile = (
    <>
      {fortress?.available && fortress.team ? (
        <>
          <p className="spotlight__figure"><span className="spotlight__big">{fortress.clean_sheets}</span><span className="spotlight__unit">{t("fortressUnit")}</span></p>
          <p className="spotlight__body"><strong>{fortress.team.name}</strong></p>
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {fortress.played} {t("playedUnit")} · {fortress.conceded} {t("concededUnit")}
          </p>
          <RefLink target={{ type: "team", slug: fortress.team.slug, id: fortress.team.id, path: fortress.team.path }} />
        </>
      ) : <p className="muted">{t("unavailable")}</p>}
    </>
  );

  const bloodTile = (
    <>
      {blood?.available && blood.player ? (
        <>
          <p className="spotlight__figure"><span className="spotlight__big">{blood.age}</span><span className="spotlight__unit">{t("bloodUnit")}</span></p>
          <p className="spotlight__body"><strong>{blood.player.name}</strong></p>
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            {blood.competition} · {blood.minutes} {t("minutesUnit")} · {blood.position}
          </p>
          <RefLink target={{ type: "player", slug: blood.player.slug, id: blood.player.id, path: blood.player.path }} />
        </>
      ) : <p className="muted">{t("unavailable")}</p>}
    </>
  );

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={result.data}
        title={t("title")}
      />

      <div className="spotlight__grid">
        <article className="spotlight__tile">
          <span className="spotlight__tile-eyebrow">{t("hitmanEyebrow")}</span>
          <h2 className="spotlight__tile-title">{t("hitmanTitle")}</h2>
          <p className="spotlight__tile-note">{t("hitmanNote")}</p>
          {hitman}
        </article>
        <article className="spotlight__tile">
          <span className="spotlight__tile-eyebrow">{t("fortressEyebrow")}</span>
          <h2 className="spotlight__tile-title">{t("fortressTitle")}</h2>
          <p className="spotlight__tile-note">{t("fortressNote")}</p>
          {fortressTile}
        </article>
        <article className="spotlight__tile">
          <span className="spotlight__tile-eyebrow">{t("bloodEyebrow")}</span>
          <h2 className="spotlight__tile-title">{t("bloodTitle")}</h2>
          <p className="spotlight__tile-note">{t("bloodNote")}</p>
          {bloodTile}
        </article>
      </div>

      <SpotlightCoachRead />

      <Provenance provenance={result.data} />
    </div>
  );
}
