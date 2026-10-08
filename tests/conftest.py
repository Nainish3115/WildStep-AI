"""Common test fixtures and helpers for WildStep AI test suite."""
import io
import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import server
SAMPLES_DIR = REPO_ROOT / "samples"
DEMO_WALK_DIR = SAMPLES_DIR / "demo-walk"


@pytest.fixture
def repo_root():
    return REPO_ROOT


@pytest.fixture
def sample_image_path():
    p = SAMPLES_DIR / "acridotheres-tristis.jpg"
    assert p.is_file(), f"Missing sample file {p}"
    return p


@pytest.fixture
def demo_image_with_gps_path():
    p = DEMO_WALK_DIR / "01-acridotheres-tristis.jpg"
    assert p.is_file(), f"Missing demo file {p}"
    return p


@pytest.fixture
def simple_jpeg_bytes():
    """Generate a clean in-memory RGB JPEG image without EXIF."""
    img = Image.new("RGB", (200, 150), color=(34, 139, 34))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def test_server():
    """Runs an ephemeral in-process HTTP server on a random OS-assigned free port."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    host, port = srv.server_address
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://{host}:{port}"
    yield base_url
    srv.shutdown()
    srv.server_close()


def http_request(url, method="GET", json_data=None, headers=None):
    """Helper to perform HTTP requests against the test server."""
    req_headers = {"User-Agent": "WildStep-Test/1.0"}
    if headers:
        req_headers.update(headers)
    body = None
    if json_data is not None:
        body = json.dumps(json_data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read()
            return resp.status, resp.headers, content
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()
