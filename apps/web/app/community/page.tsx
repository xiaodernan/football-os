import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { CommunityWall, PostComposer } from "@/components/CommunityTools";
import { Panel } from "@/components/ui";
import { WorldHead, WorldUnavailable } from "@/components/world";
import { refusalFigures, type CommunityFeed, type CommunityProfile, type CommunityRules } from "@/lib/community";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";

import "../../styles/tactics.css";

export const dynamic = "force-dynamic";

/**
 * §35's community: what this account publishes, what reaches it, and the rulebook that says why.
 *
 * Private, because a feed is a person's reading list — while the vocabulary it is built from is published at
 * `GET /api/v1/community/rules`, which needs no account and is fetched here anyway, so the page can hold its own
 * numbers against the caps it did not write.
 *
 * Three things on this screen are deliberately not invented by the page:
 *
 * * every figure (`likes`, `comments`, `reposts`, `followers`, `following`, `total`) is counted by the door from
 *   the rows it names, and the formula is printed beside it — the tier stores no counter, so a stale figure is
 *   not a thing this page could show;
 * * a post's `pointer` is an address, never a copy: the link goes to the page the kind names, and the figures of
 *   the board, plan or match behind it are read where they live;
 * * the follow state of a button is derived from the feed's own authors (the tier's `feed_total` formula says a
 *   reachable post is the reader's own or from an account they follow). A followed account that publishes nothing
 *   reachable is therefore not listed here, because the doors publish counts and no recipient list, and a page
 *   that guessed the missing rows would be inventing the one thing this tier refuses to store.
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("community");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/community") },
  };
}

export default async function CommunityPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcommunity");

  const t = await getTranslations("community");
  const tn = await getTranslations("nav");
  const [rules, feed, profile] = await Promise.all([
    serverFetch<CommunityRules>("/community/rules"),
    serverFetch<CommunityFeed>("/community/posts"),
    serverFetch<CommunityProfile>(`/community/members/${encodeURIComponent(user.id)}`),
  ]);
  if (!rules.ok) return <WorldUnavailable detail={refusalFigures(rules.error.details).join(" · ")} message={rules.error.message} title={tn("community")} />;
  if (!feed.ok) return <WorldUnavailable detail={refusalFigures(feed.error.details).join(" · ")} message={feed.error.message} title={tn("community")} />;
  if (!profile.ok) return <WorldUnavailable message={t("profileUnreadable")} title={tn("community")} />;

  const following = [...new Set(feed.data.items.filter(row => row.author.id !== user.id).map(row => row.author.id))];

  return (
    <div className="container page stack">
      <WorldHead
        back={{href: "/", label: tn("home")}}
        eyebrow={t("headEyebrow", { name: user.display_name, posts: profile.data.posts, max: rules.data.caps.post_max, followers: profile.data.followers })}
        lede={t("headLede")}
        title={t("headTitle")}
      />

      <Panel eyebrow={t("composerEyebrow", { following: profile.data.following, followingMax: rules.data.caps.following_max, posts: rules.data.counts.posts, follows: rules.data.counts.follows })} title={t("composerTitle")}>
        <PostComposer caps={rules.data.caps} profile={profile.data} />
      </Panel>

      <Panel eyebrow={t("feedEyebrow", { total: feed.data.total, printed: feed.data.items.length, authors: feed.data.feed_authors ?? 0 })} title={t("feedTitle")}>
        <CommunityWall caps={rules.data.caps} feed={feed.data} following={following} profile={profile.data} viewer={user.id} />
        <p className="muted" style={{fontSize: "0.8rem"}}>
          {t("feedNote")}
        </p>
      </Panel>

      <Panel eyebrow={t("refusalsEyebrow", { count: Object.keys(rules.data.refusal_answers).length })} title={t("refusalsTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("thCode")}</th>
                <th scope="col">{t("thAnswer")}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(rules.data.refusal_answers)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([code, answer]) => (
                  <tr data-refusal={code} key={code}>
                    <td className="mono">{code}</td>
                    <td className="num">{answer}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{fontSize: "0.82rem"}}>
          {t("refusalsNote")}
        </p>
      </Panel>

      <Panel eyebrow={t("doorsEyebrow", { count: rules.data.routes.length })} title={t("doorsTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("thMethod")}</th>
                <th scope="col">{t("thPath")}</th>
                <th scope="col">{t("thPurpose")}</th>
              </tr>
            </thead>
            <tbody>
              {rules.data.routes.map(route => (
                <tr data-door={`${route.method} ${route.path}`} key={`${route.method} ${route.path}`}>
                  <td className="mono">{route.method}</td>
                  <td className="mono">{route.path}</td>
                  <td className="muted">{route.door}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel eyebrow={t("pointersEyebrow", { count: Object.keys(rules.data.caps.pointer_prefixes).length })} title={t("pointersTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("thKind")}</th>
                <th scope="col">{t("thPrefix")}</th>
                <th scope="col">{t("thOpens")}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(rules.data.caps.pointer_prefixes).map(([kind, prefix]) => (
                <tr data-kind={kind} key={kind}>
                  <td className="mono">{kind}</td>
                  <td className="mono">{prefix}</td>
                  <td>
                    <Link className="world-link" href={prefix}>
                      {prefix}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted" style={{fontSize: "0.82rem"}}>
          {t("pointersNote")}
        </p>
      </Panel>

      <Panel eyebrow={rules.data.limitation ? t("limitsEyebrowOne") : t("limitsEyebrowNone")} title={t("limitsTitle")}>
        <p className="muted" style={{fontSize: "0.86rem", margin: 0}}>
          {rules.data.limitation}
        </p>
        <p className="muted" style={{fontSize: "0.82rem", marginTop: "0.6rem"}}>
          {t.rich("limitsNote", { code: chunks => <span className="mono">{chunks}</span> })}
        </p>
      </Panel>
    </div>
  );
}
