import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { CreatorRulesView } from "@/lib/creator";
import { CreatorWorkbench } from "@/components/CreatorWorkbench";

import "../../styles/tactics.css";
import "../../styles/world.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Creator Studio",
  description: "Publish guides that cite the corpus. Every figure is counted now; nothing is stored that the corpus already holds.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/creator") },
};

export default async function CreatorPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcreator");

  const rules = await serverFetch<CreatorRulesView>("/creator/rules");
  if (!rules.ok) {
    return <WorldUnavailable eyebrow="Creator Studio" message={rules.error.message} title="Creator Studio" />;
  }
  const data = rules.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/world", label: "Football world" }}
        eyebrow={`${user.display_name} · publishing and reading are private to your account`}
        lede="A guide is a frame: a section, a title, a summary and the addresses of the passages it cites. The corpus stays the corpus — re-ingesting it cannot leave a guide quoting words the document no longer holds. Every figure on a guide is counted from the rows its own formula names, recomputed on every read."
        provenance={{ data_origin: data.data_origin, is_demo_data: data.is_demo_data, disclaimer: data.disclaimer }}
        title="Creator Studio"
      />

      {data.counts.profiles === 0 && data.counts.guides === 0 && (
        <p className="notice">
          No creator profiles yet. Publish your profile to begin — the first guide you write creates it.
        </p>
      )}

      <CreatorWorkbench rules={data} />

      <Panel eyebrow={`${data.counts.profiles} profiles · ${data.counts.guides} guides · ${data.counts.citations} citations`} title="What this vocabulary understands">
        <div className="stack-sm">
          <KeyValueGrid
            rows={[
              ["Guide caps", `${data.caps.guide_max} per creator · ${data.caps.guide_title_max}-character titles · ${data.caps.guide_summary_max}-character summaries · ${data.caps.guide_slug_max}-character slugs`],
              ["Citation caps", `${data.caps.citation_max} per guide · ${data.caps.citation_note_max}-character notes`],
              ["Profile caps", `${data.caps.profile_headline_max}-character headlines · ${data.caps.profile_bio_max}-character biographies`],
              ["Sections", data.caps.sections.join(" · ")],
              ["Visibilities", data.caps.visibilities.join(" · ")],
              ["Visibility rule", data.caps.visibility_rule],
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

      <Provenance provenance={{ data_origin: data.data_origin, is_demo_data: data.is_demo_data, disclaimer: data.disclaimer }} />
    </div>
  );
}