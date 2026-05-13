"""Tests E2E pour le pipeline complet et l'API.

Ces tests verifient le fonctionnement de bout en bout:
- Endpoints API REST
- Serveur MCP JSON-RPC
- Pipeline complet d'extraction et indexation
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_embedder, get_orchestrator, get_vector_store
from src.core.config import settings
from src.core.exceptions import DocumentNotFoundError, EmptyQueryError, SourceFileNotFoundError
from src.main import app
from src.mcp.server import MCPServer
from src.mcp.tools.get_document import GetDocumentTool
from src.mcp.tools.index_document import IndexDocumentTool
from src.mcp.tools.read_document_content import ReadDocumentContentTool
from src.mcp.tools.search import SearchDocumentsTool
from src.services.pipeline.orchestrator import DocumentPipelineOrchestrator


if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Client de test FastAPI."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mcp_server_instance() -> MCPServer:
    """Instance du serveur MCP pour les tests."""
    return MCPServer()


# =============================================================================
# Tests: API Health
# =============================================================================


class TestHealthAPI:
    """Tests pour les endpoints de health check."""

    def test_root_returns_info(self, client: TestClient) -> None:
        """Test que la route racine retourne les infos du service."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "health" in data

    def test_health_endpoint_returns_status(self, client: TestClient) -> None:
        """Test que /health retourne un statut."""
        with patch(
            "src.api.routes.health._check_qdrant",
            new_callable=AsyncMock,
            return_value="healthy",
        ):
            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert "status" in data
            assert "version" in data
            assert "qdrant_status" in data
            assert "mistral_status" in data

    def test_liveness_returns_alive(self, client: TestClient) -> None:
        """Test que /health/live retourne alive."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_check(self, client: TestClient) -> None:
        """Test que /health/ready verifie les dependances."""
        with patch(
            "src.api.routes.health._check_qdrant",
            new_callable=AsyncMock,
            return_value="healthy",
        ):
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["ready", "not_ready"]


# =============================================================================
# Tests: API Documents
# =============================================================================


class TestDocumentsAPI:
    """Tests pour les endpoints de documents."""

    def test_index_requires_pdf_file(self, client: TestClient) -> None:
        """Test que l'indexation rejette les fichiers non-PDF."""
        response = client.post(
            "/api/v1/documents/index",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_index_rejects_empty_file(self, client: TestClient) -> None:
        """Test que l'indexation rejette les fichiers vides."""
        response = client.post(
            "/api/v1/documents/index",
            files={"file": ("test.pdf", b"", "application/pdf")},
        )
        # Un PDF vide n'est pas valide
        assert response.status_code in [400, 500]

    def test_index_pdf_success(
        self,
        client: TestClient,
        sample_text_pdf: Path,
    ) -> None:
        """Test l'indexation reussie d'un PDF."""
        # Mock de l'orchestrateur
        mock_orchestrator = AsyncMock()
        mock_result = MagicMock()
        mock_result.analysis.metadata.document_id = "test-doc-id"
        mock_result.analysis.metadata.total_pages = 2
        mock_result.pages_processed_native = 2
        mock_result.pages_processed_ocr = 0
        mock_result.chunks_generated = 5
        mock_result.chunks_embedded = 5
        mock_result.chunks_stored = 5
        mock_result.processing_time_seconds = 1.5
        mock_result.errors = []

        mock_orchestrator.initialize = AsyncMock()
        mock_orchestrator.process_and_index = AsyncMock(return_value=mock_result)

        mock_store = MagicMock()
        mock_store.initialize = AsyncMock()

        app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
        app.dependency_overrides[get_vector_store] = lambda: mock_store

        try:
            with Path(sample_text_pdf).open("rb") as f:
                response = client.post(
                    "/api/v1/documents/index",
                    files={"file": ("test.pdf", f, "application/pdf")},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert "document_id" in data
            assert "chunks_stored" in data
        finally:
            app.dependency_overrides.pop(get_orchestrator, None)
            app.dependency_overrides.pop(get_vector_store, None)

    def test_get_document_stats(self, client: TestClient) -> None:
        """Test la recuperation des statistiques."""
        with patch("src.api.dependencies.get_vector_store") as mock_get_store:
            mock_store = AsyncMock()
            mock_store.COLLECTION_NAME = "documents"
            mock_store.get_stats = AsyncMock(
                return_value={
                    "points_count": 100,
                    "indexed_vectors_count": 100,
                    "status": "green",
                }
            )
            mock_get_store.return_value = mock_store

            response = client.get("/api/v1/documents")
            assert response.status_code == 200
            data = response.json()
            assert "collection" in data


# =============================================================================
# Tests: API Search
# =============================================================================


class TestSearchAPI:
    """Tests pour les endpoints de recherche."""

    def test_search_requires_query(self, client: TestClient) -> None:
        """Test que la recherche exige une requete."""
        response = client.get("/api/v1/search")
        # Query parameter 'q' is required
        assert response.status_code == 422

    def test_search_get_with_query(self, client: TestClient) -> None:
        """Test la recherche GET avec une requete."""
        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

        # Mock vector store
        mock_store = MagicMock()
        mock_store.search = AsyncMock(
            return_value=[
                {
                    "chunk_id": "chunk-1",
                    "document_id": "doc-1",
                    "content": "Test content",
                    "content_preview": "Test...",
                    "score": 0.95,
                    "page_numbers": [1],
                    "section_title": "Test Section",
                    "content_type": "text",
                    "doc_filename": "test.pdf",
                }
            ]
        )

        # Override dependencies
        app.dependency_overrides[get_embedder] = lambda: mock_embedder
        app.dependency_overrides[get_vector_store] = lambda: mock_store

        try:
            response = client.get("/api/v1/search?q=test%20query")
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert data["query"] == "test query"
        finally:
            # Clean up overrides
            app.dependency_overrides.clear()

    def test_search_post_with_body(self, client: TestClient) -> None:
        """Test la recherche POST avec un corps JSON."""
        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

        # Mock vector store
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        # Override dependencies
        app.dependency_overrides[get_embedder] = lambda: mock_embedder
        app.dependency_overrides[get_vector_store] = lambda: mock_store

        try:
            response = client.post(
                "/api/v1/search",
                json={
                    "query": "test query",
                    "top_k": 10,
                    "score_threshold": 0.5,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_results"] == 0
        finally:
            # Clean up overrides
            app.dependency_overrides.clear()


# =============================================================================
# Tests: MCP Server
# =============================================================================


class TestMCPServer:
    """Tests pour le serveur MCP."""

    def test_mcp_server_initialization(self, mcp_server_instance: MCPServer) -> None:
        """Test l'initialisation du serveur MCP."""
        assert mcp_server_instance.name is not None
        assert mcp_server_instance.version is not None
        assert len(mcp_server_instance.tools) == 11

    def test_mcp_tools_registered(self, mcp_server_instance: MCPServer) -> None:
        """Test que tous les tools sont enregistres."""
        expected_tools = [
            "create_excel_document",
            "edit_excel_document",
            "inspect_generated_file",
            "index_document",
            "search_documents",
            "get_document",
            "delete_document",
            "list_indexed_documents",
            "list_available_documents",
            "get_excel_formulas",
            "read_document_content",
        ]
        for tool_name in expected_tools:
            assert tool_name in mcp_server_instance.tools

    @pytest.mark.asyncio
    async def test_mcp_invalid_jsonrpc_version(self, mcp_server_instance: MCPServer) -> None:
        """Test le rejet de version JSON-RPC invalide."""
        response = await mcp_server_instance.handle_request(
            {
                "jsonrpc": "1.0",
                "method": "tools/list",
                "id": 1,
            }
        )
        assert "error" in response
        assert response["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_mcp_missing_method(self, mcp_server_instance: MCPServer) -> None:
        """Test le rejet de requete sans methode."""
        response = await mcp_server_instance.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
            }
        )
        assert "error" in response
        assert response["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_mcp_unknown_method(self, mcp_server_instance: MCPServer) -> None:
        """Test le rejet de methode inconnue."""
        response = await mcp_server_instance.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "unknown/method",
                "id": 1,
            }
        )
        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_mcp_tools_list(self, mcp_server_instance: MCPServer) -> None:
        """Test la liste des tools."""
        response = await mcp_server_instance.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1,
            }
        )
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 11

    @pytest.mark.asyncio
    async def test_mcp_initialize(self, mcp_server_instance: MCPServer) -> None:
        """Test l'initialisation MCP."""
        with patch.object(mcp_server_instance, "initialize", new_callable=AsyncMock):
            response = await mcp_server_instance.handle_request(
                {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {},
                    "id": 1,
                }
            )
            assert "result" in response
            assert "protocolVersion" in response["result"]
            assert "serverInfo" in response["result"]

    @pytest.mark.asyncio
    async def test_mcp_tools_call_unknown_tool(self, mcp_server_instance: MCPServer) -> None:
        """Test l'appel d'un tool inconnu."""
        response = await mcp_server_instance.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "unknown_tool",
                    "arguments": {},
                },
                "id": 1,
            }
        )
        assert "error" in response
        assert response["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_mcp_tools_call_missing_name(self, mcp_server_instance: MCPServer) -> None:
        """Test l'appel sans nom de tool."""
        response = await mcp_server_instance.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "arguments": {},
                },
                "id": 1,
            }
        )
        assert "error" in response
        assert response["error"]["code"] == -32602


# =============================================================================
# Tests: MCP Endpoint Integration
# =============================================================================


class TestMCPEndpoint:
    """Tests pour l'endpoint MCP via HTTP."""

    def test_mcp_endpoint_tools_list(self, client: TestClient) -> None:
        """Test l'endpoint /mcp pour lister les tools."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data or "error" in data

    def test_mcp_endpoint_invalid_json(self, client: TestClient) -> None:
        """Test l'endpoint /mcp avec JSON invalide."""
        response = client.post(
            "/mcp",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32700


# =============================================================================
# Tests: MCP Tools
# =============================================================================


class TestMCPTools:
    """Tests pour les tools MCP individuels."""

    @pytest.mark.asyncio
    async def test_index_document_tool_file_not_found(self) -> None:
        """Test que index_document leve une erreur si fichier introuvable."""
        tool = IndexDocumentTool()
        tool._initialized = True
        with (
            patch.object(settings, "DOCUMENTS_PATH", "/app/documents"),
            pytest.raises(SourceFileNotFoundError),
        ):
            await tool.execute({"file_path": "/app/documents/nonexistent/file.pdf"})

    @pytest.mark.asyncio
    async def test_search_tool_empty_query(self) -> None:
        """Test que search rejette une requete vide."""
        tool = SearchDocumentsTool()
        with patch.object(tool, "_vector_store"):
            tool._initialized = True
            with pytest.raises(EmptyQueryError):
                await tool.execute({"query": "  "})

    @pytest.mark.asyncio
    async def test_get_document_tool_not_found(self) -> None:
        """Test que get_document leve une erreur si document introuvable."""
        tool = GetDocumentTool()

        # Mock le vector store
        mock_store = AsyncMock()
        mock_store.get_document_chunks = AsyncMock(return_value=[])
        mock_store.initialize = AsyncMock()
        tool._vector_store = mock_store
        tool._initialized = True

        with pytest.raises(DocumentNotFoundError):
            await tool.execute({"document_id": "nonexistent-doc"})

    @pytest.mark.asyncio
    async def test_read_document_content_tool_not_found(self) -> None:
        """Test que read_document_content leve une erreur si document introuvable."""
        tool = ReadDocumentContentTool()

        mock_store = AsyncMock()
        mock_store.get_document_chunks = AsyncMock(return_value=[])
        mock_store.initialize = AsyncMock()
        tool._vector_store = mock_store
        tool._initialized = True

        with pytest.raises(DocumentNotFoundError):
            await tool.execute({"document_id": "nonexistent-doc"})

    @pytest.mark.asyncio
    async def test_read_document_content_tool_success(self) -> None:
        """Test la lecture reussie d'un document."""
        tool = ReadDocumentContentTool()

        mock_chunks = [
            {
                "chunk_id": "chunk-1",
                "chunk_index": 0,
                "content": "# Title\n\nFirst paragraph.",
                "page_numbers": [0],
                "doc_filename": "test.pdf",
                "doc_total_pages": 2,
                "token_count": 25,
                "char_count": 75,
            },
            {
                "chunk_id": "chunk-2",
                "chunk_index": 1,
                "content": "## Section\n\nSecond paragraph.",
                "page_numbers": [1],
                "doc_filename": "test.pdf",
                "doc_total_pages": 2,
                "token_count": 30,
                "char_count": 90,
            },
        ]

        mock_store = AsyncMock()
        mock_store.get_document_chunks = AsyncMock(return_value=mock_chunks)
        mock_store.initialize = AsyncMock()
        tool._vector_store = mock_store
        tool._initialized = True

        result = await tool.execute({"document_id": "doc-test"})

        assert result["document_id"] == "doc-test"
        assert result["filename"] == "test.pdf"
        assert result["total_pages"] == 2
        assert result["total_chunks"] == 2
        assert result["total_tokens"] == 55
        assert "# Title" in result["content"]
        assert "## Section" in result["content"]

    @pytest.mark.asyncio
    async def test_read_document_content_with_page_filter(self) -> None:
        """Test la lecture avec filtrage par pages."""
        tool = ReadDocumentContentTool()

        mock_chunks = [
            {
                "chunk_id": "chunk-1",
                "chunk_index": 0,
                "content": "Page 1 content",
                "page_numbers": [0],
                "doc_filename": "test.pdf",
                "doc_total_pages": 3,
                "token_count": 10,
                "char_count": 30,
            },
            {
                "chunk_id": "chunk-2",
                "chunk_index": 1,
                "content": "Page 2 content",
                "page_numbers": [1],
                "doc_filename": "test.pdf",
                "doc_total_pages": 3,
                "token_count": 10,
                "char_count": 30,
            },
            {
                "chunk_id": "chunk-3",
                "chunk_index": 2,
                "content": "Page 3 content",
                "page_numbers": [2],
                "doc_filename": "test.pdf",
                "doc_total_pages": 3,
                "token_count": 10,
                "char_count": 30,
            },
        ]

        mock_store = AsyncMock()
        mock_store.get_document_chunks = AsyncMock(return_value=mock_chunks)
        mock_store.initialize = AsyncMock()
        tool._vector_store = mock_store
        tool._initialized = True

        result = await tool.execute(
            {
                "document_id": "doc-test",
                "page_start": 2,
                "page_end": 2,
            }
        )

        assert result["chunks_returned"] == 1
        assert result["pages_returned"] == [2]
        assert "Page 2 content" in result["content"]
        assert "Page 1 content" not in result["content"]
        assert "Page 3 content" not in result["content"]

    @pytest.mark.asyncio
    async def test_read_document_content_with_chunks_detail(self) -> None:
        """Test la lecture avec details des chunks."""
        tool = ReadDocumentContentTool()

        mock_chunks = [
            {
                "chunk_id": "chunk-1",
                "chunk_index": 0,
                "content": "Content with table",
                "page_numbers": [0],
                "doc_filename": "test.pdf",
                "doc_total_pages": 1,
                "section_title": "Introduction",
                "content_type": "text",
                "token_count": 15,
                "char_count": 45,
                "has_table": True,
                "has_image": False,
            },
        ]

        mock_store = AsyncMock()
        mock_store.get_document_chunks = AsyncMock(return_value=mock_chunks)
        mock_store.initialize = AsyncMock()
        tool._vector_store = mock_store
        tool._initialized = True

        result = await tool.execute(
            {
                "document_id": "doc-test",
                "include_chunks_detail": True,
            }
        )

        assert "chunks_detail" in result
        assert len(result["chunks_detail"]) == 1
        detail = result["chunks_detail"][0]
        assert detail["chunk_index"] == 0
        assert detail["page_numbers"] == [1]
        assert detail["section_title"] == "Introduction"
        assert detail["has_table"] is True
        assert detail["has_image"] is False


# =============================================================================
# Tests: Integration Pipeline
# =============================================================================


class TestPipelineIntegration:
    """Tests d'integration du pipeline complet."""

    @pytest.mark.asyncio
    async def test_full_pipeline_mock(self, sample_text_pdf: Path) -> None:
        """Test du pipeline complet avec mocks."""
        orchestrator = DocumentPipelineOrchestrator()

        # Patcher les services externes
        with (
            patch.object(orchestrator, "_ocr_processor", create=True) as mock_ocr,
            patch.object(orchestrator, "_embedder", create=True) as mock_embedder,
            patch.object(orchestrator, "_vector_store", create=True) as mock_store,
        ):
            # Configurer les mocks
            mock_ocr.process_pages = AsyncMock(return_value={})
            mock_embedder.embed_chunks = AsyncMock(side_effect=lambda x, **_kwargs: x)
            mock_store.initialize = AsyncMock()
            mock_store.store_chunks = AsyncMock(
                return_value={"stored_chunks": 5, "skipped_chunks": 0}
            )

            # Executer le pipeline (juste extraction sans OCR/embedding)
            result = await orchestrator.process_document(
                sample_text_pdf,
                options={"skip_ocr": True},
            )

            assert result.analysis is not None
            assert result.analysis.metadata.total_pages == 2
            assert result.processing_time_seconds > 0

    def test_api_to_mcp_integration(self, client: TestClient) -> None:
        """Test que l'API et le MCP fonctionnent ensemble."""
        # Test health
        health_response = client.get("/health/live")
        assert health_response.status_code == 200

        # Test MCP tools/list
        mcp_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1,
            },
        )
        assert mcp_response.status_code == 200
