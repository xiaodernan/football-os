"use client";

/**
 * The two slots a duel is picked in.
 *
 * A search box per corner rather than two dropdowns of the whole world: the world holds hundreds of players and a
 * `<select>` of them is a haystack with a lid. Typing hits `/world/search?types=players`, which is the same ranked
 * search the header uses, so the picker cannot disagree with the site's own idea of a match.
 *
 * Nothing navigates on its own. Two names are chosen, the reader presses the one button, and the address it goes to
 * is the duel's canonical URL — `/world/duel/<left>/<right>` — so the pair can be shared, bookmarked and read by a
 * search engine as a page rather than as a query string.
 */

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

type Slot = "left" | "right";
type Hit = { slug: string; title: string; subtitle: string };
type Chosen = Partial<Record<Slot, Hit>>;

async function searchPlayers(query: string, signal: AbortSignal): Promise<Hit[]> {
  const response = await fetch(`/api/v1/world/search?q=${encodeURIComponent(query)}&types=players&limit_rows=8`, {
    credentials: "same-origin",
    signal,
  });
  if (!response.ok) return [];
  const body = (await response.json()) as { results?: Hit[] };
  return body.results ?? [];
}

export function DuelPicker({ initialLeft }: { initialLeft?: Hit }) {
  const t = useTranslations("duel");
  const [slot, setSlot] = useState<Slot>(initialLeft ? "right" : "left");
  const [chosen, setChosen] = useState<Chosen>(initialLeft ? { left: initialLeft } : {});
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [busy, setBusy] = useState(false);
  const [drawn, setDrawn] = useState(false);
  const input = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setHits([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      searchPlayers(trimmed, controller.signal)
        .then(setHits)
        .catch(() => setHits([]));
    }, 220);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query]);

  function pick(hit: Hit) {
    setChosen((current) => ({ ...current, [slot]: hit }));
    setSlot(slot === "left" ? "right" : "left");
    setQuery("");
    setHits([]);
    input.current?.focus();
  }

  async function drawPair() {
    setBusy(true);
    try {
      const first = await fetch("/api/v1/world/players?page_size=100&sort=overall&order=desc", { credentials: "same-origin" });
      const body = (await first.json()) as { items?: { slug: string; name: string; position: string; overall: number }[] };
      const pool = body.items ?? [];
      if (pool.length < 2) return;
      const pickAt = () => pool[Math.floor(Math.random() * pool.length)];
      const a = pickAt();
      let b = pickAt();
      for (let guard = 0; guard < 8 && b.slug === a.slug; guard += 1) b = pickAt();
      if (a.slug === b.slug) return;
      setChosen({
        left: { slug: a.slug, title: a.name, subtitle: `${a.position} · ${a.overall}` },
        right: { slug: b.slug, title: b.name, subtitle: `${b.position} · ${b.overall}` },
      });
      setDrawn(true);
    } finally {
      setBusy(false);
    }
  }

  const ready = chosen.left && chosen.right && chosen.left.slug !== chosen.right.slug;

  const renderSlot = (side: "left" | "right") => {
    const picked = chosen[side];
    return (
      <button
        key={side}
        type="button"
        className={`duel-picker__slot duel-picker__slot--${side}${slot === side ? " is-active" : ""}${picked ? " is-filled" : ""}`}
        onClick={() => {
          setSlot(side);
          input.current?.focus();
        }}
        aria-pressed={slot === side}
      >
        <span className="duel-picker__corner">{side === "left" ? t("pickerLeft") : t("pickerRight")}</span>
        {picked ? (
          <>
            <strong className="duel-picker__name">{picked.title}</strong>
            <span className="duel-picker__sub">{picked.subtitle}</span>
            <span className="duel-picker__change">{t("pickerChange")}</span>
          </>
        ) : (
          <span className="duel-picker__empty">{t("pickerChoose")}</span>
        )}
      </button>
    );
  };

  return (
    <div className="duel-picker stack">
      <div className="duel-picker__slots">
        {renderSlot("left")}
        <span className="duel-picker__seam" aria-hidden="true">
          v
        </span>
        {renderSlot("right")}
      </div>

      <div className="field">
        <label className="field__label" htmlFor="duel-search">
          {t("pickerSearchLabel")}
        </label>
        <input
          id="duel-search"
          ref={input}
          className="input"
          type="search"
          value={query}
          placeholder={t("pickerSearchPlaceholder")}
          autoComplete="off"
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {hits.length > 0 && (
        <ul className="duel-picker__hits">
          {hits.map((hit) => (
            <li key={hit.slug}>
              <button type="button" className="duel-picker__hit" onClick={() => pick(hit)}>
                <strong>{hit.title}</strong>
                <span className="muted">{hit.subtitle}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {query.trim().length >= 2 && hits.length === 0 && <p className="field__hint">{t("pickerEmpty")}</p>}

      <div className="row between wrap duel-picker__actions">
        <button type="button" className="btn btn--ghost" onClick={drawPair} disabled={busy}>
          {busy ? t("pickerDrawing") : t("pickerRandom")}
        </button>
        {ready ? (
          <Link className="btn btn--primary" href={`/world/duel/${chosen.left?.slug}/${chosen.right?.slug}`}>
            {t("pickerFight")}
          </Link>
        ) : (
          <span className="muted">{drawn && !ready ? t("pickerSamePlayer") : t("pickerNeedTwo")}</span>
        )}
      </div>
    </div>
  );
}
