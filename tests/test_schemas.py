"""JSON Schema contract and validation tests for WildStep AI."""
import pytest
import jsonschema
import server


def test_quest_schema_accepts_valid_data():
    valid = {
        "title": "Autumn Discovery Walk",
        "quests": [
            {"text": "A fallen acorn", "emoji": "🌰", "points": 10},
            {"text": "A yellow leaf", "emoji": "🍂", "points": 10},
            {"text": "A robin", "emoji": "🐦", "points": 15},
            {"text": "A spider web", "emoji": "🕸️", "points": 20},
            {"text": "Tree bark texture", "emoji": "🌳", "points": 15},
            {"text": "A cloud shape", "emoji": "☁️", "points": 10},
        ],
    }
    jsonschema.validate(instance=valid, schema=server.QUEST_SCHEMA)


def test_quest_schema_rejects_missing_title():
    invalid = {
        "quests": [
            {"text": "Item", "emoji": "🌳", "points": 10} for _ in range(6)
        ]
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=server.QUEST_SCHEMA)


def test_quest_schema_rejects_wrong_quest_count():
    # Only 5 items (schema requires minItems=6, maxItems=6)
    invalid_5 = {
        "title": "Short Hunt",
        "quests": [{"text": f"Item {i}", "emoji": "🌳", "points": 10} for i in range(5)],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_5, schema=server.QUEST_SCHEMA)

    # 7 items
    invalid_7 = {
        "title": "Long Hunt",
        "quests": [{"text": f"Item {i}", "emoji": "🌳", "points": 10} for i in range(7)],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_7, schema=server.QUEST_SCHEMA)


def test_quest_schema_rejects_invalid_field_types():
    invalid_types = {
        "title": 12345,  # title should be string
        "quests": [
            {"text": "Item", "emoji": "🌳", "points": "ten"}  # points should be integer
            for _ in range(6)
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_types, schema=server.QUEST_SCHEMA)


def test_check_schema_accepts_valid_vision_output():
    ids = ["q1", "q2", "q3"]
    schema = server.check_schema(ids)
    valid_output = {
        "what_i_see": "A Common Myna perched on a grassy field.",
        "main_subject": "A bird (Common Myna)",
        "checks": [
            {"id": "q1", "evidence": "A clear brown bird is in the center", "is_main_subject": True, "completed": True},
            {"id": "q2", "evidence": "No leaf is in focus", "is_main_subject": False, "completed": False},
            {"id": "q3", "evidence": "No running water visible", "is_main_subject": False, "completed": False},
        ],
    }
    jsonschema.validate(instance=valid_output, schema=schema)


def test_check_schema_rejects_unlisted_quest_id():
    ids = ["q1", "q2"]
    schema = server.check_schema(ids)
    invalid_id = {
        "what_i_see": "Photo description",
        "main_subject": "Subject",
        "checks": [
            {"id": "q1", "evidence": "Present", "is_main_subject": True, "completed": True},
            {"id": "q999_fake", "evidence": "Unknown ID", "is_main_subject": False, "completed": False},
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_id, schema=schema)


def test_check_schema_rejects_missing_required_fields():
    ids = ["q1"]
    schema = server.check_schema(ids)
    missing_subject = {
        "what_i_see": "A photo of grass",
        # missing "main_subject"
        "checks": [
            {"id": "q1", "evidence": "Leaves in background", "is_main_subject": False, "completed": False}
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=missing_subject, schema=schema)
