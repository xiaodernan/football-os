import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/lib/server";
import { RegisterForm } from "./RegisterForm";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Create your account",
  description: "Register for FOOTBALL OS and start your explainable training journey.",
};

export default async function RegisterPage() {
  const user = await currentUser();
  if (user) redirect("/my-football");

  return (
    <div className="container page" style={{ maxWidth: "520px" }}>
      <div className="stack" style={{ gap: "1.25rem" }}>
        <div>
          <p className="eyebrow">Get started</p>
          <h1 className="h1">Create your account</h1>
          <p className="lede" style={{ marginTop: "0.5rem" }}>
            Set up an account, then build a football identity to start earning XP and growing
            attributes.
          </p>
        </div>
        <RegisterForm />
      </div>
    </div>
  );
}
