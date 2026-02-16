// Cognitive framework form logic for quiz generation

const BLOOMS_LEVELS = [
    {number: 1, name: "Remember", color: "#8B5CF6"},
    {number: 2, name: "Understand", color: "#3B82F6"},
    {number: 3, name: "Apply", color: "#10B981"},
    {number: 4, name: "Analyze", color: "#F59E0B"},
    {number: 5, name: "Evaluate", color: "#EF4444"},
    {number: 6, name: "Create", color: "#EC4899"}
];

const DOK_LEVELS = [
    {number: 1, name: "Recall", color: "#3B82F6"},
    {number: 2, name: "Skill/Concept", color: "#10B981"},
    {number: 3, name: "Strategic Thinking", color: "#F59E0B"},
    {number: 4, name: "Extended Thinking", color: "#EF4444"}
];

// Default percentage spreads for each framework (must sum to 100)
const DEFAULT_SPREADS = {
    blooms: [
        {level: 1, pct: 15},  // Remember
        {level: 2, pct: 25},  // Understand
        {level: 3, pct: 25},  // Apply
        {level: 4, pct: 20},  // Analyze
        {level: 5, pct: 10},  // Evaluate
        {level: 6, pct: 5}    // Create
    ],
    dok: [
        {level: 1, pct: 25},  // Recall
        {level: 2, pct: 40},  // Skill/Concept
        {level: 3, pct: 25},  // Strategic Thinking
        {level: 4, pct: 10}   // Extended Thinking
    ]
};

function computeDefaultCounts(framework, total) {
    var spread = DEFAULT_SPREADS[framework];
    if (!spread) return {};
    var counts = {};
    var assigned = 0;
    // First pass: floor of each proportion
    spread.forEach(function(s) {
        var raw = total * s.pct / 100;
        counts[s.level] = Math.floor(raw);
        assigned += counts[s.level];
    });
    // Distribute remainder to levels with largest fractional parts
    var remainder = total - assigned;
    if (remainder > 0) {
        var fractionals = spread.map(function(s) {
            return {level: s.level, frac: (total * s.pct / 100) - Math.floor(total * s.pct / 100)};
        }).sort(function(a, b) { return b.frac - a.frac; });
        for (var i = 0; i < remainder && i < fractionals.length; i++) {
            counts[fractionals[i].level]++;
        }
    }
    return counts;
}

const DIFFICULTY_LABELS = {
    1: "1 - Basic recall",
    2: "2 - Below grade level",
    3: "3 - Grade-level application",
    4: "4 - Challenging analysis",
    5: "5 - Evaluation and synthesis"
};

(function() {
    var radios = document.querySelectorAll('input[name="cognitive_framework_radio"]');
    var hiddenFramework = document.getElementById("cognitive_framework");
    var distGroup = document.getElementById("cognitive-distribution-group");
    var tbody = document.querySelector("#cognitive-table tbody");
    var totalSpan = document.getElementById("cognitive-total");
    var targetSpan = document.getElementById("cognitive-target");
    var validationMsg = document.getElementById("validation-msg");
    var hiddenDistribution = document.getElementById("cognitive_distribution");
    var numQuestionsInput = document.getElementById("num_questions");
    var difficultyInput = document.getElementById("difficulty");
    var difficultyLabel = document.getElementById("difficulty-label");
    var form = document.querySelector("form.form");

    var currentFramework = "";

    // Radio change handler
    radios.forEach(function(radio) {
        radio.addEventListener("change", function() {
            var value = this.value;
            hiddenFramework.value = value;
            currentFramework = value;

            if (value === "") {
                distGroup.style.display = "none";
                hiddenDistribution.value = "";
            } else {
                distGroup.style.display = "";
                var levels = value === "blooms" ? BLOOMS_LEVELS : DOK_LEVELS;
                var total = parseInt(numQuestionsInput.value) || 20;
                var defaults = computeDefaultCounts(value, total);
                buildTable(levels, defaults);
            }
        });
    });

    function buildTable(levels, defaultCounts) {
        tbody.innerHTML = "";

        // Add action buttons row before the table body
        var existingActions = document.getElementById("cognitive-actions");
        if (existingActions) existingActions.remove();
        var actionsDiv = document.createElement("div");
        actionsDiv.id = "cognitive-actions";
        actionsDiv.className = "cognitive-actions";
        var clearBtn = document.createElement("button");
        clearBtn.type = "button";
        clearBtn.className = "btn btn-sm btn-outline";
        clearBtn.textContent = "Clear All";
        clearBtn.addEventListener("click", function() {
            var inputs = document.querySelectorAll(".level-count");
            inputs.forEach(function(input) { input.value = "0"; });
            updateTotal();
        });
        var resetBtn = document.createElement("button");
        resetBtn.type = "button";
        resetBtn.className = "btn btn-sm btn-outline";
        resetBtn.textContent = "Reset Defaults";
        resetBtn.addEventListener("click", function() {
            applyDefaults();
        });
        actionsDiv.appendChild(resetBtn);
        actionsDiv.appendChild(clearBtn);
        var tableEl = document.getElementById("cognitive-table");
        tableEl.parentNode.insertBefore(actionsDiv, tableEl);

        levels.forEach(function(level) {
            var tr = document.createElement("tr");

            // Level cell with colored badge
            var tdLevel = document.createElement("td");
            var badge = document.createElement("span");
            badge.className = "level-badge";
            badge.style.backgroundColor = level.color;
            badge.textContent = level.number + ". " + level.name;
            tdLevel.appendChild(badge);
            tr.appendChild(tdLevel);

            // Count cell
            var tdCount = document.createElement("td");
            var countInput = document.createElement("input");
            countInput.type = "number";
            countInput.className = "level-count";
            countInput.setAttribute("data-level", level.number);
            countInput.min = "0";
            countInput.max = "50";
            countInput.value = (defaultCounts && defaultCounts[level.number]) ? defaultCounts[level.number] : "0";
            countInput.addEventListener("change", updateTotal);
            countInput.addEventListener("input", updateTotal);
            tdCount.appendChild(countInput);
            tr.appendChild(tdCount);

            tbody.appendChild(tr);
        });
        updateTotal();
    }

    function applyDefaults() {
        if (!currentFramework) return;
        var total = parseInt(numQuestionsInput.value) || 20;
        var defaults = computeDefaultCounts(currentFramework, total);
        var inputs = document.querySelectorAll(".level-count");
        inputs.forEach(function(input) {
            var level = parseInt(input.getAttribute("data-level"));
            input.value = defaults[level] || 0;
        });
        updateTotal();
    }

    function updateTotal() {
        var inputs = document.querySelectorAll(".level-count");
        var total = 0;
        inputs.forEach(function(input) {
            total += parseInt(input.value) || 0;
        });
        var target = parseInt(numQuestionsInput.value) || 0;
        totalSpan.textContent = total;
        targetSpan.textContent = target;

        var totalCell = totalSpan.parentElement;
        if (total === target) {
            totalCell.classList.add("valid");
            totalCell.classList.remove("invalid");
            validationMsg.textContent = "";
        } else {
            totalCell.classList.remove("valid");
            totalCell.classList.add("invalid");
            validationMsg.textContent = "Total must equal " + target;
            validationMsg.style.color = "#dc2626";
        }
    }

    // Update target when num_questions changes; re-apply defaults if distribution matches current defaults
    numQuestionsInput.addEventListener("change", function() {
        updateTotal();
        if (currentFramework) {
            // Check if user has customized or if we should auto-update defaults
            var inputs = document.querySelectorAll(".level-count");
            var allZero = true;
            inputs.forEach(function(input) {
                if (parseInt(input.value) !== 0) allZero = false;
            });
            // If all zero (user cleared), re-apply defaults for new total
            if (allZero) applyDefaults();
        }
    });
    numQuestionsInput.addEventListener("input", updateTotal);

    // Difficulty slider
    difficultyInput.addEventListener("input", function() {
        difficultyLabel.textContent = DIFFICULTY_LABELS[parseInt(this.value)] || this.value;
    });

    // Form submit handler — serialize cognitive distribution
    form.addEventListener("submit", function(e) {
        var framework = hiddenFramework.value;

        if (!framework) {
            hiddenDistribution.value = "";
            return;
        }

        // Validate total matches num_questions
        var inputs = document.querySelectorAll(".level-count");
        var total = 0;
        inputs.forEach(function(input) {
            total += parseInt(input.value) || 0;
        });
        var target = parseInt(numQuestionsInput.value) || 0;

        if (total !== target) {
            e.preventDefault();
            validationMsg.textContent = "Total (" + total + ") must equal number of questions (" + target + ")";
            validationMsg.style.color = "#dc2626";
            return;
        }

        // Serialize distribution as JSON — counts only, no per-level types
        var distribution = {};
        inputs.forEach(function(input) {
            var level = input.getAttribute("data-level");
            var count = parseInt(input.value) || 0;
            distribution[level] = {count: count};
        });

        hiddenDistribution.value = JSON.stringify(distribution);
    });
})();
