# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Detection des marqueurs de contenu (tableaux, images, equations) dans un chunk.

Fonctions pures extraites de SmartChunker pour faciliter la testabilite.
"""

from __future__ import annotations

import re


_TABLE_INLINE_PATTERN = re.compile(r"\|.+\|.*\n\|[-:| ]+\|")


def has_table(content: str) -> bool:
    """Detecte la presence d'un tableau Markdown."""
    return bool(_TABLE_INLINE_PATTERN.search(content))


def has_image(content: str) -> bool:
    """Detecte la presence d'une image Markdown (motif ![...](...))."""
    return "![" in content


def has_equation(content: str) -> bool:
    """Detecte la presence d'une equation LaTeX (presence d'un $)."""
    return "$" in content
