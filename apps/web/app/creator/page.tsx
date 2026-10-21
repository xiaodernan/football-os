import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { KeyValueGrid, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { CreatorRulesView } from "@/lib/creator";
import { CreatorWorkbench } from "@/components/CreatorWorkbench";

import "../../styles/tactics.css";
import "../../styles/world.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("creator");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/creator") },
  };
}

export default async function CreatorPage() {
  const t = await getTranslations("creator");
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcreator");

  const rules = await serverFetch<CreatorRulesView>("/creator/rules");
  if (!rules.ok) {
    return (
      <WorldUnavailable
        eyebrow={t("metaTitle")}
        message={rules.error.message}
        title={t("metaTitle")}
      />
    );
  }
  const data = rules.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: t("backLabel") }}
        eyebrow={t("eyebrow", { name: user.display_name })}
        lede={t("lede")}
        title={t("metaTitle")}
      />

      {data.counts.profiles === 0 && data.counts.guides === 0 && (
        <p className="notice">
          {t("noProfiles")}
        </p>
      )}

      <CreatorWorkbench creator={user.id} rules={data} />

      <Panel
        eyebrow={t("vocabularyEyebrow", {
          profiles: data.counts.profiles,
          guides: data.counts.guides,
          citations: data.counts.citations,
        })}
        title={t("vocabularyTitle")}
      >
        <div className="stack-sm">
          <KeyValueGrid
            rows={[
              [t("rowGuideCaps"), t("guideCapsValue", { guides: data.caps.guide_max, titles: data.caps.guide_title_max, summaries: data.caps.guide_summary_max, slugs: data.caps.guide_slug_max })],
              [t("rowCitationCaps"), t("citationCapsValue", { citations: data.caps.citation_max, notes: data.caps.citation_note_max })],
              [t("rowProfileCaps"), t("profileCapsValue", { headlines: data.caps.profile_headline_max, biographies: data.caps.profile_bio_max })],
              [t("rowSections"), data.caps.sections.join(" · ")],
              [t("rowVisibilities"), data.caps.visibilities.join(" · ")],
              [t("rowVisibilityRule"), data.caps.visibility_rule],
            ]}
          />
          <p className="muted">{data.limitation}</p>
          <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
            {data.routes.map((route, i) => (
              <li className="muted" key={i}>
                <span className="mono">{route.method} {route.path}</span> — {route.door}
              </li>
            ))}
          </ul>
        </div>
      </Panel>

      <Panel
        eyebrow={t("refusalsEyebrow", { count: Object.keys(data.refusal_answers).length })}
        title={t("refusalsTitle")}
      >
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("thCode")}</th>
                <th scope="col">{t("thAnswer")}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.refusal_answers)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([code, answer]) => (
                  <tr data-refusal={code} key={code}>
                    <td className="mono">{code}</td>
                    <td className="num">{answer}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {t("entitlementNote", { features: data.entitlement_features.join(", ") })}
        </p>
      </Panel>
    </div>
  );
}
