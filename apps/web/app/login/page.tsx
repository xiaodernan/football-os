import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { currentUser } from "@/lib/server";
import { LoginForm } from "./LoginForm";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auth");
  return {
    title: t("signIn"),
    description: t("signInDescription"),
  };
}

export default async function LoginPage() {
  const user = await currentUser();
  if (user) redirect("/my-football");
  const t = await getTranslations("auth");

  return (
    <div className="container page" style={{ maxWidth: "480px" }}>
      <div className="stack" style={{ gap: "1.25rem" }}>
        <div>
          <p className="eyebrow">{t("welcomeBack")}</p>
          <h1 className="h1">{t("signIn")}</h1>
          <p className="lede" style={{ marginTop: "0.5rem" }}>
            {t("signInLede")}
          </p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
