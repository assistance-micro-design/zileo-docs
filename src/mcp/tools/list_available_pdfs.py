"""Tool MCP pour lister les fichiers PDF disponibles dans le dossier."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from src.core.config import settings


logger = logging.getLogger(__name__)


class ListAvailablePdfsTool:
    """Tool MCP pour lister les fichiers PDF disponibles.

    Ce tool permet au LLM de decouvrir les fichiers PDF
    qui peuvent etre indexes.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = ListAvailablePdfsTool()
        >>> result = await tool.execute({})
        >>> for pdf in result["files"]:
        ...     print(f"{pdf['filename']}: {pdf['path']}")
    """

    name: ClassVar[str] = "list_available_pdfs"
    description: ClassVar[str] = (
        "Liste les fichiers PDF disponibles dans le dossier monte. "
        "Utiliser pour savoir quels PDFs peuvent etre indexes. "
        "Retourne: liste des fichiers avec chemin, taille, date."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "subdirectory": {
                "type": "string",
                "description": "Sous-dossier optionnel a scanner (relatif au dossier racine)",
                "default": "",
            },
            "recursive": {
                "type": "boolean",
                "description": "Scanner recursivement les sous-dossiers (defaut: true)",
                "default": True,
            },
        },
        "required": [],
    }

    def __init__(self) -> None:
        """Initialise le tool."""
        self._documents_path = Path(settings.DOCUMENTS_PATH)

    async def initialize(self) -> None:
        """Pas d'initialisation requise pour ce tool."""

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Liste les fichiers PDF disponibles.

        Args:
            arguments: Parametres optionnels:
                - subdirectory: Sous-dossier a scanner
                - recursive: Scanner recursivement

        Returns:
            Dictionnaire avec:
                - base_path: Chemin du dossier scanne
                - total_files: Nombre de fichiers PDF
                - files: Liste des fichiers avec:
                    - filename: Nom du fichier
                    - path: Chemin absolu (pour index_document)
                    - size_mb: Taille en MB
                    - modified_at: Date de modification
        """
        subdirectory = arguments.get("subdirectory", "")
        recursive = arguments.get("recursive", True)

        # Determiner le chemin a scanner
        scan_path = self._documents_path
        if subdirectory:
            scan_path = scan_path / subdirectory

        if not scan_path.exists():
            logger.warning("Documents path does not exist: %s", scan_path)
            return {
                "base_path": str(scan_path),
                "total_files": 0,
                "files": [],
                "error": f"Dossier inexistant: {scan_path}",
            }

        logger.info("Scanning for PDFs in: %s (recursive=%s)", scan_path, recursive)

        # Scanner les fichiers PDF
        pdf_files: list[dict[str, Any]] = []
        pattern = "**/*.pdf" if recursive else "*.pdf"

        for pdf_path in scan_path.glob(pattern):
            if pdf_path.is_file():
                stat = pdf_path.stat()
                pdf_files.append({
                    "filename": pdf_path.name,
                    "path": str(pdf_path),
                    "relative_path": str(pdf_path.relative_to(self._documents_path)),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified_at": stat.st_mtime,
                })

        # Trier par nom
        pdf_files.sort(key=lambda x: x["filename"].lower())

        logger.info("Found %d PDF files", len(pdf_files))

        return {
            "base_path": str(scan_path),
            "total_files": len(pdf_files),
            "files": pdf_files,
        }
