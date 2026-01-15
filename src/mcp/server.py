"""Serveur MCP (Model Context Protocol) pour le traitement PDF.

Ce module implemente un serveur MCP compatible JSON-RPC 2.0 qui expose
les outils de traitement PDF aux clients MCP (Claude, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from src.core.config import settings
from src.core.exceptions import MCPZileoPDFError
from src.mcp.tools.base import BaseMCPTool
from src.mcp.tools.delete_document import DeleteDocumentTool
from src.mcp.tools.get_document import GetDocumentTool
from src.mcp.tools.get_excel_formulas import GetExcelFormulasTool
from src.mcp.tools.index_document import IndexDocumentTool
from src.mcp.tools.list_available_documents import ListAvailableDocumentsTool
from src.mcp.tools.list_available_pdfs import ListAvailablePdfsTool
from src.mcp.tools.list_indexed_documents import ListIndexedDocumentsTool
from src.mcp.tools.read_document_content import ReadDocumentContentTool
from src.mcp.tools.search import SearchDocumentsTool
from src.mcp.types import RequestId
from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.vector.qdrant_store import QdrantVectorStore


logger = logging.getLogger(__name__)


def _format_tool_error(error: Exception) -> str:
    """Formate une erreur pour reponse MCP.

    Args:
        error: Exception a formater.

    Returns:
        Texte d'erreur formate pour le LLM.
    """
    if isinstance(error, MCPZileoPDFError):
        return error.to_llm_format()
    return (
        f"ERROR [INTERNAL_ERROR]: {error!s}\n"
        "SUGGESTION: Erreur inattendue. Reessayer ou contacter le support."
    )


class MCPServer:
    """Serveur MCP pour le traitement de documents PDF.

    Ce serveur expose des outils MCP via le protocole JSON-RPC 2.0:
    - index_document: Extraire et indexer un PDF dans la base vectorielle
    - search_documents: Recherche semantique dans les documents indexes
    - get_document: Obtenir les informations d'un document indexe
    - delete_document: Supprimer un document de l'index vectoriel
    - list_indexed_documents: Lister tous les documents indexes
    - list_available_pdfs: Lister les fichiers PDF disponibles (deprecated)
    - list_available_documents: Lister tous les documents disponibles (PDF/Excel/Word)
    - get_excel_formulas: Récupérer les formules d'un document Excel indexé
    - read_document_content: Lire le contenu Markdown complet d'un document

    Attributes:
        name: Nom du serveur MCP.
        version: Version du serveur.
        tools: Dictionnaire des outils disponibles.

    Example:
        >>> server = MCPServer()
        >>> await server.initialize()
        >>> result = await server.handle_request(
        ...     {
        ...         "jsonrpc": "2.0",
        ...         "method": "tools/call",
        ...         "params": {"name": "index_document", "arguments": {"file_path": "doc.pdf"}},
        ...         "id": 1,
        ...     }
        ... )
    """

    def __init__(self) -> None:
        """Initialise le serveur MCP avec injection de dependances."""
        self.name = settings.APP_NAME
        self.version = settings.APP_VERSION
        self._initialized = False

        # Dependances partagees (Refactoring #3: DI)
        self._shared_vector_store = QdrantVectorStore()
        self._shared_embedder = MistralEmbedder()

        # Instancier les tools avec injection de dependances
        self._index_document = IndexDocumentTool()
        self._search_documents = SearchDocumentsTool(
            vector_store=self._shared_vector_store,
            embedder=self._shared_embedder,
        )
        self._get_document = GetDocumentTool(
            vector_store=self._shared_vector_store,
        )
        self._delete_document = DeleteDocumentTool(
            vector_store=self._shared_vector_store,
        )
        self._list_indexed_documents = ListIndexedDocumentsTool(
            vector_store=self._shared_vector_store,
        )
        self._list_available_pdfs = ListAvailablePdfsTool()
        self._list_available_documents = ListAvailableDocumentsTool()
        self._get_excel_formulas = GetExcelFormulasTool(
            vector_store=self._shared_vector_store,
        )
        self._read_document_content = ReadDocumentContentTool(
            vector_store=self._shared_vector_store,
        )

        # Registry des tools
        self.tools: dict[str, BaseMCPTool] = {
            "index_document": self._index_document,
            "search_documents": self._search_documents,
            "get_document": self._get_document,
            "delete_document": self._delete_document,
            "list_indexed_documents": self._list_indexed_documents,
            "list_available_pdfs": self._list_available_pdfs,
            "list_available_documents": self._list_available_documents,
            "get_excel_formulas": self._get_excel_formulas,
            "read_document_content": self._read_document_content,
        }

        # Refactoring #5: Routing optimise (defini une seule fois)
        self._method_handlers: dict[
            str, Callable[[RequestId, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]
        ] = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
        }

        logger.info(
            "MCP Server initialise: %s v%s (%d tools)",
            self.name,
            self.version,
            len(self.tools),
        )

    async def initialize(self) -> None:
        """Initialise tous les tools en parallele.

        Refactoring #2: Utilise asyncio.gather pour l'initialisation parallele.
        Doit etre appele avant de traiter des requetes pour
        s'assurer que les connexions aux services externes sont etablies.
        """
        if not self._initialized:
            await asyncio.gather(*(tool.initialize() for tool in self.tools.values()))
            self._initialized = True
            logger.info("MCP Server services initialized")

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Traite une requete JSON-RPC 2.0.

        Args:
            request: Requete JSON-RPC 2.0 avec:
                - jsonrpc: "2.0"
                - method: Methode a appeler
                - params: Parametres de la methode
                - id: Identifiant de la requete

        Returns:
            Reponse JSON-RPC 2.0.

        Example:
            >>> response = await server.handle_request(
            ...     {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
            ... )
        """
        request_id = request.get("id")
        method = request.get("method", "")

        try:
            # Validation JSON-RPC et routing
            return await self._route_request(request_id, method, request)
        except Exception as e:
            logger.exception("Error handling MCP request: %s", e)
            return self._error_response(
                request_id,
                -32603,
                f"Internal error: {e!s}",
            )

    async def _route_request(
        self,
        request_id: RequestId,
        method: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Route la requete vers le handler approprie.

        Refactoring #5: Utilise le dictionnaire de handlers predefini.

        Args:
            request_id: ID de la requete.
            method: Methode a appeler.
            request: Requete complete.

        Returns:
            Reponse JSON-RPC 2.0.
        """
        # Validation JSON-RPC
        if request.get("jsonrpc") != "2.0":
            return self._error_response(
                request_id,
                -32600,
                "Invalid Request: jsonrpc must be '2.0'",
            )

        if not method:
            return self._error_response(
                request_id,
                -32600,
                "Invalid Request: method is required",
            )

        # Router la requete via le dictionnaire predefini
        handler = self._method_handlers.get(method)
        if handler:
            return await handler(request_id, request.get("params", {}))

        return self._error_response(
            request_id,
            -32601,
            f"Method not found: {method}",
        )

    async def _handle_initialize(
        self,
        request_id: RequestId,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        """Gere la requete d'initialisation MCP.

        Args:
            request_id: ID de la requete.
            _params: Parametres d'initialisation (non utilises).

        Returns:
            Reponse avec les capabilities du serveur.
        """
        await self.initialize()

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
                "capabilities": {
                    "tools": {
                        "listChanged": False,
                    },
                },
            },
        }

    async def _handle_tools_list(
        self,
        request_id: RequestId,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        """Gere la requete de liste des tools.

        Args:
            request_id: ID de la requete.
            _params: Parametres (non utilises).

        Returns:
            Liste des tools disponibles avec leurs schemas.
        """
        tools_list = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in self.tools.values()
        ]

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools_list,
            },
        }

    async def _handle_tools_call(
        self,
        request_id: RequestId,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Gere l'appel d'un tool.

        Args:
            request_id: ID de la requete.
            params: Parametres avec 'name' et 'arguments'.

        Returns:
            Resultat de l'execution du tool.
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return self._error_response(
                request_id,
                -32602,
                "Invalid params: tool name is required",
            )

        if tool_name not in self.tools:
            return self._error_response(
                request_id,
                -32602,
                f"Unknown tool: {tool_name}",
            )

        try:
            tool = self.tools[tool_name]
            result = await tool.execute(arguments)

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": self._format_result(result),
                        }
                    ],
                },
            }

        except (MCPZileoPDFError, Exception) as e:
            # Refactoring #6: Formatage d'erreur extrait
            return self._tool_error_response(request_id, e)

    def _tool_error_response(
        self,
        request_id: RequestId,
        error: Exception,
    ) -> dict[str, Any]:
        """Construit une reponse d'erreur pour un tool MCP.

        Refactoring #6: Methode extraite pour le formatage d'erreurs.

        Args:
            request_id: ID de la requete.
            error: Exception levee.

        Returns:
            Reponse JSON-RPC avec isError=True.
        """
        # Logging: ternaire pour selectionner la fonction de log
        log_func = (
            logger.warning if isinstance(error, MCPZileoPDFError) else logger.exception
        )
        log_func("Tool error: %s", error)

        # Formatage: helper pour separer les responsabilites
        error_text = _format_tool_error(error)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": error_text,
                    }
                ],
                "isError": True,
            },
        }

    def _error_response(
        self,
        request_id: RequestId,
        code: int,
        message: str,
    ) -> dict[str, Any]:
        """Construit une reponse d'erreur JSON-RPC.

        Args:
            request_id: ID de la requete.
            code: Code d'erreur JSON-RPC.
            message: Message d'erreur.

        Returns:
            Reponse d'erreur JSON-RPC.
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def _format_result(self, result: dict[str, Any]) -> str:
        """Formate le resultat pour la reponse MCP.

        Args:
            result: Resultat a formater.

        Returns:
            Resultat formate en string JSON ou texte.
        """
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)


# Instance globale du serveur
mcp_server = MCPServer()
