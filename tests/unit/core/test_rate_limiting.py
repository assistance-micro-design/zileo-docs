"""Tests unitaires pour la configuration du rate limiting."""

from __future__ import annotations

import pytest

from src.core.config import Settings


class TestRateLimitConfig:
    """Tests pour les settings de rate limiting."""

    def test_default_rate_limit(self) -> None:
        settings = Settings(MISTRAL_API_KEY="test")
        assert settings.RATE_LIMIT_DEFAULT == "60/minute"

    def test_index_rate_limit(self) -> None:
        settings = Settings(MISTRAL_API_KEY="test")
        assert settings.RATE_LIMIT_INDEX == "10/minute"

    def test_mcp_rate_limit(self) -> None:
        settings = Settings(MISTRAL_API_KEY="test")
        assert settings.RATE_LIMIT_MCP == "30/minute"

    def test_search_rate_limit(self) -> None:
        settings = Settings(MISTRAL_API_KEY="test")
        assert settings.RATE_LIMIT_SEARCH == "30/minute"

    def test_rate_limit_configurable_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RATE_LIMIT_INDEX", "5/minute")
        monkeypatch.setenv("MISTRAL_API_KEY", "test")
        settings = Settings()
        assert settings.RATE_LIMIT_INDEX == "5/minute"


class TestRateLimitMiddleware:
    """Tests pour la presence du middleware dans l'app."""

    def test_limiter_on_app_state(self) -> None:
        from src.main import create_app

        app = create_app()
        assert hasattr(app.state, "limiter")
