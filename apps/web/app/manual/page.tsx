import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { pageMetadata } from "@/lib/site";
import "@/styles/manual.css";

/**
 * The concise manual — the book this product hopes every reader opens before anything else.
 *
 * A page, not a PDF. Everything printed on it is a door the reader can actually walk through,
 * and every product claim it makes is the kind this codebase is already held to: doors that exist,
 * figures the gates make, words from the catalogues — never invention, never a promise the
 * build cannot back. Static, public, crawlable by design: the one page of this site a reader can
 * hand to a friend and say "start here".
 */
export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("manual");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/manual",
  });
}

export default async function ManualPage() {
  const t = await getTranslations("manual");
  const tc = await getTranslations("common");
  const tw = await getTranslations("world");

  const quick: { at: number; title: string; desc: string }[] = [
    { at: 1, title: t("quick1t"), desc: t("quick1d") },
    { at: 2, title: t("quick2t"), desc: t("quick2d") },
    { at: 3, title: t("quick3t"), desc: t("quick3d") },
    { at: 4, title: t("quick4t"), desc: t("quick4d") },
    { at: 5, title: t("quick5t"), desc: t("quick5d") },
  ];

  const tour: { href: string; title: string; desc: string }[] = [
    { href: "/my-football", title: t("tour1t"), desc: t("tour1d") },
    { href: "/coach", title: t("tour2t"), desc: t("tour2d") },
    { href: "/world", title: t("tour3t"), desc: t("tour3d") },
    { href: "/world/almanac", title: t("tour4t"), desc: t("tour4d") },
    { href: "/world/story", title: t("tour5t"), desc: t("tour5d") },
    { href: "/world/records", title: t("tour6t"), desc: t("tour6d") },
    { href: "/world/matchday-xi", title: t("tour7t"), desc: t("tour7d") },
    { href: "/world/duel", title: t("tour8t"), desc: t("tour8d") },
    { href: "/world/spotlight", title: t("tour9t"), desc: t("tour9d") },
    { href: "/world/timeline", title: t("tour10t"), desc: t("tour10d") },
    { href: "/world/gazette", title: t("tour11t"), desc: t("tour11d") },
    { href: "/world/finals", title: t("tour12t"), desc: t("tour12d") },
    { href: "/world/noise", title: t("tour13t"), desc: t("tour13d") },
    { href: "/world/upsets", title: t("tour14t"), desc: t("tour14d") },
    { href: "/world/dynasties", title: t("tour15t"), desc: t("tour15d") },
    { href: "/tutorial", title: t("tour16t"), desc: t("tour16d") },
    { href: "/world/real-book", title: t("tour17t"), desc: t("tour17d") },
  ];

  const rules = [t("rule1"), t("rule2"), t("rule3"), t("rule4"), t("rule5"), t("rule6")];
  const faq = [
    { q: t("faq1q"), a: t("faq1a") },
    { q: t("faq2q"), a: t("faq2a") },
    { q: t("faq3q"), a: t("faq3a") },
    { q: t("faq4q"), a: t("faq4a") },
  ];
  const glossary = [
    { term: t("gSeedTitle"), body: t("gSeedBody") },
    { term: t("gTierTitle"), body: t("gTierBody") },
    { term: t("gOverallTitle"), body: t("gOverallBody") },
    { term: t("gXgTitle"), body: t("gXgBody") },
    { term: t("gFormTitle"), body: t("gFormBody") },
    { term: t("gStreakTitle"), body: t("gStreakBody") },
    { term: t("gUpsetTitle"), body: t("gUpsetBody") },
    { term: t("gOriginTitle"), body: t("gOriginBody") },
  ];

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <header className="manual__hero">
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1 className="h1 manual__title">{t("title")}</h1>
        <p className="lede manual__lede">{t("lede")}</p>
      </header>

      <Panel eyebrow={t("quickTitle")} title="">
        <ol className="manual__steps">
          {quick.map((s) => (
            <li key={s.at} className="manual__step">
              <span className="manual__step-num" aria-hidden="true">{s.at}</span>
              <span className="manual__step-body">
                <strong>{s.title}</strong>
                <span className="muted">{s.desc}</span>
              </span>
            </li>
          ))}
        </ol>
      </Panel>

      <Panel eyebrow={t("tourTitle")} title="">
        <div className="manual__doors">
          {tour.map((item) => (
            <Link key={item.href} className="manual__door" href={item.href}>
              <strong>{item.title}</strong>
              <span className="muted">{item.desc}</span>
              <span className="manual__door-arrow" aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      </Panel>

      <Panel eyebrow={t("rulesTitle")} title="">
        <ul className="manual__rules">
          {rules.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>
      </Panel>

      <section className="manual__glossary" aria-labelledby="manual-glossary-eyebrow">
        <div className="manual__glossary-head">
          <span className="manual__toc-eyebrow" id="manual-glossary-eyebrow">{t("glossaryEyebrow")}</span>
          <h2 className="manual__glossary-title">{t("glossaryTitle")}</h2>
          <p className="manual__glossary-lede muted">{t("glossaryLede")}</p>
        </div>
        <dl className="manual__glossary-list">
          {glossary.map(({ term, body }) => (
            <div key={term} className="manual__glossary-row">
              <dt className="manual__glossary-term">{term}</dt>
              <dd className="manual__glossary-body muted">{body}</dd>
            </div>
          ))}
        </dl>
      </section>

      <Panel eyebrow={t("faqTitle")} title="">
        <div className="manual__faq">
          {faq.map((item) => (
            <div key={item.q} className="manual__faq-item">
              <p className="manual__faq-q">{item.q}</p>
              <p className="manual__faq-a muted">{item.a}</p>
            </div>
          ))}
        </div>
      </Panel>

      <p className="manual__closing muted">{t("closingNote")}</p>
    </div>
  );
}
