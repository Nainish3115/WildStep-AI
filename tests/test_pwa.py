"""Tests for Progressive Web App (PWA) and Offline Application Shell in WildStep AI.

Validates:
1. Web App Manifest existence, schema compliance, identity, and icon references.
2. Icon assets existence, dimensions, and local availability.
3. Service worker caching strategy, versioning, narrow allowlists, and cache bypass for API/POST requests.
4. Privacy: Zero caching of user photographs, zero external CDN dependencies.
5. Client-side Service Worker registration and install prompt (beforeinstallprompt) integration.
6. Honest connectivity and local AI status reporting (distinguishing offline network from Ollama/server state).
7. Server MIME types for PWA assets (.webmanifest, .svg, .png).
"""

import json
from pathlib import Path
import re
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "static"
MANIFEST_PATH = STATIC_DIR / "manifest.webmanifest"
SW_PATH = STATIC_DIR / "sw.js"
INDEX_PATH = STATIC_DIR / "index.html"
SERVER_PATH = REPO_ROOT / "server.py"


@pytest.fixture(scope="module")
def manifest_data() -> dict:
    """Loads and parses static/manifest.webmanifest."""
    assert MANIFEST_PATH.exists(), "static/manifest.webmanifest must exist"
    content = MANIFEST_PATH.read_text(encoding="utf-8")
    return json.loads(content)


@pytest.fixture(scope="module")
def sw_content() -> str:
    """Loads static/sw.js."""
    assert SW_PATH.exists(), "static/sw.js must exist"
    return SW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html_content() -> str:
    """Loads static/index.html."""
    assert INDEX_PATH.exists(), "static/index.html must exist"
    return INDEX_PATH.read_text(encoding="utf-8")


# ===========================================================================
# 1. Web App Manifest
# ===========================================================================

def test_manifest_metadata(manifest_data: dict):
    """Manifest must contain correct WildStep AI identity and PWA configuration."""
    assert manifest_data["name"] == "WildStep AI"
    assert manifest_data["short_name"] == "WildStep"
    assert "Real-world missions" in manifest_data["description"]
    assert manifest_data["start_url"] == "/"
    assert manifest_data["display"] == "standalone"
    assert manifest_data["theme_color"] == "#2f6b2a"
    assert manifest_data["background_color"] == "#081107"


def test_manifest_icons_exist_and_match_dimensions(manifest_data: dict):
    """All icon files specified in manifest.webmanifest must physically exist with valid dimensions."""
    icons = manifest_data.get("icons", [])
    assert len(icons) >= 3, "Manifest must specify at least 192px, 512px, and svg icons"

    for icon in icons:
        src = icon["src"].lstrip("/")
        icon_file = STATIC_DIR / src
        assert icon_file.exists(), f"Icon referenced in manifest does not exist: {src}"

        # If PNG, inspect actual pixel dimensions
        if icon["type"] == "image/png":
            with Image.open(icon_file) as img:
                expected_sizes = icon["sizes"].split("x")
                assert img.width == int(expected_sizes[0])
                assert img.height == int(expected_sizes[1])
        elif icon["type"] == "image/svg+xml":
            assert icon_file.suffix == ".svg"


# ===========================================================================
# 2. Service Worker Contract & Caching Strategy
# ===========================================================================

def test_service_worker_cache_version(sw_content: str):
    """Service worker must define a versioned cache identifier."""
    assert "CACHE_NAME" in sw_content
    pattern = r"CACHE_NAME\s*=\s*['\"]wildstep-shell-v\d+['\"]"
    assert re.search(pattern, sw_content) is not None, "Cache name must follow wildstep-shell-v* pattern"


def test_service_worker_preloads_core_shell_assets(sw_content: str):
    """Service worker install event must pre-cache core application shell files."""
    for asset in ["/", "/index.html", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/icon.svg"]:
        assert asset in sw_content, f"Core shell asset missing from precache list: {asset}"
    assert "skipWaiting" in sw_content


def test_service_worker_activation_cleanup(sw_content: str):
    """Service worker activation must purge obsolete wildstep-* caches."""
    assert "activate" in sw_content
    assert "caches.delete" in sw_content
    assert "clients.claim" in sw_content


def test_service_worker_strictly_ignores_post_requests(sw_content: str):
    """Service worker must strictly bypass non-GET requests (e.g. POST /api/check)."""
    assert "event.request.method !== 'GET'" in sw_content
    pattern = r"if\s*\(\s*event\.request\.method\s*!==\s*['\"]GET['\"]\s*\)\s*\{\s*return;\s*\}"
    assert re.search(pattern, sw_content) is not None


def test_service_worker_bypasses_api_requests(sw_content: str):
    """Service worker must NEVER cache /api/* routes (live local server required)."""
    assert "url.pathname.startsWith('/api/')" in sw_content
    pattern = r"if\s*\(\s*url\.pathname\.startsWith\(['\"]/api/['\"]\)\s*\)\s*\{\s*return;\s*\}"
    assert re.search(pattern, sw_content) is not None


def test_service_worker_same_origin_restriction(sw_content: str):
    """Service worker must reject or ignore external domains."""
    assert "url.origin !== self.location.origin" in sw_content


def test_service_worker_never_caches_user_photographs(sw_content: str):
    """No photo paths or user photo caches should be stored permanently by the service worker."""
    forbidden = ["walk_photo", "user-photo", "photo-cache", "photos-cache"]
    for f in forbidden:
        assert f not in sw_content


# ===========================================================================
# 3. HTML Integration & Registration
# ===========================================================================

def test_html_includes_manifest_and_meta_tags(html_content: str):
    """HTML must declare manifest link, theme-color, and mobile web app meta tags."""
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html_content
    assert '<meta name="theme-color" content="#2f6b2a">' in html_content
    assert '<meta name="mobile-web-app-capable" content="yes">' in html_content
    assert '<link rel="icon" type="image/svg+xml" href="/icon.svg">' in html_content
    assert '<link rel="apple-touch-icon" href="/icon-192.png">' in html_content


def test_html_registers_service_worker_safely(html_content: str):
    """Service worker registration must feature feature-detection and safe error handling."""
    assert "'serviceWorker' in navigator" in html_content
    assert "navigator.serviceWorker.register('/sw.js')" in html_content
    assert ".catch(" in html_content


def test_install_button_and_prompt_lifecycle(html_content: str):
    """Install button must exist and handle beforeinstallprompt / appinstalled events."""
    assert 'id="installBtn"' in html_content
    assert "beforeinstallprompt" in html_content
    assert "deferredInstallPrompt" in html_content
    assert "deferredInstallPrompt.prompt()" in html_content
    assert "appinstalled" in html_content


def test_honest_offline_connectivity_reporting(html_content: str):
    """Status indicator must distinguish network offline from unreachable local AI server."""
    assert "updateConnectivityStatus" in html_content
    assert "navigator.onLine" in html_content
    assert "Offline app shell active · Local AI connection unavailable" in html_content
    assert "App shell available · Local AI server unreachable" in html_content
    assert "App shell ready" in html_content


# ===========================================================================
# 4. Server Route & MIME Handling
# ===========================================================================

def test_server_serves_webmanifest_and_icons():
    """server.py must configure correct MIME types for .webmanifest, .svg, and .png."""
    server_code = SERVER_PATH.read_text(encoding="utf-8")
    assert ".webmanifest" in server_code
    assert "application/manifest+json" in server_code
    assert ".svg" in server_code
    assert "image/svg+xml" in server_code
    assert ".png" in server_code
    assert "image/png" in server_code
