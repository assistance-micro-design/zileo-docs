"""Tests unitaires pour MistralEmbedder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.models.chunk import ChunkMetadata, DocumentChunk
from src.services.embedding.mistral_embedder import MistralEmbedder


@pytest.fixture
def mock_embedding_response() -> MagicMock:
    """Cree une reponse d'embedding mockee."""
    mock_response = MagicMock()
    mock_data_item = MagicMock()
    mock_data_item.embedding = [0.1] * 1024
    mock_response.data = [mock_data_item]
    return mock_response


@pytest.fixture
def sample_chunk() -> DocumentChunk:
    """Cree un chunk de test avec metadata."""
    metadata = ChunkMetadata(
        chunk_id="test-chunk-001",
        document_id="doc-test-123",
        page_numbers=[1],
        start_page=1,
        end_page=1,
        section_title="Introduction",
        content_type="text",
        token_count=50,
    )
    return DocumentChunk(
        content="Ceci est le contenu brut du chunk.",
        metadata=metadata,
        content_with_context="Section: Introduction\n\nCeci est le contenu enrichi avec contexte.",
    )


@pytest.fixture
def sample_chunk_without_context() -> DocumentChunk:
    """Cree un chunk de test sans content_with_context."""
    metadata = ChunkMetadata(
        chunk_id="test-chunk-002",
        document_id="doc-test-123",
        page_numbers=[2],
        start_page=2,
        end_page=2,
        content_type="text",
        token_count=30,
    )
    return DocumentChunk(
        content="Contenu brut uniquement.",
        metadata=metadata,
        content_with_context=None,
    )


@pytest.fixture
def sample_chunks_list(sample_chunk: DocumentChunk) -> list[DocumentChunk]:
    """Cree une liste de chunks de test."""
    _ = sample_chunk  # Use fixture to satisfy signature
    chunks = []
    for i in range(5):
        metadata = ChunkMetadata(
            chunk_id=f"chunk-{i:03d}",
            document_id="doc-test-123",
            page_numbers=[i + 1],
            start_page=i + 1,
            end_page=i + 1,
            content_type="text",
            token_count=100,
        )
        chunk = DocumentChunk(
            content=f"Contenu du chunk {i}",
            metadata=metadata,
            content_with_context=f"Context enrichi du chunk {i}",
        )
        chunks.append(chunk)
    return chunks


def create_mock_embeddings_response(count: int) -> MagicMock:
    """Cree une reponse avec plusieurs embeddings."""
    mock_response = MagicMock()
    mock_response.data = []
    for i in range(count):
        mock_item = MagicMock()
        mock_item.embedding = [0.1 + i * 0.01] * 1024
        mock_response.data.append(mock_item)
    return mock_response


class TestMistralEmbedderInit:
    """Tests pour l'initialisation de MistralEmbedder."""

    def test_init_with_api_key(self) -> None:
        """Test initialisation avec cle API fournie."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tiktoken.get_encoding.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-api-key")

            mock_mistral.assert_called_once_with(api_key="test-api-key")
            assert embedder.dimensions == 1024
            assert embedder.model_name == "mistral-embed"

    def test_init_with_settings(self) -> None:
        """Test initialisation avec settings par defaut."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
            patch("src.services.embedding.mistral_embedder.settings") as mock_settings,
        ):
            mock_tiktoken.get_encoding.return_value = MagicMock()
            mock_settings.MISTRAL_API_KEY = "settings-api-key"
            mock_settings.MISTRAL_EMBED_MODEL = "custom-embed-model"

            embedder = MistralEmbedder()

            mock_mistral.assert_called_once_with(api_key="settings-api-key")
            assert embedder.model_name == "custom-embed-model"

    def test_init_raises_without_api_key(self) -> None:
        """Test erreur si aucune cle API n'est configuree."""
        with patch("src.services.embedding.mistral_embedder.settings") as mock_settings:
            mock_settings.MISTRAL_API_KEY = ""

            with pytest.raises(ValueError, match="MISTRAL_API_KEY est requise"):
                MistralEmbedder()


class TestEmbedChunks:
    """Tests pour embed_chunks."""

    @pytest.mark.asyncio
    async def test_embed_chunks_with_enriched_content(
        self, sample_chunks_list: list[DocumentChunk]
    ) -> None:
        """Test embedding avec content_with_context (use_enriched=True)."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(50))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer

            mock_client = MagicMock()
            mock_response = create_mock_embeddings_response(5)
            mock_client.embeddings.create.return_value = mock_response
            mock_mistral.return_value = mock_client

            embedder = MistralEmbedder(api_key="test-key")
            result = await embedder.embed_chunks(sample_chunks_list, use_enriched=True)

            call_args = mock_client.embeddings.create.call_args
            inputs = call_args.kwargs["inputs"]

            assert all("Context enrichi" in text for text in inputs)
            assert len(result) == 5
            for chunk in result:
                assert chunk.embedding is not None
                assert len(chunk.embedding) == 1024

    @pytest.mark.asyncio
    async def test_embed_chunks_with_raw_content(
        self, sample_chunks_list: list[DocumentChunk]
    ) -> None:
        """Test embedding avec content brut (use_enriched=False)."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(50))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer

            mock_client = MagicMock()
            mock_response = create_mock_embeddings_response(5)
            mock_client.embeddings.create.return_value = mock_response
            mock_mistral.return_value = mock_client

            embedder = MistralEmbedder(api_key="test-key")
            result = await embedder.embed_chunks(sample_chunks_list, use_enriched=False)

            call_args = mock_client.embeddings.create.call_args
            inputs = call_args.kwargs["inputs"]

            assert all("Contenu du chunk" in text for text in inputs)
            assert not any("Context enrichi" in text for text in inputs)
            assert len(result) == 5
            for chunk in result:
                assert chunk.embedding is not None

    @pytest.mark.asyncio
    async def test_embed_chunks_fallback_to_raw_content(
        self, sample_chunk_without_context: DocumentChunk
    ) -> None:
        """Test fallback vers content brut si content_with_context est None."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(30))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer

            mock_client = MagicMock()
            mock_response = create_mock_embeddings_response(1)
            mock_client.embeddings.create.return_value = mock_response
            mock_mistral.return_value = mock_client

            embedder = MistralEmbedder(api_key="test-key")
            result = await embedder.embed_chunks([sample_chunk_without_context], use_enriched=True)

            call_args = mock_client.embeddings.create.call_args
            inputs = call_args.kwargs["inputs"]

            assert inputs[0] == "Contenu brut uniquement."
            assert result[0].embedding is not None

    @pytest.mark.asyncio
    async def test_empty_chunks_list(self) -> None:
        """Test gestion liste vide de chunks."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tiktoken.get_encoding.return_value = MagicMock()
            mock_client = MagicMock()
            mock_mistral.return_value = mock_client

            embedder = MistralEmbedder(api_key="test-key")
            result = await embedder.embed_chunks([])

            assert result == []
            mock_client.embeddings.create.assert_not_called()


class TestEmbedQuery:
    """Tests pour embed_query."""

    @pytest.mark.asyncio
    async def test_embed_query(self) -> None:
        """Test embedding d'une requete simple."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(10))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer

            mock_client = MagicMock()
            mock_response = create_mock_embeddings_response(1)
            mock_client.embeddings.create.return_value = mock_response
            mock_mistral.return_value = mock_client

            embedder = MistralEmbedder(api_key="test-key")
            result = await embedder.embed_query("comment configurer l'application?")

            call_args = mock_client.embeddings.create.call_args
            assert call_args.kwargs["inputs"] == ["comment configurer l'application?"]
            assert call_args.kwargs["model"] == "mistral-embed"

            assert isinstance(result, list)
            assert len(result) == 1024

    @pytest.mark.asyncio
    async def test_embed_query_strips_whitespace(self) -> None:
        """Test que la requete est nettoyee des espaces."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(5))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer

            mock_client = MagicMock()
            mock_response = create_mock_embeddings_response(1)
            mock_client.embeddings.create.return_value = mock_response
            mock_mistral.return_value = mock_client

            embedder = MistralEmbedder(api_key="test-key")
            await embedder.embed_query("  requete avec espaces  ")

            call_args = mock_client.embeddings.create.call_args
            assert call_args.kwargs["inputs"] == ["requete avec espaces"]

    @pytest.mark.asyncio
    async def test_empty_query_raises_error(self) -> None:
        """Test erreur pour requete vide."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tiktoken.get_encoding.return_value = MagicMock()
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")

            with pytest.raises(ValueError, match="requete ne peut pas etre vide"):
                await embedder.embed_query("")

    @pytest.mark.asyncio
    async def test_whitespace_only_query_raises_error(self) -> None:
        """Test erreur pour requete contenant uniquement des espaces."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tiktoken.get_encoding.return_value = MagicMock()
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")

            with pytest.raises(ValueError, match="requete ne peut pas etre vide"):
                await embedder.embed_query("   ")


class TestCreateBatches:
    """Tests pour _create_batches."""

    def test_create_batches_respects_max_batch_size(self) -> None:
        """Test que les batches respectent MAX_BATCH_SIZE."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(10))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")

            texts = [f"Texte {i}" for i in range(250)]
            batches = embedder._create_batches(texts)

            assert len(batches) == 3
            assert len(batches[0]) == 100
            assert len(batches[1]) == 100
            assert len(batches[2]) == 50

    def test_create_batches_respects_max_tokens(self) -> None:
        """Test que les batches respectent MAX_TOKENS_PER_REQUEST."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(5000))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")

            texts = [f"Texte long {i}" for i in range(5)]
            batches = embedder._create_batches(texts)

            assert len(batches) == 2
            assert len(batches[0]) == 3
            assert len(batches[1]) == 2

    def test_create_batches_single_large_text(self) -> None:
        """Test qu'un texte tres long est place seul dans un batch."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()

            def mock_encode(text: str) -> list[int]:
                if "Enorme" in text:
                    return list(range(20000))
                return list(range(100))

            mock_tokenizer.encode.side_effect = mock_encode
            mock_tiktoken.get_encoding.return_value = mock_tokenizer
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")

            texts = ["Texte Enorme", "Petit 1", "Petit 2"]
            batches = embedder._create_batches(texts)

            assert len(batches) >= 2
            assert batches[0] == ["Texte Enorme"]

    def test_create_batches_empty_list(self) -> None:
        """Test avec liste vide."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tiktoken.get_encoding.return_value = MagicMock()
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")
            batches = embedder._create_batches([])

            assert batches == []

    def test_create_batches_preserves_order(self) -> None:
        """Test que l'ordre des textes est preserve."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(100))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")

            texts = [f"Texte_{i:03d}" for i in range(150)]
            batches = embedder._create_batches(texts)

            flattened = []
            for batch in batches:
                flattened.extend(batch)

            assert flattened == texts


class TestCountTokens:
    """Tests pour count_tokens."""

    def test_count_tokens(self) -> None:
        """Test comptage de tokens simple."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5]
            mock_tiktoken.get_encoding.return_value = mock_tokenizer
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")
            count = embedder.count_tokens("Hello world test")

            assert count == 5
            mock_tokenizer.encode.assert_called_with("Hello world test")

    def test_count_tokens_empty_string(self) -> None:
        """Test comptage tokens pour chaine vide."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = []
            mock_tiktoken.get_encoding.return_value = mock_tokenizer
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")
            count = embedder.count_tokens("")

            assert count == 0

    def test_count_tokens_unicode(self) -> None:
        """Test comptage tokens avec caracteres unicode."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(10))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer
            mock_mistral.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")
            count = embedder.count_tokens("Texte francais avec accents: e, a, u")

            assert count == 10


class TestProperties:
    """Tests pour les proprietes."""

    def test_dimensions_property(self) -> None:
        """Test propriete dimensions."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral"),
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tiktoken.get_encoding.return_value = MagicMock()

            embedder = MistralEmbedder(api_key="test-key")
            assert embedder.dimensions == 1024

    def test_model_name_property_default(self) -> None:
        """Test propriete model_name avec valeur par defaut."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral"),
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
            patch("src.services.embedding.mistral_embedder.settings") as mock_settings,
        ):
            mock_settings.MISTRAL_API_KEY = "test-key"
            mock_settings.MISTRAL_EMBED_MODEL = ""
            mock_tiktoken.get_encoding.return_value = MagicMock()

            embedder = MistralEmbedder()
            assert embedder.model_name == "mistral-embed"

    def test_model_name_property_custom(self) -> None:
        """Test propriete model_name avec modele custom."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral"),
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
            patch("src.services.embedding.mistral_embedder.settings") as mock_settings,
        ):
            mock_settings.MISTRAL_API_KEY = "test-key"
            mock_settings.MISTRAL_EMBED_MODEL = "mistral-embed-v2"
            mock_tiktoken.get_encoding.return_value = MagicMock()

            embedder = MistralEmbedder()
            assert embedder.model_name == "mistral-embed-v2"


class TestMistralEmbedderIntegrationMocked:
    """Tests d'integration avec API mockee."""

    @pytest.mark.asyncio
    async def test_embed_multiple_batches(self) -> None:
        """Test embedding avec plusieurs batches."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(6000))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer

            mock_client = MagicMock()
            call_count = 0

            def mock_create(**kwargs: object) -> MagicMock:
                nonlocal call_count
                call_count += 1
                inputs = kwargs.get("inputs", [])
                return create_mock_embeddings_response(len(inputs))  # type: ignore[arg-type]

            mock_client.embeddings.create.side_effect = mock_create
            mock_mistral.return_value = mock_client

            embedder = MistralEmbedder(api_key="test-key")

            chunks = []
            for i in range(5):
                metadata = ChunkMetadata(
                    chunk_id=f"chunk-{i}",
                    document_id="doc-123",
                    token_count=6000,
                )
                chunk = DocumentChunk(
                    content=f"Contenu {i}",
                    metadata=metadata,
                )
                chunks.append(chunk)

            result = await embedder.embed_chunks(chunks, use_enriched=False)

            assert call_count >= 2
            assert len(result) == 5
            for chunk in result:
                assert chunk.embedding is not None
                assert len(chunk.embedding) == 1024

    @pytest.mark.asyncio
    async def test_embed_query_and_chunks_same_model(self) -> None:
        """Test que query et chunks utilisent le meme modele."""
        with (
            patch("src.services.embedding.mistral_embedder.Mistral") as mock_mistral,
            patch("src.services.embedding.mistral_embedder.tiktoken") as mock_tiktoken,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = list(range(50))
            mock_tiktoken.get_encoding.return_value = mock_tokenizer

            mock_client = MagicMock()
            mock_response = create_mock_embeddings_response(1)
            mock_client.embeddings.create.return_value = mock_response
            mock_mistral.return_value = mock_client

            embedder = MistralEmbedder(api_key="test-key")

            await embedder.embed_query("test query")
            query_call = mock_client.embeddings.create.call_args_list[0]

            metadata = ChunkMetadata(chunk_id="c1", document_id="d1")
            chunk = DocumentChunk(content="Test chunk", metadata=metadata)
            await embedder.embed_chunks([chunk])
            chunk_call = mock_client.embeddings.create.call_args_list[1]

            assert query_call.kwargs["model"] == chunk_call.kwargs["model"]
            assert query_call.kwargs["model"] == "mistral-embed"
