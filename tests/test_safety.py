"""Safety filter and hazard mitigation tests for WildStep AI."""
import re
import server


def test_clearly_safe_outdoor_items_pass():
    safe_samples = [
        "A yellow leaf on the grass",
        "A cloud shaped like a rabbit",
        "Tree bark with deep ridges",
        "A puddle reflecting the sky",
        "A feather on a trail",
    ]
    for text in safe_samples:
        assert not server.UNSAFE.search(text), f"Falsely flagged safe item: {text}"


def test_unsafe_terms_blocked():
    unsafe_keywords = [
        "climb", "cliff", "edge", "swim", "wade", "enter the water",
        "touch", "pick", "eat", "taste", "feed", "pet", "chase",
        "snake", "trespass", "private", "night", "alone", "road",
        "highway", "rail", "track"
    ]
    for kw in unsafe_keywords:
        sample = f"Find a {kw} outdoors"
        assert server.UNSAFE.search(sample), f"Failed to catch unsafe term: {kw}"


def test_mixed_case_unsafe_terms_blocked():
    samples = [
        "CLIMB a tall tree",
        "swiMMinG in the river",
        "TReSpAss on the property",
        "EAT a wild plant",
        "WaDe into deep water",
    ]
    for text in samples:
        assert server.UNSAFE.search(text), f"Failed mixed-case check: {text}"


def test_punctuation_variants_blocked():
    samples = [
        "Climb! the wall",
        "Walk near the cliff...",
        "Try to (swim) here",
        "Do you eat/taste this leaf?",
        "Cross the highway; hurry",
    ]
    for text in samples:
        assert server.UNSAFE.search(text), f"Failed punctuation check: {text}"


def test_empty_and_whitespace_items():
    for text in ["", "   ", "\t\n  "]:
        cleaned = re.sub(r"[^\w\s,'()/:-]+", "", str(text)).strip().rstrip(".")
        assert not cleaned, f"Expected empty result for '{text}'"


def test_multiple_unsafe_terms_blocked():
    sample = "Climb the cliff, swim across, and pick mushrooms to eat"
    assert server.UNSAFE.search(sample)


def test_mushroom_and_fungi_get_photo_only_disclaimer():
    items = [
        "A red mushroom",
        "Fungus on fallen log",
        "Tree fungi growth",
        "Wild berries on branch",
    ]
    for text in items:
        assert server.PHOTO_ONLY.search(text), f"PHOTO_ONLY missed: {text}"


def test_nests_and_eggs_get_photo_only_disclaimer():
    items = [
        "A bird nest high in a tree",
        "Fallen robin eggs on path",
    ]
    for text in items:
        assert server.PHOTO_ONLY.search(text), f"PHOTO_ONLY missed: {text}"


def test_dont_touch_disclaimer_is_permitted():
    # "don't touch" is a safety disclaimer, so it should not be treated as a command to touch
    text = "Look at the smooth stone (don't touch)"
    checked = re.sub(r"\b(don'?t|do not|without|no)\s+touch\w*", "", text, flags=re.I)
    assert not server.UNSAFE.search(checked), "Mistakenly blocked safety disclaimer 'don't touch'"


def test_direct_touch_command_is_blocked():
    text = "Touch the soft green moss"
    checked = re.sub(r"\b(don'?t|do not|without|no)\s+touch\w*", "", text, flags=re.I)
    assert server.UNSAFE.search(checked), "Failed to block direct command to touch"


def test_safe_pool_replacement_when_all_model_quests_are_unsafe(monkeypatch):
    """If model outputs 6 unsafe quests, all 6 must be replaced from SAFE_POOL."""
    unsafe_model_output = '{"title": "Hazardous Walk", "quests": [' + ",".join([
        '{"text": "Climb high cliff", "emoji": "🧗", "points": 20}',
        '{"text": "Swim across river", "emoji": "🏊", "points": 25}',
        '{"text": "Pick wild berries", "emoji": "🍓", "points": 15}',
        '{"text": "Feed stray dog", "emoji": "🐕", "points": 10}',
        '{"text": "Trespass on private track", "emoji": "🚫", "points": 30}',
        '{"text": "Walk on railway line", "emoji": "🚂", "points": 20}'
    ]) + ']}'

    monkeypatch.setattr(server, "ollama_chat", lambda *a, **kw: unsafe_model_output)
    result = server.make_quests("Park", "October", "solo")

    assert len(result["quests"]) == 6
    # None of the final quests should contain any unsafe terms
    for q in result["quests"]:
        checked = re.sub(r"\b(don'?t|do not|without|no)\s+touch\w*", "", q["text"], flags=re.I)
        assert not server.UNSAFE.search(checked), f"Unsafe quest leaked through: {q['text']}"
        assert q["id"].startswith("q")
        assert 5 <= q["points"] <= 30
