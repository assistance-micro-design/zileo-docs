# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour src/services/vector/payload_reader.py (extract_doc_summary)."""

from __future__ import annotations

from src.services.vector.payload_reader import extract_doc_summary


class TestExtractDocSummary:
    """Tests pour extract_doc_summary (lecture du payload Qdrant)."""

    def test_returns_all_doc_fields_when_present(self) -> None:
        chunk = {
            "doc_filename": "rapport.pdf",
            "doc_title": "Rapport mensuel",
            "doc_author": "Zileo",
            "doc_total_pages": 12,
            "ingested_at": "2026-05-15T10:00:00Z",
            "doc_file_hash": "abc123",
            "other_field": "ignored",
        }
        summary = extract_doc_summary(chunk)
        assert summary == {
            "filename": "rapport.pdf",
            "title": "Rapport mensuel",
            "author": "Zileo",
            "total_pages": 12,
            "ingested_at": "2026-05-15T10:00:00Z",
            "file_hash": "abc123",
        }

    def test_returns_none_for_missing_fields(self) -> None:
        """Si une cle manque, sa valeur est None (pas KeyError)."""
        summary = extract_doc_summary({"doc_filename": "only_name.pdf"})
        assert summary["filename"] == "only_name.pdf"
        assert summary["title"] is None
        assert summary["author"] is None
        assert summary["total_pages"] is None
        assert summary["ingested_at"] is None
        assert summary["file_hash"] is None

    def test_handles_empty_chunk(self) -> None:
        summary = extract_doc_summary({})
        assert all(value is None for value in summary.values())
