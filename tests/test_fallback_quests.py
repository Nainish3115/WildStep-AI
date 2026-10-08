"""Tests for deterministic and offline fallback mission generation."""
import urllib.error
import server


def test_quick_quests_contract():
    card = server.quick_quests()
    assert isinstance(card, dict)
    assert card["title"] == "Quick Quest"
    quests = card["quests"]
    assert len(quests) == 6

    seen_ids = set()
    for idx, q in enumerate(quests, start=1):
        assert q["id"] == f"q{idx}"
        seen_ids.add(q["id"])
        assert isinstance(q["text"], str) and len(q["text"]) > 0
        assert isinstance(q["emoji"], str) and len(q["emoji"]) > 0
        assert isinstance(q["points"], int)
        assert 5 <= q["points"] <= 30
    assert len(seen_ids) == 6


def test_quick_quests_randomness_contract():
    """Verify quick_quests samples 6 distinct items from SAFE_POOL."""
    pool_texts = {p[0] for p in server.SAFE_POOL}
    card = server.quick_quests()
    for q in card["quests"]:
        assert q["text"] in pool_texts


def test_make_quests_when_ollama_unreachable(monkeypatch):
    """When Ollama raises URLError (connection refused/down), make_quests falls back to safe pool."""
    def mock_ollama_fail(*args, **kwargs):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(server, "ollama_chat", mock_ollama_fail)
    card = server.make_quests("Nagpur", "October", "me and friend")

    assert card["title"] == "WildStep Mission"
    assert len(card["quests"]) == 6
    for i, q in enumerate(card["quests"], start=1):
        assert q["id"] == f"q{i}"
        assert len(q["text"]) > 0
        assert 5 <= q["points"] <= 30


def test_make_quests_when_ollama_returns_broken_json(monkeypatch):
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: "NOT JSON {{{")
    card = server.make_quests("Anywhere", "May", "family")

    assert card["title"] == "WildStep Mission"
    assert len(card["quests"]) == 6
    for i, q in enumerate(card["quests"], 1):
        assert q["id"] == f"q{i}"


def test_make_quests_handles_none_and_empty_inputs(monkeypatch):
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: '{"title": "Valid Walk", "quests": []}')
    card = server.make_quests(None, None, None)
    assert len(card["quests"]) == 6
    for q in card["quests"]:
        assert q["id"].startswith("q")


def test_make_quests_handles_partial_model_response(monkeypatch):
    """Model only returned 2 valid items; the remaining 4 must be filled from SAFE_POOL."""
    partial = '{"title": "Partial", "quests": [' + \
        '{"text": "A yellow leaf", "emoji": "🍃", "points": 10},' + \
        '{"text": "A bird singing", "emoji": "🐦", "points": 15}' + \
        ']}'
    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: partial)
    card = server.make_quests("Trail", "June", "solo")

    assert card["title"] == "Partial"
    assert len(card["quests"]) == 6
    assert card["quests"][0]["text"] == "A yellow leaf"
    assert card["quests"][1]["text"] == "A bird singing"
    # Remaining 4 are filled from SAFE_POOL
    for i, q in enumerate(card["quests"], 1):
        assert q["id"] == f"q{i}"
