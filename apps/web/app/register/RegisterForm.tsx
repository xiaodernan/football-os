"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";
import type { TokenPair } from "@/lib/types";

const ROLES: { value: string; label: string }[] = [
  { value: "fan", label: "Fan — I follow the game" },
  { value: "player", label: "Player — I want to train" },
  { value: "coach", label: "Coach" },
  { value: "manager", label: "Manager" },
  { value: "scout", label: "Scout" },
  { value: "academy", label: "Academy" },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const CONSENT =
  "I understand FOOTBALL OS stores the details I enter to build my profile, that all content in this build is synthetic demo data, and that AI coach output is an estimate — not a performance, medical or scouting certification.";

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
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("player");
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  function validate(): string[] {
    const found: string[] = [];
    if (!EMAIL_RE.test(email.trim())) found.push("Enter a valid email address.");
    if (password.length < 10) found.push("Password must be at least 10 characters.");
    if (!displayName.trim()) found.push("Enter a display name.");
    if (!role) found.push("Choose what best describes you.");
    if (!consent) found.push("You must accept the data policy to continue.");
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
        ? "That email is already registered. Try signing in instead."
        : errorMessage(result.error, "We could not create your account.");
    setErrors(detail.length ? [headline, ...detail] : [headline]);
  }

  return (
    <form className="panel" onSubmit={onSubmit} style={{ display: "grid", gap: "1rem", padding: "1.15rem" }}>
      <div className="field">
        <label className="field__label" htmlFor="email">
          Email
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
        <span className="field__hint">We only use this to sign you in.</span>
      </div>

      <div className="field">
        <label className="field__label" htmlFor="password">
          Password
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
        <span className="field__hint">At least 10 characters.</span>
      </div>

      <div className="field">
        <label className="field__label" htmlFor="display_name">
          Display name
        </label>
        <input
          id="display_name"
          className="input"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="What should we call you?"
        />
      </div>

      <div className="field">
        <label className="field__label" htmlFor="role">
          I am a…
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
        <span>{CONSENT}</span>
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
        {pending ? "Creating account…" : "Create account"}
      </button>

      <p className="muted" style={{ fontSize: "0.88rem" }}>
        Already registered?{" "}
        <Link href="/login" style={{ color: "var(--accent)" }}>
          Sign in
        </Link>
      </p>
    </form>
  );
}
