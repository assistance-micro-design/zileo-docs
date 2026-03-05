"""Tests unitaires pour les parametres Pydantic ajoutés."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.api import InspectGeneratedFileParams, ListAvailableDocumentsParams


class TestListAvailableDocumentsParams:
    """Tests pour la validation des champs source et type_filter."""

    def test_source_valid_values(self) -> None:
        for source in ("documents", "generated", "templates", "images"):
            params = ListAvailableDocumentsParams(source=source)
            assert params.source == source

    def test_source_default_is_documents(self) -> None:
        params = ListAvailableDocumentsParams()
        assert params.source == "documents"

    def test_source_invalid_rejected(self) -> None:
        with pytest.raises(ValidationError, match="source invalide"):
            ListAvailableDocumentsParams(source="invalid")

    def test_type_filter_valid_values(self) -> None:
        for tf in ("all", "pdf", "excel", "word", "presentation", "template", "image"):
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
