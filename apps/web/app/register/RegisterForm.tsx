"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { browserFetch, errorMessage } from "@/lib/api";
import type { TokenPair } from "@/lib/types";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function detailMessages(details: unknown): string[] {
  if (!Array.isArray(details)) return [];
  return details
    .map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        const msg = (item as { msg?: unknown }).msg;
        return typeof msg === "string" ? msg : null;
      }
      return null;
    })
    .filter((m): m is string => Boolean(m));
}

export function RegisterForm() {
  const t = useTranslations("auth");
  const settingsT = useTranslations("settings");
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("player");
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  const ROLES: { value: string; label: string }[] = [
    { value: "fan", label: t("roleFan") },
    { value: "player", label: t("rolePlayer") },
    { value: "coach", label: t("roleCoach") },
    { value: "manager", label: t("roleManager") },
    { value: "scout", label: t("roleScout") },
    { value: "academy", label: t("roleAcademy") },
  ];

  function validate(): string[] {
    const found: string[] = [];
    if (!EMAIL_RE.test(email.trim())) found.push(t("errEmail"));
    if (password.length < 10) found.push(t("errPasswordLength"));
    if (!displayName.trim()) found.push(t("errDisplayName"));
    if (!role) found.push(t("errRole"));
    if (!consent) found.push(t("errConsent"));
    return found;
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clientErrors = validate();
    if (clientErrors.length) {
      setErrors(clientErrors);
      return;
    }
    setErrors([]);
    setPending(true);
    const result = await browserFetch<TokenPair>("/auth/register", {
      method: "POST",
      body: {
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        role,
        accepts_data_policy: true,
      },
    });
    if (result.ok) {
      router.push("/onboarding");
      router.refresh();
      return;
    }
    setPending(false);
    const detail = detailMessages(result.error.details);
    const headline =
      result.error.code === "email_taken"
        ? t("emailTaken")
        : errorMessage(result.error, t("registerFailed"));
    setErrors(detail.length ? [headline, ...detail] : [headline]);
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
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
        <span className="field__hint">{t("emailHint")}</span>
      </div>

      <div className="field">
        <label className="field__label" htmlFor="password">
          {t("password")}
        </label>
        <input
          id="password"
          className="input"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={10}
        />
        <span className="field__hint">{t("passwordHint")}</span>
      </div>

      <div className="field">
        <label className="field__label" htmlFor="display_name">
          {settingsT("displayName")}
        </label>
        <input
          id="display_name"
          className="input"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder={t("displayNamePlaceholder")}
        />
      </div>

      <div className="field">
        <label className="field__label" htmlFor="role">
          {t("rolePrompt")}
        </label>
        <select id="role" className="select" value={role} onChange={(e) => setRole(e.target.value)}>
          {ROLES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <label className="check">
        <input
          type="checkbox"
          style={{ width: "auto", marginTop: "0.2rem" }}
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        <span>{t("consent")}</span>
      </label>

      {errors.length > 0 && (
        <div className="notice notice--warn" role="alert">
          <ul className="reasons" style={{ margin: 0 }}>
            {errors.map((message, index) => (
              <li className="reasons__item" key={`${message}-${index}`}>
                {message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <button className="btn btn--primary" type="submit" disabled={pending}>
        {pending ? t("creatingAccount") : t("createAccount")}
      </button>

      <p className="muted" style={{ fontSize: "0.88rem" }}>
        {t("alreadyRegistered")}{" "}
        <Link href="/login" style={{ color: "var(--accent)" }}>
          {t("signIn")}
        </Link>
      </p>
    </form>
  );
}
