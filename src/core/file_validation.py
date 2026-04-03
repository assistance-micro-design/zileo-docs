# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Validation de fichiers par magic numbers et extension."""

from __future__ import annotations

from pathlib import Path


_MAGIC_NUMBERS: dict[bytes, set[str]] = {
    b"%PDF": {".pdf"},
    b"PK\x03\x04": {".xlsx", ".docx"},
}


def validate_filename_safety(filename: str) -> bool:
    """Verifie qu'un nom de fichier ne contient pas de traversal.

    Args:
        filename: Nom du fichier a valider.

    Returns:
        True si le nom est safe.
    """
    return ".." not in filename and "/" not in filename and "\\" not in filename


def validate_file_magic(file_path: Path) -> bool:
    """Verifie que le magic number correspond a l'extension du fichier.

    Args:
        file_path: Chemin vers le fichier a valider.

    Returns:
        True si le magic number correspond a l'extension.
    """
    ext = file_path.suffix.lower()
    expected_magics = {magic for magic, exts in _MAGIC_NUMBERS.items() if ext in exts}

    if not expected_magics:
        return True

    with file_path.open("rb") as f:
        header = f.read(4)

    return any(header.startswith(magic) for magic in expected_magics)
