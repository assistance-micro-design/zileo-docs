# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour src/services/vector/payload_builder.py."""

from __future__ import annotations

from datetime import UTC, datetime

from src.models.chunk import ChunkMetadata, DocumentChunk
from src.models.document import DocumentMetadata
from src.models.unified import DocumentType, UnifiedMetadata
from src.services.vector.payload_builder import (
    build_payload,
    build_unified_payload,
    generate_point_id,
)


def _chunk(content: str = "hello", chunk_id: str = "chunk-1") -> DocumentChunk:
    return DocumentChunk(
        content=content,
        metadata=ChunkMetadata(
            chunk_id=chunk_id,
            document_id="doc-1",
            page_numbers=[1],
            start_page=1,
            end_page=1,
            section_title="Intro",
            content_type="text",
            has_table=False,
            has_image=False,
            has_equation=False,
            token_count=10,
            char_count=len(content),
            word_count=1,
        ),
    )


def _doc_meta() -> DocumentMetadata:
    return DocumentMetadata(
        document_id="doc-1",
        file_hash="abc123",
        filename="rapport.pdf",
        file_size_bytes=1024,
        title="Titre",
        author="Auteur",
        total_pages=42,
        ingested_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )


def _unified_meta(doc_type: DocumentType = DocumentType.EXCEL) -> UnifiedMetadata:
    return UnifiedMetadata(
        filename="data.xlsx",
        file_path="/tmp/data.xlsx",
        document_type=doc_type,
        original_format=".xlsx",
        file_hash="xyz789",
        page_count=3,
        has_formulas=True,
        sheet_names=["Sheet1", "Sheet2"],
        title="Donnees",
        author="Editeur",
        indexed_at=datetime(2026, 5, 13, 14, 0, tzinfo=UTC),
    )


def test_generate_point_id_is_deterministic() -> None:
    """generate_point_id() produit le meme id pour le meme chunk_id."""
    a = generate_point_id("chunk-xyz")
    b = generate_point_id("chunk-xyz")

    assert a == b
    assert isinstance(a, int)
    assert a > 0


def test_generate_point_id_differs_per_chunk() -> None:
    """generate_point_id() produit des ids differents pour des chunks differents."""
    assert generate_point_id("chunk-a") != generate_point_id("chunk-b")


def test_build_payload_pdf_contains_doc_fields() -> None:
    """build_payload() injecte les champs doc_* du DocumentMetadata."""
    payload = build_payload(_chunk(), _doc_meta())

    assert payload["doc_filename"] == "rapport.pdf"
    assert payload["doc_title"] == "Titre"
    assert payload["doc_author"] == "Auteur"
    assert payload["doc_total_pages"] == 42
    assert payload["doc_file_hash"] == "abc123"
    assert payload["ingested_at"] == "2026-05-13T12:00:00+00:00"
    assert payload["doc_creation_date"] is None


def test_build_payload_pdf_sets_document_type_to_pdf() -> None:
    """build_payload() marque document_type='pdf' pour la symetrie avec Excel/Word."""
    payload = build_payload(_chunk(), _doc_meta())

    assert payload["document_type"] == "pdf"


def test_build_payload_pdf_includes_chunk_fields() -> None:
    """build_payload() conserve les champs communs du chunk."""
    payload = build_payload(_chunk(content="hello world"), _doc_meta())

    assert payload["chunk_id"] == "chunk-1"
    assert payload["document_id"] == "doc-1"
    assert payload["content"] == "hello world"
    assert payload["content_preview"] == "hello world"
    assert payload["section_title"] == "Intro"
    assert payload["has_table"] is False
    assert payload["token_count"] == 10


def test_build_unified_payload_excel_includes_formula_and_sheets() -> None:
    """build_unified_payload() injecte has_formula et sheet_names."""
    payload = build_unified_payload(_chunk(), _unified_meta(DocumentType.EXCEL))

    assert payload["document_type"] == "excel"
    assert payload["has_formula"] is True
    assert payload["sheet_names"] == ["Sheet1", "Sheet2"]
    assert payload["doc_filename"] == "data.xlsx"
    assert payload["doc_total_pages"] == 3
    assert payload["ingested_at"] == "2026-05-13T14:00:00+00:00"


def test_build_unified_payload_word_marks_document_type() -> None:
    """build_unified_payload() expose document_type=word pour Word."""
    meta = _unified_meta(DocumentType.WORD)
    meta.has_formulas = False
    meta.sheet_names = []

    payload = build_unified_payload(_chunk(), meta)

    assert payload["document_type"] == "word"
    assert payload["has_formula"] is False
    assert payload["sheet_names"] == []


def test_build_payload_truncates_content_preview_to_500_chars() -> None:
    """content_preview est limite a 500 caracteres."""
    long_content = "a" * 1000

    payload = build_payload(_chunk(content=long_content), _doc_meta())

    assert isinstance(payload["content_preview"], str)
    assert len(payload["content_preview"]) == 500


def test_build_unified_payload_handles_optional_page_count() -> None:
    """page_count=None devient 0 dans doc_total_pages."""
    meta = _unified_meta()
    meta.page_count = None

    payload = build_unified_payload(_chunk(), meta)

    assert payload["doc_total_pages"] == 0
