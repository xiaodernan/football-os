import "./progress.css";

/** Static skeleton for /progress so route transitions do not flash an empty page. */
export default function ProgressLoading() {
  return (
    <div className="page container progress-loading">
      <div className="stack">
        <div className="stack-sm">
          <span className="skeleton" style={{ maxWidth: 120 }} />
          <span className="skeleton" style={{ maxWidth: 260, height: "1.8rem" }} />
          <span className="skeleton" style={{ maxWidth: 380 }} />
        </div>

        <div className="panel">
          <div className="panel__body">
            <div className="pg-hero-grid">
              {Array.from({ length: 5 }).map((_, index) => (
                <span className="skeleton" key={index} style={{ height: "3.4rem" }} />
              ))}
            </div>
            <span className="skeleton" style={{ height: "0.6rem", marginTop: "1.15rem" }} />
          </div>
        </div>

        <div className="grid grid-2">
          <div className="panel">
            <div className="panel__body pg-radar">
              <span className="skeleton skeleton--circle" />
              <span className="skeleton" style={{ width: "100%" }} />
              <span className="skeleton" style={{ width: "100%" }} />
            </div>
          </div>
          <div className="panel">
            <div className="panel__body stack">
              {Array.from({ length: 4 }).map((_, index) => (
                <span className="skeleton" key={index} style={{ height: "2.6rem" }} />
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="panel" key={index}>
              <div className="panel__body stack-sm">
                <span className="skeleton skeleton--tile" style={{ height: "9rem" }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
