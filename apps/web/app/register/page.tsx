import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { currentUser } from "@/lib/server";
import { RegisterForm } from "./RegisterForm";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auth");
  return {
    title: t("createTitle"),
    description: t("createDescription"),
  };
}

export default async function RegisterPage() {
  const user = await currentUser();
  if (user) redirect("/my-football");
  const t = await getTranslations("auth");

  return (
    <div className="container page" style={{ maxWidth: "520px" }}>
      <div className="stack" style={{ gap: "1.25rem" }}>
        <div>
          <p className="eyebrow">{t("getStarted")}</p>
          <h1 className="h1">{t("createTitle")}</h1>
          <p className="lede" style={{ marginTop: "0.5rem" }}>
            {t("registerLede")}
          </p>
        </div>
        <RegisterForm />
      </div>
    </div>
  );
}
