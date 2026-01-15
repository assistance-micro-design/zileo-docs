# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP unifié pour l'indexation de documents PDF, Excel et Word."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from src.core.exceptions import PDFNotFoundError
from src.mcp.tools.base import BaseMCPTool
from src.models.api import UnifiedIndexDocumentParams
from src.models.chunk import ChunkMetadata, DocumentChunk
from src.models.unified import DocumentType, FormulaData, UnifiedDocument
from src.services.document.router import DocumentRouter
from src.services.embedding.mistral_embedder import MistralEmbedder
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
        "Extrait et indexe un document (PDF/Excel/Word) pour la recherche semantique. "
        "Etape obligatoire avant search_documents. "
        "Retourne: document_id, type, metadonnees, nombre de passages indexes."
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

    def __init__(self) -> None:
        """Initialise le tool d'indexation."""
        super().__init__()
        self._pdf_orchestrator = PDFPipelineOrchestrator()
        self._router = DocumentRouter()
        self._embedder = MistralEmbedder()
        self._vector_store = QdrantVectorStore()

    async def _do_initialize(self) -> None:
        """Initialise les services (vector store, router)."""
        await self._pdf_orchestrator.initialize()
        await self._router.initialize()
        await self._vector_store.initialize()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute l'indexation du document.

        Args:
            arguments: Parametres d'indexation:
                - file_path: Chemin vers le document
                - force_ocr: Forcer OCR (PDF uniquement)
                - sheets: Feuilles a indexer (Excel uniquement)
                - table_format: Format tableaux

        Returns:
            Dictionnaire avec:
                - document_id: ID unique du document
                - document_type: Type (pdf/excel/word)
                - filename: Nom du fichier
                - chunks_stored: Nombre de chunks indexes
                - has_tables/has_formulas/has_images: Drapeaux
                - sheet_names: Noms des feuilles (Excel)
                - processing_time_seconds: Temps de traitement

        Raises:
            PDFNotFoundError: Si le fichier n'existe pas.
            ValueError: Si le format n'est pas supporté.
        """
        params = UnifiedIndexDocumentParams(**arguments)
        file_path = Path(params.file_path)

        if not file_path.exists():
            raise PDFNotFoundError(str(file_path))

        # Detecter le type de document
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
            "has_tables": any(
                c.metadata.has_table for c in result.chunks if c.metadata.has_table
            ),
            "has_formulas": False,
            "has_images": any(
                c.metadata.has_image for c in result.chunks if c.metadata.has_image
            ),
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

        # Generer les embeddings
        if chunks:
            chunks = await self._embedder.embed_chunks(chunks, use_enriched=True)

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

        # Chunk principal avec le contenu Markdown complet
        main_content = doc.content_markdown
        if main_content.strip():
            chunk_id = f"{doc.document_id}_main"
            chunk_content = main_content[:8000]  # Limite pour embedding
            chunks.append(
                DocumentChunk(
                    content=chunk_content,
                    metadata=ChunkMetadata(
                        chunk_id=chunk_id,
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
            )

        # Chunks additionnels pour le contenu restant
        if len(main_content) > 8000:
            remaining = main_content[8000:]
            chunk_size = 4000
            overlap = 200

            for i, start in enumerate(range(0, len(remaining), chunk_size - overlap)):
                chunk_content = remaining[start : start + chunk_size]
                if chunk_content.strip():
                    chunk_id = f"{doc.document_id}_part_{i + 1}"
                    chunks.append(
                        DocumentChunk(
                            content=chunk_content,
                            metadata=ChunkMetadata(
                                chunk_id=chunk_id,
                                document_id=doc.document_id,
                                chunk_index=len(chunks),
                                char_count=len(chunk_content),
                                document_type=doc.document_type.value,
                                has_table=doc.metadata.has_tables,
                                has_image=doc.metadata.has_images,
                                has_formula=doc.metadata.has_formulas,
                            ),
                            content_with_context=self._enrich_content(chunk_content, doc),
                        )
                    )

        # Chunks pour les formules Excel (si presentes)
        if doc.structured_data.formulas:
            formulas_content = self._format_formulas_for_chunk(doc.structured_data.formulas)
            if formulas_content:
                chunk_id = f"{doc.document_id}_formulas"
                chunks.append(
                    DocumentChunk(
                        content=formulas_content,
                        metadata=ChunkMetadata(
                            chunk_id=chunk_id,
                            document_id=doc.document_id,
                            chunk_index=len(chunks),
                            char_count=len(formulas_content),
                            section_title="Formules Excel",
                            document_type=doc.document_type.value,
                            has_formula=True,
                        ),
                        content_with_context=f"FORMULES EXCEL - {doc.filename}\n\n{formulas_content}",
                    )
                )

        # Mettre a jour total_chunks
        for chunk in chunks:
            chunk.metadata.total_chunks = len(chunks)

        return chunks

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
