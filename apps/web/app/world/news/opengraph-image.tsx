/** The index doors' share card — news. */

import { ImageResponse } from "next/og";

import { INDEX_CARD_SIZE, indexCard } from "../_og/index-card";

export const alt = "FOOTBALL OS";
export const size = { ...INDEX_CARD_SIZE };
export const contentType = "image/png";
export const dynamic = "force-static";

export default function NewsOpenGraphImage() {
  return new ImageResponse(indexCard({ word: "NEWS" }), { ...size });
}
