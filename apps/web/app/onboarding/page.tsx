import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { errorMessage } from "@/lib/api";
import { currentUser, serverFetch } from "@/lib/server";
import type { Player } from "@/lib/types";
import { OnboardingForm } from "./OnboardingForm";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Create your football identity",
  description: "Tell us who you play as and FOOTBALL OS derives your starting profile.",
};

export default async function OnboardingPage() {
  const user = await currentUser();
  if (!user) redirect("/login");

  const playersResult = await serverFetch<Player[]>("/players");
  if (playersResult.ok && playersResult.data.length > 0) redirect("/my-football");

  const notice =
    !playersResult.ok && playersResult.status !== 401 && playersResult.status !== 409
      ? errorMessage(playersResult.error, "We could not check for an existing profile. You can still create one below.")
      : null;

  return (
    <div className="container page" style={{ maxWidth: "640px" }}>
      <div className="stack" style={{ gap: "1.25rem" }}>
        <div>
          <p className="eyebrow">One-time setup</p>
          <h1 className="h1">Create your football identity</h1>
          <p className="lede" style={{ marginTop: "0.5rem" }}>
            Your overall rating and archetype are not invented — they are derived from your level,
            position and the stored attribute model, then shown with the reasons behind them.
          </p>
        </div>
        {notice && <div className="notice notice--warn">{notice}</div>}
        <OnboardingForm />
      </div>
    </div>
  );
}
