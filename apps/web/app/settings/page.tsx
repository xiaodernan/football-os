import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { DataUnavailable, KeyValue, Panel, Stat } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { serverFetch } from "@/lib/server";
import type { CapabilitiesResponse, HealthResponse, UserOut } from "@/lib/types";

import { PrivacyPanel } from "./PrivacyPanel";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Settings",
  description: "Account, data rights, honest platform status and the danger zone.",
};

/** Only the boolean switches may be listed as milestones, so a data block (`m3_world`) cannot be
 * rendered as a "Live / Not built" row by accident. */
type MilestoneKey = {
  [K in keyof CapabilitiesResponse]-?: CapabilitiesResponse[K] extends boolean ? K : never;
}[keyof CapabilitiesResponse];

const MILESTONES: { key: MilestoneKey; label: string }[] = [
  { key: "m0_foundation", label: "M0 · Foundation (accounts, training loop, progress)" },
  { key: "m1_player_ai_coach", label: "M1 · Player AI coach" },
  { key: "m2_rag", label: "M2 · RAG knowledge base" },
  { key: "m3_football_world", label: "M3 · Football World" },
  { key: "m4_tactical_lab", label: "M4 · Tactical Lab" },
  { key: "m5_video_analysis", label: "M5 · Video analysis" },
  { key: "m6_simulation", label: "M6 · Match simulation" },
  { key: "m7_scouting", label: "M7 · Scouting" },
  { key: "m8_club_os", label: "M8 · Club OS" },
  { key: "m9_community", label: "M9 · Community" },
];

function describeProvider(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "unreported";
  return "configured";
}

export default async function SettingsPage() {
  const [meResult, healthResult, capsResult] = await Promise.all([
    serverFetch<UserOut>("/auth/me"),
    serverFetch<HealthResponse>("/healthz"),
    serverFetch<CapabilitiesResponse>("/capabilities"),
  ]);

  if (!meResult.ok && meResult.status === 401) redirect("/login");
  if (!meResult.ok && meResult.status === 409 && meResult.error.code === "no_player") redirect("/onboarding");

  const me = meResult.ok ? meResult.data : null;
  const health = healthResult.ok ? healthResult.data : null;
  const capabilities = capsResult.ok ? capsResult.data : null;

  return (
    <div className="page container">
      <div className="stack">
        <div className="between wrap" style={{ alignItems: "flex-start", gap: "1rem" }}>
          <div className="stack-sm">
            <span className="eyebrow">Settings</span>
            <h1 className="h1">Account &amp; platform</h1>
            <p className="lede">
              What we store about you, what the platform can actually do today, and the two buttons that change it.
            </p>
          </div>
          {health && (
            <span className={`badge ${health.status === "ok" ? "badge--live" : "badge--demo"}`}>
              API {health.status}
            </span>
          )}
        </div>

        {!meResult.ok && (
          <div className="notice notice--warn">
            {errorMessage(meResult.error, "Account data is unavailable right now.")}
          </div>
        )}

        <Panel
          eyebrow="Account"
          title="Your profile"
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              Read-only on purpose: the API exposes no profile-edit endpoint yet, so this screen does not pretend to have
              one. Email and password changes arrive with that endpoint.
            </span>
          }
        >
          {!me ? (
            <DataUnavailable metric="Account details" />
          ) : (
            <>
              <div className="st-stats">
                <Stat label="Streak" value={<span className="num">{me.streak_days}</span>} hint="days in a row" />
                <Stat label="Role" value={<span className="upper">{me.role}</span>} />
                <Stat label="Plan" value={<span className="upper">{me.plan}</span>} />
              </div>
              <div style={{ marginTop: "1.1rem" }}>
                <KeyValue
                  rows={[
                    ["Display name", me.display_name],
                    ["Email", <span className="mono" key="email">{me.email}</span>],
                    ["Locale", me.locale],
                    ["Role", <span className="upper" key="role">{me.role}</span>],
                    ["Plan", <span className="upper" key="plan">{me.plan}</span>],
                    ["User ID", <span className="mono" key="id">{me.id}</span>],
                  ]}
                />
              </div>
            </>
          )}
        </Panel>

        <Panel
          eyebrow="Data & privacy"
          title="Export what we hold"
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              <span className="mono">GET /progress/export</span> returns plain JSON; the file is assembled and saved by
              your browser.
            </span>
          }
        >
          <PrivacyPanel mode="export" />
        </Panel>

        <Panel eyebrow="Platform status" title="What this deployment really is">
          {!health ? (
            <div className="stack-sm">
              <DataUnavailable metric="Health check" />
              <div className="notice notice--warn">
                {errorMessage(healthResult.ok ? undefined : healthResult.error, "The API did not answer /healthz.")}
              </div>
            </div>
          ) : (
            <div className="stack" style={{ gap: "1rem" }}>
              <KeyValue
                rows={[
                  ["Environment", <span className="upper" key="env">{health.environment}</span>],
                  ["Database dialect", <span className="mono" key="dialect">{health.database_dialect}</span>],
                  [
                    "pgvector",
                    health.pgvector ? (
                      <span className="badge badge--live" key="pg">enabled</span>
                    ) : (
                      <span className="chip" key="pg">false — vector search is off</span>
                    ),
                  ],
                  ["API status", <span className="upper" key="status">{health.status}</span>],
                ]}
              />
              <div className="stack-sm">
                <span className="eyebrow">Provider wiring</span>
                {Object.keys(health.providers ?? {}).length === 0 ? (
                  <DataUnavailable metric="Providers" />
                ) : (
                  <div className="tag-list">
                    {Object.entries(health.providers).map(([key, value]) => (
                      <span className="chip mono" key={key}>
                        {key}: {describeProvider(value)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {(health.notes ?? []).length > 0 && (
                <div className="stack-sm">
                  <span className="eyebrow">Operator notes</span>
                  <ul className="reasons">
                    {health.notes.map((note, index) => (
                      <li className="reasons__item" key={`${note}-${index}`}>
                        {note}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Panel>

        <Panel
          eyebrow="Feature map"
          title="Built vs. not built"
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              These switches come straight from <span className="mono">GET /capabilities</span>. Anything marked “not
              built” has no endpoint behind it yet, so no screen fakes it.
            </span>
          }
        >
          {!capabilities ? (
            <div className="stack-sm">
              <DataUnavailable metric="Capabilities" />
              <div className="notice notice--warn">
                {errorMessage(capsResult.ok ? undefined : capsResult.error, "Capabilities could not be read.")}
              </div>
            </div>
          ) : (
            <div>
              {MILESTONES.filter((milestone) => milestone.key in capabilities).map((milestone) => {
                const live = capabilities[milestone.key] === true;
                return (
                  <div className="st-status-row" key={milestone.key}>
                    <span className="st-status-row__label">{milestone.label}</span>
                    {live ? (
                      <span className="badge badge--live">Live</span>
                    ) : (
                      <span className="badge badge--demo">Not built</span>
                    )}
                  </div>
                );
              })}
              <div className="st-status-row">
                <span className="st-status-row__label">Demo mode (no live AI provider key)</span>
                {capabilities.demo_mode === true ? (
                  <span className="badge badge--demo" key="demo">
                    Demo data
                  </span>
                ) : (
                  <span className="badge badge--live" key="demo">
                    Live provider
                  </span>
                )}
              </div>
              <div className="st-status-row">
                <span className="st-status-row__label">Locales shipped</span>
                <span className="row wrap" style={{ gap: "0.3rem", justifyContent: "flex-end" }}>
                  {(capabilities.locales ?? []).length === 0 ? (
                    <DataUnavailable metric="Locales" />
                  ) : (
                    (capabilities.locales ?? []).map((locale) => (
                      <span className="chip mono" key={locale}>
                        {locale}
                      </span>
                    ))
                  )}
                  {(capabilities.locales_planned ?? [])
                    .filter((locale) => !(capabilities.locales ?? []).includes(locale))
                    .map((locale) => (
                      <span className="chip mono muted" key={`planned-${locale}`} title="Planned, not shipped">
                        {locale} · planned
                      </span>
                    ))}
                </span>
              </div>
            </div>
          )}
        </Panel>

        <Panel
          eyebrow="Danger zone"
          title="Remove training history"
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              <span className="mono">DELETE /progress/player-data</span> — your sign-in and this page stay available
              afterwards.
            </span>
          }
        >
          <PrivacyPanel mode="delete" />
        </Panel>

        <Panel
          eyebrow="Account"
          title="Delete account permanently"
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              <span className="mono">DELETE /auth/account</span> — requires your current password and the
              confirmation phrase.
            </span>
          }
        >
          <PrivacyPanel mode="account" />
        </Panel>
      </div>
    </div>
  );
}
