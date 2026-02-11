/**
 * Keyboard Shortcuts - QuizWeaver
 * Two-key "chord" shortcuts (g+d, n+q, etc.) and single-key shortcuts.
 */
(function() {
    'use strict';

    var pendingPrefix = null;
    var prefixTimeout = null;
    var CHORD_DELAY = 1000; // ms to wait for second key

    var SHORTCUTS = [
        { keys: '?', label: 'Show keyboard shortcuts', action: toggleHelpModal },
        { keys: 'g d', label: 'Go to Dashboard', action: function() { nav('/dashboard'); } },
        { keys: 'g q', label: 'Go to Quizzes', action: function() { nav('/quizzes'); } },
        { keys: 'g s', label: 'Go to Study Materials', action: function() { nav('/study'); } },
        { keys: 'g c', label: 'Go to Classes', action: function() { nav('/classes'); } },
        { keys: 'g b', label: 'Go to Question Bank', action: function() { nav('/question-bank'); } },
        { keys: 'g h', label: 'Go to Help', action: function() { nav('/help'); } },
        { keys: 'g $', label: 'Go to Costs', action: function() { nav('/costs'); } },
        { keys: 'd', label: 'Toggle dark mode', action: function() { if (typeof toggleTheme === 'function') toggleTheme(); } },
        { keys: 'n q', label: 'New Quiz', action: function() { nav('/quizzes/generate'); } },
        { keys: 'n s', label: 'New Study Material', action: function() { nav('/study/generate'); } },
        { keys: 'Escape', label: 'Close modal/dialog', action: closeHelpModal },
    ];

    function nav(url) {
        window.location.href = url;
    }

    function isInputFocused() {
        var el = document.activeElement;
        if (!el) return false;
        var tag = el.tagName.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
        if (el.isContentEditable) return true;
        return false;
    }

    // --- Help Modal ---

    var modal = null;

    function createHelpModal() {
        modal = document.createElement('div');
        modal.id = 'shortcuts-modal';
        modal.className = 'shortcuts-modal';
        modal.style.display = 'none';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-label', 'Keyboard shortcuts');

        var html = '<div class="shortcuts-modal-content">';
        html += '<div class="shortcuts-modal-header">';
        html += '<h2>Keyboard Shortcuts</h2>';
        html += '<button class="shortcuts-close" aria-label="Close">&times;</button>';
        html += '</div>';
        html += '<div class="shortcuts-modal-body">';

        // Group shortcuts
        var navShortcuts = SHORTCUTS.filter(function(s) { return s.keys.charAt(0) === 'g'; });
        var createShortcuts = SHORTCUTS.filter(function(s) { return s.keys.charAt(0) === 'n'; });
        var otherShortcuts = SHORTCUTS.filter(function(s) { return s.keys.charAt(0) !== 'g' && s.keys.charAt(0) !== 'n'; });

        html += '<h3>Navigation</h3>';
        html += '<table class="shortcuts-table">';
        navShortcuts.forEach(function(s) {
            html += '<tr><td class="shortcut-keys">' + formatKeys(s.keys) + '</td><td>' + s.label + '</td></tr>';
        });
        html += '</table>';

        html += '<h3>Create</h3>';
        html += '<table class="shortcuts-table">';
        createShortcuts.forEach(function(s) {
            html += '<tr><td class="shortcut-keys">' + formatKeys(s.keys) + '</td><td>' + s.label + '</td></tr>';
        });
        html += '</table>';

        html += '<h3>Other</h3>';
        html += '<table class="shortcuts-table">';
        otherShortcuts.forEach(function(s) {
            html += '<tr><td class="shortcut-keys">' + formatKeys(s.keys) + '</td><td>' + s.label + '</td></tr>';
        });
        html += '</table>';

        html += '</div></div>';
        modal.innerHTML = html;
        document.body.appendChild(modal);

        // Close button
        modal.querySelector('.shortcuts-close').addEventListener('click', closeHelpModal);
        // Click outside to close
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeHelpModal();
        });
    }

    function formatKeys(keys) {
        return keys.split(' ').map(function(k) {
            return '<kbd>' + k + '</kbd>';
        }).join(' then ');
    }

    function toggleHelpModal() {
        if (!modal) createHelpModal();
        if (modal.style.display === 'none') {
            modal.style.display = 'flex';
            localStorage.setItem('qw-shortcuts-seen', 'true');
            var hint = document.getElementById('shortcutsHint');
            if (hint) hint.classList.add('seen');
        } else {
            modal.style.display = 'none';
        }
    }

    function closeHelpModal() {
        if (modal) modal.style.display = 'none';
    }

    // --- Keydown Handler ---

    document.addEventListener('keydown', function(e) {
        // Always allow Escape
        if (e.key === 'Escape') {
            if (modal && modal.style.display !== 'none') {
                closeHelpModal();
                return;
            }
            pendingPrefix = null;
            return;
        }

        // Don't trigger shortcuts when typing in inputs
        if (isInputFocused()) return;

        // Don't trigger on modifier keys
        if (e.ctrlKey || e.metaKey || e.altKey) return;

        var key = e.key;

        // Check for chord completion
        if (pendingPrefix) {
            clearTimeout(prefixTimeout);
            var chord = pendingPrefix + ' ' + key;
            pendingPrefix = null;

            var matched = SHORTCUTS.filter(function(s) { return s.keys === chord; });
            if (matched.length > 0) {
                e.preventDefault();
                matched[0].action();
                return;
            }
            // No chord match - fall through to single key
        }

        // Check if this key starts a chord
        var isPrefix = SHORTCUTS.some(function(s) {
            var parts = s.keys.split(' ');
            return parts.length === 2 && parts[0] === key;
        });

        if (isPrefix) {
            pendingPrefix = key;
            prefixTimeout = setTimeout(function() {
                pendingPrefix = null;
            }, CHORD_DELAY);
            return;
        }

        // Single-key shortcuts
        var matched = SHORTCUTS.filter(function(s) { return s.keys === key && s.keys.indexOf(' ') === -1; });
        if (matched.length > 0) {
            e.preventDefault();
            matched[0].action();
        }
    });

})();
