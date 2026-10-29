import { NextResponse, type NextRequest } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE, REFRESH_COOKIE_PATH, REFRESH_PATH, apiBase } from "@/lib/api";
import { defaultLocale, locales, type Locale } from "@/i18n/request";

/**
 * The locale a request is answered in, decided **without touching the URL**.
 *
 * This file used to run next-intl's own middleware, which rewrites `/world` to `/en/world` internally. That
 * rewrite expects an `app/[locale]/…` tree, and this app has none, so from the moment it landed (`9ba8178`,
 * 2026-09-28) **every route answered 404** — including `/healthz`, `/robots.txt` and `/sitemap.xml`. The
 * messages, the provider and the layout are all kept; only the URL rewriting is gone, so the URLs every page,
 * sitemap and walk script already uses keep working.
 *
 * The choice, in order: the `fo_locale` cookie written below, the browser's `Accept-Language`, then English.
 * A signed-in account's own locale is a column on its row (`users.locale`) and is what `/settings` prints.
 */
const LOCALE_COOKIE = "fo_locale";
// next-intl's own header name, read by `app/layout.tsx` to pick the message bundle.
const LOCALE_HEADER = "x-next-intl-locale";
const LOCALE_TTL_SECONDS = 400 * 86400;

/**
 * The paths that need a token minted *before* they render, because they call the API during the render.
 *
 * This list is deliberately narrower than "everything session-gated": `/club`, `/community`, `/creator` and
 * `/scout` redirect an anonymous visitor themselves, and `/club/rules` is a page a signed-out visitor may read —
 * a prefix here would take that away. Only a surface that needs the cookie forwarded mid-render belongs.
 */
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
  "/notifications",
  "/video",
  // The walk found this list drifting from the pages that gate themselves: a prefix missing here
  // means the middleware never refreshes that surface's expired access token, so a signed-in
  // reader whose 15-minute token died mid-visit was bounced to /login by the page's own
  // currentUser() — /simulation/aggregates was where the walk proved it. Every prefix below is
  // one whose pages gate themselves, in either of the two shapes the census finds: `currentUser()`
  // then redirect on null, or `serverFetch` then redirect on its 401 (/progress, /history, /settings
  // are the second shape, and testing only the first spelling mis-files all three).
  "/agents",
  "/club",
  "/community",
  "/creator",
  "/graph",
  "/portfolio",
  "/scout",
  "/simulate",
  "/simulation",
  "/traces",
];

/**
 * Prefixes under a protected prefix that a signed-out reader must still reach.
 *
 * Matched the way `PROTECTED_PREFIXES` is matched — as a prefix, not a whole pathname — because both share
 * surfaces below sit one dynamic segment deep (`/video/shared/<token>`), where an exact set lookup can never
 * hit. The live read proved it: `/video/shared/e90273…` answered 307 to `/login` in all three locales while
 * `/tactics/shared/<token>` — the same design, under a prefix that was never listed — answered 200.
 *
 * What earns a place here is the property `scripts/qa-middleware-gating.mjs` measures on every run: the page
 * never reads a session and has no path to `/login`, so gating it can only deny a reader what the page was
 * built to hand them. `/club/rules` qualifies; `/club` does not, and its own page redirects a signed-out visitor.
 */
const PUBLIC_EXCEPTIONS = new Set(["/club/rules", "/portfolio/shared", "/scout/shared", "/video/shared"]);

const SKEW_SECONDS = 60;
const REFRESH_TTL_DAYS = Number(process.env.REFRESH_TOKEN_TTL_DAYS ?? 30);
const IS_SECURE = process.env.NODE_ENV === "production";

type Minted = { accessToken: string; expiresIn: number; refresh?: string };

function isProtected(pathname: string): boolean {
  // Prefix semantics, identical to the protected list's, so an exemption actually reaches the segment below it.
  for (const exception of PUBLIC_EXCEPTIONS) {
    if (pathname === exception || pathname.startsWith(`${exception}/`)) return false;
  }
  return PROTECTED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function preferredLocale(request: NextRequest): Locale {
  const stored = request.cookies.get(LOCALE_COOKIE)?.value;
  if (stored && (locales as readonly string[]).includes(stored)) return stored as Locale;
  for (const part of (request.headers.get("accept-language") ?? "").split(",")) {
    const tag = part.split(";")[0]?.trim().toLowerCase() ?? "";
    if (!tag) continue;
    const exact = (locales as readonly string[]).find((locale) => locale.toLowerCase() === tag);
    if (exact) return exact as Locale;
    const base = tag.split("-")[0];
    if (base === "zh") return /-(tw|hk|mo)/u.test(tag) ? "zh-TW" : "zh";
    if (base === "en") return "en";
  }
  return defaultLocale;
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

/** The headers the app renders against: the caller's own, plus the locale this middleware decided. */
function forwardedHeaders(request: NextRequest, locale: Locale): Headers {
  const headers = new Headers(request.headers);
  headers.set(LOCALE_HEADER, locale);
  return headers;
}

function rememberLocale(response: NextResponse, request: NextRequest, locale: Locale): NextResponse {
  if (request.cookies.get(LOCALE_COOKIE)?.value !== locale) {
    response.cookies.set(LOCALE_COOKIE, locale, { sameSite: "lax", path: "/", maxAge: LOCALE_TTL_SECONDS, secure: IS_SECURE });
  }
  return response;
}

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { pathname, search } = request.nextUrl;
  const locale = preferredLocale(request);

  if (!isProtected(pathname)) {
    return rememberLocale(NextResponse.next({ request: { headers: forwardedHeaders(request, locale) } }), request, locale);
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
  const requestHeaders = forwardedHeaders(request, locale);
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
  return rememberLocale(response, request, locale);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|apple-touch-icon.png).*)"],
};
