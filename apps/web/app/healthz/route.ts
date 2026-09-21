/**
 * Public system-status endpoint for this web tier.
 * `/` and `/settings` render the same facts server-side; this route exposes them to
 * monitors and to the landing page's client-side refresh without leaking the upstream
 * base URL. Nothing here is synthesised: every field is a passthrough from FastAPI, and
 * `status` only reports whether those two upstream calls answered.
 */

import { NextResponse } from "next/server";

import { serverFetch } from "@/lib/server";
import type { CapabilitiesResponse, HealthResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

type HealthPayload = {
  status: "ok" | "degraded";
  checked_at: string;
  api: HealthResponse | null;
  capabilities: CapabilitiesResponse | null;
  message: string | null;
};

export async function GET(): Promise<NextResponse<HealthPayload>> {
  const [healthResult, capabilitiesResult] = await Promise.all([
    serverFetch<HealthResponse>("/healthz"),
    serverFetch<CapabilitiesResponse>("/capabilities"),
  ]);

  const payload: HealthPayload = {
    status: healthResult.ok ? "ok" : "degraded",
    checked_at: new Date().toISOString(),
    api: healthResult.ok ? healthResult.data : null,
    capabilities: capabilitiesResult.ok ? capabilitiesResult.data : null,
    message: healthResult.ok ? null : healthResult.error.message,
  };

  return NextResponse.json(payload, { status: healthResult.ok ? 200 : 503 });
}
