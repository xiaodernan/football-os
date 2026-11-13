/**
 * The route's first paint: the shell, the rhythm and the number of panels the page is about to
 * fill — no copy, so nothing here needs a catalogue key and nothing shifts language.
 *
 * Next renders this while the server component resolves, which on these four routes means a
 * database read over the generated world or the tactical catalogue. A blank page during that read
 * is the one moment this product looks broken; a skeleton in the same shapes is the same page,
 * still loading.
 */
export default function Loading() {
  return (
    <div className="page container route-loading">
      <div className="stack">
        <div className="stack-sm">
          <span className="skeleton" style={{ maxWidth: 110, height: "0.7rem" }} />
          <span className="skeleton" style={{ maxWidth: 320, height: "2.1rem" }} />
          <span className="skeleton" style={{ maxWidth: 460 }} />
        </div>
        <div className="grid grid-4">
          {Array.from({ length: 4 }).map((_, index) => (
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
            {Array.from({ length: 6 }).map((_, index) => (
              <span className="skeleton" key={index} style={{ height: "2.4rem" }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
