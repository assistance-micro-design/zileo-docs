# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Services de stockage vectoriel.

Ce module expose les services de stockage vectoriel pour les embeddings
de documents.
"""

from __future__ import annotations

from src.services.vector.qdrant_store import QdrantVectorStore


__all__ = [
    "QdrantVectorStore",
]
