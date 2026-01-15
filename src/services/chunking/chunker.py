# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Chunking semantique intelligent pour documents PDF.

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


if TYPE_CHECKING:
    from src.models.document import DocumentMetadata
    from src.models.extraction import ExtractedContent, OCRResult


class SmartChunker:
    """Chunking semantique intelligent pour documents PDF.

    Cette classe decoupe le contenu extrait d'un document PDF en chunks
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

    # Patterns pour detection des regions protegees
    TABLE_PATTERN = re.compile(r"\|.+\|\n\|[-:| ]+\|\n(?:\|.+\|\n?)+")
    CODE_PATTERN = re.compile(r"```[\s\S]*?```")
    EQUATION_BLOCK_PATTERN = re.compile(r"\$\$[\s\S]*?\$\$")
    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
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
        merged_content, page_mapping = self._merge_content(
            native_content, ocr_content, metadata.total_pages
        )

        # 2. Identifier regions protegees (tableaux, code, equations)
        protected_regions = self._identify_protected_regions(merged_content)

        # 3. Parser structure (sections et hierarchie)
        sections = self._parse_sections(merged_content)

        # 4. Chunking recursif semantique
        raw_chunks = self._recursive_chunk(merged_content, protected_regions, sections)

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

    def _merge_content(
        self,
        native: dict[int, ExtractedContent],
        ocr: dict[int, OCRResult],
        total_pages: int,
    ) -> tuple[str, dict[int, tuple[int, int, int]]]:
        """Fusionne les contenus natif et OCR dans l'ordre des pages.

        Priorite: contenu natif > contenu OCR.

        Args:
            native: Contenu natif indexe par page (0-indexed).
            ocr: Contenu OCR indexe par page (0-indexed).
            total_pages: Nombre total de pages du document.

        Returns:
            Tuple contenant:
            - Le contenu fusionne en une seule chaine.
            - Un mapping page_num -> (start_pos, end_pos, page_num).
        """
        parts: list[str] = []
        page_mapping: dict[int, tuple[int, int, int]] = {}
        current_pos = 0

        for page_num in range(total_pages):
            # Marqueur de page pour tracabilite
            page_marker = f"\n<!-- Page {page_num + 1} -->\n"
            parts.append(page_marker)
            current_pos += len(page_marker)

            # Le contenu natif a la priorite sur l'OCR
            content = ""
            if page_num in native and native[page_num].markdown_content:
                content = native[page_num].markdown_content
            elif page_num in ocr and ocr[page_num].markdown_content:
                content = ocr[page_num].markdown_content

            if content:
                start_pos = current_pos
                parts.append(content)
                parts.append("\n\n")
                current_pos += len(content) + 2
                end_pos = current_pos

                # Mapping page_num -> (start, end, page) pour tracabilite
                page_mapping[page_num] = (start_pos, end_pos, page_num)

        return "".join(parts), page_mapping

    def _identify_protected_regions(
        self,
        content: str,
    ) -> list[tuple[int, int, str]]:
        """Identifie les regions a ne pas couper (tableaux, code, equations).

        Args:
            content: Contenu textuel complet.

        Returns:
            Liste de tuples (start, end, type) pour chaque region protegee,
            triee par position de debut.
        """
        regions: list[tuple[int, int, str]] = []

        # Tableaux Markdown
        if self.preserve_tables:
            for match in self.TABLE_PATTERN.finditer(content):
                regions.append((match.start(), match.end(), "table"))

        # Blocs de code
        if self.preserve_code:
            for match in self.CODE_PATTERN.finditer(content):
                regions.append((match.start(), match.end(), "code"))

        # Equations en bloc ($$...$$)
        for match in self.EQUATION_BLOCK_PATTERN.finditer(content):
            regions.append((match.start(), match.end(), "equation"))

        return sorted(regions, key=lambda x: x[0])

    def _parse_sections(self, content: str) -> list[dict[str, object]]:
        """Parse la hierarchie des sections depuis les headers Markdown.

        Args:
            content: Contenu textuel complet.

        Returns:
            Liste de dictionnaires avec les informations de section:
            - level: Niveau du header (1-6)
            - title: Titre de la section
            - hierarchy: Liste des titres parents
            - position: Position dans le texte
        """
        sections: list[dict[str, object]] = []
        current_hierarchy: list[str] = []

        for match in self.HEADER_PATTERN.finditer(content):
            level = len(match.group(1))
            title = match.group(2).strip()

            # Ajuster la hierarchie selon le niveau
            # On retire tous les elements de niveau >= au niveau actuel
            while len(current_hierarchy) >= level:
                current_hierarchy.pop()
            current_hierarchy.append(title)

            sections.append(
                {
                    "level": level,
                    "title": title,
                    "hierarchy": current_hierarchy.copy(),
                    "position": match.start(),
                }
            )

        return sections

    def _recursive_chunk(
        self,
        content: str,
        protected_regions: list[tuple[int, int, str]],
        sections: list[dict[str, object]],
    ) -> list[tuple[str, dict[str, object], str]]:
        """Chunking recursif semantique.

        Decoupe le contenu en preservant:
        - Les regions protegees (tableaux, code, equations)
        - Les limites de sections
        - L'overlap entre chunks

        Args:
            content: Contenu textuel complet.
            protected_regions: Regions a ne pas couper.
            sections: Information sur les sections.

        Returns:
            Liste de tuples (contenu, info_section, type_contenu).
        """
        chunks: list[tuple[str, dict[str, object], str]] = []
        current_chunk = ""
        current_section: dict[str, object] = {"title": None, "hierarchy": []}

        # Decouper par paragraphes (double saut de ligne)
        paragraphs = re.split(r"\n\n+", content)

        for raw_para in paragraphs:
            para = raw_para.strip()
            if not para:
                continue

            # Ignorer les marqueurs de page
            if self.PAGE_MARKER_PATTERN.match(para):
                continue

            # Detecter si c'est un header
            header_match = re.match(r"^(#{1,6})\s+(.+)$", para)
            if header_match:
                # Sauvegarder le chunk courant avant de changer de section
                if self._should_save_chunk(current_chunk):
                    chunks.append(
                        (
                            current_chunk.strip(),
                            dict(current_section),
                            "text",
                        )
                    )
                    current_chunk = ""

                # Mettre a jour la section courante
                current_section = {
                    "title": header_match.group(2),
                    "hierarchy": self._get_hierarchy_at(content.find(para), sections),
                }
                current_chunk = para + "\n\n"
                continue

            # Verifier si le paragraphe est dans une region protegee
            is_protected, region_type = self._is_in_protected(para, content, protected_regions)

            if is_protected:
                # Sauvegarder le chunk courant
                if self._should_save_chunk(current_chunk):
                    chunks.append(
                        (
                            current_chunk.strip(),
                            dict(current_section),
                            "text",
                        )
                    )
                    current_chunk = ""

                # L'element protege forme son propre chunk
                chunks.append((para, dict(current_section), region_type))
                continue

            # Verifier la taille avec ce paragraphe
            test_chunk = current_chunk + para + "\n\n"
            token_count = self._count_tokens(test_chunk)

            # Cas simple: le paragraphe tient dans le chunk
            if token_count <= self.chunk_size:
                current_chunk = test_chunk
                continue

            # Chunk plein: sauvegarder et recommencer avec overlap
            if self._should_save_chunk(current_chunk):
                chunks.append(
                    (
                        current_chunk.strip(),
                        dict(current_section),
                        "text",
                    )
                )

            overlap = self._get_overlap(current_chunk)
            current_chunk = overlap + para + "\n\n"

        # Sauvegarder le dernier chunk
        if self._should_save_chunk(current_chunk):
            chunks.append(
                (
                    current_chunk.strip(),
                    dict(current_section),
                    "text",
                )
            )

        return chunks

    def _build_document_chunks(
        self,
        raw_chunks: list[tuple[str, dict[str, object], str]],
        document_id: str,
        merged_content: str,
        page_mapping: dict[int, tuple[int, int, int]],
    ) -> list[DocumentChunk]:
        """Construit les DocumentChunk a partir des chunks bruts.

        Args:
            raw_chunks: Liste de tuples (contenu, info_section, type).
            document_id: Identifiant du document.
            merged_content: Contenu fusionne complet.
            page_mapping: Mapping page_num -> (start_pos, end_pos, page_num).

        Returns:
            Liste de DocumentChunk enrichis.
        """
        chunks: list[DocumentChunk] = []

        for i, (content, section_info, content_type) in enumerate(raw_chunks):
            # Determiner les pages du chunk
            pages = self._get_pages_for_chunk(content, merged_content, page_mapping)

            # Extraire le contexte environnant
            chunk_start = merged_content.find(content)
            context_size = 100

            preceding_start = max(0, chunk_start - context_size)
            preceding = merged_content[preceding_start:chunk_start]

            following_end = min(len(merged_content), chunk_start + len(content) + context_size)
            following = merged_content[chunk_start + len(content) : following_end]

            # Extraire la hierarchie comme liste de str
            hierarchy_raw = section_info.get("hierarchy", [])
            hierarchy: list[str] = (
                [str(h) for h in hierarchy_raw] if isinstance(hierarchy_raw, list) else []
            )

            # Extraire le titre de section
            section_title_raw = section_info.get("title")
            section_title: str | None = (
                str(section_title_raw) if section_title_raw is not None else None
            )

            # Construire les metadonnees
            chunk_metadata = ChunkMetadata(
                chunk_id=f"{document_id}_chunk_{i}",
                document_id=document_id,
                page_numbers=pages,
                start_page=min(pages) if pages else 0,
                end_page=max(pages) if pages else 0,
                section_title=section_title,
                section_hierarchy=hierarchy,
                chunk_index=i,
                content_type=content_type,
                has_table=self._has_table(content),
                has_image=self._has_image(content),
                has_equation=self._has_equation(content),
                token_count=self._count_tokens(content),
                char_count=len(content),
                word_count=len(content.split()),
                preceding_context=preceding.strip(),
                following_context=following.strip(),
            )

            # Contenu enrichi pour meilleur embedding
            enriched = self._enrich_for_embedding(content, chunk_metadata)

            chunks.append(
                DocumentChunk(
                    content=content,
                    metadata=chunk_metadata,
                    content_with_context=enriched,
                )
            )

        return chunks

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
            if isinstance(section_pos, int) and section_pos <= pos:
                section_hierarchy = section.get("hierarchy", [])
                if isinstance(section_hierarchy, list):
                    hierarchy = [str(h) for h in section_hierarchy]
            else:
                break

        return hierarchy

    def _get_pages_for_chunk(
        self,
        chunk: str,
        full_content: str,
        page_mapping: dict[int, tuple[int, int, int]],
    ) -> list[int]:
        """Determine les pages couvertes par un chunk.

        Utilise les marqueurs <!-- Page X --> dans le chunk ou la position.

        Args:
            chunk: Contenu du chunk.
            full_content: Contenu complet.
            page_mapping: Mapping page_num -> (start_pos, end_pos, page_num).

        Returns:
            Liste des numeros de pages (1-indexed) triee.
        """
        pages: set[int] = set()

        # Methode 1: Extraire les marqueurs de page du chunk
        page_markers = re.findall(r"<!--\s*Page\s+(\d+)\s*-->", chunk)
        if page_markers:
            for marker in page_markers:
                pages.add(int(marker))

        # Methode 2: Chercher la position du chunk dans le contenu original
        if not pages:
            chunk_start = full_content.find(chunk)
            if chunk_start != -1:
                chunk_end = chunk_start + len(chunk)

                for page_num, (page_start, page_end, _) in page_mapping.items():
                    if chunk_start < page_end and chunk_end > page_start:
                        pages.add(page_num + 1)

        # Methode 3: Chercher avec le debut du chunk (premiers 200 chars)
        if not pages and len(chunk) > 50:
            chunk_prefix = chunk[:200]
            chunk_start = full_content.find(chunk_prefix)
            if chunk_start != -1:
                for page_num, (page_start, page_end, _) in page_mapping.items():
                    if page_start <= chunk_start < page_end:
                        pages.add(page_num + 1)
                        break

        return sorted(pages) if pages else [1]

    def _has_table(self, content: str) -> bool:
        """Detecte la presence d'un tableau Markdown.

        Args:
            content: Contenu a analyser.

        Returns:
            True si un tableau est detecte.
        """
        return bool(re.search(r"\|.+\|.*\n\|[-:| ]+\|", content))

    def _has_image(self, content: str) -> bool:
        """Detecte la presence d'une image Markdown.

        Args:
            content: Contenu a analyser.

        Returns:
            True si une image est detectee.
        """
        return "![" in content

    def _has_equation(self, content: str) -> bool:
        """Detecte la presence d'une equation LaTeX.

        Args:
            content: Contenu a analyser.

        Returns:
            True si une equation est detectee.
        """
        return "$" in content

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
