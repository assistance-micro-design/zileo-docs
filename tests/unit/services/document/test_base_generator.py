# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests unitaires pour BaseDocumentGenerator (sanitize + verify_file_size)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import MCPZileoError
from src.services.document.base_generator import BaseDocumentGenerator


class TestSanitizeFilename:
    """Tests pour sanitize_filename: rejet path traversal."""

    def test_accepts_simple_name(self, tmp_path: Path) -> None:
        gen = BaseDocumentGenerator(output_path=tmp_path)
        assert gen.sanitize_filename("report.xlsx") == "report.xlsx"

    def test_rejects_double_dot(self, tmp_path: Path) -> None:
        gen = BaseDocumentGenerator(output_path=tmp_path)
        with pytest.raises(MCPZileoError, match="invalide"):
            gen.sanitize_filename("../etc/passwd")

    def test_rejects_forward_slash(self, tmp_path: Path) -> None:
        gen = BaseDocumentGenerator(output_path=tmp_path)
        with pytest.raises(MCPZileoError, match="invalide"):
            gen.sanitize_filename("subdir/file.xlsx")

    def test_rejects_backslash(self, tmp_path: Path) -> None:
        gen = BaseDocumentGenerator(output_path=tmp_path)
        with pytest.raises(MCPZileoError, match="invalide"):
            gen.sanitize_filename("subdir\\file.xlsx")

    def test_error_has_invalid_filename_code(self, tmp_path: Path) -> None:
        gen = BaseDocumentGenerator(output_path=tmp_path)
        with pytest.raises(MCPZileoError) as exc_info:
            gen.sanitize_filename("../foo")
        assert exc_info.value.code == "INVALID_FILENAME"


class TestEnsureOutputDir:
    """Tests pour ensure_output_dir: creation idempotente."""

    def test_creates_missing_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "new_output"
        assert not target.exists()
        gen = BaseDocumentGenerator(output_path=target)
        gen.ensure_output_dir()
        assert target.is_dir()

    def test_idempotent_when_exists(self, tmp_path: Path) -> None:
        gen = BaseDocumentGenerator(output_path=tmp_path)
        gen.ensure_output_dir()
        gen.ensure_output_dir()
        assert tmp_path.is_dir()


class TestVerifyFileSize:
    """Tests pour verify_file_size: cap output."""

    def test_accepts_small_file(self, tmp_path: Path) -> None:
        gen = BaseDocumentGenerator(output_path=tmp_path)
        path = tmp_path / "small.xlsx"
        path.write_bytes(b"x" * 1024)
        assert gen.verify_file_size(path, "small.xlsx") == 1024

    def test_rejects_oversized_file_and_unlinks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gen = BaseDocumentGenerator(output_path=tmp_path)
        monkeypatch.setattr(gen, "_max_output_size_mb", 1)
        path = tmp_path / "big.xlsx"
        path.write_bytes(b"x" * (2 * 1024 * 1024))
        with pytest.raises(MCPZileoError) as exc_info:
            gen.verify_file_size(path, "big.xlsx")
        assert exc_info.value.code == "OUTPUT_TOO_LARGE"
        assert not path.exists()
