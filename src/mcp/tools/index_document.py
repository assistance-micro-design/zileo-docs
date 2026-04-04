# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP unifié pour l'indexation de documents PDF, Excel et Word."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from src.core.config import settings
from src.core.exceptions import SourceFileNotFoundError
from src.core.file_validation import compute_file_hash, validate_file_magic
from src.mcp.tools.base import BaseMCPTool
from src.models.api import UnifiedIndexDocumentParams
from src.models.chunk import ChunkMetadata, DocumentChunk
from src.models.unified import DocumentType, FormulaData, UnifiedDocument
from src.services.document.router import DocumentRouter
from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.embedding.sparse_embedder import SparseEmbedder, embed_dense_and_sparse
from src.services.pipeline.orchestrator import PDFPipelineOrchestrator
from src.services.vector.qdrant_store import QdrantVectorStore


logger = logging.getLogger(__name__)


class IndexDocumentTool(BaseMCPTool):
    """Tool MCP unifié pour extraire et indexer un document dans la base vectorielle.

    Supporte les formats:
    - PDF: Pipeline complet (analyse, extraction native, OCR, chunking, embedding)
    - Excel: Extraction formules et tableaux, conversion en chunks
    - Word: Extraction texte, tableaux et images, conversion en chunks

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = IndexDocumentTool()
        >>> await tool.initialize()
        >>> result = await tool.execute({"file_path": "document.xlsx"})
        >>> print(f"Indexed {result['chunks_stored']} chunks")
    """

    name: ClassVar[str] = "index_document"
    description: ClassVar[str] = (
        "Indexe un document (PDF/Excel/Word) pour la recherche semantique. "
        "Si deja indexe, retourne l'ID existant. Si modifie, le signale. "
        "Retourne: document_id, type, chunks indexes."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Chemin absolu vers le document. Ex: /data/docs/rapport.xlsx",
            },
            "force_ocr": {
                "type": "boolean",
                "description": "PDF uniquement: forcer OCR meme si texte natif (defaut: false)",
                "default": False,
            },
            "sheets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Excel uniquement: noms des feuilles a indexer (toutes si vide)",
            },
            "table_format": {
                "type": "string",
                "description": "Format des tableaux: 'markdown' ou 'html' (defaut: markdown)",
                "default": "markdown",
                "enum": ["markdown", "html"],
            },
        },
        "required": ["file_path"],
    }

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        embedder: MistralEmbedder | None = None,
        sparse_embedder: SparseEmbedder | None = None,
    ) -> None:
        """Initialise le tool d'indexation.

        Args:
            vector_store: Instance partagee du vector store (injection).
            embedder: Instance partagee de l'embedder (injection).
            sparse_embedder: Instance partagee du sparse embedder (injection).
        """
        super().__init__()
        self._pdf_orchestrator = PDFPipelineOrchestrator()
        self._router = DocumentRouter()
        self._embedder = embedder or MistralEmbedder()
        self._sparse_embedder = sparse_embedder or SparseEmbedder()
        self._vector_store = vector_store or QdrantVectorStore()

    async def _do_initialize(self) -> None:
        """Initialise les services (vector store, router)."""
        await self._pdf_orchestrator.initialize()
        await self._router.initialize()
        await self._vector_store.initialize()

    def _validate_file(self, file_path: Path) -> dict[str, Any] | None:
        """Valide le chemin, l'existence et le magic number du fichier.

        Returns:
            Dictionnaire d'erreur si invalide, None si valide.

        Raises:
            SourceFileNotFoundError: Si le fichier n'existe pas.
        """
        documents_path = Path(settings.DOCUMENTS_PATH).resolve()
        resolved = file_path.resolve()
        if not resolved.is_relative_to(documents_path):
            return {
                "error": "File path must be within documents directory",
                "file_path": str(file_path),
            }

        if not file_path.exists():
            raise SourceFileNotFoundError(str(file_path))

        if not validate_file_magic(file_path):
            return {
                "error": f"Invalid file: magic number mismatch for {file_path.suffix}",
                "file_path": str(file_path),
            }

        return None

    async def _check_duplicate(self, file_path: Path) -> dict[str, Any] | None:
        """Verifie si le fichier est deja indexe, avec comparaison de hash.

        Returns:
            Dictionnaire de reponse si doublon detecte, None sinon.
        """
        current_hash = compute_file_hash(file_path)
        existing = await self._vector_store.find_document_by_filename(file_path.name)
        if not existing:
            return None

        stored_hash = existing.get("file_hash", "")
        if stored_hash and stored_hash != current_hash:
            return self._build_file_modified_response(existing, file_path.name)
        return self._build_already_indexed_response(existing, file_path.name)

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute l'indexation du document.

        Args:
            arguments: Parametres d'indexation (file_path, force_ocr, sheets, table_format).

        Returns:
            Resultat d'indexation ou reponse doublon/erreur.

        Raises:
            SourceFileNotFoundError: Si le fichier n'existe pas.
            ValueError: Si le format n'est pas supporté.
        """
        params = UnifiedIndexDocumentParams(**arguments)
        file_path = Path(params.file_path)

        validation_error = self._validate_file(file_path)
        if validation_error:
            return validation_error

        duplicate_response = await self._check_duplicate(file_path)
        if duplicate_response:
            return duplicate_response

        doc_type = self._router.detect_type(file_path)

        logger.info(
            "Indexation document: %s (type=%s, force_ocr=%s)",
            file_path,
            doc_type.value,
            params.force_ocr,
        )

        start_time = datetime.now(UTC)

        # Cas PDF: pipeline dedie
        if doc_type == DocumentType.PDF:
            result = await self._index_pdf(file_path, params)
            result["processing_time_seconds"] = (datetime.now(UTC) - start_time).total_seconds()
            return result

        # Autres formats: pipeline unifie
        result = await self._index_unified(file_path, doc_type, params)
        result["processing_time_seconds"] = (datetime.now(UTC) - start_time).total_seconds()
        return result

    def _build_already_indexed_response(
        self, existing: dict[str, Any], filename: str
    ) -> dict[str, Any]:
        """Construit la reponse pour un document deja indexe."""
        logger.info(
            "Document deja indexe: %s (document_id=%s, chunks=%d)",
            filename,
            existing["document_id"],
            existing["total_chunks"],
        )
        return {
            "already_indexed": True,
            "document_id": existing["document_id"],
            "filename": filename,
            "total_chunks": existing["total_chunks"],
            "ingested_at": existing["ingested_at"],
            "message": (
                "Ce document est deja indexe. "
                "Utilisez le document_id pour search_documents. "
                "Pour re-indexer, supprimez d'abord avec delete_document."
            ),
        }

    def _build_file_modified_response(
        self, existing: dict[str, Any], filename: str
    ) -> dict[str, Any]:
        """Construit la reponse quand le fichier a ete modifie depuis la derniere indexation."""
        logger.info(
            "Fichier modifie detecte: %s (document_id=%s)",
            filename,
            existing["document_id"],
        )
        return {
            "file_modified": True,
            "document_id": existing["document_id"],
            "filename": filename,
            "total_chunks": existing["total_chunks"],
            "ingested_at": existing["ingested_at"],
            "message": (
                "Ce fichier a ete modifie depuis sa derniere indexation. "
                "Pour re-indexer, supprimez d'abord avec delete_document "
                f"(document_id: {existing['document_id']}), puis relancez index_document."
            ),
        }

    async def _index_pdf(
        self,
        file_path: Path,
        params: UnifiedIndexDocumentParams,
    ) -> dict[str, Any]:
        """Indexe un document PDF via le pipeline existant.

        Args:
            file_path: Chemin vers le PDF.
            params: Parametres d'indexation.

        Returns:
            Resultat d'indexation.
        """
        result = await self._pdf_orchestrator.process_and_index(
            file_path,
            options={
                "force_ocr": params.force_ocr,
                "table_format": params.table_format,
            },
        )

        return {
            "document_id": result.analysis.metadata.document_id,
            "document_type": "pdf",
            "filename": result.analysis.metadata.filename,
            "total_pages": result.analysis.metadata.total_pages,
            "pages_processed_native": result.pages_processed_native,
            "pages_processed_ocr": result.pages_processed_ocr,
            "chunks_stored": result.chunks_stored,
            "has_tables": any(c.metadata.has_table for c in result.chunks if c.metadata.has_table),
            "has_formulas": False,
            "has_images": any(c.metadata.has_image for c in result.chunks if c.metadata.has_image),
            "metadata": {
                "title": result.analysis.metadata.title,
                "author": result.analysis.metadata.author,
                "creation_date": (
                    result.analysis.metadata.creation_date.isoformat()
                    if result.analysis.metadata.creation_date
                    else None
                ),
            },
            "errors": result.errors,
        }

    async def _index_unified(
        self,
        file_path: Path,
        doc_type: DocumentType,
        params: UnifiedIndexDocumentParams,
    ) -> dict[str, Any]:
        """Indexe un document Excel ou Word via le router unifie.

        Args:
            file_path: Chemin vers le document.
            doc_type: Type de document detecte.
            params: Parametres d'indexation.

        Returns:
            Resultat d'indexation.
        """
        # Extraire via le router
        unified_doc = await self._router.extract(file_path)

        # Creer les chunks a partir du contenu unifie
        chunks = await self._create_chunks_from_unified(unified_doc, params)

        # Generer les embeddings (dense + sparse en parallele)
        if chunks:
            chunks = await embed_dense_and_sparse(chunks, self._embedder, self._sparse_embedder)

        # Stocker dans Qdrant
        chunks_stored = 0
        if chunks:
            store_result = await self._vector_store.store_unified_chunks(
                chunks=chunks,
                unified_metadata=unified_doc.metadata,
            )
            chunks_stored = store_result.get("stored_chunks", 0)

        logger.info(
            "Document %s indexe: %d chunks",
            unified_doc.document_id,
            chunks_stored,
        )

        return {
            "document_id": unified_doc.document_id,
            "document_type": doc_type.value,
            "filename": unified_doc.filename,
            "chunks_stored": chunks_stored,
            "has_tables": unified_doc.metadata.has_tables,
            "has_formulas": unified_doc.metadata.has_formulas,
            "has_images": unified_doc.metadata.has_images,
            "sheet_names": unified_doc.metadata.sheet_names or None,
            "metadata": {
                "title": unified_doc.metadata.title,
                "author": unified_doc.metadata.author,
                "page_count": unified_doc.metadata.page_count,
                "word_count": unified_doc.metadata.word_count,
            },
        }

    async def _create_chunks_from_unified(
        self,
        doc: UnifiedDocument,
        _params: UnifiedIndexDocumentParams,
    ) -> list[DocumentChunk]:
        """Cree des chunks a partir d'un document unifie.

        Strategie de chunking pour Excel/Word:
        1. Chunk principal avec le contenu Markdown
        2. Chunks additionnels pour les tableaux volumineux
        3. Chunks pour les formules (Excel)

        Args:
            doc: Document unifie extrait.
            params: Parametres d'indexation.

        Returns:
            Liste de DocumentChunk prets pour embedding.
        """
        chunks: list[DocumentChunk] = []

        main_chunk = self._create_main_chunk(doc)
        if main_chunk:
            chunks.append(main_chunk)

        chunks.extend(self._create_overflow_chunks(doc, len(chunks)))

        formula_chunk = self._create_formula_chunk(doc, len(chunks))
        if formula_chunk:
            chunks.append(formula_chunk)

        for chunk in chunks:
            chunk.metadata.total_chunks = len(chunks)
        return chunks

    def _create_main_chunk(self, doc: UnifiedDocument) -> DocumentChunk | None:
        """Cree le chunk principal (max 8000 chars)."""
        main_content = doc.content_markdown
        if not main_content.strip():
            return None
        chunk_content = main_content[:8000]
        return DocumentChunk(
            content=chunk_content,
            metadata=ChunkMetadata(
                chunk_id=f"{doc.document_id}_main",
                document_id=doc.document_id,
                chunk_index=0,
                char_count=len(chunk_content),
                section_title=doc.metadata.title or doc.filename,
                document_type=doc.document_type.value,
                has_table=doc.metadata.has_tables,
                has_image=doc.metadata.has_images,
                has_formula=doc.metadata.has_formulas,
            ),
            content_with_context=self._enrich_content(chunk_content, doc),
        )

    def _create_overflow_chunks(
        self, doc: UnifiedDocument, start_index: int
    ) -> list[DocumentChunk]:
        """Cree les chunks supplementaires pour le contenu au-dela de 8000 chars."""
        main_content = doc.content_markdown
        if len(main_content) <= 8000:
            return []
        remaining = main_content[8000:]
        chunk_size = 4000
        overlap = 200
        chunks: list[DocumentChunk] = []
        for i, start in enumerate(range(0, len(remaining), chunk_size - overlap)):
            chunk_content = remaining[start : start + chunk_size]
            if not chunk_content.strip():
                continue
            chunks.append(
                DocumentChunk(
                    content=chunk_content,
                    metadata=ChunkMetadata(
                        chunk_id=f"{doc.document_id}_part_{i + 1}",
                        document_id=doc.document_id,
                        chunk_index=start_index + len(chunks),
                        char_count=len(chunk_content),
                        document_type=doc.document_type.value,
                        has_table=doc.metadata.has_tables,
                        has_image=doc.metadata.has_images,
                        has_formula=doc.metadata.has_formulas,
                    ),
                    content_with_context=self._enrich_content(chunk_content, doc),
                )
            )
        return chunks

    def _create_formula_chunk(self, doc: UnifiedDocument, chunk_index: int) -> DocumentChunk | None:
        """Cree le chunk des formules Excel."""
        if not doc.structured_data.formulas:
            return None
        formulas_content = self._format_formulas_for_chunk(doc.structured_data.formulas)
        if not formulas_content:
            return None
        return DocumentChunk(
            content=formulas_content,
            metadata=ChunkMetadata(
                chunk_id=f"{doc.document_id}_formulas",
                document_id=doc.document_id,
                chunk_index=chunk_index,
                char_count=len(formulas_content),
                section_title="Formules Excel",
                document_type=doc.document_type.value,
                has_formula=True,
            ),
            content_with_context=f"FORMULES EXCEL - {doc.filename}\n\n{formulas_content}",
        )

    def _enrich_content(self, content: str, doc: UnifiedDocument) -> str:
        """Enrichit le contenu pour meilleur embedding.

        Args:
            content: Contenu brut.
            doc: Document source.

        Returns:
            Contenu enrichi avec contexte.
        """
        header = f"DOCUMENT: {doc.filename} (Type: {doc.document_type.value})"
        if doc.metadata.title:
            header += f"\nTITRE: {doc.metadata.title}"
        if doc.metadata.sheet_names:
            header += f"\nFEUILLES: {', '.join(doc.metadata.sheet_names)}"

        return f"{header}\n\n{content}"

    def _format_formulas_for_chunk(self, formulas: list[FormulaData]) -> str:
        """Formate les formules pour le chunk.

        Args:
            formulas: Liste des formules extraites.

        Returns:
            Contenu Markdown des formules.
        """
        if not formulas:
            return ""

        lines = ["# Formules Excel", ""]
        for f in formulas[:50]:  # Limite 50 formules par chunk
            result_str = f" = {f.result}" if f.result is not None else ""
            lines.append(f"- **{f.sheet}!{f.cell}**: `{f.formula}`{result_str}")

        if len(formulas) > 50:
            lines.append(f"\n*... et {len(formulas) - 50} autres formules*")

        return "\n".join(lines)
