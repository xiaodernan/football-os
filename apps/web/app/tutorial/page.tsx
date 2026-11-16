import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { pageMetadata } from "@/lib/site";

export const dynamic = "force-dynamic";

/**
 * The tutorial — the one door a new reader is invited to knock before anything else.
 *
 * It is deliberately a page inside the product, not a PDF or a doc: every step is a
 * Link the user can follow today, and every claim the page makes about the product is
 * the kind a new user can verify before signing up as anything more than a spectator.
 * The order follows a first session: arrive, know where you are, know what the doors
 * do, take one seat, watch one match, learn the world, read the manual, come back.
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("tutorial");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/tutorial",
  });
}

type Step = { n: number; titleKey: string; bodyKey: string; href: string };

const STEPS: Step[] = [
  { n: 1, titleKey: "step1Title", bodyKey: "step1Body", href: "/login" },
  { n: 2, titleKey: "step2Title", bodyKey: "step2Body", href: "/my-football" },
  { n: 3, titleKey: "step3Title", bodyKey: "step3Body", href: "/world" },
  { n: 4, titleKey: "step4Title", bodyKey: "step4Body", href: "/coach" },
  { n: 5, titleKey: "step5Title", bodyKey: "step5Body", href: "/world/almanac" },
  { n: 6, titleKey: "step6Title", bodyKey: "step6Body", href: "/tactics" },
  { n: 7, titleKey: "step7Title", bodyKey: "step7Body", href: "/challenges" },
  { n: 8, titleKey: "step8Title", bodyKey: "step8Body", href: "/live" },
  { n: 9, titleKey: "step9Title", bodyKey: "step9Body", href: "/manual" },
  { n: 10, titleKey: "step10Title", bodyKey: "step10Body", href: "/" },
];

export default async function TutorialPage() {
  const t = await getTranslations("tutorial");
        return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <header className="page__head" style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1 className="h1" style={{ maxWidth: "32ch" }}>{t("title")}</h1>
        <p className="lede" style={{ maxWidth: "58ch" }}>{t("lede")}</p>
        <p className="muted" style={{ maxWidth: "58ch", fontSize: "0.82rem" }}>{t("honestyNote")}</p>
      </header>

      <Panel eyebrow={t("quickTitle")} title="">
        <ol className="manual__steps">
          {STEPS.map((step) => (
            <li key={step.n} className="manual__step">
              <span className="manual__step-num" aria-hidden="true">{step.n}</span>
              <span className="manual__step-body">
                <strong>{t(step.titleKey)}</strong>
                <span className="muted">{t(step.bodyKey)}</span>
                <span style={{ marginTop: "0.35rem" }}>
                  <Link className="btn btn--small" href={step.href}>
                    {t("openLink")} <span className="manual__door-arrow" aria-hidden="true"> → </span>
                  </Link>
                </span>
              </span>
            </li>
          ))}
        </ol>
      </Panel>

      <section className="manual__glossary" style={{ paddingTop: "1.1rem" }}>
        <span className="manual__toc-eyebrow">{t("deepDiveEyebrow")}</span>
        <h2 className="manual__glossary-title">{t("deepDiveTitle")}</h2>
        <p className="manual__glossary-lede muted">{t("deepDiveLede")}</p>
        <div className="manual__glossary-list" style={{ marginTop: "0.6rem" }}>
          <div className="manual__glossary-row">
            <dt className="manual__glossary-term">{t("dd1Term")}</dt>
            <dd className="manual__glossary-body muted">{t("dd1Body")}</dd>
          </div>
          <div className="manual__glossary-row">
            <dt className="manual__glossary-term">{t("dd2Term")}</dt>
            <dd className="manual__glossary-body muted">{t("dd2Body")}</dd>
          </div>
          <div className="manual__glossary-row">
            <dt className="manual__glossary-term">{t("dd3Term")}</dt>
            <dd className="manual__glossary-body muted">{t("dd3Body")}</dd>
          </div>
          <div className="manual__glossary-row">
            <dt className="manual__glossary-term">{t("dd4Term")}</dt>
            <dd className="manual__glossary-body muted">{t("dd4Body")}</dd>
          </div>
        </div>
      </section>

      <p className="manual__closing muted">
        <Link href="/manual" className="manual__door-arrow" style={{ textDecoration: "underline" }}>
          {t("toManual")}
        </Link>
        <span style={{ margin: "0 0.9rem" }}>·</span>
        <Link href="/" className="manual__door-arrow" style={{ textDecoration: "underline" }}>
          {t("toHome")}
        </Link>
      </p>
    </div>
  );
}
