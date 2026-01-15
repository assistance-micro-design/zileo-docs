"""MCP Tools pour le traitement PDF.

Ce module expose les tools MCP disponibles pour le serveur.
"""

from src.mcp.tools.base import BaseMCPTool
from src.mcp.tools.delete_document import DeleteDocumentTool
from src.mcp.tools.get_document import GetDocumentTool
from src.mcp.tools.index_document import IndexDocumentTool
from src.mcp.tools.list_available_pdfs import ListAvailablePdfsTool
from src.mcp.tools.list_indexed_documents import ListIndexedDocumentsTool
from src.mcp.tools.read_document_content import ReadDocumentContentTool
from src.mcp.tools.search import SearchDocumentsTool


__all__ = [
    "BaseMCPTool",
    "DeleteDocumentTool",
    "GetDocumentTool",
    "IndexDocumentTool",
    "ListAvailablePdfsTool",
    "ListIndexedDocumentsTool",
    "ReadDocumentContentTool",
    "SearchDocumentsTool",
]
