/**
 * The world scrolls exactly as the browser scrolls.
 *
 * This module used to install an inverted-wheel handler for readers who found the paging direction
 * confusing. That toggle no longer exists: the reported post-release experience was "the page
 * scrolls the wrong way for me everywhere", not "I would like a custom inversion", so inverted
 * scrolling is not a supported mode any more. The only thing left here is a one-line key cleanup
 * script that deletes the legacy `fo_scroll_direction` localStorage key on the very next load, so
 * a browser that once stored `inverted` silently returns to native scrolling without a support
 * ticket and without any scroll interception by this application.
 */

const INLINE_INSTALL = `
(function () {
  try {
    window.localStorage.removeItem('fo_scroll_direction');
  } catch (error) {
    void error;
  }
})();
`;
export { INLINE_INSTALL as SCROLL_DIRECTION_INSTALL_SCRIPT };
