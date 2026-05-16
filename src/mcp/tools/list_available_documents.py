# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tool MCP pour lister les fichiers disponibles (documents, generated)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar, NamedTuple

from src.core.config import settings
from src.mcp.tools.base import BaseMCPTool
from src.models.api import ListAvailableDocumentsParams


logger = logging.getLogger(__name__)


class _SourceConfig(NamedTuple):
    path_attr: str
    extensions: dict[str, str]
    excluded_dirs: set[str]


class ListAvailableDocumentsTool(BaseMCPTool):
    """Liste les fichiers disponibles dans le projet.

    Supporte 2 sources: documents (indexation), generated (fichiers crees).

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.
    """

    name: ClassVar[str] = "list_available_documents"
    description: ClassVar[str] = (
        "Liste les fichiers disponibles dans le projet. "
        "source='documents' (defaut): PDF/Excel/Word pour indexation via index_document. "
        "source='generated': fichiers Excel crees par create_excel_document. "
        "Filtrable par type et sous-dossier."
    )

    SUPPORTED_EXTENSIONS: ClassVar[dict[str, str]] = {
        ".pdf": "pdf",
        ".xlsx": "excel",
        ".xls": "excel",
        ".docx": "word",
    }
    GENERATED_EXTENSIONS: ClassVar[dict[str, str]] = {
        ".xlsx": "excel",
    }

    _SOURCE_CONFIGS: ClassVar[dict[str, _SourceConfig]] = {
        "documents": _SourceConfig("_documents_path", SUPPORTED_EXTENSIONS, set()),
        "generated": _SourceConfig("_output_path", GENERATED_EXTENSIONS, set()),
    }

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "enum": ["documents", "generated"],
                "description": (
                    "Quelle source lister. "
                    "'documents': fichiers PDF/Excel/Word a indexer (defaut). "
                    "'generated': fichiers Excel crees par create_excel_document."
                ),
                "default": "documents",
            },
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
        self._output_path = Path(settings.OUTPUT_PATH)

    async def _do_initialize(self) -> None:
        """Pas d'initialisation requise pour ce tool."""

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Liste les fichiers disponibles.

        Args:
            arguments: Parametres optionnels (source, type_filter, subdirectory, recursive).

        Returns:
            Dictionnaire avec source, base_path, total_files, by_type, files.
        """
        params = ListAvailableDocumentsParams(**arguments)
        config = self._SOURCE_CONFIGS[params.source]
        base_path: Path = getattr(self, config.path_attr)

        scan_path = base_path
        if params.subdirectory:
            scan_path = base_path / params.subdirectory

        error = self._validate_scan_path(scan_path, base_path)
        if error:
            return {
                "source": params.source,
                "base_path": str(scan_path),
                "total_files": 0,
                "by_type": {},
                "files": [],
                "error": error,
            }

        logger.info(
            "Scanning %s in: %s (recursive=%s, filter=%s)",
            params.source,
            scan_path,
            params.recursive,
            params.type_filter,
        )

        files = self._scan_files(
            scan_path, params, config.extensions, config.excluded_dirs, base_path
        )
        files.sort(key=lambda f: (f["type"], f["filename"].lower()))

        stats: dict[str, int] = {}
        for f in files:
            stats[f["type"]] = stats.get(f["type"], 0) + 1

        logger.info(
            "Found %d files (%s): %s",
            len(files),
            params.source,
            ", ".join(f"{k}={v}" for k, v in stats.items()),
        )

        return {
            "source": params.source,
            "base_path": str(scan_path),
            "total_files": len(files),
            "by_type": stats,
            "files": files,
        }

    def _validate_scan_path(self, scan_path: Path, base_path: Path) -> str | None:
        """Valide le chemin de scan (anti-traversal + existence)."""
        resolved = scan_path.resolve()
        if not resolved.is_relative_to(base_path.resolve()):
            return "Subdirectory must stay within documents directory"

        if not scan_path.exists():
            logger.warning("Path does not exist: %s", scan_path)
            return f"Dossier inexistant: {scan_path}"

        return None

    def _scan_files(
        self,
        scan_path: Path,
        params: ListAvailableDocumentsParams,
        extensions: dict[str, str],
        excluded_dirs: set[str],
        base_path: Path,
    ) -> list[dict[str, Any]]:
        """Scanne les fichiers dans le dossier."""
        files: list[dict[str, Any]] = []
        pattern = "**/*" if params.recursive else "*"

        for file_path in scan_path.glob(pattern):
            if not file_path.is_file():
                continue

            # Exclure les sous-dossiers configures
            if excluded_dirs and self._is_in_excluded_dir(file_path, scan_path, excluded_dirs):
                continue

            ext = file_path.suffix.lower()
            if ext not in extensions:
                continue

            doc_type = extensions[ext]
            if params.type_filter not in ("all", doc_type):
                continue

            entry = self._build_file_entry(file_path, base_path, doc_type, ext, params.source)
            files.append(entry)

        return files

    def _is_in_excluded_dir(
        self, file_path: Path, scan_path: Path, excluded_dirs: set[str]
    ) -> bool:
        """Verifie si le fichier est dans un dossier exclu."""
        try:
            relative = file_path.relative_to(scan_path)
        except ValueError:
            return False
        return any(part in excluded_dirs for part in relative.parts[:-1])

    def _build_file_entry(
        self,
        file_path: Path,
        base_path: Path,
        doc_type: str,
        ext: str,
        source: str,
    ) -> dict[str, Any]:
        """Construit un dictionnaire representant un fichier."""
        stat = file_path.stat()
        entry: dict[str, Any] = {
            "filename": file_path.name,
            "path": str(file_path),
            "relative_path": str(file_path.relative_to(base_path)),
            "type": doc_type,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "extension": ext,
            "modified_at": stat.st_mtime,
        }

        # Champs contextuels
        if source == "generated" and doc_type == "excel":
            entry["editable_with"] = "edit_excel_document"

        return entry
