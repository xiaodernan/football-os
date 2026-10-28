import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import type { FixtureList, OrganizationList } from "@/lib/club";
import { currentUser, serverFetch } from "@/lib/server";
import type { Player } from "@/lib/types";
import { OnboardingForm } from "./OnboardingForm";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("onboarding");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

/**
 * §16's first-run path: the player, the club, the team, the fixture and the result.
 *
 * The creation form is the first step and nothing more. Once a player row exists, this page stops
 * redirecting and instead reads the account's own rows back — the club list's `teams` counter and the
 * first club's fixture list — and prints which of the five steps a row already answers, with the link
 * that opens the surface for the next one. No step is ticked by hand, and a step whose row cannot be
 * read is printed as unknown rather than as done.
 */
export default async function OnboardingPage() {
  const t = await getTranslations("onboarding");
  const user = await currentUser();
  if (!user) redirect("/login");

  const playersResult = await serverFetch<Player[]>("/players");
  const players = playersResult.ok ? playersResult.data : [];

  if (players.length === 0) {
    const notice =
      !playersResult.ok && playersResult.status !== 401 && playersResult.status !== 409
        ? errorMessage(playersResult.error, t("noticeFallback"))
        : null;

    return (
      <div className="container page" style={{ maxWidth: "640px" }}>
        <div className="stack" style={{ gap: "1.25rem" }}>
          <div>
            <p className="eyebrow">{t("eyebrow")}</p>
            <h1 className="h1">{t("title")}</h1>
            <p className="lede" style={{ marginTop: "0.5rem" }}>
              {t("lede")}
            </p>
          </div>
          {notice && <div className="notice notice--warn">{notice}</div>}
          <OnboardingForm />
        </div>
      </div>
    );
  }

  const player = players[0];
  const clubResult = await serverFetch<OrganizationList>("/club");
  const club = clubResult.ok ? clubResult.data : null;
  const firstClub = club?.items[0] ?? null;
  const fixturesResult = firstClub ? await serverFetch<FixtureList>(`${firstClub.path}/fixtures`) : null;
  const fixtures = fixturesResult?.ok ? fixturesResult.data : null;

  const clubUnknown = !clubResult.ok;
  const fixtureUnknown = firstClub !== null && !(fixturesResult?.ok ?? false);

  const steps = [
    {
      key: "identity",
      title: t("stepIdentity"),
      done: true,
      unknown: false,
      evidence: t("evidencePlayer", { name: player.name }),
      href: "/my-football",
    },
    {
      key: "club",
      title: t("stepClub"),
      done: (club?.total ?? 0) > 0,
      unknown: clubUnknown,
      evidence: firstClub
        ? t("evidenceClub", { name: firstClub.name })
        : clubUnknown
          ? t("figuresUnknown")
          : t("noClubYet"),
      href: "/club",
    },
    {
      key: "team",
      title: t("stepTeam"),
      done: (firstClub?.teams ?? 0) > 0,
      unknown: clubUnknown,
      evidence: firstClub
        ? t("evidenceTeams", { count: firstClub.teams })
        : clubUnknown
          ? t("figuresUnknown")
          : t("noClubYet"),
      href: firstClub?.path ?? "/club",
    },
    {
      key: "fixture",
      title: t("stepFixture"),
      done: (fixtures?.fixtures_held ?? 0) > 0,
      unknown: fixtureUnknown,
      evidence: fixtures
        ? t("evidenceFixtures", { count: fixtures.fixtures_held })
        : fixtureUnknown
          ? t("figuresUnknown")
          : t("noClubYet"),
      href: firstClub?.path ?? "/club",
    },
    {
      key: "result",
      title: t("stepResult"),
      done: (fixtures?.played ?? 0) > 0,
      unknown: fixtureUnknown,
      evidence: fixtures
        ? t("evidencePlayed", { count: fixtures.played })
        : fixtureUnknown
          ? t("figuresUnknown")
          : t("noClubYet"),
      href: firstClub?.path ?? "/club",
    },
  ];
  const complete = steps.every((step) => step.done);

  return (
    <div className="container page" style={{ maxWidth: "820px" }}>
      <div className="stack" style={{ gap: "1.25rem" }}>
        <div>
          <p className="eyebrow">{t("firstRunEyebrow")}</p>
          <h1 className="h1">{t("firstRunTitle")}</h1>
          <p className="lede" style={{ marginTop: "0.5rem" }}>
            {t("firstRunLede")}
          </p>
        </div>

        {!clubResult.ok && (
          <div className="notice notice--warn">{errorMessage(clubResult.error, t("clubUnreadable"))}</div>
        )}

        <Panel eyebrow={t("firstRunEyebrow")} title={t("firstRunTitle")}>
          <ol className="stack-sm" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {steps.map((step, index) => (
              <li
                key={step.key}
                className="between wrap"
                style={{
                  gap: "0.6rem",
                  padding: "0.6rem 0",
                  borderTop: index === 0 ? "none" : "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <div className="stack-sm">
                  <span className="row wrap" style={{ gap: "0.5rem", alignItems: "center" }}>
                    <span className="num muted">{index + 1}.</span>
                    <strong>{step.title}</strong>
                    <span className={`badge ${step.done ? "badge--live" : "badge--demo"}`}>
                      {step.done ? t("stepDone") : step.unknown ? t("stepUnknown") : t("stepNext")}
                    </span>
                  </span>
                  <span className="muted" style={{ fontSize: "0.82rem" }}>
                    {step.evidence}
                  </span>
                </div>
                {!step.done && (
                  <Link className="btn btn--ghost btn--sm" href={step.href}>
                    {t("openStep")}
                  </Link>
                )}
              </li>
            ))}
          </ol>
          <p className="muted" style={{ fontSize: "0.82rem", marginTop: "0.75rem" }}>
            {complete ? t("firstRunComplete") : t("firstRunFooter")}
          </p>
          <div className="row wrap" style={{ gap: "0.6rem", marginTop: "0.75rem" }}>
            <Link className="btn btn--primary" href="/my-football">
              {t("openMyFootball")}
            </Link>
          </div>
        </Panel>
      </div>
    </div>
  );
}
