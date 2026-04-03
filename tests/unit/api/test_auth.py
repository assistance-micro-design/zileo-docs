"""Tests unitaires pour l'authentification API."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app


@pytest.fixture
def app():
    """Application FastAPI de test."""
    return create_app()


@pytest.fixture
async def client(app):
    """Client HTTP de test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestApiKeyAuth:
    """Tests pour le middleware d'authentification X-API-Key."""

    @pytest.mark.asyncio
    async def test_no_auth_required_when_api_key_empty(self, client: AsyncClient) -> None:
        """Sans API_KEY configuree, les endpoints sont accessibles."""
        with patch("src.api.auth.settings") as mock_settings:
            mock_settings.API_KEY = ""
            response = await client.get("/health/live")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_401_when_api_key_required_but_missing(self, client: AsyncClient) -> None:
        """Avec API_KEY configuree, un header manquant donne 401."""
        with patch("src.api.auth.settings") as mock_settings:
            mock_settings.API_KEY = "test-secret-key"
            response = await client.get("/api/v1/search?query=test")

        assert response.status_code == 401
        assert "X-API-Key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_403_when_api_key_invalid(self, client: AsyncClient) -> None:
        """Avec API_KEY configuree, une mauvaise cle donne 403."""
        with patch("src.api.auth.settings") as mock_settings:
            mock_settings.API_KEY = "test-secret-key"
            response = await client.get(
                "/api/v1/search?query=test",
                headers={"X-API-Key": "wrong-key"},
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_health_accessible_without_api_key(self, client: AsyncClient) -> None:
        """Les endpoints health ne sont pas proteges par l'auth."""
        with patch("src.api.auth.settings") as mock_settings:
            mock_settings.API_KEY = "test-secret-key"
            response = await client.get("/health/live")

        assert response.status_code == 200
