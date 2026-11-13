import { RouteSkeleton } from "@/components/RouteSkeleton";

// `/tactics/boards` — a list of boards, four to a row on a wide screen.
export default function Loading() {
  return <RouteSkeleton cards={4} rows={5} />;
}
