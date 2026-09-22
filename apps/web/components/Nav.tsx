"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { browserFetch } from "@/lib/api";
import type { UserOut } from "@/lib/types";

const LINKS: { href: string; label: string }[] = [
  { href: "/", label: "Home" },
  { href: "/my-football", label: "My Football" },
  { href: "/coach", label: "AI Coach" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/world", label: "Football World" },
  { href: "/tactics", label: "Tactical Lab" },
  { href: "/training", label: "Training" },
  { href: "/progress", label: "Progress" },
  { href: "/history", label: "History" },
];

export function Nav({ user, demoMode }: { user: UserOut | null; demoMode: boolean }) {
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
                {link.label}
              </Link>
            );
          })}
          {/* A board is private working material, so the only door to it is an authenticated one. */}
          {user && (
            <>
              <Link className={`nav__link ${pathname.startsWith("/tactics/boards") ? "nav__link--active" : ""}`} href="/tactics/boards">
                My boards
              </Link>
              <Link className={`nav__link ${pathname.startsWith("/video") ? "nav__link--active" : ""}`} href="/video">
                Video
              </Link>
            </>
          )}
        </div>
        <div className="nav__actions">
          {demoMode && (
            <span className="badge badge--demo" title="No AI provider key configured — outputs come from the rule engine.">
              DEMO MODE
            </span>
          )}
          {user ? (
            <>
              <Link className="nav__link" href="/settings">
                {user.display_name}
              </Link>
              <button className="btn btn--ghost btn--sm" onClick={signOut} disabled={busy} type="button">
                {busy ? "Signing out…" : "Sign out"}
              </button>
            </>
          ) : (
            <>
              <Link className="nav__link" href="/login">
                Sign in
              </Link>
              <Link className="btn btn--primary btn--sm" href="/register">
                Create account
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
