"""Models Pydantic et dataclasses pour le projet MCP Zileo PDF."""

from __future__ import annotations

from src.models.api import (
    DeleteDocumentRequest,
    DeleteResult,
    DocumentInfo,
    DocumentSummary,
    ErrorResponse,
    ExtractionResult,
    ExtractPDFParams,
    ExtractPDFRequest,
    GetDocumentParams,
    HealthResponse,
    IndexDocumentParams,
    IndexDocumentRequest,
    IndexResult,
    ProcessingStatus,
    SearchDocumentsParams,
    TableFormat,
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
    "DeleteDocumentRequest",
    "DeleteResult",
    "DocumentAnalysisResult",
    "DocumentChunk",
    "DocumentInfo",
    "DocumentMetadata",
    "DocumentSummary",
    "EquationData",
    "ErrorResponse",
    "ExtractPDFParams",
    "ExtractPDFRequest",
    "ExtractedContent",
    "ExtractionResult",
    "GetDocumentParams",
    "HeaderInfo",
    "HealthResponse",
    "ImageData",
    "ImagePlaceholder",
    "IndexDocumentParams",
    "IndexDocumentRequest",
    "IndexResult",
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
    "TableFormat",
    "TablePlaceholder",
]
