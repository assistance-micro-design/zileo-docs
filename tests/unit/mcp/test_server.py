# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour MCPServer (routing JSON-RPC 2.0)."""

from __future__ import annotations

import pytest

from src.mcp.server import MCPServer


@pytest.fixture
def server() -> MCPServer:
    """Instance MCPServer fraichement construite (sans initialize)."""
    return MCPServer()


class TestJsonRpcValidation:
    """Tests des codes d'erreur JSON-RPC standards."""

    @pytest.mark.asyncio
    async def test_rejects_missing_jsonrpc_field(self, server: MCPServer) -> None:
        response = await server.handle_request({"method": "tools/list", "id": 1})
        assert response["error"]["code"] == -32600
        assert "jsonrpc" in response["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_rejects_wrong_jsonrpc_version(self, server: MCPServer) -> None:
        response = await server.handle_request({"jsonrpc": "1.0", "method": "tools/list", "id": 1})
        assert response["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_rejects_missing_method(self, server: MCPServer) -> None:
        response = await server.handle_request({"jsonrpc": "2.0", "id": 1})
        assert response["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_rejects_unknown_method(self, server: MCPServer) -> None:
        response = await server.handle_request(
            {"jsonrpc": "2.0", "method": "unknown/method", "id": 1}
        )
        assert response["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_rejects_unknown_tool(self, server: MCPServer) -> None:
        response = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 1,
                "params": {"name": "no_such_tool", "arguments": {}},
            }
        )
        assert response["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_rejects_tools_call_without_name(self, server: MCPServer) -> None:
        response = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 1,
                "params": {"arguments": {}},
            }
        )
        assert response["error"]["code"] == -32602


class TestToolsList:
    """Test que tools/list retourne le registre attendu."""

    @pytest.mark.asyncio
    async def test_returns_all_registered_tools(self, server: MCPServer) -> None:
        response = await server.handle_request({"jsonrpc": "2.0", "method": "tools/list", "id": 42})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 42
        names = {t["name"] for t in response["result"]["tools"]}
        # 13 tools attendus dans l'inventory (search splitte en hybrid + semantic)
        assert len(names) == 13
        assert "search_hybrid" in names
        assert "search_semantic" in names
        assert "index_document" in names


class TestServerRegistry:
    """Test que les helpers de construction restent coherents."""

    def test_build_tools_returns_13_entries(self, server: MCPServer) -> None:
        assert len(server.tools) == 13

    def test_method_handlers_cover_initialize_list_call(self, server: MCPServer) -> None:
        assert set(server._method_handlers.keys()) == {
            "initialize",
            "tools/list",
            "tools/call",
        }
