# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour les models Pydantic d'edition de presentations PowerPoint."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.api import EditPresentationParams
from src.models.presentation_edit import (
    AddImageOp,
    AddSlideOp,
    DeleteSlideOp,
    ReorderSlideOp,
    ReplaceImageOp,
    SetBackgroundOp,
    UpdateBulletsOp,
    UpdateChartOp,
    UpdateNotesOp,
    UpdateSubtitleOp,
    UpdateTitleOp,
)
from src.models.presentation_generation import (
    BulletItem,
    ChartSeriesDef,
    ImageDef,
    PresentationChartDef,
    TextStyle,
    TitleSlideDef,
)


class TestUpdateTitleOp:
    """Tests pour UpdateTitleOp."""

    def test_valid(self) -> None:
        op = UpdateTitleOp(slide_index=0, title="Nouveau titre")
        assert op.op == "update_title"
        assert op.slide_index == 0
        assert op.title == "Nouveau titre"
        assert op.style is None

    def test_with_style(self) -> None:
        op = UpdateTitleOp(
            slide_index=1,
            title="Styled",
            style=TextStyle(bold=True, font_size=36),
        )
        assert op.style is not None
        assert op.style.bold is True

    def test_negative_index_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateTitleOp(slide_index=-1, title="T")

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError, match="title"):
            UpdateTitleOp(slide_index=0, title="")


class TestUpdateSubtitleOp:
    """Tests pour UpdateSubtitleOp."""

    def test_valid(self) -> None:
        op = UpdateSubtitleOp(slide_index=0, subtitle="Sous-titre")
        assert op.op == "update_subtitle"
        assert op.subtitle == "Sous-titre"


class TestUpdateBulletsOp:
    """Tests pour UpdateBulletsOp."""

    def test_valid(self) -> None:
        op = UpdateBulletsOp(
            slide_index=1,
            bullets=[BulletItem(text="A"), BulletItem(text="B")],
        )
        assert op.op == "update_bullets"
        assert len(op.bullets) == 2

    def test_empty_bullets_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateBulletsOp(slide_index=0, bullets=[])


class TestAddSlideOp:
    """Tests pour AddSlideOp."""

    def test_append(self) -> None:
        op = AddSlideOp(slide=TitleSlideDef(title="New"))
        assert op.op == "add_slide"
        assert op.at_index is None

    def test_insert_at_index(self) -> None:
        op = AddSlideOp(slide=TitleSlideDef(title="New"), at_index=2)
        assert op.at_index == 2


class TestDeleteSlideOp:
    """Tests pour DeleteSlideOp."""

    def test_valid(self) -> None:
        op = DeleteSlideOp(slide_index=3)
        assert op.op == "delete_slide"
        assert op.slide_index == 3


class TestReorderSlideOp:
    """Tests pour ReorderSlideOp."""

    def test_valid(self) -> None:
        op = ReorderSlideOp(from_index=0, to_index=3)
        assert op.op == "reorder_slide"

    def test_same_indices_rejected(self) -> None:
        with pytest.raises(ValidationError, match="differents"):
            ReorderSlideOp(from_index=2, to_index=2)


class TestReplaceImageOp:
    """Tests pour ReplaceImageOp."""

    def test_valid(self) -> None:
        op = ReplaceImageOp(slide_index=1, image=ImageDef(filename="new.png"))
        assert op.op == "replace_image"
        assert op.image.filename == "new.png"


class TestAddImageOp:
    """Tests pour AddImageOp."""

    def test_valid(self) -> None:
        op = AddImageOp(slide_index=0, image=ImageDef(filename="logo.png"))
        assert op.op == "add_image"


class TestUpdateNotesOp:
    """Tests pour UpdateNotesOp."""

    def test_valid(self) -> None:
        op = UpdateNotesOp(slide_index=0, notes="Notes ici")
        assert op.op == "update_notes"

    def test_max_length(self) -> None:
        op = UpdateNotesOp(slide_index=0, notes="x" * 5000)
        assert len(op.notes) == 5000

        with pytest.raises(ValidationError):
            UpdateNotesOp(slide_index=0, notes="x" * 5001)


class TestUpdateChartOp:
    """Tests pour UpdateChartOp."""

    def test_valid(self) -> None:
        op = UpdateChartOp(
            slide_index=2,
            chart=PresentationChartDef(
                chart_type="line",
                categories=["Jan", "Feb"],
                series=[ChartSeriesDef(name="Revenue", values=[100, 150])],
            ),
        )
        assert op.op == "update_chart"
        assert op.chart.chart_type == "line"


class TestSetBackgroundOp:
    """Tests pour SetBackgroundOp."""

    def test_valid(self) -> None:
        op = SetBackgroundOp(slide_index=0, color="FFFFFF")
        assert op.op == "set_background"
        assert op.color == "FFFFFF"

    def test_invalid_color_rejected(self) -> None:
        with pytest.raises(ValidationError, match="color"):
            SetBackgroundOp(slide_index=0, color="GGGGGG")


class TestDiscriminatedUnion:
    """Tests pour la discriminated union PresentationEditOp."""

    def test_from_dict_update_title(self) -> None:
        params = EditPresentationParams(
            filename="test.pptx",
            operations=[{"op": "update_title", "slide_index": 0, "title": "T"}],  # type: ignore[list-item]
        )
        assert isinstance(params.operations[0], UpdateTitleOp)

    def test_from_dict_delete_slide(self) -> None:
        params = EditPresentationParams(
            filename="test.pptx",
            operations=[{"op": "delete_slide", "slide_index": 0}],  # type: ignore[list-item]
        )
        assert isinstance(params.operations[0], DeleteSlideOp)

    def test_invalid_op_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EditPresentationParams(
                filename="test.pptx",
                operations=[{"op": "unknown_op", "slide_index": 0}],  # type: ignore[list-item]
            )

    def test_missing_op_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EditPresentationParams(
                filename="test.pptx",
                operations=[{"slide_index": 0, "title": "T"}],  # type: ignore[list-item]
            )


class TestEditPresentationParams:
    """Tests pour EditPresentationParams."""

    def test_filename_must_end_pptx(self) -> None:
        with pytest.raises(ValidationError, match="filename"):
            EditPresentationParams(
                filename="test.ppt",
                operations=[UpdateTitleOp(slide_index=0, title="T")],
            )

    def test_operations_empty_rejected(self) -> None:
        with pytest.raises(ValidationError, match="operations"):
            EditPresentationParams(filename="test.pptx", operations=[])

    def test_operations_max_100(self) -> None:
        ops = [UpdateTitleOp(slide_index=0, title="T")] * 100
        params = EditPresentationParams(filename="test.pptx", operations=ops)
        assert len(params.operations) == 100

        ops_101 = [UpdateTitleOp(slide_index=0, title="T")] * 101
        with pytest.raises(ValidationError):
            EditPresentationParams(filename="test.pptx", operations=ops_101)
