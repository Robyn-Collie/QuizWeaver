"""Tests for QTI export with TTS audio bundling."""

import json
import os
import tempfile
import zipfile

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session
from src.export import export_qti


@pytest.fixture
def quiz_with_audio(tmp_path):
    """Create a quiz with questions and audio files on disk."""
    db_path = str(tmp_path / "test.db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Science 7",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    quiz = Quiz(
        title="Audio Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade"}),
    )
    session.add(quiz)
    session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is photosynthesis?",
        points=2.0,
        data=json.dumps({
            "type": "mc",
            "options": ["Light reaction", "Dark reaction", "Both", "Neither"],
            "correct_index": 2,
        }),
    )
    q2 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q2",
        text="What is mitosis?",
        points=2.0,
        data=json.dumps({
            "type": "mc",
            "options": ["Cell division", "Cell death", "Cell growth", "Cell repair"],
            "correct_index": 0,
        }),
    )
    session.add(q1)
    session.add(q2)
    session.commit()

    # Create audio files on disk
    audio_dir = str(tmp_path / "audio")
    os.makedirs(audio_dir, exist_ok=True)
    # Create fake MP3 files (just need to exist)
    with open(os.path.join(audio_dir, f"q{q1.id}.mp3"), "wb") as f:
        f.write(b"fake-mp3-q1")
    with open(os.path.join(audio_dir, f"q{q2.id}.mp3"), "wb") as f:
        f.write(b"fake-mp3-q2")

    result = {
        "quiz": quiz,
        "questions": [q1, q2],
        "audio_dir": audio_dir,
        "q1_id": q1.id,
        "q2_id": q2.id,
    }

    yield result

    session.close()
    engine.dispose()


class TestQTIAudioBundling:
    """Verify audio files are bundled in QTI ZIP packages."""

    def test_audio_files_in_zip(self, quiz_with_audio):
        """MP3 files should be in the ZIP under media/ directory."""
        d = quiz_with_audio
        buf = export_qti(d["quiz"], d["questions"], audio_dir=d["audio_dir"])
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert f"media/q{d['q1_id']}.mp3" in names
            assert f"media/q{d['q2_id']}.mp3" in names

    def test_audio_manifest_entries(self, quiz_with_audio):
        """Manifest should have webcontent resources for each audio file."""
        d = quiz_with_audio
        buf = export_qti(d["quiz"], d["questions"], audio_dir=d["audio_dir"])
        with zipfile.ZipFile(buf) as zf:
            manifest = zf.read("imsmanifest.xml").decode()
            assert 'type="webcontent"' in manifest
            assert f"media/q{d['q1_id']}.mp3" in manifest
            assert f"media/q{d['q2_id']}.mp3" in manifest

    def test_audio_html_in_question_xml(self, quiz_with_audio):
        """Question XML should contain audio tags."""
        d = quiz_with_audio
        buf = export_qti(d["quiz"], d["questions"], audio_dir=d["audio_dir"])
        with zipfile.ZipFile(buf) as zf:
            # Find the assessment XML file (not the manifest)
            xml_files = [n for n in zf.namelist() if n.endswith(".xml") and n != "imsmanifest.xml"]
            assert len(xml_files) == 1
            assessment = zf.read(xml_files[0]).decode()
            # Check for audio tag (XML-escaped)
            assert "%24IMS-CC-FILEBASE%24/media/q" in assessment
            assert "audio controls" in assessment

    def test_no_audio_dir_no_audio(self, quiz_with_audio):
        """Without audio_dir, ZIP should have no media/ entries."""
        d = quiz_with_audio
        buf = export_qti(d["quiz"], d["questions"])  # no audio_dir
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            media_files = [n for n in names if n.startswith("media/")]
            assert len(media_files) == 0

    def test_no_audio_files_on_disk(self, quiz_with_audio, tmp_path):
        """When audio_dir exists but has no files, no audio bundled."""
        d = quiz_with_audio
        empty_dir = str(tmp_path / "empty_audio")
        os.makedirs(empty_dir, exist_ok=True)
        buf = export_qti(d["quiz"], d["questions"], audio_dir=empty_dir)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            media_files = [n for n in names if n.startswith("media/")]
            assert len(media_files) == 0
            # Assessment XML should not have audio tags
            xml_files = [n for n in names if n.endswith(".xml") and n != "imsmanifest.xml"]
            assessment = zf.read(xml_files[0]).decode()
            assert "audio controls" not in assessment

    def test_partial_audio(self, quiz_with_audio):
        """When only some questions have audio, only those get audio tags."""
        d = quiz_with_audio
        # Remove audio for q2
        os.remove(os.path.join(d["audio_dir"], f"q{d['q2_id']}.mp3"))

        buf = export_qti(d["quiz"], d["questions"], audio_dir=d["audio_dir"])
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert f"media/q{d['q1_id']}.mp3" in names
            assert f"media/q{d['q2_id']}.mp3" not in names
            # Manifest should only reference q1 audio
            manifest = zf.read("imsmanifest.xml").decode()
            assert f"media/q{d['q1_id']}.mp3" in manifest
            assert f"media/q{d['q2_id']}.mp3" not in manifest

    def test_audio_with_images(self, quiz_with_audio, tmp_path):
        """Audio and images can coexist in the same QTI ZIP."""
        d = quiz_with_audio
        # Create an image for q1
        image_dir = str(tmp_path / "images")
        os.makedirs(image_dir, exist_ok=True)
        with open(os.path.join(image_dir, "test.png"), "wb") as f:
            f.write(b"fake-png")

        # Add image_ref to q1's data
        q1_data = json.loads(d["questions"][0].data)
        q1_data["image_ref"] = "test.png"
        d["questions"][0].data = json.dumps(q1_data)

        buf = export_qti(d["quiz"], d["questions"], image_dir=image_dir, audio_dir=d["audio_dir"])
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert "images/test.png" in names
            assert f"media/q{d['q1_id']}.mp3" in names
            # Both webcontent types in manifest
            manifest = zf.read("imsmanifest.xml").decode()
            assert "images/test.png" in manifest
            assert f"media/q{d['q1_id']}.mp3" in manifest
