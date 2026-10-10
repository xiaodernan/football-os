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
export const metadata: Metadata = {
  title: "Community",
  description: "What your account publishes, the feed that reaches you, and the rules that decide who reads a post.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/community") },
};

export default async function CommunityPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcommunity");

  const tn = await getTranslations("nav");
  const [rules, feed, profile] = await Promise.all([
    serverFetch<CommunityRules>("/community/rules"),
    serverFetch<CommunityFeed>("/community/posts"),
    serverFetch<CommunityProfile>(`/community/members/${encodeURIComponent(user.id)}`),
  ]);
  if (!rules.ok) return <WorldUnavailable detail={refusalFigures(rules.error.details).join(" · ")} message={rules.error.message} title={tn("community")} />;
  if (!feed.ok) return <WorldUnavailable detail={refusalFigures(feed.error.details).join(" · ")} message={feed.error.message} title={tn("community")} />;
  if (!profile.ok) return <WorldUnavailable message="Your own wall counts could not be read, so this page has nothing to size the ceilings against." title={tn("community")} />;

  const following = [...new Set(feed.data.items.filter(row => row.author.id !== user.id).map(row => row.author.id))];

  return (
    <div className="container page stack">
      <WorldHead
        back={{href: "/", label: "Home"}}
        eyebrow={`${user.display_name} · ${profile.data.posts} of ${rules.data.caps.post_max} posts · ${profile.data.followers} follower(s)`}
        lede="A post here is a pointer and the author's own words: it names the page it shares and stores no figure about it, so what you read beside a share is counted from the rows the moment you ask. Reach is a predicate over follows, recomputed on every read — unfollowing someone withdraws their posts at once and deletes nothing."
        title="Community wall"
      />

      <Panel eyebrow={`${profile.data.following} of ${rules.data.caps.following_max} followed · ${rules.data.counts.posts} posts and ${rules.data.counts.follows} follow rows on the platform`} title="Publish something you own">
        <PostComposer caps={rules.data.caps} profile={profile.data} />
      </Panel>

      <Panel eyebrow={`${feed.data.total} reachable · ${feed.data.items.length} printed · a feed of ${feed.data.feed_authors ?? 0} author(s)`} title="What reaches you right now">
        <CommunityWall caps={rules.data.caps} feed={feed.data} following={following} profile={profile.data} viewer={user.id} />
        <p className="muted" style={{fontSize: "0.8rem"}}>
          The follow button on a row is decided from the authors this feed lists, because the tier publishes counts and no list of who follows whom. A
          followed account with nothing reachable here is not shown as followed.
        </p>
      </Panel>

      <Panel eyebrow={`${Object.keys(rules.data.refusal_answers).length} codes · one status each, from the project’s one table`} title="What a door here refuses, and with what answer">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Answer</th>
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
          There is no 403 in this tier: a community door asks only whether you have a session, and what you may not reach is answered as absence — the same shape a
          row that was never written earns, so no door confirms that somebody else&apos;s private wall exists.
        </p>
      </Panel>

      <Panel eyebrow={`${rules.data.routes.length} published doors`} title="The doors themselves">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Method</th>
                <th scope="col">Path</th>
                <th scope="col">What it is for</th>
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

      <Panel eyebrow={`${Object.keys(rules.data.caps.pointer_prefixes).length} kinds that point, and the page each one names`} title="Where a pointer has to land">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Kind</th>
                <th scope="col">Prefix</th>
                <th scope="col">The page it opens</th>
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
          A `note` points at nothing and every other kind must point under its own prefix; the door refuses the pair otherwise, with the prefix it expected in the
          refusal.
        </p>
      </Panel>

      <Panel eyebrow={`${rules.data.limitation ? "one limit, stated by the API on every read" : "no limit published"}`} title="What this tier does not do">
        <p className="muted" style={{fontSize: "0.86rem", margin: 0}}>
          {rules.data.limitation}
        </p>
        <p className="muted" style={{fontSize: "0.82rem", marginTop: "0.6rem"}}>
          Nothing here is gated on a plan: the entitlement table has no community feature today, so publishing costs nothing and the ceilings above are row counts,
          not prices. Read the vocabulary at <span className="mono">/api/v1/community/rules</span>, which needs no account.
        </p>
      </Panel>
    </div>
  );
}
