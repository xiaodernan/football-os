import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { DuelPicker } from "@/components/DuelPicker";
import { Panel } from "@/components/ui";
import { WorldHead } from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { cleanParams, readWorld } from "@/lib/world";
import type { PlayerDetail } from "@/lib/types";

import "@/styles/duel.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("duel");
  return pageMetadata({
    title: t("metaPickerTitle"),
    description: t("metaPickerDescription"),
    path: "/world/duel",
    images: [{ url: absolute("/world/duel/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS — pick two players, the ledger decides" }],
  });
}

/**
 * The door to the duel: two slots, one search, one button.
 *
 * This page is deliberately thin. Everything that can be argued about (who wins, which column, what a tie is)
 * belongs on the duel page itself and in `app.services.world.duel`; this one only decides which two names the
 * argument is about.
 */
type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function DuelPickerPage({ searchParams }: Props) {
  const t = await getTranslations("duel");
  const tw = await getTranslations("world");
  const query = cleanParams(await searchParams);
  // `/world/duel?left=<slug>` is how a player's own page hands its subject to the picker. The name is read
  // here, server-side, so the corner arrives filled rather than as a slug the reader has to trust.
  const seed = query.left ? await readWorld<PlayerDetail>(`/world/players/${encodeURIComponent(query.left)}`) : null;
  const initialLeft = seed?.ok
    ? { slug: seed.data.player.slug, title: seed.data.player.name, subtitle: `${seed.data.player.position} · ${seed.data.player.overall}` }
    : undefined;
  return (
    <div className="container page stack">
      <WorldHead
        eyebrow={t("eyebrow")}
        title={t("pickerTitle")}
        lede={t("pickerLede")}
        back={{ href: "/world/players", label: tw("sectionPlayersLabel") }}
      />
      <div className="grid grid-2 duel-picker__grid">
        <Panel title={t("pickerPanelTitle")} eyebrow={t("pickerPanelEyebrow")}>
          <DuelPicker initialLeft={initialLeft} />
        </Panel>
        <Panel title={t("rulesTitle")} eyebrow={t("rulesEyebrow")}>
          <ol className="duel-rules">
            <li>{t("ruleOne")}</li>
            <li>{t("ruleTwo")}</li>
            <li>{t("ruleThree")}</li>
          </ol>
        </Panel>
      </div>
    </div>
  );
}
