import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { DataUnavailable, KeyValue, Panel, Stat } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { serverFetch } from "@/lib/server";
import type { CapabilitiesResponse, HealthResponse, UserOut } from "@/lib/types";

import { PrivacyPanel } from "./PrivacyPanel";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("settings");
  return { title: t("title"), description: t("tagline") };
}

/** Only the boolean switches may be listed as milestones, so a data block (`m3_world`) cannot be
 * rendered as a "Live / Not built" row by accident. */
type MilestoneKey = {
  [K in keyof CapabilitiesResponse]-?: CapabilitiesResponse[K] extends boolean ? K : never;
}[keyof CapabilitiesResponse];

const MILESTONES: { key: MilestoneKey; labelKey: string }[] = [
  { key: "m0_foundation", labelKey: "milestoneM0" },
  { key: "m1_player_ai_coach", labelKey: "milestoneM1" },
  { key: "m2_rag", labelKey: "milestoneM2" },
  { key: "m3_football_world", labelKey: "milestoneM3" },
  { key: "m4_tactical_lab", labelKey: "milestoneM4" },
  { key: "m5_video_analysis", labelKey: "milestoneM5" },
  { key: "m6_simulation", labelKey: "milestoneM6" },
  { key: "m7_scouting", labelKey: "milestoneM7" },
  { key: "m8_club_os", labelKey: "milestoneM8" },
  { key: "m9_community", labelKey: "milestoneM9" },
];

function describeProvider(value: unknown, labels: { unreported: string; configured: string }): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return labels.unreported;
  return labels.configured;
}

export default async function SettingsPage() {
  const t = await getTranslations("settings");
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
            <span className="eyebrow">{t("title")}</span>
            <h1 className="h1">{t("heading")}</h1>
            <p className="lede">{t("lede")}</p>
          </div>
          {health && (
            <span className={`badge ${health.status === "ok" ? "badge--live" : "badge--demo"}`}>
              {t("apiBadge", { status: health.status })}
            </span>
          )}
        </div>

        {!meResult.ok && (
          <div className="notice notice--warn">
            {errorMessage(meResult.error, t("accountUnavailable"))}
          </div>
        )}

        <Panel
          eyebrow={t("profileEyebrow")}
          title={t("profileTitle")}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("profileFooter")}
            </span>
          }
        >
          {!me ? (
            <DataUnavailable metric={t("accountDetails")} />
          ) : (
            <>
              <div className="st-stats">
                <Stat label={t("streak")} value={<span className="num">{me.streak_days}</span>} hint={t("streakHint")} />
                <Stat label={t("role")} value={<span className="upper">{me.role}</span>} />
                <Stat label={t("plan")} value={<span className="upper">{me.plan}</span>} />
              </div>
              <div style={{ marginTop: "1.1rem" }}>
                <KeyValue
                  rows={[
                    [t("displayName"), me.display_name],
                    [t("email"), <span className="mono" key="email">{me.email}</span>],
                    [t("locale"), me.locale],
                    [t("role"), <span className="upper" key="role">{me.role}</span>],
                    [t("plan"), <span className="upper" key="plan">{me.plan}</span>],
                    [t("userId"), <span className="mono" key="id">{me.id}</span>],
                  ]}
                />
              </div>
            </>
          )}
        </Panel>

        <Panel
          eyebrow={t("dataPrivacy")}
          title={t("exportTitle")}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("exportFooter")}
            </span>
          }
        >
          <PrivacyPanel mode="export" />
        </Panel>

        <Panel eyebrow={t("platformEyebrow")} title={t("platformTitle")}>
          {!health ? (
            <div className="stack-sm">
              <DataUnavailable metric={t("healthCheck")} />
              <div className="notice notice--warn">
                {errorMessage(healthResult.ok ? undefined : healthResult.error, t("noHealthz"))}
              </div>
            </div>
          ) : (
            <div className="stack" style={{ gap: "1rem" }}>
              <KeyValue
                rows={[
                  [t("environment"), <span className="upper" key="env">{health.environment}</span>],
                  [t("dialect"), <span className="mono" key="dialect">{health.database_dialect}</span>],
                  [
                    "pgvector",
                    health.pgvector ? (
                      <span className="badge badge--live" key="pg">{t("pgOn")}</span>
                    ) : (
                      <span className="chip" key="pg">{t("pgOff")}</span>
                    ),
                  ],
                  [t("apiStatusRow"), <span className="upper" key="status">{health.status}</span>],
                ]}
              />
              <div className="stack-sm">
                <span className="eyebrow">{t("providerWiring")}</span>
                {Object.keys(health.providers ?? {}).length === 0 ? (
                  <DataUnavailable metric={t("providers")} />
                ) : (
                  <div className="tag-list">
                    {Object.entries(health.providers).map(([key, value]) => (
                      <span className="chip mono" key={key}>
                        {key}: {describeProvider(value, { unreported: t("unreported"), configured: t("configured") })}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {(health.notes ?? []).length > 0 && (
                <div className="stack-sm">
                  <span className="eyebrow">{t("operatorNotes")}</span>
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
          eyebrow={t("featureMapEyebrow")}
          title={t("featureMapTitle")}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("featureMapFooter")}
            </span>
          }
        >
          {!capabilities ? (
            <div className="stack-sm">
              <DataUnavailable metric={t("capabilities")} />
              <div className="notice notice--warn">
                {errorMessage(capsResult.ok ? undefined : capsResult.error, t("capsUnreadable"))}
              </div>
            </div>
          ) : (
            <div>
              {MILESTONES.filter((milestone) => milestone.key in capabilities).map((milestone) => {
                const live = capabilities[milestone.key] === true;
                return (
                  <div className="st-status-row" key={milestone.key}>
                    <span className="st-status-row__label">{t(milestone.labelKey)}</span>
                    {live ? (
                      <span className="badge badge--live">{t("live")}</span>
                    ) : (
                      <span className="badge badge--demo">{t("notBuilt")}</span>
                    )}
                  </div>
                );
              })}
              <div className="st-status-row">
                <span className="st-status-row__label">{t("demoModeRow")}</span>
                {capabilities.demo_mode === true ? (
                  <span className="badge badge--demo" key="demo">
                    {t("demoData")}
                  </span>
                ) : (
                  <span className="badge badge--live" key="demo">
                    {t("liveProvider")}
                  </span>
                )}
              </div>
              <div className="st-status-row">
                <span className="st-status-row__label">{t("localesShipped")}</span>
                <span className="row wrap" style={{ gap: "0.3rem", justifyContent: "flex-end" }}>
                  {(capabilities.locales ?? []).length === 0 ? (
                    <DataUnavailable metric={t("localesShipped")} />
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
                      <span className="chip mono muted" key={`planned-${locale}`} title={t("plannedTitle")}>
                        {t("plannedChip", { locale })}
                      </span>
                    ))}
                </span>
              </div>
            </div>
          )}
        </Panel>

        <Panel
          eyebrow={t("dangerEyebrow")}
          title={t("deleteHistoryTitle")}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("deleteHistoryFooter")}
            </span>
          }
        >
          <PrivacyPanel mode="delete" />
        </Panel>

        <Panel
          eyebrow={t("profileEyebrow")}
          title={t("deleteAccountTitle")}
          footer={
            <span className="muted" style={{ fontSize: "0.82rem" }}>
              {t("deleteAccountFooter")}
            </span>
          }
        >
          <PrivacyPanel mode="account" />
        </Panel>
      </div>
    </div>
  );
}
