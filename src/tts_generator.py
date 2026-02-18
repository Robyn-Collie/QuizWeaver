"""Server-side text-to-speech generation for quiz audio exports.

Uses gTTS (Google Text-to-Speech) to generate MP3 audio files for quiz
questions.  gTTS is an optional dependency -- the module degrades
gracefully when it is not installed, disabling audio features without
raising errors.

Audio files are stored under ``uploads/audio/{quiz_id}/`` and can be
served individually or bundled into a ZIP download.
"""

import logging
import os
import re
import zipfile
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    from gtts import gTTS

    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Hard cap to prevent runaway file generation.
MAX_QUESTIONS_PER_QUIZ = 50


def is_tts_available():
    """Return True if the gTTS library is installed and importable."""
    return TTS_AVAILABLE


def _sanitize_text(text):
    """Strip HTML tags and collapse whitespace for cleaner speech output."""
    if not text:
        return ""
    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _build_question_text(question):
    """Build the full spoken text for a question dict.

    Includes the question text and, for multiple-choice questions, the
    lettered options.
    """
    parts = []
    text = _sanitize_text(question.get("text", ""))
    if text:
        parts.append(text)

    options = question.get("options", [])
    if options:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for idx, opt in enumerate(options):
            letter = letters[idx] if idx < len(letters) else str(idx + 1)
            parts.append(f"{letter}. {_sanitize_text(opt)}")

    return ". ".join(parts)


def generate_question_audio(question_text, output_path, lang="en"):
    """Generate an MP3 audio file for a single question's text.

    Parameters
    ----------
    question_text : str
        The text to convert to speech.
    output_path : str
        Full filesystem path for the resulting .mp3 file.
    lang : str
        BCP-47 language code (default ``"en"``).

    Returns
    -------
    str | None
        The *output_path* on success, or ``None`` if generation failed.

    Raises
    ------
    RuntimeError
        If gTTS is not installed.
    """
    if not TTS_AVAILABLE:
        raise RuntimeError("gTTS is not installed. Run: pip install gtts")

    cleaned = _sanitize_text(question_text)
    if not cleaned:
        logger.warning("Empty text passed to generate_question_audio; skipping.")
        return None

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        tts = gTTS(text=cleaned, lang=lang)
        tts.save(output_path)
        return output_path
    except Exception:
        logger.exception("Failed to generate audio for: %s...", cleaned[:60])
        return None


def generate_quiz_audio(questions, output_dir, lang="en"):
    """Generate MP3 files for every question in *questions*.

    Parameters
    ----------
    questions : list[dict]
        Each dict must have ``"id"`` and ``"text"`` keys; ``"options"``
        is optional (included in the audio when present).
    output_dir : str
        Directory under which ``q{id}.mp3`` files will be created.
    lang : str
        BCP-47 language code.

    Returns
    -------
    dict[int, str]
        Mapping of question-id to the generated file path.  Questions
        that fail or are skipped are omitted from the dict.
    """
    if not TTS_AVAILABLE:
        raise RuntimeError("gTTS is not installed. Run: pip install gtts")

    os.makedirs(output_dir, exist_ok=True)
    results = {}

    for q in questions[:MAX_QUESTIONS_PER_QUIZ]:
        q_id = q.get("id")
        spoken = _build_question_text(q)
        if not spoken:
            continue

        filename = f"q{q_id}.mp3"
        filepath = os.path.join(output_dir, filename)

        path = generate_question_audio(spoken, filepath, lang=lang)
        if path:
            results[q_id] = path

    return results


def bundle_audio_zip(audio_dir, quiz_title="quiz"):
    """Create an in-memory ZIP of all MP3 files in *audio_dir*.

    Returns
    -------
    BytesIO
        A seeked-to-zero BytesIO buffer containing the ZIP archive.
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.isdir(audio_dir):
            for fname in sorted(os.listdir(audio_dir)):
                if fname.lower().endswith(".mp3"):
                    fpath = os.path.join(audio_dir, fname)
                    zf.write(fpath, f"{quiz_title}_audio/{fname}")
    buf.seek(0)
    return buf


def cleanup_quiz_audio(quiz_id, base_dir="uploads/audio"):
    """Remove all generated audio files for a quiz.

    Safe to call even when the directory does not exist.
    """
    audio_dir = os.path.join(base_dir, str(quiz_id))
    if not os.path.isdir(audio_dir):
        return
    for fname in os.listdir(audio_dir):
        fpath = os.path.join(audio_dir, fname)
        try:
            os.remove(fpath)
        except OSError:
            pass
    try:
        os.rmdir(audio_dir)
    except OSError:
        pass


def get_quiz_audio_dir(quiz_id, base_dir="uploads/audio"):
    """Return the canonical audio directory path for a quiz."""
    return os.path.join(base_dir, str(quiz_id))


def has_audio(quiz_id, base_dir="uploads/audio"):
    """Return True if audio files have already been generated for a quiz."""
    audio_dir = get_quiz_audio_dir(quiz_id, base_dir)
    if not os.path.isdir(audio_dir):
        return False
    return any(f.endswith(".mp3") for f in os.listdir(audio_dir))
