import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container page" style={{ maxWidth: "560px" }}>
      <div className="stack" style={{ gap: "1rem" }}>
        <span className="eyebrow">Error 404</span>
        <h1 className="h1">This page is not on the pitch</h1>
        <p className="lede">
          We could not find what you were looking for. It may have moved, or the link may be out of
          date. Nothing has been lost — pick a destination below.
        </p>
        <div className="row wrap" style={{ gap: "0.6rem" }}>
          <Link className="btn btn--primary" href="/">
            Back home
          </Link>
          <Link className="btn" href="/my-football">
            My Football
          </Link>
          <Link className="btn btn--ghost" href="/training">
            Training
          </Link>
        </div>
      </div>
    </div>
  );
}
