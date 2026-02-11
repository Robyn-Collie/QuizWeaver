/**
 * Study Materials JavaScript - QuizWeaver
 * Handles: flip cards, delete confirmation, class->quiz filtering, generate form
 */
(function() {
    'use strict';

    // --- Class -> Quiz dropdown filtering on generate form ---
    var classSelect = document.getElementById('class_id');
    var quizSelect = document.getElementById('quiz_id');

    if (classSelect && quizSelect) {
        classSelect.addEventListener('change', function() {
            var classId = this.value;
            // Clear existing options
            quizSelect.innerHTML = '<option value="">-- None (use topic instead) --</option>';

            if (!classId) return;

            fetch('/api/classes/' + classId + '/quizzes')
                .then(function(response) { return response.json(); })
                .then(function(quizzes) {
                    quizzes.forEach(function(q) {
                        var opt = document.createElement('option');
                        opt.value = q.id;
                        // Build rich label: "Title (#ID) - 20 Qs - Jan 15"
                        var label = q.title;
                        var details = [];
                        if (q.question_count) details.push(q.question_count + ' Qs');
                        if (q.standards && q.standards.length > 0) details.push(q.standards.join(', '));
                        if (q.reading_level) details.push(q.reading_level.replace(/_/g, ' '));
                        if (q.date) details.push(q.date);
                        if (details.length > 0) label += ' (' + details.join(' | ') + ')';
                        opt.textContent = label;
                        quizSelect.appendChild(opt);
                    });
                })
                .catch(function(err) {
                    console.error('Failed to load quizzes:', err);
                });
        });
    }

    // --- Generate form progress overlay ---
    var generateForm = document.getElementById('study-generate-form');
    var overlay = document.getElementById('study-generate-progress');

    if (generateForm && overlay) {
        generateForm.addEventListener('submit', function(e) {
            e.preventDefault();
            overlay.style.display = 'flex';

            // Animate steps
            var steps = ['study-step-0', 'study-step-1', 'study-step-2'];
            var delays = [0, 500, 1500];
            var timers = [];

            function setStep(idx, state) {
                var li = document.getElementById(steps[idx]);
                if (!li) return;
                var icon = li.querySelector('.step-icon');
                icon.className = 'step-icon step-' + state;
                if (state === 'active') li.classList.add('step-active');
                else if (state === 'done') {
                    li.classList.add('step-complete');
                    li.classList.remove('step-active');
                }
            }

            delays.forEach(function(delay, idx) {
                timers.push(setTimeout(function() {
                    for (var i = 0; i < idx; i++) setStep(i, 'done');
                    setStep(idx, 'active');
                }, delay));
            });

            // Submit via fetch
            var formData = new FormData(generateForm);
            fetch(generateForm.action, {
                method: 'POST',
                body: formData,
                redirect: 'follow',
            })
            .then(function(response) {
                timers.forEach(clearTimeout);
                if (response.redirected) {
                    steps.forEach(function(_, idx) { setStep(idx, 'done'); });
                    setTimeout(function() {
                        window.location.href = response.url;
                    }, 500);
                } else {
                    overlay.style.display = 'none';
                    // Reload with error
                    response.text().then(function(html) {
                        document.open();
                        document.write(html);
                        document.close();
                    });
                }
            })
            .catch(function(err) {
                timers.forEach(clearTimeout);
                overlay.style.display = 'none';
                alert('Network error: ' + err.message);
            });
        });
    }

    // --- Delete study set ---
    document.querySelectorAll('.study-delete-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var id = this.getAttribute('data-id');
            if (!confirm('Delete this study set? This cannot be undone.')) return;

            fetch('/api/study-sets/' + id, { method: 'DELETE' })
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    if (data.ok) {
                        // Remove card from DOM
                        var card = document.querySelector('.study-card[data-id="' + id + '"]');
                        if (card) card.remove();
                    } else {
                        alert('Failed to delete: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(function(err) {
                    alert('Network error: ' + err.message);
                });
        });
    });

    // --- Export dropdown toggle ---
    document.querySelectorAll('.export-dropdown-toggle').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            var menu = this.nextElementSibling;
            // Close all other open menus
            document.querySelectorAll('.export-dropdown-menu.open').forEach(function(m) {
                if (m !== menu) m.classList.remove('open');
            });
            menu.classList.toggle('open');
        });
    });

    // Close dropdowns when clicking elsewhere
    document.addEventListener('click', function() {
        document.querySelectorAll('.export-dropdown-menu.open').forEach(function(m) {
            m.classList.remove('open');
        });
    });
})();
