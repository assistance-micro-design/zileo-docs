# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour les models Pydantic d'inspection de templates PowerPoint."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.template_inspection import (
    LayoutInfo,
    PlaceholderInfo,
    TemplateInspectionResult,
    ThemeInfo,
)


class TestPlaceholderInfo:
    """Tests pour PlaceholderInfo."""

    def test_valid(self) -> None:
        ph = PlaceholderInfo(
            idx=0,
            name="Title 1",
            type="TITLE",
            left_cm=1.52,
            top_cm=6.02,
            width_cm=21.33,
            height_cm=3.25,
        )
        assert ph.idx == 0
        assert ph.name == "Title 1"
        assert ph.type == "TITLE"
        assert ph.left_cm == 1.52

    def test_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            PlaceholderInfo(idx=0, name="Title 1")  # type: ignore[call-arg]


class TestLayoutInfo:
    """Tests pour LayoutInfo."""

    def test_valid_with_placeholders(self) -> None:
        layout = LayoutInfo(
            index=0,
            name="Title Slide",
            placeholders=[
                PlaceholderInfo(
                    idx=0,
                    name="Title 1",
                    type="TITLE",
                    left_cm=1.0,
                    top_cm=2.0,
                    width_cm=20.0,
                    height_cm=3.0,
                ),
            ],
        )
        assert layout.index == 0
        assert layout.name == "Title Slide"
        assert len(layout.placeholders) == 1

    def test_empty_placeholders(self) -> None:
        layout = LayoutInfo(index=6, name="Blank", placeholders=[])
        assert layout.placeholders == []


class TestThemeInfo:
    """Tests pour ThemeInfo."""

    def test_defaults_all_none(self) -> None:
        theme = ThemeInfo()
        assert theme.name is None
        assert theme.color_scheme is None
        assert theme.font_major is None
        assert theme.font_minor is None

    def test_full(self) -> None:
        theme = ThemeInfo(
            name="Office Theme",
            color_scheme="Office",
            font_major="Calibri Light",
            font_minor="Calibri",
        )
        assert theme.name == "Office Theme"
        assert theme.font_major == "Calibri Light"


class TestTemplateInspectionResult:
    """Tests pour TemplateInspectionResult."""

    def test_valid_complete(self) -> None:
        result = TemplateInspectionResult(
            template="corporate.pptx",
            file_size_bytes=45320,
            slide_width_cm=33.87,
            slide_height_cm=19.05,
            theme=ThemeInfo(name="Office Theme"),
            total_layouts=2,
            layouts=[
                LayoutInfo(
                    index=0,
                    name="Title Slide",
                    placeholders=[
                        PlaceholderInfo(
                            idx=0,
                            name="Title 1",
                            type="TITLE",
                            left_cm=1.0,
                            top_cm=2.0,
                            width_cm=20.0,
                            height_cm=3.0,
                        ),
                    ],
                ),
                LayoutInfo(index=6, name="Blank", placeholders=[]),
            ],
            existing_slides_count=0,
            hint="Ce template a 2 layouts.",
        )
        assert result.template == "corporate.pptx"
        assert result.total_layouts == 2
        assert len(result.layouts) == 2
        assert result.existing_slides_count == 0

    def test_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            TemplateInspectionResult(template="x.pptx")  # type: ignore[call-arg]
