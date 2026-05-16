"""Tests unitaires pour les routes health."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app


@pytest.fixture
def app():
    """Application FastAPI de test."""
    from src.api.auth import verify_api_key

    app = create_app()
    app.dependency_overrides[verify_api_key] = lambda: None
    return app


@pytest.fixture
async def client(app):
    """Client HTTP de test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthRoutes:
    """Tests pour les endpoints health."""

    @pytest.mark.asyncio
    async def test_liveness(self, client: AsyncClient) -> None:
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    @pytest.mark.asyncio
    async def test_readiness_qdrant_healthy(self, client: AsyncClient) -> None:
        with patch(
            "src.api.routes.health._check_qdrant",
            new_callable=AsyncMock,
            return_value="healthy",
        ):
            response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    @pytest.mark.asyncio
    async def test_readiness_qdrant_unhealthy(self, client: AsyncClient) -> None:
        with patch(
            "src.api.routes.health._check_qdrant",
            new_callable=AsyncMock,
            return_value="unhealthy",
        ):
            response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient) -> None:
        with (
            patch(
                "src.api.routes.health._check_qdrant",
                new_callable=AsyncMock,
                return_value="healthy",
            ),
            patch(
                "src.api.routes.health._check_mistral_config",
                return_value="healthy",
            ),
        ):
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, client: AsyncClient) -> None:
        with (
            patch(
                "src.api.routes.health._check_qdrant",
                new_callable=AsyncMock,
                return_value="unhealthy",
            ),
            patch(
                "src.api.routes.health._check_mistral_config",
                return_value="healthy",
            ),
        ):
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "degraded"


class TestHealthRateLimit:
    """Tests S2a: GET /health doit etre rate-limite, /live et /ready ne le sont pas."""

    def test_health_check_has_rate_limit(self) -> None:
        from src.api.routes.health import limiter

        assert "src.api.routes.health.health_check" in limiter._route_limits

    def test_liveness_not_rate_limited(self) -> None:
        from src.api.routes.health import limiter

        assert "src.api.routes.health.liveness" not in limiter._route_limits

    def test_readiness_not_rate_limited(self) -> None:
        from src.api.routes.health import limiter

        assert "src.api.routes.health.readiness" not in limiter._route_limits
