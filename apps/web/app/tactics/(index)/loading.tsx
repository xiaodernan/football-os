import { RouteSkeleton } from "@/components/RouteSkeleton";

/**
 * `/tactics` — the catalogue's first paint.
 *
 * This skeleton used to live at `app/tactics/loading.tsx` and therefore covered every route below the
 * segment, including the five that answer `notFound()`. A loading boundary flushes the shell before the
 * page runs, so those routes painted the not-found screen under a **200**. It now covers only the route
 * it was drawn for; the leaves that can 404 have no boundary above them.
 */
export default function Loading() {
  return <RouteSkeleton cards={4} rows={6} />;
}
