"""Tool MCP pour l'indexation de documents PDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from src.core.exceptions import PDFNotFoundError
from src.models.api import ExtractPDFParams
from src.services.pipeline.orchestrator import PDFPipelineOrchestrator


logger = logging.getLogger(__name__)


class IndexDocumentTool:
    """Tool MCP pour extraire et indexer un PDF dans la base vectorielle.

    Ce tool execute le pipeline complet:
    1. Extraction du contenu (natif + OCR)
    2. Chunking semantique
    3. Generation d'embeddings Mistral
    4. Stockage dans Qdrant

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = IndexDocumentTool()
        >>> await tool.initialize()
        >>> result = await tool.execute({"file_path": "document.pdf"})
        >>> print(f"Indexed {result['chunks_stored']} chunks")
    """

    name: ClassVar[str] = "index_document"
    description: ClassVar[str] = (
        "Extrait et indexe un PDF pour la recherche semantique. "
        "Etape obligatoire avant search_documents. "
        "Retourne: document_id, metadonnees, nombre de passages indexes."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Chemin absolu vers le PDF. Ex: /data/docs/rapport.pdf",
            },
            "force_ocr": {
                "type": "boolean",
                "description": "Forcer OCR meme si le PDF contient du texte (defaut: false)",
                "default": False,
            },
            "table_format": {
                "type": "string",
                "description": "Format des tableaux extraits: 'markdown' ou 'html' (defaut: markdown)",
                "default": "markdown",
                "enum": ["markdown", "html"],
            },
        },
        "required": ["file_path"],
    }

    def __init__(self) -> None:
        """Initialise le tool d'indexation."""
        self._orchestrator = PDFPipelineOrchestrator()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialise les services (vector store).

        Doit etre appele avant execute() pour garantir
        que la collection Qdrant existe.
        """
        if not self._initialized:
            await self._orchestrator.initialize()
            self._initialized = True

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute l'indexation du PDF.

        Args:
            arguments: Parametres d'indexation:
                - file_path: Chemin vers le PDF
                - force_ocr: Forcer OCR (optionnel)
                - table_format: Format tableaux (optionnel)

        Returns:
            Dictionnaire avec:
                - document_id: ID unique du document
                - filename: Nom du fichier
                - total_pages: Nombre de pages
                - chunks_generated: Nombre de chunks crees
                - chunks_embedded: Nombre de chunks avec embeddings
                - chunks_stored: Nombre de chunks indexes
                - processing_time_seconds: Temps de traitement

        Raises:
            PDFNotFoundError: Si le fichier n'existe pas.
            PDFCorruptedError: Si le fichier n'est pas un PDF valide.
        """
        # S'assurer que les services sont initialises
        if not self._initialized:
            await self.initialize()

        # Valider les parametres
        params = ExtractPDFParams(**arguments)
        pdf_path = Path(params.file_path)

        if not pdf_path.exists():
            raise PDFNotFoundError(str(pdf_path))

        logger.info(
            "Indexation PDF: %s (force_ocr=%s, table_format=%s)",
            pdf_path,
            params.force_ocr,
            params.table_format,
        )

        # Executer le pipeline complet
        result = await self._orchestrator.process_and_index(
            pdf_path,
            options={
                "force_ocr": params.force_ocr,
                "table_format": params.table_format,
            },
        )

        # Construire la reponse
        return {
            "document_id": result.analysis.metadata.document_id,
            "filename": result.analysis.metadata.filename,
            "total_pages": result.analysis.metadata.total_pages,
            "pages_processed_native": result.pages_processed_native,
            "pages_processed_ocr": result.pages_processed_ocr,
            "chunks_generated": result.chunks_generated,
            "chunks_embedded": result.chunks_embedded,
            "chunks_stored": result.chunks_stored,
            "metadata": {
                "title": result.analysis.metadata.title,
                "author": result.analysis.metadata.author,
                "creation_date": (
                    result.analysis.metadata.creation_date.isoformat()
                    if result.analysis.metadata.creation_date
                    else None
                ),
            },
            "processing_time_seconds": result.processing_time_seconds,
            "errors": result.errors,
        }
