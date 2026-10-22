/**
 * Client-safe half of the API layer: no `next/headers` import anywhere in this module,
 * so client components may import it (Next rejects that dependency in a client bundle).
 * Server components use `@/lib/server` instead.
 */

import type { ApiError, UserOut } from "@/lib/types";

export const ACCESS_COOKIE = "fo_access";
export const REFRESH_COOKIE = "fo_refresh";
export const REFRESH_PATH = "/api/v1/auth/refresh";
/**
 * Where the browser keeps `fo_refresh` — `/`, not `/api/v1/auth`.
 *
 * The cookie's path is a browser-side filter: a cookie scoped to `/api/v1/auth` is only ever attached
 * to requests under that prefix, so neither tier that refreshes could read it — the middleware on a
 * page request, the proxy on `/api/v1/careers`. Both read it out of the incoming request's jar, both
 * would find nothing, and a session older than the 15-minute access token ended at the login screen
 * with a valid 30-day credential sitting in the jar. The token is httpOnly and `SameSite=Strict`
 * either way, and the proxy already forwards it to the API on every call it makes, so widening the
 * path exposes it to nothing it did not already travel to.
 */
export const REFRESH_COOKIE_PATH = "/";

export function apiBase(): string {
  return process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8731";
}

export type ApiResult<T> = { ok: true; status: number; data: T } | { ok: false; status: number; error: ApiError };

function normalizeError(status: number, payload: unknown): ApiError {
  const detail = payload && typeof payload === "object" && "detail" in payload ? (payload as { detail: unknown }).detail : payload;
  if (typeof detail === "string") return { code: "error", message: detail };
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>;
    // A refusal that arrives flat — `{code, message, fee, remaining}` — carries its figures beside the
    // sentence, and the sentence is only checkable if the figures survive the trip to the browser.
    const figures = Object.fromEntries(Object.entries(d).filter(([key]) => key !== "code" && key !== "message"));
    return {
      code: typeof d.code === "string" ? d.code : "error",
      message: typeof d.message === "string" ? d.message : "",
      details: d.details ?? d.detail ?? (Object.keys(figures).length ? figures : undefined),
    };
  }
  return { code: "error", message: "" };
}

/**
 * The refusal the API answered with, as the web tier's own error shape.
 *
 * The optional **transform** is how a server-side caller localises the refusal's sentence before it is
 * normalised: the API's `message` is its own English, and `lib/refusals.ts` replaces it with the
 * catalogue's sentence for the same code. The transform is optional so this module stays free of the
 * catalogue — it is imported by client components, and the messages reach the browser through
 * next-intl's provider, not through a bundle of its own.
 */
export async function readError(response: Response, transform?: (payload: unknown) => unknown | Promise<unknown>): Promise<ApiError> {
  try {
    const payload = await response.json();
    return normalizeError(response.status, transform ? await transform(payload) : payload);
  } catch {
    return { code: "error", message: "" };
  }
}

export function errorMessage(error: ApiError | undefined, fallback: string): string {
  if (!error) return fallback;
  return error.message || fallback;
}

/** Client-side call through the Next proxy at /api/v1/*. Cookies travel automatically. */
export async function browserFetch<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<ApiResult<T>> {
  const headers: Record<string, string> = { accept: "application/json" };
  let body: string | undefined;
  if (init.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(init.body);
  }
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method: init.method ?? "GET",
      headers,
      body,
      credentials: "same-origin",
    });
  } catch {
    return { ok: false, status: 502, error: { code: "network_error", message: "" } };
  }
  if (!response.ok) return { ok: false, status: response.status, error: await readError(response) };
  if (response.status === 204) return { ok: true, status: 204, data: null as T };
  return { ok: true, status: response.status, data: (await response.json()) as T };
}

export type { ApiError, UserOut };
