"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { browserFetch } from "@/lib/api";
import { locales } from "@/i18n/locales";
import type { UserOut } from "@/lib/types";

/**
 * The shell, read from `messages/*.json` rather than from string literals.
 *
 * This is the first component in the project to read a catalogue at all. Until it, the whole i18n chain was
 * wired and unused: `middleware.ts` decided a locale from the `fo_locale` cookie, `Accept-Language` and the
 * account's own column; `i18n/request.ts` loaded the matching bundle; `app/layout.tsx` handed it to
 * `NextIntlClientProvider` — and not one page or component called `useTranslations`, so the bundle was loaded
 * into the tree and read by nobody. A catalogue nothing reads is a translation that ships to nobody, and it also
 * means the plumbing could not be checked: with every page on literals, "the locale works" was untestable.
 *
 * The keys are the `nav.*` namespace, which already existed in every catalogue and already matched this
 * list one for one. The few labels that had no key were added rather than renamed, so the English a reader sees
 * is byte-identical to what it was — an i18n change should not be a copy change.
 */
const LINKS: { href: string; key: string; hint: string; authed?: boolean }[] = [
  { href: "/", key: "home", hint: "navHintHome" },
  { href: "/tutorial", key: "tutorial", hint: "navHintTutorial" },
  { href: "/my-football", key: "myFootball", hint: "navHintHome" },
  { href: "/coach", key: "coach", hint: "navHintCoach" },
  { href: "/knowledge", key: "knowledge", hint: "navHintKnowledge" },
  { href: "/world", key: "world", hint: "navHintWorld" },
  { href: "/tactics", key: "tactics", hint: "navHintKnowledge" },
  { href: "/agents", key: "agents", hint: "navHintCoach" },
  { href: "/scout", key: "scout", hint: "navHintKnowledge" },
  { href: "/training", key: "training", hint: "navHintTraining" },
  { href: "/progress", key: "progress", hint: "navHintTraining" },
  { href: "/history", key: "history", hint: "navHintTraining" },
  { href: "/leaderboard", key: "leaderboard", hint: "navHintWorld" },
  { href: "/notifications", key: "notifications", hint: "navHintNotifications", authed: true },
  { href: "/live", key: "live", hint: "navHintLive", authed: true },
  { href: "/tactics/boards", key: "myBoards", hint: "navHintBoards", authed: true },
  { href: "/video", key: "videoShort", hint: "navHintVideo", authed: true },
  { href: "/club", key: "club", hint: "navHintClub", authed: true },
  { href: "/community", key: "community", hint: "navHintCommunity", authed: true },
  { href: "/portfolio", key: "footballCv", hint: "navHintPortfolio", authed: true },
  { href: "/simulate", key: "simulator", hint: "navHintSimulate", authed: true },
  { href: "/traces", key: "traces", hint: "navHintTraces", authed: true },
];

export function Nav({ user, demoMode }: { user: UserOut | null; demoMode: boolean }) {
  const t = useTranslations("nav");
  const tAuth = useTranslations("auth");
  const tCommon = useTranslations("common");
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  // The tray's unread count, fetched once per mount for a signed-in reader: the badge is
  // an invitation to look, and the tray itself is the source of truth for what it holds.
  const [unread, setUnread] = useState<number | null>(null);
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    fetch("/api/v1/notifications/unread-total", { credentials: "same-origin" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (!cancelled && body && typeof body.unread_total === "number") setUnread(body.unread_total);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [user, pathname]);

  async function signOut() {
    setBusy(true);
    await browserFetch("/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <nav className="nav" aria-label={t("primaryNav")}>
      <div className="nav__inner">
        <Link className="nav__brand" href="/">
          FOOTBALL<span>OS</span>
        </Link>
        <div className="nav__links">
          {LINKS.filter((link) => !link.authed).map((link) => {
            const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                aria-current={active ? "page" : undefined}
                className={`nav__link ${active ? "nav__link--active" : ""}`}
                href={link.href}
                key={link.href}
                title={t(link.hint)}
              >
                {t(link.key)}
              </Link>
            );
          })}
          {/* A board is private working material, so the only door to it is an authenticated one. */}
          {user &&
            LINKS.filter((link) => link.authed).map((link) => {
              const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
              const badge = link.href === "/notifications" && unread !== null && unread > 0 ? unread : null;
              const isTraces = link.href === "/traces";
              if (isTraces && user.role !== "admin") return null;
              return (
                <Link
                  aria-current={active ? "page" : undefined}
                  className={`nav__link ${active ? "nav__link--active" : ""}`}
                  href={link.href}
                  key={link.href}
                  title={t(link.hint)}
                >
                  {t(link.key)}
                  {badge !== null && <span className="chip chip--accent" style={{ marginLeft: "0.3rem", fontSize: "0.72rem" }}>{badge}</span>}
                </Link>
              );
            })}
        </div>
        <div className="nav__actions">
          <LocaleSwitcher locales={[...locales]} />
          {demoMode && (
            <span className="badge badge--demo" title={tCommon("demoModeTitle")}>
              {tCommon("demoMode")}
            </span>
          )}
          {user ? (
            <>
              <Link className="nav__link" href="/settings">
                {user.display_name}
              </Link>
              <button className="btn btn--ghost btn--sm" onClick={signOut} disabled={busy} type="button" title={tAuth("signOut")}>
                {busy ? tAuth("signingOut") : tAuth("signOut")}
              </button>
            </>
          ) : (
            <>
              <Link className="nav__link" href="/login" title={tAuth("signIn")}>
                {tAuth("signIn")}
              </Link>
              <Link className="btn btn--primary btn--sm" href="/register" title={tAuth("createAccount")}>
                {tAuth("createAccount")}
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
