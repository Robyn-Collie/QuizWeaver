/**
 * Quiz editing client-side logic for QuizWeaver.
 * All interactions use vanilla fetch() to JSON API endpoints.
 */
(function () {
  "use strict";

  // --- Helpers ---

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function apiCall(url, options) {
    return fetch(url, options).then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    });
  }

  function jsonPut(url, body) {
    return apiCall(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: JSON.stringify(body),
    });
  }

  function jsonPost(url, body) {
    return apiCall(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: JSON.stringify(body),
    });
  }

  function jsonDelete(url) {
    return apiCall(url, { method: "DELETE", headers: { "X-CSRFToken": getCsrfToken() } });
  }

  function renumberQuestions() {
    var cards = document.querySelectorAll(".question-card");
    cards.forEach(function (card, i) {
      var idx = card.querySelector(".q-index");
      if (idx) idx.textContent = i + 1;
    });
    var countEl = document.getElementById("question-count");
    if (countEl) countEl.textContent = cards.length;
  }

  function getQuestionIds() {
    var ids = [];
    document.querySelectorAll(".question-card").forEach(function (card) {
      ids.push(parseInt(card.dataset.questionId, 10));
    });
    return ids;
  }

  // --- Title Editing ---

  var titleDisplay = document.querySelector(".quiz-title-row");
  var titleEdit = document.querySelector(".quiz-title-edit");

  if (titleDisplay && titleEdit) {
    var editBtn = titleDisplay.querySelector(".edit-title-btn");
    var saveBtn = titleEdit.querySelector(".save-title-btn");
    var cancelBtn = titleEdit.querySelector(".cancel-title-btn");
    var titleInput = titleEdit.querySelector(".quiz-title-input");
    var quizId = titleEdit.dataset.quizId;
    var h1 = titleDisplay.querySelector("h1");

    editBtn.addEventListener("click", function () {
      titleDisplay.style.display = "none";
      titleEdit.style.display = "flex";
      titleInput.focus();
      titleInput.select();
    });

    cancelBtn.addEventListener("click", function () {
      titleInput.value = h1.textContent;
      titleEdit.style.display = "none";
      titleDisplay.style.display = "flex";
    });

    function saveTitle() {
      var newTitle = titleInput.value.trim();
      if (!newTitle) return;
      jsonPut("/api/quizzes/" + quizId + "/title", { title: newTitle }).then(
        function (res) {
          if (res.data.ok) {
            h1.textContent = res.data.title;
            titleEdit.style.display = "none";
            titleDisplay.style.display = "flex";
          } else {
            alert(res.data.error || "Failed to update title");
          }
        }
      );
    }

    saveBtn.addEventListener("click", saveTitle);
    titleInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        saveTitle();
      }
      if (e.key === "Escape") cancelBtn.click();
    });
  }

  // --- Question Card Event Delegation ---

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("button");
    if (!btn) return;
    var card = btn.closest(".question-card");
    if (!card) return;

    var questionId = card.dataset.questionId;
    var quizId = card.dataset.quizId;

    // Edit
    if (btn.classList.contains("btn-edit-question")) {
      card.querySelector(".question-view-mode").style.display = "none";
      card.querySelector(".question-edit-mode").style.display = "block";
      card.querySelector(".question-regen-panel").style.display = "none";
      return;
    }

    // Cancel edit
    if (btn.classList.contains("btn-cancel-edit")) {
      card.querySelector(".question-edit-mode").style.display = "none";
      card.querySelector(".question-view-mode").style.display = "block";
      return;
    }

    // Save question edit
    if (btn.classList.contains("btn-save-question")) {
      var editMode = card.querySelector(".question-edit-mode");
      var text = editMode.querySelector(".edit-question-text").value.trim();
      var points = parseFloat(
        editMode.querySelector(".edit-question-points").value
      );
      var qType = editMode.querySelector(".edit-question-type").value;

      if (!text) {
        alert("Question text cannot be empty");
        return;
      }

      var payload = {
        text: text,
        points: points,
        question_type: qType,
      };

      // Collect options for mc/ma
      if (qType === "mc" || qType === "ma") {
        var options = [];
        editMode
          .querySelectorAll(".edit-option-text")
          .forEach(function (input) {
            options.push(input.value);
          });
        payload.options = options;

        var checkedRadio = editMode.querySelector(
          ".edit-correct-radio:checked"
        );
        if (checkedRadio) {
          payload.correct_index = parseInt(checkedRadio.value, 10);
          payload.correct_answer = options[payload.correct_index] || "";
        }
      }

      // TF correct answer
      if (qType === "tf") {
        var tfRadio = editMode.querySelector(".edit-tf-radio:checked");
        payload.correct_answer = tfRadio ? tfRadio.value : "True";
      }

      btn.disabled = true;
      jsonPut("/api/questions/" + questionId, payload).then(function (res) {
        btn.disabled = false;
        if (res.data.ok) {
          // Reload the page to show updated question
          window.location.reload();
        } else {
          alert(res.data.error || "Failed to save question");
        }
      });
      return;
    }

    // Delete question
    if (btn.classList.contains("btn-delete-question")) {
      if (!confirm("Delete this question? This cannot be undone.")) return;
      btn.disabled = true;
      jsonDelete("/api/questions/" + questionId).then(function (res) {
        if (res.data.ok) {
          card.remove();
          renumberQuestions();
        } else {
          btn.disabled = false;
          alert(res.data.error || "Failed to delete question");
        }
      });
      return;
    }

    // Move up
    if (btn.classList.contains("btn-move-up")) {
      var prev = card.previousElementSibling;
      if (prev && prev.classList.contains("question-card")) {
        card.parentNode.insertBefore(card, prev);
        renumberQuestions();
        jsonPut("/api/quizzes/" + quizId + "/reorder", {
          question_ids: getQuestionIds(),
        });
      }
      return;
    }

    // Move down
    if (btn.classList.contains("btn-move-down")) {
      var next = card.nextElementSibling;
      if (next && next.classList.contains("question-card")) {
        card.parentNode.insertBefore(next, card);
        renumberQuestions();
        jsonPut("/api/quizzes/" + quizId + "/reorder", {
          question_ids: getQuestionIds(),
        });
      }
      return;
    }

    // Upload image button -> trigger file input
    if (btn.classList.contains("btn-upload-image")) {
      card.querySelector(".image-file-input").click();
      return;
    }

    // Remove image
    if (btn.classList.contains("btn-remove-image")) {
      if (!confirm("Remove this image?")) return;
      jsonDelete("/api/questions/" + questionId + "/image").then(function (
        res
      ) {
        if (res.data.ok) {
          var wrapper = card.querySelector(".question-image-wrapper");
          if (wrapper) wrapper.remove();
        }
      });
      return;
    }

    // Clear suggested image description
    if (btn.classList.contains("btn-clear-image-desc")) {
      jsonDelete("/api/questions/" + questionId + "/image-description").then(
        function (res) {
          if (res.data.ok) {
            var placeholder = card.querySelector(".image-placeholder");
            if (placeholder) placeholder.remove();
          }
        }
      );
      return;
    }

    // Regen button -> show panel
    if (btn.classList.contains("btn-regen-question")) {
      card.querySelector(".question-view-mode").style.display = "none";
      card.querySelector(".question-edit-mode").style.display = "none";
      card.querySelector(".question-regen-panel").style.display = "block";
      return;
    }

    // Cancel regen
    if (btn.classList.contains("btn-regen-cancel")) {
      card.querySelector(".question-regen-panel").style.display = "none";
      card.querySelector(".question-view-mode").style.display = "block";
      return;
    }

    // Submit regen
    if (btn.classList.contains("btn-regen-submit")) {
      var notes = card.querySelector(".regen-notes").value.trim();
      card.classList.add("regenerating");
      if (window.QWLoading) {
        window.QWLoading.setBtnLoading(btn, "Regenerating...");
      } else {
        btn.disabled = true;
        btn.textContent = "Regenerating...";
      }
      jsonPost("/api/questions/" + questionId + "/regenerate", {
        teacher_notes: notes,
      }).then(function (res) {
        card.classList.remove("regenerating");
        if (window.QWLoading) {
          window.QWLoading.resetBtn(btn);
        } else {
          btn.disabled = false;
          btn.textContent = "Regenerate";
        }
        if (res.data.ok) {
          window.location.reload();
        } else {
          alert(res.data.error || "Regeneration failed");
        }
      });
      return;
    }

    // Add option
    if (btn.classList.contains("btn-add-option")) {
      var list = card.querySelector(".edit-options-list");
      var idx = list.querySelectorAll(".edit-option-row").length;
      var row = document.createElement("div");
      row.className = "edit-option-row";
      row.innerHTML =
        '<input type="radio" name="correct_' +
        questionId +
        '" class="edit-correct-radio" value="' +
        idx +
        '">' +
        '<input type="text" class="edit-option-text" value="" placeholder="New option">' +
        '<button class="btn btn-sm btn-outline btn-remove-option" title="Remove option">x</button>';
      list.appendChild(row);
      return;
    }

    // Remove option
    if (btn.classList.contains("btn-remove-option")) {
      btn.closest(".edit-option-row").remove();
      // Re-index radio values
      card
        .querySelectorAll(".edit-option-row")
        .forEach(function (row, i) {
          row.querySelector(".edit-correct-radio").value = i;
        });
      return;
    }
  });

  // --- File upload handler ---

  document.addEventListener("change", function (e) {
    if (!e.target.classList.contains("image-file-input")) return;
    var fileInput = e.target;
    var card = fileInput.closest(".question-card");
    var questionId = card.dataset.questionId;
    var file = fileInput.files[0];
    if (!file) return;

    var formData = new FormData();
    formData.append("image", file);

    fetch("/api/questions/" + questionId + "/image", {
      method: "POST",
      headers: { "X-CSRFToken": getCsrfToken() },
      body: formData,
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.ok) {
          window.location.reload();
        } else {
          alert(data.error || "Image upload failed");
        }
      });

    // Reset so same file can be re-selected
    fileInput.value = "";
  });

  // --- Type change toggles options/tf sections ---

  document.addEventListener("change", function (e) {
    if (!e.target.classList.contains("edit-question-type")) return;
    var card = e.target.closest(".question-card");
    var val = e.target.value;
    var optSec = card.querySelector(".edit-options-section");
    var tfSec = card.querySelector(".edit-tf-section");

    if (val === "mc" || val === "ma") {
      optSec.style.display = "block";
      tfSec.style.display = "none";
    } else if (val === "tf") {
      optSec.style.display = "none";
      tfSec.style.display = "block";
    } else {
      optSec.style.display = "none";
      tfSec.style.display = "none";
    }
  });

  // --- Question Bank Toggle ---

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".btn-bank-toggle");
    if (!btn) return;

    var card = btn.closest("[data-question-id]");
    if (!card) return;
    var qId = card.getAttribute("data-question-id");
    var isSaved = btn.getAttribute("data-saved") === "true";
    var endpoint = isSaved
      ? "/api/question-bank/remove"
      : "/api/question-bank/add";

    btn.disabled = true;
    jsonPost(endpoint, { question_id: parseInt(qId, 10) }).then(function (res) {
      btn.disabled = false;
      if (res.data.ok) {
        if (isSaved) {
          btn.setAttribute("data-saved", "false");
          btn.textContent = "Bank";
          btn.classList.remove("btn-secondary");
          btn.classList.add("btn-outline");
          btn.title = "Save to Bank";
        } else {
          btn.setAttribute("data-saved", "true");
          btn.textContent = "Banked";
          btn.classList.remove("btn-outline");
          btn.classList.add("btn-secondary");
          btn.title = "Remove from Bank";
        }
      } else {
        alert("Error: " + (res.data.error || "Unknown"));
      }
    });
  });
})();
