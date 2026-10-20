import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { Player } from "@/lib/types";
import { OnboardingForm } from "./OnboardingForm";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("onboarding");
  return { title: t("metaTitle"), description: t("metaDescription") };
}

export default async function OnboardingPage() {
  const t = await getTranslations("onboarding");
  const user = await currentUser();
  if (!user) redirect("/login");

  const playersResult = await serverFetch<Player[]>("/players");
  if (playersResult.ok && playersResult.data.length > 0) redirect("/my-football");

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
