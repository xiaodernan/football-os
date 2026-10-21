/**
 * Football World primitives (spec §54–§56, §62, §65, §80).
 *
 * The rule these enforce: provenance travels with the row. `data_origin` and `is_demo_data`
 * are wire fields on every `/world/*` payload, so the badge and the disclaimer are rendered
 * from the payload rather than from a string a page author remembered to type. A row that
 * ever comes from a licensed provider flips the badge on its own.
 */

import { useTranslations } from "next-intl";
import Link from "next/link";
import type { ReactNode } from "react";

import type { CompetitionBrief, EntityRef, MatchBrief, PlayerBrief, TeamBrief, WorldEnvelope } from "@/lib/types";

import "../styles/world.css";

/** The two wire fields that say what a row is, plus the disclaimer that says why. */
export type RowProvenance = Pick<WorldEnvelope, "data_origin" | "is_demo_data"> & { disclaimer?: string };

/** `iso` → "17 Aug 2027". Everything is formatted in UTC because the stored timestamps are UTC. */
export function formatDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const stamp = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(stamp.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(stamp);
}

export function formatMoment(iso: string | null | undefined): string {
  if (!iso) return "—";
  const stamp = new Date(iso);
  if (Number.isNaN(stamp.getTime())) return iso;
  return `${new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(stamp)} · ${new Intl
    .DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }).format(stamp)} UTC`;
}

/**
 * One badge for the whole `data_origin` vocabulary, so two surfaces cannot label the same fact
 * differently. Synthetic is demo data; project-authored is authored content (the knowledge corpus,
 * the tactical catalogue) and must not be softened into "demo"; anything else is a named source.
 */
export function OriginBadge({ provenance }: { provenance: RowProvenance }) {
  const t = useTranslations("common");
  const authored = provenance.data_origin === "project-authored" && !provenance.is_demo_data;
  const synthetic = !authored && (provenance.data_origin === "synthetic" || provenance.is_demo_data);
  const label = authored ? t("authoredBadge") : synthetic ? t("demoData") : t("sourceLabel", { origin: provenance.data_origin });
  const title = authored
    ? t("authoredBadgeTitle")
    : synthetic
      ? t("demoDataTitle", { origin: provenance.data_origin, demo: String(provenance.is_demo_data) })
      : t("sourceTitle", { origin: provenance.data_origin });
  return (
    <span className={`badge ${authored ? "badge--authored" : synthetic ? "badge--demo" : "badge--live"}`} title={title}>
      {label}
    </span>
  );
}

/** The row's own disclaimer, printed under the content it describes. */
export function Provenance({ provenance, extra }: { provenance: RowProvenance; extra?: ReactNode }) {
  return (
    <div className="world-prov">
      <div className="tag-list">
        <span className="chip mono">data_origin: {provenance.data_origin}</span>
        <span className="chip mono">is_demo_data: {String(provenance.is_demo_data)}</span>
        {extra}
      </div>
      {provenance.disclaimer && <p className="world-prov__text muted">{provenance.disclaimer}</p>}
    </div>
  );
}

export function WorldHead({
  eyebrow,
  title,
  lede,
  provenance,
  back,
  children,
}: {
  eyebrow: string;
  title: string;
  lede?: string;
  provenance?: RowProvenance;
  back?: { href: string; label: string };
  children?: ReactNode;
}) {
  return (
    <div>
      {back && (
        <Link className="muted world-back" href={back.href}>
          ← {back.label}
        </Link>
      )}
      <div className="between wrap world-head">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="h1">{title}</h1>
          {lede && <p className="lede">{lede}</p>}
        </div>
        {provenance && <OriginBadge provenance={provenance} />}
      </div>
      {children}
    </div>
  );
}

/** Links out of the API's own `path` fields — the §80 route table lives in one place, server-side. */
export function EntityLink({
  href,
  label,
  fallback,
  className = "world-link",
}: {
  href: string | null | undefined;
  label: string | null | undefined;
  fallback?: string;
  className?: string;
}) {
  const t = useTranslations("common");
  if (!label) return <span className="unavailable">{fallback ?? t("dataUnavailable")}</span>;
  if (!href) return <span>{label}</span>;
  return (
    <Link className={className} href={href}>
      {label}
    </Link>
  );
}

export function TeamLink({ team, fallbackName }: { team: TeamBrief | null; fallbackName?: string }) {
  return <EntityLink href={team?.path} label={team?.name} fallback={fallbackName} />;
}

export function PlayerLink({ player }: { player: PlayerBrief | null }) {
  return <EntityLink href={player?.path} label={player?.name} />;
}

export function CompetitionLink({ competition }: { competition: CompetitionBrief | null }) {
  return <EntityLink href={competition?.path} label={competition?.name} />;
}

/** `ref` is reserved by React, so the pointer arrives under a different name. */
export function RefLink({ target }: { target: EntityRef }) {
  return (
    <Link className="chip world-ref" href={target.path}>
      <span className="world-ref__type">{target.type}</span>
      {target.slug.replace(/-/g, " ")}
    </Link>
  );
}

/** The "no score yet" state (spec §65): a scheduled fixture shows a kick-off time, never 0-0. */
export function MatchRow({ match }: { match: MatchBrief }) {
  const played = match.status === "completed" && match.home_goals !== null && match.away_goals !== null;
  return (
    <li className="world-fixture">
      <div className="world-fixture__when">
        <span className="mono muted">{formatDay(match.kickoff_at)}</span>
        <span className="world-fixture__round">{match.round_label}</span>
      </div>
      <div className="world-fixture__teams">
        <TeamLink team={match.home} />
        <span aria-label="versus">
          <TeamLink team={match.away} />
        </span>
      </div>
      <div className="world-fixture__score">
        {played ? (
          <span className="num mono">
            {match.home_goals}–{match.away_goals}
          </span>
        ) : (
          <span className="unavailable">Not played · Data unavailable</span>
        )}
      </div>
    </li>
  );
}

/** Server-rendered pagination: real `<a href>`s, so a crawler and a JS-free visitor both work. */
export function WorldPager({
  page,
  pages,
  total,
  build,
}: {
  page: number;
  pages: number;
  total: number;
  build: (page: number) => string;
}) {
  const t = useTranslations("common");
  if (pages <= 1) {
    return <p className="muted world-pageinfo">{t("rowsCount", { total: total.toLocaleString("en-GB") })}</p>;
  }
  return (
    <nav className="between wrap world-pageinfo" aria-label={t("paginationAria")}>
      <span className="muted">
        {t("pageOf", { page, pages, total: total.toLocaleString("en-GB") })}
      </span>
      <div className="row" style={{ gap: "0.4rem" }}>
        {page > 1 && (
          <Link className="btn btn--sm" href={build(page - 1)}>
            ← {t("previousPage")}
          </Link>
        )}
        {page < pages && (
          <Link className="btn btn--sm" href={build(page + 1)}>
            {t("nextPage")} →
          </Link>
        )}
      </div>
    </nav>
  );
}

/** Filter chips that keep every other query parameter, so filters compose instead of resetting. */
export function FilterChips({
  label,
  base,
  param,
  options,
  active,
  query,
  drop = [],
}: {
  label: string;
  base: string;
  param: string;
  options: string[];
  active?: string;
  query: Record<string, string>;
  drop?: string[];
}) {
  const href = (value?: string) => {
    const params = new URLSearchParams(query);
    for (const key of [param, "page", ...drop]) params.delete(key);
    if (value) params.set(param, value);
    const qs = params.toString();
    return qs ? `${base}?${qs}` : base;
  };
  return (
    <div className="stack-sm">
      <span className="eyebrow">{label}</span>
      <div className="tag-list">
        <Link className={`chip ${active ? "" : "chip--accent"}`} href={href()}>
          all
        </Link>
        {options.map((option) => (
          <Link className={`chip ${active === option ? "chip--accent" : ""}`} href={href(option)} key={option}>
            {option.replace(/_/g, " ")}
          </Link>
        ))}
      </div>
    </div>
  );
}

export function KeyValueGrid({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="world-kv">
      {rows.map(([key, value]) => (
        <div className="world-kv__row" key={key}>
          <dt>{key}</dt>
          <dd className="num">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The one state a data-driven page must never paper over: the tables are empty or the API is down. */
export function WorldUnavailable({
  message,
  detail,
  eyebrow,
  title,
}: {
  message: string;
  detail?: ReactNode;
  eyebrow?: string;
  title?: string;
}) {
  const t = useTranslations("common");
  return (
    <div className="container page stack">
      <WorldHead eyebrow={eyebrow ?? t("worldTitle")} title={title ?? t("dataUnavailable")} />
      <div className="notice notice--warn">{message}</div>
      <p className="muted" style={{ fontSize: "0.88rem" }}>
        Nothing here is substituted with invented values (spec §78). {detail}
      </p>
    </div>
  );
}

/** Initials on the club's own colour. No crest, badge or logo image is reproduced (spec §61). */
export function Crest({ color, name }: { color?: string; name: string }) {
  return (
    <span aria-hidden="true" className="world-crest" style={color ? { background: color } : undefined}>
      {name.slice(0, 2).toUpperCase()}
    </span>
  );
}

/** A generated report classifies its own claim level, and the page must show it (spec §62). */
export function ClaimChip({ claimClass }: { claimClass: string }) {
  const className =
    claimClass === "fact" ? "chip chip--accent" : claimClass === "speculation" ? "chip badge--demo" : "chip badge--sim";
  return (
    <span className={className} title={`claim_class: ${claimClass}`}>
      {claimClass}
    </span>
  );
}

export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}
