import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/lib/server";
import { LoginForm } from "./LoginForm";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your FOOTBALL OS account.",
};

export default async function LoginPage() {
  const user = await currentUser();
  if (user) redirect("/my-football");

  return (
    <div className="container page" style={{ maxWidth: "480px" }}>
      <div className="stack" style={{ gap: "1.25rem" }}>
        <div>
          <p className="eyebrow">Welcome back</p>
          <h1 className="h1">Sign in</h1>
          <p className="lede" style={{ marginTop: "0.5rem" }}>
            Pick up your player profile, streak and training plan where you left them.
          </p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
