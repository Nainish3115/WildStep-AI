"""Mocked Ollama boundary tests verifying internal logic contracts."""
import io
import json
import urllib.error
import pytest

import server


class MockHTTPResponse:
    def __init__(self, data_dict, status=200):
        self.raw = json.dumps(data_dict).encode("utf-8")
        self.status = status

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_ollama_chat_success(monkeypatch):
    expected_content = '{"title": "Morning Walk", "quests": []}'
    mock_payload = {"message": {"content": expected_content}}

    def mock_urlopen(req, timeout=None):
        return MockHTTPResponse(mock_payload)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    res = server.ollama_chat([{"role": "user", "content": "hi"}])
    assert res == expected_content


def test_ollama_chat_network_failure(monkeypatch):
    def mock_urlopen(req, timeout=None):
        raise urllib.error.URLError("Connection refused: 127.0.0.1:11434")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    with pytest.raises(urllib.error.URLError):
        server.ollama_chat([{"role": "user", "content": "hi"}])


def test_check_photo_dual_condition_and_evidence_threshold(monkeypatch, simple_jpeg_bytes):
    """completed requires: completed=True AND is_main_subject=True AND len(evidence) > 10."""
    quests = [
        {"id": "q1", "text": "A bird"},
        {"id": "q2", "text": "A leaf"},
        {"id": "q3", "text": "A cloud"},
    ]
    model_response = {
        "what_i_see": "A Common Myna sitting on the ground with blurry grass in the background.",
        "main_subject": "A bird",
        "checks": [
            {
                "id": "q1",
                "evidence": "A clear brown bird is the central focus",
                "is_main_subject": True,
                "completed": True,
            },
            {
                "id": "q2",
                "evidence": "Leaves in distant background blur",
                "is_main_subject": False,  # Background leaf: must NOT complete quest
                "completed": True,
            },
            {
                "id": "q3",
                "evidence": "short",  # len <= 10: must NOT complete quest
                "is_main_subject": True,
                "completed": True,
            },
        ],
    }

    monkeypatch.setattr(
        server,
        "ollama_chat",
        lambda *args, **kwargs: json.dumps(model_response),
    )

    result = server.check_photo(simple_jpeg_bytes, quests)
    assert result["main_subject"] == "A bird"
    assert len(result["completed"]) == 1
    assert result["completed"][0]["id"] == "q1"
    assert "clear brown bird" in result["completed"][0]["evidence"]


def test_check_photo_rejects_unregistered_quest_ids(monkeypatch, simple_jpeg_bytes):
    quests = [{"id": "q1", "text": "A bird"}]
    hallucinated_response = {
        "what_i_see": "A scene",
        "main_subject": "Unknown",
        "checks": [
            {
                "id": "q99_hallucinated",
                "evidence": "The model invented this quest ID",
                "is_main_subject": True,
                "completed": True,
            }
        ],
    }
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: json.dumps(hallucinated_response))
    result = server.check_photo(simple_jpeg_bytes, quests)
    assert len(result["completed"]) == 0


def test_check_photo_deduplicates_duplicate_checks_in_same_photo(monkeypatch, simple_jpeg_bytes):
    quests = [{"id": "q1", "text": "A bird"}]
    duplicate_checks = {
        "what_i_see": "A bird",
        "main_subject": "A bird",
        "checks": [
            {"id": "q1", "evidence": "First evidence describing bird", "is_main_subject": True, "completed": True},
            {"id": "q1", "evidence": "Second evidence describing bird", "is_main_subject": True, "completed": True},
        ],
    }
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: json.dumps(duplicate_checks))
    result = server.check_photo(simple_jpeg_bytes, quests)
    assert len(result["completed"]) == 1


def test_check_photo_handles_malformed_json_gracefully(monkeypatch, simple_jpeg_bytes):
    """When Ollama returns invalid JSON, check_photo fails safely without unhandled exceptions."""
    quests = [{"id": "q1", "text": "A bird"}]
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: "THIS IS NOT JSON {{{")
    result = server.check_photo(simple_jpeg_bytes, quests)
    assert isinstance(result, dict)
    assert result["completed"] == []
    assert result["what_i_see"] == ""


def test_check_photo_handles_non_dict_json(monkeypatch, simple_jpeg_bytes):
    """When Ollama returns a list or primitive instead of a JSON object."""
    quests = [{"id": "q1", "text": "A bird"}]
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: json.dumps(["not", "an", "object"]))
    result = server.check_photo(simple_jpeg_bytes, quests)
    assert isinstance(result, dict)
    assert result["completed"] == []


def test_check_photo_handles_corrupted_checks_array(monkeypatch, simple_jpeg_bytes):
    """When checks contains non-dict elements or is not a list."""
    quests = [{"id": "q1", "text": "A bird"}]
    corrupted = {
        "what_i_see": "A scene",
        "main_subject": "A subject",
        "checks": ["not a dict", None, 42],
    }
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: json.dumps(corrupted))
    result = server.check_photo(simple_jpeg_bytes, quests)
    assert isinstance(result, dict)
    assert result["completed"] == []
    assert result["what_i_see"] == "A scene"
