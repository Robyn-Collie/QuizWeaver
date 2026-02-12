"""
Deterministic layers for QuizWeaver.

These are RULE-BASED, non-AI systems that provide predictable, auditable
constraints for assessment generation. This follows the AI literacy principle:
deterministic layers handle critical constraints, AI handles creative tasks.

Includes:
- Lexile/reading complexity bands by grade level
- Flesch-Kincaid text complexity estimation (pure math, no AI)
- Assessment blueprint templates for cognitive level distribution
"""

import re
from typing import Dict, List, Optional

# --- Lexile / Reading Complexity Bands ---

LEXILE_BANDS = {
    "2": {"min": 420, "max": 650, "label": "Grade 2"},
    "3": {"min": 520, "max": 820, "label": "Grade 3"},
    "4": {"min": 640, "max": 940, "label": "Grade 4"},
    "5": {"min": 730, "max": 1010, "label": "Grade 5"},
    "6": {"min": 925, "max": 1070, "label": "Grade 6"},
    "7": {"min": 970, "max": 1120, "label": "Grade 7"},
    "8": {"min": 1010, "max": 1185, "label": "Grade 8"},
    "9": {"min": 1050, "max": 1260, "label": "Grade 9"},
    "10": {"min": 1080, "max": 1335, "label": "Grade 10"},
    "11": {"min": 1100, "max": 1385, "label": "Grade 11"},
    "12": {"min": 1120, "max": 1385, "label": "Grade 12"},
}


def get_lexile_band(grade_level: str) -> Optional[Dict]:
    """Return Lexile range for a grade level.

    Args:
        grade_level: Grade level string (e.g., "6", "7", "8").
            Also accepts formats like "6th", "Grade 6", "8th Grade".

    Returns:
        Dict with 'min', 'max', 'label' keys, or None if grade not found.
    """
    # Normalize grade level -- extract digits
    match = re.search(r"(\d+)", str(grade_level))
    if not match:
        return None
    grade = match.group(1)
    return LEXILE_BANDS.get(grade)


def get_all_lexile_bands() -> Dict[str, Dict]:
    """Return all Lexile bands.

    Returns:
        Dict mapping grade level strings to band info dicts.
    """
    return dict(LEXILE_BANDS)


# --- Text Complexity Estimation (Flesch-Kincaid) ---


def _count_syllables(word: str) -> int:
    """Count syllables in a word using a heuristic approach.

    This is a deterministic algorithm, no AI involved.
    Based on the vowel-counting method with common English adjustments.

    Args:
        word: A single word string.

    Returns:
        Estimated number of syllables (minimum 1).
    """
    word = word.lower().strip()
    if not word:
        return 0

    # Remove non-alpha characters
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 0

    vowels = "aeiouy"
    count = 0
    prev_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel

    # Adjust for silent 'e' at end
    if word.endswith("e") and count > 1:
        count -= 1

    # Adjust for common endings
    if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
        count += 1

    # Adjust for -ed endings that don't add a syllable
    if word.endswith("ed") and count > 1 and not word.endswith("ted") and not word.endswith("ded"):
        count -= 1

    return max(1, count)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences.

    Args:
        text: Input text.

    Returns:
        List of sentence strings.
    """
    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r"[.!?]+(?:\s|$)", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _split_words(text: str) -> List[str]:
    """Split text into words.

    Args:
        text: Input text.

    Returns:
        List of word strings.
    """
    return [w for w in re.findall(r"[a-zA-Z']+", text) if w]


def estimate_text_complexity(text: str) -> Dict:
    """Estimate reading complexity using Flesch-Kincaid Grade Level formula.

    This is a DETERMINISTIC calculation -- pure math, no AI involved.
    Formula: grade = 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59

    Args:
        text: The text to analyze.

    Returns:
        Dict with:
            - 'grade_level': Estimated Flesch-Kincaid grade level (float)
            - 'total_words': Number of words
            - 'total_sentences': Number of sentences
            - 'total_syllables': Number of syllables
            - 'avg_words_per_sentence': Average words per sentence
            - 'avg_syllables_per_word': Average syllables per word
            - 'lexile_estimate': Approximate Lexile range string

    Raises:
        ValueError: If text is empty or has no analyzable content.
    """
    if not text or not text.strip():
        raise ValueError("Cannot estimate complexity of empty text")

    words = _split_words(text)
    sentences = _split_sentences(text)

    total_words = len(words)
    total_sentences = len(sentences)

    if total_words == 0:
        raise ValueError("No words found in text")
    if total_sentences == 0:
        total_sentences = 1  # Treat entire text as one sentence

    total_syllables = sum(_count_syllables(w) for w in words)

    avg_words_per_sentence = total_words / total_sentences
    avg_syllables_per_word = total_syllables / total_words

    # Flesch-Kincaid Grade Level
    grade_level = 0.39 * avg_words_per_sentence + 11.8 * avg_syllables_per_word - 15.59

    # Clamp to reasonable range
    grade_level = max(0.0, round(grade_level, 1))

    # Estimate Lexile from grade level
    lexile_estimate = _grade_to_lexile_estimate(grade_level)

    return {
        "grade_level": grade_level,
        "total_words": total_words,
        "total_sentences": total_sentences,
        "total_syllables": total_syllables,
        "avg_words_per_sentence": round(avg_words_per_sentence, 1),
        "avg_syllables_per_word": round(avg_syllables_per_word, 2),
        "lexile_estimate": lexile_estimate,
    }


def _grade_to_lexile_estimate(grade_level: float) -> str:
    """Convert a Flesch-Kincaid grade level to an approximate Lexile range.

    Args:
        grade_level: FK grade level.

    Returns:
        String like "970L-1120L" or "Below Grade 2" / "Above Grade 12".
    """
    grade_int = str(max(2, min(12, round(grade_level))))
    band = LEXILE_BANDS.get(grade_int)
    if band:
        return f"{band['min']}L-{band['max']}L"
    if grade_level < 2:
        return "Below 420L"
    return "Above 1385L"


# --- Assessment Blueprint Templates ---

BLUEPRINT_TEMPLATES = {
    "balanced": {
        "label": "Balanced Assessment",
        "description": "Even distribution across cognitive levels, suitable for unit tests.",
        "distribution": {
            "Remember": 15,
            "Understand": 25,
            "Apply": 25,
            "Analyze": 20,
            "Evaluate": 10,
            "Create": 5,
        },
    },
    "higher_order": {
        "label": "Higher-Order Thinking",
        "description": "Emphasizes analysis, evaluation, and creation for advanced assessments.",
        "distribution": {
            "Remember": 5,
            "Understand": 15,
            "Apply": 20,
            "Analyze": 25,
            "Evaluate": 20,
            "Create": 15,
        },
    },
    "foundational": {
        "label": "Foundational Knowledge",
        "description": "Focuses on recall and understanding, ideal for formative checks.",
        "distribution": {
            "Remember": 30,
            "Understand": 30,
            "Apply": 25,
            "Analyze": 10,
            "Evaluate": 5,
            "Create": 0,
        },
    },
    "application_focused": {
        "label": "Application-Focused",
        "description": "Emphasizes applying knowledge to solve problems, good for practice assessments.",
        "distribution": {
            "Remember": 10,
            "Understand": 15,
            "Apply": 35,
            "Analyze": 20,
            "Evaluate": 15,
            "Create": 5,
        },
    },
    "dok_aligned": {
        "label": "DOK-Aligned",
        "description": "Aligned with Webb's Depth of Knowledge expectations for standardized tests.",
        "distribution": {
            "Remember": 10,
            "Understand": 20,
            "Apply": 30,
            "Analyze": 25,
            "Evaluate": 10,
            "Create": 5,
        },
    },
}


def get_blueprint(name: str) -> Optional[Dict]:
    """Return an assessment blueprint template by name.

    Args:
        name: Blueprint key (e.g., 'balanced', 'higher_order').

    Returns:
        Blueprint dict with 'label', 'description', 'distribution', or None.
    """
    return BLUEPRINT_TEMPLATES.get(name)


def get_available_blueprints() -> List[Dict]:
    """Return all available blueprint templates.

    Returns:
        List of dicts with 'key', 'label', 'description', 'distribution'.
    """
    result = []
    for key, bp in BLUEPRINT_TEMPLATES.items():
        result.append(
            {
                "key": key,
                "label": bp["label"],
                "description": bp["description"],
                "distribution": dict(bp["distribution"]),
            }
        )
    return result


def apply_blueprint_to_config(blueprint_name: str, question_count: int) -> Dict[str, int]:
    """Convert a blueprint to actual question count per cognitive level.

    Uses the blueprint's percentage distribution and the total question count
    to calculate how many questions should target each cognitive level.
    Ensures the total adds up exactly to question_count through rounding
    adjustment.

    Args:
        blueprint_name: Key from BLUEPRINT_TEMPLATES.
        question_count: Total number of questions desired.

    Returns:
        Dict mapping cognitive level names to question counts.

    Raises:
        ValueError: If blueprint_name is not found or question_count < 1.
    """
    if question_count < 1:
        raise ValueError("question_count must be at least 1")

    bp = BLUEPRINT_TEMPLATES.get(blueprint_name)
    if bp is None:
        raise ValueError(f"Unknown blueprint '{blueprint_name}'. Available: {list(BLUEPRINT_TEMPLATES.keys())}")

    distribution = bp["distribution"]
    result = {}
    remainder_tracking = []

    # First pass: floor division
    allocated = 0
    for level, pct in distribution.items():
        exact = question_count * pct / 100.0
        floored = int(exact)
        result[level] = floored
        allocated += floored
        remainder_tracking.append((exact - floored, level))

    # Distribute remaining questions to levels with largest fractional parts
    remaining = question_count - allocated
    remainder_tracking.sort(reverse=True, key=lambda x: x[0])
    for i in range(remaining):
        level = remainder_tracking[i][1]
        result[level] += 1

    return result
