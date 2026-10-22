/**
 * Cookie-based auth proxy: the only place browser traffic meets FastAPI.
 *
 * Responsibilities (spec §60, ADR-003):
 *  - keep the access token httpOnly so no client script can read it
 *  - carry the rotating refresh cookie through to the API and back
 *  - refresh once, transparently, when the access token has expired
 */

import { cookies } from "next/headers";

import { ACCESS_COOKIE, REFRESH_COOKIE, REFRESH_COOKIE_PATH, apiBase } from "@/lib/api";
import { localiseRefusal } from "@/lib/refusals";

type Params = { params: Promise<{ path: string[] }> };

const REFRESH_TTL_DAYS = Number(process.env.REFRESH_TOKEN_TTL_DAYS ?? 30);

type Captured = { accessToken?: string; expiresIn?: number; refresh?: string };

const refreshes = new Map<string, Promise<Captured | null>>();

function parseRefreshCookie(setCookie: string | null): string | undefined {  if (!setCookie) return undefined;
  const pair = setCookie.split(";")[0];
  const index = pair.indexOf("=");
  if (index < 0) return undefined;
  const name = pair.slice(0, index).trim();
  if (name !== REFRESH_COOKIE) return undefined;
  return pair.slice(index + 1).trim();
}

/** The headers that describe a byte range or downloaded file survive only if the proxy copies them across. */
function byteRangeHeaders(response: Response): Record<string, string> {
  const copied: Record<string, string> = {};
  for (const header of ["content-range", "accept-ranges", "content-length", "content-disposition", "cache-control"] as const) {
    const value = response.headers.get(header);
    if (value) copied[header] = value;
  }
  return copied;
}

/** JSON is what the API answers; a byte-range request is media, and must not claim to want JSON. */
function requestAccept(range?: string | null): string {
  return range ? "*/*" : "application/json";
}

async function callApi(
  method: string,
  path: string,
  options: { body?: ArrayBuffer | null; token?: string | null; refreshCookie?: string | null; contentType?: string | null; range?: string | null },
): Promise<{ response: Response; captured: Captured }> {
  const headers: Record<string, string> = { accept: requestAccept(options.range) };
  if (options.token) headers.authorization = `Bearer ${options.token}`;
  if (options.refreshCookie) headers.cookie = `${REFRESH_COOKIE}=${options.refreshCookie}`;
  if (options.body && options.contentType) headers["content-type"] = options.contentType;
  // A <video> element seeks by byte range; without this the player would get the whole clip for every hop.
  if (options.range) headers.range = options.range;

  const response = await fetch(`${apiBase()}${path}`, {
    method,
    headers,
    body: options.body ?? null,
    cache: "no-store",
  });

  const captured: Captured = {};
  const cloned = response.clone();
  try {
    const payload = (await cloned.json()) as { access_token?: string; expires_in_seconds?: number };
    if (payload?.access_token) {
      captured.accessToken = payload.access_token;
      captured.expiresIn = payload.expires_in_seconds;
    }
  } catch {
    /* non-JSON responses are forwarded untouched */
  }
  const refresh = parseRefreshCookie(response.headers.get("set-cookie"));
  if (refresh) captured.refresh = refresh;
  return { response, captured };
}

async function refreshSession(refreshCookie: string | null): Promise<Captured | null> {
  if (!refreshCookie) return null;
  // One page load fans out into several parallel API calls, and each of them would otherwise
  // spend the same single-use refresh token. The API tolerates that for a minute; not minting
  // the duplicates in the first place is what keeps a session from churning rows per request.
  const inFlight = refreshes.get(refreshCookie);
  if (inFlight) return inFlight;
  const attempt = (async () => {
    const { response, captured } = await callApi("POST", "/api/v1/auth/refresh", { refreshCookie });
    return response.ok ? captured : null;
  })().finally(() => refreshes.delete(refreshCookie));
  refreshes.set(refreshCookie, attempt);
  return attempt;
}

function applyCookies(response: Response, captured: Captured, options: { clear?: boolean } = {}): Response {
  if (options.clear) {
    response.headers.append("set-cookie", `${ACCESS_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict`);
    response.headers.append("set-cookie", `${REFRESH_COOKIE}=; Path=${REFRESH_COOKIE_PATH}; Max-Age=0; HttpOnly; SameSite=Strict`);
    return response;
  }
  if (captured.accessToken) {
    const maxAge = Math.max(60, captured.expiresIn ?? 900);
    response.headers.append("set-cookie", `${ACCESS_COOKIE}=${captured.accessToken}; Path=/; Max-Age=${maxAge}; HttpOnly; SameSite=Strict`);
  }
  if (captured.refresh) {
    response.headers.append("set-cookie", `${REFRESH_COOKIE}=${captured.refresh}; Path=${REFRESH_COOKIE_PATH}; Max-Age=${REFRESH_TTL_DAYS * 86400}; HttpOnly; SameSite=Strict`);
  }
  return response;
}

async function handle(request: Request, { params }: Params): Promise<Response> {
  const { path } = await params;
  const target = `/api/v1/${path.join("/")}${new URL(request.url).search}`;
  const method = request.method.toUpperCase();
  const isAuthRoute = path[0] === "auth";

  const body = method === "GET" || method === "HEAD" ? null : await request.arrayBuffer();
  const contentType = request.headers.get("content-type");
  const range = request.headers.get("range");
  const jar = await cookies();
  let token = jar.get(ACCESS_COOKIE)?.value ?? null;
  const refreshCookie = jar.get(REFRESH_COOKIE)?.value ?? null;

  // Cookies minted by an internal refresh call must still reach the browser.
  let mintedCookies: Captured = {};
  let attemptedRefresh = false;

  if (!token && !isAuthRoute && refreshCookie) {
    const minted = await refreshSession(refreshCookie);
    if (minted?.accessToken) {
      token = minted.accessToken;
      mintedCookies = minted;
      attemptedRefresh = true;
    }
  }

  let { response, captured } = await callApi(method, target, { body, token, refreshCookie, contentType, range });

  if (response.status === 401 && !isAuthRoute && !attemptedRefresh) {
    const minted = await refreshSession(refreshCookie);
    if (minted?.accessToken) {
      const retry = await callApi(method, target, { body, token: minted.accessToken, refreshCookie, contentType, range });
      response = retry.response;
      captured = retry.captured;
      mintedCookies = minted;
    }
  }

  /**
   * A refusal's sentence is the API's own English, and the reader is the one who has to read it. The
   * proxy is where the browser's traffic meets the API, so this is where the sentence becomes the
   * catalogue's — one place, for every client-side error, and nothing below it changes.
   */
  let outBody: BodyInit | null = response.body;
  const headers = new Headers({
    "content-type": response.headers.get("content-type") ?? "application/json",
    ...byteRangeHeaders(response),
  });
  if (!response.ok && (headers.get("content-type") ?? "").includes("application/json")) {
    const raw = await response.text();
    let payload: unknown = null;
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = null;
    }
    const localised = payload ? await localiseRefusal(payload) : null;
    outBody = localised ? JSON.stringify(localised) : raw;
    // The body changed, so the length the API sent no longer describes it.
    headers.delete("content-length");
  }

  const out = new Response(outBody, {
    status: response.status,
    headers,
  });

  if (path.join("/") === "auth/logout" && response.status === 204) return applyCookies(out, {}, { clear: true });
  if (path.join("/") === "auth/account" && method === "DELETE" && response.ok) return applyCookies(out, {}, { clear: true });
  if (path.join("/") === "auth/refresh" && !response.ok) return applyCookies(out, {}, { clear: true });
  return applyCookies(out, { ...mintedCookies, ...captured });
}

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const DELETE = handle;

export const dynamic = "force-dynamic";
