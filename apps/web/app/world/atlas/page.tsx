import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/atlas.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldAtlas");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/atlas",
  });
}

type AtlasNode = { href: string; label: string; note?: string };

const STARS: { cx: number; cy: number; r: number; o: number }[] = [
  { cx: 60, cy: 90, r: 1.4, o: 0.9 }, { cx: 120, cy: 40, r: 1.0, o: 0.5 }, { cx: 180, cy: 130, r: 1.8, o: 0.8 },
  { cx: 240, cy: 70, r: 1.1, o: 0.6 }, { cx: 300, cy: 160, r: 2.2, o: 0.9 }, { cx: 350, cy: 90, r: 0.9, o: 0.4 },
  { cx: 410, cy: 190, r: 1.5, o: 0.7 }, { cx: 460, cy: 60, r: 1.2, o: 0.6 }, { cx: 520, cy: 140, r: 2.6, o: 1 },
  { cx: 580, cy: 210, r: 1.0, o: 0.5 }, { cx: 640, cy: 80, r: 1.6, o: 0.8 }, { cx: 700, cy: 150, r: 1.2, o: 0.6 },
  { cx: 760, cy: 40, r: 2.0, o: 0.9 }, { cx: 810, cy: 190, r: 1.1, o: 0.5 }, { cx: 870, cy: 110, r: 1.7, o: 0.8 },
  { cx: 930, cy: 160, r: 1.0, o: 0.5 }, { cx: 980, cy: 70, r: 2.4, o: 1 }, { cx: 1040, cy: 140, r: 1.3, o: 0.6 },
  { cx: 1100, cy: 90, r: 1.8, o: 0.8 }, { cx: 160, cy: 210, r: 0.8, o: 0.4 }, { cx: 340, cy: 230, r: 1.0, o: 0.5 },
  { cx: 600, cy: 250, r: 1.4, o: 0.6 }, { cx: 900, cy: 230, r: 0.9, o: 0.4 }, { cx: 1130, cy: 200, r: 1.1, o: 0.6 },
  { cx: 90, cy: 250, r: 1.2, o: 0.5 },
];

const BRIGHT = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18];
const RIDGE = [0, 2, 4, 6, 9, 12, 15, 18];
const constellationOf = (pick: number[]) => pick.map((i) => `${STARS[i].cx},${STARS[i].cy}`).join(" ");

export default async function AtlasPage() {
  const t = await getTranslations("worldAtlas");
  const tw = await getTranslations("world");
  const tsp = await getTranslations("worldSpotlight");
  const tt = await getTranslations("worldTimeline");
  const tg = await getTranslations("worldGazette");
  const tf = await getTranslations("worldFinals");
  const tn = await getTranslations("worldNoise");
  const tu = await getTranslations("worldUpsets");
  const td = await getTranslations("worldDynasties");
  const tr = await getTranslations("worldRealBook");
  const tc = await getTranslations("worldChampions");
  const tcd = await getTranslations("worldCreed");
  const thon = await getTranslations("worldHonours");

  const world = await readWorld<WorldEnvelope>("/world/status");
  if (!world.ok) return <WorldUnavailable message={world.message} />;

  const browsing: AtlasNode[] = [
    { href: "/world/competitions", label: tw("sectionCompetitionsLabel"), note: tw("sectionCompetitionsNote") },
    { href: "/world/teams", label: tw("sectionClubsLabel"), note: tw("sectionClubsNote") },
    { href: "/world/players", label: tw("sectionPlayersLabel"), note: tw("sectionPlayersNote") },
    { href: "/world/matches", label: tw("sectionFixturesLabel"), note: tw("sectionFixturesNote") },
    { href: "/world/news", label: tw("sectionReportsLabel"), note: tw("sectionReportsNote") },
    { href: "/world/training", label: t("trainingLabel"), note: t("trainingNote") },
  ];
  const league: AtlasNode[] = [
    { href: "/world/almanac", label: tw("sectionAlmanacLabel"), note: tw("sectionAlmanacNote") },
    { href: "/world/story", label: tw("sectionStoryLabel"), note: tw("sectionStoryNote") },
    { href: "/world/records", label: tw("sectionRecordsLabel"), note: tw("sectionRecordsNote") },
    { href: "/world/matchday-xi", label: tw("sectionMatchdayXiLabel"), note: tw("sectionMatchdayXiNote") },
    { href: "/world/spotlight", label: tsp("sectionSpotlightLabel"), note: tsp("sectionSpotlightNote") },
    { href: "/world/timeline", label: tt("sectionTimelineLabel"), note: tt("sectionTimelineNote") },
    { href: "/world/gazette", label: tg("sectionGazetteLabel"), note: tg("sectionGazetteNote") },
    { href: "/world/finals", label: tf("sectionFinalsLabel"), note: tf("sectionFinalsNote") },
    { href: "/world/noise", label: tn("sectionNoiseLabel"), note: tn("sectionNoiseNote") },
    { href: "/world/upsets", label: tu("sectionUpsetsLabel"), note: tu("sectionUpsetsNote") },
    { href: "/world/dynasties", label: td("sectionDynastiesLabel"), note: td("sectionDynastiesNote") },
  ];
  const book: AtlasNode[] = [
    { href: "/world/real-book", label: tr("sectionRealBookLabel"), note: tr("sectionRealBookNote") },
    { href: "/world/champions", label: tc("sectionChampionsLabel"), note: tc("sectionChampionsNote") },
    { href: "/world/creed", label: tcd("eyebrow"), note: tcd("footerClaim") },
    { href: "/world/honours", label: thon("eyebrow"), note: thon("snapshotNote") },
    { href: "/tutorial", label: t("tutorialLabel"), note: t("tutorialNote") },
    { href: "/manual", label: t("manualLabel"), note: t("manualNote") },
  ];

  const clusters: { title: string; rows: AtlasNode[] }[] = [
    { title: t("clusterBrowsing"), rows: browsing },
    { title: t("clusterLeague"), rows: league },
    { title: t("clusterBook"), rows: book },
  ];

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={world.data}
        title={t("title")}
      />

      <figure className="atlas__sky" aria-hidden="true">
        <svg viewBox="0 0 1200 300" role="presentation" focusable="false" className="atlas__stars">
          <title>{t("diagramTitle")}</title>
          <polyline className="atlas__constellation" points={constellationOf(BRIGHT)} />
          <polyline className="atlas__constellation atlas__constellation--dim" points={constellationOf(RIDGE)} />
          {STARS.map((star, index) => (
            <circle key={index} cx={star.cx} cy={star.cy} r={star.r} className="atlas__star" opacity={star.o} />
          ))}
        </svg>
      </figure>

      <div className="atlas__clusters">
        {clusters.map((cluster) => (
          <Panel key={cluster.title} eyebrow={t("clusterEyebrow")} title={cluster.title}>
            <ul className="atlas__list">
              {cluster.rows.map((node) => (
                <li key={node.href}>
                  <Link className="atlas__door" href={node.href}>
                    <span className="atlas__door-body">
                      <strong>{node.label}</strong>
                      {node.note ? <span className="muted">{node.note}</span> : null}
                    </span>
                    <span className="atlas__door-arrow" aria-hidden="true">→</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>

      <p className="atlas__note muted">{t("footerNote")}</p>

      <Provenance provenance={world.data} />
    </div>
  );
}
