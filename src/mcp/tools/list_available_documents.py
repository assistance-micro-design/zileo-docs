# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour lister tous les documents disponibles (PDF, Excel, Word)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from src.core.config import settings
from src.mcp.tools.base import BaseMCPTool
from src.models.api import ListAvailableDocumentsParams


logger = logging.getLogger(__name__)


class ListAvailableDocumentsTool(BaseMCPTool):
    """Liste tous les documents disponibles dans le dossier monté.

    Remplace et étend list_available_pdfs pour supporter
    tous les formats de documents.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.
        SUPPORTED_EXTENSIONS: Mapping extension -> type document.

    Example:
        >>> tool = ListAvailableDocumentsTool()
        >>> result = await tool.execute({"type_filter": "excel"})
        >>> for doc in result["files"]:
        ...     print(f"{doc['filename']}: {doc['type']}")
    """

    name: ClassVar[str] = "list_available_documents"
    description: ClassVar[str] = (
        "Liste les fichiers disponibles pour indexation. "
        "Types supportés: PDF (.pdf), Excel (.xlsx, .xls), Word (.docx). "
        "Peut filtrer par type et sous-dossier."
    )

    SUPPORTED_EXTENSIONS: ClassVar[dict[str, str]] = {
        ".pdf": "pdf",
        ".xlsx": "excel",
        ".xls": "excel",
        ".docx": "word",
    }

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "type_filter": {
                "type": "string",
                "enum": ["pdf", "excel", "word", "all"],
                "description": "Filtrer par type de document (defaut: all)",
                "default": "all",
            },
            "subdirectory": {
                "type": "string",
                "description": "Sous-dossier relatif a explorer",
                "default": "",
            },
            "recursive": {
                "type": "boolean",
                "description": "Explorer recursivement les sous-dossiers (defaut: true)",
                "default": True,
            },
        },
        "required": [],
    }

    def __init__(self) -> None:
        """Initialise le tool."""
        super().__init__()
        self._documents_path = Path(settings.DOCUMENTS_PATH)

    async def _do_initialize(self) -> None:
        """Pas d'initialisation requise pour ce tool."""

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Liste les documents disponibles.

        Args:
            arguments: Parametres optionnels:
                - type_filter: Filtrer par type (pdf/excel/word/all)
                - subdirectory: Sous-dossier a scanner
                - recursive: Scanner recursivement

        Returns:
            Dictionnaire avec:
                - base_path: Chemin du dossier scanné
                - total_files: Nombre de fichiers trouvés
                - by_type: Statistiques par type
                - files: Liste des fichiers avec:
                    - filename: Nom du fichier
                    - path: Chemin absolu (pour index_document)
                    - relative_path: Chemin relatif
                    - type: Type de document
                    - size_mb: Taille en MB
                    - extension: Extension du fichier
        """
        params = ListAvailableDocumentsParams(**arguments)

        # Determiner le chemin a scanner
        scan_path = self._documents_path
        if params.subdirectory:
            scan_path = scan_path / params.subdirectory

        # Validation anti-traversal
        resolved = scan_path.resolve()
        if not resolved.is_relative_to(self._documents_path.resolve()):
            return {
                "base_path": str(scan_path),
                "total_files": 0,
                "by_type": {},
                "files": [],
                "error": "Subdirectory must stay within documents directory",
            }

        if not scan_path.exists():
            logger.warning("Documents path does not exist: %s", scan_path)
            return {
                "base_path": str(scan_path),
                "total_files": 0,
                "by_type": {},
                "files": [],
                "error": f"Dossier inexistant: {scan_path}",
            }

        logger.info(
            "Scanning for documents in: %s (recursive=%s, filter=%s)",
            scan_path,
            params.recursive,
            params.type_filter,
        )

        # Scanner les fichiers
        files: list[dict[str, Any]] = []
        pattern = "**/*" if params.recursive else "*"

        for file_path in scan_path.glob(pattern):
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            if ext not in self.SUPPORTED_EXTENSIONS:
                continue

            doc_type = self.SUPPORTED_EXTENSIONS[ext]

            # Appliquer filtre type
            if params.type_filter not in ("all", doc_type):
                continue

            stat = file_path.stat()
            files.append(
                {
                    "filename": file_path.name,
                    "path": str(file_path),
                    "relative_path": str(file_path.relative_to(self._documents_path)),
                    "type": doc_type,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "extension": ext,
                    "modified_at": stat.st_mtime,
                }
            )

        # Trier par type puis nom
        files.sort(key=lambda f: (f["type"], f["filename"].lower()))

        # Statistiques par type
        stats: dict[str, int] = {}
        for f in files:
            t = f["type"]
            stats[t] = stats.get(t, 0) + 1

        logger.info(
            "Found %d documents: %s",
            len(files),
            ", ".join(f"{k}={v}" for k, v in stats.items()),
        )

        return {
            "base_path": str(scan_path),
            "total_files": len(files),
            "by_type": stats,
            "files": files,
        }
