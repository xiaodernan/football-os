#!/usr/bin/env node
/*
 * The locales' technical tokens: the values that are the same in every language, and only those.
 *
 * Two claims in this project were conventions rather than measurements, and this file is both of them
 * turned into checks.
 *
 * **The first: "the identical values are the ones that are supposed to be identical."** A key whose
 * Chinese value is byte-identical to its English value is, by that claim, a technical token — an
 * acronym, a unit, an API field name printed as itself, a proper name used as an example. The claim was
 * never checked, so an English *phrase* could sit in the Chinese catalogue untranslated and nobody
 * would know: a Chinese reader saw "weekly minutes" as a cap's name, and "pressing, transitions" as an
 * example of what to type. So the set of identical values is now **named**, key by key, with the reason
 * each one is the same in every language — and a key that is not named is a finding.
 *
 * **The second: "the English catalogue is English."** `en.json` held `scout.placeholder` in Chinese —
 * "e.g. 找一个 22 岁以下、左脚、能踢 CM、预算 2000 万以下的球员" — so an English reader was shown a Chinese
 * sentence, and the Chinese catalogue's identical value made the coverage figures call it translated.
 * Neither the copy gate (which reads the source, not the catalogue) nor the locale sweep (which looks
 * for *English* on a Chinese page) could see it. So the English file now has to hold no Chinese.
 *
 * Files only: no server, no browser, no port, which is why it belongs with the other file-only gates in
 * `scripts/check.sh` and in CI.
 *
 * **Two holes found in it on 2026-11-08, both the same shape.** Its `LOCALES` named `zh` and `zh-TW` in the
 * source, so an `ar.json` that is a byte copy of `en.json` — every message of it still English — added
 * nothing to any of these checks and this gate stayed green beside it; the measured pre-fix run is §41. And
 * every walk here descended exactly two levels, so a Chinese sentence written three levels deep inside
 * `en.json` passed the very check this file was written to hold: `en.json` carrying Chinese was the
 * *founding* defect, and the census that looks for it could not see past `probe.deep`. Both are cured — the
 * directory now decides which locales are judged, every leaf at every depth is visited, a locale that ships
 * without a floor on record is a finding rather than an absence, and a check holds that this table is copied
 * nowhere else.
 */

import { readdirSync, readFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const MESSAGES = join(WEB, "messages");
const SELF = basename(fileURLToPath(import.meta.url));

/**
 * Discovery, not a candidate list: the directory decides which locales are judged.
 *
 * The old line was `const LOCALES = ["zh", "zh-TW"]`. A locale that ships — `ar.json`, `he.json`, a `fr.json`
 * nobody intended — joined every catalogue in the build and was judged by none of these five checks, which is
 * how a byte copy of English could sit beside a green gate.
 */
const SHIPPED = readdirSync(MESSAGES)
  .filter((name) => name.endsWith(".json"))
  .map((name) => basename(name, ".json"))
  .sort();
const LOCALES = SHIPPED.filter((locale) => locale !== "en");

/**
 * The values that are the same in every language, and why.
 *
 * Each entry names a key and the *kind* of thing it is, because a list without reasons is the same as
 * no list at all: it is a place where an untranslated phrase goes to stop the gate from noticing.
 */
const TOKENS = new Map([
  // An acronym, a unit, or a file format: the same word in every language.
  ["settings.apiBadge", "the API's own name"],
  ["world.thOvr", "the rating scale's own name"],
  ["world.thPot", "the rating scale's own name"],
  ["worldTeam.thOvr", "the rating scale's own name"],
  ["worldTeam.thPot", "the rating scale's own name"],
  ["worldPlayer.thRpe", "the scale's own name"],
  ["worldTraining.thRpe", "the scale's own name"],
  ["careerDetail.thLedgerXg", "the metric's own name"],
  ["simulationAggregates.thXg", "the metric's own name"],
  ["simulate.blockThXG", "the metric's own name"],
  ["club.tableHeaderRPE", "the scale's own name"],
  ["club.tableHeaderHTTP", "the protocol's own name"],
  ["portfolio.pdfTitle", "the file format's own name"],
  ["knowledge.bm25Chip", "the ranking function's own name"],

  // An API field name printed as itself: the name an operator greps for, and the name the tier owns.
  ["club.capNameMax", "an API field name"],
  ["club.capTeamNameMax", "an API field name"],
  ["club.capNoteMax", "an API field name"],
  ["club.capCountry", "an API field name"],
  ["club.capKinds", "an API field name"],
  ["club.capRatingRange", "an API field name"],
  ["club.capReviewWeeksRange", "an API field name"],
  ["worldPlayer.recentFormEyebrow", "an API field name"],
  ["academy.sharedWithGuardian", "an API field name"],
  ["scout.comparisonNull", "an API field name and its null"],
  ["knowledge.provenanceFooter", "the API's own field names"],
  ["video.measuredEyebrow", "the API's own field name"],

  // A template whose parts are names, numbers or the API's own enums: there is no sentence to translate.
  ["tactics.tableA", "a template of a side's name"],
  ["tactics.tableB", "a template of a side's name"],
  ["tactics.tableDelta", "the two sides' own letters"],
  ["challenges.clubOption", "a template of names and figures"],
  ["challenges.cardObjective", "a template of a figure"],
  ["challenges.vs", "the word every football page uses"],
  ["community.busyEllipsis", "a punctuation mark"],
  ["simulate.xgLine", "a template of the metric's own name and two figures"],
  ["club.matrixDefault", "a template of the API's own values"],
  ["club.consentEyebrow", "a template of two figures"],
  ["careerDetail.eyebrow", "a template of names"],
  ["worldPlayer.eyebrow", "a template of names"],
  ["worldMatch.eyebrow", "a template of names"],
  ["worldCompetition.metaTitleKind", "a template of the API's own kind"],
  ["graph.listingTitle", "a template of the API's own kind"],
  ["graph.backLabel", "a template of the API's own kind and slug"],

  // A proper name used as an example of a name.
  ["club.createNamePlaceholder", "an example proper name"],
  ["club.teamNamePlaceholder", "an example proper name"],
  ["club.playerSlugPlaceholder", "an example slug"],
]);

/**
 * French-only identical values, named key by key (2026-11-09, the fr milestone).
 *
 * TOKENS above holds the language-neutral set: those keys are identical in EVERY catalogue, and a
 * locale that translated one has been charged by this gate for §41 and its siblings. The values
 * here are not language-neutral: French and English share them as loanword doublets (club, score,
 * format, note, section…), as the tables' own abbreviations (Min, RPE, p50), or as templates of
 * names and figures — and the Chinese, Arabic and Hebrew catalogues translate them. French exempts
 * exactly this set and nothing else; every other locale answers to TOKENS alone.
 */
const FR_TOKENS = new Map([
  // French–English identical values, named key by key (2026-11-09, the fr milestone).
  // Most are loanword doublets (club, score, note, section…) or templates of names and figures; the rest
  // are abbreviations of the tables themselves. Naming them keeps the gate honest: an identical value that
  // is not named is still a finding, and no byte of English prose slipped through — the two English gloss
  // lines that had (home.metaTitle, home.heroLine1/2) were translated, not named.
  ["common.sourceLabel", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["common.minutesCount", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["challenges.competitionOption", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["worldCompetition.chipClubs", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["worldCompetition.entrantsEyebrow", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["worldCompetition.movementPath", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["worldMatch.metaDescriptionPlayed", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["worldTeam.eyebrow", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["simulate.matchMeta", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["tactics.sideBoardCaption", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["tactics.measuresEyebrow", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["tactics.sharedPanelEyebrow", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["knowledge.resultLine", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["knowledge.resultLineOne", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["knowledge.passagesCount", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["knowledge.scoreChip", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["knowledge.citationScore", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["simulate.indicesChip", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["training.minuteOption", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["scout.possession", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["market.boardNeedPositions", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["market.figClause", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["market.clauseBtn", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["live.minutesNote", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["live.minutesChip", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["simulate.possessionLabel", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["simulate.simulationBadge", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["worldPlayer.heightValue", "a template of names, figures and arrows — the words around the placeholders are proper nouns or the game own names"],
  ["world.thMinutes", "the column's, scale's or metric's own abbreviation"],
  ["worldTeam.thMin", "the column's, scale's or metric's own abbreviation"],
  ["worldMatch.thMin", "the column's, scale's or metric's own abbreviation"],
  ["worldTraining.thMin", "the column's, scale's or metric's own abbreviation"],
  ["worldPlayer.thMin", "the column's, scale's or metric's own abbreviation"],
  ["worldPlayer.thDiff", "the column's, scale's or metric's own abbreviation"],
  ["world.thPos", "the column's, scale's or metric's own abbreviation"],
  ["worldTeam.thPos", "the column's, scale's or metric's own abbreviation"],
  ["worldMatch.thPos", "the column's, scale's or metric's own abbreviation"],
  ["worldTraining.thPos", "the column's, scale's or metric's own abbreviation"],
  ["careerDetail.thPoints", "the column's, scale's or metric's own abbreviation"],
  ["challenges.tPts", "the column's, scale's or metric's own abbreviation"],
  ["worldCompetition.thPts", "the column's, scale's or metric's own abbreviation"],
  ["history.colDiff", "the column's, scale's or metric's own abbreviation"],
  ["history.colMin", "the column's, scale's or metric's own abbreviation"],
  ["traces.thP50", "the column's, scale's or metric's own abbreviation"],
  ["traces.thP95", "the column's, scale's or metric's own abbreviation"],
  ["traces.milliseconds", "the column's, scale's or metric's own abbreviation"],
  ["traces.window15", "the column's, scale's or metric's own abbreviation"],
  ["training.overallChip", "the column's, scale's or metric's own abbreviation"],
  ["academy.sessionRpeLabel", "the column's, scale's or metric's own abbreviation"],
  ["careerDetail.contractsBand2125", "the column's, scale's or metric's own abbreviation"],
  ["careerDetail.contractsBand2629", "the column's, scale's or metric's own abbreviation"],
  ["careerDetail.contractsBand3033", "the column's, scale's or metric's own abbreviation"],
  ["career.thPoints", "the column's, scale's or metric's own abbreviation"],
  ["common.xpGain", "the game's own coin"],
  ["history.colXp", "the game's own coin"],
  ["history.metricXp", "the game's own coin"],
  ["history.xpPlus", "the game's own coin"],
  ["history.xpAmount", "the game's own coin"],
  ["training.xpAwarded", "the game's own coin"],
  ["coach.statXp", "the game's own coin"],
  ["career.club", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["career.thClub", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["world.thClub", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["world.thClubs", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["world.sectionClubsLabel", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["world.clubsUnit", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["worldCompetition.thClub", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["simulationAggregates.thClub", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["challenges.club", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["challenges.tableClub", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["world.thScore", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["challenges.tScore", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["careerDetail.thScore", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["careerDetail.cupThScore", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["creator.thScore", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["video.matchChip", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["worldTeam.matchFallback", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["worldPlayer.thMatch", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["worldPlayer.rowCleanSheets", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["academy.sessionFocusPlaceholder", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["coach.intentPressing", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["video.tablePosition", "the football English French media uses as-is (club, match, score, pressing, clean sheet)"],
  ["nav.club", "the feature's own name"],
  ["nav.scout", "the feature's own name"],
  ["settings.milestoneM7", "the feature's own name"],
  ["settings.milestoneM8", "the feature's own name"],
  ["scout.title", "the feature's own name"],
  ["creator.metaTitle", "the feature's own name"],
  ["nav.notifications", "a field/interface term French spells the same as English (loanword doublet)"],
  ["nav.traces", "a field/interface term French spells the same as English (loanword doublet)"],
  ["common.paginationAria", "a field/interface term French spells the same as English (loanword doublet)"],
  ["common.rowQuestion", "a field/interface term French spells the same as English (loanword doublet)"],
  ["auth.roleManager", "a field/interface term French spells the same as English (loanword doublet)"],
  ["auth.roleScout", "a field/interface term French spells the same as English (loanword doublet)"],
  ["scout.kvPercentile", "a field/interface term French spells the same as English (loanword doublet)"],
  ["scout.pointsLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["scout.thDelta", "a field/interface term French spells the same as English (loanword doublet)"],
  ["scout.thDirection", "a field/interface term French spells the same as English (loanword doublet)"],
  ["scout.thLeader", "a field/interface term French spells the same as English (loanword doublet)"],
  ["scout.thNote", "a field/interface term French spells the same as English (loanword doublet)"],
  ["scout.thVerdict", "a field/interface term French spells the same as English (loanword doublet)"],
  ["scout.versus", "a field/interface term French spells the same as English (loanword doublet)"],
  ["career.budget", "a field/interface term French spells the same as English (loanword doublet)"],
  ["career.thManager", "a field/interface term French spells the same as English (loanword doublet)"],
  ["world.tableHeaderTable", "a field/interface term French spells the same as English (loanword doublet)"],
  ["world.teamsNationLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["world.competitionsFormatLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["world.thFormat", "a field/interface term French spells the same as English (loanword doublet)"],
  ["world.thManager", "a field/interface term French spells the same as English (loanword doublet)"],
  ["coach.tabPlan", "a field/interface term French spells the same as English (loanword doublet)"],
  ["coach.alternatives", "a field/interface term French spells the same as English (loanword doublet)"],
  ["coach.horizonLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["progress.groupMental", "a field/interface term French spells the same as English (loanword doublet)"],
  ["agents.citationsLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["agents.modeLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["agents.rosterLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["agents.traceLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["tactics.labelTempo", "a field/interface term French spells the same as English (loanword doublet)"],
  ["tactics.phaseLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["tactics.pause", "a field/interface term French spells the same as English (loanword doublet)"],
  ["tactics.simulation", "a field/interface term French spells the same as English (loanword doublet)"],
  ["history.colDate", "a field/interface term French spells the same as English (loanword doublet)"],
  ["history.colNotes", "a field/interface term French spells the same as English (loanword doublet)"],
  ["training.ratingFocus5", "a field/interface term French spells the same as English (loanword doublet)"],
  ["training.instructions", "a field/interface term French spells the same as English (loanword doublet)"],
  ["training.progressions", "a field/interface term French spells the same as English (loanword doublet)"],
  ["training.testTitle", "a field/interface term French spells the same as English (loanword doublet)"],
  ["knowledge.provenanceEyebrow", "a field/interface term French spells the same as English (loanword doublet)"],
  ["knowledge.passagesH2", "a field/interface term French spells the same as English (loanword doublet)"],
  ["knowledge.modeLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["challenges.kvPoints", "a field/interface term French spells the same as English (loanword doublet)"],
  ["challenges.tableVerdict", "a field/interface term French spells the same as English (loanword doublet)"],
  ["market.kvFormation", "a field/interface term French spells the same as English (loanword doublet)"],
  ["market.badgeRival", "a field/interface term French spells the same as English (loanword doublet)"],
  ["portfolio.thSections", "a field/interface term French spells the same as English (loanword doublet)"],
  ["community.thCode", "a field/interface term French spells the same as English (loanword doublet)"],
  ["simulate.thExpression", "a field/interface term French spells the same as English (loanword doublet)"],
  ["simulate.minutes", "a field/interface term French spells the same as English (loanword doublet)"],
  ["simulate.mPasses", "a field/interface term French spells the same as English (loanword doublet)"],
  ["simulate.mPossession", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.capAxes", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.capInvitations", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.kvCurriculum", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderCurriculum", "a field/interface term French spells the same as English (loanword doublet)"],
  ["market.buyThClause", "a field/interface term French spells the same as English (loanword doublet)"],
  ["simulationAggregates.backSimulation", "a field/interface term French spells the same as English (loanword doublet)"],
  ["traces.thCount", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderClip", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderCoach", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderDate", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderFocus", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderNote", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderOrganisation", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderPhases", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tableHeaderTable", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.tenantMetaTitle", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.thAudience", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.thNote", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.thOrganisation", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.sharePlanThPlan", "a field/interface term French spells the same as English (loanword doublet)"],
  ["club.sharedPlanKVFocus", "a field/interface term French spells the same as English (loanword doublet)"],
  ["careerDetail.academyThVerdict", "a field/interface term French spells the same as English (loanword doublet)"],
  ["careerDetail.contractsKindBuy", "a field/interface term French spells the same as English (loanword doublet)"],
  ["careerDetail.rowPoints", "a field/interface term French spells the same as English (loanword doublet)"],
  ["careerDetail.seasonsThVerdict", "a field/interface term French spells the same as English (loanword doublet)"],
  ["careerDetail.thClub", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldPlayer.rowMinutes", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldPlayer.thDate", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldPlayer.thPasses", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldPlayer.centre", "a field/interface term French spells the same as English (loanword doublet)"],
  ["simulationAggregates.thType", "a field/interface term French spells the same as English (loanword doublet)"],
  ["simulationAggregates.thSlug", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldTeam.rowManager", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldTeam.thNation", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldTeam.thMinutes", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldTeam.thPasses", "a field/interface term French spells the same as English (loanword doublet)"],
  ["graph.thDirection", "a field/interface term French spells the same as English (loanword doublet)"],
  ["graph.kvSlug", "a field/interface term French spells the same as English (loanword doublet)"],
  ["graph.slugPlaceholder", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldTraining.thDate", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldCompetition.claimTitle", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldCompetition.rowFormat", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldCompetition.entrantsTitle", "a field/interface term French spells the same as English (loanword doublet)"],
  ["worldNews.rowSource", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.rowSections", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thCode", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.guidesTitle", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.labelSection", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thGuide", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thSection", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thCitations", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thTokens", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.citationsTitle", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.labelNote", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thDocument", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thOrdinal", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.programMinutesLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.programNoteLabel", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thNote", "a field/interface term French spells the same as English (loanword doublet)"],
  ["creator.thPoints", "a field/interface term French spells the same as English (loanword doublet)"],
  ["academy.noteLabel", "a field/interface term French spells the same as English (loanword doublet)"],

  ["live.pause", "a field/interface term French spells the same as English (loanword doublet)"],
]);


/** The exemption set for one locale. `fr` alone carries the FR_TOKENS doublet set on top of the
 *  language-neutral tokens; no other locale reads FR_TOKENS, so a French-only name cannot excuse a
 *  key for the other catalogues. */
const EXEMPTIONS = (locale) =>
  locale === "fr" ? new Set([...TOKENS.keys(), ...FR_TOKENS.keys()]) : TOKENS;


const catalogue = (locale) => JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8"));

/**
 * A *text* read, folded to `\n`.
 *
 * These two files are the only ones here that a regular expression runs over, and a regular expression reads
 * line endings: `messages/README.md` is CRLF on a Windows checkout and LF in the git object the same commit
 * holds, so an unfolded read is a verdict that depends on where the reader stood. A JSON read needs no
 * folding — a raw `\r` cannot sit inside a JSON string, so the same bytes parse to the same object on either
 * plane, which is why `catalogue` above is plain.
 */
const readText = (path) => readFileSync(path, "utf8").replace(/\r\n/g, "\n");

/**
 * Every string leaf as `dotted.path -> value`, at whatever depth it sits.
 *
 * Each walk below used to be two nested `Object.entries` loops, so a value three levels down was never
 * reached: the outer loop saw an object, `typeof value !== "string"` moved past it, and the check reported a
 * clean verdict about a leaf it had not visited. Measured on 2026-11-08 (§41): a Chinese sentence written at
 * `probe.chinese.inner` passed the check this file exists to hold.
 */
const leaves = (node, prefix = "", out = new Map()) => {
  if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) leaves(value, prefix ? `${prefix}.${key}` : key, out);
    return out;
  }
  if (typeof node === "string") out.set(prefix, node);
  return out;
};

/** Read each catalogue once. The old code called `catalogue(locale)` from inside the per-key loop, so every
 *  key re-parsed every file: the walks below are the same census for a fraction of the reads. */
const english = catalogue("en");
const ENGLISH = leaves(english);
const LEAVES = new Map(SHIPPED.map((locale) => [locale, leaves(catalogue(locale))]));
const valuesOf = (locale) => LEAVES.get(locale) ?? new Map();

/** What every check below is graded on, printed so a reader can see the population rather than assume it. */
const JUDGED = `${LOCALES.length} catalogue(s) beside the fallback (${LOCALES.join(", ") || "none"}), ${ENGLISH.size} English leaf(s)`;

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

/* --- the first claim: the English file is English --- */
const cjk = /\p{Script=Han}/u;
const chineseInEnglish = [];
for (const [path, value] of ENGLISH) {
  if (cjk.test(value)) chineseInEnglish.push(path);
}

check(
  "the English catalogue holds no Chinese",
  chineseInEnglish.length === 0,
  chineseInEnglish.length === 0
    ? `${ENGLISH.size} English leaf(s) read at every depth`
    : `${chineseInEnglish.length} value(s) in English that are Chinese: ${chineseInEnglish.slice(0, 6).join(", ")}`,
);

/* The population. Every other check on this plane compares the fallback against a second catalogue, so a
 * plane where `messages/` holds only `en.json` gives all four of them nothing to compare and a green line
 * each. Refuse instead. */
check(
  "the directory ships at least one catalogue beside the fallback",
  SHIPPED.includes("en") && LOCALES.length > 0,
  SHIPPED.includes("en") && LOCALES.length > 0
    ? JUDGED
    : SHIPPED.includes("en")
      ? `messages/ ships en.json alone — the four comparison rules below have no second side, so ${ENGLISH.size} English leaf(s) went unjudged`
      : `messages/ ships ${SHIPPED.join(", ") || "nothing"} — no en.json, so the reference every check below compares against is missing`,
);

/* --- the second claim: the identical values are the named ones --- */
const unnamed = [];
const stale = [];
for (const locale of LOCALES) {
  const other = valuesOf(locale);
  const exempt = EXEMPTIONS(locale);
  for (const [path, value] of ENGLISH) {
    if (other.get(path) === value && !exempt.has(path)) unnamed.push(`${locale}: ${path}`);
  }
}
for (const locale of LOCALES) {
  const other = valuesOf(locale);
  const exempt = EXEMPTIONS(locale);
  for (const path of exempt.keys()) {
    const value = ENGLISH.get(path);
    if (value === undefined) {
      stale.push(`${locale}: ${path} is named a token but is not in the English catalogue`);
      continue;
    }
    if (!other.has(path)) stale.push(`${locale}: ${path} is named a token but the catalogue holds no such key`);
    else if (other.get(path) !== value) stale.push(`${locale}: ${path} is named a token but is translated`);
  }
}

check(
  "every value any catalogue shares with the English is a named technical token",
  unnamed.length === 0,
  unnamed.length === 0
    ? `${EXEMPTIONS("fr").size} token(s) named for fr, ${TOKENS.size} language-neutral; ${LOCALES.length} catalogue(s) compared (${LOCALES.join(", ") || "none"})`
    : `${unnamed.length} identical value(s) that are not named: ${unnamed.slice(0, 8).join(" | ")}`,
);

check(
  "every named technical token is still a token",
  stale.length === 0,
  stale.length === 0
    ? `${TOKENS.size} language-neutral token(s) plus ${FR_TOKENS.size} French-only doublet(s), checked per catalogue across ${LOCALES.length} catalogue(s)`
    : `${stale.length} stale name(s): ${stale.slice(0, 8).join(" | ")}`,
);

/**
 * The catalogue's own table: the figures it publishes, checked against the catalogue itself.
 *
 * `apps/web/messages/README.md` states how many keys the catalogue holds and how many of them are
 * translated, and that table is the number a reader is given. It was stale twice in this arc — once
 * because nothing recomputed it, and once because four keys landed after the last recompute and only
 * the API's suite could see it. This gate can see it too: the population and the translated count are
 * both derivable from the catalogues the directory ships, and the two numbers the table states are the
 * two numbers a reader is given. The loop is over the discovered locales, so an `ar.json` that ships
 * without a row in this table is a finding, not an omission nobody was asked about.
 */
const translatedCount = (locale) => {
  const other = valuesOf(locale);
  let count = 0;
  for (const [path, value] of ENGLISH) {
    if (other.get(path) !== value) count += 1;
  }
  return count;
};

let readme = "";
try {
  readme = readText(join(MESSAGES, "README.md"));
} catch {
  readme = "";
}
const population = ENGLISH.size;
const staleRows = [];
for (const locale of LOCALES) {
  const row = new RegExp(`\\|\\s*\`?${locale}\\.json\`?\\s*\\|\\s*(\\d+) of (\\d+)`, "u").exec(readme);
  if (!row) {
    staleRows.push(`${locale}: the table states no figure`);
    continue;
  }
  const stated = Number(row[1]);
  const statedPopulation = Number(row[2]);
  const translated = translatedCount(locale);
  if (statedPopulation !== population) {
    staleRows.push(`${locale}: the table counts a population of ${statedPopulation}; the catalogue holds ${population}`);
  }
  if (stated !== translated) {
    staleRows.push(`${locale}: the table claims ${stated} translated keys; the catalogue holds ${translated}`);
  }
}

check(
  "the catalogue's own table states the figures the catalogue holds",
  staleRows.length === 0,
  staleRows.length === 0
    ? `${population} key(s); ${LOCALES.map((locale) => `${locale} ${translatedCount(locale)}`).join(", ")} translated`
    : staleRows.join(" | "),
);

/**
 * The sentences held under two keys, and whether they are worded the same way in every language.
 *
 * A sentence written twice is a translation written twice, and the two will drift: the reader meets
 * one button written two ways. The count is a **floor** for now, at the count this gate read when it
 * learned to see the shape, and it may only fall — every sentence that is brought into line lowers
 * it. A repeat inside one namespace is a tier's own name in its own surfaces, which is deliberate.
 *
 * The floors are keyed on the locales that have been **measured**, and a catalogue that ships without
 * one is a finding: the old `drift = { zh: [], "zh-TW": [] }` plus a discovered locale was a crash, and
 * a crash is not a verdict either. Shipping a new language means writing down the count its copy starts
 * at, which is the argument the floor exists to force.
 */
const DRIFT_FLOORS = { zh: 0, "zh-TW": 0, ar: 0, he: 0, fr: 0 };
const holders = new Map();
for (const [path, value] of ENGLISH) {
  if (value.length <= 12) continue;
  if (!holders.has(value)) holders.set(value, []);
  holders.get(value).push(path);
}
const drift = new Map(LOCALES.map((locale) => [locale, []]));
const noFloor = [];
for (const [value, keys] of holders) {
  if (keys.length < 2) continue;
  if (new Set(keys.map((path) => path.split(".")[0])).size === 1) continue;
  for (const locale of LOCALES) {
    if (!Object.hasOwn(DRIFT_FLOORS, locale)) continue;
    const wordings = new Set(keys.map((path) => valuesOf(locale).get(path)));
    if (wordings.size > 1) drift.get(locale).push(`${value.slice(0, 40)} — ${keys.join(", ")}`);
  }
}
const driftFindings = [];
for (const locale of LOCALES) {
  if (!Object.hasOwn(DRIFT_FLOORS, locale)) {
    noFloor.push(`${locale}: ${locale}.json ships but no floor is on record — write DRIFT_FLOORS.${locale} at the count this rule measures today, with the reason if it is not 0`);
    continue;
  }
  const found = drift.get(locale);
  if (found.length > DRIFT_FLOORS[locale]) {
    driftFindings.push(
      `${locale}: ${found.length} sentence(s) held under two keys are worded more than one way (floor ${DRIFT_FLOORS[locale]}): ${found.slice(0, 4).join(" | ")}`,
    );
  }
}

check(
  "a sentence held under two keys is worded the same way in every language",
  driftFindings.length === 0 && noFloor.length === 0,
  driftFindings.length === 0 && noFloor.length === 0
    ? `${holders.size} distinct sentence(s) over ${LOCALES.length} catalogue(s); floors ${Object.entries(DRIFT_FLOORS).map(([l, n]) => `${l} ${n}`).join(", ")}`
    : [...noFloor, ...driftFindings].join(" | "),
);

/**
 * The table is defined once. A second copy is where an exemption goes stale.
 *
 * `qa-token-drift.mjs` held the same 45 paths and the same 45 reasons as its own literal on 2026-11-08, and
 * because the two copies agreed, nothing was wrong — which is exactly how a copy survives: it agrees right up
 * to the edit that only one of them gets. This census counts, for every script sitting beside this one, how
 * many of the paths defined here appear as an entry literal in its own source, and charges any file that
 * holds enough of them to be a table rather than a passing mention.
 */
const COPY_THRESHOLD = 5;
const SCRIPTS_DIR = join(WEB, "scripts");
const ALL_TOKEN_KEYS = [...TOKENS.keys(), ...FR_TOKENS.keys()];
const copiers = [];
for (const name of readdirSync(SCRIPTS_DIR).filter((f) => f.endsWith(".mjs"))) {
  if (name === SELF) continue;
  const text = readText(join(SCRIPTS_DIR, name));
  const held = ALL_TOKEN_KEYS.filter((path) => text.includes(`["${path}",`)).length;
  if (held >= COPY_THRESHOLD) copiers.push(`${name} re-states ${held} of the ${ALL_TOKEN_KEYS.length} entries as its own literals`);
}

check(
  "this table is defined in one file and read by every gate that needs it",
  copiers.length === 0,
  copiers.length === 0
    ? `${ALL_TOKEN_KEYS.length} entries defined here (${TOKENS.size} language-neutral + ${FR_TOKENS.size} French-only); no other script in scripts/ holds ${COPY_THRESHOLD}+ of them as literals`
    : copiers.join(" | "),
);

const failed = checks.filter((entry) => !entry.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);

/** Four of the checks above are *comparisons*, and with no second catalogue each of them visits nothing and
 *  prints a clean line. The population check reds, so the gate does not pass — but a reader scanning for
 *  `FAIL` should not have to work out which PASSes judged anything. */
if (LOCALES.length === 0) {
  console.log(`\nNOT JUDGED  the shared-value rule, the named-token rule, the catalogue's own table and the drift floors compared nothing: messages/ holds no catalogue beside en.json (${SHIPPED.join(", ") || "not even that"}).`);
}

if (failed.length) {
  console.log("");
  console.log("Every value below is the same in every language without a reason, or is named without being one:");
  for (const path of unnamed) console.log(`  ${path}`);
  for (const path of stale) console.log(`  ${path}`);
  process.exitCode = 1;
}
