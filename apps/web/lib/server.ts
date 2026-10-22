/**
 * Server-only half of the API layer: reads the httpOnly access token from the request
 * cookie jar and calls FastAPI directly. Importable from server components only.
 */

import { cookies } from "next/headers";

import { ACCESS_COOKIE, apiBase, readError, type ApiResult } from "@/lib/api";
import { localiseRefusal } from "@/lib/refusals";
import type { UserOut } from "@/lib/types";

export type ServerFetchOptions = {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  cache?: RequestCache;
};

export async function serverFetch<T>(path: string, init: ServerFetchOptions = {}): Promise<ApiResult<T>> {
  const url = new URL(`/api/v1${path}`, apiBase());
  for (const [key, value] of Object.entries(init.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  const jar = await cookies();
  const token = jar.get(ACCESS_COOKIE)?.value;
  const headers: Record<string, string> = { accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  let body: string | undefined;
  if (init.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(init.body);
  }
  let response: Response;
  try {
    response = await fetch(url, { method: init.method ?? "GET", headers, body, cache: init.cache ?? "no-store" });
  } catch {
    return {
      ok: false,
      status: 503,
      error: { code: "api_unreachable", message: "The API is not reachable. Start it with scripts/dev.sh." },
    };
  }
  if (!response.ok) return { ok: false, status: response.status, error: await readError(response, localiseRefusal) };
  if (response.status === 204) return { ok: true, status: 204, data: null as T };
  return { ok: true, status: response.status, data: (await response.json()) as T };
}

/** The signed-in user for this request, or null when the session is absent or expired. */
export async function currentUser(): Promise<UserOut | null> {
  const jar = await cookies();
  if (!jar.get(ACCESS_COOKIE)?.value) return null;
  const result = await serverFetch<UserOut>("/auth/me");
  return result.ok ? result.data : null;
}
