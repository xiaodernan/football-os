import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { Provenance, RefLink, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
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

export default async function SpotlightPage() {
  const t = await getTranslations("worldSpotlight");
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");
  const tt = await getTranslations("worldSpotlight");

  const result = await readWorld<{ spotlights: { key: string; available: boolean; [k: string]: unknown }[]; season: { label: string } }>(
    "/world/spotlight",
  );

  if (!result.ok) return <WorldUnavailable message={result.message} />;

  const { spotlights, season } = result.data;
  const hit = spotlights.find((s) => s.key === "hitman");
  const fortress = spotlights.find((s) => s.key === "fortress");
  const blood = spotlights.find((s) => s.key === "new_blood");

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={tt("eyebrow")}
        lede={tt("lede")}
        provenance={result.data}
        title={tt("title")}
      />

      <div className="spotlight__grid">
        {[
          {
            panel: "hitman",
            eyebrow: tt("hitmanEyebrow"),
            title: tt("hitmanTitle"),
            note: tt("hitmanNote"),
            body: hit?.available ? (
              <>
                <p className="spotlight__figure"><span className="spotlight__big">{Number(hit.per_90 ?? 0).toFixed(2)}</span><span className="spotlight__unit">{tt("hitmanUnit")}</span></p>
                <p className="spotlight__body"><strong>{hit.player?.name as string}</strong></p>
                <p className="muted" style={{ fontSize: "0.82rem" }}>{hit.competition as string} · {hit.goals as number} {tt("goalsUnit")} · {hit.minutes as number} {tt("minutesUnit")}</p>
                <RefLink target={{ type: "player", slug: hit.player?.slug as string, id: hit.player?.id as string, path: hit.player?.path as string }} />
              </>
            ) : <p className="muted">{tt("unavailable")}</p>,
          },
          {
            panel: "fortress",
            eyebrow: tt("fortressEyebrow"),
            title: tt("fortressTitle"),
            note: tt("fortressNote"),
            body: fortress?.available ? (
              <>
                <p className="spotlight__figure"><span className="spotlight__big">{fortress.clean_sheets as number}</span><span className="spotlight__unit">{tt("fortressUnit")}</span></p>
                <p className="spotlight__body"><strong>{fortress.team?.name as string}</strong></p>
                <p className="muted" style={{ fontSize: "0.82rem" }}>{fortress.played as number} {tt("playedUnit")} · {fortress.conceded as number} {tt("concededUnit")}</p>
                <RefLink target={{ type: "team", slug: fortress.team?.slug as string, id: fortress.team?.id as string, path: fortress.team?.path as string }} />
              </>
            ) : <p className="muted">{tt("unavailable")}</p>,
          },
          {
            panel: "blood",
            eyebrow: tt("bloodEyebrow"),
            title: tt("bloodTitle"),
            note: tt("bloodNote"),
            body: blood?.available ? (
              <>
                <p className="spotlight__figure"><span className="spotlight__big">{blood.age as number}</span><span className="spotlight__unit">{tt("bloodUnit")}</span></p>
                <p className="spotlight__body"><strong>{blood.player?.name as string}</strong></p>
                <p className="muted" style={{ fontSize: "0.82rem" }}>{blood.competition as string} · {blood.minutes as number} {tt("minutesUnit")} · {blood.position as string}</p>
                <RefLink target={{ type: "player", slug: blood.player?.slug as string, id: blood.player?.id as string, path: blood.player?.path as string }} />
              </>
            ) : <p className="muted">{tt("unavailable")}</p>,
          },
        ].map((panel) => (
          <article key={panel.panel} className="spotlight__tile">
            <span className="spotlight__tile-eyebrow">{panel.eyebrow}</span>
            <h2 className="spotlight__tile-title">{panel.title}</h2>
            <p className="spotlight__tile-note">{panel.note}</p>
            {panel.body}
          </article>
        ))}
      </div>

      <Provenance provenance={result.data} />
    </div>
  );
}
