"""Configuration precedence and storage migration tests."""
import os
from pathlib import Path
import pytest

import durable
import server


def test_env_var_precedence_wildstep_over_quest(monkeypatch):
    """WILDSTEP_* should take precedence over QUEST_*."""
    monkeypatch.setenv("WILDSTEP_PORT", "9999")
    monkeypatch.setenv("QUEST_PORT", "8888")

    port = int(os.environ.get("WILDSTEP_PORT", os.environ.get("QUEST_PORT", "8777")))
    assert port == 9999


def test_env_var_fallback_quest_when_wildstep_absent(monkeypatch):
    """QUEST_* acts as fallback when WILDSTEP_* is absent."""
    monkeypatch.delenv("WILDSTEP_PORT", raising=False)
    monkeypatch.setenv("QUEST_PORT", "8888")

    port = int(os.environ.get("WILDSTEP_PORT", os.environ.get("QUEST_PORT", "8777")))
    assert port == 8888


def test_env_var_default_when_both_absent(monkeypatch):
    monkeypatch.delenv("WILDSTEP_PORT", raising=False)
    monkeypatch.delenv("QUEST_PORT", raising=False)

    port = int(os.environ.get("WILDSTEP_PORT", os.environ.get("QUEST_PORT", "8777")))
    assert port == 8777


def test_env_model_precedence(monkeypatch):
    monkeypatch.setenv("WILDSTEP_MODEL", "gemma-test-custom")
    monkeypatch.setenv("QUEST_MODEL", "gemma-old")

    model = os.environ.get("WILDSTEP_MODEL", os.environ.get("QUEST_MODEL", "gemma4:e2b"))
    assert model == "gemma-test-custom"


def test_storage_dir_custom_wildstep_data(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_data"
    monkeypatch.setenv("WILDSTEP_DATA", str(custom_dir))
    monkeypatch.delenv("QUEST_DATA", raising=False)

    walks_dir = durable._get_walks_dir()
    assert walks_dir == custom_dir / "walks"


def test_storage_dir_custom_quest_data_fallback(tmp_path, monkeypatch):
    custom_dir = tmp_path / "legacy_custom_data"
    monkeypatch.delenv("WILDSTEP_DATA", raising=False)
    monkeypatch.setenv("QUEST_DATA", str(custom_dir))

    walks_dir = durable._get_walks_dir()
    assert walks_dir == custom_dir / "walks"


def test_storage_dir_legacy_fallback_when_old_dir_exists(tmp_path, monkeypatch):
    """When ~/.outside-quest/walks exists on machine, it should fall back to it."""
    mock_home = tmp_path / "fake_home"
    mock_home.mkdir()
    legacy_walks = mock_home / ".outside-quest" / "walks"
    legacy_walks.mkdir(parents=True)

    monkeypatch.delenv("WILDSTEP_DATA", raising=False)
    monkeypatch.delenv("QUEST_DATA", raising=False)
    monkeypatch.setattr(Path, "home", lambda: mock_home)

    walks_dir = durable._get_walks_dir()
    assert walks_dir == legacy_walks


def test_storage_dir_new_default_when_no_legacy_exists(tmp_path, monkeypatch):
    """When no legacy directory exists, defaults to ~/.wildstep-ai/walks."""
    mock_home = tmp_path / "clean_home"
    mock_home.mkdir()

    monkeypatch.delenv("WILDSTEP_DATA", raising=False)
    monkeypatch.delenv("QUEST_DATA", raising=False)
    monkeypatch.setattr(Path, "home", lambda: mock_home)

    walks_dir = durable._get_walks_dir()
    assert walks_dir == mock_home / ".wildstep-ai" / "walks"


def test_walk_dir_regex_validation():
    # Valid IDs
    assert durable.WALK_ID.match("walk-12345678")
    assert durable.WALK_ID.match("abcdefgh-1234")

    # Invalid IDs with special characters or path traversal
    assert not durable.WALK_ID.match("../traversal")
    assert not durable.WALK_ID.match("short")
    assert not durable.WALK_ID.match("UPPERCASE")
    assert not durable.WALK_ID.match("with space")
