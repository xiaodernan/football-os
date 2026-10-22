"use client";

import { useTranslations } from "next-intl";

/**
 * The page's own failure boundary.
 *
 * The tree had a `not-found.tsx` in the reader's language and **no** boundary for a page that throws —
 * so a broken page was Next.js's default error screen: an English sentence in every language, on a
 * page whose every other sentence comes from the catalogue. The boundary is the reader's language
 * too, and it offers the one thing a reader can do with a page that failed: ask for it again.
 *
 * The error itself is not shown: it is the server's, and it is the operator's to read in the log. What
 * the reader is shown is the sentence and the way back.
 */
export default function ErrorBoundary({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useTranslations("errorBoundary");
  return (
    <div className="container page" style={{ maxWidth: "560px" }}>
      <div className="stack" style={{ gap: "1rem" }}>
        <span className="eyebrow">{t("eyebrow")}</span>
        <h1 className="h1">{t("title")}</h1>
        <p className="lede">{t("lede")}</p>
        <div className="row wrap" style={{ gap: "0.6rem" }}>
          <button className="btn btn--primary" type="button" onClick={() => reset()}>
            {t("retry")}
          </button>
        </div>
      </div>
    </div>
  );
}
