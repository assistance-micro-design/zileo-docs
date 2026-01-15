"""Tests unitaires pour ReadDocumentContentTool.

Ces tests verifient le fonctionnement du tool read_document_content:
- Lecture du contenu complet d'un document
- Filtrage par pages
- Gestion des erreurs (document non trouve)
- Format de reponse avec et sans details des chunks
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.core.exceptions import DocumentNotFoundError
from src.mcp.tools.read_document_content import ReadDocumentContentTool


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock du vector store pour les tests."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    return store


@pytest.fixture
def sample_chunks() -> list[dict[str, Any]]:
    """Chunks de test representant un document de 3 pages."""
    return [
        {
            "chunk_id": "chunk-001",
            "chunk_index": 0,
            "content": "# Introduction\n\nPremier paragraphe du document.",
            "content_preview": "# Introduction",
            "page_numbers": [0],
            "doc_filename": "test.pdf",
            "doc_total_pages": 3,
            "doc_title": "Test Document",
            "section_title": "Introduction",
            "content_type": "text",
            "token_count": 50,
            "char_count": 150,
            "has_table": False,
            "has_image": False,
        },
        {
            "chunk_id": "chunk-002",
            "chunk_index": 1,
            "content": "## Chapitre 1\n\nContenu du premier chapitre.",
            "content_preview": "## Chapitre 1",
            "page_numbers": [0, 1],
            "doc_filename": "test.pdf",
            "doc_total_pages": 3,
            "section_title": "Chapitre 1",
            "content_type": "text",
            "token_count": 40,
            "char_count": 120,
            "has_table": True,
            "has_image": False,
        },
        {
            "chunk_id": "chunk-003",
            "chunk_index": 2,
            "content": "## Chapitre 2\n\nContenu du deuxieme chapitre avec image.",
            "content_preview": "## Chapitre 2",
            "page_numbers": [1, 2],
            "doc_filename": "test.pdf",
            "doc_total_pages": 3,
            "section_title": "Chapitre 2",
            "content_type": "text",
            "token_count": 60,
            "char_count": 180,
            "has_table": False,
            "has_image": True,
        },
        {
            "chunk_id": "chunk-004",
            "chunk_index": 3,
            "content": "## Conclusion\n\nFin du document.",
            "content_preview": "## Conclusion",
            "page_numbers": [2],
            "doc_filename": "test.pdf",
            "doc_total_pages": 3,
            "section_title": "Conclusion",
            "content_type": "text",
            "token_count": 30,
            "char_count": 90,
            "has_table": False,
            "has_image": False,
        },
    ]


@pytest.fixture
def tool_with_mock(
    mock_vector_store: AsyncMock,
    sample_chunks: list[dict[str, Any]],
) -> ReadDocumentContentTool:
    """Tool avec vector store mocke."""
    tool = ReadDocumentContentTool(vector_store=mock_vector_store)
    mock_vector_store.get_document_chunks = AsyncMock(return_value=sample_chunks)
    tool._initialized = True
    return tool


class TestReadDocumentContentToolInit:
    """Tests pour l'initialisation du tool."""

    def test_tool_name(self) -> None:
        """Test le nom du tool."""
        assert ReadDocumentContentTool.name == "read_document_content"

    def test_tool_description(self) -> None:
        """Test la description du tool."""
        assert "contenu Markdown" in ReadDocumentContentTool.description
        assert "document indexe" in ReadDocumentContentTool.description

    def test_input_schema_required_fields(self) -> None:
        """Test le schema des parametres requis."""
        schema = ReadDocumentContentTool.input_schema
        assert schema["required"] == ["document_id"]

    def test_input_schema_optional_fields(self) -> None:
        """Test le schema des parametres optionnels."""
        schema = ReadDocumentContentTool.input_schema
        properties = schema["properties"]
        assert "page_start" in properties
        assert "page_end" in properties
        assert "include_chunks_detail" in properties

    def test_page_params_minimum(self) -> None:
        """Test que page_start et page_end ont un minimum de 1."""
        schema = ReadDocumentContentTool.input_schema
        assert schema["properties"]["page_start"]["minimum"] == 1
        assert schema["properties"]["page_end"]["minimum"] == 1

    @pytest.mark.asyncio
    async def test_initialize(self, mock_vector_store: AsyncMock) -> None:
        """Test l'initialisation du tool."""
        tool = ReadDocumentContentTool(vector_store=mock_vector_store)
        await tool.initialize()

        mock_vector_store.initialize.assert_called_once()
        assert tool._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mock_vector_store: AsyncMock) -> None:
        """Test que l'initialisation est idempotente."""
        tool = ReadDocumentContentTool(vector_store=mock_vector_store)
        await tool.initialize()
        await tool.initialize()

        mock_vector_store.initialize.assert_called_once()


class TestReadFullDocument:
    """Tests pour la lecture complete d'un document."""

    @pytest.mark.asyncio
    async def test_read_full_document(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test la lecture du document complet."""
        result = await tool_with_mock.execute({"document_id": "doc-test"})

        assert result["document_id"] == "doc-test"
        assert result["filename"] == "test.pdf"
        assert result["total_pages"] == 3
        assert result["total_chunks"] == 4
        assert result["total_tokens"] == 180
        assert result["chunks_returned"] == 4

    @pytest.mark.asyncio
    async def test_content_concatenation(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que le contenu est concatene correctement."""
        result = await tool_with_mock.execute({"document_id": "doc-test"})

        content = result["content"]
        assert "# Introduction" in content
        assert "## Chapitre 1" in content
        assert "## Chapitre 2" in content
        assert "## Conclusion" in content

    @pytest.mark.asyncio
    async def test_pages_returned_all(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que toutes les pages sont retournees."""
        result = await tool_with_mock.execute({"document_id": "doc-test"})

        assert result["pages_returned"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_tokens_counted(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que les tokens sont comptes correctement."""
        result = await tool_with_mock.execute({"document_id": "doc-test"})

        assert result["total_tokens"] == 180
        assert result["tokens_returned"] == 180

    @pytest.mark.asyncio
    async def test_chars_counted(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que les caracteres sont comptes."""
        result = await tool_with_mock.execute({"document_id": "doc-test"})

        assert result["total_chars"] == 540


class TestPageFiltering:
    """Tests pour le filtrage par pages."""

    @pytest.mark.asyncio
    async def test_filter_page_start(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test le filtrage avec page_start."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "page_start": 2,
            }
        )

        # Chunks contenant au moins une page >= 2 (1-indexed)
        # Chunk 1: pages [0] (page 1) -> exclu
        # Chunk 2: pages [0,1] (pages 1,2) -> inclus (contient page 2)
        # Chunk 3: pages [1,2] (pages 2,3) -> inclus
        # Chunk 4: pages [2] (page 3) -> inclus
        assert result["chunks_returned"] == 3
        # Les chunks 2,3,4 couvrent les pages 1,2,3 donc toutes les pages sont presentes
        assert 2 in result["pages_returned"]
        assert 3 in result["pages_returned"]

    @pytest.mark.asyncio
    async def test_filter_page_end(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test le filtrage avec page_end."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "page_end": 1,
            }
        )

        assert 3 not in result["pages_returned"]

    @pytest.mark.asyncio
    async def test_filter_page_range(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test le filtrage avec plage de pages."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "page_start": 2,
                "page_end": 2,
            }
        )

        assert 2 in result["pages_returned"]

    @pytest.mark.asyncio
    async def test_filter_reduces_tokens(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que le filtrage reduit les tokens retournes."""
        full_result = await tool_with_mock.execute({"document_id": "doc-test"})
        filtered_result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "page_start": 3,
            }
        )

        assert filtered_result["tokens_returned"] < full_result["tokens_returned"]
        assert filtered_result["total_tokens"] == full_result["total_tokens"]

    @pytest.mark.asyncio
    async def test_filter_preserves_total_stats(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que le filtrage preserve les stats du document complet."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "page_start": 2,
                "page_end": 2,
            }
        )

        assert result["total_pages"] == 3
        assert result["total_chunks"] == 4
        assert result["total_tokens"] == 180


class TestChunksDetail:
    """Tests pour l'option include_chunks_detail."""

    @pytest.mark.asyncio
    async def test_no_detail_by_default(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que les details ne sont pas inclus par defaut."""
        result = await tool_with_mock.execute({"document_id": "doc-test"})

        assert "chunks_detail" not in result

    @pytest.mark.asyncio
    async def test_include_detail(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test l'inclusion des details."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "include_chunks_detail": True,
            }
        )

        assert "chunks_detail" in result
        assert len(result["chunks_detail"]) == 4

    @pytest.mark.asyncio
    async def test_detail_structure(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test la structure des details."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "include_chunks_detail": True,
            }
        )

        detail = result["chunks_detail"][0]
        assert "chunk_index" in detail
        assert "page_numbers" in detail
        assert "section_title" in detail
        assert "content_type" in detail
        assert "token_count" in detail
        assert "has_table" in detail
        assert "has_image" in detail

    @pytest.mark.asyncio
    async def test_detail_page_numbers_1indexed(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que les pages dans detail sont 1-indexed."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "include_chunks_detail": True,
            }
        )

        assert result["chunks_detail"][0]["page_numbers"] == [1]

    @pytest.mark.asyncio
    async def test_detail_respects_filter(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test que les details respectent le filtre de pages."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "page_start": 3,
                "include_chunks_detail": True,
            }
        )

        assert len(result["chunks_detail"]) < 4

    @pytest.mark.asyncio
    async def test_detail_has_table_flag(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test le flag has_table dans les details."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "include_chunks_detail": True,
            }
        )

        chunk_with_table = next(c for c in result["chunks_detail"] if c["chunk_index"] == 1)
        assert chunk_with_table["has_table"] is True

    @pytest.mark.asyncio
    async def test_detail_has_image_flag(
        self,
        tool_with_mock: ReadDocumentContentTool,
    ) -> None:
        """Test le flag has_image dans les details."""
        result = await tool_with_mock.execute(
            {
                "document_id": "doc-test",
                "include_chunks_detail": True,
            }
        )

        chunk_with_image = next(c for c in result["chunks_detail"] if c["chunk_index"] == 2)
        assert chunk_with_image["has_image"] is True


class TestErrorHandling:
    """Tests pour la gestion des erreurs."""

    @pytest.mark.asyncio
    async def test_document_not_found(
        self,
        mock_vector_store: AsyncMock,
    ) -> None:
        """Test l'erreur quand le document n'existe pas."""
        mock_vector_store.get_document_chunks = AsyncMock(return_value=[])
        tool = ReadDocumentContentTool(vector_store=mock_vector_store)
        tool._initialized = True

        with pytest.raises(DocumentNotFoundError):
            await tool.execute({"document_id": "nonexistent-doc"})

    @pytest.mark.asyncio
    async def test_invalid_document_id_type(
        self,
        mock_vector_store: AsyncMock,
    ) -> None:
        """Test l'erreur avec un document_id invalide."""
        tool = ReadDocumentContentTool(vector_store=mock_vector_store)
        tool._initialized = True

        with pytest.raises(ValidationError, match="document_id"):
            await tool.execute({"document_id": 123})  # type: ignore[dict-item]

    @pytest.mark.asyncio
    async def test_missing_document_id(
        self,
        mock_vector_store: AsyncMock,
    ) -> None:
        """Test l'erreur quand document_id est manquant."""
        tool = ReadDocumentContentTool(vector_store=mock_vector_store)
        tool._initialized = True

        with pytest.raises(ValidationError, match="document_id"):
            await tool.execute({})


class TestChunkOrdering:
    """Tests pour le tri des chunks."""

    @pytest.mark.asyncio
    async def test_chunks_sorted_by_index(
        self,
        mock_vector_store: AsyncMock,
    ) -> None:
        """Test que les chunks sont tries par chunk_index."""
        shuffled_chunks = [
            {"chunk_id": "3", "chunk_index": 2, "content": "Third", "page_numbers": [2]},
            {"chunk_id": "1", "chunk_index": 0, "content": "First", "page_numbers": [0]},
            {"chunk_id": "2", "chunk_index": 1, "content": "Second", "page_numbers": [1]},
        ]
        for c in shuffled_chunks:
            c.update(
                {
                    "doc_filename": "test.pdf",
                    "doc_total_pages": 3,
                    "token_count": 10,
                    "char_count": 30,
                }
            )

        mock_vector_store.get_document_chunks = AsyncMock(return_value=shuffled_chunks)
        tool = ReadDocumentContentTool(vector_store=mock_vector_store)
        tool._initialized = True

        result = await tool.execute({"document_id": "doc-test"})

        assert result["content"] == "First\n\nSecond\n\nThird"


class TestEmptyContent:
    """Tests pour les chunks avec contenu vide."""

    @pytest.mark.asyncio
    async def test_empty_content_filtered(
        self,
        mock_vector_store: AsyncMock,
    ) -> None:
        """Test que les chunks avec contenu vide ne sont pas concatenes."""
        chunks = [
            {
                "chunk_id": "1",
                "chunk_index": 0,
                "content": "Content 1",
                "page_numbers": [0],
                "doc_filename": "test.pdf",
                "doc_total_pages": 1,
                "token_count": 10,
                "char_count": 30,
            },
            {
                "chunk_id": "2",
                "chunk_index": 1,
                "content": "",
                "page_numbers": [0],
                "doc_filename": "test.pdf",
                "doc_total_pages": 1,
                "token_count": 0,
                "char_count": 0,
            },
            {
                "chunk_id": "3",
                "chunk_index": 2,
                "content": "Content 3",
                "page_numbers": [0],
                "doc_filename": "test.pdf",
                "doc_total_pages": 1,
                "token_count": 10,
                "char_count": 30,
            },
        ]

        mock_vector_store.get_document_chunks = AsyncMock(return_value=chunks)
        tool = ReadDocumentContentTool(vector_store=mock_vector_store)
        tool._initialized = True

        result = await tool.execute({"document_id": "doc-test"})

        assert result["content"] == "Content 1\n\nContent 3"
