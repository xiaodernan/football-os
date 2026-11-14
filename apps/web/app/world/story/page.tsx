import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Provenance, WorldHead, WorldUnavailable, formatMoment } from "@/components/world";
import { pageMetadata, absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type {
  StoryChapterAvalancheAvailable,
  StoryChapterUnbeatenAvailable,
  StoryResult,
} from "@/lib/types";

import "@/styles/story.css";

export const dynamic = "force-dynamic";

type Translator = Awaited<ReturnType<typeof getTranslations>>;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldStory");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/story",
    images: [{ url: absolute("/world/story/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

export default async function StoryPage() {
  const t = await getTranslations("worldStory");
  const result = await readWorld<StoryResult>("/world/story");

  if (!result.ok) {
    return (
      <div className="container page stack">
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} />
        <p className="story-unavailable">{t("unavailable")}</p>
      </div>
    );
  }

  const [titleRace, avalanche, unbeaten] = result.data.chapters;

  return (
    <div className="container page stack">
      <WorldHead
        eyebrow={t("eyebrow")}
        title={t("title")}
        lede={t("lede")}
        provenance={result.data}
        back={{ href: "/world", label: t("backWorld") }}
      />
      <p className="chip mono" style={{ alignSelf: "flex-start" }}>{t("seasonLabel")}</p>

      <div className="story-book">
        <section className="story-chapter" aria-label={t("chapterOneHint")}>
          <div className="story-chapter__numeral" aria-hidden="true">I</div>
          <div>
            <span className="story-chapter__eyebrow">{t("chapterOneLabel")} · {t("chapterOneHint")}</span>
            <h2 className="story-chapter__title">{titleRace.available ? titleRace.competition : t("unavailable")}</h2>
            <p className="story-chapter__lede">{t("chapterOneLede")}</p>
            {titleRace.available && (
              <div className="story-chapter__figures">
                <div className="story-vs-row">
                  <Link href={titleRace.champion.path ?? "/world"} className="story-scoreline__club">
                    {titleRace.champion.name}
                  </Link>
                  <span className="story-scoreline__goals">{titleRace.champion.points}</span>
                  <span className="story-scoreline__dash">·</span>
                  <Link href={titleRace.runner_up.path ?? "/world"} className="story-scoreline__club" style={{ color: "var(--text-2)" }}>
                    {titleRace.runner_up.name}
                  </Link>
                  <span className="story-scoreline__goals" style={{ color: "var(--text-2)" }}>{titleRace.runner_up.points}</span>
                </div>
                <div className="story-gd-story">
                  {titleRace.margin > 0 ? (
                    <span className="story-margin-figure">
                      <strong>+{titleRace.margin}</strong>
                      <span>{t("chapterTwoMargin")}</span>
                    </span>
                  ) : (
                    <span className="story-margin-figure">
                      <strong>+{titleRace.gd_margin}</strong>
                      <span>{t("chapterOneGdGap")}</span>
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="story-chapter" aria-label={t("chapterTwoHint")}>
          <div className="story-chapter__numeral" aria-hidden="true">II</div>
          <div>
            <span className="story-chapter__eyebrow">{t("chapterTwoLabel")} · {t("chapterTwoHint")}</span>
            <h2 className="story-chapter__title">{avalanche.available ? avalanche.winner_name : t("unavailable")}</h2>
            <p className="story-chapter__lede">{t("chapterTwoLede")}</p>
            {avalanche.available ? (
              <AvalancheFoot chapter={avalanche} t={t} />
            ) : (
              <p className="story-unavailable">{t("unavailable")}</p>
            )}
          </div>
        </section>

        <section className="story-chapter" aria-label={t("chapterThreeHint")}>
          <div className="story-chapter__numeral" aria-hidden="true">III</div>
          <div>
            <span className="story-chapter__eyebrow">{t("chapterThreeLabel")} · {t("chapterThreeHint")}</span>
            <h2 className="story-chapter__title">{unbeaten.available ? unbeaten.team.name : t("unavailable")}</h2>
            <p className="story-chapter__lede">{t("chapterThreeLede")}</p>
            {unbeaten.available ? (
              <UnbeatenFoot chapter={unbeaten} t={t} />
            ) : (
              <p className="story-unavailable">{t("unavailable")}</p>
            )}
          </div>
        </section>
      </div>

      <Provenance provenance={result.data} />
    </div>
  );
}

function AvalancheFoot({ chapter, t }: { chapter: StoryChapterAvalancheAvailable; t: Translator }) {
  const kickoff = chapter.kickoff_at ? formatMoment(chapter.kickoff_at) : null;
  return (
    <div className="story-chapter__figures">
      <div className="story-scoreline">
        {chapter.home.path ? (
          <Link className="story-scoreline__club" href={chapter.home.path}>{chapter.home.name}</Link>
        ) : (
          <span className="story-scoreline__club">{chapter.home.name}</span>
        )}
        <span className="story-scoreline__goals">{chapter.home.goals}</span>
        <span className="story-scoreline__dash">–</span>
        <span className="story-scoreline__goals">{chapter.away.goals}</span>
        {chapter.away.path ? (
          <Link className="story-scoreline__club" href={chapter.away.path}>{chapter.away.name}</Link>
        ) : (
          <span className="story-scoreline__club">{chapter.away.name}</span>
        )}
      </div>
      <div className="story-gd-story">
        <span className="story-margin-figure">
          <strong>{chapter.margin}</strong>
          <span>{t("chapterTwoMargin")}</span>
        </span>
      </div>
      <Link href={chapter.match_path} className="story-venue">
        {t("chapterTwoVenue", { venue: chapter.venue_name, city: chapter.venue_city })}
        {kickoff ? <> · {kickoff}</> : null}
      </Link>
    </div>
  );
}

function UnbeatenFoot({ chapter, t }: { chapter: StoryChapterUnbeatenAvailable; t: Translator }) {
  return (
    <div className="story-chapter__figures">
      <div className="story-gd-story">
        <span className="story-margin-figure">
          <strong>{chapter.run}</strong>
          <span>{t("chapterThreeRun", { run: chapter.run })}</span>
        </span>
      </div>
      <span className={chapter.alive ? "story-alive" : "story-ended"}>
        {chapter.alive ? t("chapterThreeAlive") : t("chapterThreeEnded")}
      </span>
      <span className="story-venue">
        <Link href={`/competition/${chapter.competition_slug}`}>{chapter.competition}</Link>
      </span>
    </div>
  );
}
