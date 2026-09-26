/**
 * §39's club tenancies, as `GET /api/v1/club…` actually answers.
 *
 * Every field here was read off a live response harvested from a throwaway database
 * (`organization.view`, `organization.view.full`, `teams.create`, `squad.list`, `invitations.pending`,
 * `organizations.mine`, `GET /club/capabilities`), not off a design note. A page may print a key that
 * exists and must not print one that does not, so the type is the contract's shadow: where the API sends
 * a figure with its formula beside it, the formula is part of the type, because the sentence is the
 * evidence and a page that drops it has kept only the number.
 */

/** `{methods, path, purpose}` — one line of the published door guide. */
export type Door = { methods: string[]; path: string; purpose: string };

/** `my_grant`, and each row of `members[]`: the standing this account (or they) hold in this tenant. */
export type Grant = {
  active: boolean;
  known_role: boolean;
  permissions: string[];
  role: string;
  status: string;
  why: string;
};

export type Organization = {
  country: string;
  created_at: string;
  data_origin: string;
  id: string;
  is_demo_data: boolean;
  kind: string;
  name: string;
  slug: string;
  visibility_default: string;
};

export type SquadRow = {
  added_at: string;
  age: number;
  is_minor: boolean;
  name: string;
  note: string;
  overall: number;
  /** The world's own player path, sent by the API rather than assembled here. */
  path: string;
  player_id: string;
  position: string;
  potential: number;
  slug: string;
};

export type WorldTeamRef = { id: string; slug: string; name: string; path: string };

/** `teams[]` on the tenant view, and the whole body of `GET …/teams/{team}/players`. */
export type TeamView = {
  age_group: string;
  /** Says where the squad figures came from: rows read on this request, not a stored copy. */
  figures_from: string;
  id: string;
  minors_on_sheet: number;
  name: string;
  room_left: number;
  squad: SquadRow[];
  squad_size: number;
  stage: string;
  world_team: WorldTeamRef | null;
};

export type MemberRow = {
  account_role: string;
  active: boolean;
  display_name: string;
  email: string;
  id: string;
  invited_by: string | null;
  known_role: boolean;
  permissions: string[];
  role: string;
  since: string;
  status: string;
  why: string;
};

export type Integrity = {
  checked: Record<string, number>;
  clean: boolean;
  problems: string[];
  rule: string;
};

export type PermissionMatrix = {
  default: string;
  matrix: Record<string, string[]>;
  meaning: Record<string, string>;
  not_stored: string;
  permissions: string[];
  roles: string[];
  rule: string;
  /** Rights that mean nothing until a row outside this table says so. */
  scoped: Record<string, string>;
  scoped_permissions: string[];
  statuses: string[];
  stored: string;
};

/** `rules` on a tenant view, and the body of `GET /club/capabilities` with the door guide added. */
export type ClubRules = {
  addressing: string;
  country: string;
  founder: string;
  invitations: string;
  kinds: string[];
  matrix: PermissionMatrix;
  max_members_per_organization: number;
  max_organizations_per_user: number;
  max_squad_per_team: number;
  max_teams_per_organization: number;
  name_max: number;
  note_max: number;
  refusals: string[];
  team_name_max: number;
  visibility_defaults: string[];
};

export type ClubCapabilities = ClubRules & {
  counts: { organizations: number; memberships: number; active_memberships: number; teams: number; squad_rows: number; rule: string };
  data_origin: string;
  demo_data: boolean;
  is_demo_data: boolean;
  /** `code → HTTP status`, published so a page never has to guess what a refusal will look like. */
  refusal_answers: Record<string, number>;
  limitations: string[];
  ready: boolean;
  routes: Door[];
};

export type OrganizationView = {
  counts: {
    active_members: number;
    invited_members: number;
    member_limit: number;
    owners: number;
    players_on_sheets: number;
    team_limit: number;
    teams: number;
  };
  data_origin: string;
  demo_data: boolean;
  integrity: Integrity;
  is_demo_data: boolean;
  isolation_rule: string;
  limitations: string[];
  members: MemberRow[];
  my_grant: Grant;
  organization: Organization;
  rules: ClubRules;
  teams: TeamView[];
};

/** One row of `GET /club` — the tenants this account stands in. */
export type OrganizationListItem = {
  active_members: number;
  kind: string;
  name: string;
  /** Sent by the API, so the page cannot advertise a route that no page answers. */
  path: string;
  role: string;
  slug: string;
  status: string;
  teams: number;
};

export type OrganizationList = {
  demo_data: boolean;
  items: OrganizationListItem[];
  limit: number;
  room_left: number;
  rule: string;
  total: number;
};

export type InvitationItem = {
  invited_at: string;
  membership: string;
  name: string;
  organization: string;
  role: string;
};

export type InvitationList = { demo_data: boolean; items: InvitationItem[]; rule: string; total: number };

/** `POST /club` and `POST …/teams` answer with the tenant's own counters beside the new row. */
export type OrganizationCreated = { demo_data: boolean; members: number; my_grant: Grant; organization: Organization; room_left: number; teams: number };
export type TeamCreated = { demo_data: boolean; organization: string; room_left: number; team: TeamView; teams: number };

/* ------------------------------------------------------------------ §40 academy */

/**
 * §40's academy shapes. What is typed here was read off `academy.plan.read`, `academy.plans.list`,
 * `academy.consents.list`, `academy.curricula.list`, `academy.player.data` and the two capability doors
 * on a live response, plus `_evidence_view` in the service for the one row my walk left empty.
 *
 * `progress` is the reason this file exists twice over: not one of its figures is stored, so the API
 * sends the arithmetic next to the answer. A page that prints the number and drops the formula has
 * turned a measurement back into a claim.
 */

export type AcademyCapabilities = {
  assessment_text_max: number;
  axes: string[];
  consent: string;
  consent_scopes: { scopes: string[]; default_granted: string[]; rule: string };
  counts: {
    assessments: number;
    closed_plans: number;
    coach_feedback: number;
    consents_granted: number;
    consents_withdrawn: number;
    curricula: number;
    feedback_held_from_guardian: number;
    plans: number;
    plans_of_minors: number;
    rule: string;
    video_citations: number;
    citations_without_clip: number;
  };
  curriculum_name_max: number;
  data_origin: string;
  default_scopes: string[];
  demo_data: boolean;
  evidence_label_max: number;
  feedback_max: number;
  focus_items_max: number;
  goal_keys: string[];
  goals_max: number;
  guardianship: string;
  is_demo_data: boolean;
  limitations: string[];
  max_assessments_per_plan: number;
  max_consents_per_guardian: number;
  max_curricula_per_organization: number;
  max_evidence_per_plan: number;
  max_feedback_per_plan: number;
  max_phases_per_curriculum: number;
  max_plans_per_organization: number;
  max_weekly_minutes: number;
  minor_age: number;
  never_stored: string[];
  plan_statuses: string[];
  rating_range: [number, number];
  ready: boolean;
  refusal_answers: Record<string, number>;
  refusals: string[];
  refusals_shared_with_club_tier: string[];
  review_weeks_range: [number, number];
  routes: Door[];
  scoped_rights: Record<string, string>;
  scopes: string[];
  stored_fields: Record<string, string[]>;
  video: string;
};

export type ChildRef = { age: number; is_minor: boolean; name: string; slug: string };

export type ConsentRow = {
  granted_at: string;
  guardian: { display_name: string; email: string };
  id: string;
  plans_for_this_child: number;
  player: ChildRef;
  scopes: string[];
  state: string;
  updated_at: string;
};

export type ConsentList = {
  demo_data: boolean;
  items: ConsentRow[];
  organization: string;
  rule: string;
  seen_as: string;
  total: number;
  under_18: number;
};

export type CurriculumPhase = { focus: string; label: string; minutes: number };

export type CurriculumRow = {
  age_group: string;
  created_at: string;
  data_origin: string;
  formulas: { phase_minutes: string; unassigned_minutes: string };
  id: string;
  is_demo_data: boolean;
  name: string;
  phase_count: number;
  phase_minutes: number;
  phases: CurriculumPhase[];
  plans_using_it: number;
  unassigned_minutes: number;
  weekly_minutes: number;
};

export type CurriculumList = {
  demo_data: boolean;
  items: CurriculumRow[];
  limit: number;
  organization: string;
  role: string;
  room_left: number;
  rule: string;
  total: number;
};

export type PlanListItem = {
  assessments: number;
  focus: string[];
  goals: number;
  id: string;
  /** The route the API itself publishes for this plan, so the page cannot invent one. */
  path: string;
  player: ChildRef;
  progress: number | null;
  review_weeks: number;
  status: string;
};

export type PlanList = {
  demo_data: boolean;
  formulas: { progress: string };
  items: PlanListItem[];
  limit: number;
  minors_in_list: number;
  organization: string;
  read_through: string;
  role: string;
  rule: string;
  total: number;
};

export type AssessmentRow = {
  areas: string;
  assessed_on: string;
  axes_missing: string[];
  id: string;
  mean_rating: number;
  measured_from: string;
  next_focus: string;
  overall_observed: number;
  ratings: Record<string, number>;
  strengths: string;
};

export type FeedbackRow = {
  id: string;
  message: string;
  /** `staff copy` on a note the guardian may not see, so the row says who is reading. */
  seen_as: string;
  shared_with_guardian: boolean;
  written_at: string;
};

export type EvidenceRow = {
  assessment_id: string | null;
  clip: { duration_s: number; id: string; owner: string; title: string } | null;
  clip_present: boolean;
  id: string;
  label: string;
  linked_at: string | null;
  playback: string;
  t_end: number;
  t_start: number;
  window_seconds: number;
};

export type PlanProgress = {
  assessments: number;
  axis_change: Record<string, number>;
  axis_change_unrated_at_one_end: string[];
  axis_means: Record<string, number>;
  days_since_review: number;
  due_in_days: number;
  first_assessed_on: string | null;
  formulas: Record<string, string>;
  last_assessed_on: string | null;
  measured_from: string;
  not_a_column: string;
  one_review_is_not_a_direction: boolean;
  opened_on: string;
  overall_change: number | null;
  overall_first: number | null;
  overall_last: number | null;
  plan_days_open: number;
  reviews_behind: number;
  reviews_due_by_cadence: number;
  span_days: number;
};

export type PlanHead = {
  age_at_open: number;
  created_at: string;
  data_origin: string;
  focus: string[];
  goals: { by: string; measure: string; title: string }[];
  id: string;
  is_demo_data: boolean;
  minor_at_open: boolean;
  review_weeks: number;
  status: string;
  updated_at: string;
};

export type PlanView = {
  aged_past_minority: boolean;
  assessments: AssessmentRow[];
  author: { display_name: string; role: string };
  consented_by?: { consent: string; guardian: string; scopes: string[] };
  curriculum: string | null;
  demo_data: boolean;
  evidence: EvidenceRow[];
  feedback: FeedbackRow[];
  figures_from: string;
  integrity: Integrity;
  limitations: string[];
  not_stored?: string;
  organization: string;
  plan: PlanHead;
  player: ChildRef & { overall: number; path: string; position: string; potential: number };
  progress: PlanProgress;
  team: string | null;
  withheld: { coach_feedback: number; rule: string; video_evidence: number; why_video: string | null };
  your_standing: { guardian_of_this_child: boolean; read_through: string; role: string; scopes_held: string[]; staff: boolean };
};

/** `GET …/players/{player}/data` — what is held about this child here, printed before anything is erased. */
export type ChildDataView = {
  columns: Record<string, string[]>;
  demo_data: boolean;
  held_by_this_tenant: Record<string, number>;
  never_stored: string[];
  organization: string;
  outside_this_tenant: { generated_world: string; other_tenants: string; uploaded_clips: string };
  player: ChildRef;
  seen_as: string;
  total_rows: number;
};

/**
 * A refusal's figures, printed as they arrived.
 *
 * `normalizeError` keeps everything the service sent except `code` and `message`, and this tier's figures
 * are the point of the answer (`threshold`, `max`, `scopes_available`, `owners`, …) — so they are rendered
 * from the object rather than from a list of names somebody typed here. Nothing is invented, nothing is
 * dropped, and a new figure in a refusal shows up on the page without a web change.
 */
export function refusalFigures(details: unknown): string[] {
  if (!details || typeof details !== "object" || Array.isArray(details)) return [];
  return Object.entries(details as Record<string, unknown>)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key} ${Array.isArray(value) ? value.join(", ") || "none" : String(value)}`);
}


