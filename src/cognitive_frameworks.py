"""
Cognitive framework constants and helpers for quiz generation.

Defines Bloom's Taxonomy levels, Webb's Depth of Knowledge (DOK) levels,
supported question types, and validation utilities for distributing
questions across cognitive levels.
"""

FRAMEWORK_BLOOMS = "blooms"
FRAMEWORK_DOK = "dok"

BLOOMS_LEVELS = [
    {"number": 1, "name": "Remember", "description": "Recall facts and basic concepts", "color": "#8B5CF6"},
    {"number": 2, "name": "Understand", "description": "Explain ideas or concepts", "color": "#3B82F6"},
    {"number": 3, "name": "Apply", "description": "Use information in new situations", "color": "#10B981"},
    {"number": 4, "name": "Analyze", "description": "Draw connections among ideas", "color": "#F59E0B"},
    {"number": 5, "name": "Evaluate", "description": "Justify a stand or decision", "color": "#EF4444"},
    {"number": 6, "name": "Create", "description": "Produce new or original work", "color": "#EC4899"},
]

DOK_LEVELS = [
    {"number": 1, "name": "Recall", "description": "Basic recall of facts, terms, or procedures", "color": "#3B82F6"},
    {
        "number": 2,
        "name": "Skill/Concept",
        "description": "Use of information, conceptual knowledge",
        "color": "#10B981",
    },
    {
        "number": 3,
        "name": "Strategic Thinking",
        "description": "Reasoning, planning, using evidence",
        "color": "#F59E0B",
    },
    {
        "number": 4,
        "name": "Extended Thinking",
        "description": "Complex reasoning over time, real-world applications",
        "color": "#EF4444",
    },
]

QUESTION_TYPES = ["mc", "tf", "fill_in_blank", "short_answer", "matching", "essay"]


def get_framework(name):
    """Return the level list for a named framework, or None if unknown."""
    if name == FRAMEWORK_BLOOMS:
        return BLOOMS_LEVELS
    if name == FRAMEWORK_DOK:
        return DOK_LEVELS
    return None


def validate_distribution(framework, distribution, total):
    """Validate a question distribution against a cognitive framework.

    Args:
        framework: str ("blooms" or "dok")
        distribution: dict mapping level number (int or str) to count (int)
        total: expected total question count

    Returns:
        (True, "") if valid, (False, "error message") if not.
    """
    levels = get_framework(framework)
    if levels is None:
        return (False, f"Unknown framework: {framework}")

    valid_numbers = {lvl["number"] for lvl in levels}

    # Normalise string keys to int
    normalised = {}
    for key, count in distribution.items():
        try:
            num = int(key)
        except (ValueError, TypeError):
            return (False, f"Invalid level key: {key}")
        normalised[num] = count

    for num in normalised:
        if num not in valid_numbers:
            return (False, f"Invalid level number {num} for framework '{framework}'")

    # Normalise dict-style entries ({"count": N, "types": [...]}) to plain int
    for num in list(normalised.keys()):
        val = normalised[num]
        if isinstance(val, dict):
            normalised[num] = val.get("count", 0)

    for num, count in normalised.items():
        if count < 0:
            return (False, f"Negative count ({count}) for level {num}")

    actual_total = sum(normalised.values())
    if actual_total != total:
        return (False, f"Distribution sums to {actual_total}, expected {total}")

    return (True, "")
