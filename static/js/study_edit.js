/**
 * Study Material Inline Editing - QuizWeaver
 * Handles: edit cards inline, delete cards, reorder with up/down buttons
 */
(function() {
    'use strict';

    var pageEl = document.getElementById('study-detail-page');
    if (!pageEl) return;
    var studySetId = pageEl.getAttribute('data-study-set-id');
    if (!studySetId) return;

    // Detect if we're inside a vocabulary table
    var vocabTable = document.getElementById('vocab-table');

    // --- Helpers for vocab table rows ---
    // In vocab mode, each card has two <tr>s: data row + edit row
    // Both share the same data-card-id

    function getEditEl(cardEl) {
        if (vocabTable) {
            // For vocab: edit row is the next sibling <tr> with same data-card-id
            var cardId = cardEl.getAttribute('data-card-id');
            return vocabTable.querySelector('tr.vocab-edit-row[data-card-id="' + cardId + '"]');
        }
        return cardEl.querySelector('.card-edit-mode');
    }

    function getViewEl(cardEl) {
        if (vocabTable) return cardEl; // The <tr> itself is the view
        return cardEl.querySelector('.card-view-mode');
    }

    // --- Inline Edit ---

    function startEdit(cardEl) {
        if (cardEl.classList.contains('editing')) return;
        cardEl.classList.add('editing');

        var frontEl = cardEl.querySelector('.card-front-text');
        var backEl = cardEl.querySelector('.card-back-text');
        var editEl = getEditEl(cardEl);

        if (!editEl) return;

        var frontInput = editEl.querySelector('.edit-front');
        var backInput = editEl.querySelector('.edit-back');

        if (frontInput && frontEl) frontInput.value = frontEl.textContent.trim();
        if (backInput && backEl) backInput.value = backEl.textContent.trim();

        if (vocabTable) {
            editEl.style.display = ''; // show the edit <tr>
        } else {
            var viewEl = getViewEl(cardEl);
            if (viewEl) viewEl.style.display = 'none';
            editEl.style.display = 'block';
        }
        if (frontInput) frontInput.focus();
    }

    function cancelEdit(cardEl) {
        cardEl.classList.remove('editing');
        var editEl = getEditEl(cardEl);
        if (vocabTable) {
            if (editEl) editEl.style.display = 'none';
        } else {
            var viewEl = getViewEl(cardEl);
            if (viewEl) viewEl.style.display = '';
            if (editEl) editEl.style.display = 'none';
        }
    }

    function saveEdit(cardEl) {
        var cardId = cardEl.getAttribute('data-card-id');
        var editEl = getEditEl(cardEl);
        if (!editEl) return;

        var frontInput = editEl.querySelector('.edit-front');
        var backInput = editEl.querySelector('.edit-back');

        var payload = {};
        if (frontInput) payload.front = frontInput.value;
        if (backInput) payload.back = backInput.value;

        var saveBtn = editEl.querySelector('.edit-save-btn');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
        }

        fetch('/api/study-cards/' + cardId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.ok) {
                var frontEl = cardEl.querySelector('.card-front-text');
                var backEl = cardEl.querySelector('.card-back-text');
                if (frontEl && payload.front !== undefined) frontEl.textContent = payload.front;
                if (backEl && payload.back !== undefined) backEl.textContent = payload.back;
                cancelEdit(cardEl);
            } else {
                alert('Save failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(function(err) {
            alert('Network error: ' + err.message);
        })
        .finally(function() {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Save';
            }
        });
    }

    // --- Delete Card ---

    function deleteCard(cardEl) {
        var cardId = cardEl.getAttribute('data-card-id');
        if (!confirm('Delete this item? This cannot be undone.')) return;

        fetch('/api/study-cards/' + cardId, { method: 'DELETE' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.ok) {
                // For vocab, also remove the edit row
                var editRow = vocabTable
                    ? vocabTable.querySelector('tr.vocab-edit-row[data-card-id="' + cardId + '"]')
                    : null;

                cardEl.style.transition = 'opacity 0.3s';
                cardEl.style.opacity = '0';
                if (editRow) {
                    editRow.style.transition = 'opacity 0.3s';
                    editRow.style.opacity = '0';
                }
                setTimeout(function() {
                    cardEl.remove();
                    if (editRow) editRow.remove();
                    renumberCards();
                }, 300);
            } else {
                alert('Delete failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(function(err) {
            alert('Network error: ' + err.message);
        });
    }

    // --- Reorder Cards ---

    function moveCard(cardEl, direction) {
        if (vocabTable) {
            moveTableRow(cardEl, direction);
        } else {
            moveDomElement(cardEl, direction);
        }
    }

    function moveDomElement(cardEl, direction) {
        var container = cardEl.parentElement;
        var cards = Array.from(container.querySelectorAll(':scope > [data-card-id]'));
        var idx = cards.indexOf(cardEl);

        if (direction === 'up' && idx > 0) {
            container.insertBefore(cardEl, cards[idx - 1]);
        } else if (direction === 'down' && idx < cards.length - 1) {
            container.insertBefore(cards[idx + 1], cardEl);
        } else {
            return;
        }

        renumberCards();
        saveOrder();
    }

    function moveTableRow(cardEl, direction) {
        var tbody = cardEl.parentElement;
        var cardId = cardEl.getAttribute('data-card-id');
        var editRow = tbody.querySelector('tr.vocab-edit-row[data-card-id="' + cardId + '"]');

        // Get only data rows (not edit rows)
        var dataRows = Array.from(tbody.querySelectorAll('tr[data-card-id]:not(.vocab-edit-row)'));
        var idx = dataRows.indexOf(cardEl);

        if (direction === 'up' && idx > 0) {
            var prevRow = dataRows[idx - 1];
            tbody.insertBefore(cardEl, prevRow);
            tbody.insertBefore(editRow, prevRow); // edit row follows data row... actually before
            // Re-insert: data row, then edit row after it
            tbody.insertBefore(editRow, cardEl.nextSibling);
        } else if (direction === 'down' && idx < dataRows.length - 1) {
            var nextRow = dataRows[idx + 1];
            var nextEditRow = tbody.querySelector('tr.vocab-edit-row[data-card-id="' + nextRow.getAttribute('data-card-id') + '"]');
            // Insert after the next pair
            var anchor = nextEditRow ? nextEditRow.nextSibling : nextRow.nextSibling;
            tbody.insertBefore(cardEl, anchor);
            tbody.insertBefore(editRow, cardEl.nextSibling);
        } else {
            return;
        }

        renumberCards();
        saveOrder();
    }

    function saveOrder() {
        var cardIds = [];
        var selector = vocabTable
            ? '#vocab-table tbody tr[data-card-id]:not(.vocab-edit-row)'
            : '.card-container > [data-card-id]';
        document.querySelectorAll(selector).forEach(function(el) {
            cardIds.push(parseInt(el.getAttribute('data-card-id'), 10));
        });
        // Deduplicate (safety)
        var seen = {};
        cardIds = cardIds.filter(function(id) {
            if (seen[id]) return false;
            seen[id] = true;
            return true;
        });

        fetch('/api/study-sets/' + studySetId + '/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_ids: cardIds }),
        })
        .catch(function(err) {
            console.error('Reorder failed:', err);
        });
    }

    function renumberCards() {
        var selector = vocabTable
            ? '#vocab-table tbody tr[data-card-id]:not(.vocab-edit-row)'
            : '.card-container [data-card-id]';
        var count = 0;
        document.querySelectorAll(selector).forEach(function(el, i) {
            var numEl = el.querySelector('.card-number');
            if (numEl) numEl.textContent = (i + 1);
            count = i + 1;
        });
        var countEl = document.getElementById('card-count');
        if (countEl) countEl.textContent = count;
    }

    // --- Event Delegation ---

    document.addEventListener('click', function(e) {
        var btn = e.target.closest('button');
        if (!btn) return;

        // For vocab edit rows, the cardEl is the data row
        var cardEl = btn.closest('[data-card-id]');
        if (!cardEl) return;

        // If we clicked in a vocab edit row, find the actual data row
        if (cardEl.classList.contains('vocab-edit-row')) {
            var cid = cardEl.getAttribute('data-card-id');
            cardEl = document.querySelector('#vocab-table tbody tr[data-card-id="' + cid + '"]:not(.vocab-edit-row)');
            if (!cardEl) return;
        }

        if (btn.classList.contains('card-edit-btn')) {
            e.preventDefault();
            startEdit(cardEl);
        } else if (btn.classList.contains('edit-save-btn')) {
            e.preventDefault();
            saveEdit(cardEl);
        } else if (btn.classList.contains('edit-cancel-btn')) {
            e.preventDefault();
            cancelEdit(cardEl);
        } else if (btn.classList.contains('card-delete-btn')) {
            e.preventDefault();
            deleteCard(cardEl);
        } else if (btn.classList.contains('card-move-up')) {
            e.preventDefault();
            moveCard(cardEl, 'up');
        } else if (btn.classList.contains('card-move-down')) {
            e.preventDefault();
            moveCard(cardEl, 'down');
        }
    });

    // Ctrl+Enter to save, Escape to cancel
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            var editMode = e.target.closest('.card-edit-mode');
            if (!editMode) editMode = e.target.closest('.vocab-edit-row');
            if (editMode) {
                var cid = editMode.getAttribute('data-card-id');
                var cardEl = vocabTable
                    ? document.querySelector('#vocab-table tbody tr[data-card-id="' + cid + '"]:not(.vocab-edit-row)')
                    : editMode.closest('[data-card-id]');
                if (cardEl) saveEdit(cardEl);
            }
        }
        if (e.key === 'Escape') {
            var editMode = e.target.closest('.card-edit-mode');
            if (!editMode) editMode = e.target.closest('.vocab-edit-row');
            if (editMode) {
                var cid = editMode.getAttribute('data-card-id');
                var cardEl = vocabTable
                    ? document.querySelector('#vocab-table tbody tr[data-card-id="' + cid + '"]:not(.vocab-edit-row)')
                    : editMode.closest('[data-card-id]');
                if (cardEl) cancelEdit(cardEl);
            }
        }
    });

})();
