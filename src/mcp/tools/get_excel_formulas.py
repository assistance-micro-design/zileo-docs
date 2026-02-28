# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour récupérer les formules d'un document Excel indexé."""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar

from src.core.exceptions import DocumentNotFoundError
from src.mcp.tools.base import VectorStoreMCPTool
from src.models.api import GetExcelFormulasParams


logger = logging.getLogger(__name__)


class GetExcelFormulasTool(VectorStoreMCPTool):
    """Récupère les formules d'un document Excel indexé.

    Permet d'obtenir la liste des formules Excel d'un document
    préalablement indexé, avec possibilité de filtrer par feuille
    ou plage de cellules.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = GetExcelFormulasTool()
        >>> await tool.initialize()
        >>> result = await tool.execute({"document_id": "doc-123"})
        >>> for f in result["formulas"]:
        ...     print(f"{f['sheet']}!{f['cell']}: {f['formula']}")
    """

    name: ClassVar[str] = "get_excel_formulas"
    description: ClassVar[str] = (
        "Récupère toutes les formules d'un document Excel indexé. "
        "Requiert: document Excel indexé via index_document. "
        "Retourne: liste des formules avec cellule, feuille, formule brute et résultat."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "ID du document Excel (retourné par index_document)",
            },
            "sheet": {
                "type": "string",
                "description": "Filtrer par nom de feuille (optionnel)",
            },
            "cell_range": {
                "type": "string",
                "description": "Filtrer par plage de cellules. Ex: 'A1:D10'",
            },
        },
        "required": ["document_id"],
    }

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Récupère les formules du document Excel.

        Args:
            arguments: Parametres validés par input_schema.

        Returns:
            Dictionnaire avec liste des formules.

        Raises:
            DocumentNotFoundError: Si le document n'existe pas.
        """
        params = GetExcelFormulasParams(**arguments)

        # Récupérer les chunks du document
        chunks = await self._vector_store.get_document_chunks(
            document_id=params.document_id,
        )

        if not chunks:
            raise DocumentNotFoundError(params.document_id)

        # Vérifier que c'est un document Excel
        doc_type = None
        for chunk in chunks:
            if "document_type" in chunk:
                doc_type = chunk["document_type"]
                break

        if doc_type and doc_type != "excel":
            return {
                "document_id": params.document_id,
                "error": f"Le document n'est pas un Excel (type: {doc_type})",
                "total_formulas": 0,
                "formulas": [],
            }

        # Extraire les formules des chunks
        formulas: list[dict[str, Any]] = []
        for chunk in chunks:
            # Chercher dans le payload des chunks avec formules
            if chunk.get("has_formula"):
                # Les formules sont stockées dans le contenu du chunk "formulas"
                content = chunk.get("content", "")
                if "# Formules Excel" in content:
                    parsed = self._parse_formulas_from_content(content, params.sheet)
                    formulas.extend(parsed)

        # Dédupliquer (une formule peut apparaître dans plusieurs chunks)
        unique_formulas = {f"{f['sheet']}!{f['cell']}": f for f in formulas}
        formula_list = list(unique_formulas.values())

        # Appliquer filtre cell_range si spécifié
        if params.cell_range:
            formula_list = self._filter_by_range(formula_list, params.cell_range)

        logger.info(
            "Récupéré %d formules pour document %s",
            len(formula_list),
            params.document_id,
        )

        return {
            "document_id": params.document_id,
            "total_formulas": len(formula_list),
            "formulas": formula_list,
        }

    def _parse_formulas_from_content(
        self,
        content: str,
        sheet_filter: str | None,
    ) -> list[dict[str, Any]]:
        """Parse les formules depuis le contenu Markdown.

        Args:
            content: Contenu Markdown du chunk formules.
            sheet_filter: Nom de feuille pour filtrer.

        Returns:
            Liste des formules parsées.
        """
        formulas: list[dict[str, Any]] = []
        # Format: - **Sheet!Cell**: `=FORMULA` = result
        pattern = r"- \*\*(.+?)!(.+?)\*\*: `(.+?)`(?: = (.+))?"

        for match in re.finditer(pattern, content):
            sheet = match.group(1)
            cell = match.group(2)
            formula = match.group(3)
            result = match.group(4)

            # Appliquer filtre feuille
            if sheet_filter and sheet != sheet_filter:
                continue

            formulas.append(
                {
                    "sheet": sheet,
                    "cell": cell,
                    "formula": formula,
                    "result": result,
                }
            )

        return formulas

    def _filter_by_range(
        self,
        formulas: list[dict[str, Any]],
        cell_range: str,
    ) -> list[dict[str, Any]]:
        """Filtre les formules par plage de cellules.

        Args:
            formulas: Liste des formules.
            cell_range: Plage au format 'A1:D10'.

        Returns:
            Formules dans la plage spécifiée.
        """
        # Parser la plage
        range_match = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", cell_range.upper())
        if not range_match:
            return formulas

        start_col = range_match.group(1)
        start_row = int(range_match.group(2))
        end_col = range_match.group(3)
        end_row = int(range_match.group(4))

        def col_to_num(col: str) -> int:
            """Convertit colonne lettre en nombre."""
            num = 0
            for c in col:
                num = num * 26 + (ord(c) - ord("A") + 1)
            return num

        start_col_num = col_to_num(start_col)
        end_col_num = col_to_num(end_col)

        filtered: list[dict[str, Any]] = []
        for f in formulas:
            cell_match = re.match(r"([A-Z]+)(\d+)", f["cell"].upper())
            if cell_match:
                col = cell_match.group(1)
                row = int(cell_match.group(2))
                col_num = col_to_num(col)

                if start_col_num <= col_num <= end_col_num and start_row <= row <= end_row:
                    filtered.append(f)

        return filtered
