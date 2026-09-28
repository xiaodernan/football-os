import { NextResponse, type NextRequest } from "next/server";
import createMiddleware from "next-intl/middleware";
import { routing } from "@/i18n/navigation";
import { ACCESS_COOKIE, REFRESH_COOKIE, REFRESH_COOKIE_PATH, REFRESH_PATH, apiBase } from "@/lib/api";

const intlMiddleware = createMiddleware(routing);

const PUBLIC_PATHS = new Set(["/", "/login", "/register", "/healthz"]);
const PROTECTED_PREFIXES = [
  "/my-football",
  "/coach",
  "/training",
  "/career",
  "/challenges",
  "/progress",
  "/history",
  "/settings",
  "/onboarding",
  "/tactics/boards",
  "/video",
];

const SKEW_SECONDS = 60;
const REFRESH_TTL_DAYS = Number(process.env.REFRESH_TOKEN_TTL_DAYS ?? 30);
const IS_SECURE = process.env.NODE_ENV === "production";

type Minted = { accessToken: string; expiresIn: number; refresh?: string };

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

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

function stripLocalePrefix(pathname: string): string {
  const segments = pathname.split("/");
  if (segments.length >= 2 && ["en", "zh", "zh-TW"].includes(segments[1])) {
    return "/" + segments.slice(2).join("/") || "/";
  }
  return pathname;
}

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const intlResponse = intlMiddleware(request);
  if (intlResponse.status === 307 || intlResponse.status === 308) {
    return intlResponse;
  }

  const { pathname, search } = request.nextUrl;
  const strippedPathname = stripLocalePrefix(pathname);

  if (!isProtected(strippedPathname) || PUBLIC_PATHS.has(strippedPathname)) {
    return intlResponse;
  }

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