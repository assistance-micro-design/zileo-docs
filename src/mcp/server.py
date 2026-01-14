"""Serveur MCP (Model Context Protocol) pour le traitement PDF.

Ce module implemente un serveur MCP compatible JSON-RPC 2.0 qui expose
les outils de traitement PDF aux clients MCP (Claude, etc.).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.core.config import settings
from src.core.exceptions import MCPZileoPDFError
from src.mcp.tools.get_document import GetDocumentTool
from src.mcp.tools.index_document import IndexDocumentTool
from src.mcp.tools.search import SearchDocumentsTool


logger = logging.getLogger(__name__)


class MCPServer:
    """Serveur MCP pour le traitement de documents PDF.

    Ce serveur expose des outils MCP via le protocole JSON-RPC 2.0:
    - index_document: Extraire et indexer un PDF dans la base vectorielle
    - search_documents: Recherche semantique dans les documents indexes
    - get_document: Obtenir les informations d'un document indexe

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
        """Initialise le serveur MCP."""
        self.name = settings.APP_NAME
        self.version = settings.APP_VERSION
        self._initialized = False

        # Instancier les tools
        self._index_document = IndexDocumentTool()
        self._search_documents = SearchDocumentsTool()
        self._get_document = GetDocumentTool()

        # Registry des tools
        self.tools: dict[str, Any] = {
            "index_document": self._index_document,
            "search_documents": self._search_documents,
            "get_document": self._get_document,
        }

        logger.info(
            "MCP Server initialise: %s v%s (%d tools)",
            self.name,
            self.version,
            len(self.tools),
        )

    async def initialize(self) -> None:
        """Initialise les services dependants.

        Doit etre appele avant de traiter des requetes pour
        s'assurer que les connexions aux services externes sont etablies.
        """
        if not self._initialized:
            await self._index_document.initialize()
            await self._search_documents.initialize()
            await self._get_document.initialize()
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
        request_id: Any,
        method: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Route la requete vers le handler approprie.

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

        # Router la requete
        handlers: dict[str, Any] = {
            "initialize": lambda: self._handle_initialize(request_id, request.get("params", {})),
            "tools/list": lambda: self._handle_tools_list(request_id),
            "tools/call": lambda: self._handle_tools_call(request_id, request.get("params", {})),
        }

        handler = handlers.get(method)
        if handler:
            result: dict[str, Any] = await handler()
            return result

        return self._error_response(
            request_id,
            -32601,
            f"Method not found: {method}",
        )

    async def _handle_initialize(
        self,
        request_id: Any,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        """Gere la requete d'initialisation MCP.

        Args:
            request_id: ID de la requete.
            params: Parametres d'initialisation.

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

    async def _handle_tools_list(self, request_id: Any) -> dict[str, Any]:
        """Gere la requete de liste des tools.

        Args:
            request_id: ID de la requete.

        Returns:
            Liste des tools disponibles avec leurs schemas.
        """
        tools_list = []

        for tool in self.tools.values():
            tools_list.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
            )

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools_list,
            },
        }

    async def _handle_tools_call(
        self,
        request_id: Any,
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

        except MCPZileoPDFError as e:
            # Erreur applicative avec suggestion pour le LLM
            logger.warning("Tool error: %s", e)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": e.to_llm_format(),
                        }
                    ],
                    "isError": True,
                },
            }
        except Exception as e:
            # Erreur inattendue
            logger.exception("Tool execution error: %s", e)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"ERROR [INTERNAL_ERROR]: {e!s}\n"
                                "SUGGESTION: Erreur inattendue. Reessayer ou contacter le support."
                            ),
                        }
                    ],
                    "isError": True,
                },
            }

    def _error_response(
        self,
        request_id: Any,
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
