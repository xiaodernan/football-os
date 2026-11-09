import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { serverFetch } from "@/lib/server";
import { LeaderboardToggle } from "@/components/LeaderboardToggle";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("leaderboard");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

type LeaderboardResult = {
  leaders: Array<{ rank: number; name: string; xp: number; streak: number }>;
  me: { xp: number; streak: number; rank: number; visible: boolean } | null;
  leaders_visible: number;
  window_days: number;
};

export default async function LeaderboardPage() {
  const [t, tAuth] = await Promise.all([getTranslations("leaderboard"), getTranslations("auth")]);

  const result = await serverFetch<LeaderboardResult>("/leaderboard");

  if (!result.ok) {
    return (
      <div className="page container">
        <div className="stack">
          <h1 className="h1">{t("title")}</h1>
          <p className="notice notice--warn">{t("requestFailed")}</p>
        </div>
      </div>
    );
  }

  const { leaders, me, leaders_visible: visible } = result.data;

  return (
    <div className="page container">
      <div className="stack">
        <span className="eyebrow">{t("eyebrow")}</span>
        <h1 className="h1">{t("title")}</h1>
        <p className="lede">{t("lede")}</p>

        {me ? (
          <LeaderboardToggle me={me} />
        ) : (
          <Link href="/login" className="chip" style={{ alignSelf: "flex-start" }}>
            {tAuth("signIn")}
          </Link>
        )}

        {me && (
          <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
            <span className="chip">{t("xp", { xp: me.xp })}</span>
            <span className="chip">{t("streak", { count: me.streak })}</span>
            <span className="chip">{t("rank", { rank: me.rank })}</span>
          </div>
        )}

        {leaders.length === 0 ? (
          <section className="empty-state">
            <h2 className="h4">{t("emptyTitle")}</h2>
            <p className="muted">{t("emptyNote")}</p>
          </section>
        ) : (
          <table className="table" aria-label={t("title")}>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">{t("thPlayer")}</th>
                <th scope="col">{t("thXp")}</th>
                <th scope="col">{t("thStreak")}</th>
              </tr>
            </thead>
            <tbody>
              {leaders.map((entry) => (
                <tr key={entry.rank}>
                  <td>{entry.rank}</td>
                  <td>{entry.name}</td>
                  <td>{t("xp", { xp: entry.xp })}</td>
                  <td>{t("streak", { count: entry.streak })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <p className="muted">
          {t("leadersVisible", { count: visible })}
          {" · "}
          <Link href="/progress">{t("meTitle")}</Link>
        </p>
      </div>
    </div>
  );
}
