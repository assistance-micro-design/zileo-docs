"""Configuration pytest et fixtures partagees."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import fitz  # PyMuPDF
import pytest


# =============================================================================
# Fixtures: PDF Files
# =============================================================================


@pytest.fixture
def sample_text_pdf(tmp_path: Path) -> Generator[Path, None, None]:
    """Cree un PDF simple avec du texte uniquement."""
    pdf_path = tmp_path / "text_only.pdf"
    doc = fitz.open()

    # Page 1: Texte simple
    page = doc.new_page()
    text = """# Introduction

    Ceci est un document de test avec du texte simple.

    Lorem ipsum dolor sit amet, consectetur adipiscing elit.
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

    ## Section 1

    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.

    - Point 1
    - Point 2
    - Point 3

    ## Section 2

    Duis aute irure dolor in reprehenderit in voluptate velit esse.
    """
    page.insert_text((72, 72), text, fontsize=11)

    # Page 2: Plus de texte
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Page 2 avec plus de contenu texte.", fontsize=11)

    doc.save(pdf_path)
    doc.close()

    yield pdf_path

    # Cleanup
    if pdf_path.exists():
        pdf_path.unlink()


@pytest.fixture
def sample_pdf_with_table(tmp_path: Path) -> Generator[Path, None, None]:
    """Cree un PDF avec un tableau simple."""
    pdf_path = tmp_path / "with_table.pdf"
    doc = fitz.open()

    page = doc.new_page()

    # Ajouter du texte
    page.insert_text((72, 72), "Document avec tableau", fontsize=14)

    # Dessiner un tableau simple (rectangles)
    rect = fitz.Rect(72, 100, 500, 300)
    page.draw_rect(rect, color=(0, 0, 0), width=1)

    # Lignes horizontales
    for y in [140, 180, 220, 260]:
        page.draw_line((72, y), (500, y), color=(0, 0, 0), width=0.5)

    # Lignes verticales
    for x in [200, 350]:
        page.draw_line((x, 100), (x, 300), color=(0, 0, 0), width=0.5)

    # Headers
    page.insert_text((80, 125), "Colonne 1", fontsize=10)
    page.insert_text((210, 125), "Colonne 2", fontsize=10)
    page.insert_text((360, 125), "Colonne 3", fontsize=10)

    doc.save(pdf_path)
    doc.close()

    yield pdf_path

    if pdf_path.exists():
        pdf_path.unlink()


@pytest.fixture
def sample_pdf_with_image(tmp_path: Path) -> Generator[Path, None, None]:
    """Cree un PDF avec une image."""
    pdf_path = tmp_path / "with_image.pdf"
    doc = fitz.open()

    page = doc.new_page()
    page.insert_text((72, 72), "Document avec image", fontsize=14)

    # Creer une image simple (rectangle colore)
    # Simuler une grande image qui couvre 30% de la page
    rect = fitz.Rect(72, 150, 400, 500)
    page.draw_rect(rect, color=(0.2, 0.4, 0.8), fill=(0.8, 0.9, 1.0), width=2)

    doc.save(pdf_path)
    doc.close()

    yield pdf_path

    if pdf_path.exists():
        pdf_path.unlink()


@pytest.fixture
def sample_empty_pdf(tmp_path: Path) -> Generator[Path, None, None]:
    """Cree un PDF vide (page blanche)."""
    pdf_path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    yield pdf_path

    if pdf_path.exists():
        pdf_path.unlink()


@pytest.fixture
def sample_multipage_pdf(tmp_path: Path) -> Generator[Path, None, None]:
    """Cree un PDF avec plusieurs pages de types differents."""
    pdf_path = tmp_path / "multipage.pdf"
    doc = fitz.open()

    # Page 1: Texte simple
    page1 = doc.new_page()
    page1.insert_text(
        (72, 72),
        "Page 1: Texte simple\n\n" + "Lorem ipsum " * 100,
        fontsize=11,
    )

    # Page 2: Avec tableau (dessins)
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Page 2: Avec tableau", fontsize=14)
    # Dessiner beaucoup de lignes pour simuler un tableau complexe
    for i in range(10):
        page2.draw_line((72, 100 + i * 30), (500, 100 + i * 30), width=0.5)
        page2.draw_line((72 + i * 45, 100), (72 + i * 45, 370), width=0.5)

    # Page 3: Plus de texte
    page3 = doc.new_page()
    page3.insert_text(
        (72, 72),
        "Page 3: Conclusion\n\n" + "Sed ut perspiciatis " * 80,
        fontsize=11,
    )

    doc.save(pdf_path)
    doc.close()

    yield pdf_path

    if pdf_path.exists():
        pdf_path.unlink()


# =============================================================================
# Fixtures: Document Models
# =============================================================================


@pytest.fixture
def sample_document_metadata() -> dict[str, object]:
    """Retourne des metadonnees de document de test."""
    return {
        "document_id": "doc-test-123",
        "file_hash": "abc123def456",
        "filename": "test_document.pdf",
        "file_size_bytes": 1024000,
        "title": "Document de Test",
        "author": "Test Author",
        "total_pages": 10,
    }


@pytest.fixture
def sample_page_analysis() -> dict[str, object]:
    """Retourne une analyse de page de test."""
    return {
        "page_number": 1,
        "page_type": "text_only",
        "has_native_text": True,
        "native_text_length": 5000,
        "has_images": False,
        "image_count": 0,
        "image_coverage_ratio": 0.0,
        "has_tables": False,
        "table_count": 0,
        "has_charts": False,
        "width": 612.0,
        "height": 792.0,
        "rotation": 0,
        "extraction_method": "pymupdf",
        "priority": 1,
    }


# =============================================================================
# Fixtures: Chunk Models
# =============================================================================


@pytest.fixture
def sample_chunk_metadata() -> dict[str, object]:
    """Retourne des metadonnees de chunk de test."""
    return {
        "chunk_id": "chunk-001",
        "document_id": "doc-test-123",
        "page_numbers": [1, 2],
        "start_page": 1,
        "end_page": 2,
        "section_title": "Introduction",
        "content_type": "text",
        "token_count": 256,
    }


# =============================================================================
# Fixtures: Extraction Models
# =============================================================================


@pytest.fixture
def sample_extracted_content() -> dict[str, object]:
    """Retourne un contenu extrait de test."""
    return {
        "page_number": 1,
        "markdown_content": "# Titre\n\nContenu du paragraphe.",
        "extraction_method": "pymupdf4llm",
        "char_count": 35,
        "word_count": 4,
    }


@pytest.fixture
def fixed_datetime() -> datetime:
    """Retourne une datetime fixe pour les tests."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
