# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour src/core/exceptions.py (hierarchie ZileoDocsError)."""

from __future__ import annotations

import json

from src.core.exceptions import (
    EmptyQueryError,
    ExcelFormulaInjectionError,
    ZileoDocsError,
    OCRRateLimitError,
    PDFError,
    SourceFileNotFoundError,
    ValidationError,
    VectorStoreConnectionError,
)


def test_source_file_not_found_inherits_zileo_docs_error() -> None:
    """SourceFileNotFoundError herite de ZileoDocsError (via PDFError)."""
    err = SourceFileNotFoundError("/tmp/missing.pdf")

    assert isinstance(err, ZileoDocsError)
    assert isinstance(err, PDFError)


def test_default_code_class_var_applied() -> None:
    """default_code ClassVar est applique si code non passe."""

    class CustomError(ZileoDocsError):
        default_code = "CUSTOM_CODE"

    err = CustomError("msg sans code")

    assert err.code == "CUSTOM_CODE"


def test_default_code_overridden_by_explicit_code() -> None:
    """Un code explicite surcharge le default_code de la classe."""
    err = ZileoDocsError("msg", code="OVERRIDE")

    assert err.code == "OVERRIDE"


def test_pdf_error_default_code() -> None:
    """PDFError applique son default_code PDF_ERROR."""
    err = PDFError("oops")

    assert err.code == "PDF_ERROR"


def test_to_llm_format_includes_code_message_suggestion() -> None:
    """to_llm_format() produit la forme ERROR [CODE]: msg\\nSUGGESTION: ..."""
    err = ZileoDocsError(
        message="boom",
        code="CODE_X",
        suggestion="essaie ceci",
        parameter="param_x",
        retry=True,
    )

    formatted = err.to_llm_format()

    assert formatted.startswith("ERROR [CODE_X]: boom")
    assert "SUGGESTION: essaie ceci" in formatted
    assert "PARAMETER: param_x" in formatted
    assert "RETRY: Corriger et reessayer" in formatted


def test_to_llm_format_minimal_when_no_suggestion() -> None:
    """to_llm_format() omet les lignes optionnelles si non fournies."""
    err = ZileoDocsError("msg", code="MINIMAL")

    formatted = err.to_llm_format()

    assert formatted == "ERROR [MINIMAL]: msg"


def test_to_dict_is_json_serializable() -> None:
    """to_dict() produit un dict serialisable JSON."""
    err = SourceFileNotFoundError("/tmp/x.pdf")

    payload = err.to_dict()
    json_str = json.dumps(payload)

    parsed = json.loads(json_str)
    assert parsed["error"] == "SOURCE_FILE_NOT_FOUND"
    assert parsed["message"].startswith("Fichier introuvable")
    assert parsed["details"]["file_path"] == "/tmp/x.pdf"
    assert parsed["suggestion"]
    assert parsed["parameter"] == "file_path"
    assert parsed["retry"] is True


def test_to_dict_omits_optional_fields_when_none() -> None:
    """to_dict() n'inclut pas suggestion/parameter/retry si non fournis."""
    err = ZileoDocsError("simple", code="SIMPLE")

    payload = err.to_dict()

    assert "suggestion" not in payload
    assert "parameter" not in payload
    assert "retry" not in payload


def test_excel_formula_injection_propagates_fields() -> None:
    """ExcelFormulaInjectionError contient pattern et code dedie."""
    err = ExcelFormulaInjectionError(value="=cmd|'/c calc'!A1", pattern="cmd")

    assert err.code == "EXCEL_FORMULA_INJECTION"
    assert err.details["matched_pattern"] == "cmd"
    assert err.parameter == "cells"
    assert err.retry is True


def test_ocr_rate_limit_with_retry_after() -> None:
    """OCRRateLimitError integre le delai retry_after dans la suggestion."""
    err = OCRRateLimitError(retry_after=42)

    assert err.code == "OCR_RATE_LIMIT"
    assert err.details["retry_after_seconds"] == 42
    assert "42s" in (err.suggestion or "")
    assert err.retry is True


def test_ocr_rate_limit_without_retry_after() -> None:
    """OCRRateLimitError gere retry_after=None sans crash."""
    err = OCRRateLimitError()

    assert err.details["retry_after_seconds"] is None
    assert err.suggestion is not None


def test_vector_store_connection_error_details() -> None:
    """VectorStoreConnectionError expose host/port dans details."""
    err = VectorStoreConnectionError(host="qdrant", port=6333)

    assert err.code == "VECTOR_STORE_CONNECTION_ERROR"
    assert err.details == {"host": "qdrant", "port": 6333}
    assert err.retry is True


def test_validation_error_field_becomes_parameter() -> None:
    """ValidationError mappe field vers parameter et details.field."""
    err = ValidationError(message="invalide", field="query")

    assert err.parameter == "query"
    assert err.details["field"] == "query"
    assert err.retry is True


def test_empty_query_error_preset() -> None:
    """EmptyQueryError pre-configure le champ query avec suggestion."""
    err = EmptyQueryError()

    assert err.parameter == "query"
    assert err.details["field"] == "query"
    assert err.retry is True
    assert err.suggestion is not None
