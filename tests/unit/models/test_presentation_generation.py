# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour les models Pydantic de generation de presentations PowerPoint."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.api import CreatePresentationParams, CreatePresentationResult
from src.models.presentation_generation import (
    BulletItem,
    ChartSeriesDef,
    ChartSlideDef,
    ClosingSlideDef,
    ContentBulletsSlideDef,
    ContentWithImageSlideDef,
    ImageDef,
    ImageFullSlideDef,
    PresentationChartDef,
    SectionHeaderSlideDef,
    SlideLayout,
    TextStyle,
    TitleSlideDef,
    TwoColumnsSlideDef,
)


class TestSlideLayout:
    """Tests pour l'enum SlideLayout."""

    def test_all_layouts(self) -> None:
        assert len(SlideLayout) == 8
        assert SlideLayout.TITLE_SLIDE == "title_slide"
        assert SlideLayout.CONTENT_BULLETS == "content_bullets"
        assert SlideLayout.CONTENT_WITH_IMAGE == "content_with_image"
        assert SlideLayout.SECTION_HEADER == "section_header"
        assert SlideLayout.TWO_COLUMNS == "two_columns"
        assert SlideLayout.IMAGE_FULL == "image_full"
        assert SlideLayout.CHART_SLIDE == "chart_slide"
        assert SlideLayout.CLOSING == "closing"


class TestTextStyle:
    """Tests pour TextStyle."""

    def test_defaults(self) -> None:
        style = TextStyle()
        assert style.bold is False
        assert style.italic is False
        assert style.font_size is None
        assert style.font_color is None

    def test_full_style(self) -> None:
        style = TextStyle(bold=True, italic=True, font_size=24, font_color="FF0000")
        assert style.bold is True
        assert style.font_size == 24
        assert style.font_color == "FF0000"

    def test_font_size_bounds(self) -> None:
        TextStyle(font_size=8)
        TextStyle(font_size=96)
        with pytest.raises(ValidationError):
            TextStyle(font_size=7)
        with pytest.raises(ValidationError):
            TextStyle(font_size=97)

    def test_invalid_font_color(self) -> None:
        with pytest.raises(ValidationError, match="font_color"):
            TextStyle(font_color="ZZZZZZ")


class TestBulletItem:
    """Tests pour BulletItem."""

    def test_simple_bullet(self) -> None:
        b = BulletItem(text="Point important")
        assert b.text == "Point important"
        assert b.level == 0
        assert b.bold is False

    def test_nested_bullet(self) -> None:
        b = BulletItem(text="Sous-point", level=2, bold=True)
        assert b.level == 2
        assert b.bold is True

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError, match="text"):
            BulletItem(text="")

    def test_level_bounds(self) -> None:
        BulletItem(text="x", level=0)
        BulletItem(text="x", level=3)
        with pytest.raises(ValidationError):
            BulletItem(text="x", level=4)


class TestImageDef:
    """Tests pour ImageDef."""

    def test_minimal_image(self) -> None:
        img = ImageDef(filename="chart.png")
        assert img.filename == "chart.png"
        assert img.width_cm is None
        assert img.height_cm is None

    def test_image_with_dimensions(self) -> None:
        img = ImageDef(filename="photo.jpg", width_cm=10.0, height_cm=7.5)
        assert img.width_cm == 10.0
        assert img.height_cm == 7.5

    def test_empty_filename_rejected(self) -> None:
        with pytest.raises(ValidationError, match="filename"):
            ImageDef(filename="")


class TestPresentationChartDef:
    """Tests pour PresentationChartDef."""

    def test_minimal_chart(self) -> None:
        chart = PresentationChartDef(
            chart_type="bar",
            categories=["Q1", "Q2"],
            series=[ChartSeriesDef(name="Ventes", values=[100, 200])],
        )
        assert chart.chart_type == "bar"
        assert len(chart.categories) == 2

    def test_all_chart_types(self) -> None:
        for ct in ("bar", "line", "pie", "scatter", "area", "column", "doughnut"):
            chart = PresentationChartDef(
                chart_type=ct,
                categories=["A"],
                series=[ChartSeriesDef(name="S", values=[1])],
            )
            assert chart.chart_type == ct

    def test_invalid_chart_type(self) -> None:
        with pytest.raises(ValidationError, match="chart_type"):
            PresentationChartDef(
                chart_type="radar",
                categories=["A"],
                series=[ChartSeriesDef(name="S", values=[1])],
            )

    def test_empty_categories_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PresentationChartDef(
                chart_type="bar",
                categories=[],
                series=[ChartSeriesDef(name="S", values=[1])],
            )


class TestTitleSlideDef:
    """Tests pour TitleSlideDef."""

    def test_minimal(self) -> None:
        slide = TitleSlideDef(title="Ma Presentation")
        assert slide.layout == "title_slide"
        assert slide.title == "Ma Presentation"
        assert slide.subtitle is None
        assert slide.notes is None

    def test_with_all_fields(self) -> None:
        slide = TitleSlideDef(
            title="Titre",
            subtitle="Sous-titre",
            title_style=TextStyle(bold=True, font_size=44),
            notes="Notes du presentateur",
        )
        assert slide.subtitle == "Sous-titre"
        assert slide.title_style is not None
        assert slide.title_style.bold is True
        assert slide.notes == "Notes du presentateur"


class TestContentBulletsSlideDef:
    """Tests pour ContentBulletsSlideDef."""

    def test_minimal(self) -> None:
        slide = ContentBulletsSlideDef(
            title="Points cles",
            bullets=[BulletItem(text="Premier")],
        )
        assert slide.layout == "content_bullets"
        assert len(slide.bullets) == 1

    def test_empty_bullets_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ContentBulletsSlideDef(title="T", bullets=[])


class TestContentWithImageSlideDef:
    """Tests pour ContentWithImageSlideDef."""

    def test_valid(self) -> None:
        slide = ContentWithImageSlideDef(
            title="Slide avec image",
            bullets=[BulletItem(text="Point")],
            image=ImageDef(filename="graph.png"),
        )
        assert slide.layout == "content_with_image"
        assert slide.image.filename == "graph.png"


class TestSectionHeaderSlideDef:
    """Tests pour SectionHeaderSlideDef."""

    def test_minimal(self) -> None:
        slide = SectionHeaderSlideDef(title="Section 1")
        assert slide.layout == "section_header"
        assert slide.subtitle is None


class TestTwoColumnsSlideDef:
    """Tests pour TwoColumnsSlideDef."""

    def test_valid(self) -> None:
        slide = TwoColumnsSlideDef(
            title="Comparaison",
            left_bullets=[BulletItem(text="Gauche")],
            right_bullets=[BulletItem(text="Droite")],
        )
        assert slide.layout == "two_columns"
        assert len(slide.left_bullets) == 1
        assert len(slide.right_bullets) == 1


class TestImageFullSlideDef:
    """Tests pour ImageFullSlideDef."""

    def test_minimal(self) -> None:
        slide = ImageFullSlideDef(image=ImageDef(filename="photo.jpg"))
        assert slide.layout == "image_full"
        assert slide.title is None
        assert slide.caption is None

    def test_with_title_and_caption(self) -> None:
        slide = ImageFullSlideDef(
            image=ImageDef(filename="photo.jpg"),
            title="Architecture",
            caption="Vue d'ensemble",
        )
        assert slide.title == "Architecture"
        assert slide.caption == "Vue d'ensemble"


class TestChartSlideDef:
    """Tests pour ChartSlideDef."""

    def test_valid(self) -> None:
        slide = ChartSlideDef(
            title="Resultats",
            chart=PresentationChartDef(
                chart_type="pie",
                categories=["A", "B"],
                series=[ChartSeriesDef(name="Repartition", values=[60, 40])],
            ),
        )
        assert slide.layout == "chart_slide"
        assert slide.chart.chart_type == "pie"


class TestClosingSlideDef:
    """Tests pour ClosingSlideDef."""

    def test_minimal(self) -> None:
        slide = ClosingSlideDef(title="Merci !")
        assert slide.layout == "closing"
        assert slide.subtitle is None
        assert slide.bullets is None

    def test_with_bullets(self) -> None:
        slide = ClosingSlideDef(
            title="Q&A",
            subtitle="Des questions ?",
            bullets=[BulletItem(text="email@example.com")],
        )
        assert slide.subtitle == "Des questions ?"
        assert len(slide.bullets) == 1


class TestDiscriminatedUnion:
    """Tests pour la discriminated union SlideDef."""

    def test_title_slide_from_dict(self) -> None:
        params = CreatePresentationParams(
            filename="test.pptx",
            slides=[{"layout": "title_slide", "title": "Test"}],  # type: ignore[list-item]
        )
        assert params.slides[0].layout == "title_slide"

    def test_content_bullets_from_dict(self) -> None:
        params = CreatePresentationParams(
            filename="test.pptx",
            slides=[
                {  # type: ignore[list-item]
                    "layout": "content_bullets",
                    "title": "T",
                    "bullets": [{"text": "P"}],
                }
            ],
        )
        assert isinstance(params.slides[0], ContentBulletsSlideDef)

    def test_invalid_layout_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreatePresentationParams(
                filename="test.pptx",
                slides=[{"layout": "unknown", "title": "T"}],  # type: ignore[list-item]
            )


class TestCreatePresentationParams:
    """Tests pour CreatePresentationParams."""

    def test_minimal(self) -> None:
        params = CreatePresentationParams(
            filename="pres.pptx",
            slides=[TitleSlideDef(title="T")],
        )
        assert params.filename == "pres.pptx"
        assert params.author is None
        assert params.template is None

    def test_filename_must_end_pptx(self) -> None:
        with pytest.raises(ValidationError, match="filename"):
            CreatePresentationParams(
                filename="test.ppt",
                slides=[TitleSlideDef(title="T")],
            )

    def test_filename_path_traversal_rejected(self) -> None:
        with pytest.raises(ValidationError, match="filename"):
            CreatePresentationParams(
                filename="../evil.pptx",
                slides=[TitleSlideDef(title="T")],
            )

    def test_slides_empty_rejected(self) -> None:
        with pytest.raises(ValidationError, match="slides"):
            CreatePresentationParams(filename="test.pptx", slides=[])

    def test_with_author_and_template(self) -> None:
        params = CreatePresentationParams(
            filename="test.pptx",
            slides=[TitleSlideDef(title="T")],
            author="Zileo",
            template="corporate.pptx",
        )
        assert params.author == "Zileo"
        assert params.template == "corporate.pptx"

    def test_author_max_length_255(self) -> None:
        with pytest.raises(ValidationError, match="author"):
            CreatePresentationParams(
                filename="test.pptx",
                slides=[TitleSlideDef(title="T")],
                author="A" * 256,
            )


class TestCreatePresentationResult:
    """Tests pour CreatePresentationResult."""

    def test_result_fields(self) -> None:
        result = CreatePresentationResult(
            file_path="/app/output/pres.pptx",
            filename="pres.pptx",
            slides_created=5,
            total_images=2,
            total_charts=1,
            file_size_bytes=50000,
            overwritten=False,
        )
        assert result.file_path == "/app/output/pres.pptx"
        assert result.slides_created == 5
        assert result.total_images == 2
        assert result.total_charts == 1
        assert result.overwritten is False
