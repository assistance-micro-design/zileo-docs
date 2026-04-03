# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Models Pydantic et dataclasses pour le projet MCP Zileo RAG."""

from __future__ import annotations

from src.models.api import (
    DeleteResult,
    GetDocumentParams,
    HealthResponse,
    ProcessingStatus,
    SearchDocumentsParams,
)
from src.models.chunk import ChunkMetadata, DocumentChunk
from src.models.document import (
    DocumentAnalysisResult,
    DocumentMetadata,
    PageAnalysis,
    PageType,
)
from src.models.extraction import (
    ChartData,
    EquationData,
    ExtractedContent,
    HeaderInfo,
    ImageData,
    ImagePlaceholder,
    ListInfo,
    OCRResult,
    TableData,
    TablePlaceholder,
)
from src.models.search import (
    SearchFilters,
    SearchQuery,
    SearchResponse,
    SearchResultItem,
)


__all__ = [
    "ChartData",
    "ChunkMetadata",
    "DeleteResult",
    "DocumentAnalysisResult",
    "DocumentChunk",
    "DocumentMetadata",
    "EquationData",
    "ExtractedContent",
    "GetDocumentParams",
    "HeaderInfo",
    "HealthResponse",
    "ImageData",
    "ImagePlaceholder",
    "ListInfo",
    "OCRResult",
    "PageAnalysis",
    "PageType",
    "ProcessingStatus",
    "SearchDocumentsParams",
    "SearchFilters",
    "SearchQuery",
    "SearchResponse",
    "SearchResultItem",
    "TableData",
    "TablePlaceholder",
]
