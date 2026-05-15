# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""MCP Tools pour le traitement de documents.

Ce module expose les tools MCP disponibles pour le serveur.
"""

from __future__ import annotations

from src.mcp.tools.base import BaseMCPTool
from src.mcp.tools.create_excel import CreateExcelTool
from src.mcp.tools.delete_document import DeleteDocumentTool
from src.mcp.tools.edit_excel import EditExcelTool
from src.mcp.tools.get_document import GetDocumentTool
from src.mcp.tools.get_excel_formulas import GetExcelFormulasTool
from src.mcp.tools.index_document import IndexDocumentTool
from src.mcp.tools.inspect_generated_file import InspectGeneratedFileTool
from src.mcp.tools.list_available_documents import ListAvailableDocumentsTool
from src.mcp.tools.list_indexed_documents import ListIndexedDocumentsTool
from src.mcp.tools.read_document_content import ReadDocumentContentTool
from src.mcp.tools.search_hybrid import SearchHybridTool
from src.mcp.tools.search_semantic import SearchSemanticTool


__all__ = [
    "BaseMCPTool",
    "CreateExcelTool",
    "DeleteDocumentTool",
    "EditExcelTool",
    "GetDocumentTool",
    "GetExcelFormulasTool",
    "IndexDocumentTool",
    "InspectGeneratedFileTool",
    "ListAvailableDocumentsTool",
    "ListIndexedDocumentsTool",
    "ReadDocumentContentTool",
    "SearchHybridTool",
    "SearchSemanticTool",
]
