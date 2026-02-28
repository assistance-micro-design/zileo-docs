# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Orchestrateur du pipeline de traitement PDF.

Coordonne les 5 phases du pipeline:
1. Analyse du document (classification des pages)
2. Extraction native (PyMuPDF4LLM pour pages simples)
3. OCR Mistral (pour pages complexes)
4. Chunking semantique + Embeddings
5. Stockage vectoriel (Qdrant)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.models.chunk import DocumentChunk
from src.models.document import DocumentAnalysisResult
from src.models.extraction import ExtractedContent, OCRResult
from src.services.chunking.chunker import SmartChunker
from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.pdf.analyzer import DocumentAnalyzer
from src.services.pdf.native_extractor import NativeContentExtractor
from src.services.pdf.ocr_processor import MistralOCRProcessor
from src.services.vector.qdrant_store import QdrantVectorStore


@dataclass
class ProcessingResult:
    """Resultat complet du pipeline de traitement.

    Attributes:
        analysis: Resultat de l'analyse du document.
        native_content: Contenu extrait nativement.
        ocr_content: Contenu extrait par OCR.
        processing_time_seconds: Temps total de traitement.
        chunks: Chunks generes avec embeddings (Phase 4).
        vector_store_result: Resultat du stockage vectoriel (Phase 5).
    """

    analysis: DocumentAnalysisResult
    native_content: dict[int, ExtractedContent]
    ocr_content: dict[int, OCRResult]
    processing_time_seconds: float = 0.0

    # Statistiques extraction
    pages_processed_native: int = 0
    pages_processed_ocr: int = 0

    # Phase 4: Chunking + Embedding
    chunks: list[DocumentChunk] = field(default_factory=list)
    chunks_generated: int = 0
    chunks_embedded: int = 0

    # Phase 5: Vector Storage
    vector_store_result: dict[str, Any] = field(default_factory=dict)
    chunks_stored: int = 0

    # Erreurs
    total_errors: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "analysis": self.analysis.to_dict(),
            "native_content": {str(k): v.to_dict() for k, v in self.native_content.items()},
            "ocr_content": {str(k): v.to_dict() for k, v in self.ocr_content.items()},
            "processing_time_seconds": self.processing_time_seconds,
            "pages_processed_native": self.pages_processed_native,
            "pages_processed_ocr": self.pages_processed_ocr,
            # Phase 4
            "chunks_generated": self.chunks_generated,
            "chunks_embedded": self.chunks_embedded,
            # Phase 5
            "vector_store_result": self.vector_store_result,
            "chunks_stored": self.chunks_stored,
            # Erreurs
            "total_errors": self.total_errors,
            "errors": self.errors,
        }

    def get_all_content_markdown(self) -> str:
        """Retourne tout le contenu Markdown concatene par ordre de page.

        Returns:
            Contenu Markdown complet du document.
        """
        all_pages: dict[int, str] = {}

        # Ajouter contenu natif
        for page_num, native_content in self.native_content.items():
            all_pages[page_num] = native_content.markdown_content

        # Ajouter contenu OCR
        for page_num, ocr_content in self.ocr_content.items():
            all_pages[page_num] = ocr_content.markdown_content

        # Trier par numero de page et concatener
        sorted_pages = sorted(all_pages.items())
        return "\n\n---\n\n".join(
            f"<!-- Page {page_num + 1} -->\n{content}" for page_num, content in sorted_pages
        )


class PDFPipelineOrchestrator:
    """Orchestre le pipeline complet d'extraction et indexation PDF.

    Coordonne les 5 phases du pipeline:
    1. Analyse du document (classification des pages)
    2. Extraction native (PyMuPDF4LLM pour pages simples)
    3. OCR Mistral (pour pages complexes)
    4. Chunking semantique + Embeddings Mistral
    5. Stockage vectoriel Qdrant

    Attributes:
        settings: Configuration de l'application.

    Example:
        >>> orchestrator = PDFPipelineOrchestrator()
        >>> await orchestrator.initialize()
        >>> result = await orchestrator.process_and_index("document.pdf")
        >>> print(f"Indexed {result.chunks_stored} chunks")
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialise l'orchestrateur.

        Args:
            api_key: Cle API Mistral optionnelle pour OCR et embeddings.
        """
        self._api_key = api_key or settings.MISTRAL_API_KEY
        self._ocr_processor: MistralOCRProcessor | None = None
        self._embedder: MistralEmbedder | None = None
        self._chunker: SmartChunker | None = None
        self._vector_store: QdrantVectorStore | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialise les services dependants (vector store).

        Doit etre appele avant process_and_index() pour garantir
        que la collection Qdrant existe.
        """
        if not self._initialized:
            await self.vector_store.initialize()
            self._initialized = True

    @property
    def ocr_processor(self) -> MistralOCRProcessor:
        """Retourne le processeur OCR (lazy initialization)."""
        if self._ocr_processor is None:
            self._ocr_processor = MistralOCRProcessor(self._api_key)
        return self._ocr_processor

    @property
    def embedder(self) -> MistralEmbedder:
        """Retourne l'embedder Mistral (lazy initialization)."""
        if self._embedder is None:
            self._embedder = MistralEmbedder(self._api_key)
        return self._embedder

    @property
    def chunker(self) -> SmartChunker:
        """Retourne le chunker semantique (lazy initialization)."""
        if self._chunker is None:
            self._chunker = SmartChunker()
        return self._chunker

    @property
    def vector_store(self) -> QdrantVectorStore:
        """Retourne le vector store Qdrant (lazy initialization)."""
        if self._vector_store is None:
            self._vector_store = QdrantVectorStore()
        return self._vector_store

    async def process_document(
        self,
        pdf_path: str | Path,
        options: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        """Execute le pipeline complet sur un document.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            options: Options de traitement optionnelles.
                - force_ocr: bool - Forcer OCR sur toutes les pages.
                - table_format: str - Format des tableaux (markdown/html).
                - skip_ocr: bool - Ignorer le traitement OCR.

        Returns:
            ProcessingResult avec tout le contenu extrait.
        """
        pdf_path = Path(pdf_path)
        options = options or {}
        start_time = datetime.now(UTC)
        errors: list[dict[str, Any]] = []

        # Phase 1: Analyse du document
        original_filename = options.get("original_filename")
        analyzer = DocumentAnalyzer(pdf_path, original_filename=original_filename)
        analysis = await analyzer.analyze()

        # Default: utiliser l'analyse
        pages_for_native = analysis.pages_for_local_extraction
        pages_for_ocr = analysis.pages_for_ocr

        # Override si force_ocr
        if options.get("force_ocr", False):
            pages_for_native = []
            pages_for_ocr = list(range(analysis.metadata.total_pages))

        # Phase 2: Extraction native (pages simples)
        native_content = await self._extract_native_pages(pdf_path, pages_for_native, errors)

        # Phase 3: OCR (pages complexes)
        ocr_content = await self._extract_ocr_pages(pdf_path, pages_for_ocr, options, errors)

        # Calculer temps de traitement
        end_time = datetime.now(UTC)
        processing_time = (end_time - start_time).total_seconds()

        # Marquer le document comme traite
        analysis.metadata.processed_at = end_time

        return ProcessingResult(
            analysis=analysis,
            native_content=native_content,
            ocr_content=ocr_content,
            processing_time_seconds=processing_time,
            pages_processed_native=len(native_content),
            pages_processed_ocr=len(ocr_content),
            total_errors=len(errors),
            errors=errors,
        )

    async def _extract_native_pages(
        self,
        pdf_path: Path,
        pages: list[int],
        errors: list[dict[str, Any]],
    ) -> dict[int, ExtractedContent]:
        """Phase 2: Extraction native des pages simples."""
        if not pages:
            return {}
        try:
            extractor = NativeContentExtractor(pdf_path)
            return await extractor.extract_pages(pages)
        except Exception as e:
            errors.append({"phase": "native_extraction", "error": str(e), "pages": pages})
            return {}

    async def _extract_ocr_pages(
        self,
        pdf_path: Path,
        pages: list[int],
        options: dict[str, Any],
        errors: list[dict[str, Any]],
    ) -> dict[int, OCRResult]:
        """Phase 3: Extraction OCR des pages complexes."""
        if not pages or options.get("skip_ocr", False):
            return {}
        try:
            ocr_options = {
                "table_format": options.get("table_format", settings.OCR_TABLE_FORMAT),
                "include_image_base64": options.get("include_images", False),
            }
            ocr_content = await self.ocr_processor.process_pages(
                pdf_path,
                pages,
                ocr_options,
            )
            for page_num, result in ocr_content.items():
                if result.confidence_score == 0.0 and "Error" in result.markdown_content:
                    errors.append(
                        {"phase": "ocr", "error": result.markdown_content, "page": page_num}
                    )
            return ocr_content
        except Exception as e:
            errors.append({"phase": "ocr", "error": str(e), "pages": pages})
            return {}

    async def analyze_only(
        self,
        pdf_path: str | Path,
    ) -> DocumentAnalysisResult:
        """Execute uniquement la phase d'analyse.

        Utile pour obtenir un apercu du document avant traitement complet.

        Args:
            pdf_path: Chemin vers le fichier PDF.

        Returns:
            DocumentAnalysisResult avec l'analyse du document.
        """
        analyzer = DocumentAnalyzer(pdf_path)
        return await analyzer.analyze()

    async def extract_pages(
        self,
        pdf_path: str | Path,
        page_numbers: list[int],
        *,
        force_ocr: bool = False,
    ) -> dict[int, ExtractedContent | OCRResult]:
        """Extrait le contenu de pages specifiques.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            page_numbers: Liste des numeros de pages a extraire (0-indexed).
            force_ocr: Forcer OCR meme pour les pages simples.

        Returns:
            Dictionnaire {page_number: ExtractedContent | OCRResult}.
        """
        pdf_path = Path(pdf_path)
        results: dict[int, ExtractedContent | OCRResult] = {}

        # Cas force_ocr: tout par OCR
        if force_ocr:
            ocr_results = await self.ocr_processor.process_pages(pdf_path, page_numbers)
            results.update(ocr_results)
            return results

        # Cas normal: analyser puis router
        analyzer = DocumentAnalyzer(pdf_path)
        analysis = await analyzer.analyze()

        # Separer les pages
        pages_native = [p for p in page_numbers if p in analysis.pages_for_local_extraction]
        pages_ocr = [p for p in page_numbers if p in analysis.pages_for_ocr]

        # Extraire nativement
        if pages_native:
            extractor = NativeContentExtractor(pdf_path)
            native_results = await extractor.extract_pages(pages_native)
            results.update(native_results)

        # Extraire par OCR
        if pages_ocr:
            ocr_results = await self.ocr_processor.process_pages(pdf_path, pages_ocr)
            results.update(ocr_results)

        return results

    async def process_and_index(
        self,
        pdf_path: str | Path,
        options: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        """Execute le pipeline complet: extraction + chunking + embedding + stockage.

        Pipeline complet en 5 phases:
        1. Analyse du document (classification des pages)
        2. Extraction native (PyMuPDF4LLM pour pages simples)
        3. OCR Mistral (pour pages complexes)
        4. Chunking semantique + Embeddings Mistral
        5. Stockage vectoriel Qdrant

        Args:
            pdf_path: Chemin vers le fichier PDF.
            options: Options de traitement optionnelles.
                - force_ocr: bool - Forcer OCR sur toutes les pages.
                - table_format: str - Format des tableaux (markdown/html).
                - skip_ocr: bool - Ignorer le traitement OCR.
                - skip_embedding: bool - Ne pas generer d'embeddings.
                - skip_storage: bool - Ne pas stocker dans Qdrant.

        Returns:
            ProcessingResult avec tout le contenu, chunks et stats.

        Example:
            >>> orchestrator = PDFPipelineOrchestrator()
            >>> await orchestrator.initialize()
            >>> result = await orchestrator.process_and_index("rapport.pdf")
            >>> print(f"Chunks: {result.chunks_generated}, Stored: {result.chunks_stored}")
        """
        pdf_path = Path(pdf_path)
        options = options or {}
        start_time = datetime.now(UTC)
        errors: list[dict[str, Any]] = []

        # Initialiser si necessaire
        if not self._initialized:
            await self.initialize()

        # Phases 1-3: Extraction (via process_document existant)
        extraction_result = await self.process_document(pdf_path, options)
        errors.extend(extraction_result.errors)

        # Phase 4: Chunking + Embedding
        chunks, chunks_generated, chunks_embedded = await self._chunk_and_embed(
            extraction_result, options, errors
        )

        # Phase 5: Stockage vectoriel
        vector_store_result, chunks_stored = await self._store_indexed_chunks(
            chunks, extraction_result, options, errors
        )

        return self._build_processing_result(
            extraction_result,
            chunks,
            chunks_generated,
            chunks_embedded,
            vector_store_result,
            chunks_stored,
            errors,
            start_time,
        )

    async def _chunk_and_embed(
        self,
        extraction_result: ProcessingResult,
        options: dict[str, Any],
        errors: list[dict[str, Any]],
    ) -> tuple[list[DocumentChunk], int, int]:
        """Phase 4: Chunking semantique + Embeddings Mistral."""
        if options.get("skip_embedding", False):
            return [], 0, 0
        try:
            chunks = await self.chunker.chunk_document(
                document_id=extraction_result.analysis.metadata.document_id,
                native_content=extraction_result.native_content,
                ocr_content=extraction_result.ocr_content,
                metadata=extraction_result.analysis.metadata,
            )
            chunks_generated = len(chunks)
            chunks_embedded = 0
            if chunks:
                chunks = await self.embedder.embed_chunks(chunks, use_enriched=True)
                chunks_embedded = sum(1 for c in chunks if c.has_embedding)
            return chunks, chunks_generated, chunks_embedded
        except Exception as e:
            errors.append({"phase": "chunking_embedding", "error": str(e)})
            return [], 0, 0

    async def _store_indexed_chunks(
        self,
        chunks: list[DocumentChunk],
        extraction_result: ProcessingResult,
        options: dict[str, Any],
        errors: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], int]:
        """Phase 5: Stockage vectoriel dans Qdrant."""
        if not chunks or options.get("skip_storage", False):
            return {}, 0
        try:
            result = await self.vector_store.store_chunks(
                chunks=chunks,
                document_metadata=extraction_result.analysis.metadata,
            )
            return result, result.get("stored_chunks", 0)
        except Exception as e:
            errors.append({"phase": "vector_storage", "error": str(e)})
            return {}, 0

    def _build_processing_result(
        self,
        extraction_result: ProcessingResult,
        chunks: list[DocumentChunk],
        chunks_generated: int,
        chunks_embedded: int,
        vector_store_result: dict[str, Any],
        chunks_stored: int,
        errors: list[dict[str, Any]],
        start_time: datetime,
    ) -> ProcessingResult:
        """Assemble le ProcessingResult final."""
        total_processing_time = (datetime.now(UTC) - start_time).total_seconds()
        return ProcessingResult(
            analysis=extraction_result.analysis,
            native_content=extraction_result.native_content,
            ocr_content=extraction_result.ocr_content,
            processing_time_seconds=total_processing_time,
            pages_processed_native=extraction_result.pages_processed_native,
            pages_processed_ocr=extraction_result.pages_processed_ocr,
            chunks=chunks,
            chunks_generated=chunks_generated,
            chunks_embedded=chunks_embedded,
            vector_store_result=vector_store_result,
            chunks_stored=chunks_stored,
            total_errors=len(errors),
            errors=errors,
        )

    async def search_documents(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Recherche semantique dans les documents indexes.

        Args:
            query: Requete de recherche en langage naturel.
            top_k: Nombre maximum de resultats. Defaut 5.
            filters: Filtres optionnels (document_id, content_type, etc.).
            score_threshold: Score minimum de similarite. Defaut 0.7.

        Returns:
            Liste des chunks correspondants avec scores.

        Example:
            >>> results = await orchestrator.search_documents(
            ...     "comment configurer l'authentification?",
            ...     top_k=10,
            ...     filters={"document_id": "doc-123"},
            ... )
            >>> for r in results:
            ...     print(f"{r['score']:.2f}: {r['content_preview']}")
        """
        # Generer embedding de la requete
        query_embedding = await self.embedder.embed_query(query)

        # Rechercher dans Qdrant
        return await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters,
            score_threshold=score_threshold,
        )

    async def delete_document(self, document_id: str) -> int:
        """Supprime un document de l'index vectoriel.

        Args:
            document_id: Identifiant du document a supprimer.

        Returns:
            Indicateur de succes (1 si succes, 0 sinon).
        """
        return await self.vector_store.delete_document(document_id)
