# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour le service TemplateInspector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.inspection.template_inspector import TemplateInspector


_PATCH_PPTX = "pptx.Presentation"


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    """Repertoire temporaire pour les templates."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()
    return tpl_dir


@pytest.fixture
def inspector(templates_dir: Path) -> TemplateInspector:
    """Inspector avec repertoire temporaire."""
    return TemplateInspector(templates_path=templates_dir)


def _create_mock_presentation() -> MagicMock:
    """Cree un mock python-pptx Presentation avec 2 layouts."""
    prs = MagicMock()

    # Dimensions du slide
    prs.slide_width = 12192000  # ~33.87 cm en EMU
    prs.slide_height = 6858000  # ~19.05 cm en EMU

    # Slides existants (vide)
    prs.slides = []

    # Layout "Title Slide" avec 2 placeholders
    ph_title = MagicMock()
    ph_title.placeholder_format.idx = 0
    ph_title.name = "Title 1"
    ph_title.placeholder_format.type = MagicMock(__str__=lambda _s: "TITLE (1)")
    ph_title.left = 547688
    ph_title.top = 2160588
    ph_title.width = 7629525
    ph_title.height = 1165225

    ph_subtitle = MagicMock()
    ph_subtitle.placeholder_format.idx = 1
    ph_subtitle.name = "Subtitle 2"
    ph_subtitle.placeholder_format.type = MagicMock(__str__=lambda _s: "SUBTITLE (2)")
    ph_subtitle.left = 547688
    ph_subtitle.top = 3556000
    ph_subtitle.width = 7629525
    ph_subtitle.height = 756000

    layout_title = MagicMock()
    layout_title.name = "Title Slide"
    layout_title.placeholders = [ph_title, ph_subtitle]

    layout_blank = MagicMock()
    layout_blank.name = "Blank"
    layout_blank.placeholders = []

    prs.slide_layouts = [layout_title, layout_blank]

    # Slide master pour le theme
    master = MagicMock()
    master.element.find.return_value = None
    prs.slide_masters = [master]

    return prs


class TestTemplateInspectorSecurity:
    """Tests de securite (path traversal, fichier inexistant)."""

    @pytest.mark.asyncio
    async def test_path_traversal_dot_dot(self, inspector: TemplateInspector) -> None:
        result = await inspector.inspect("../secret.pptx")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_path_traversal_slash(self, inspector: TemplateInspector) -> None:
        result = await inspector.inspect("/etc/passwd")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_path_traversal_backslash(self, inspector: TemplateInspector) -> None:
        result = await inspector.inspect("..\\secret.pptx")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_template_not_found(self, inspector: TemplateInspector) -> None:
        result = await inspector.inspect("nonexistent.pptx")
        assert "error" in result
        assert "available_templates" in result

    @pytest.mark.asyncio
    async def test_template_not_found_lists_available(
        self, inspector: TemplateInspector, templates_dir: Path
    ) -> None:
        (templates_dir / "existing.pptx").write_bytes(b"PK")
        result = await inspector.inspect("nonexistent.pptx")
        assert "existing.pptx" in result["available_templates"]


class TestTemplateInspectorExtraction:
    """Tests d'extraction des layouts et placeholders."""

    @pytest.mark.asyncio
    async def test_extracts_layouts(
        self, inspector: TemplateInspector, templates_dir: Path
    ) -> None:
        (templates_dir / "test.pptx").write_bytes(b"PK fake pptx")

        with patch(_PATCH_PPTX, return_value=_create_mock_presentation()):
            result = await inspector.inspect("test.pptx")

        assert result["total_layouts"] == 2
        assert result["layouts"][0]["name"] == "Title Slide"
        assert result["layouts"][1]["name"] == "Blank"

    @pytest.mark.asyncio
    async def test_extracts_placeholders(
        self, inspector: TemplateInspector, templates_dir: Path
    ) -> None:
        (templates_dir / "test.pptx").write_bytes(b"PK fake pptx")

        with patch(_PATCH_PPTX, return_value=_create_mock_presentation()):
            result = await inspector.inspect("test.pptx")

        placeholders = result["layouts"][0]["placeholders"]
        assert len(placeholders) == 2
        assert placeholders[0]["idx"] == 0
        assert placeholders[0]["name"] == "Title 1"
        assert "TITLE" in placeholders[0]["type"]
        assert isinstance(placeholders[0]["left_cm"], float)
        assert isinstance(placeholders[0]["width_cm"], float)

    @pytest.mark.asyncio
    async def test_extracts_blank_layout_no_placeholders(
        self, inspector: TemplateInspector, templates_dir: Path
    ) -> None:
        (templates_dir / "test.pptx").write_bytes(b"PK fake pptx")

        with patch(_PATCH_PPTX, return_value=_create_mock_presentation()):
            result = await inspector.inspect("test.pptx")

        assert result["layouts"][1]["placeholders"] == []

    @pytest.mark.asyncio
    async def test_extracts_slide_dimensions(
        self, inspector: TemplateInspector, templates_dir: Path
    ) -> None:
        (templates_dir / "test.pptx").write_bytes(b"PK fake pptx")

        with patch(_PATCH_PPTX, return_value=_create_mock_presentation()):
            result = await inspector.inspect("test.pptx")

        assert result["slide_width_cm"] == pytest.approx(33.87, abs=0.1)
        assert result["slide_height_cm"] == pytest.approx(19.05, abs=0.1)

    @pytest.mark.asyncio
    async def test_extracts_existing_slides_count(
        self, inspector: TemplateInspector, templates_dir: Path
    ) -> None:
        (templates_dir / "test.pptx").write_bytes(b"PK fake pptx")

        with patch(_PATCH_PPTX, return_value=_create_mock_presentation()):
            result = await inspector.inspect("test.pptx")

        assert result["existing_slides_count"] == 0

    @pytest.mark.asyncio
    async def test_extracts_theme_info(
        self, inspector: TemplateInspector, templates_dir: Path
    ) -> None:
        (templates_dir / "test.pptx").write_bytes(b"PK fake pptx")

        with patch(_PATCH_PPTX, return_value=_create_mock_presentation()):
            result = await inspector.inspect("test.pptx")

        assert "theme" in result
        assert isinstance(result["theme"], dict)

    @pytest.mark.asyncio
    async def test_returns_hint(self, inspector: TemplateInspector, templates_dir: Path) -> None:
        (templates_dir / "test.pptx").write_bytes(b"PK fake pptx")

        with patch(_PATCH_PPTX, return_value=_create_mock_presentation()):
            result = await inspector.inspect("test.pptx")

        assert "hint" in result
        assert "2 layouts" in result["hint"]

    @pytest.mark.asyncio
    async def test_corrupted_file(self, inspector: TemplateInspector, templates_dir: Path) -> None:
        (templates_dir / "corrupted.pptx").write_bytes(b"not a real pptx")

        with patch(_PATCH_PPTX, side_effect=Exception("Bad file")):
            result = await inspector.inspect("corrupted.pptx")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_returns_file_size(
        self, inspector: TemplateInspector, templates_dir: Path
    ) -> None:
        (templates_dir / "test.pptx").write_bytes(b"PK" * 100)

        with patch(_PATCH_PPTX, return_value=_create_mock_presentation()):
            result = await inspector.inspect("test.pptx")

        assert result["file_size_bytes"] == 200
