/**
 * Read helpers for the public Football World pages.
 *
 * `serverFetch` already returns a typed result; what these add is the part every world page
 * would otherwise repeat: normalising `searchParams`, rebuilding a link that keeps the other
 * filters, and turning a failed read into the one sentence the spec allows (§78 — say the data
 * is unavailable, never substitute a value for it).
 */

import { getTranslations } from "next-intl/server";

import { errorMessage } from "@/lib/api";
import { serverFetch } from "@/lib/server";
import type { ApiResult } from "@/lib/api";

export type WorldQuery = Record<string, string>;

/** `searchParams` is `string | string[] | undefined`; every world filter is a single scalar. */
export function cleanParams(raw: Record<string, string | string[] | undefined>): WorldQuery {
  const query: WorldQuery = {};
  for (const [key, value] of Object.entries(raw)) {
    const scalar = Array.isArray(value) ? value[0] : value;
    if (scalar && scalar.trim()) query[key] = scalar.trim();
  }
  return query;
}

export function buildHref(base: string, query: WorldQuery, overrides: WorldQuery = {}, drop: string[] = []): string {
  const params = new URLSearchParams(query);
  for (const key of drop) params.delete(key);
  for (const [key, value] of Object.entries(overrides)) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

export type WorldRead<T> = { ok: true; data: T; result: ApiResult<T> } | { ok: false; message: string; status: number; notFound: boolean };

function read<T>(result: ApiResult<T>, fallback: string): WorldRead<T> {
  if (result.ok) return { ok: true, data: result.data, result };
  return {
    ok: false,
    status: result.status,
    notFound: result.status === 404 || result.error.code === "not_found",
    message: errorMessage(result.error, fallback),
  };
}

export async function readWorld<T>(path: string, query?: Record<string, string | number | undefined>): Promise<WorldRead<T>> {
  const tc = await getTranslations("common");
  return read(await serverFetch<T>(path, { query }), tc("requestFailed"));
}

/** All five list routes share this `page`/`page_size` convention. */
export function pageOf(query: WorldQuery): number {
  const parsed = Number.parseInt(query.page ?? "1", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

const HEX_COLOR = /^#[0-9a-f]{6}$/i;

/**
 * A club's brand colour reaches an inline `style`, so it is validated rather than trusted:
 * anything but a plain hex triplet renders as no colour at all.
 */
export function brandColor(value: string | null | undefined): string | undefined {
  return value && HEX_COLOR.test(value) ? value : undefined;
}
