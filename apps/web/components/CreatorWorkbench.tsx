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

function shelfEyebrow(
  shelf: GuideShelfView | null,
  t: (key: string, values?: Record<string, string | number>) => string,
): string {
  if (!shelf) return t("shelfUnread");
  const parts = [t("shelfCount", { count: shelf.total })];
  if (shelf.section) parts.push(t("shelfSection", { section: shelf.section }));
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
  const tp = useTranslations("creator");
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
      <Panel
        eyebrow={profile ? tp("profilePublishedAs", { slug: profile.slug }) : tp("profileNone")}
        title={tp("profileTitle")}
      >
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
                  {profile.account.display_name} · {tp("profileSince", { date: profile.since })} ·{" "}
                  {tp("guidesCount", { count: profile.guides })} ·{" "}
                  {tp("subscribersCount", { count: profile.subscribers })}
                </div>
              </div>
              <input aria-label={tp("labelHeadline")} className="grow" data-creator-headline maxLength={rules.caps.profile_headline_max} onChange={(e) => setHeadline(e.target.value)} placeholder={tp("labelHeadline")} value={headline} />
              <input aria-label={tp("labelBiography")} className="grow" data-creator-bio maxLength={rules.caps.profile_bio_max} onChange={(e) => setBio(e.target.value)} placeholder={tp("labelBiography")} value={bio} />
              <button className="btn" data-creator-publish-profile disabled={profileCall.busy !== null} onClick={() => void publishProfile()} type="button">
                {profileCall.busy === "profile" ? tp("updating") : tp("amendProfile")}
              </button>
            </div>
          ) : (
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label={tp("labelProfileSlug")} className="grow mono" data-creator-slug maxLength={64} onChange={(e) => setSlug(e.target.value)} placeholder="your-handle" value={slug} />
              <input aria-label={tp("labelHeadline")} className="grow" data-creator-headline maxLength={rules.caps.profile_headline_max} onChange={(e) => setHeadline(e.target.value)} placeholder={tp("placeholderHeadline")} value={headline} />
              <input aria-label={tp("labelBiography")} className="grow" data-creator-bio maxLength={rules.caps.profile_bio_max} onChange={(e) => setBio(e.target.value)} placeholder={tp("placeholderBiography")} value={bio} />
              <button className="btn btn--primary" data-creator-publish-profile disabled={profileCall.busy !== null} onClick={() => void publishProfile()} type="button">
                {profileCall.busy === "profile" ? tp("publishing") : tp("publishProfile")}
              </button>
            </div>
          )}
          {!profile && (
            <p className="muted mono">{tp("slugNote")}</p>
          )}
          <CallNote note={profileCall.note} />
        </div>
      </Panel>

      <Panel eyebrow={shelfEyebrow(shelf, tp)} title={tp("guidesTitle")}>
        <div className="stack-sm" data-creator-shelf={shelf ? String(shelf.total) : "unread"}>
          {!profile ? (
            <p className="muted">{tp("profileFirst")}</p>
          ) : (
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label={tp("labelGuideTitle")} className="grow" data-creator-guide-title maxLength={rules.caps.guide_title_max} onChange={(e) => setGuideTitle(e.target.value)} placeholder={tp("placeholderGuideTitle")} value={guideTitle} />
              <select aria-label={tp("labelSection")} className="mono" data-creator-guide-section onChange={(e) => setGuideSection(e.target.value as GuideIn["section"])} value={guideSection}>
                {SECTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select aria-label={tp("labelVisibility")} className="mono" data-creator-guide-visibility onChange={(e) => setGuideVisibility(e.target.value as GuideIn["visibility"])} value={guideVisibility}>
                {VISIBILITIES.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
              {/* the parenthetical keeps its own lower case: t("optional") is the label form "Optional" */}
              <input aria-label={t("summary")} className="grow" data-creator-guide-summary maxLength={rules.caps.guide_summary_max} onChange={(e) => setGuideSummary(e.target.value)} placeholder={`${t("summary")} (${t("optional").toLowerCase()})`} value={guideSummary} />
              <button className="btn btn--primary" data-creator-publish-guide disabled={guideCall.busy !== null || !guideTitle.trim()} onClick={() => void publishGuide()} type="button">
                {guideCall.busy === "guide" ? tp("publishing") : tp("publishGuide")}
              </button>
            </div>
          )}
          <p className="muted mono">{tp("guideFrameNote")}</p>

          {shelf && shelf.items.length === 0 && <p className="muted">{tp("noGuides")}</p>}

          {shelf && shelf.items.length > 0 && (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{tp("thGuide")}</th>
                    <th scope="col">{tp("thSection")}</th>
                    <th scope="col">{tp("thVisibility")}</th>
                    <th scope="col" className="num">{tp("thCitations")}</th>
                    <th scope="col" className="num">{tp("thMoved")}</th>
                    <th scope="col" className="num">{tp("thTokens")}</th>
                    <th scope="col">{tp("thPublished")}</th>
                    <th scope="col">{t("open")}</th>
                    <th scope="col">{tp("erase")}</th>
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
                          {tp("erase")}
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
          title={tp("citationsTitle")}
        >
          <div className="stack-sm" data-creator-citations={selectedGuide.id}>
            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <input aria-label={tp("labelDocumentSlug")} className="grow mono" data-creator-cite-document maxLength={80} onChange={(e) => setCitationDocument(e.target.value)} placeholder={tp("placeholderDocumentSlug")} value={citationDocument} />
              <input aria-label={tp("labelPassageOrdinal")} className="mono" data-creator-cite-ordinal maxLength={4} onChange={(e) => setCitationOrdinal(e.target.value)} placeholder="ordinal" type="number" value={citationOrdinal} />
              <input aria-label={tp("labelNote")} className="grow" data-creator-cite-note maxLength={rules.caps.citation_note_max} onChange={(e) => setCitationNote(e.target.value)} placeholder={tp("placeholderNote")} value={citationNote} />
              <button className="btn btn--primary" data-creator-cite disabled={citationCall.busy !== null || !citationDocument.trim()} onClick={() => void addCitation()} type="button">
                {citationCall.busy === "cite" ? tp("citing") : tp("citePassage")}
              </button>
            </div>
            <p className="muted mono">{tp("citeNote")}</p>

            {selectedGuide.passages.length === 0 && <p className="muted">{tp("noCitations")}</p>}

            {selectedGuide.passages.length > 0 && (
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{tp("thDocument")}</th>
                      <th scope="col" className="num">{tp("thOrdinal")}</th>
                      <th scope="col">{tp("thHeading")}</th>
                      <th scope="col">{tp("thMoved")}</th>
                      <th scope="col">{tp("thNote")}</th>
                      <th scope="col">{tp("thRemove")}</th>
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
