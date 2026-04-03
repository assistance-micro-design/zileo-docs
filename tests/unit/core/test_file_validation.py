"""Tests unitaires pour la validation de fichiers."""

from __future__ import annotations

from pathlib import Path

from src.core.file_validation import (
    compute_file_hash,
    validate_file_magic,
    validate_filename_safety,
)


class TestValidateFilenameSafety:
    """Tests pour validate_filename_safety."""

    def test_safe_filename(self) -> None:
        assert validate_filename_safety("report.xlsx") is True

    def test_dotdot_rejected(self) -> None:
        assert validate_filename_safety("../etc/passwd") is False

    def test_slash_rejected(self) -> None:
        assert validate_filename_safety("path/file.xlsx") is False

    def test_backslash_rejected(self) -> None:
        assert validate_filename_safety("path\\file.xlsx") is False

    def test_filename_with_spaces(self) -> None:
        assert validate_filename_safety("my report.xlsx") is True


class TestValidateFileMagic:
    """Tests pour validate_file_magic."""

    def test_valid_pdf(self, tmp_path: Path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        assert validate_file_magic(pdf) is True

    def test_invalid_pdf_magic(self, tmp_path: Path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"PK\x03\x04 not a pdf")
        assert validate_file_magic(pdf) is False

    def test_valid_xlsx(self, tmp_path: Path) -> None:
        xlsx = tmp_path / "test.xlsx"
        xlsx.write_bytes(b"PK\x03\x04 zip content")
        assert validate_file_magic(xlsx) is True

    def test_unknown_extension_always_valid(self, tmp_path: Path) -> None:
        txt = tmp_path / "test.txt"
        txt.write_bytes(b"just text")
        assert validate_file_magic(txt) is True


class TestComputeFileHash:
    """Tests pour compute_file_hash."""

    def test_returns_sha256_hex(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        h = compute_file_hash(f)
        assert len(h) == 64  # SHA-256 hex = 64 chars
        assert h.isalnum()

    def test_same_content_same_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"identical")
        f2.write_bytes(b"identical")
        assert compute_file_hash(f1) == compute_file_hash(f2)

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert compute_file_hash(f1) != compute_file_hash(f2)
