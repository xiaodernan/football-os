"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { CallNote, useClubCall } from "@/components/ClubTools";
import { Panel } from "@/components/ui";
import { browserFetch } from "@/lib/api";
import { refusalFigures, type CreatorProfileView, type CreatorRulesView, type GuideDetailView, type GuideIn, type GuideShelfView, type GuideView } from "@/lib/creator";
import type { ApiError } from "@/lib/types";

const SECTIONS: GuideIn["section"][] = ["plan", "drill", "match", "tactic", "scout", "video"];
const VISIBILITIES: GuideIn["visibility"][] = ["public", "unlisted", "followers"];

/** What a failed *read* says, in the shape a reader can act on: the code, the sentence, and any figure beside it. */
function faultLine(error: ApiError): string {
  return [`${error.code}: ${error.message}`, ...refusalFigures(error.details)].join(" · ");
}

function shelfEyebrow(shelf: GuideShelfView | null): string {
  if (!shelf) return "your shelf has not been read yet";
  const parts = [`${shelf.total} guide${shelf.total === 1 ? "" : "s"} on your shelf`];
  if (shelf.section) parts.push(`section: ${shelf.section}`);
  return parts.join(" · ");
}

/**
 * The one workbench this tier needs: publish a profile, frame a guide, cite a passage by address.
 *
 * Four rules are held by the shape of this component rather than by a comment in it:
 *
 * * **every write is answered by the door.** `useClubCall` prints what the API said — its status, its code, its
 *   sentence and the figures that came with it — so a press the server refused cannot look like a press that
 *   worked, and `router.refresh()` re-reads the server page so the counts above this panel are the server's.
 * * **the answer is painted where the press was made.** Three panels write here and each holds its own runner, so a
 *   refused guide or citation is answered beside the form that asked: one runner for the whole workbench put every
 *   note in the profile panel, and a reader who pressed "Publish guide" was told about it somewhere else on the page.
 * * **nothing is remembered here that the door already counts.** The shelf and the open guide are re-read through
 *   `GET` after every write, so a figure in this table is the door's own, counted from its rows at that read.
 * * **a failed read is never folded into an empty state.** "You have published nothing yet" and "the profile door
 *   did not answer" are different facts, and a page that showed the first for the second would be telling the reader
 *   something the server never said.
 */
export function CreatorWorkbench({ rules, creator }: { rules: CreatorRulesView; creator: string }) {
  const t = useTranslations("common");
  const profileCall = useClubCall();
  const guideCall = useClubCall();
  const citationCall = useClubCall();

  const [readFault, setReadFault] = useState("");
  const [profile, setProfile] = useState<CreatorProfileView | null>(null);
  const [slug, setSlug] = useState("");
  const [headline, setHeadline] = useState("");
  const [bio, setBio] = useState("");

  const [shelf, setShelf] = useState<GuideShelfView | null>(null);
  const [guideTitle, setGuideTitle] = useState("");
  const [guideSummary, setGuideSummary] = useState("");
  const [guideSection, setGuideSection] = useState<GuideIn["section"]>("plan");
  const [guideVisibility, setGuideVisibility] = useState<GuideIn["visibility"]>("public");

  const [selectedGuide, setSelectedGuide] = useState<GuideDetailView | null>(null);
  const [citationDocument, setCitationDocument] = useState("");
  const [citationOrdinal, setCitationOrdinal] = useState("");
  const [citationNote, setCitationNote] = useState("");

  const loadProfile = useCallback(async () => {
    const result = await browserFetch<CreatorProfileView>("/creator/profile");
    if (result.ok) {
      setProfile(result.data);
      setHeadline(result.data.headline);
      setBio(result.data.bio);
      setReadFault("");
      return;
    }
    // `no_such_creator` is the tier's honest answer to "this account has published nothing yet": a state, not a
    // failure, and the panel below says so. Any other answer is a fault this page has to show rather than hide.
    if (result.error.code === "no_such_creator") {
      setProfile(null);
      setReadFault("");
      return;
    }
    setReadFault(faultLine(result.error));
  }, []);

  const loadShelf = useCallback(async () => {
    // Scoped to this account, because the panel is titled "your shelf" and the door's unscoped listing is
    // everybody's public shelf. Without the scope the page showed other people's guides beside an Erase button
    // that only ever answered absence — the door was right and the page was describing a different list.
    const result = await browserFetch<GuideShelfView>(`/creator/guides?creator=${encodeURIComponent(creator)}`);
    if (result.ok) setShelf(result.data);
    else setReadFault(faultLine(result.error));
  }, [creator]);

  const readGuide = useCallback(async (guideId: string) => {
    const result = await browserFetch<GuideDetailView>(`/creator/guides/${guideId}`);
    if (result.ok) setSelectedGuide(result.data);
    else setReadFault(faultLine(result.error));
  }, []);

  useEffect(() => {
    void loadProfile();
    void loadShelf();
  }, [loadProfile, loadShelf]);

  async function publishProfile() {
    const answer = await profileCall.call("profile", "/creator/profile", { body: { slug: slug.trim() || undefined, headline: headline.trim() || undefined, bio: bio.trim() || undefined } });
    if (!answer) return;
    setSlug("");
    await loadProfile();
  }

  async function publishGuide() {
    if (!guideTitle.trim()) return;
    const answer = await guideCall.call("guide", "/creator/guides", { body: { section: guideSection, title: guideTitle.trim(), summary: guideSummary.trim() || undefined, visibility: guideVisibility } });
    if (!answer) return;
    setGuideTitle("");
    setGuideSummary("");
    await loadShelf();
  }

  async function openGuide(guide: GuideView) {
    setSelectedGuide({ ...guide, passages: [] });
    await readGuide(guide.id);
  }

  async function addCitation() {
    if (!selectedGuide || !citationDocument.trim()) return;
    const answer = await citationCall.call("cite", `/creator/guides/${selectedGuide.id}/citations`, { body: { document: citationDocument.trim(), ordinal: Number(citationOrdinal) || 0, note: citationNote.trim() || undefined } });
    if (!answer) return;
    setCitationDocument("");
    setCitationOrdinal("");
    setCitationNote("");
    await readGuide(selectedGuide.id);
    await loadShelf();
  }

  async function removeCitation(citationId: string) {
    if (!selectedGuide) return;
    const answer = await citationCall.call("uncite", `/creator/guides/${selectedGuide.id}/citations/${citationId}`, { method: "DELETE" });
    if (!answer) return;
    await readGuide(selectedGuide.id);
    await loadShelf();
  }

  async function eraseGuide(guideId: string) {
    if (!confirm("Erase this guide and its citations?")) return;
    const answer = await guideCall.call("erase", `/creator/guides/${guideId}`, { method: "DELETE" });
    if (!answer) return;
    setSelectedGuide(null);
    await loadShelf();
  }

  return (
    <div className="stack">
      <Panel eyebrow={profile ? `Published as ${profile.slug}` : "No profile yet — the first publication creates it"} title="Your creator profile">
        <div className="stack-sm" data-creator-profile={profile ? "published" : "none"}>
          {readFault && (
            <p className="notice notice--warn" data-creator-read-fault>
              {readFault}
            </p>
          )}
          {profile ? (
            <div className="row wrap" style={{ gap: "0.6rem", alignItems: "flex-end" }}>
              <div className="grow">
                <strong data-creator-slug-shown>{profile.slug}</strong>
                <div className="muted mono" data-creator-account>
                  {profile.account.display_name} · since {profile.since} · {profile.guides} guide(s) · {profile.subscribers} subscriber(s)
                </div>
              </div>
              <input aria-label="Headline" className="grow" data-creator-headline maxLength={rules.caps.profile_headline_max} onChange={(e) => setHeadline(e.target.value)} placeholder="Headline" value={headline} />
              <input aria-label="Biography" className="grow" data-creator-bio maxLength={rules.caps.profile_bio_max} onChange={(e) => setBio(e.target.value)} placeholder="Biography" value={bio} />
              <button className="btn" data-creator-publish-profile disabled={profileCall.busy !== null} onClick={() => void publishProfile()} type="button">
                {profileCall.busy === "profile" ? "Updating…" : "Amend profile"}
              </button>
            </div>
          ) : (
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label="Profile slug" className="grow mono" data-creator-slug maxLength={64} onChange={(e) => setSlug(e.target.value)} placeholder="your-handle" value={slug} />
              <input aria-label="Headline" className="grow" data-creator-headline maxLength={rules.caps.profile_headline_max} onChange={(e) => setHeadline(e.target.value)} placeholder="One line that says what you write about" value={headline} />
              <input aria-label="Biography" className="grow" data-creator-bio maxLength={rules.caps.profile_bio_max} onChange={(e) => setBio(e.target.value)} placeholder="A short biography" value={bio} />
              <button className="btn btn--primary" data-creator-publish-profile disabled={profileCall.busy !== null} onClick={() => void publishProfile()} type="button">
                {profileCall.busy === "profile" ? "Publishing…" : "Publish profile"}
              </button>
            </div>
          )}
          {!profile && (
            <p className="muted mono">The slug is derived from your display name if you leave it blank. It cannot be changed after the first publication.</p>
          )}
          <CallNote note={profileCall.note} />
        </div>
      </Panel>

      <Panel eyebrow={shelfEyebrow(shelf)} title="Guides">
        <div className="stack-sm" data-creator-shelf={shelf ? String(shelf.total) : "unread"}>
          {!profile ? (
            <p className="muted">Publish your profile first — a guide needs an author.</p>
          ) : (
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label="Guide title" className="grow" data-creator-guide-title maxLength={rules.caps.guide_title_max} onChange={(e) => setGuideTitle(e.target.value)} placeholder="e.g. How to defend a low block" value={guideTitle} />
              <select aria-label="Section" className="mono" data-creator-guide-section onChange={(e) => setGuideSection(e.target.value as GuideIn["section"])} value={guideSection}>
                {SECTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select aria-label="Visibility" className="mono" data-creator-guide-visibility onChange={(e) => setGuideVisibility(e.target.value as GuideIn["visibility"])} value={guideVisibility}>
                {VISIBILITIES.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
              <input aria-label="Summary" className="grow" data-creator-guide-summary maxLength={rules.caps.guide_summary_max} onChange={(e) => setGuideSummary(e.target.value)} placeholder="Summary (optional)" value={guideSummary} />
              <button className="btn btn--primary" data-creator-publish-guide disabled={guideCall.busy !== null || !guideTitle.trim()} onClick={() => void publishGuide()} type="button">
                {guideCall.busy === "guide" ? "Publishing…" : "Publish guide"}
              </button>
            </div>
          )}
          <p className="muted mono">A guide is a frame. The title, section and summary are yours; the substance stays in the corpus and is cited by address.</p>

          {shelf && shelf.items.length === 0 && <p className="muted">No guides yet. Publish one above.</p>}

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
                    <th scope="col">{t("open")}</th>
                    <th scope="col">Erase</th>
                  </tr>
                </thead>
                <tbody>
                  {shelf.items.map((guide) => (
                    <tr data-creator-guide={guide.id} key={guide.id}>
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
                        <button className="btn btn--sm" data-creator-guide-open disabled={guideCall.busy !== null} onClick={() => void openGuide(guide)} type="button">
                          {t("open")}
                        </button>
                      </td>
                      <td>
                        <button className="btn btn--sm" data-creator-guide-erase disabled={guideCall.busy !== null} onClick={() => void eraseGuide(guide.id)} type="button">
                          Erase
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <CallNote note={guideCall.note} />
        </div>
      </Panel>

      {selectedGuide && (
        <Panel
          eyebrow={`${selectedGuide.title} · ${selectedGuide.section} · ${selectedGuide.visibility} · ${selectedGuide.citations} citation(s) · ${selectedGuide.moved} moved · ${selectedGuide.tokens} tokens`}
          title="Citations"
        >
          <div className="stack-sm" data-creator-citations={selectedGuide.id}>
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label="Document slug" className="grow mono" data-creator-cite-document maxLength={80} onChange={(e) => setCitationDocument(e.target.value)} placeholder="document slug (e.g. tactics-2026-pressing)" value={citationDocument} />
              <input aria-label="Passage ordinal" className="mono" data-creator-cite-ordinal maxLength={4} onChange={(e) => setCitationOrdinal(e.target.value)} placeholder="ordinal" type="number" value={citationOrdinal} />
              <input aria-label="Note" className="grow" data-creator-cite-note maxLength={rules.caps.citation_note_max} onChange={(e) => setCitationNote(e.target.value)} placeholder="Your note on this passage (optional)" value={citationNote} />
              <button className="btn btn--primary" data-creator-cite disabled={citationCall.busy !== null || !citationDocument.trim()} onClick={() => void addCitation()} type="button">
                {citationCall.busy === "cite" ? "Citing…" : "Cite passage"}
              </button>
            </div>
            <p className="muted mono">Cite by (document slug, ordinal). The chunk&apos;s hash is recorded; if the corpus re-ingests and the passage changes, the guide will say the passage has moved.</p>

            {selectedGuide.passages.length === 0 && <p className="muted">No citations yet. Add one above.</p>}

            {selectedGuide.passages.length > 0 && (
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
                      <tr data-creator-citation={citation.id} key={citation.id}>
                        <td className="mono">{citation.document}</td>
                        <td className="num">{citation.ordinal}</td>
                        <td>{citation.heading ?? <span className="muted">—</span>}</td>
                        <td>{citation.moved ? <span className="badge badge--demo">YES</span> : <span className="badge badge--live">NO</span>}</td>
                        <td className="muted">{citation.note || <span className="mono">—</span>}</td>
                        <td>
                          <button className="btn btn--sm" data-creator-citation-remove disabled={citationCall.busy !== null} onClick={() => void removeCitation(citation.id)} type="button">
                            {t("remove")}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <p className="muted" style={{ fontSize: "0.82rem" }}>{rules.formulas.citations}</p>
            <CallNote note={citationCall.note} />
          </div>
        </Panel>
      )}
    </div>
  );
}
