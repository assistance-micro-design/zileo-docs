# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Routeur de documents pour le support multi-format."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar, Protocol

from src.core.file_validation import compute_file_hash
from src.models.unified import (
    DocumentType,
    FormulaData,
    StructuredData,
    UnifiedDocument,
    UnifiedImageData,
    UnifiedMetadata,
    UnifiedTableData,
)


logger = logging.getLogger(__name__)


class DocumentExtractor(Protocol):
    """Protocol pour les extracteurs de documents.

    Le type de retour est Any car les extracteurs retournent
    des types natifs (ExcelDocument, WordDocument) qui sont
    convertis en UnifiedDocument par DocumentRouter.
    """

    async def extract(self, file_path: str | Path) -> Any:
        """Extrait le contenu d'un document."""
        ...


class DocumentRouter:
    """Route les documents vers l'extracteur approprie.

    Attributes:
        SUPPORTED_EXTENSIONS: Mapping extension -> type de document.
        _extractors: Mapping type de document -> extracteur instancie.
        _initialized: Indique si les extracteurs ont ete initialises.
    """

    SUPPORTED_EXTENSIONS: ClassVar[dict[str, DocumentType]] = {
        ".pdf": DocumentType.PDF,
        ".xlsx": DocumentType.EXCEL,
        ".xls": DocumentType.EXCEL,
        ".docx": DocumentType.WORD,
    }

    def __init__(self) -> None:
        """Initialise le routeur."""
        self._extractors: dict[DocumentType, DocumentExtractor] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialise les extracteurs."""
        if self._initialized:
            return

        # Import local: ExcelExtractor/WordExtractor importent indirectement
        # des helpers qui re-importent ce module — evite un cycle reel.
        from src.services.excel.extractor import ExcelExtractor  # noqa: PLC0415
        from src.services.word.extractor import WordExtractor  # noqa: PLC0415

        self._extractors[DocumentType.EXCEL] = ExcelExtractor()
        self._extractors[DocumentType.WORD] = WordExtractor()

        self._initialized = True
        logger.info(
            "DocumentRouter initialisé avec %d extracteurs",
            len(self._extractors),
        )

    def detect_type(self, file_path: str | Path) -> DocumentType:
        """Détecte le type de document à partir de l'extension.

        Args:
            file_path: Chemin vers le fichier.

        Returns:
            Type de document détecté.

        Raises:
            ValueError: Si le format n'est pas supporté.
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(self.SUPPORTED_EXTENSIONS.keys())
            msg = f"Format non supporté: {ext}. Formats acceptés: {supported}"
            raise ValueError(msg)

        return self.SUPPORTED_EXTENSIONS[ext]

    def is_supported(self, file_path: str | Path) -> bool:
        """Vérifie si le format de fichier est supporté.

        Args:
            file_path: Chemin vers le fichier.

        Returns:
            True si le format est supporté.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS

    def get_supported_extensions(self) -> list[str]:
        """Retourne la liste des extensions supportées.

        Returns:
            Liste des extensions (ex: ['.pdf', '.xlsx', '.xls', '.docx']).
        """
        return list(self.SUPPORTED_EXTENSIONS.keys())

    async def extract(self, file_path: str | Path) -> UnifiedDocument:
        """Extrait et unifie le contenu d'un document.

        Args:
            file_path: Chemin vers le document.

        Returns:
            UnifiedDocument prêt pour indexation.

        Raises:
            ValueError: Si le format n'est pas supporté ou l'extracteur n'est pas disponible.
            FileNotFoundError: Si le fichier n'existe pas.
        """
        path = Path(file_path)

        if not path.exists():
            msg = f"Fichier introuvable: {path}"
            raise FileNotFoundError(msg)

        doc_type = self.detect_type(path)

        if doc_type == DocumentType.PDF:
            return await self._extract_pdf(path)
        if doc_type == DocumentType.EXCEL:
            return await self._extract_excel(path)
        if doc_type == DocumentType.WORD:
            return await self._extract_word(path)

        msg = f"Type non géré: {doc_type}"
        raise ValueError(msg)

    async def _extract_pdf(self, path: Path) -> UnifiedDocument:
        """Extrait un PDF vers UnifiedDocument.

        Args:
            path: Chemin vers le fichier PDF.

        Returns:
            UnifiedDocument avec le contenu PDF.
        """
        # Import local: orchestrator depend de chunker qui peut creer un cycle.
        from src.services.pipeline.orchestrator import (  # noqa: PLC0415
            DocumentPipelineOrchestrator,
        )

        orchestrator = DocumentPipelineOrchestrator()
        await orchestrator.initialize()

        result = await orchestrator.process_document(str(path))

        # Convertir vers UnifiedDocument
        metadata = UnifiedMetadata(
            filename=path.name,
            file_path=str(path.absolute()),
            document_type=DocumentType.PDF,
            original_format=".pdf",
            page_count=result.total_pages if hasattr(result, "total_pages") else None,
            has_tables=result.has_tables if hasattr(result, "has_tables") else False,
            has_images=result.has_images if hasattr(result, "has_images") else False,
            has_ocr_content=result.ocr_applied if hasattr(result, "ocr_applied") else False,
        )

        content = ""
        if hasattr(result, "get_all_content_markdown"):
            content = result.get_all_content_markdown()
        elif hasattr(result, "content"):
            content = result.content

        return UnifiedDocument(
            metadata=metadata,
            content_markdown=content,
            structured_data=StructuredData(),
        )

    async def _extract_excel(self, path: Path) -> UnifiedDocument:
        """Extrait un Excel vers UnifiedDocument.

        Args:
            path: Chemin vers le fichier Excel.

        Returns:
            UnifiedDocument avec le contenu Excel.
        """
        excel_doc = await self._extractors[DocumentType.EXCEL].extract(path)
        tables = self._excel_tables(excel_doc)
        formulas = self._excel_formulas(excel_doc)

        metadata = UnifiedMetadata(
            filename=excel_doc.filename,
            file_path=excel_doc.file_path,
            file_hash=compute_file_hash(path),
            document_type=DocumentType.EXCEL,
            original_format=f".{excel_doc.format}",
            page_count=len(excel_doc.sheets),
            has_tables=len(tables) > 0,
            has_formulas=len(formulas) > 0,
            title=excel_doc.properties.get("title"),
            author=excel_doc.properties.get("author"),
            sheet_names=[s.name for s in excel_doc.sheets],
        )
        return UnifiedDocument(
            metadata=metadata,
            content_markdown=excel_doc.to_markdown(),
            structured_data=StructuredData(tables=tables, formulas=formulas),
        )

    async def _extract_word(self, path: Path) -> UnifiedDocument:
        """Extrait un Word vers UnifiedDocument.

        Args:
            path: Chemin vers le fichier Word.

        Returns:
            UnifiedDocument avec le contenu Word.
        """
        word_doc = await self._extractors[DocumentType.WORD].extract(path)
        tables = self._word_tables(word_doc)
        images = self._word_images(word_doc)

        metadata = UnifiedMetadata(
            filename=word_doc.filename,
            file_path=word_doc.file_path,
            file_hash=compute_file_hash(path),
            document_type=DocumentType.WORD,
            original_format=".docx",
            word_count=word_doc.word_count,
            has_tables=len(tables) > 0,
            has_images=len(images) > 0,
            title=word_doc.metadata.get("title"),
            author=word_doc.metadata.get("author"),
        )
        return UnifiedDocument(
            metadata=metadata,
            content_markdown=word_doc.to_markdown(),
            structured_data=StructuredData(tables=tables, images=images),
        )

    @staticmethod
    def _excel_tables(excel_doc: object) -> list[object]:
        """Convertit les tableaux d'un classeur Excel en UnifiedTableData."""
        return [
            UnifiedTableData(
                headers=table.headers,
                rows=table.data,
                source_location=f"Feuille: {sheet.name}",
            )
            for sheet in excel_doc.sheets  # type: ignore[attr-defined]
            for table in sheet.tables
        ]

    @staticmethod
    def _excel_formulas(excel_doc: object) -> list[object]:
        """Convertit les formules d'un classeur Excel en FormulaData."""
        return [
            FormulaData(
                cell=f.cell,
                sheet=f.sheet,
                formula=f.formula,
                result=f.result,
                dependencies=f.dependencies,
            )
            for f in excel_doc.get_all_formulas()  # type: ignore[attr-defined]
        ]

    @staticmethod
    def _word_tables(word_doc: object) -> list[object]:
        """Convertit les tableaux d'un document Word en UnifiedTableData."""
        result: list[object] = []
        for table in word_doc.tables:  # type: ignore[attr-defined]
            headers = table.headers or ([c.text for c in table.rows[0]] if table.rows else [])
            data_rows = table.rows[1:] if table.rows and not table.headers else table.rows
            result.append(
                UnifiedTableData(
                    headers=headers,
                    rows=[[c.text for c in row] for row in data_rows],
                )
            )
        return result

    @staticmethod
    def _word_images(word_doc: object) -> list[object]:
        """Convertit les images d'un document Word en UnifiedImageData."""
        return [
            UnifiedImageData(
                filename=img.filename,
                content_type=img.content_type,
                size_kb=img.size_kb,
                has_base64=True,
                alt_text=img.alt_text,
            )
            for img in word_doc.images  # type: ignore[attr-defined]
        ]
