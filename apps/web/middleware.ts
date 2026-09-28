/**
 * Route protection and silent session refresh (ADR-003).
 *
 * Server components read the access token straight from the cookie jar, so a page rendered
 * after the 15-minute token expires would bounce the user to the login screen even though a
 * 30-day refresh cookie is still valid. Middleware is the only tier that can mint cookies
 * before rendering, so the rotation happens here; browser traffic is refreshed by the
 * /api/v1 proxy instead.
 */

import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE, REFRESH_COOKIE_PATH, REFRESH_PATH, apiBase } from "@/lib/api";

const PUBLIC_PATHS = new Set(["/", "/login", "/register", "/healthz"]);
const PROTECTED_PREFIXES = [
  "/my-football",
  "/coach",
  "/training",
  // A season is an account's fiction about a generated club, so it is read only by its owner.
  "/career",
  // A live challenge is a season too — the catalogue is public through the API, but the page that
  // starts a run and lists this account's verdicts sits behind the same wall.
  "/challenges",
  "/progress",
  "/history",
  "/settings",
  "/onboarding",
  // A user's own boards are theirs; `/tactics` and `/tactics/{slug}` stay public, and a shared
  // board is reached through `/tactics/shared/{token}` precisely so it does NOT hit this wall.
  "/tactics/boards",
  // Uploads are the most identifying files the platform can hold: no public read of a clip,
  // a frame or a report, and no sitemap or robots allowance either.
  "/video",
];

/** Re-authenticate slightly early so the token cannot expire mid-render. */
const SKEW_SECONDS = 60;
const REFRESH_TTL_DAYS = Number(process.env.REFRESH_TOKEN_TTL_DAYS ?? 30);
const IS_SECURE = process.env.NODE_ENV === "production";

type Minted = { accessToken: string; expiresIn: number; refresh?: string };

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/** Access tokens are HS256 JWTs; only the payload's expiry is needed here, never the signature. */
function tokenIsFresh(token: string | null | undefined): boolean {
  const payload = token?.split(".")[1];
  if (!payload) return false;
  const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
  try {
    const decoded = JSON.parse(atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4))) as { exp?: unknown };
    return typeof decoded.exp === "number" && decoded.exp > Math.floor(Date.now() / 1000) + SKEW_SECONDS;
  } catch {
    return false;
  }
}

function refreshCookieFrom(setCookieHeader: string | null): string | undefined {
  const pair = new RegExp(`${REFRESH_COOKIE}=([^;]+)`).exec(setCookieHeader ?? "");
  return pair?.[1];
}

async function refreshSession(refreshToken: string): Promise<Minted | null> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${REFRESH_PATH}`, {
      method: "POST",
      headers: { cookie: `${REFRESH_COOKIE}=${refreshToken}`, accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    return null;
  }
  if (!response.ok) return null;
  try {
    const payload = (await response.json()) as { access_token?: string; expires_in_seconds?: number };
    if (!payload.access_token) return null;
    return {
      accessToken: payload.access_token,
      expiresIn: payload.expires_in_seconds ?? 900,
      refresh: refreshCookieFrom(response.headers.get("set-cookie")),
    };
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { pathname, search } = request.nextUrl;
  if (!isProtected(pathname) || PUBLIC_PATHS.has(pathname)) return NextResponse.next();

  const storedAccess = request.cookies.get(ACCESS_COOKIE)?.value ?? null;
  const storedRefresh = request.cookies.get(REFRESH_COOKIE)?.value ?? null;

  let token = tokenIsFresh(storedAccess) ? storedAccess : null;
  let minted: Minted | null = null;
  if (!token && storedRefresh) {
    minted = await refreshSession(storedRefresh);
    token = minted?.accessToken ?? null;
  }

  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    if (storedAccess || storedRefresh) loginUrl.searchParams.set("expired", "1");
    const redirect = NextResponse.redirect(loginUrl);
    redirect.cookies.set(ACCESS_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0, secure: IS_SECURE });
    return redirect;
  }

  const refreshValue = minted?.refresh ?? storedRefresh;
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("cookie", refreshValue ? `${ACCESS_COOKIE}=${token}; ${REFRESH_COOKIE}=${refreshValue}` : `${ACCESS_COOKIE}=${token}`);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  if (minted) {
    response.cookies.set(ACCESS_COOKIE, minted.accessToken, {
      httpOnly: true,
      sameSite: "strict",
      path: "/",
      maxAge: Math.max(60, minted.expiresIn),
      secure: IS_SECURE,
    });
    if (minted.refresh) {
      response.cookies.set(REFRESH_COOKIE, minted.refresh, {
        httpOnly: true,
        sameSite: "strict",
        path: REFRESH_COOKIE_PATH,
        maxAge: REFRESH_TTL_DAYS * 86400,
        secure: IS_SECURE,
      });
    }
  }
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|apple-touch-icon.png).*)"],
};
