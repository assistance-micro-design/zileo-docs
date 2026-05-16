# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Chunking semantique intelligent pour documents.

Ce module fournit un chunker intelligent qui:
- Preserve les tableaux et blocs de code intacts
- Detecte la structure hierarchique (headers, sections)
- Compte les tokens avec tiktoken
- Gere l'overlap entre chunks
- Enrichit le contenu pour un meilleur embedding
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import tiktoken

from src.core.config import settings
from src.models.chunk import ChunkMetadata, DocumentChunk
from src.services.chunking.content_detection import has_equation, has_image, has_table
from src.services.chunking.page_mapping import get_pages_at_position, get_pages_for_chunk
from src.services.chunking.parsing import (
    identify_protected_regions,
    merge_content,
    parse_sections,
)


if TYPE_CHECKING:
    from src.models.document import DocumentMetadata
    from src.models.extraction import ExtractedContent, OCRResult


class SmartChunker:
    """Chunking semantique intelligent pour documents.

    Cette classe decoupe le contenu extrait d'un document en chunks
    optimises pour la recherche semantique et l'embedding.

    Attributes:
        chunk_size: Taille cible des chunks en tokens.
        chunk_overlap: Nombre de tokens de chevauchement entre chunks.
        min_chunk_size: Taille minimum d'un chunk en tokens.
        preserve_tables: Conserver les tableaux intacts.
        preserve_code: Conserver les blocs de code intacts.
        tokenizer: Encodeur tiktoken pour comptage precis des tokens.

    Example:
        >>> chunker = SmartChunker(chunk_size=512, chunk_overlap=50)
        >>> chunks = await chunker.chunk_document(
        ...     document_id="doc_123",
        ...     native_content={0: extracted_content},
        ...     ocr_content={},
        ...     metadata=doc_metadata,
        ... )
    """

    # Pattern utilise dans le chunking recursif pour detecter les marqueurs
    PAGE_MARKER_PATTERN = re.compile(r"^<!-- Page \d+ -->$")

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        min_chunk_size: int = 100,
        preserve_tables: bool = True,
        preserve_code: bool = True,
    ) -> None:
        """Initialise le chunker avec les parametres de configuration.

        Args:
            chunk_size: Taille cible des chunks en tokens.
                Defaut: valeur de settings.CHUNK_SIZE.
            chunk_overlap: Nombre de tokens de chevauchement.
                Defaut: valeur de settings.CHUNK_OVERLAP.
            min_chunk_size: Taille minimum d'un chunk en tokens.
            preserve_tables: Si True, garde les tableaux intacts.
            preserve_code: Si True, garde les blocs de code intacts.
        """
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.min_chunk_size = min_chunk_size
        self.preserve_tables = preserve_tables
        self.preserve_code = preserve_code

        # Tokenizer pour comptage precis (compatible GPT-4/Claude)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    async def chunk_document(
        self,
        document_id: str,
        native_content: dict[int, ExtractedContent],
        ocr_content: dict[int, OCRResult],
        metadata: DocumentMetadata,
    ) -> list[DocumentChunk]:
        """Point d'entree principal du chunking.

        Fusionne le contenu natif et OCR, puis decoupe en chunks optimises
        pour la recherche semantique.

        Args:
            document_id: Identifiant unique du document.
            native_content: Contenu extrait nativement, indexe par numero de page.
            ocr_content: Contenu extrait par OCR, indexe par numero de page.
            metadata: Metadonnees du document.

        Returns:
            Liste de DocumentChunk prets pour embedding.

        Example:
            >>> chunks = await chunker.chunk_document(
            ...     document_id="doc_123",
            ...     native_content={0: content_page_1},
            ...     ocr_content={1: ocr_page_2},
            ...     metadata=doc_metadata,
            ... )
        """
        # 1. Fusionner contenus dans l'ordre des pages
        merged_content, page_mapping = merge_content(
            native_content, ocr_content, metadata.total_pages
        )

        # 2. Identifier regions protegees (tableaux, code, equations)
        protected_regions = identify_protected_regions(
            merged_content,
            preserve_tables=self.preserve_tables,
            preserve_code=self.preserve_code,
        )

        # 3. Parser structure (sections et hierarchie)
        sections = parse_sections(merged_content)

        # 4. Chunking recursif semantique (avec propagation des pages)
        raw_chunks = self._recursive_chunk(
            merged_content, protected_regions, sections, page_mapping
        )

        # 5. Enrichir avec metadata et construire DocumentChunk
        chunks = self._build_document_chunks(
            raw_chunks=raw_chunks,
            document_id=document_id,
            merged_content=merged_content,
            page_mapping=page_mapping,
        )

        # 6. Mettre a jour total_chunks dans tous les chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk.metadata.total_chunks = total_chunks

        return chunks

    def _recursive_chunk(
        self,
        content: str,
        protected_regions: list[tuple[int, int, str]],
        sections: list[dict[str, object]],
        page_mapping: dict[int, tuple[int, int, int]] | None = None,
    ) -> list[tuple[str, dict[str, object], str, set[int]]]:
        """Chunking recursif semantique.

        Decoupe le contenu en preservant:
        - Les regions protegees (tableaux, code, equations)
        - Les limites de sections
        - L'overlap entre chunks
        - Les numeros de pages par chunk (propages via page_mapping)

        Args:
            content: Contenu textuel complet.
            protected_regions: Regions a ne pas couper.
            sections: Information sur les sections.
            page_mapping: Mapping page_num -> (start_pos, end_pos, page_num).

        Returns:
            Liste de tuples (contenu, info_section, type_contenu, pages_set).
        """
        chunks: list[tuple[str, dict[str, object], str, set[int]]] = []
        chunk = ""
        pages: set[int] = set()
        section: dict[str, object] = {"title": None, "hierarchy": []}

        for raw_para in re.split(r"\n\n+", content):
            para = raw_para.strip()
            if not para or self.PAGE_MARKER_PATTERN.match(para):
                continue

            para_pages = get_pages_at_position(content.find(para), len(para), page_mapping)
            chunk, pages, section = self._dispatch_paragraph(
                para,
                chunks,
                chunk,
                pages,
                section,
                content,
                sections,
                protected_regions,
                para_pages,
            )

        self._save_current_chunk_with_pages(chunks, chunk, section, pages)
        return chunks

    def _dispatch_paragraph(
        self,
        para: str,
        chunks: list[tuple[str, dict[str, object], str, set[int]]],
        chunk: str,
        pages: set[int],
        section: dict[str, object],
        content: str,
        sections: list[dict[str, object]],
        protected_regions: list[tuple[int, int, str]],
        para_pages: set[int],
    ) -> tuple[str, set[int], dict[str, object]]:
        """Traite un paragraphe et retourne le nouvel etat (chunk, pages, section)."""
        header_match = re.match(r"^(#{1,6})\s+(.+)$", para)
        if header_match:
            self._save_current_chunk_with_pages(chunks, chunk, section, pages)
            return self._start_chunk_at_header(header_match, content, sections, para_pages)

        is_protected, region_type = self._is_in_protected(para, content, protected_regions)
        if is_protected:
            self._save_current_chunk_with_pages(chunks, chunk, section, pages)
            chunks.append((para, dict(section), region_type, set(para_pages)))
            return "", set(), section

        test_chunk = chunk + para + "\n\n"
        if self._count_tokens(test_chunk) <= self.chunk_size:
            return test_chunk, pages | para_pages, section

        self._save_current_chunk_with_pages(chunks, chunk, section, pages)
        return self._get_overlap(chunk) + para + "\n\n", set(para_pages), section

    def _start_chunk_at_header(
        self,
        header_match: re.Match[str],
        content: str,
        sections: list[dict[str, object]],
        para_pages: set[int],
    ) -> tuple[str, set[int], dict[str, object]]:
        """Construit le chunk initial pour un nouveau header."""
        new_section: dict[str, object] = {
            "title": header_match.group(2),
            "hierarchy": self._get_hierarchy_at(content.find(header_match.group(0)), sections),
        }
        return header_match.group(0) + "\n\n", set(para_pages), new_section

    def _save_current_chunk_with_pages(
        self,
        chunks: list[tuple[str, dict[str, object], str, set[int]]],
        chunk: str,
        section_info: dict[str, object],
        pages: set[int],
    ) -> None:
        """Valide et ajoute le chunk courant a la liste avec ses pages."""
        if self._should_save_chunk(chunk):
            chunks.append((chunk.strip(), dict(section_info), "text", set(pages)))

    def _build_document_chunks(
        self,
        raw_chunks: list[tuple[str, dict[str, object], str, set[int]]],
        document_id: str,
        merged_content: str,
        page_mapping: dict[int, tuple[int, int, int]],
    ) -> list[DocumentChunk]:
        """Construit les DocumentChunk a partir des chunks bruts.

        Args:
            raw_chunks: Liste de tuples (contenu, info_section, type, pages).
            document_id: Identifiant du document.
            merged_content: Contenu fusionne complet.
            page_mapping: Mapping page_num -> (start_pos, end_pos, page_num).

        Returns:
            Liste de DocumentChunk enrichis.
        """
        chunks: list[DocumentChunk] = []

        for i, (content, section_info, content_type, propagated_pages) in enumerate(raw_chunks):
            pages = (
                sorted(propagated_pages)
                if propagated_pages
                else get_pages_for_chunk(content, merged_content, page_mapping)
            )
            preceding, following = self._extract_chunk_context(content, merged_content)
            chunk_metadata = self._build_chunk_metadata(
                content,
                section_info,
                content_type,
                i,
                document_id,
                pages,
                preceding,
                following,
            )

            enriched = self._enrich_for_embedding(content, chunk_metadata)
            chunks.append(
                DocumentChunk(
                    content=content,
                    metadata=chunk_metadata,
                    content_with_context=enriched,
                )
            )

        return chunks

    def _extract_chunk_context(
        self, content: str, merged_content: str, context_size: int = 100
    ) -> tuple[str, str]:
        """Extrait le contexte precedent et suivant d'un chunk."""
        chunk_start = merged_content.find(content)
        preceding_start = max(0, chunk_start - context_size)
        preceding = merged_content[preceding_start:chunk_start]
        following_end = min(len(merged_content), chunk_start + len(content) + context_size)
        following = merged_content[chunk_start + len(content) : following_end]
        return preceding.strip(), following.strip()

    def _build_chunk_metadata(
        self,
        content: str,
        section_info: dict[str, object],
        content_type: str,
        index: int,
        document_id: str,
        pages: list[int],
        preceding: str,
        following: str,
    ) -> ChunkMetadata:
        """Construit les metadonnees d'un chunk."""
        hierarchy_raw = section_info.get("hierarchy", [])
        hierarchy: list[str] = (
            [str(h) for h in hierarchy_raw] if isinstance(hierarchy_raw, list) else []
        )
        section_title_raw = section_info.get("title")
        section_title: str | None = (
            str(section_title_raw) if section_title_raw is not None else None
        )

        return ChunkMetadata(
            chunk_id=f"{document_id}_chunk_{index}",
            document_id=document_id,
            page_numbers=pages,
            start_page=min(pages) if pages else 0,
            end_page=max(pages) if pages else 0,
            section_title=section_title,
            section_hierarchy=hierarchy,
            chunk_index=index,
            content_type=content_type,
            has_table=has_table(content),
            has_image=has_image(content),
            has_equation=has_equation(content),
            token_count=self._count_tokens(content),
            char_count=len(content),
            word_count=len(content.split()),
            preceding_context=preceding,
            following_context=following,
        )

    def _should_save_chunk(self, chunk: str) -> bool:
        """Verifie si le chunk doit etre sauvegarde.

        Un chunk est sauvegarde s'il n'est pas vide et atteint
        la taille minimum en tokens.

        Args:
            chunk: Contenu du chunk.

        Returns:
            True si le chunk doit etre sauvegarde.
        """
        if not chunk.strip():
            return False
        token_count = self._count_tokens(chunk)
        return token_count >= self.min_chunk_size

    def _is_in_protected(
        self,
        text: str,
        full_content: str,
        protected: list[tuple[int, int, str]],
    ) -> tuple[bool, str]:
        """Verifie si le texte est dans une region protegee.

        Args:
            text: Texte a verifier.
            full_content: Contenu complet.
            protected: Liste des regions protegees.

        Returns:
            Tuple (est_protege, type_region).
        """
        pos = full_content.find(text)
        if pos == -1:
            return False, ""

        for start, end, region_type in protected:
            if start <= pos < end:
                return True, region_type

        return False, ""

    def _get_overlap(self, chunk: str) -> str:
        """Extrait l'overlap de la fin du chunk.

        L'overlap permet une meilleure continuite semantique
        entre chunks adjacents.

        Args:
            chunk: Contenu du chunk.

        Returns:
            Texte de l'overlap (derniers N tokens).
        """
        if not chunk:
            return ""

        tokens = self.tokenizer.encode(chunk)
        if len(tokens) > self.chunk_overlap:
            overlap_tokens = tokens[-self.chunk_overlap :]
            decoded: str = self.tokenizer.decode(overlap_tokens)
            return decoded

        return ""

    def _get_hierarchy_at(
        self,
        pos: int,
        sections: list[dict[str, object]],
    ) -> list[str]:
        """Trouve la hierarchie de section a une position donnee.

        Args:
            pos: Position dans le texte.
            sections: Liste des sections parsees.

        Returns:
            Liste des titres de section (du plus haut au plus bas niveau).
        """
        hierarchy: list[str] = []

        for section in sections:
            section_pos = section.get("position", 0)
            if not (isinstance(section_pos, int) and section_pos <= pos):
                break
            section_hierarchy = section.get("hierarchy", [])
            if isinstance(section_hierarchy, list):
                hierarchy = [str(h) for h in section_hierarchy]

        return hierarchy

    def _count_tokens(self, text: str) -> int:
        """Compte le nombre de tokens dans un texte.

        Utilise tiktoken avec l'encodage cl100k_base
        (compatible GPT-4, Claude).

        Args:
            text: Texte a analyser.

        Returns:
            Nombre de tokens.
        """
        return len(self.tokenizer.encode(text))

    def _enrich_for_embedding(
        self,
        content: str,
        metadata: ChunkMetadata,
    ) -> str:
        """Enrichit le contenu pour un meilleur embedding.

        Ajoute des informations contextuelles (section, type)
        qui ameliorent la qualite de l'embedding.

        Args:
            content: Contenu du chunk.
            metadata: Metadonnees du chunk.

        Returns:
            Contenu enrichi avec contexte.
        """
        parts: list[str] = []

        # Ajouter la hierarchie de section
        if metadata.section_hierarchy:
            hierarchy_str = " > ".join(metadata.section_hierarchy)
            parts.append(f"Section: {hierarchy_str}")

        # Ajouter le type de contenu si special
        if metadata.content_type != "text":
            parts.append(f"Type: {metadata.content_type}")

        # Contenu principal
        parts.append(content)

        return "\n".join(parts)

    def count_tokens(self, text: str) -> int:
        """Methode publique pour compter les tokens.

        Args:
            text: Texte a analyser.

        Returns:
            Nombre de tokens.
        """
        return self._count_tokens(text)
