"""
Tests for image upload functionality (BL-008 stretch: file upload).

Tests cover:
- Generic image upload endpoint (POST /api/upload-image)
- Per-question image upload updated to use uploads/images/ with UUID filenames
- Serving uploaded images (GET /uploads/images/<filename>)
- File validation (extension, missing file)
- Auth guards
- UUID filename collision prevention
- Path traversal prevention
"""

import os
from io import BytesIO

import pytest

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def upload_client(flask_app, tmp_path):
    """Logged-in test client with upload directory configured."""
    upload_dir = str(tmp_path / "uploads" / "images")
    flask_app.config["APP_CONFIG"]["paths"]["upload_dir"] = upload_dir
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield c


@pytest.fixture
def anon_upload_client(flask_app, tmp_path):
    """Unauthenticated test client with upload directory configured."""
    upload_dir = str(tmp_path / "uploads" / "images")
    flask_app.config["APP_CONFIG"]["paths"]["upload_dir"] = upload_dir
    with flask_app.test_client() as c:
        yield c


def _png_bytes():
    """Return minimal valid PNG-like bytes for upload testing."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _jpg_bytes():
    """Return minimal JPEG-like bytes for upload testing."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


# ============================================================
# Generic Upload Endpoint Tests (POST /api/upload-image)
# ============================================================


class TestGenericImageUpload:
    """Tests for POST /api/upload-image."""

    def test_upload_png(self, upload_client, tmp_path):
        data = {"image": (BytesIO(_png_bytes()), "photo.png")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["ok"] is True
        assert result["url"].startswith("/uploads/images/")
        assert result["url"].endswith(".png")
        assert "filename" in result
        # Verify file was actually saved
        upload_dir = str(tmp_path / "uploads" / "images")
        assert os.path.exists(os.path.join(upload_dir, result["filename"]))

    def test_upload_jpg(self, upload_client, tmp_path):
        data = {"image": (BytesIO(_jpg_bytes()), "photo.jpg")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["ok"] is True
        assert result["url"].endswith(".jpg")

    def test_upload_jpeg(self, upload_client):
        data = {"image": (BytesIO(_jpg_bytes()), "photo.jpeg")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["ok"] is True
        assert result["url"].endswith(".jpeg")

    def test_upload_gif(self, upload_client):
        data = {"image": (BytesIO(b"GIF89a" + b"\x00" * 100), "anim.gif")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_upload_webp(self, upload_client):
        data = {"image": (BytesIO(b"RIFF" + b"\x00" * 100), "image.webp")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_reject_exe(self, upload_client):
        data = {"image": (BytesIO(b"MZ" + b"\x00" * 100), "malware.exe")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        result = resp.get_json()
        assert result["ok"] is False
        assert "Invalid file type" in result["error"]

    def test_reject_html(self, upload_client):
        data = {"image": (BytesIO(b"<html>XSS</html>"), "page.html")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_reject_py(self, upload_client):
        data = {"image": (BytesIO(b"import os"), "script.py")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_reject_no_file(self, upload_client):
        resp = upload_client.post("/api/upload-image")
        assert resp.status_code == 400
        result = resp.get_json()
        assert result["ok"] is False
        assert "No image file" in result["error"]

    def test_reject_empty_filename(self, upload_client):
        data = {"image": (BytesIO(_png_bytes()), "")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_uuid_filename(self, upload_client):
        """Filename should be a UUID, not the original filename."""
        data = {"image": (BytesIO(_png_bytes()), "my_secret_name.png")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        result = resp.get_json()
        filename = result["filename"]
        # Should NOT contain the original name
        assert "my_secret_name" not in filename
        # Should be uuid hex (32 chars) + extension
        name_part = filename.rsplit(".", 1)[0]
        assert len(name_part) == 32
        # Verify it's valid hex
        int(name_part, 16)

    def test_no_path_traversal(self, upload_client):
        """Filenames with path traversal components should be safe."""
        data = {"image": (BytesIO(_png_bytes()), "../../../etc/passwd.png")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert ".." not in result["filename"]
        assert "/" not in result["filename"]
        assert "\\" not in result["filename"]

    def test_multiple_uploads_unique(self, upload_client):
        """Multiple uploads of the same file get different filenames."""
        filenames = set()
        for _ in range(5):
            data = {"image": (BytesIO(_png_bytes()), "same.png")}
            resp = upload_client.post(
                "/api/upload-image",
                data=data,
                content_type="multipart/form-data",
            )
            result = resp.get_json()
            filenames.add(result["filename"])
        assert len(filenames) == 5

    def test_requires_login(self, anon_upload_client):
        data = {"image": (BytesIO(_png_bytes()), "photo.png")}
        resp = anon_upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 303


# ============================================================
# Per-Question Upload Tests (updated to use uploads/images/)
# ============================================================


class TestQuestionImageUploadUpdated:
    """Tests for POST /api/questions/<id>/image with UUID filenames."""

    def test_upload_saves_to_uploads_dir(self, upload_client, flask_app, tmp_path):
        data = {"image": (BytesIO(_png_bytes()), "test.png")}
        resp = upload_client.post(
            "/api/questions/1/image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["ok"] is True
        assert "image_ref" in result
        assert "url" in result
        assert result["url"].startswith("/uploads/images/")
        # Verify UUID filename
        name_part = result["image_ref"].rsplit(".", 1)[0]
        assert len(name_part) == 32

    def test_upload_updates_question_data(self, upload_client, flask_app, tmp_path):
        data = {"image": (BytesIO(_png_bytes()), "test.png")}
        resp = upload_client.post(
            "/api/questions/1/image",
            data=data,
            content_type="multipart/form-data",
        )
        result = resp.get_json()
        # Verify the question's data was updated with the image_ref
        with flask_app.test_client() as c:
            with c.session_transaction() as sess:
                sess["logged_in"] = True
                sess["username"] = "teacher"
            detail_resp = c.get("/quizzes/1")
            assert result["image_ref"].encode() in detail_resp.data


# ============================================================
# Serving Uploaded Images Tests
# ============================================================


class TestServeUploadedImages:
    """Tests for GET /uploads/images/<filename>."""

    def test_serve_existing_image(self, upload_client, flask_app, tmp_path):
        # First upload an image
        data = {"image": (BytesIO(_png_bytes()), "test.png")}
        resp = upload_client.post(
            "/api/upload-image",
            data=data,
            content_type="multipart/form-data",
        )
        result = resp.get_json()

        # Then fetch it
        serve_resp = upload_client.get(result["url"])
        assert serve_resp.status_code == 200

    def test_serve_nonexistent_image(self, upload_client):
        resp = upload_client.get("/uploads/images/nonexistent_abc123.png")
        assert resp.status_code == 404

    def test_serve_requires_login(self, anon_upload_client):
        resp = anon_upload_client.get("/uploads/images/somefile.png")
        assert resp.status_code == 303

    def test_path_traversal_blocked(self, upload_client):
        """Path traversal in the filename should not escape the uploads dir."""
        resp = upload_client.get("/uploads/images/..%2F..%2Fconfig.yaml")
        # Flask's send_from_directory should reject this
        assert resp.status_code in (400, 404)


# ============================================================
# Upload Directory Auto-Creation
# ============================================================


class TestUploadDirCreation:
    """Test that the upload directory is created automatically."""

    def test_dir_created_on_upload(self, flask_app, tmp_path):
        upload_dir = str(tmp_path / "new_dir" / "images")
        flask_app.config["APP_CONFIG"]["paths"]["upload_dir"] = upload_dir
        assert not os.path.exists(upload_dir)

        with flask_app.test_client() as c:
            with c.session_transaction() as sess:
                sess["logged_in"] = True
                sess["username"] = "teacher"

            data = {"image": (BytesIO(_png_bytes()), "test.png")}
            resp = c.post(
                "/api/upload-image",
                data=data,
                content_type="multipart/form-data",
            )
            assert resp.status_code == 200
            assert os.path.exists(upload_dir)
