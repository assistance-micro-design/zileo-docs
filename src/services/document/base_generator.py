# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Classe de base pour les generateurs de documents (Excel, Word)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.core.config import settings
from src.core.exceptions import MCPZileoError
from src.core.file_validation import validate_filename_safety


class BaseDocumentGenerator:
    """Base commune pour ExcelGenerator et WordGenerator.

    Factorise la gestion du repertoire de sortie, la sanitization
    des noms de fichiers et la verification de taille.

    Attributes:
        _output_path: Repertoire de sortie des fichiers generes.
        _max_output_size_mb: Taille max du fichier en MB.
    """

    _error_class: type[MCPZileoError] = MCPZileoError

    def __init__(self, output_path: Path | None = None) -> None:
        self._output_path = Path(output_path or settings.OUTPUT_PATH)
        self._max_output_size_mb = settings.MAX_OUTPUT_FILE_SIZE_MB

    def ensure_output_dir(self) -> None:
        """Cree le repertoire OUTPUT_PATH s'il n'existe pas."""
        self._output_path.mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, filename: str) -> str:
        """Securise le nom de fichier (path traversal prevention).

        Args:
            filename: Nom de fichier a securiser.

        Returns:
            Nom de fichier securise.

        Raises:
            MCPZileoError: Si le nom est invalide ou dangereux.
        """
        if not validate_filename_safety(filename):
            raise self._error_class(
                message=f"Nom de fichier invalide: {filename}",
                code="INVALID_FILENAME",
                suggestion="Le nom de fichier ne doit pas contenir '..' , '/' ou '\\'.",
                parameter="filename",
                retry=True,
            )

        resolved = (self._output_path / filename).resolve()
        if not resolved.is_relative_to(self._output_path.resolve()):
            raise self._error_class(
                message=f"Path traversal detecte: {filename}",
                code="PATH_TRAVERSAL",
                suggestion="Utiliser un nom de fichier simple sans chemin.",
                parameter="filename",
                retry=True,
            )

        return filename

    def persist_and_verify(
        self,
        save_callable: Callable[[Path], None],
        file_path: Path,
        filename: str,
    ) -> int:
        """Sauvegarde via le callable injecte puis verifie la taille.

        Factorise le pattern "ecrire le fichier puis verifier" partage
        entre Excel et Word (signatures de save divergentes).

        Args:
            save_callable: Fonction qui ecrit le document a `file_path`.
            file_path: Destination du fichier.
            filename: Nom (utilise pour les messages d'erreur).

        Returns:
            Taille du fichier en octets.
        """
        save_callable(file_path)
        return self.verify_file_size(file_path, filename)

    def verify_file_size(self, file_path: Path, filename: str) -> int:
        """Verifie la taille d'un fichier genere et le supprime si trop gros.

        Args:
            file_path: Chemin du fichier a verifier.
            filename: Nom du fichier (pour les messages d'erreur).

        Returns:
            Taille du fichier en octets.
        """
        file_size = file_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        if size_mb > self._max_output_size_mb:
            file_path.unlink()
            raise self._error_class(
                message=f"Fichier trop volumineux: {size_mb:.1f}MB (max: {self._max_output_size_mb}MB)",
                code="OUTPUT_TOO_LARGE",
                details={
                    "filename": filename,
                    "size_mb": size_mb,
                    "max_size_mb": self._max_output_size_mb,
                },
                suggestion=f"Reduire le contenu. Max {self._max_output_size_mb}MB.",
                parameter="content",
                retry=True,
            )
        return file_size
