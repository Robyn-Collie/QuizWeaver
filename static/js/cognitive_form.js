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

const QUESTION_TYPES = ["mc", "tf", "fill_in_blank", "short_answer", "matching", "essay"];
const QUESTION_TYPE_LABELS = {
    "mc": "MC", "tf": "T/F", "fill_in_blank": "Fill-in",
    "short_answer": "Short Ans", "matching": "Match", "essay": "Essay"
};

const DIFFICULTY_LABELS = {
    1: "1 - Easy", 2: "2 - Below Average", 3: "3 - Moderate",
    4: "4 - Challenging", 5: "5 - Expert"
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

    // Radio change handler
    radios.forEach(function(radio) {
        radio.addEventListener("change", function() {
            var value = this.value;
            hiddenFramework.value = value;

            if (value === "") {
                distGroup.style.display = "none";
                hiddenDistribution.value = "";
            } else {
                distGroup.style.display = "";
                var levels = value === "blooms" ? BLOOMS_LEVELS : DOK_LEVELS;
                buildTable(levels);
            }
        });
    });

    function buildTable(levels) {
        tbody.innerHTML = "";
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
            countInput.value = "0";
            countInput.addEventListener("change", updateTotal);
            countInput.addEventListener("input", updateTotal);
            tdCount.appendChild(countInput);
            tr.appendChild(tdCount);

            // Question types cell
            var tdTypes = document.createElement("td");
            var typesDiv = document.createElement("div");
            typesDiv.className = "type-checkboxes";
            QUESTION_TYPES.forEach(function(qtype) {
                var lbl = document.createElement("label");
                var cb = document.createElement("input");
                cb.type = "checkbox";
                cb.className = "type-cb";
                cb.setAttribute("data-level", level.number);
                cb.value = qtype;
                if (qtype === "mc") cb.checked = true;
                lbl.appendChild(cb);
                lbl.appendChild(document.createTextNode(" " + QUESTION_TYPE_LABELS[qtype]));
                typesDiv.appendChild(lbl);
            });
            tdTypes.appendChild(typesDiv);
            tr.appendChild(tdTypes);

            tbody.appendChild(tr);
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

    // Update target when num_questions changes
    numQuestionsInput.addEventListener("change", updateTotal);
    numQuestionsInput.addEventListener("input", updateTotal);

    // Difficulty slider
    difficultyInput.addEventListener("input", function() {
        difficultyLabel.textContent = DIFFICULTY_LABELS[parseInt(this.value)] || this.value;
    });

    // Form submit handler
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

        // Serialize distribution as JSON
        var distribution = {};
        inputs.forEach(function(input) {
            var level = input.getAttribute("data-level");
            var count = parseInt(input.value) || 0;
            var types = [];
            var checkboxes = document.querySelectorAll('.type-cb[data-level="' + level + '"]');
            checkboxes.forEach(function(cb) {
                if (cb.checked) types.push(cb.value);
            });
            distribution[level] = {count: count, types: types};
        });

        hiddenDistribution.value = JSON.stringify(distribution);
    });
})();
