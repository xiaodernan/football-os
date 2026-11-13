import { RouteSkeleton } from "@/components/RouteSkeleton";

// `/tactics/compare` — two systems side by side, so two bands rather than four cards.
export default function Loading() {
  return <RouteSkeleton cards={2} rows={8} />;
}
