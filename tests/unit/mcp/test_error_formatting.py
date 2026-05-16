# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour le formatage des erreurs MCP (LLM-friendly)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.exceptions import ExcelFileNotFoundError
from src.mcp.server import _format_tool_error
from src.models.api import CreateExcelParams, EditExcelParams


class TestFormatToolError:
    """Tests de _format_tool_error."""

    def test_zileo_docs_error_uses_llm_format(self) -> None:
        """ZileoDocsError -> to_llm_format()."""
        error = ExcelFileNotFoundError("test.xlsx")
        result = _format_tool_error(error)
        assert "EXCEL_FILE_NOT_FOUND" in result
        assert "SUGGESTION" in result

    def test_unknown_exception_returns_internal_error(self) -> None:
        """Exception inconnue -> message generique."""
        error = RuntimeError("boom")
        result = _format_tool_error(error)
        assert "INTERNAL_ERROR" in result

    def test_pydantic_validation_error_returns_structured_message(self) -> None:
        """ValidationError Pydantic -> message structure avec count."""
        with pytest.raises(ValidationError) as exc_info:
            EditExcelParams(filename="test.xlsx", operations=[{"bad": "data"}])
        result = _format_tool_error(exc_info.value)
        assert "VALIDATION_ERROR" in result
        assert "RETRY" in result


class TestValidationErrorHints:
    """Tests des hints contextuels pour erreurs de validation."""

    def test_union_tag_not_found_shows_ops_hint(self) -> None:
        """union_tag_not_found -> hint avec liste des ops et exemples."""
        with pytest.raises(ValidationError) as exc_info:
            EditExcelParams(
                filename="test.xlsx",
                operations=[{"chart_type": "bar", "title": "Test"}],
            )
        result = _format_tool_error(exc_info.value)
        assert "op" in result
        assert "add_chart" in result
        assert "update_cells" in result
        assert "HINT" in result

    def test_chart_type_missing_shows_chart_hint(self) -> None:
        """Chart sans type -> hint specifique charts."""
        with pytest.raises(ValidationError) as exc_info:
            CreateExcelParams(
                filename="test.xlsx",
                sheets=[
                    {
                        "name": "S1",
                        "charts": [{"chart_name": "Histogram", "data_range": "A1:B5"}],
                    }
                ],
            )
        result = _format_tool_error(exc_info.value)
        assert "VALIDATION_ERROR" in result
        assert "type" in result.lower()

    def test_error_lists_all_fields_in_error(self) -> None:
        """Chaque champ en erreur est liste."""
        with pytest.raises(ValidationError) as exc_info:
            EditExcelParams(
                filename="test.xlsx",
                operations=[
                    {"stuff": "a"},
                    {"other": "b"},
                ],
            )
        result = _format_tool_error(exc_info.value)
        # Les 2 erreurs sont listees avec le chemin
        assert "operations -> 0" in result
        assert "operations -> 1" in result
        assert "discriminator" in result
