"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { CallNote, useClubCall } from "@/components/ClubTools";
import { Panel } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import {
  refusalFigures,
  type CareerChallengeIn,
  type CareerChallengeShelfView,
  type CareerChallengeView,
  type CreatorProfileView,
  type CreatorRulesView,
  type GuideDetailView,
  type GuideIn,
  type GuideShelfView,
  type GuideView,
  type ProgramIn,
  type ProgramShelfView,
} from "@/lib/creator";
import type { CareerList, Drill } from "@/lib/types";
import type { ApiError } from "@/lib/types";

const SECTIONS: GuideIn["section"][] = ["plan", "drill", "match", "tactic", "scout", "video"];
const VISIBILITIES: GuideIn["visibility"][] = ["public", "unlisted", "followers"];
/** The verdicts the API publishes for a run; a status nobody has a word for is shown as its own code. */
const ATTEMPT_STATUS_KEY: Record<string, string> = {
  in_progress: "challengeStatusInProgress",
  met: "challengeStatusMet",
  missed: "challengeStatusMissed",
  career_retired: "challengeStatusRetired",
  career_missing: "challengeStatusMissing",
};

/** What a failed *read* says, in the shape a reader can act on: the code, the sentence, and any figure beside it. */
function faultLine(error: ApiError, fallback: string): string {
  return [`${error.code}: ${errorMessage(error, fallback)}`, ...refusalFigures(error.details)].join(" · ");
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
 * * **the answer is painted where the press was made.** Every writing panel holds its own runner, so a refused
 *   guide, citation, program or challenge is answered beside the form that asked: one runner for the whole
 *   workbench put every note in the profile panel, and a reader who pressed "Publish guide" was told about it
 *   somewhere else on the page.
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
  const programCall = useClubCall();
  const [programs, setPrograms] = useState<ProgramShelfView | null>(null);
  const [drills, setDrills] = useState<Drill[]>([]);
  const [programTitle, setProgramTitle] = useState("");
  const [programSummary, setProgramSummary] = useState("");
  const [programVisibility, setProgramVisibility] = useState<ProgramIn["visibility"]>("public");
  const [programSteps, setProgramSteps] = useState<{ drill: string; minutes: string; note: string }[]>([
    { drill: "", minutes: "20", note: "" },
  ]);
  const [citationDocument, setCitationDocument] = useState("");
  const [citationOrdinal, setCitationOrdinal] = useState("");
  const [citationNote, setCitationNote] = useState("");

  const challengeCall = useClubCall();
  const attemptCall = useClubCall();
  const [challenges, setChallenges] = useState<CareerChallengeShelfView | null>(null);
  const [careers, setCareers] = useState<CareerList["items"]>([]);
  const [challengeTitle, setChallengeTitle] = useState("");
  const [challengeSummary, setChallengeSummary] = useState("");
  const [challengeObjective, setChallengeObjective] = useState("wins");
  const [challengeTarget, setChallengeTarget] = useState("3");
  const [challengeWindow, setChallengeWindow] = useState("5");
  const [challengeVisibility, setChallengeVisibility] = useState("public");
  const [selectedChallenge, setSelectedChallenge] = useState<CareerChallengeView | null>(null);
  const [careerChoice, setCareerChoice] = useState("");

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
    setReadFault(faultLine(result.error, t("requestFailed")));
  }, []);

  const loadShelf = useCallback(async () => {
    // Scoped to this account, because the panel is titled "your shelf" and the door's unscoped listing is
    // everybody's public shelf. Without the scope the page showed other people's guides beside an Erase button
    // that only ever answered absence — the door was right and the page was describing a different list.
    const result = await browserFetch<GuideShelfView>(`/creator/guides?creator=${encodeURIComponent(creator)}`);
    if (result.ok) setShelf(result.data);
    else setReadFault(faultLine(result.error, t("requestFailed")));
  }, [creator]);

  const readGuide = useCallback(async (guideId: string) => {
    const result = await browserFetch<GuideDetailView>(`/creator/guides/${guideId}`);
    if (result.ok) setSelectedGuide(result.data);
    else setReadFault(faultLine(result.error, t("requestFailed")));
  }, []);

  const loadPrograms = useCallback(async () => {
    // Scoped to this account for the same reason the guide shelf is: the panel is titled "your
    // shelf", and the door's unscoped listing is everybody's.
    const result = await browserFetch<ProgramShelfView>(`/creator/programs?creator=${encodeURIComponent(creator)}`);
    if (result.ok) setPrograms(result.data);
    else setReadFault(faultLine(result.error, t("requestFailed")));
  }, [creator]);

  const loadDrills = useCallback(async () => {
    const result = await browserFetch<Drill[]>("/trainings/drills");
    if (result.ok) setDrills(result.data);
  }, []);

  const loadChallenges = useCallback(async () => {
    const result = await browserFetch<CareerChallengeShelfView>(`/creator/challenges?creator=${encodeURIComponent(creator)}`);
    if (result.ok) setChallenges(result.data);
    else setReadFault(faultLine(result.error, t("requestFailed")));
  }, [creator]);

  const loadCareers = useCallback(async () => {
    const result = await browserFetch<CareerList>("/careers");
    if (result.ok) {
      setCareers(result.data.items);
      setCareerChoice((current) => current || result.data.items[0]?.slug || "");
      return;
    }
    // An empty select because the door did not answer is not "you have no career": the fault is shown instead.
    setReadFault(faultLine(result.error, t("requestFailed")));
  }, []);

  useEffect(() => {
    void loadProfile();
    void loadShelf();
    void loadPrograms();
    void loadDrills();
    void loadChallenges();
    void loadCareers();
  }, [loadProfile, loadShelf, loadPrograms, loadDrills, loadChallenges, loadCareers]);

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

  async function publishProgram() {
    if (!programTitle.trim() || programSteps.length === 0) return;
    const steps = programSteps
      .filter((step) => step.drill.trim())
      .map((step) => ({ drill: step.drill.trim(), minutes: Number(step.minutes) || 0, note: step.note.trim() || undefined }));
    if (steps.length === 0) return;
    const answer = await programCall.call("program", "/creator/programs", {
      body: { title: programTitle.trim(), summary: programSummary.trim() || undefined, visibility: programVisibility, steps },
    });
    if (!answer) return;
    setProgramTitle("");
    setProgramSummary("");
    setProgramSteps([{ drill: "", minutes: "20", note: "" }]);
    await loadPrograms();
  }

  async function startProgram(programId: string) {
    const answer = await programCall.call("start", `/creator/programs/${programId}/start`);
    if (!answer) return;
    await loadPrograms();
  }

  async function eraseProgram(programId: string) {
    if (!confirm(tp("programEraseConfirm"))) return;
    const answer = await programCall.call("erase", `/creator/programs/${programId}`, { method: "DELETE" });
    if (!answer) return;
    await loadPrograms();
  }

  async function publishChallenge() {
    if (!challengeTitle.trim()) return;
    const body: CareerChallengeIn = {
      title: challengeTitle.trim(),
      summary: challengeSummary.trim() || undefined,
      visibility: challengeVisibility,
      objective: challengeObjective,
      target: Number(challengeTarget) || 0,
      window_rounds: Number(challengeWindow) || 0,
    };
    const answer = await challengeCall.call("challenge", "/creator/challenges", { body });
    if (!answer) return;
    setChallengeTitle("");
    setChallengeSummary("");
    await loadChallenges();
  }

  async function openChallenge(challengeId: string) {
    // A read through the door, so the verdict painted below is the one summed at this read rather than the
    // counts the shelf was painted with.
    const result = await browserFetch<CareerChallengeView>(`/creator/challenges/${challengeId}`);
    if (result.ok) setSelectedChallenge(result.data);
    else setReadFault(faultLine(result.error, t("requestFailed")));
  }

  async function enterChallenge() {
    if (!selectedChallenge || !careerChoice) return;
    const answer = await attemptCall.call("enter", `/creator/challenges/${selectedChallenge.id}/enter`, { body: { career: careerChoice } });
    if (!answer) return;
    await openChallenge(selectedChallenge.id);
    await loadChallenges();
  }

  async function withdrawChallenge() {
    if (!selectedChallenge) return;
    const answer = await attemptCall.call("withdraw", `/creator/challenges/${selectedChallenge.id}/enter`, { method: "DELETE" });
    if (!answer) return;
    await openChallenge(selectedChallenge.id);
    await loadChallenges();
  }

  async function eraseChallenge(challengeId: string) {
    if (!confirm(tp("challengeEraseConfirm"))) return;
    const answer = await challengeCall.call("challenge-erase", `/creator/challenges/${challengeId}`, { method: "DELETE" });
    if (!answer) return;
    if (selectedChallenge?.id === challengeId) setSelectedChallenge(null);
    await loadChallenges();
  }

  async function eraseGuide(guideId: string) {
    if (!confirm(tp("eraseGuideConfirm"))) return;
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

      <Panel
        eyebrow={
          programs
            ? tp("programsEyebrow", { count: programs.total })
            : tp("programsUnread")
        }
        title={tp("programsTitle")}
      >
        <div className="stack-sm" data-creator-programs={programs ? String(programs.total) : "unread"}>
          <div className="row wrap" style={{ gap: "0.6rem", alignItems: "flex-end" }}>
            <input
              aria-label={tp("programLabelTitle")}
              className="grow"
              data-creator-program-title
              maxLength={160}
              onChange={(e) => setProgramTitle(e.target.value)}
              placeholder={tp("programPlaceholderTitle")}
              value={programTitle}
            />
            <input
              aria-label={tp("programLabelSummary")}
              className="grow"
              data-creator-program-summary
              maxLength={600}
              onChange={(e) => setProgramSummary(e.target.value)}
              placeholder={tp("programPlaceholderSummary")}
              value={programSummary}
            />
            <select
              aria-label={tp("labelVisibility")}
              className="mono"
              data-creator-program-visibility
              onChange={(e) => setProgramVisibility(e.target.value as ProgramIn["visibility"])}
              value={programVisibility}
            >
              {VISIBILITIES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
            <button
              className="btn btn--primary"
              data-creator-publish-program
              disabled={programCall.busy !== null || !programTitle.trim()}
              onClick={() => void publishProgram()}
              type="button"
            >
              {tp("programPublish")}
            </button>
          </div>

          {programSteps.map((step, index) => (
            <div className="row wrap" key={index} style={{ gap: "0.6rem", alignItems: "flex-end" }}>
              <select
                aria-label={tp("programDrillLabel")}
                className="grow mono"
                data-creator-program-drill
                onChange={(e) =>
                  setProgramSteps((previous) =>
                    previous.map((row, at) => (at === index ? { ...row, drill: e.target.value } : row)),
                  )
                }
                value={step.drill}
              >
                <option value="">—</option>
                {drills.map((drill) => (
                  <option key={drill.id} value={drill.slug}>
                    {drill.title}
                  </option>
                ))}
              </select>
              <input
                aria-label={tp("programMinutesLabel")}
                className="mono"
                data-creator-program-minutes
                maxLength={3}
                onChange={(e) =>
                  setProgramSteps((previous) =>
                    previous.map((row, at) => (at === index ? { ...row, minutes: e.target.value } : row)),
                  )
                }
                type="number"
                value={step.minutes}
              />
              <input
                aria-label={tp("programNoteLabel")}
                className="grow"
                data-creator-program-note
                maxLength={300}
                onChange={(e) =>
                  setProgramSteps((previous) =>
                    previous.map((row, at) => (at === index ? { ...row, note: e.target.value } : row)),
                  )
                }
                value={step.note}
              />
              {programSteps.length > 1 && (
                <button
                  className="btn btn--sm"
                  data-creator-program-remove-step
                  onClick={() => setProgramSteps((previous) => previous.filter((_, at) => at !== index))}
                  type="button"
                >
                  {tp("programRemoveStep")}
                </button>
              )}
            </div>
          ))}
          <button
            className="btn btn--sm"
            data-creator-program-add-step
            onClick={() => setProgramSteps((previous) => [...previous, { drill: "", minutes: "20", note: "" }])}
            type="button"
          >
            {tp("programAddStep")}
          </button>
          <p className="muted mono">{tp("programNote")}</p>

          {programs && programs.programs.length === 0 && <p className="muted">{tp("noPrograms")}</p>}

          {programs && programs.programs.length > 0 && (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{tp("thProgram")}</th>
                    <th scope="col">{tp("thSteps")}</th>
                    <th scope="col">{tp("thPublished")}</th>
                    <th scope="col">{tp("programStart")}</th>
                    <th scope="col">{tp("erase")}</th>
                  </tr>
                </thead>
                <tbody>
                  {programs.programs.map((program) => (
                    <tr data-creator-program={program.id} key={program.id}>
                      <td>
                        <strong>{program.title}</strong>
                        <div className="muted mono">{program.slug}</div>
                      </td>
                      <td className="num">{program.steps}</td>
                      <td className="mono">{program.published_on}</td>
                      <td>
                        <button
                          className="btn btn--sm"
                          data-creator-program-start
                          disabled={programCall.busy !== null}
                          onClick={() => void startProgram(program.id)}
                          type="button"
                        >
                          {tp("programStart")}
                        </button>
                      </td>
                      <td>
                        <button
                          className="btn btn--sm"
                          data-creator-program-erase
                          disabled={programCall.busy !== null}
                          onClick={() => void eraseProgram(program.id)}
                          type="button"
                        >
                          {tp("erase")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <CallNote note={programCall.note} />
        </div>
      </Panel>

      <Panel
        eyebrow={challenges ? tp("challengesEyebrow", { count: challenges.total }) : tp("challengesUnread")}
        title={tp("challengesTitle")}
      >
        <div className="stack-sm" data-creator-challenges={challenges ? String(challenges.total) : "unread"}>
          <div className="row wrap" style={{ gap: "0.6rem", alignItems: "flex-end" }}>
            <input
              aria-label={tp("challengeLabelTitle")}
              className="grow"
              data-creator-challenge-title
              maxLength={rules.career_challenge_caps.career_challenge_title_max}
              onChange={(e) => setChallengeTitle(e.target.value)}
              placeholder={tp("challengePlaceholderTitle")}
              value={challengeTitle}
            />
            <input
              aria-label={tp("challengeLabelSummary")}
              className="grow"
              data-creator-challenge-summary
              maxLength={rules.career_challenge_caps.career_challenge_summary_max}
              onChange={(e) => setChallengeSummary(e.target.value)}
              placeholder={tp("challengePlaceholderSummary")}
              value={challengeSummary}
            />
            <select
              aria-label={tp("challengeLabelObjective")}
              className="mono"
              data-creator-challenge-objective
              onChange={(e) => setChallengeObjective(e.target.value)}
              value={challengeObjective}
            >
              {Object.keys(rules.career_challenge_objective_kinds).map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </select>
            <input
              aria-label={tp("challengeLabelTarget")}
              className="mono"
              data-creator-challenge-target
              maxLength={2}
              min={rules.career_challenge_caps.career_challenge_target_min}
              max={rules.career_challenge_caps.career_challenge_target_max}
              onChange={(e) => setChallengeTarget(e.target.value)}
              type="number"
              value={challengeTarget}
            />
            <input
              aria-label={tp("challengeLabelWindow")}
              className="mono"
              data-creator-challenge-window
              maxLength={2}
              min={rules.career_challenge_caps.career_challenge_window_min}
              max={rules.career_challenge_caps.career_challenge_window_max}
              onChange={(e) => setChallengeWindow(e.target.value)}
              type="number"
              value={challengeWindow}
            />
            <select
              aria-label={tp("labelVisibility")}
              className="mono"
              data-creator-challenge-visibility
              onChange={(e) => setChallengeVisibility(e.target.value)}
              value={challengeVisibility}
            >
              {VISIBILITIES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
            <button
              className="btn btn--primary"
              data-creator-publish-challenge
              disabled={challengeCall.busy !== null || !challengeTitle.trim()}
              onClick={() => void publishChallenge()}
              type="button"
            >
              {tp("challengePublish")}
            </button>
          </div>
          {/* The formula the door publishes for the chosen objective, quoted rather than paraphrased. */}
          <p className="muted mono" data-creator-challenge-formula>
            {rules.career_challenge_objective_kinds[challengeObjective]}
          </p>
          <p className="muted mono">{tp("challengeNote")}</p>

          {challenges && challenges.items.length === 0 && <p className="muted">{tp("challengeNoChallenges")}</p>}

          {challenges && challenges.items.length > 0 && (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{tp("thChallenge")}</th>
                    <th scope="col">{tp("thObjective")}</th>
                    <th scope="col" className="num">{tp("thWindow")}</th>
                    <th scope="col">{tp("thVisibility")}</th>
                    <th scope="col" className="num">{tp("thAttempts")}</th>
                    <th scope="col">{tp("thEntered")}</th>
                    <th scope="col">{tp("thPublished")}</th>
                    <th scope="col">{t("open")}</th>
                    <th scope="col">{tp("erase")}</th>
                  </tr>
                </thead>
                <tbody>
                  {challenges.items.map((challenge) => (
                    <tr data-creator-challenge={challenge.id} key={challenge.id}>
                      <td>
                        <strong>{challenge.title}</strong>
                        <div className="muted mono">{challenge.slug}</div>
                      </td>
                      <td className="mono">
                        {challenge.objective.kind} {challenge.objective.target}
                      </td>
                      <td className="num">{challenge.window_rounds}</td>
                      <td className="mono">{challenge.visibility}</td>
                      <td className="num">{challenge.attempts}</td>
                      <td>
                        {challenge.entered ? <span className="badge badge--live">{t("yes")}</span> : <span className="badge badge--demo">{t("no")}</span>}
                      </td>
                      <td className="mono">{challenge.published_on}</td>
                      <td>
                        <button className="btn btn--sm" data-creator-challenge-open disabled={challengeCall.busy !== null} onClick={() => void openChallenge(challenge.id)} type="button">
                          {t("open")}
                        </button>
                      </td>
                      <td>
                        <button className="btn btn--sm" data-creator-challenge-erase disabled={challengeCall.busy !== null} onClick={() => void eraseChallenge(challenge.id)} type="button">
                          {tp("erase")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <CallNote note={challengeCall.note} />
        </div>
      </Panel>

      {selectedChallenge && (
        <Panel
          eyebrow={tp("challengeDetailEyebrow", {
            title: selectedChallenge.title,
            kind: selectedChallenge.objective.kind,
            target: selectedChallenge.objective.target,
            window: selectedChallenge.window_rounds,
            attempts: selectedChallenge.figures.attempts,
          })}
          title={tp("challengeDetailTitle")}
        >
          <div className="stack-sm" data-creator-challenge-detail={selectedChallenge.id}>
            <p className="muted">{selectedChallenge.summary || selectedChallenge.rule}</p>
            <p className="muted mono">{selectedChallenge.objective.formula}</p>

            {!selectedChallenge.attempt && careers.length === 0 && <p className="muted">{tp("challengeNoCareers")}</p>}

            {!selectedChallenge.attempt && careers.length > 0 && (
              <div className="row wrap" style={{ gap: "0.6rem", alignItems: "flex-end" }}>
                <select
                  aria-label={tp("challengeLabelCareer")}
                  className="grow mono"
                  data-creator-challenge-career
                  onChange={(e) => setCareerChoice(e.target.value)}
                  value={careerChoice}
                >
                  {careers.map((career) => (
                    <option key={career.slug} value={career.slug}>
                      {career.manager_name} · {career.club_name} · {career.status}
                    </option>
                  ))}
                </select>
                <button className="btn btn--primary" data-creator-challenge-enter disabled={attemptCall.busy !== null || !careerChoice} onClick={() => void enterChallenge()} type="button">
                  {tp("challengeEnter")}
                </button>
              </div>
            )}

            {selectedChallenge.attempt ? (
              <div className="stack-sm" data-creator-challenge-attempt={selectedChallenge.attempt.status}>
                <p>
                  <strong data-creator-challenge-status>
                    {ATTEMPT_STATUS_KEY[selectedChallenge.attempt.status] ? tp(ATTEMPT_STATUS_KEY[selectedChallenge.attempt.status]) : selectedChallenge.attempt.status}
                  </strong>
                  {" · "}
                  {tp("challengeVerdict", {
                    actual: selectedChallenge.attempt.actual ?? "—",
                    target: selectedChallenge.attempt.target,
                    status: selectedChallenge.attempt.status,
                  })}
                </p>
                <p className="muted mono">
                  {selectedChallenge.attempt.career.stored
                    ? `${selectedChallenge.attempt.career.slug} · ${selectedChallenge.attempt.career.manager_name ?? ""} · ${selectedChallenge.attempt.career.club_name ?? ""}`
                    : tp("challengeCareerGone", { slug: selectedChallenge.attempt.career.slug })}
                </p>
                <p className="muted mono" data-creator-challenge-window-line>
                  {tp("challengeWindowLine", {
                    start: selectedChallenge.attempt.window.start_round,
                    end: selectedChallenge.attempt.window.end_round,
                    played: selectedChallenge.attempt.window.played ?? "—",
                    remaining: selectedChallenge.attempt.window.remaining ?? "—",
                    closed: selectedChallenge.attempt.window.closed ? tp("challengeWindowClosed") : tp("challengeWindowOpen"),
                  })}
                </p>
                <p className="muted">{selectedChallenge.attempt.reason}</p>
                <button className="btn" data-creator-challenge-withdraw disabled={attemptCall.busy !== null} onClick={() => void withdrawChallenge()} type="button">
                  {tp("challengeWithdraw")}
                </button>

                <h3 style={{ margin: "0.4rem 0 0" }}>{tp("challengeRounds")}</h3>
                {selectedChallenge.attempt.rounds.length === 0 ? (
                  <p className="muted">{tp("challengeNoRounds")}</p>
                ) : (
                  <div className="world-tablewrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th scope="col" className="num">{tp("thRound")}</th>
                          <th scope="col">{tp("thOutcome")}</th>
                          <th scope="col">{tp("thScore")}</th>
                          <th scope="col" className="num">{tp("thPoints")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedChallenge.attempt.rounds.map((round) => (
                          <tr data-creator-challenge-round={round.round_index} key={round.round_index}>
                            <td className="num">{round.round_index}</td>
                            <td className="mono">{round.outcome}</td>
                            <td className="mono">
                              {round.club_goals}–{round.opponent_goals}
                            </td>
                            <td className="num">{round.points}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ) : (
              <p className="muted" data-creator-challenge-no-attempt>
                {tp("challengeNoAttempt")}
              </p>
            )}
            <CallNote note={attemptCall.note} />
          </div>
        </Panel>
      )}

      {selectedGuide && (
        <Panel
          eyebrow={tp("guideEyebrow", {
            title: selectedGuide.title,
            section: selectedGuide.section,
            visibility: selectedGuide.visibility,
            citations: selectedGuide.citations,
            moved: selectedGuide.moved,
            tokens: selectedGuide.tokens,
          })}
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
