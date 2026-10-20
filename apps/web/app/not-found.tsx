import Link from "next/link";
import { useTranslations } from "next-intl";

export default function NotFound() {
  const t = useTranslations("notFound");
  return (
    <div className="container page" style={{ maxWidth: "560px" }}>
      <div className="stack" style={{ gap: "1rem" }}>
        <span className="eyebrow">{t("eyebrow")}</span>
        <h1 className="h1">{t("title")}</h1>
        <p className="lede">
          {t("lede")}
        </p>
        <div className="row wrap" style={{ gap: "0.6rem" }}>
          <Link className="btn btn--primary" href="/">
            {t("backHome")}
          </Link>
          <Link className="btn" href="/my-football">
            My Football
          </Link>
          <Link className="btn btn--ghost" href="/training">
            Training
          </Link>
        </div>
      </div>
    </div>
  );
}
