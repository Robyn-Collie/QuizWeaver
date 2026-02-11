/**
 * QuizWeaver - Reusable Loading Overlay
 *
 * Provides a simple loading overlay for forms that submit to the server
 * and wait for a redirect (variant generation, rubric generation, reteach, etc.)
 *
 * Usage: Add data-loading-form attribute to a <form> element.
 * Optional attributes:
 *   data-loading-title     - Overlay title (default: "Generating...")
 *   data-loading-message   - Subtitle text (default: "This may take a few seconds.")
 *   data-loading-btn       - Selector for the submit button (default: finds first [type=submit])
 */
(function () {
  "use strict";

  /**
   * Create and show a loading overlay on the page.
   * Returns the overlay element for later removal.
   */
  function createOverlay(title, message) {
    var overlay = document.createElement("div");
    overlay.className = "loading-overlay";
    overlay.id = "qw-loading-overlay";
    overlay.innerHTML =
      '<div class="loading-card">' +
      "<h2>" +
      escapeHtml(title) +
      "</h2>" +
      '<div class="loading-spinner"></div>' +
      "<p>" +
      escapeHtml(message) +
      "</p>" +
      "</div>";
    document.body.appendChild(overlay);
    return overlay;
  }

  function removeOverlay() {
    var overlay = document.getElementById("qw-loading-overlay");
    if (overlay) overlay.remove();
  }

  function escapeHtml(text) {
    var el = document.createElement("span");
    el.textContent = text;
    return el.innerHTML;
  }

  /**
   * Set a button to loading state with inline spinner.
   */
  function setBtnLoading(btn, loadingText) {
    if (!btn) return;
    btn.disabled = true;
    btn.classList.add("btn-loading");
    btn._originalText = btn.textContent;
    btn.innerHTML =
      '<span class="btn-spinner"></span>' + escapeHtml(loadingText);
  }

  /**
   * Restore a button from loading state.
   */
  function resetBtn(btn) {
    if (!btn) return;
    btn.disabled = false;
    btn.classList.remove("btn-loading");
    if (btn._originalText) {
      btn.textContent = btn._originalText;
    }
  }

  /**
   * Attach loading overlay behavior to all forms with data-loading-form.
   */
  function init() {
    var forms = document.querySelectorAll("[data-loading-form]");
    forms.forEach(function (form) {
      form.addEventListener("submit", function (e) {
        var title = form.getAttribute("data-loading-title") || "Generating...";
        var message =
          form.getAttribute("data-loading-message") ||
          "This may take a few seconds.";

        // Find submit button
        var btnSelector = form.getAttribute("data-loading-btn");
        var btn = btnSelector
          ? form.querySelector(btnSelector)
          : form.querySelector('[type="submit"], button.btn-primary');

        // Show overlay and set button loading state
        createOverlay(title, message);
        setBtnLoading(
          btn,
          form.getAttribute("data-loading-btn-text") || "Generating..."
        );

        // Let the form submit normally (no e.preventDefault).
        // The page will navigate away on success.
        // If the server returns the same page (error), the overlay will be gone
        // because the page reloads.
      });
    });
  }

  // Expose for programmatic use (e.g., question regeneration inline spinner)
  window.QWLoading = {
    createOverlay: createOverlay,
    removeOverlay: removeOverlay,
    setBtnLoading: setBtnLoading,
    resetBtn: resetBtn,
  };

  // Auto-init on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
