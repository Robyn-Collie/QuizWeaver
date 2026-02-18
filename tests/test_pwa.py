"""Tests for Progressive Web App (PWA) support.

Covers manifest.json, service worker, offline route, icon files,
and base.html integration tags.
"""

import json
import os
import struct

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def _read_template(name):
    """Return the raw text of a template file."""
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# manifest.json tests
# ---------------------------------------------------------------------------


class TestManifest:
    """Tests for static/manifest.json validity and required fields."""

    def test_manifest_is_valid_json(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, dict)

    def test_manifest_required_fields(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["name"] == "QuizWeaver"
        assert data["short_name"] == "QuizWeaver"
        assert data["start_url"] == "/dashboard"
        assert data["display"] == "standalone"
        assert data["background_color"] == "#ffffff"
        assert data["theme_color"] == "#2c5f2d"
        assert "description" in data

    def test_manifest_icons_array(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        icons = data.get("icons", [])
        sizes = {icon["sizes"] for icon in icons}
        assert "192x192" in sizes
        assert "512x512" in sizes

    def test_manifest_categories(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        categories = data.get("categories", [])
        assert "education" in categories
        assert "productivity" in categories

    def test_manifest_served_at_correct_url(self, flask_client):
        resp = flask_client.get("/static/manifest.json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["name"] == "QuizWeaver"


# ---------------------------------------------------------------------------
# Icon file tests
# ---------------------------------------------------------------------------


class TestIcons:
    """Tests that icon files exist and are valid PNGs."""

    @pytest.mark.parametrize("size", [192, 512])
    def test_icon_file_exists(self, size):
        path = os.path.join(STATIC_DIR, "icons", f"icon-{size}.png")
        assert os.path.isfile(path), f"icon-{size}.png should exist"

    @pytest.mark.parametrize("size", [192, 512])
    def test_icon_is_valid_png(self, size):
        path = os.path.join(STATIC_DIR, "icons", f"icon-{size}.png")
        with open(path, "rb") as fh:
            header = fh.read(8)
        # PNG magic bytes
        assert header[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.parametrize("size", [192, 512])
    def test_icon_dimensions(self, size):
        """Verify the IHDR chunk reports the expected dimensions."""
        path = os.path.join(STATIC_DIR, "icons", f"icon-{size}.png")
        with open(path, "rb") as fh:
            fh.read(8)  # skip PNG signature
            fh.read(4)  # skip IHDR length
            fh.read(4)  # skip 'IHDR' tag
            width = struct.unpack(">I", fh.read(4))[0]
            height = struct.unpack(">I", fh.read(4))[0]
        assert width == size
        assert height == size


# ---------------------------------------------------------------------------
# base.html integration tests
# ---------------------------------------------------------------------------


class TestBaseTemplate:
    """Tests that base.html includes all required PWA tags."""

    def test_manifest_link_tag(self):
        html = _read_template("base.html")
        assert 'rel="manifest"' in html
        assert "manifest.json" in html

    def test_theme_color_meta(self):
        html = _read_template("base.html")
        assert 'name="theme-color"' in html
        assert "#2c5f2d" in html

    def test_apple_mobile_web_app_capable(self):
        html = _read_template("base.html")
        assert 'name="apple-mobile-web-app-capable"' in html

    def test_apple_mobile_web_app_status_bar_style(self):
        html = _read_template("base.html")
        assert 'name="apple-mobile-web-app-status-bar-style"' in html

    def test_apple_touch_icon(self):
        html = _read_template("base.html")
        assert 'rel="apple-touch-icon"' in html
        assert "icon-192.png" in html

    def test_service_worker_registration(self):
        html = _read_template("base.html")
        assert "serviceWorker" in html
        assert "sw.js" in html


# ---------------------------------------------------------------------------
# Service worker tests
# ---------------------------------------------------------------------------


class TestServiceWorker:
    """Tests for static/sw.js content and availability."""

    def test_sw_js_served(self, flask_client):
        resp = flask_client.get("/static/sw.js")
        assert resp.status_code == 200

    def test_sw_js_has_cache_version(self):
        path = os.path.join(STATIC_DIR, "sw.js")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "CACHE_VERSION" in content

    def test_sw_js_has_cache_logic(self):
        path = os.path.join(STATIC_DIR, "sw.js")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "caches.open" in content
        assert "install" in content
        assert "activate" in content
        assert "fetch" in content


# ---------------------------------------------------------------------------
# Offline route tests
# ---------------------------------------------------------------------------


class TestOfflineRoute:
    """Tests for the /offline fallback page."""

    def test_offline_returns_200(self, flask_client):
        resp = flask_client.get("/offline")
        assert resp.status_code == 200

    def test_offline_no_auth_required(self, anon_flask_client):
        resp = anon_flask_client.get("/offline")
        assert resp.status_code == 200

    def test_offline_contains_message(self, flask_client):
        resp = flask_client.get("/offline")
        html = resp.data.decode("utf-8")
        assert "offline" in html.lower()
        assert "reconnect" in html.lower()
