"""Tests unitaires pour les routes search."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app


@pytest.fixture
def mock_embedder():
    """Mock de l'embedder."""
    embedder = AsyncMock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
    return embedder


@pytest.fixture
def mock_vector_store():
    """Mock du vector store."""
    return AsyncMock()


@pytest.fixture
def search_results() -> list[dict[str, Any]]:
    """Resultats de recherche simules."""
    return [
        {
            "chunk_id": "c1",
            "document_id": "doc-1",
            "content": "Contenu pertinent.",
            "content_preview": "Contenu",
            "score": 0.9,
            "page_numbers": [1],
            "section_title": "Section",
            "content_type": "text",
            "doc_filename": "test.pdf",
        },
    ]


@pytest.fixture
def app(mock_embedder, mock_vector_store, search_results):
    """Application avec mocks."""
    app = create_app()

    from src.api.dependencies import get_embedder, get_vector_store

    mock_vector_store.search = AsyncMock(return_value=search_results)
    app.dependency_overrides[get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_vector_store] = lambda: mock_vector_store
    return app


@pytest.fixture
async def client(app):
    """Client HTTP de test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestSearchPost:
    """Tests pour POST /api/v1/search."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/search",
            json={"query": "test query", "top_k": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1
        assert data["query"] == "test query"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/search",
            json={"query": ""},
        )

        assert response.status_code == 422


class TestSearchGet:
    """Tests pour GET /api/v1/search."""

    @pytest.mark.asyncio
    async def test_search_get(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/search?q=test+query")

        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1

    @pytest.mark.asyncio
    async def test_search_get_missing_query(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/search")

        assert response.status_code == 422
