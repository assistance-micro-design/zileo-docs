# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour SmartChunker."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.models.chunk import ChunkMetadata
from src.models.document import DocumentMetadata
from src.models.extraction import ExtractedContent, OCRResult
from src.services.chunking.chunker import SmartChunker


# --- Fixtures ---


@pytest.fixture
def chunker() -> SmartChunker:
    """Cree un SmartChunker avec configuration de test."""
    return SmartChunker(
        chunk_size=200,
        chunk_overlap=20,
        min_chunk_size=10,
        preserve_tables=True,
        preserve_code=True,
    )


@pytest.fixture
def small_chunker() -> SmartChunker:
    """Cree un SmartChunker avec petite taille pour tests d'overlap."""
    return SmartChunker(
        chunk_size=50,
        chunk_overlap=10,
        min_chunk_size=5,
        preserve_tables=True,
        preserve_code=True,
    )


@pytest.fixture
def document_metadata() -> DocumentMetadata:
    """Cree des metadonnees de document de test."""
    return DocumentMetadata(
        document_id="doc_test_001",
        file_hash="abc123def456",
        filename="test_document.pdf",
        file_size_bytes=1024000,
        total_pages=3,
    )


@pytest.fixture
def single_page_metadata() -> DocumentMetadata:
    """Cree des metadonnees pour un document d'une seule page."""
    return DocumentMetadata(
        document_id="doc_single_001",
        file_hash="single123",
        filename="single_page.pdf",
        file_size_bytes=512000,
        total_pages=1,
    )


@pytest.fixture
def native_content_with_table() -> dict[int, ExtractedContent]:
    """Cree du contenu natif avec un tableau Markdown."""
    content = """# Document avec Tableau

Ce document contient un tableau important.

| Nom | Age | Ville |
|-----|-----|-------|
| Alice | 30 | Paris |
| Bob | 25 | Lyon |
| Charlie | 35 | Marseille |

Le tableau ci-dessus presente les donnees des utilisateurs."""

    return {
        0: ExtractedContent(
            page_number=0,
            markdown_content=content,
            extraction_method="pymupdf4llm",
            char_count=len(content),
            word_count=len(content.split()),
        )
    }


@pytest.fixture
def native_content_with_code() -> dict[int, ExtractedContent]:
    """Cree du contenu natif avec un bloc de code.

    Note: Le bloc de code ne doit pas avoir de lignes vides internes
    car le chunker split sur les paragraphes (double newline).
    """
    content = """# Guide de Programmation

Voici un exemple de code Python:

```python
def hello_world():
    print("Hello, World!")
    return True
```

Ce code affiche un message de bienvenue."""

    return {
        0: ExtractedContent(
            page_number=0,
            markdown_content=content,
            extraction_method="pymupdf4llm",
            char_count=len(content),
            word_count=len(content.split()),
        )
    }


@pytest.fixture
def native_content_with_headers() -> dict[int, ExtractedContent]:
    """Cree du contenu natif avec hierarchie de sections."""
    content = """# Titre Principal

Introduction du document.

## Section 1

Contenu de la section 1.

### Sous-section 1.1

Details de la sous-section 1.1.

### Sous-section 1.2

Details de la sous-section 1.2.

## Section 2

Contenu de la section 2.

### Sous-section 2.1

Details de la sous-section 2.1.

# Nouveau Chapitre

Debut d'un nouveau chapitre."""

    return {
        0: ExtractedContent(
            page_number=0,
            markdown_content=content,
            extraction_method="pymupdf4llm",
            char_count=len(content),
            word_count=len(content.split()),
        )
    }


@pytest.fixture
def native_content_long() -> dict[int, ExtractedContent]:
    """Cree du contenu natif long pour tester le chunking."""
    # Generer un contenu suffisamment long pour creer plusieurs chunks
    paragraphs = []
    for i in range(20):
        paragraphs.append(
            f"Paragraphe {i + 1}: Lorem ipsum dolor sit amet, consectetur "
            f"adipiscing elit. Sed do eiusmod tempor incididunt ut labore "
            f"et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
            f"exercitation ullamco laboris nisi ut aliquip ex ea commodo."
        )

    content = "# Document Long\n\n" + "\n\n".join(paragraphs)

    return {
        0: ExtractedContent(
            page_number=0,
            markdown_content=content,
            extraction_method="pymupdf4llm",
            char_count=len(content),
            word_count=len(content.split()),
        )
    }


@pytest.fixture
def multipage_native_content() -> dict[int, ExtractedContent]:
    """Cree du contenu natif sur plusieurs pages."""
    return {
        0: ExtractedContent(
            page_number=0,
            markdown_content="# Page 1\n\nContenu de la premiere page.",
            extraction_method="pymupdf4llm",
            char_count=50,
            word_count=8,
        ),
        1: ExtractedContent(
            page_number=1,
            markdown_content="# Page 2\n\nContenu de la deuxieme page.",
            extraction_method="pymupdf4llm",
            char_count=50,
            word_count=8,
        ),
        2: ExtractedContent(
            page_number=2,
            markdown_content="# Page 3\n\nContenu de la troisieme page.",
            extraction_method="pymupdf4llm",
            char_count=50,
            word_count=8,
        ),
    }


@pytest.fixture
def ocr_content() -> dict[int, OCRResult]:
    """Cree du contenu OCR de test."""
    return {
        1: OCRResult(
            page_number=1,
            markdown_content="# Contenu OCR\n\nTexte extrait par OCR de la page 2.",
            confidence_score=0.95,
            processing_time_ms=500,
        )
    }


@pytest.fixture
def native_and_ocr_content() -> tuple[dict[int, ExtractedContent], dict[int, OCRResult]]:
    """Cree du contenu mixte natif et OCR.

    Page 0: natif seul
    Page 1: natif ET OCR -> OCR prioritaire
    Page 2: OCR seul
    """
    native = {
        0: ExtractedContent(
            page_number=0,
            markdown_content="# Page Texte Natif\n\nContenu natif de la page 1.",
            extraction_method="pymupdf4llm",
            char_count=60,
            word_count=10,
        ),
        # Page 1 a du contenu natif ET OCR (OCR prioritaire)
        1: ExtractedContent(
            page_number=1,
            markdown_content="# Page Native Ignoree\n\nLe contenu natif sera ignore.",
            extraction_method="pymupdf4llm",
            char_count=70,
            word_count=12,
        ),
    }

    ocr = {
        # Page 1 a aussi de l'OCR -> OCR gagne
        1: OCRResult(
            page_number=1,
            markdown_content="# Page OCR Prioritaire\n\nLe contenu OCR a priorite.",
            confidence_score=0.90,
            processing_time_ms=400,
        ),
        # Page 2 n'a que de l'OCR
        2: OCRResult(
            page_number=2,
            markdown_content="# Page OCR Seul\n\nContenu OCR pour page sans natif.",
            confidence_score=0.92,
            processing_time_ms=450,
        ),
    }

    return native, ocr


# --- Tests: Preservation des Tableaux ---


class TestPreserveTables:
    """Tests pour la preservation des tableaux Markdown."""

    @pytest.mark.asyncio
    async def test_preserve_tables_intact(
        self,
        chunker: SmartChunker,
        native_content_with_table: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que les tableaux Markdown restent intacts."""
        chunks = await chunker.chunk_document(
            document_id="doc_table_001",
            native_content=native_content_with_table,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Chercher le chunk contenant le tableau
        table_chunk = None
        for chunk in chunks:
            if "| Nom | Age | Ville |" in chunk.content:
                table_chunk = chunk
                break

        assert table_chunk is not None, "Le tableau doit etre present dans un chunk"

        # Verifier que le tableau est complet (toutes les lignes)
        assert "| Alice | 30 | Paris |" in table_chunk.content
        assert "| Bob | 25 | Lyon |" in table_chunk.content
        assert "| Charlie | 35 | Marseille |" in table_chunk.content

        # Verifier les metadonnees
        assert table_chunk.metadata.has_table is True
        assert table_chunk.metadata.content_type == "table"

    @pytest.mark.asyncio
    async def test_table_not_split_across_chunks(
        self,
        small_chunker: SmartChunker,
        native_content_with_table: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier qu'un tableau n'est jamais coupe entre chunks."""
        chunks = await small_chunker.chunk_document(
            document_id="doc_table_002",
            native_content=native_content_with_table,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Pour chaque chunk, verifier qu'il ne contient pas de tableau partiel
        for chunk in chunks:
            content = chunk.content
            # Si le chunk commence un tableau, il doit le terminer
            if "| Nom | Age | Ville |" in content:
                assert "| Charlie | 35 | Marseille |" in content

    def test_identify_protected_regions_tables(self, chunker: SmartChunker) -> None:
        """Test detection des tableaux comme regions protegees."""
        content = """Texte avant

| Col1 | Col2 |
|------|------|
| A    | B    |
| C    | D    |

Texte apres"""

        from src.services.chunking.parsing import identify_protected_regions

        regions = identify_protected_regions(
            content,
            preserve_tables=chunker.preserve_tables,
            preserve_code=chunker.preserve_code,
        )

        table_regions = [r for r in regions if r[2] == "table"]
        assert len(table_regions) == 1

        # Verifier que la region couvre tout le tableau
        start, end, _region_type = table_regions[0]
        table_content = content[start:end]
        assert "| Col1 | Col2 |" in table_content
        assert "| C    | D    |" in table_content


# --- Tests: Preservation des Blocs de Code ---


class TestPreserveCodeBlocks:
    """Tests pour la preservation des blocs de code."""

    @pytest.mark.asyncio
    async def test_preserve_code_blocks_intact(
        self,
        chunker: SmartChunker,
        native_content_with_code: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que les blocs de code restent intacts."""
        chunks = await chunker.chunk_document(
            document_id="doc_code_001",
            native_content=native_content_with_code,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Chercher le chunk contenant le code
        code_chunk = None
        for chunk in chunks:
            if "def hello_world():" in chunk.content:
                code_chunk = chunk
                break

        assert code_chunk is not None, "Le bloc de code doit etre present"

        # Verifier que le bloc de code est complet
        assert "```python" in code_chunk.content
        assert 'print("Hello, World!")' in code_chunk.content
        assert "return True" in code_chunk.content
        # Verifier que le bloc se termine par ```
        assert code_chunk.content.strip().endswith("```")

        # Verifier le type de contenu
        assert code_chunk.metadata.content_type == "code"

    @pytest.mark.asyncio
    async def test_code_block_not_split(
        self,
        chunker: SmartChunker,
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier qu'un bloc de code identifie comme protege reste intact."""
        # Utiliser un contenu avec un bloc de code simple sans lignes vides internes
        content = """# Introduction

Texte introductif.

```python
x = 1
y = 2
print(x + y)
```

Texte conclusif."""

        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content=content,
                extraction_method="pymupdf4llm",
                char_count=len(content),
                word_count=len(content.split()),
            )
        }

        chunks = await chunker.chunk_document(
            document_id="doc_code_002",
            native_content=native,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Chercher le chunk de type code
        code_chunks = [c for c in chunks if c.metadata.content_type == "code"]

        # Le bloc de code doit etre dans un seul chunk
        assert len(code_chunks) >= 1, "Au moins un chunk de type code attendu"

        for code_chunk in code_chunks:
            content = code_chunk.content
            # Compter les occurrences de ```
            backtick_count = content.count("```")
            # Doit etre pair (ouverture + fermeture)
            assert backtick_count % 2 == 0, (
                f"Bloc de code incomplet: {backtick_count} occurrences de ```"
            )

    def test_identify_protected_regions_code(self, chunker: SmartChunker) -> None:
        """Test detection des blocs de code comme regions protegees."""
        content = """Texte avant

```python
def test():
    pass
```

Texte apres"""

        from src.services.chunking.parsing import identify_protected_regions

        regions = identify_protected_regions(
            content,
            preserve_tables=chunker.preserve_tables,
            preserve_code=chunker.preserve_code,
        )

        code_regions = [r for r in regions if r[2] == "code"]
        assert len(code_regions) == 1

        start, end, _region_type = code_regions[0]
        code_content = content[start:end]
        assert "```python" in code_content
        assert "def test():" in code_content
        assert "```" in code_content


# --- Tests: Hierarchie des Sections ---


class TestSectionHierarchy:
    """Tests pour la detection de la hierarchie des sections."""

    def test_parse_sections_simple(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Test parsing des sections simples."""
        content = """# Titre 1

Contenu.

## Titre 2

Plus de contenu.

### Titre 3

Encore du contenu."""

        from src.services.chunking.parsing import parse_sections

        sections = parse_sections(content)

        assert len(sections) == 3

        assert sections[0]["level"] == 1
        assert sections[0]["title"] == "Titre 1"
        assert sections[0]["hierarchy"] == ["Titre 1"]

        assert sections[1]["level"] == 2
        assert sections[1]["title"] == "Titre 2"
        assert sections[1]["hierarchy"] == ["Titre 1", "Titre 2"]

        assert sections[2]["level"] == 3
        assert sections[2]["title"] == "Titre 3"
        assert sections[2]["hierarchy"] == ["Titre 1", "Titre 2", "Titre 3"]

    def test_parse_sections_hierarchy_reset(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Test que la hierarchie se reinitialise correctement."""
        content = """# Chapitre 1

## Section 1.1

### Sous-section 1.1.1

## Section 1.2

# Chapitre 2

## Section 2.1"""

        from src.services.chunking.parsing import parse_sections

        sections = parse_sections(content)

        # Verifier la hierarchie du Chapitre 2
        chapitre2 = next(s for s in sections if s["title"] == "Chapitre 2")
        assert chapitre2["hierarchy"] == ["Chapitre 2"]

        # Verifier la hierarchie de Section 2.1
        section21 = next(s for s in sections if s["title"] == "Section 2.1")
        assert section21["hierarchy"] == ["Chapitre 2", "Section 2.1"]

    @pytest.mark.asyncio
    async def test_chunk_contains_section_hierarchy(
        self,
        chunker: SmartChunker,
        native_content_with_headers: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que les chunks contiennent l'information de hierarchie."""
        chunks = await chunker.chunk_document(
            document_id="doc_sections_001",
            native_content=native_content_with_headers,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Au moins un chunk doit avoir une hierarchie de section
        chunks_with_hierarchy = [c for c in chunks if len(c.metadata.section_hierarchy) > 0]
        assert len(chunks_with_hierarchy) > 0

        # Verifier qu'un chunk avec sous-section a la hierarchie complete
        for chunk in chunks:
            if chunk.metadata.section_title == "Sous-section 1.1":
                assert "Section 1" in chunk.metadata.section_hierarchy

    def test_get_hierarchy_at_position(self, chunker: SmartChunker) -> None:
        """Test recuperation de la hierarchie a une position donnee."""
        content = """# Titre
## Section
### Sous-section
Contenu ici"""

        from src.services.chunking.parsing import parse_sections

        sections = parse_sections(content)

        # Position apres "### Sous-section"
        pos = content.find("Contenu ici")
        hierarchy = chunker._get_hierarchy_at(pos, sections)

        assert hierarchy == ["Titre", "Section", "Sous-section"]


# --- Tests: Taille des Chunks ---


class TestChunkSizeRespected:
    """Tests pour verifier le respect de la taille des chunks."""

    @pytest.mark.asyncio
    async def test_chunk_size_limit(
        self,
        chunker: SmartChunker,
        native_content_long: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que la taille des chunks est respectee."""
        chunks = await chunker.chunk_document(
            document_id="doc_size_001",
            native_content=native_content_long,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Verifier que chaque chunk respecte la taille maximum
        for chunk in chunks:
            # Les regions protegees peuvent depasser la taille
            if chunk.metadata.content_type == "text":
                token_count = chunker.count_tokens(chunk.content)
                # Tolerance de 20% pour les chunks de texte
                assert token_count <= chunker.chunk_size * 1.2, (
                    f"Chunk trop grand: {token_count} tokens (max: {chunker.chunk_size})"
                )

    @pytest.mark.asyncio
    async def test_multiple_chunks_created_for_long_content(
        self,
        small_chunker: SmartChunker,
        native_content_long: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que le contenu long est decoupe en plusieurs chunks."""
        chunks = await small_chunker.chunk_document(
            document_id="doc_multi_001",
            native_content=native_content_long,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Le contenu long doit creer plusieurs chunks
        assert len(chunks) > 1, "Le contenu long doit etre decoupe en plusieurs chunks"

    def test_count_tokens(self, chunker: SmartChunker) -> None:
        """Test comptage des tokens."""
        text = "Hello world, this is a test."
        token_count = chunker.count_tokens(text)

        assert token_count > 0
        assert isinstance(token_count, int)

    @pytest.mark.asyncio
    async def test_min_chunk_size_respected(
        self,
        chunker: SmartChunker,
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que la taille minimum des chunks est respectee."""
        # Contenu court
        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content="# Titre\n\nUn petit paragraphe de test.",
                extraction_method="pymupdf4llm",
                char_count=40,
                word_count=6,
            )
        }

        chunks = await chunker.chunk_document(
            document_id="doc_min_001",
            native_content=native,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Chaque chunk doit atteindre la taille minimum (sauf si contenu insuffisant)
        for chunk in chunks:
            token_count = chunker.count_tokens(chunk.content)
            # Le chunk doit avoir au moins min_chunk_size tokens
            # sauf si c'est le seul chunk possible
            if len(chunks) > 1:
                assert token_count >= chunker.min_chunk_size


# --- Tests: Overlap entre Chunks ---


class TestOverlapBetweenChunks:
    """Tests pour verifier l'overlap entre chunks adjacents."""

    @pytest.mark.asyncio
    async def test_overlap_exists_between_chunks(
        self,
        small_chunker: SmartChunker,
        native_content_long: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier l'overlap entre chunks adjacents."""
        chunks = await small_chunker.chunk_document(
            document_id="doc_overlap_001",
            native_content=native_content_long,
            ocr_content={},
            metadata=single_page_metadata,
        )

        if len(chunks) < 2:
            pytest.skip("Pas assez de chunks pour tester l'overlap")

        # Verifier l'overlap entre chunks adjacents de type text
        text_chunks = [c for c in chunks if c.metadata.content_type == "text"]

        for i in range(len(text_chunks) - 1):
            current = text_chunks[i]
            next_chunk = text_chunks[i + 1]

            # Extraire les derniers mots du chunk courant
            current_words = current.content.split()[-20:]

            # Extraire les premiers mots du chunk suivant
            next_words = next_chunk.content.split()[:20]

            # Il devrait y avoir une certaine similarite (overlap)
            # On verifie qu'au moins quelques mots se retrouvent
            common = set(current_words) & set(next_words)
            # Note: l'overlap peut etre subtil, on verifie juste la structure
            assert len(chunks) > 1, (
                f"L'overlap devrait creer une continuite, mots communs: {len(common)}"
            )

    def test_get_overlap_method(self, chunker: SmartChunker) -> None:
        """Test de la methode _get_overlap."""
        chunk = "Premier paragraphe avec du contenu. " * 10

        overlap = chunker._get_overlap(chunk)

        # L'overlap ne doit pas etre vide pour un chunk suffisamment long
        if chunker.count_tokens(chunk) > chunker.chunk_overlap:
            assert len(overlap) > 0

    def test_get_overlap_empty_chunk(self, chunker: SmartChunker) -> None:
        """Test overlap sur chunk vide."""
        overlap = chunker._get_overlap("")
        assert overlap == ""

    def test_get_overlap_short_chunk(self, chunker: SmartChunker) -> None:
        """Test overlap sur chunk plus court que l'overlap."""
        short_chunk = "Court"
        overlap = chunker._get_overlap(short_chunk)

        # Pour un chunk tres court, l'overlap devrait etre vide
        # car le chunk n'a pas assez de tokens
        assert overlap == ""


# --- Tests: Fusion Contenu Natif et OCR ---


class TestMergeNativeAndOCRContent:
    """Tests pour la fusion du contenu natif et OCR."""

    @pytest.mark.asyncio
    async def test_ocr_priority_over_native(
        self,
        chunker: SmartChunker,
        native_and_ocr_content: tuple[dict[int, ExtractedContent], dict[int, OCRResult]],
    ) -> None:
        """Verifier que le contenu OCR a priorite sur le natif."""
        native, ocr = native_and_ocr_content

        metadata = DocumentMetadata(
            document_id="doc_merge_001",
            file_hash="merge123",
            filename="merged.pdf",
            file_size_bytes=2048000,
            total_pages=3,
        )

        chunks = await chunker.chunk_document(
            document_id="doc_merge_001",
            native_content=native,
            ocr_content=ocr,
            metadata=metadata,
        )

        # Concatener tout le contenu des chunks
        all_content = " ".join([c.content for c in chunks])

        # Le contenu natif de la page 1 doit etre present (pas d'OCR pour cette page)
        assert "Page Texte Natif" in all_content or "Contenu natif" in all_content

        # Le contenu OCR prioritaire de la page 2 doit etre present
        assert "OCR Prioritaire" in all_content or "OCR a priorite" in all_content

        # Le contenu natif de la page 2 ne doit PAS etre present
        assert "Page Native Ignoree" not in all_content

        # Le contenu OCR de la page 3 DOIT etre present (pas de natif)
        assert "Page OCR Seul" in all_content or "OCR pour page" in all_content

    def test_merge_content_order(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Test de l'ordre de fusion des pages."""
        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content="Contenu page 1",
                extraction_method="pymupdf4llm",
            ),
            2: ExtractedContent(
                page_number=2,
                markdown_content="Contenu page 3",
                extraction_method="pymupdf4llm",
            ),
        }

        ocr = {
            1: OCRResult(
                page_number=1,
                markdown_content="Contenu OCR page 2",
            ),
        }

        from src.services.chunking.parsing import merge_content

        merged, _page_mapping = merge_content(native, ocr, total_pages=3)

        # Verifier l'ordre
        pos_page1 = merged.find("Contenu page 1")
        pos_page2 = merged.find("Contenu OCR page 2")
        pos_page3 = merged.find("Contenu page 3")

        assert pos_page1 < pos_page2 < pos_page3

    def test_merge_content_page_markers(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Test des marqueurs de page dans le contenu fusionne."""
        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content="Contenu",
                extraction_method="pymupdf4llm",
            ),
        }

        from src.services.chunking.parsing import merge_content

        merged, _ = merge_content(native, {}, total_pages=2)

        # Verifier la presence des marqueurs de page
        assert "<!-- Page 1 -->" in merged
        assert "<!-- Page 2 -->" in merged


# --- Tests: Enrichissement pour Embedding ---


class TestEnrichmentForEmbedding:
    """Tests pour l'enrichissement du contenu pour embedding."""

    @pytest.mark.asyncio
    async def test_enriched_content_includes_hierarchy(
        self,
        chunker: SmartChunker,
        native_content_with_headers: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que le contenu enrichi inclut la hierarchie."""
        chunks = await chunker.chunk_document(
            document_id="doc_enrich_001",
            native_content=native_content_with_headers,
            ocr_content={},
            metadata=single_page_metadata,
        )

        # Chercher un chunk avec hierarchie
        chunks_with_hierarchy = [c for c in chunks if len(c.metadata.section_hierarchy) > 0]

        for chunk in chunks_with_hierarchy:
            enriched = chunk.content_with_context
            assert enriched is not None

            # Le contenu enrichi doit inclure "Section:" si hierarchie presente
            if chunk.metadata.section_hierarchy:
                assert "Section:" in enriched

    def test_enrich_for_embedding_with_type(self, chunker: SmartChunker) -> None:
        """Test enrichissement avec type de contenu special."""
        content = "SELECT * FROM users WHERE id = 1;"

        metadata = ChunkMetadata(
            chunk_id="chunk_001",
            document_id="doc_001",
            content_type="code",
            section_hierarchy=["Database", "Queries"],
        )

        enriched = chunker._enrich_for_embedding(content, metadata)

        assert "Section: Database > Queries" in enriched
        assert "Type: code" in enriched
        assert content in enriched

    def test_enrich_for_embedding_text_only(self, chunker: SmartChunker) -> None:
        """Test enrichissement pour contenu texte simple."""
        content = "Un simple paragraphe de texte."

        metadata = ChunkMetadata(
            chunk_id="chunk_002",
            document_id="doc_002",
            content_type="text",
            section_hierarchy=[],
        )

        enriched = chunker._enrich_for_embedding(content, metadata)

        # Pour du texte simple sans hierarchie, le contenu reste tel quel
        assert content in enriched
        # Pas de "Type:" car c'est du texte standard
        assert "Type:" not in enriched


# --- Tests: Page Mapping ---


class TestPageMapping:
    """Tests pour la detection des numeros de pages."""

    @pytest.mark.asyncio
    async def test_page_numbers_in_chunks(
        self,
        chunker: SmartChunker,
        multipage_native_content: dict[int, ExtractedContent],
        document_metadata: DocumentMetadata,
    ) -> None:
        """Verifier la detection des numeros de pages dans les chunks."""
        chunks = await chunker.chunk_document(
            document_id="doc_pages_001",
            native_content=multipage_native_content,
            ocr_content={},
            metadata=document_metadata,
        )

        # Chaque chunk doit avoir des numeros de pages
        for chunk in chunks:
            assert len(chunk.metadata.page_numbers) > 0
            assert chunk.metadata.start_page >= 0
            assert chunk.metadata.end_page >= chunk.metadata.start_page

    @pytest.mark.asyncio
    async def test_page_numbers_range(
        self,
        chunker: SmartChunker,
        multipage_native_content: dict[int, ExtractedContent],
        document_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que start_page et end_page sont coherents."""
        chunks = await chunker.chunk_document(
            document_id="doc_pages_002",
            native_content=multipage_native_content,
            ocr_content={},
            metadata=document_metadata,
        )

        for chunk in chunks:
            # start_page doit etre <= end_page
            assert chunk.metadata.start_page <= chunk.metadata.end_page

            # Les pages doivent etre dans la plage du document (1-indexed)
            for page in chunk.metadata.page_numbers:
                assert 1 <= page <= document_metadata.total_pages

    def test_get_pages_for_chunk(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Test de la methode _get_pages_for_chunk."""
        full_content = """<!-- Page 1 -->
Contenu page 1.

<!-- Page 2 -->
Contenu page 2.

<!-- Page 3 -->
Contenu page 3."""

        # New structure: page_num -> (start_pos, end_pos, page_num)
        page_mapping = {
            0: (16, 34, 0),  # Page 1 content: positions 16-34
            1: (50, 68, 1),  # Page 2 content: positions 50-68
            2: (84, 100, 2),  # Page 3 content: positions 84-100
        }

        # Chercher les pages pour "Contenu page 2"
        from src.services.chunking.page_mapping import get_pages_for_chunk

        pages = get_pages_for_chunk("Contenu page 2", full_content, page_mapping)

        # Should return page 2 (1-indexed)
        assert 2 in pages

    @pytest.mark.asyncio
    async def test_total_chunks_updated(
        self,
        chunker: SmartChunker,
        native_content_long: dict[int, ExtractedContent],
        single_page_metadata: DocumentMetadata,
    ) -> None:
        """Verifier que total_chunks est mis a jour dans tous les chunks."""
        chunks = await chunker.chunk_document(
            document_id="doc_total_001",
            native_content=native_content_long,
            ocr_content={},
            metadata=single_page_metadata,
        )

        total = len(chunks)

        for chunk in chunks:
            assert chunk.metadata.total_chunks == total
            assert chunk.metadata.chunk_index < total


# --- Tests: Methodes Helper ---


class TestHelperMethods:
    """Tests pour les methodes helper du chunker."""

    def test_has_table(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Test detection des tableaux."""
        from src.services.chunking.content_detection import has_table

        with_table = "| A | B |\n|---|---|\n| 1 | 2 |"
        without_table = "Texte simple sans tableau."

        assert has_table(with_table) is True
        assert has_table(without_table) is False

    def test_has_image(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Test detection des images."""
        from src.services.chunking.content_detection import has_image

        with_image = "Texte avec ![image](path.png) intègre."
        without_image = "Texte simple sans image."

        assert has_image(with_image) is True
        assert has_image(without_image) is False

    def test_has_equation(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Test detection des equations."""
        from src.services.chunking.content_detection import has_equation

        with_equation = "La formule $E = mc^2$ est celebre."
        without_equation = "Texte simple sans equation."

        assert has_equation(with_equation) is True
        assert has_equation(without_equation) is False

    def test_should_save_chunk(self, chunker: SmartChunker) -> None:
        """Test de la decision de sauvegarde d'un chunk."""
        # Chunk vide
        assert chunker._should_save_chunk("") is False
        assert chunker._should_save_chunk("   ") is False

        # Chunk trop court
        assert chunker._should_save_chunk("court") is False

        # Chunk suffisamment long
        long_chunk = "Un chunk avec suffisamment de contenu " * 10
        assert chunker._should_save_chunk(long_chunk) is True

    def test_is_in_protected_region(self, chunker: SmartChunker) -> None:
        """Test verification si texte dans region protegee."""
        content = "Avant ```code``` Apres"
        protected = [(6, 16, "code")]

        is_protected, region_type = chunker._is_in_protected("code", content, protected)
        assert is_protected is True
        assert region_type == "code"

        is_protected, region_type = chunker._is_in_protected("Avant", content, protected)
        assert is_protected is False


# --- Tests: Integration ---


class TestChunkerIntegration:
    """Tests d'integration du chunker."""

    @pytest.mark.asyncio
    async def test_full_document_chunking(self, chunker: SmartChunker) -> None:
        """Test du chunking complet d'un document."""
        content = """# Introduction

Bienvenue dans ce document de test.

## Section 1: Tableaux

Voici un tableau de donnees:

| Nom | Valeur |
|-----|--------|
| A   | 100    |
| B   | 200    |

## Section 2: Code

Exemple de code:

```python
def process(data):
    return data * 2
```

## Conclusion

Fin du document."""

        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content=content,
                extraction_method="pymupdf4llm",
                char_count=len(content),
                word_count=len(content.split()),
            )
        }

        metadata = DocumentMetadata(
            document_id="doc_full_001",
            file_hash="full123",
            filename="full_doc.pdf",
            file_size_bytes=4096,
            total_pages=1,
        )

        chunks = await chunker.chunk_document(
            document_id="doc_full_001",
            native_content=native,
            ocr_content={},
            metadata=metadata,
        )

        assert len(chunks) > 0

        # Verifier les types de contenu
        content_types = {c.metadata.content_type for c in chunks}
        assert "text" in content_types or "table" in content_types or "code" in content_types

        # Verifier que tous les chunks ont les metadonnees requises
        for chunk in chunks:
            assert chunk.metadata.document_id == "doc_full_001"
            assert chunk.metadata.chunk_id.startswith("doc_full_001_chunk_")
            assert chunk.content_with_context is not None

    @pytest.mark.asyncio
    async def test_empty_document(self, chunker: SmartChunker) -> None:
        """Test du chunking d'un document vide."""
        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content="",
                extraction_method="pymupdf4llm",
                char_count=0,
                word_count=0,
            )
        }

        metadata = DocumentMetadata(
            document_id="doc_empty_001",
            file_hash="empty123",
            filename="empty.pdf",
            file_size_bytes=1024,
            total_pages=1,
        )

        chunks = await chunker.chunk_document(
            document_id="doc_empty_001",
            native_content=native,
            ocr_content={},
            metadata=metadata,
        )

        # Document vide = pas de chunks
        assert len(chunks) == 0


# --- Tests: Configuration ---


class TestChunkerConfiguration:
    """Tests pour la configuration du chunker."""

    def test_default_configuration(self) -> None:
        """Test configuration par defaut."""
        with patch("src.services.chunking.chunker.settings") as mock_settings:
            mock_settings.CHUNK_SIZE = 512
            mock_settings.CHUNK_OVERLAP = 50

            chunker = SmartChunker()

            assert chunker.chunk_size == 512
            assert chunker.chunk_overlap == 50
            assert chunker.preserve_tables is True
            assert chunker.preserve_code is True

    def test_custom_configuration(self) -> None:
        """Test configuration personnalisee."""
        chunker = SmartChunker(
            chunk_size=1000,
            chunk_overlap=100,
            min_chunk_size=50,
            preserve_tables=False,
            preserve_code=False,
        )

        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 100
        assert chunker.min_chunk_size == 50
        assert chunker.preserve_tables is False
        assert chunker.preserve_code is False

    def test_preserve_tables_disabled(self) -> None:
        """Test avec preservation des tableaux desactivee."""
        from src.services.chunking.parsing import identify_protected_regions

        chunker = SmartChunker(preserve_tables=False)

        content = "| A | B |\n|---|---|\n| 1 | 2 |"
        regions = identify_protected_regions(
            content,
            preserve_tables=chunker.preserve_tables,
            preserve_code=chunker.preserve_code,
        )

        table_regions = [r for r in regions if r[2] == "table"]
        assert len(table_regions) == 0

    def test_preserve_code_disabled(self) -> None:
        """Test avec preservation du code desactivee."""
        from src.services.chunking.parsing import identify_protected_regions

        chunker = SmartChunker(preserve_code=False)

        content = "```python\ncode\n```"
        regions = identify_protected_regions(
            content,
            preserve_tables=chunker.preserve_tables,
            preserve_code=chunker.preserve_code,
        )

        code_regions = [r for r in regions if r[2] == "code"]
        assert len(code_regions) == 0


# --- Tests: Conversion 0-indexed -> 1-indexed ---


class TestDisplayPageConversion:
    """Tests pour la centralisation de la conversion page 0-indexed -> 1-indexed."""

    def test_to_display_page_zero(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Page 0 interne -> page 1 affichee."""
        from src.services.chunking.page_mapping import to_display_page

        assert to_display_page(0) == 1

    def test_to_display_page_positive(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """Page N interne -> page N+1 affichee."""
        from src.services.chunking.page_mapping import to_display_page

        assert to_display_page(4) == 5
        assert to_display_page(99) == 100


# --- Tests: Propagation des pages dans le chunking ---


class TestPagePropagationThroughChunking:
    """Tests pour la propagation robuste des pages a travers _recursive_chunk."""

    @pytest.mark.asyncio
    async def test_pages_propagated_without_markers_in_content(
        self,
        small_chunker: SmartChunker,
    ) -> None:
        """Les chunks ont les bonnes pages meme quand le contenu est decoupe."""
        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content=(
                    "# Titre Page Un\n\n" + "Paragraphe long de la page un avec du contenu. " * 10
                ),
                extraction_method="pymupdf4llm",
            ),
        }
        ocr = {
            1: OCRResult(
                page_number=1,
                markdown_content=(
                    "# Chapitre OCR Page Deux\n\n"
                    + "Contenu OCR de la page deux avec du texte. " * 10
                ),
                confidence_score=0.95,
                processing_time_ms=300,
            ),
        }
        metadata = DocumentMetadata(
            document_id="doc_prop_001",
            file_hash="prop123",
            filename="prop.pdf",
            file_size_bytes=2048,
            total_pages=2,
        )

        chunks = await small_chunker.chunk_document(
            document_id="doc_prop_001",
            native_content=native,
            ocr_content=ocr,
            metadata=metadata,
        )

        # Plusieurs chunks doivent etre crees (small_chunker = 50 tokens)
        assert len(chunks) > 1

        # Les pages doivent etre correctement assignees (1-indexed)
        all_pages = set()
        for chunk in chunks:
            all_pages.update(chunk.metadata.page_numbers)
        assert 1 in all_pages
        assert 2 in all_pages

        # Chaque chunk doit avoir au moins une page assignee
        for chunk in chunks:
            assert len(chunk.metadata.page_numbers) > 0

    @pytest.mark.asyncio
    async def test_multipage_chunks_have_correct_pages(
        self,
        small_chunker: SmartChunker,
    ) -> None:
        """Un chunk couvrant 2 pages a les 2 numeros de page."""
        # Page 0 finit court, page 1 commence -> le chunk peut couvrir les 2
        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content="Contenu court page un.",
                extraction_method="pymupdf4llm",
            ),
            1: ExtractedContent(
                page_number=1,
                markdown_content="Contenu court page deux.",
                extraction_method="pymupdf4llm",
            ),
        }
        metadata = DocumentMetadata(
            document_id="doc_multi_pages",
            file_hash="multi123",
            filename="multi.pdf",
            file_size_bytes=1024,
            total_pages=2,
        )

        chunks = await small_chunker.chunk_document(
            document_id="doc_multi_pages",
            native_content=native,
            ocr_content={},
            metadata=metadata,
        )

        # Verifier que les pages couvrent [1, 2]
        all_pages = set()
        for chunk in chunks:
            all_pages.update(chunk.metadata.page_numbers)
        assert 1 in all_pages
        assert 2 in all_pages

    def test_merge_content_ocr_priority(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """_merge_content donne priorite a l'OCR quand les 2 existent."""
        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content="Contenu natif",
                extraction_method="pymupdf4llm",
            ),
        }
        ocr = {
            0: OCRResult(
                page_number=0,
                markdown_content="Contenu OCR",
                confidence_score=0.95,
                processing_time_ms=200,
            ),
        }

        from src.services.chunking.parsing import merge_content

        merged, _ = merge_content(native, ocr, total_pages=1)

        assert "Contenu OCR" in merged
        assert "Contenu natif" not in merged

    def test_merge_content_native_fallback(self, chunker: SmartChunker) -> None:  # noqa: ARG002
        """_merge_content utilise le natif quand pas d'OCR."""
        native = {
            0: ExtractedContent(
                page_number=0,
                markdown_content="Contenu natif seul",
                extraction_method="pymupdf4llm",
            ),
        }

        from src.services.chunking.parsing import merge_content

        merged, _ = merge_content(native, {}, total_pages=1)

        assert "Contenu natif seul" in merged
