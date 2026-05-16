"""Tests unitaires pour les parametres Pydantic ajoutés."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.api import (
    CreateExcelParams,
    CreateWordParams,
    DeleteDocumentParams,
    EditExcelParams,
    GetDocumentParams,
    GetExcelFormulasParams,
    InspectGeneratedFileParams,
    ListAvailableDocumentsParams,
    ReadDocumentContentParams,
    UnifiedIndexDocumentParams,
)


class TestListAvailableDocumentsParams:
    """Tests pour la validation des champs source et type_filter."""

    def test_source_valid_values(self) -> None:
        for source in ("documents", "generated"):
            params = ListAvailableDocumentsParams(source=source)
            assert params.source == source

    def test_source_default_is_documents(self) -> None:
        params = ListAvailableDocumentsParams()
        assert params.source == "documents"

    def test_source_invalid_rejected(self) -> None:
        with pytest.raises(ValidationError, match="source invalide"):
            ListAvailableDocumentsParams(source="invalid")

    def test_type_filter_valid_values(self) -> None:
        for tf in ("all", "pdf", "excel", "word"):
            params = ListAvailableDocumentsParams(type_filter=tf)
            assert params.type_filter == tf

    def test_type_filter_default_is_all(self) -> None:
        params = ListAvailableDocumentsParams()
        assert params.type_filter == "all"

    def test_type_filter_invalid_rejected(self) -> None:
        with pytest.raises(ValidationError, match="type_filter invalide"):
            ListAvailableDocumentsParams(type_filter="csv")


class TestInspectGeneratedFileParams:
    """Tests pour InspectGeneratedFileParams."""

    def test_filename_required(self) -> None:
        with pytest.raises(ValidationError):
            InspectGeneratedFileParams()  # type: ignore[call-arg]

    def test_filename_traversal_rejected(self) -> None:
        with pytest.raises(ValidationError, match="ne doit pas contenir"):
            InspectGeneratedFileParams(filename="../secret.xlsx")

    def test_filename_slash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="ne doit pas contenir"):
            InspectGeneratedFileParams(filename="path/file.xlsx")

    def test_filename_backslash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="ne doit pas contenir"):
            InspectGeneratedFileParams(filename="path\\file.xlsx")

    def test_max_rows_default(self) -> None:
        params = InspectGeneratedFileParams(filename="test.xlsx")
        assert params.max_rows_per_sheet == 10

    def test_max_rows_bounds_min(self) -> None:
        with pytest.raises(ValidationError):
            InspectGeneratedFileParams(filename="test.xlsx", max_rows_per_sheet=0)

    def test_max_rows_bounds_max(self) -> None:
        with pytest.raises(ValidationError):
            InspectGeneratedFileParams(filename="test.xlsx", max_rows_per_sheet=101)


class TestParamsExtraForbid:
    """Garantit fail-fast cote LLM si un client envoie un champ ignore par erreur."""

    def test_get_document_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            GetDocumentParams(document_id="doc-1", extra_field="oops")  # type: ignore[call-arg]

    def test_delete_document_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            DeleteDocumentParams(document_id="doc-1", extra_field="oops")  # type: ignore[call-arg]

    def test_read_document_content_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            ReadDocumentContentParams(document_id="doc-1", extra_field="oops")  # type: ignore[call-arg]

    def test_unified_index_document_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            UnifiedIndexDocumentParams(file_path="/tmp/x.pdf", extra_field="oops")  # type: ignore[call-arg]

    def test_get_excel_formulas_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            GetExcelFormulasParams(document_id="doc-1", extra_field="oops")  # type: ignore[call-arg]

    def test_create_excel_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            CreateExcelParams(  # type: ignore[call-arg]
                filename="r.xlsx",
                sheets=[{"name": "S1"}],
                extra_field="oops",
            )

    def test_edit_excel_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            EditExcelParams(  # type: ignore[call-arg]
                filename="r.xlsx",
                operations=[{"op": "delete_rows", "sheet": "S1", "start_row": 1, "end_row": 1}],
                extra_field="oops",
            )

    def test_create_word_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            CreateWordParams(  # type: ignore[call-arg]
                filename="r.docx",
                content="# Test",
                extra_field="oops",
            )

    def test_list_available_documents_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            ListAvailableDocumentsParams(extra_field="oops")  # type: ignore[call-arg]

    def test_inspect_generated_file_params_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            InspectGeneratedFileParams(filename="r.xlsx", extra_field="oops")  # type: ignore[call-arg]
