/**
 * A refusal's message, in the reader's language.
 *
 * The API answers a refusal with a **code** and a **sentence**: `detail.code` is the stable handle —
 * the operator's, the log's, the page's — and `detail.message` is the API's own English. The web tier
 * shows that sentence: `errorMessage()` in `lib/api.ts` returns `error.message`. So a Chinese reader was
 * told *"The current password is incorrect"* in English, on a page whose every other sentence came from
 * the Chinese catalogue.
 *
 * The fix is the arc's method applied to the other side of the wire: **the catalogue holds one key per
 * refusal code, and the English value is the API's message verbatim**, so the English rendering is
 * byte-identical and this is a translation rather than a copy change. The code needs no translation at
 * all — it is already the locale-neutral handle the page prints beside the sentence.
 *
 * It is read at the **two** places an API answer reaches the web tier, and nowhere else:
 *
 *  * the cookie proxy (`app/api/v1/[...path]/route.ts`), for the browser's traffic;
 *  * `serverFetch` (`lib/server.ts`), for the server's own reads.
 *
 * Nothing else changes. `errorMessage()` and the forty-two call sites that pass it a fallback stay
 * exactly as they are, and the fallback they pass is still what a reader sees when the API sends no
 * message at all.
 */
import { getTranslations } from "next-intl/server";

import enMessages from "@/messages/en.json";

/**
 * The refusal codes the catalogue carries a sentence for.
 *
 * The set is read from the English file because the code set is the same in all three: a code the
 * catalogue does not name has no sentence in any language, and the API's own words are the right answer
 * for it.
 */
const KNOWN = new Set(Object.keys((enMessages as { errors?: Record<string, string> }).errors ?? {}));

/** The refusal's code and message, wherever in the body they sit. */
function readRefusal(body: unknown): { code: string; message: string | undefined } | null {
  if (!body || typeof body !== "object") return null;
  const outer = body as Record<string, unknown>;
  // The API's own shape is `{detail: {code, message}}`; a refusal that arrives flat — `{code, message,
  // fee, remaining}` — carries its figures beside the sentence, and the figures have to survive.
  const detail = "detail" in outer ? outer.detail : outer;
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return null;
  const record = detail as Record<string, unknown>;
  if (typeof record.code !== "string") return null;
  return { code: record.code, message: typeof record.message === "string" ? record.message : undefined };
}

/** The same body, with the refusal's message replaced and everything beside it untouched. */
function withMessage(body: unknown, message: string): unknown {
  if (!body || typeof body !== "object") return body;
  const outer = body as Record<string, unknown>;
  if (!("detail" in outer)) return { ...outer, message };
  return { ...outer, detail: { ...(outer.detail as Record<string, unknown>), message } };
}

/**
 * The body's refusal sentence, in the reader's language.
 *
 * A body the catalogue has no sentence for is returned **untouched**: the API's own words are better
 * than a guess, and the codes whose message names a value the request supplied — "philosophy must be
 * one of [...]" — are named in `qa-api-refusals.mjs` as the ones the catalogue cannot reproduce.
 */
export async function localiseRefusal(body: unknown): Promise<unknown> {
  const refusal = readRefusal(body);
  if (!refusal || !KNOWN.has(refusal.code)) return body;
  const te = await getTranslations("errors");
  return withMessage(body, te(refusal.code));
}
