// Rubric delete confirmation
(function() {
    var deleteBtn = document.getElementById('delete-rubric-btn');
    if (!deleteBtn) return;

    deleteBtn.addEventListener('click', function() {
        var rubricId = this.getAttribute('data-rubric-id');
        if (!confirm('Are you sure you want to delete this rubric?')) return;

        fetch('/api/rubrics/' + rubricId, {method: 'DELETE'})
            .then(function(resp) { return resp.json(); })
            .then(function(data) {
                if (data.ok) {
                    // Find the quiz link and go back to quiz, or go to quizzes list
                    var quizLink = document.querySelector('.quiz-info a[href^="/quizzes/"]');
                    if (quizLink) {
                        window.location.href = quizLink.getAttribute('href');
                    } else {
                        window.location.href = '/quizzes';
                    }
                } else {
                    alert('Delete failed: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function(err) {
                alert('Delete failed: ' + err.message);
            });
    });
})();
