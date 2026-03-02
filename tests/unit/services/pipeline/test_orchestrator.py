"""Tests unitaires pour PDFPipelineOrchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.document import DocumentAnalysisResult, DocumentMetadata
from src.models.extraction import ExtractedContent, OCRResult
from src.services.pipeline.orchestrator import PDFPipelineOrchestrator, ProcessingResult


if TYPE_CHECKING:
    from collections.abc import Generator


class TestProcessingResult:
    """Tests pour ProcessingResult."""

    def test_to_dict(self) -> None:
        """Test serialisation en dictionnaire."""
        metadata = DocumentMetadata(
            document_id="test-id",
            file_hash="abc123",
            filename="test.pdf",
            file_size_bytes=1000,
        )
        analysis = DocumentAnalysisResult(
            metadata=metadata,
            pages=[],
        )

        result = ProcessingResult(
            analysis=analysis,
            native_content={},
            ocr_content={},
            processing_time_seconds=1.5,
        )

        result_dict = result.to_dict()

        assert "analysis" in result_dict
        assert "native_content" in result_dict
        assert "ocr_content" in result_dict
        assert result_dict["processing_time_seconds"] == 1.5

    def test_get_all_content_markdown(self) -> None:
        """Test concatenation du contenu Markdown."""
        metadata = DocumentMetadata(
            document_id="test-id",
            file_hash="abc123",
            filename="test.pdf",
            file_size_bytes=1000,
        )
        analysis = DocumentAnalysisResult(
            metadata=metadata,
            pages=[],
        )

        native_content = {
            0: ExtractedContent(page_number=0, markdown_content="# Page 1"),
            2: ExtractedContent(page_number=2, markdown_content="# Page 3"),
        }
        ocr_content = {
            1: OCRResult(page_number=1, markdown_content="# Page 2 (OCR)"),
        }

        result = ProcessingResult(
            analysis=analysis,
            native_content=native_content,
            ocr_content=ocr_content,
        )

        markdown = result.get_all_content_markdown()

        # Verifier l'ordre des pages
        assert "Page 1" in markdown
        assert "Page 2" in markdown
        assert "Page 3" in markdown
        assert markdown.index("Page 1") < markdown.index("Page 2")
        assert markdown.index("Page 2") < markdown.index("Page 3")


class TestPDFPipelineOrchestrator:
    """Tests pour PDFPipelineOrchestrator."""

    def test_initialization(self) -> None:
        """Test initialisation de l'orchestrateur."""
        orchestrator = PDFPipelineOrchestrator(api_key="test-key")
        assert orchestrator._api_key == "test-key"
        assert orchestrator._ocr_processor is None

    def test_lazy_ocr_processor_initialization(self) -> None:
        """Test initialisation lazy du processeur OCR."""
        orchestrator = PDFPipelineOrchestrator(api_key="test-key")

        # Premier acces initialise le processeur
        processor = orchestrator.ocr_processor
        assert processor is not None

        # Second acces retourne le meme
        processor2 = orchestrator.ocr_processor
        assert processor is processor2

    @pytest.mark.asyncio
    async def test_analyze_only(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test analyse seule sans extraction."""
        pdf_path = next(iter([sample_text_pdf]))

        orchestrator = PDFPipelineOrchestrator(api_key="test-key")
        result = await orchestrator.analyze_only(pdf_path)

        assert isinstance(result, DocumentAnalysisResult)
        assert result.metadata.total_pages == 2

    @pytest.mark.asyncio
    async def test_process_document_text_only(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test traitement document texte simple."""
        pdf_path = next(iter([sample_text_pdf]))

        orchestrator = PDFPipelineOrchestrator(api_key="test-key")

        # Skip OCR pour ce test (pas de cle API)
        result = await orchestrator.process_document(
            pdf_path,
            options={"skip_ocr": True},
        )

        assert isinstance(result, ProcessingResult)
        assert result.analysis.metadata.total_pages == 2
        # Toutes les pages sont TEXT_ONLY donc extraction native
        assert result.pages_processed_native > 0

    @pytest.mark.asyncio
    async def test_process_document_with_timestamps(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test que les timestamps sont mis a jour."""
        pdf_path = next(iter([sample_text_pdf]))

        orchestrator = PDFPipelineOrchestrator(api_key="test-key")
        result = await orchestrator.process_document(
            pdf_path,
            options={"skip_ocr": True},
        )

        # processed_at doit etre defini apres traitement
        assert result.analysis.metadata.processed_at is not None
        assert result.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_process_document_force_ocr(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test force_ocr sur toutes les pages."""
        pdf_path = next(iter([sample_text_pdf]))

        orchestrator = PDFPipelineOrchestrator(api_key="test-key")

        # Mock le processeur OCR
        mock_ocr = AsyncMock()
        mock_ocr.return_value = {
            0: OCRResult(page_number=0, markdown_content="OCR content 0"),
            1: OCRResult(page_number=1, markdown_content="OCR content 1"),
        }

        with patch.object(
            orchestrator.ocr_processor,
            "process_pages",
            mock_ocr,
        ):
            result = await orchestrator.process_document(
                pdf_path,
                options={"force_ocr": True},
            )

            # Avec force_ocr, pas d'extraction native
            assert result.pages_processed_native == 0
            assert mock_ocr.called


class TestPipelineOrchestratorMocked:
    """Tests avec composants mockes."""

    @pytest.mark.asyncio
    async def test_full_pipeline_mocked(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test pipeline complet avec mocks."""
        pdf_path = next(iter([sample_text_pdf]))

        orchestrator = PDFPipelineOrchestrator(api_key="test-key")

        # Le document texte simple ne necessite pas d'OCR
        result = await orchestrator.process_document(
            pdf_path,
            options={"skip_ocr": True},
        )

        # Verifier structure du resultat
        assert isinstance(result, ProcessingResult)
        assert result.analysis is not None
        assert isinstance(result.native_content, dict)
        assert isinstance(result.ocr_content, dict)

    @pytest.mark.asyncio
    async def test_error_handling_native_extraction(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test gestion erreur extraction native."""
        pdf_path = next(iter([sample_text_pdf]))

        orchestrator = PDFPipelineOrchestrator(api_key="test-key")

        # Mock pour simuler une erreur
        with patch(
            "src.services.pipeline.orchestrator.NativeContentExtractor"
        ) as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_extractor.extract_pages = AsyncMock(side_effect=Exception("Extraction error"))
            mock_extractor_class.return_value = mock_extractor

            result = await orchestrator.process_document(
                pdf_path,
                options={"skip_ocr": True},
            )

            # L'erreur doit etre capturee
            assert result.total_errors > 0
            assert any("native_extraction" in e["phase"] for e in result.errors)

    @pytest.mark.asyncio
    async def test_extract_specific_pages(
        self, sample_multipage_pdf: Generator[Path, None, None]
    ) -> None:
        """Test extraction de pages specifiques."""
        pdf_path = next(iter([sample_multipage_pdf]))

        orchestrator = PDFPipelineOrchestrator(api_key="test-key")

        # Extraire seulement les pages 0 et 2
        results = await orchestrator.extract_pages(
            pdf_path,
            page_numbers=[0, 2],
            force_ocr=False,
        )

        # Devrait avoir 2 resultats
        assert len(results) == 2
        assert 0 in results
        assert 2 in results

    @pytest.mark.asyncio
    async def test_extract_pages_force_ocr(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test extraction pages avec force_ocr."""
        pdf_path = next(iter([sample_text_pdf]))

        orchestrator = PDFPipelineOrchestrator(api_key="test-key")

        # Mock le processeur OCR
        mock_result = {
            0: OCRResult(page_number=0, markdown_content="OCR content"),
        }

        with patch.object(
            orchestrator.ocr_processor,
            "process_pages",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            results = await orchestrator.extract_pages(
                pdf_path,
                page_numbers=[0],
                force_ocr=True,
            )

            assert 0 in results
            assert isinstance(results[0], OCRResult)
