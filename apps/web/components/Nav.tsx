"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

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
 * The keys are the `nav.*` namespace, which already existed in all three catalogues and already matched this
 * list one for one. The few labels that had no key were added rather than renamed, so the English a reader sees
 * is byte-identical to what it was — an i18n change should not be a copy change.
 */
const LINKS: { href: string; key: string }[] = [
  { href: "/", key: "home" },
  { href: "/my-football", key: "myFootball" },
  { href: "/coach", key: "coach" },
  { href: "/knowledge", key: "knowledge" },
  { href: "/world", key: "world" },
  { href: "/tactics", key: "tactics" },
  { href: "/agents", key: "agents" },
  { href: "/scout", key: "scout" },
  { href: "/training", key: "training" },
  { href: "/progress", key: "progress" },
  { href: "/history", key: "history" },
];

export function Nav({ user, demoMode }: { user: UserOut | null; demoMode: boolean }) {
  const t = useTranslations("nav");
  const tAuth = useTranslations("auth");
  const tCommon = useTranslations("common");
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    await browserFetch("/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <nav className="nav">
      <div className="nav__inner">
        <Link className="nav__brand" href="/">
          FOOTBALL<span>OS</span>
        </Link>
        <div className="nav__links">
          {LINKS.map((link) => {
            const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link className={`nav__link ${active ? "nav__link--active" : ""}`} href={link.href} key={link.href}>
                {t(link.key)}
              </Link>
            );
          })}
          {/* A board is private working material, so the only door to it is an authenticated one. */}
          {user && (
            <>
              <Link className={`nav__link ${pathname.startsWith("/tactics/boards") ? "nav__link--active" : ""}`} href="/tactics/boards">
                {t("myBoards")}
              </Link>
              <Link className={`nav__link ${pathname.startsWith("/video") ? "nav__link--active" : ""}`} href="/video">
                {t("videoShort")}
              </Link>
              <Link className={`nav__link ${pathname.startsWith("/club") ? "nav__link--active" : ""}`} href="/club">
                {t("club")}
              </Link>
              <Link className={`nav__link ${pathname.startsWith("/community") ? "nav__link--active" : ""}`} href="/community">
                {t("community")}
              </Link>
              <Link className={`nav__link ${pathname.startsWith("/portfolio") ? "nav__link--active" : ""}`} href="/portfolio">
                {t("footballCv")}
              </Link>
              <Link className={`nav__link ${pathname.startsWith("/simulate") ? "nav__link--active" : ""}`} href="/simulate">
                {t("simulator")}
              </Link>
            </>
          )}
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
              <button className="btn btn--ghost btn--sm" onClick={signOut} disabled={busy} type="button">
                {busy ? tAuth("signingOut") : tAuth("signOut")}
              </button>
            </>
          ) : (
            <>
              <Link className="nav__link" href="/login">
                {tAuth("signIn")}
              </Link>
              <Link className="btn btn--primary btn--sm" href="/register">
                {tAuth("createAccount")}
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
