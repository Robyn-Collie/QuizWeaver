/**
 * Interactive drag-and-drop for matching and ordering questions.
 *
 * Uses SortableJS for drag interactions.  Falls back gracefully to the
 * static display when JavaScript is disabled (the static markup remains
 * in the DOM; the interactive layer is shown via a CSS class toggle).
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
    wrapper.className = "dnd-matching-wrapper";

    var termsCol = document.createElement("div");
    termsCol.className = "dnd-terms-col";

    var defsCol = document.createElement("div");
    defsCol.className = "dnd-defs-col";
    defsCol.setAttribute("aria-label", "Drag definitions to reorder");

    // Populate terms (fixed order)
    matches.forEach(function (m, idx) {
      var termEl = document.createElement("div");
      termEl.className = "dnd-term";
      termEl.setAttribute("data-id", String(idx));
      termEl.textContent = m.term;
      termsCol.appendChild(termEl);
    });

    // Populate definitions (shuffled)
    var defIndices = matches.map(function (_, i) { return i; });
    shuffle(defIndices);

    defIndices.forEach(function (idx) {
      var defEl = document.createElement("div");
      defEl.className = "dnd-def";
      defEl.setAttribute("data-id", String(idx));
      defEl.setAttribute("role", "listitem");
      defEl.setAttribute("tabindex", "0");
      defEl.innerHTML = '<span class="dnd-drag-handle" aria-hidden="true">&#9776;</span> ' +
        matches[idx].definition;
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

    // Initialize SortableJS
    if (typeof Sortable !== "undefined") {
      Sortable.create(defsCol, {
        animation: 150,
        ghostClass: "dnd-ghost",
        chosenClass: "dnd-chosen",
        handle: ".dnd-drag-handle",
        onEnd: function () {
          // Clear feedback on reorder
          var defs = defsCol.querySelectorAll(".dnd-def");
          defs.forEach(clearFeedback);
        },
      });
    }

    // Check answers
    checkBtn.addEventListener("click", function () {
      var terms = termsCol.querySelectorAll(".dnd-term");
      var defs = defsCol.querySelectorAll(".dnd-def");
      defs.forEach(function (def, i) {
        clearFeedback(def);
        if (i < terms.length && def.getAttribute("data-id") === terms[i].getAttribute("data-id")) {
          def.classList.add("dnd-correct");
        } else {
          def.classList.add("dnd-incorrect");
        }
      });
    });

    // Reset (re-shuffle)
    resetBtn.addEventListener("click", function () {
      var defs = Array.from(defsCol.querySelectorAll(".dnd-def"));
      defs.forEach(clearFeedback);
      shuffle(defs);
      defs.forEach(function (d) { defsCol.appendChild(d); });
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
    listEl.setAttribute("aria-label", "Drag items to reorder");

    // Shuffled indices
    var indices = items.map(function (_, i) { return i; });
    shuffle(indices);

    indices.forEach(function (idx) {
      var itemEl = document.createElement("div");
      itemEl.className = "dnd-order-item";
      itemEl.setAttribute("data-idx", String(idx));
      itemEl.setAttribute("role", "listitem");
      itemEl.setAttribute("tabindex", "0");
      itemEl.innerHTML = '<span class="dnd-drag-handle" aria-hidden="true">&#9776;</span> ' +
        items[idx];
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

    // Initialize SortableJS
    if (typeof Sortable !== "undefined") {
      Sortable.create(listEl, {
        animation: 150,
        ghostClass: "dnd-ghost",
        chosenClass: "dnd-chosen",
        handle: ".dnd-drag-handle",
        onEnd: function () {
          var orderItems = listEl.querySelectorAll(".dnd-order-item");
          orderItems.forEach(clearFeedback);
        },
      });
    }

    // Check order
    checkBtn.addEventListener("click", function () {
      var orderItems = listEl.querySelectorAll(".dnd-order-item");
      orderItems.forEach(function (el, pos) {
        clearFeedback(el);
        var idx = parseInt(el.getAttribute("data-idx"), 10);
        if (correctOrder[pos] === idx) {
          el.classList.add("dnd-correct");
        } else {
          el.classList.add("dnd-incorrect");
        }
      });
    });

    // Reset
    resetBtn.addEventListener("click", function () {
      var orderItems = Array.from(listEl.querySelectorAll(".dnd-order-item"));
      orderItems.forEach(clearFeedback);
      shuffle(orderItems);
      orderItems.forEach(function (el) { listEl.appendChild(el); });
    });

    // Show correct order
    showBtn.addEventListener("click", function () {
      correctOrder.forEach(function (idx) {
        var match = listEl.querySelector('.dnd-order-item[data-idx="' + idx + '"]');
        if (match) {
          clearFeedback(match);
          match.classList.add("dnd-correct");
          listEl.appendChild(match);
        }
      });
    });

    container.classList.add("dnd-active");
  }

  // ── Init on DOMContentLoaded ────────────────────────────────────

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".matching-interactive").forEach(initMatchingInteractive);
    document.querySelectorAll(".ordering-interactive").forEach(initOrderingInteractive);
  });
})();
