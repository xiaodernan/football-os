/**
 * The world reverse-scrolls only when the reader opts in.
 *
 * A `<script>` that runs before hydration installs the wheel handler. The handler intercepts
 * `wheel` events on `window` in the capture phase, inverts `deltaY`, and re-scrolls the
 * document manually. The script returns early when localStorage is blocked so a private
 * window still sees whatever the document paints natively.
 */
export const SCROLL_DIRECTION = "fo_scroll_direction" as const;
export type ScrollDirection = "natural" | "inverted";

const INLINE_INSTALL = `
(function () {
  try {
    var stored = window.localStorage.getItem(${JSON.stringify(SCROLL_DIRECTION)});
    if (stored !== 'inverted') return;
    var clamp = function (value) {
      var max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      return Math.max(0, Math.min(max, value));
    };
    window.addEventListener('wheel', function (event) {
      var target = document.elementFromPoint(event.clientX, event.clientY);
      if (target && target.closest && target.closest('[data-scroll-skip]')) return;
      if (event.ctrlKey || event.metaKey) return;
      event.preventDefault();
      var next = clamp(window.scrollY - event.deltaY);
      window.scrollTo({ top: next, left: 0, behavior: 'auto' });
    }, { passive: false, capture: true });
  } catch (error) {
    void error;
  }
})();
`;
export { INLINE_INSTALL as SCROLL_DIRECTION_INSTALL_SCRIPT };

/** A fresh read of the stored value; used by the toggle UI. */
export function readScrollDirection(): ScrollDirection {
  if (typeof window === "undefined") return "natural";
  try {
    return window.localStorage.getItem(SCROLL_DIRECTION) === "inverted" ? "inverted" : "natural";
  } catch {
    return "natural";
  }
}
