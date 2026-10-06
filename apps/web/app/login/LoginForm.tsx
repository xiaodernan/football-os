"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { browserFetch, errorMessage } from "@/lib/api";
import type { TokenPair } from "@/lib/types";

export function LoginForm() {
  const t = useTranslations("auth");
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const result = await browserFetch<TokenPair>("/auth/login", {
      method: "POST",
      body: { email: email.trim(), password },
    });
    if (result.ok) {
      router.push("/my-football");
      router.refresh();
      return;
    }
    setPending(false);
    setError(errorMessage(result.error, t("signInFailed")));
  }

  return (
    <form className="panel" onSubmit={onSubmit} style={{ display: "grid", gap: "1rem", padding: "1.15rem" }}>
      <div className="field">
        <label className="field__label" htmlFor="email">
          {t("email")}
        </label>
        <input
          id="email"
          className="input"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
      </div>

      <div className="field">
        <label className="field__label" htmlFor="password">
          {t("password")}
        </label>
        <input
          id="password"
          className="input"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••••"
        />
      </div>

      {error && (
        <div className="notice notice--warn" role="alert">
          {error}
        </div>
      )}

      <button className="btn btn--primary" type="submit" disabled={pending}>
        {pending ? t("signingIn") : t("signIn")}
      </button>

      <p className="muted" style={{ fontSize: "0.88rem" }}>
        {t("noAccountYet")}{" "}
        <Link href="/register" style={{ color: "var(--accent)" }}>
          {t("createOne")}
        </Link>
      </p>

      <p className="field__hint">
        Demo account available: demo@footballos.local / demo-password-123
      </p>
    </form>
  );
}
