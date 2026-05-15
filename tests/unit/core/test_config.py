# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour src/core/config.py (Settings pydantic)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.config import Settings


def test_defaults_loaded() -> None:
    """Settings() charge les valeurs par defaut documentees."""
    settings = Settings()

    assert settings.APP_NAME == "MCP Zileo RAG"
    assert settings.APP_VERSION == "0.3.0"
    assert settings.QDRANT_PORT == 6333
    assert settings.QDRANT_COLLECTION == "documents"
    assert settings.CHUNK_SIZE == 512
    assert settings.OCR_DPI == 300
    assert settings.OCR_TABLE_FORMAT == "markdown"
    assert settings.MISTRAL_TIMEOUT_S == 30
    assert settings.MAX_FILE_SIZE_MB == 50
    assert settings.MAX_DECOMPRESSED_MB == 200
    assert settings.LOG_LEVEL == "INFO"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une variable d'environnement surcharge la valeur par defaut."""
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "100")

    settings = Settings()

    assert settings.MAX_FILE_SIZE_MB == 100


def test_ocr_dpi_below_minimum_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """OCR_DPI < 72 leve ValidationError."""
    monkeypatch.setenv("OCR_DPI", "10")

    with pytest.raises(ValidationError):
        Settings()


def test_log_level_invalid_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_LEVEL hors pattern leve ValidationError."""
    monkeypatch.setenv("LOG_LEVEL", "foo")

    with pytest.raises(ValidationError):
        Settings()


def test_ocr_table_format_invalid_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """OCR_TABLE_FORMAT autre que markdown/html leve ValidationError."""
    monkeypatch.setenv("OCR_TABLE_FORMAT", "xml")

    with pytest.raises(ValidationError):
        Settings()


def test_mistral_timeout_valid_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """MISTRAL_TIMEOUT_S accepte une valeur dans la plage [1, 600]."""
    monkeypatch.setenv("MISTRAL_TIMEOUT_S", "600")

    settings = Settings()

    assert settings.MISTRAL_TIMEOUT_S == 600


def test_mistral_timeout_zero_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """MISTRAL_TIMEOUT_S=0 leve ValidationError (ge=1)."""
    monkeypatch.setenv("MISTRAL_TIMEOUT_S", "0")

    with pytest.raises(ValidationError):
        Settings()


def test_max_decompressed_above_max_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """MAX_DECOMPRESSED_MB > 2000 leve ValidationError."""
    monkeypatch.setenv("MAX_DECOMPRESSED_MB", "10000")

    with pytest.raises(ValidationError):
        Settings()
