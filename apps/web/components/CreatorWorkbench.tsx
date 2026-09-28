"use client";

import React from "react";
import { useCallback, useEffect, useState } from "react";

import { Panel } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import type { ApiError } from "@/lib/types";
import type { CreatorProfileView, CreatorRulesView, GuideIn, GuideShelfView, GuideView, GuideCitationView } from "@/lib/creator";

const SECTIONS: GuideIn["section"][] = ["plan", "drill", "match", "tactic", "scout", "video"];
const VISIBILITIES: GuideIn["visibility"][] = ["public", "unlisted", "followers"];

type Busy = "profile" | "guide" | "citation" | "load" | null;

function shelfEyebrow(shelf: GuideShelfView | null): string {
  if (!shelf) return "Guides";
  const parts = [`${shelf.total} guide${shelf.total === 1 ? "" : "s"}`];
  if (shelf.creator) parts.push(`by ${shelf.creator}`);
  else parts.push("all creators");
  if (shelf.section) parts.push(`section: ${shelf.section}`);
  else parts.push("all sections");
  return parts.join(" · ");
}

export function CreatorWorkbench({ rules }: { rules: CreatorRulesView }) {
  const [busy, setBusy] = useState<Busy>(null);
  const [fault, setFault] = useState<ApiError | null>(null);

  const [profile, setProfile] = useState<CreatorProfileView | null>(null);
  const [slug, setSlug] = useState("");
  const [headline, setHeadline] = useState("");
  const [bio, setBio] = useState("");

  const [shelf, setShelf] = useState<GuideShelfView | null>(null);
  const [guideTitle, setGuideTitle] = useState("");
  const [guideSummary, setGuideSummary] = useState("");
  const [guideSection, setGuideSection] = useState<GuideIn["section"]>("plan");
  const [guideVisibility, setGuideVisibility] = useState<GuideIn["visibility"]>("public");

  const [selectedGuide, setSelectedGuide] = useState<GuideView | null>(null);
  const [citationDocument, setCitationDocument] = useState("");
  const [citationOrdinal, setCitationOrdinal] = useState("");
  const [citationNote, setCitationNote] = useState("");

  const loadProfile = useCallback(async () => {
    const result = await browserFetch<CreatorProfileView>("/creator/profile");
    if (result.ok) setProfile(result.data);
  }, []);

  const loadShelf = useCallback(async () => {
    const result = await browserFetch<GuideShelfView>("/creator/guides");
    if (result.ok) setShelf(result.data);
  }, []);

  useEffect(() => {
    void loadProfile();
    void loadShelf();
  }, [loadProfile, loadShelf]);

  async function ask(route: string, method: "POST" | "DELETE", body?: Record<string, unknown>) {
    const result = await browserFetch<Record<string, unknown>>(route, { method, body });
    if (!result.ok) {
      setFault(result.error);
      return null;
    }
    setFault(null);
    return result.data;
  }

  async function publishProfile() {
    setBusy("profile");
    const created = await ask("/creator/profile", "POST", { slug: slug.trim() || undefined, headline: headline.trim() || undefined, bio: bio.trim() || undefined });
    setBusy(null);
    if (!created) return;
    await loadProfile();
    setSlug("");
    setHeadline("");
    setBio("");
  }

  async function publishGuide() {
    if (!guideTitle.trim()) return;
    setBusy("guide");
    const created = await ask("/creator/guides", "POST", { section: guideSection, title: guideTitle.trim(), summary: guideSummary.trim() || undefined, visibility: guideVisibility });
    setBusy(null);
    if (!created) return;
    setGuideTitle("");
    setGuideSummary("");
    await loadShelf();
  }

  async function openGuide(guide: GuideView) {
    setSelectedGuide(guide);
    const result = await browserFetch(`/creator/guides/${guide.id}`);
    if (result.ok) setSelectedGuide(result.data as GuideView & { passages: GuideCitationView[] });
  }

  async function addCitation() {
    if (!selectedGuide || !citationDocument.trim()) return;
    setBusy("citation");
    await ask(`/creator/guides/${selectedGuide.id}/citations`, "POST", { document: citationDocument.trim(), ordinal: Number(citationOrdinal) || 0, note: citationNote.trim() || undefined });
    setCitationDocument("");
    setCitationOrdinal("");
    setCitationNote("");
    setBusy(null);
    await openGuide(selectedGuide);
  }

  async function removeCitation(citationId: string) {
    if (!selectedGuide) return;
    await ask(`/creator/guides/${selectedGuide.id}/citations/${citationId}`, "DELETE");
    await openGuide(selectedGuide);
  }

  async function eraseGuide(guideId: string) {
    if (!confirm("Erase this guide and its citations?")) return;
    await ask(`/creator/guides/${guideId}`, "DELETE");
    setSelectedGuide(null);
    await loadShelf();
  }

  const figures = fault?.details && typeof fault.details === "object" ? JSON.stringify(fault.details) : "";

  return (
    <div className="stack">
      <Panel eyebrow={profile ? `Published as ${profile.slug}` : "No profile yet — the first guide you publish creates it"} title="Your creator profile">
        <div className="stack-sm">
          {profile ? (
            <div className="row wrap" style={{ gap: "0.6rem", alignItems: "flex-end" }}>
              <div className="grow">
                <strong>{profile.slug}</strong>
                <div className="muted mono">{profile.account.display_name} · {profile.since}</div>
              </div>
              <div className="grow">
                <input aria-label="Headline" className="grow" maxLength={rules.caps.profile_headline_max} onChange={(e) => setHeadline(e.target.value)} placeholder="Headline" value={profile.headline} />
              </div>
              <div className="grow">
                <input aria-label="Biography" className="grow" maxLength={rules.caps.profile_bio_max} onChange={(e) => setBio(e.target.value)} placeholder="Biography" value={profile.bio} />
              </div>
              <button className="btn" disabled={busy !== null} onClick={() => void publishProfile()} type="button">
                {busy === "profile" ? "Updating…" : "Amend profile"}
              </button>
            </div>
          ) : (
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label="Profile slug" className="grow mono" maxLength={64} onChange={(e) => setSlug(e.target.value)} placeholder="your-handle" value={slug} />
              <input aria-label="Headline" className="grow" maxLength={rules.caps.profile_headline_max} onChange={(e) => setHeadline(e.target.value)} placeholder="One line that says what you write about" value={headline} />
              <input aria-label="Biography" className="grow" maxLength={rules.caps.profile_bio_max} onChange={(e) => setBio(e.target.value)} placeholder="A short biography" value={bio} />
              <button className="btn btn--primary" disabled={busy !== null} onClick={() => void publishProfile()} type="button">
                {busy === "profile" ? "Publishing…" : "Publish profile"}
              </button>
            </div>
          )}
          {!profile && (
            <p className="muted mono">The slug is derived from your display name if you leave it blank. It cannot be changed after the first publication.</p>
          )}
          {fault && (
            <p className="notice notice--warn">
              <strong>{fault.code ?? "error"}</strong> — {errorMessage(fault)}
              {figures ? <span className="mono"> {figures}</span> : null}
            </p>
          )}
        </div>
      </Panel>

      <Panel eyebrow={shelfEyebrow(shelf)} title="Guides">
        <div className="stack-sm">
          {!profile ? (
            <p className="muted">Publish your profile first — a guide needs an author.</p>
          ) : (
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label="Guide title" className="grow" maxLength={rules.caps.guide_title_max} onChange={(e) => setGuideTitle(e.target.value)} placeholder="e.g. How to defend a low block" value={guideTitle} />
              <select aria-label="Section" className="mono" onChange={(e) => setGuideSection(e.target.value as GuideIn["section"])} value={guideSection}>
                {SECTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select aria-label="Visibility" className="mono" onChange={(e) => setGuideVisibility(e.target.value as GuideIn["visibility"])} value={guideVisibility}>
                {VISIBILITIES.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
              <input aria-label="Summary" className="grow" maxLength={rules.caps.guide_summary_max} onChange={(e) => setGuideSummary(e.target.value)} placeholder="Summary (optional)" value={guideSummary} />
              <button className="btn btn--primary" disabled={busy !== null || !guideTitle.trim()} onClick={() => void publishGuide()} type="button">
                {busy === "guide" ? "Publishing…" : "Publish guide"}
              </button>
            </div>
          )}
          <p className="muted mono">A guide is a frame. The title, section and summary are yours; the substance stays in the corpus and is cited by address.</p>

          {shelf && shelf.items.length === 0 && (
            <p className="muted">No guides yet. Publish one above.</p>
          )}

          {shelf && shelf.items.length > 0 && (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Guide</th>
                    <th scope="col">Section</th>
                    <th scope="col">Visibility</th>
                    <th scope="col" className="num">Citations</th>
                    <th scope="col" className="num">Moved</th>
                    <th scope="col" className="num">Tokens</th>
                    <th scope="col">Published</th>
                    <th scope="col">Open</th>
                    <th scope="col">Erase</th>
                  </tr>
                </thead>
                <tbody>
                  {shelf.items.map((guide) => (
                    <tr key={guide.id}>
                      <td>
                        <strong>{guide.title}</strong>
                        <div className="muted mono">{guide.slug}</div>
                      </td>
                      <td className="mono">{guide.section}</td>
                      <td className="mono">{guide.visibility}</td>
                      <td className="num">{guide.citations}</td>
                      <td className="num">{guide.moved}</td>
                      <td className="num">{guide.tokens}</td>
                      <td className="mono">{guide.published_on}</td>
                      <td>
                        <button className="btn btn--sm" disabled={busy !== null} onClick={() => void openGuide(guide)} type="button">
                          Open
                        </button>
                      </td>
                      <td>
                        <button className="btn btn--sm" disabled={busy !== null} onClick={() => void eraseGuide(guide.id)} type="button">
                          Erase
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Panel>

      {selectedGuide && (
        <Panel eyebrow={`Guide · ${selectedGuide.title} · ${selectedGuide.section} · ${selectedGuide.visibility}`} title="Citations">
          <div className="stack-sm">
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label="Document slug" className="grow mono" maxLength={80} onChange={(e) => setCitationDocument(e.target.value)} placeholder="document slug (e.g. tactics-2026-pressing)" value={citationDocument} />
              <input aria-label="Passage ordinal" className="mono" maxLength={4} onChange={(e) => setCitationOrdinal(e.target.value)} placeholder="ordinal" type="number" value={citationOrdinal} />
              <input aria-label="Note" className="grow" maxLength={rules.caps.citation_note_max} onChange={(e) => setCitationNote(e.target.value)} placeholder="Your note on this passage (optional)" value={citationNote} />
              <button className="btn btn--primary" disabled={busy !== null || !citationDocument.trim()} onClick={() => void addCitation()} type="button">
                {busy === "citation" ? "Citing…" : "Cite passage"}
              </button>
            </div>
            <p className="muted mono">Cite by (document, ordinal). The chunk&apos;s hash is recorded; if the corpus re-ingests and the passage changes, the guide will show it as moved.</p>

            {selectedGuide.passages && selectedGuide.passages.length === 0 && (
              <p className="muted">No citations yet. Add one above.</p>
            )}

            {selectedGuide.passages && selectedGuide.passages.length > 0 && (
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Document</th>
                      <th scope="col" className="num">Ordinal</th>
                      <th scope="col">Heading</th>
                      <th scope="col">Moved</th>
                      <th scope="col">Note</th>
                      <th scope="col">Remove</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedGuide.passages.map((citation) => (
                      <tr key={citation.id}>
                        <td className="mono">{citation.document}</td>
                        <td className="num">{citation.ordinal}</td>
                        <td>{citation.heading ?? <span className="muted">—</span>}</td>
                        <td>
                          {citation.moved ? (
                            <span className="badge badge--demo">YES</span>
                          ) : (
                            <span className="badge badge--live">NO</span>
                          )}
                        </td>
                        <td className="muted">{citation.note || <span className="mono">—</span>}</td>
                        <td>
                          <button className="btn btn--sm" disabled={busy !== null} onClick={() => void removeCitation(citation.id)} type="button">
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <p className="muted">{selectedGuide.citations} citation{selectedGuide.citations === 1 ? "" : "s"} · {selectedGuide.moved} moved · {selectedGuide.tokens} tokens · {rules.formulas.citations}</p>
          </div>
        </Panel>
      )}
    </div>
  );
}