import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { pageMetadata } from "@/lib/site";
import "../coach.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("coachHow");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/coach/how-it-works",
  });
}

type Node = { id: string; titleKey: string; bodyKey: string };

// The six stages, named exactly as the compiled StateGraph and the graph_trace chips name them.
const NODES: Node[] = [
  { id: "classify_intent", titleKey: "node1Title", bodyKey: "node1Body" },
  { id: "build_arithmetic", titleKey: "node2Title", bodyKey: "node2Body" },
  { id: "spend_gate", titleKey: "node3Title", bodyKey: "node3Body" },
  { id: "phrase_answer", titleKey: "node4Title", bodyKey: "node4Body" },
  { id: "persist_answer", titleKey: "node5Title", bodyKey: "node5Body" },
  { id: "END", titleKey: "node6Title", bodyKey: "node6Body" },
];

const TRACE: string[] = ["START", ...NODES.map((node) => node.id)];

export default async function CoachHowItWorks() {
  const t = await getTranslations("coachHow");

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <header className="coach-how__hero">
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1 className="h1 coach-how__title">{t("title")}</h1>
        <p className="lede coach-how__lede">{t("lede")}</p>
        <Link href="/coach#ask" className="btn btn--primary">
          {t("tryInCoachCta")}
        </Link>
      </header>

      <Panel eyebrow={t("sixNodesEyebrow")} title={t("sixNodesTitle")}>
        <ol className="coach-how__steps">
          {NODES.map((node, index) => (
            <li key={node.id} className="coach-how__step">
              <span className="coach-how__num" aria-hidden="true">{index + 1}</span>
              <span className="coach-how__body">
                <strong>{t(node.titleKey as Parameters<typeof t>[0])}</strong>
                <span className="muted">{t(node.bodyKey as Parameters<typeof t>[0])}</span>
              </span>
            </li>
          ))}
        </ol>
      </Panel>

      <Panel eyebrow={t("neverEyebrow")} title={t("neverTitle")}>
        <ul className="coach-how__faq">
          <li className="coach-how__faq-item"><p>{t("never1")}</p></li>
          <li className="coach-how__faq-item"><p>{t("never2")}</p></li>
          <li className="coach-how__faq-item"><p>{t("never3")}</p></li>
          <li className="coach-how__faq-item"><p>{t("never4")}</p></li>
        </ul>
      </Panel>

      <Panel eyebrow={t("traceEyebrow")} title={t("traceTitle")}>
        <p className="lede coach-how__trace-lede">{t("traceBody")}</p>
        <ol className="coach-how__trace">
          {TRACE.map((nodeName, index) => (
            <li key={`${nodeName}-${index}`}>
              <code>{nodeName}</code>
              {index < TRACE.length - 1 ? <span aria-hidden="true"> → </span> : null}
            </li>
          ))}
        </ol>
      </Panel>

      <p className="muted coach-how__foot">
        {t("moreInLibrary")}{" "}
        <Link className="coach-how__inline-link" href="/knowledge/stategraph-native-zh">
          {t("libraryLink")}
        </Link>
      </p>
    </div>
  );
}
