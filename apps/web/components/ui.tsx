import type { ComponentProps, ReactNode } from "react";
import { useTranslations } from "next-intl";

import type { Drill } from "@/lib/types";

/** Presentational primitives shared by every page. Keep styling in styles/globals.css. */

export function Panel({
  title,
  eyebrow,
  action,
  children,
  footer,
  className = "",
  ...rest
}: Omit<ComponentProps<"section">, "children"> & {
  title?: ReactNode;
  eyebrow?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`.trim()} {...rest}>
      {(title || action) && (
        <header className="panel__head">
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            {title && <h2 className="panel__title">{title}</h2>}
          </div>
          {action}
        </header>
      )}
      <div className="panel__body">{children}</div>
      {footer && <footer className="panel__foot">{footer}</footer>}
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      {hint && <span className="muted" style={{ fontSize: "0.8rem" }}>{hint}</span>}
    </div>
  );
}

export function Meter({ value, max = 99, label }: { value: number; max?: number; label?: ReactNode }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="stack-sm" style={{ gap: "0.25rem" }}>
      {label && (
        <div className="between" style={{ fontSize: "0.82rem" }}>
          <span className="muted">{label}</span>
          <span className="num mono">{value}</span>
        </div>
      )}
      <div className="bar">
        <div className="bar__fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Honest labelling (spec §62): demo mode, provider, model and confidence are always visible. */
export function AiBadge({
  demo_mode,
  provider,
  model,
  confidence,
}: {
  demo_mode?: boolean;
  provider?: string;
  model?: string;
  confidence?: number;
}) {
  const t = useTranslations("common");
  return (
    <div className="row wrap" style={{ gap: "0.4rem" }}>
      {demo_mode ? (
        <span className="badge badge--demo" title={t("noAiKey")}>
          {t("demoData")}
        </span>
      ) : (
        <span className="badge badge--live">{t("aiGenerated")}</span>
      )}
      {provider && <span className="chip">{provider}</span>}
      {model && <span className="chip mono">{model}</span>}
      {typeof confidence === "number" && (
        <span className="chip">{t("confidence", { value: Math.round(confidence * 100) })}</span>
      )}
    </div>
  );
}

export function ReasonList({ items, title }: { items: string[]; title?: string }) {
  const t = useTranslations("common");
  if (!items?.length) return null;
  return (
    <div className="stack-sm">
      <span className="eyebrow">{title ?? t("whyChosen")}</span>
      <ul className="reasons">
        {items.map((item, index) => (
          <li className="reasons__item" key={`${item}-${index}`}>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Empty({ title, body, href, cta }: { title: string; body?: ReactNode; href?: string; cta?: string }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {body && <span className="muted">{body}</span>}
      {href && cta && (
        <a className="btn btn--primary btn--sm" href={href}>
          {cta}
        </a>
      )}
    </div>
  );
}

export function DataUnavailable({ metric }: { metric?: string }) {
  const t = useTranslations("common");
  return (
    <span className="unavailable">
      {metric ? `${metric}: ` : ""}
      {t("dataUnavailable")}
    </span>
  );
}

export function DrillMeta({ drill }: { drill: Drill }) {
  const t = useTranslations("common");
  return (
    <div className="tag-list">
      <span className="chip">{drill.category}</span>
      <span className="chip">{t("minutesCount", { count: drill.duration_min })}</span>
      <span className="chip">{t("difficultyOf", { value: drill.difficulty })}</span>
      <span className="chip">{t("xpGain", { value: drill.xp_base })}</span>
    </div>
  );
}

export function KeyValue({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <div>
      {rows.map(([key, value]) => (
        <div className="kv" key={key}>
          <span className="kv__key">{key}</span>
          <span className="kv__value">{value}</span>
        </div>
      ))}
    </div>
  );
}
