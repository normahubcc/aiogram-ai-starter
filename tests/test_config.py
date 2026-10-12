"""Tests for bot configuration and environment variable loading."""

import pytest
from pydantic import ValidationError

from bot.config import BotConfig


def test_config_minimal_valid(monkeypatch):
    """Test successful configuration loading with required credentials."""
    monkeypatch.setenv("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setenv("NORMAHUB_API_KEY", "nr_hub_testkey123456789")

    config = BotConfig()

    assert config.bot_token.get_secret_value() == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert config.normahub_api_key.get_secret_value() == "nr_hub_testkey123456789"
    # Ensure tokens are masked in str / repr
    assert "nr_hub_testkey" not in str(config.normahub_api_key)
    assert "ABC-DEF" not in str(config.bot_token)

    # Check defaults
    assert config.normahub_base_url == "https://api.normahub.cc/v1"
    assert config.default_model == "deepseek-v4.1-flash"
    assert config.stream_debounce_interval == 0.8
    assert config.max_context_turns == 10
    assert config.rate_limit_per_second == 1.0


def test_config_missing_required(monkeypatch):
    """Test validation failure when required credentials are missing."""
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("NORMAHUB_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        BotConfig(_env_file=None)


def test_config_base_url_trailing_slash_stripped(monkeypatch):
    """Test that trailing slashes are cleanly stripped from base URL."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")
    monkeypatch.setenv("NORMAHUB_API_KEY", "fake_key")
    monkeypatch.setenv("NORMAHUB_BASE_URL", "https://api.normahub.cc/v1///")

    config = BotConfig()
    assert config.normahub_base_url == "https://api.normahub.cc/v1"


def test_config_log_level_validation(monkeypatch):
    """Test log level normalization and invalid input rejection."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")
    monkeypatch.setenv("NORMAHUB_API_KEY", "fake_key")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    config = BotConfig()
    assert config.log_level == "DEBUG"

    monkeypatch.setenv("LOG_LEVEL", "INVALID_LEVEL")
    with pytest.raises(ValidationError):
        BotConfig()


def test_config_admin_check(monkeypatch):
    """Test administrator ID verification helper."""
    monkeypatch.setenv("BOT_TOKEN", "fake_token")
    monkeypatch.setenv("NORMAHUB_API_KEY", "fake_key")

    config = BotConfig(admin_user_ids=[100, 200, 300])
    assert config.is_admin(100) is True
    assert config.is_admin(200) is True
    assert config.is_admin(999) is False
