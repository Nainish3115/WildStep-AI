"""HTTP API endpoints and integration tests using ephemeral in-process server."""
import base64
import json
import urllib.error
import pytest

import server
from conftest import http_request


def test_get_health_when_ollama_offline(test_server, monkeypatch):
    real_urlopen = urllib.request.urlopen

    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "11434" in url or "tags" in url:
            raise urllib.error.URLError("Ollama not running")
        return real_urlopen(req, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    code, headers, body = http_request(f"{test_server}/api/health")
    assert code == 200
    data = json.loads(body.decode("utf-8"))
    assert data["ok"] is False
    assert "error" in data


def test_get_health_when_ollama_online(test_server, monkeypatch):
    class MockTags:
        def __init__(self):
            self.data = json.dumps({"models": [{"name": server.MODEL}]}).encode()

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    real_urlopen = urllib.request.urlopen

    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "11434" in url or "tags" in url:
            return MockTags()
        return real_urlopen(req, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    code, headers, body = http_request(f"{test_server}/api/health")
    assert code == 200
    data = json.loads(body.decode("utf-8"))
    assert data["ok"] is True
    assert data["model"] == server.MODEL


def test_get_root_serves_html(test_server):
    code, headers, body = http_request(f"{test_server}/")
    assert code == 200
    assert "text/html" in headers.get("Content-Type", "")
    html = body.decode("utf-8")
    assert "<title>WildStep AI" in html
    assert "WildStep AI 🌿" in html


def test_get_index_html_serves_html(test_server):
    code, headers, body = http_request(f"{test_server}/index.html")
    assert code == 200
    assert "text/html" in headers.get("Content-Type", "")


def test_post_quests_quick_card(test_server):
    code, headers, body = http_request(f"{test_server}/api/quests", method="POST", json_data={"quick": True})
    assert code == 200
    data = json.loads(body.decode("utf-8"))
    assert data["title"] == "Quick Quest"
    assert len(data["quests"]) == 6


def test_post_missions_alias_quick_card(test_server):
    """Verify /api/missions endpoint alias functions identically to /api/quests."""
    code, headers, body = http_request(f"{test_server}/api/missions", method="POST", json_data={"quick": True})
    assert code == 200
    data = json.loads(body.decode("utf-8"))
    assert data["title"] == "Quick Quest"
    assert len(data["quests"]) == 6


def test_post_quests_generate_mission(test_server, monkeypatch):
    mock_quests = '{"title": "Park Walk", "quests": [' + ",".join([
        f'{{"text": "Find item {i}", "emoji": "🌱", "points": 10}}' for i in range(6)
    ]) + ']}'
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: mock_quests)

    payload = {"place": "Forest Reserve", "who": "duo", "month": "October"}
    code, headers, body = http_request(f"{test_server}/api/quests", method="POST", json_data=payload)
    assert code == 200
    data = json.loads(body.decode("utf-8"))
    assert data["title"] == "Park Walk"
    assert len(data["quests"]) == 6


def test_post_check_photo_success(test_server, monkeypatch, simple_jpeg_bytes):
    mock_resp = {
        "what_i_see": "A green leaf closeup",
        "main_subject": "A leaf",
        "checks": [
            {"id": "q1", "evidence": "A large green leaf in full focus", "is_main_subject": True, "completed": True}
        ],
    }
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: json.dumps(mock_resp))

    b64_img = "data:image/jpeg;base64," + base64.b64encode(simple_jpeg_bytes).decode("ascii")
    payload = {"quests": [{"id": "q1", "text": "A leaf"}], "image": b64_img}

    code, headers, body = http_request(f"{test_server}/api/check", method="POST", json_data=payload)
    assert code == 200
    data = json.loads(body.decode("utf-8"))
    assert data["main_subject"] == "A leaf"
    assert len(data["completed"]) == 1
    assert "thumb" in data


def test_post_check_photo_when_ollama_unreachable_returns_503(test_server, monkeypatch, simple_jpeg_bytes):
    """Regression test: when Ollama raises URLError, /api/check must return HTTP 503."""
    def mock_ollama_down(*a, **kw):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(server, "ollama_chat", mock_ollama_down)

    b64_img = "data:image/jpeg;base64," + base64.b64encode(simple_jpeg_bytes).decode("ascii")
    payload = {"quests": [{"id": "q1", "text": "A leaf"}], "image": b64_img}

    code, headers, body = http_request(f"{test_server}/api/check", method="POST", json_data=payload)
    assert code == 503
    data = json.loads(body.decode("utf-8"))
    assert "The local model is not running" in data["error"]


def test_post_check_photo_corrupted_image_returns_400(test_server):
    payload = {"quests": [{"id": "q1", "text": "A leaf"}], "image": "data:image/jpeg;base64,bm90YW5pbWFnZQ=="}
    code, headers, body = http_request(f"{test_server}/api/check", method="POST", json_data=payload)
    assert code == 400
    data = json.loads(body.decode("utf-8"))
    assert "Could not read that photo" in data["error"]


def test_get_unknown_path_returns_404(test_server):
    code, headers, body = http_request(f"{test_server}/api/nonexistent_endpoint")
    assert code == 404
    data = json.loads(body.decode("utf-8"))
    assert data["error"] == "not found"


def test_post_malformed_json_returns_400(test_server):
    code, headers, body = http_request(
        f"{test_server}/api/quests",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    # Empty body with Content-Length 0
    assert code == 400


def test_post_check_timeout_returns_503(test_server, monkeypatch, simple_jpeg_bytes):
    """TimeoutError in ollama_chat must produce HTTP 503 instead of crashing the server."""
    def mock_ollama_timeout(*a, **kw):
        raise TimeoutError("Ollama request timed out")

    monkeypatch.setattr(server, "ollama_chat", mock_ollama_timeout)

    b64_img = "data:image/jpeg;base64," + base64.b64encode(simple_jpeg_bytes).decode("ascii")
    payload = {"quests": [{"id": "q1", "text": "A leaf"}], "image": b64_img}

    code, headers, body = http_request(f"{test_server}/api/check", method="POST", json_data=payload)
    assert code == 503
    data = json.loads(body.decode("utf-8"))
    assert "timed out" in data["error"]


def test_post_unknown_endpoint_returns_404(test_server):
    """POST to unhandled route returns 404."""
    code, headers, body = http_request(
        f"{test_server}/api/unhandled",
        method="POST",
        json_data={"foo": "bar"},
    )
    assert code == 404
    data = json.loads(body.decode("utf-8"))
    assert data["error"] == "not found"
