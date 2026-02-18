/**
 * Interactive drag-and-drop for matching and ordering questions.
 *
 * Uses native HTML5 Drag and Drop API -- no external libraries required.
 * Falls back gracefully to the static display when JavaScript is disabled
 * (the static markup remains in the DOM; the interactive layer is shown
 * via a CSS class toggle).
 *
 * Accessibility:
 *   - Keyboard: Tab to focus items, Enter/Space to pick up, Arrow keys to
 *     move within the list, Enter/Space to drop, Escape to cancel.
 *   - Touch: touchstart/touchmove/touchend for tablet and mobile devices.
 *   - Screen readers: ARIA live region announces current state.
 *
 * Teacher-preview only -- does not modify any data or exports.
 */

(function () {
  "use strict";

  // ── Helpers ──────────────────────────────────────────────────────

  /** Fisher-Yates shuffle (in-place). */
  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = arr[i];
      arr[i] = arr[j];
      arr[j] = tmp;
    }
    return arr;
  }

  /** Remove feedback classes from an element. */
  function clearFeedback(el) {
    el.classList.remove("dnd-correct", "dnd-incorrect");
  }

  /** Escape HTML to prevent XSS when building DOM from data attributes. */
  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  /** Create an ARIA live region for screen reader announcements. */
  function createLiveRegion(container) {
    var live = document.createElement("div");
    live.setAttribute("aria-live", "polite");
    live.setAttribute("aria-atomic", "true");
    live.className = "sr-only dnd-live-region";
    live.style.position = "absolute";
    live.style.width = "1px";
    live.style.height = "1px";
    live.style.overflow = "hidden";
    live.style.clip = "rect(0,0,0,0)";
    container.appendChild(live);
    return live;
  }

  function announce(liveRegion, message) {
    if (liveRegion) {
      liveRegion.textContent = "";
      // Force re-announce by toggling content in next frame
      requestAnimationFrame(function () {
        liveRegion.textContent = message;
      });
    }
  }

  // ── Native Drag and Drop helpers ─────────────────────────────────

  /**
   * Set up native HTML5 drag-and-drop on a sortable list container.
   * Items must have the given itemSelector class.
   */
  function setupNativeDragDrop(listEl, itemSelector, onReorder) {
    var draggedEl = null;

    listEl.addEventListener("dragstart", function (e) {
      var item = e.target.closest(itemSelector);
      if (!item || !listEl.contains(item)) return;
      draggedEl = item;
      item.classList.add("dnd-ghost", "dnd-chosen");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", "");
    });

    listEl.addEventListener("dragend", function (e) {
      if (draggedEl) {
        draggedEl.classList.remove("dnd-ghost", "dnd-chosen");
        draggedEl = null;
      }
      // Remove all drag-over highlights
      var items = listEl.querySelectorAll(itemSelector);
      items.forEach(function (el) {
        el.classList.remove("dnd-drag-over");
      });
    });

    listEl.addEventListener("dragover", function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      var target = e.target.closest(itemSelector);
      if (!target || target === draggedEl || !listEl.contains(target)) return;
      target.classList.add("dnd-drag-over");
    });

    listEl.addEventListener("dragleave", function (e) {
      var target = e.target.closest(itemSelector);
      if (target) {
        target.classList.remove("dnd-drag-over");
      }
    });

    listEl.addEventListener("drop", function (e) {
      e.preventDefault();
      var target = e.target.closest(itemSelector);
      if (!target || !draggedEl || target === draggedEl) return;
      target.classList.remove("dnd-drag-over");

      // Determine whether to insert before or after
      var items = Array.from(listEl.querySelectorAll(itemSelector));
      var dragIdx = items.indexOf(draggedEl);
      var dropIdx = items.indexOf(target);

      if (dragIdx < dropIdx) {
        listEl.insertBefore(draggedEl, target.nextSibling);
      } else {
        listEl.insertBefore(draggedEl, target);
      }

      if (onReorder) onReorder();
    });
  }

  // ── Touch support ────────────────────────────────────────────────

  /**
   * Add touch-based drag for mobile/tablet devices.
   * Works alongside native DnD (which does not fire on touch devices).
   */
  function setupTouchDrag(listEl, itemSelector, onReorder) {
    var touchItem = null;
    var touchClone = null;
    var startY = 0;
    var startX = 0;
    var scrollOffset = 0;

    listEl.addEventListener("touchstart", function (e) {
      var item = e.target.closest(itemSelector);
      if (!item || !listEl.contains(item)) return;
      touchItem = item;
      var touch = e.touches[0];
      startY = touch.clientY;
      startX = touch.clientX;
      scrollOffset = window.pageYOffset;

      // Create a floating clone for visual feedback
      touchClone = item.cloneNode(true);
      touchClone.className = item.className + " dnd-touch-clone";
      touchClone.style.position = "fixed";
      touchClone.style.zIndex = "9999";
      touchClone.style.pointerEvents = "none";
      touchClone.style.opacity = "0.85";
      touchClone.style.width = item.offsetWidth + "px";
      var rect = item.getBoundingClientRect();
      touchClone.style.left = rect.left + "px";
      touchClone.style.top = rect.top + "px";
      document.body.appendChild(touchClone);

      item.classList.add("dnd-ghost");
    }, { passive: true });

    listEl.addEventListener("touchmove", function (e) {
      if (!touchItem || !touchClone) return;
      e.preventDefault();
      var touch = e.touches[0];
      var dy = touch.clientY - startY + (window.pageYOffset - scrollOffset);
      var dx = touch.clientX - startX;

      var rect = touchItem.getBoundingClientRect();
      touchClone.style.top = (rect.top + dy + (window.pageYOffset - scrollOffset)) + "px";
      touchClone.style.left = (rect.left + dx) + "px";

      // Find item under touch point
      touchClone.style.display = "none";
      var elemBelow = document.elementFromPoint(touch.clientX, touch.clientY);
      touchClone.style.display = "";

      // Clear all drag-over highlights
      var items = listEl.querySelectorAll(itemSelector);
      items.forEach(function (el) { el.classList.remove("dnd-drag-over"); });

      if (elemBelow) {
        var target = elemBelow.closest(itemSelector);
        if (target && target !== touchItem && listEl.contains(target)) {
          target.classList.add("dnd-drag-over");
        }
      }
    }, { passive: false });

    listEl.addEventListener("touchend", function (e) {
      if (!touchItem) return;

      // Find drop target from last touch position
      if (touchClone) {
        touchClone.style.display = "none";
        var lastTouch = e.changedTouches[0];
        var elemBelow = document.elementFromPoint(lastTouch.clientX, lastTouch.clientY);
        touchClone.style.display = "";

        if (elemBelow) {
          var target = elemBelow.closest(itemSelector);
          if (target && target !== touchItem && listEl.contains(target)) {
            var items = Array.from(listEl.querySelectorAll(itemSelector));
            var dragIdx = items.indexOf(touchItem);
            var dropIdx = items.indexOf(target);
            if (dragIdx < dropIdx) {
              listEl.insertBefore(touchItem, target.nextSibling);
            } else {
              listEl.insertBefore(touchItem, target);
            }
            if (onReorder) onReorder();
          }
        }

        document.body.removeChild(touchClone);
        touchClone = null;
      }

      touchItem.classList.remove("dnd-ghost");
      // Clear all drag-over highlights
      var allItems = listEl.querySelectorAll(itemSelector);
      allItems.forEach(function (el) { el.classList.remove("dnd-drag-over"); });
      touchItem = null;
    }, { passive: true });
  }

  // ── Keyboard support ─────────────────────────────────────────────

  /**
   * Add keyboard-based reordering for accessibility.
   * Tab to focus, Enter/Space to pick up, Arrow keys to move, Enter/Space to drop,
   * Escape to cancel.
   */
  function setupKeyboardDrag(listEl, itemSelector, liveRegion, onReorder) {
    var pickedUp = null;

    listEl.addEventListener("keydown", function (e) {
      var item = e.target.closest(itemSelector);
      if (!item || !listEl.contains(item)) return;

      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (!pickedUp) {
          // Pick up the item
          pickedUp = item;
          item.classList.add("dnd-chosen");
          item.setAttribute("aria-grabbed", "true");
          announce(liveRegion, "Picked up. Use arrow keys to move, Enter to drop, Escape to cancel.");
        } else if (pickedUp === item) {
          // Drop the item in current position
          pickedUp.classList.remove("dnd-chosen");
          pickedUp.removeAttribute("aria-grabbed");
          announce(liveRegion, "Dropped.");
          pickedUp = null;
          if (onReorder) onReorder();
        }
        return;
      }

      if (e.key === "Escape" && pickedUp) {
        e.preventDefault();
        pickedUp.classList.remove("dnd-chosen");
        pickedUp.removeAttribute("aria-grabbed");
        announce(liveRegion, "Cancelled.");
        pickedUp = null;
        return;
      }

      if ((e.key === "ArrowUp" || e.key === "ArrowDown") && pickedUp) {
        e.preventDefault();
        var items = Array.from(listEl.querySelectorAll(itemSelector));
        var idx = items.indexOf(pickedUp);

        if (e.key === "ArrowUp" && idx > 0) {
          listEl.insertBefore(pickedUp, items[idx - 1]);
          pickedUp.focus();
          announce(liveRegion, "Moved up to position " + idx + " of " + items.length + ".");
        } else if (e.key === "ArrowDown" && idx < items.length - 1) {
          listEl.insertBefore(pickedUp, items[idx + 1].nextSibling);
          pickedUp.focus();
          announce(liveRegion, "Moved down to position " + (idx + 2) + " of " + items.length + ".");
        }
      }
    });
  }

  // ── Matching questions ──────────────────────────────────────────

  function initMatchingInteractive(container) {
    var dataAttr = container.getAttribute("data-matches");
    if (!dataAttr) return;

    var matches;
    try {
      matches = JSON.parse(dataAttr);
    } catch (e) {
      return;
    }
    if (!matches || !matches.length) return;

    // Build the interactive DOM
    var wrapper = document.createElement("div");
    wrapper.className = "dnd-matching-wrapper matching-container";

    var termsCol = document.createElement("div");
    termsCol.className = "dnd-terms-col";

    var defsCol = document.createElement("div");
    defsCol.className = "dnd-defs-col";
    defsCol.setAttribute("role", "list");
    defsCol.setAttribute("aria-label", "Definitions. Reorder to match the terms on the left.");

    // ARIA live region for announcements
    var liveRegion = createLiveRegion(container);

    // Populate terms (fixed order)
    matches.forEach(function (m, idx) {
      var termEl = document.createElement("div");
      termEl.className = "dnd-term matching-term";
      termEl.setAttribute("data-id", String(idx));
      termEl.textContent = m.term;
      termsCol.appendChild(termEl);
    });

    // Populate definitions (shuffled)
    var defIndices = matches.map(function (_, i) { return i; });
    shuffle(defIndices);

    defIndices.forEach(function (idx) {
      var defEl = document.createElement("div");
      defEl.className = "dnd-def matching-dropzone";
      defEl.setAttribute("data-id", String(idx));
      defEl.setAttribute("draggable", "true");
      defEl.setAttribute("role", "listitem");
      defEl.setAttribute("tabindex", "0");
      defEl.setAttribute("aria-label", matches[idx].definition);
      defEl.innerHTML =
        '<span class="dnd-drag-handle" aria-hidden="true">&#9776;</span> ' +
        escapeHtml(matches[idx].definition);
      defsCol.appendChild(defEl);
    });

    wrapper.appendChild(termsCol);
    wrapper.appendChild(defsCol);

    // Buttons row
    var btnRow = document.createElement("div");
    btnRow.className = "dnd-btn-row";

    var checkBtn = document.createElement("button");
    checkBtn.className = "btn btn-sm btn-primary dnd-check-btn";
    checkBtn.textContent = "Check Answers";
    checkBtn.type = "button";

    var resetBtn = document.createElement("button");
    resetBtn.className = "btn btn-sm btn-secondary dnd-reset-btn";
    resetBtn.textContent = "Reset";
    resetBtn.type = "button";

    var showBtn = document.createElement("button");
    showBtn.className = "btn btn-sm btn-outline dnd-show-btn";
    showBtn.textContent = "Show Answers";
    showBtn.type = "button";

    btnRow.appendChild(checkBtn);
    btnRow.appendChild(resetBtn);
    btnRow.appendChild(showBtn);

    container.appendChild(wrapper);
    container.appendChild(btnRow);

    // Clear feedback on any reorder
    function onReorder() {
      var defs = defsCol.querySelectorAll(".dnd-def");
      defs.forEach(clearFeedback);
    }

    // Native HTML5 Drag and Drop
    setupNativeDragDrop(defsCol, ".dnd-def", onReorder);

    // Touch support for mobile/tablet
    setupTouchDrag(defsCol, ".dnd-def", onReorder);

    // Keyboard accessibility
    setupKeyboardDrag(defsCol, ".dnd-def", liveRegion, onReorder);

    // Check answers
    checkBtn.addEventListener("click", function () {
      var terms = termsCol.querySelectorAll(".dnd-term");
      var defs = defsCol.querySelectorAll(".dnd-def");
      var correctCount = 0;
      defs.forEach(function (def, i) {
        clearFeedback(def);
        if (
          i < terms.length &&
          def.getAttribute("data-id") === terms[i].getAttribute("data-id")
        ) {
          def.classList.add("dnd-correct");
          correctCount++;
        } else {
          def.classList.add("dnd-incorrect");
        }
      });
      announce(
        liveRegion,
        correctCount + " of " + matches.length + " correct."
      );
    });

    // Reset (re-shuffle)
    resetBtn.addEventListener("click", function () {
      var defs = Array.from(defsCol.querySelectorAll(".dnd-def"));
      defs.forEach(clearFeedback);
      shuffle(defs);
      defs.forEach(function (d) {
        defsCol.appendChild(d);
      });
      announce(liveRegion, "Reset. Definitions have been reshuffled.");
    });

    // Show answers (reorder to match terms)
    showBtn.addEventListener("click", function () {
      var terms = termsCol.querySelectorAll(".dnd-term");
      terms.forEach(function (term) {
        var id = term.getAttribute("data-id");
        var match = defsCol.querySelector('.dnd-def[data-id="' + id + '"]');
        if (match) {
          clearFeedback(match);
          match.classList.add("dnd-correct");
          defsCol.appendChild(match);
        }
      });
      announce(liveRegion, "Showing correct answers.");
    });

    // Show the interactive container
    container.classList.add("dnd-active");
  }

  // ── Ordering questions ──────────────────────────────────────────

  function initOrderingInteractive(container) {
    var dataAttr = container.getAttribute("data-correct-order");
    var itemsAttr = container.getAttribute("data-items");
    if (!dataAttr || !itemsAttr) return;

    var correctOrder, items;
    try {
      correctOrder = JSON.parse(dataAttr);
      items = JSON.parse(itemsAttr);
    } catch (e) {
      return;
    }
    if (!items || !items.length) return;

    // Build interactive DOM
    var listEl = document.createElement("div");
    listEl.className = "dnd-ordering-list";
    listEl.setAttribute("role", "list");
    listEl.setAttribute("aria-label", "Drag items to reorder.");

    // ARIA live region
    var liveRegion = createLiveRegion(container);

    // Shuffled indices
    var indices = items.map(function (_, i) {
      return i;
    });
    shuffle(indices);

    indices.forEach(function (idx) {
      var itemEl = document.createElement("div");
      itemEl.className = "dnd-order-item";
      itemEl.setAttribute("data-idx", String(idx));
      itemEl.setAttribute("draggable", "true");
      itemEl.setAttribute("role", "listitem");
      itemEl.setAttribute("tabindex", "0");
      itemEl.setAttribute("aria-label", items[idx]);
      itemEl.innerHTML =
        '<span class="dnd-drag-handle" aria-hidden="true">&#9776;</span> ' +
        escapeHtml(items[idx]);
      listEl.appendChild(itemEl);
    });

    // Buttons row
    var btnRow = document.createElement("div");
    btnRow.className = "dnd-btn-row";

    var checkBtn = document.createElement("button");
    checkBtn.className = "btn btn-sm btn-primary dnd-check-btn";
    checkBtn.textContent = "Check Order";
    checkBtn.type = "button";

    var resetBtn = document.createElement("button");
    resetBtn.className = "btn btn-sm btn-secondary dnd-reset-btn";
    resetBtn.textContent = "Reset";
    resetBtn.type = "button";

    var showBtn = document.createElement("button");
    showBtn.className = "btn btn-sm btn-outline dnd-show-btn";
    showBtn.textContent = "Show Correct Order";
    showBtn.type = "button";

    btnRow.appendChild(checkBtn);
    btnRow.appendChild(resetBtn);
    btnRow.appendChild(showBtn);

    container.appendChild(listEl);
    container.appendChild(btnRow);

    function onReorder() {
      var orderItems = listEl.querySelectorAll(".dnd-order-item");
      orderItems.forEach(clearFeedback);
    }

    // Native HTML5 Drag and Drop
    setupNativeDragDrop(listEl, ".dnd-order-item", onReorder);

    // Touch support
    setupTouchDrag(listEl, ".dnd-order-item", onReorder);

    // Keyboard accessibility
    setupKeyboardDrag(listEl, ".dnd-order-item", liveRegion, onReorder);

    // Check order
    checkBtn.addEventListener("click", function () {
      var orderItems = listEl.querySelectorAll(".dnd-order-item");
      var correctCount = 0;
      orderItems.forEach(function (el, pos) {
        clearFeedback(el);
        var idx = parseInt(el.getAttribute("data-idx"), 10);
        if (correctOrder[pos] === idx) {
          el.classList.add("dnd-correct");
          correctCount++;
        } else {
          el.classList.add("dnd-incorrect");
        }
      });
      announce(
        liveRegion,
        correctCount + " of " + items.length + " in correct position."
      );
    });

    // Reset
    resetBtn.addEventListener("click", function () {
      var orderItems = Array.from(
        listEl.querySelectorAll(".dnd-order-item")
      );
      orderItems.forEach(clearFeedback);
      shuffle(orderItems);
      orderItems.forEach(function (el) {
        listEl.appendChild(el);
      });
      announce(liveRegion, "Reset. Items have been reshuffled.");
    });

    // Show correct order
    showBtn.addEventListener("click", function () {
      correctOrder.forEach(function (idx) {
        var match = listEl.querySelector(
          '.dnd-order-item[data-idx="' + idx + '"]'
        );
        if (match) {
          clearFeedback(match);
          match.classList.add("dnd-correct");
          listEl.appendChild(match);
        }
      });
      announce(liveRegion, "Showing correct order.");
    });

    container.classList.add("dnd-active");
  }

  // ── Init on DOMContentLoaded ────────────────────────────────────

  document.addEventListener("DOMContentLoaded", function () {
    document
      .querySelectorAll(".matching-interactive")
      .forEach(initMatchingInteractive);
    document
      .querySelectorAll(".ordering-interactive")
      .forEach(initOrderingInteractive);
  });
})();
