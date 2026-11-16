"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { readScrollDirection, SCROLL_DIRECTION } from "@/lib/scrollDirection";

/**
 * The reverse-wheel switch. Mounts inside the Appearance Panel of /settings.
 *
 * The toggle source of truth is localStorage; the inline script in `app/layout.tsx`
 * reads that key on every navigation to decide what direction the page's wheel handler
 * uses. So the toggle writes the key, then reloads — the reload is the install.
 */
export function ScrollDirectionToggle() {
  const t = useTranslations("settings");
  const [direction, setDirection] = useState<"natural" | "inverted">(() => readScrollDirection());
  const [pending, setPending] = useState(false);

  useEffect(() => {
    setDirection(readScrollDirection());
  }, []);

  function toggle() {
    if (pending) return;
    setPending(true);
    try {
      const next = direction === "natural" ? "inverted" : "natural";
      if (next === "natural") {
        window.localStorage.removeItem(SCROLL_DIRECTION);
      } else {
        window.localStorage.setItem(SCROLL_DIRECTION, "inverted");
      }
      setDirection(next);
      // The wheel handler is installed inline by the layout; reloading runs it with the new flag.
      window.location.reload();
    } catch {
      setDirection(direction);
      setPending(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
      <label className="check" style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
        <input type="checkbox" checked={direction === "inverted"} disabled={pending} onChange={toggle} />
        <span>{direction === "inverted" ? t("wheelInvertLabel") : t("wheelNaturalLabel")}</span>
      </label>
      <p className="muted" style={{ fontSize: "0.78rem", margin: 0 }}>{t("wheelNote")}</p>
    </div>
  );
}
