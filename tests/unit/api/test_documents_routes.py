# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour les routes documents."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app


@pytest.fixture
def mock_orchestrator():
    """Mock de l'orchestrateur."""
    orchestrator = AsyncMock()
    orchestrator.initialize = AsyncMock()

    mock_result = MagicMock()
    mock_result.analysis.metadata.document_id = "doc-test"
    mock_result.analysis.metadata.filename = "test.pdf"
    mock_result.analysis.metadata.total_pages = 5
    mock_result.pages_processed_native = 4
    mock_result.pages_processed_ocr = 1
    mock_result.chunks_generated = 10
    mock_result.chunks_embedded = 10
    mock_result.chunks_stored = 10
    mock_result.processing_time_seconds = 2.5
    mock_result.errors = []

    orchestrator.process_and_index = AsyncMock(return_value=mock_result)
    return orchestrator


@pytest.fixture
def mock_vector_store():
    """Mock du vector store."""
    store = AsyncMock()
    store.COLLECTION_NAME = "test_collection"
    return store


@pytest.fixture
def app(mock_orchestrator, mock_vector_store):
    """Application FastAPI avec mocks."""
    app = create_app()

    from src.api.auth import verify_api_key
    from src.api.dependencies import get_orchestrator, get_vector_store

    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[get_vector_store] = lambda: mock_vector_store
    app.dependency_overrides[verify_api_key] = lambda: None
    return app


@pytest.fixture
async def client(app):
    """Client HTTP de test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestGetDocument:
    """Tests pour GET /api/v1/documents/{document_id}."""

    @pytest.mark.asyncio
    async def test_get_existing_document(
        self, client: AsyncClient, mock_vector_store: AsyncMock
    ) -> None:
        chunks: list[dict[str, Any]] = [
            {
                "chunk_id": "c1",
                "doc_filename": "test.pdf",
                "doc_title": "Test",
                "doc_author": "Author",
                "doc_total_pages": 3,
                "ingested_at": "2026-01-01",
                "content_preview": "Preview",
                "page_numbers": [0],
                "section_title": "Intro",
                "content_type": "text",
            },
        ]
        mock_vector_store.get_document_chunks = AsyncMock(return_value=chunks)

        response = await client.get("/api/v1/documents/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert data["total_chunks"] == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(
        self, client: AsyncClient, mock_vector_store: AsyncMock
    ) -> None:
        mock_vector_store.get_document_chunks = AsyncMock(return_value=[])

        response = await client.get("/api/v1/documents/nonexistent")

        assert response.status_code == 404


class TestDeleteDocument:
    """Tests pour DELETE /api/v1/documents/{document_id}."""

    @pytest.mark.asyncio
    async def test_delete_document(self, client: AsyncClient, mock_vector_store: AsyncMock) -> None:
        mock_vector_store.delete_document = AsyncMock(return_value=5)

        response = await client.delete("/api/v1/documents/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["chunks_deleted"] == 5


class TestListStats:
    """Tests pour GET /api/v1/documents."""

    @pytest.mark.asyncio
    async def test_list_stats(self, client: AsyncClient, mock_vector_store: AsyncMock) -> None:
        mock_vector_store.get_stats = AsyncMock(
            return_value={"points_count": 100, "indexed_vectors_count": 100, "status": "green"}
        )

        response = await client.get("/api/v1/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["total_chunks"] == 100

    @pytest.mark.asyncio
    async def test_list_stats_unavailable(
        self, client: AsyncClient, mock_vector_store: AsyncMock
    ) -> None:
        mock_vector_store.get_stats = AsyncMock(side_effect=Exception("connection error"))

        response = await client.get("/api/v1/documents")

        assert response.status_code == 200
        assert response.json()["status"] == "unavailable"


class TestRateLimitDecorators:
    """Verifie que GET/DELETE et list_stats sont rate-limites via slowapi."""

    def test_get_document_has_rate_limit(self) -> None:
        from src.api.routes.documents import limiter

        assert "src.api.routes.documents.get_document" in limiter._route_limits

    def test_delete_document_has_rate_limit(self) -> None:
        from src.api.routes.documents import limiter

        assert "src.api.routes.documents.delete_document" in limiter._route_limits

    def test_list_stats_has_rate_limit(self) -> None:
        from src.api.routes.documents import limiter

        assert "src.api.routes.documents.list_stats" in limiter._route_limits
