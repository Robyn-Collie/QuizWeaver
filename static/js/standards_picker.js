/**
 * Standards Picker - Autocomplete search with tag chips.
 *
 * Usage:
 *   initStandardsPicker({
 *     inputId: 'standards',           // The visible text input ID
 *     hiddenInputId: 'standards_val', // Hidden input that stores comma-separated codes
 *     chipsContainerId: 'standards_chips',
 *     apiUrl: '/api/standards/search',
 *     initialValues: ['SOL 7.1', 'SOL 7.2']  // optional pre-selected codes
 *   });
 */
function initStandardsPicker(opts) {
    var input = document.getElementById(opts.inputId);
    var hiddenInput = document.getElementById(opts.hiddenInputId);
    var chipsContainer = document.getElementById(opts.chipsContainerId);

    if (!input || !hiddenInput || !chipsContainer) return;

    var apiUrl = opts.apiUrl || '/api/standards/search';
    var selected = [];
    var debounceTimer = null;
    var highlightIndex = -1;
    var dropdownResults = [];

    // Create dropdown element
    var dropdown = document.createElement('div');
    dropdown.className = 'picker-dropdown';
    input.parentNode.appendChild(dropdown);

    // Load initial values (handle both array and JSON string)
    var initVals = opts.initialValues || [];
    if (typeof initVals === 'string') {
        try {
            initVals = JSON.parse(initVals);
        } catch (e) {
            // Comma-separated string fallback
            initVals = initVals.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
        }
    }
    if (!Array.isArray(initVals)) {
        initVals = [];
    }
    if (initVals.length > 0) {
        initVals.forEach(function(code) {
            if (code && code.trim()) {
                addChip(code.trim());
            }
        });
    }

    // --- Event handlers ---
    input.addEventListener('input', function() {
        var q = input.value.trim();
        clearTimeout(debounceTimer);
        if (q.length < 2) {
            closeDropdown();
            return;
        }
        debounceTimer = setTimeout(function() {
            fetchResults(q);
        }, 300);
    });

    input.addEventListener('keydown', function(e) {
        if (!dropdown.classList.contains('open')) {
            // Backspace with empty input removes last chip
            if (e.key === 'Backspace' && input.value === '' && selected.length > 0) {
                removeChip(selected[selected.length - 1]);
            }
            return;
        }

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            highlightIndex = Math.min(highlightIndex + 1, dropdownResults.length - 1);
            updateHighlight();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            highlightIndex = Math.max(highlightIndex - 1, 0);
            updateHighlight();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (highlightIndex >= 0 && highlightIndex < dropdownResults.length) {
                selectResult(dropdownResults[highlightIndex]);
            }
        } else if (e.key === 'Escape') {
            closeDropdown();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!input.parentNode.contains(e.target)) {
            closeDropdown();
        }
    });

    // --- Functions ---
    function fetchResults(q) {
        var url = apiUrl + '?q=' + encodeURIComponent(q);
        fetch(url)
            .then(function(res) { return res.json(); })
            .then(function(data) {
                // Filter out already-selected standards
                dropdownResults = (data.results || []).filter(function(item) {
                    return selected.indexOf(item.code) === -1;
                });
                highlightIndex = -1;
                renderDropdown();
            })
            .catch(function() {
                dropdownResults = [];
                renderDropdown();
            });
    }

    function renderDropdown() {
        dropdown.innerHTML = '';
        if (dropdownResults.length === 0) {
            if (input.value.trim().length >= 2) {
                var noResults = document.createElement('div');
                noResults.className = 'picker-no-results';
                noResults.textContent = 'No matching standards found. You can type a custom code and press Enter.';
                dropdown.appendChild(noResults);
            }
            dropdown.classList.add('open');
            return;
        }
        dropdownResults.forEach(function(item, idx) {
            var option = document.createElement('div');
            option.className = 'picker-option' + (idx === highlightIndex ? ' highlighted' : '');
            option.innerHTML = '<span class="picker-option-code">' + escapeHtml(item.code) + '</span>' +
                '<span class="picker-option-desc">' + escapeHtml(item.description) + '</span>';
            option.addEventListener('click', function() {
                selectResult(item);
            });
            dropdown.appendChild(option);
        });
        dropdown.classList.add('open');
    }

    function updateHighlight() {
        var options = dropdown.querySelectorAll('.picker-option');
        options.forEach(function(opt, idx) {
            opt.classList.toggle('highlighted', idx === highlightIndex);
        });
        // Scroll into view
        if (options[highlightIndex]) {
            options[highlightIndex].scrollIntoView({ block: 'nearest' });
        }
    }

    function selectResult(item) {
        addChip(item.code);
        input.value = '';
        closeDropdown();
        input.focus();
    }

    function addChip(code) {
        if (selected.indexOf(code) !== -1) return;
        selected.push(code);
        syncHiddenInput();

        var chip = document.createElement('span');
        chip.className = 'standards-chip';
        chip.setAttribute('data-code', code);
        chip.innerHTML = escapeHtml(code) +
            '<button type="button" class="chip-remove" aria-label="Remove ' + escapeHtml(code) + '">&times;</button>';
        chip.querySelector('.chip-remove').addEventListener('click', function() {
            removeChip(code);
        });
        chipsContainer.appendChild(chip);
    }

    function removeChip(code) {
        selected = selected.filter(function(c) { return c !== code; });
        syncHiddenInput();
        var chip = chipsContainer.querySelector('[data-code="' + CSS.escape(code) + '"]');
        if (chip) chip.remove();
    }

    function syncHiddenInput() {
        hiddenInput.value = selected.join(', ');
    }

    function closeDropdown() {
        dropdown.classList.remove('open');
        dropdown.innerHTML = '';
        highlightIndex = -1;
        dropdownResults = [];
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Allow typing custom standards on Enter when dropdown is closed
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !dropdown.classList.contains('open')) {
            e.preventDefault();
            var val = input.value.trim();
            if (val) {
                addChip(val);
                input.value = '';
            }
        }
    });
}
