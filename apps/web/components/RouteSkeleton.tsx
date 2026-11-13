/**
 * The shape of a page before its data arrives.
 *
 * Every `loading.tsx` in this app drew its own copy of this markup, which meant the skeleton drifted
 * from the page it stood in for — the tactics skeleton promised four panels and a six-row table on a
 * route that had three. One component, one shape, and the leaves say only how many rows they expect.
 *
 * There is no copy in here on purpose: a skeleton that carries a sentence needs a catalogue key, and a
 * skeleton that is translated can shift language while the page it replaces arrives in another.
 */
export function RouteSkeleton({ cards = 4, rows = 6 }: { cards?: number; rows?: number }) {
  return (
    <div className="page container route-loading" aria-busy="true" aria-live="polite">
      <div className="stack">
        <div className="stack-sm">
          <span className="skeleton" style={{ maxWidth: 110, height: "0.7rem" }} />
          <span className="skeleton" style={{ maxWidth: 320, height: "2.1rem" }} />
          <span className="skeleton" style={{ maxWidth: 460 }} />
        </div>
        <div className="grid grid-4">
          {Array.from({ length: cards }).map((_, index) => (
            <div className="panel" key={index}>
              <div className="panel__body stack-sm">
                <span className="skeleton" style={{ maxWidth: 88, height: "0.65rem" }} />
                <span className="skeleton" style={{ maxWidth: 140, height: "1.6rem" }} />
              </div>
            </div>
          ))}
        </div>
        <div className="panel">
          <div className="panel__body stack-sm">
            {Array.from({ length: rows }).map((_, index) => (
              <span className="skeleton" key={index} style={{ height: "2.4rem" }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
