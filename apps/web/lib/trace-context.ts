/**
 * W3C Trace Context across the cookie proxy.
 *
 * The proxy is the only place browser traffic meets the API, and it builds its outgoing headers
 * from an allowlist — so a trace an upstream caller had already started (`traceparent` from a load
 * balancer, an edge worker, a gateway) stopped here and the API began a second trace for the same
 * request. The API continues an incoming `traceparent`; this module is the other end of that
 * contract: a valid context is forwarded unchanged, an invalid one is not propagated (the spec
 * forbids it, and forwarding one would tell the API to continue a trace that never existed), and
 * `tracestate` travels only beside a valid `traceparent`.
 *
 * The tier still starts no trace of its own: with no incoming header nothing is sent, and this
 * module never mints ids. Instrumenting the proxy's own span is a separate decision.
 */

type HeaderReader = { get(name: string): string | null };

const VERSION = /^[0-9a-f]{2}$/;
const TRACE_ID = /^[0-9a-f]{32}$/;
const PARENT_ID = /^[0-9a-f]{16}$/;
const FLAGS = /^[0-9a-f]{2}$/;

export function traceContextHeaders(incoming: HeaderReader): Record<string, string> {
  const traceparent = incoming.get("traceparent");
  if (!traceparent) return {};

  // version 00 is exactly four fields; a higher version may append its own, which this tier
  // forwards without interpreting them (the spec's forward-compatibility rule).
  const pieces = traceparent.split("-");
  const [version, traceId, parentId, flags] = pieces;
  if (!VERSION.test(version) || !TRACE_ID.test(traceId) || !PARENT_ID.test(parentId) || !FLAGS.test(flags)) return {};
  if (version === "ff") return {};
  if (version === "00" && pieces.length !== 4) return {};
  if (/^0+$/.test(traceId) || /^0+$/.test(parentId)) return {};

  const headers: Record<string, string> = { traceparent };
  const tracestate = incoming.get("tracestate");
  if (tracestate) headers.tracestate = tracestate;
  return headers;
}
