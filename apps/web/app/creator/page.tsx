import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { KeyValueGrid, WorldHead, WorldUnavailable } from "@/components/world";
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
        title="Creator Studio"
      />

      {data.counts.profiles === 0 && data.counts.guides === 0 && (
        <p className="notice">
          No creator profiles yet. Publish your profile to begin — the first guide you write creates it.
        </p>
      )}

      <CreatorWorkbench creator={user.id} rules={data} />

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

      <Panel
        eyebrow={`${Object.keys(data.refusal_answers).length} codes · one status each, from the project's one table`}
        title="What a door here refuses, and with what answer"
      >
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Answer</th>
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
          There is no 403 in this tier: a creator door asks only whether you have a session, so what you may not reach is answered as absence — the same
          shape a row that was never written earns, and the same table §39&apos;s doors answer from.
        </p>
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          This tier names two features in §42&apos;s entitlement table (<span className="mono">{data.entitlement_features.join(", ")}</span>). They are
          ceilings the data holds and no door refuses on yet, so the caps above are what actually bites.
        </p>
      </Panel>
    </div>
  );
}
