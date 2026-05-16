# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour src/main.py: lifespan, /mcp endpoint, exception handler."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.core.exceptions import ZileoDocsError
from src.main import app, create_app, lifespan


@pytest.fixture
def test_client() -> TestClient:
    """TestClient FastAPI partage (le lifespan est execute via context manager)."""
    return TestClient(app)


@pytest.fixture
def mocked_mcp_server() -> Any:
    """Patch MCPServer pour que initialize() ne tente pas de se connecter a Qdrant.

    Necessaire depuis que le lifespan fail-fast sur init MCPServer:
    le vrai MCPServer.initialize() echoue hors container Docker.
    """
    mock_server = MagicMock()
    mock_server.initialize = AsyncMock()
    with patch("src.main.MCPServer", return_value=mock_server):
        yield mock_server


class TestLifespanStartup:
    """Tests pour le cycle de vie applicatif (lifespan)."""

    @pytest.mark.asyncio
    async def test_lifespan_attaches_mcp_server_to_app_state(self) -> None:
        """Au demarrage, lifespan instancie MCPServer et l'attache a app.state."""
        from src.main import MCPServer

        mock_server = MagicMock(spec=MCPServer)
        mock_server.initialize = AsyncMock()

        fake_app = MagicMock()
        fake_app.state = MagicMock()

        with patch("src.main.MCPServer", return_value=mock_server):
            async with lifespan(fake_app):
                assert fake_app.state.mcp_server is mock_server
                mock_server.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_refuses_production_without_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hors DEBUG et sans API_KEY, lifespan leve RuntimeError."""
        from src.main import settings

        monkeypatch.setattr(settings, "DEBUG", False)
        monkeypatch.setattr(settings, "API_KEY", "")

        fake_app = MagicMock()
        fake_app.state = MagicMock()

        with pytest.raises(RuntimeError, match="API_KEY non configuree"):
            async with lifespan(fake_app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_raises_on_mcp_init_failure(self) -> None:
        """Une exception dans MCPServer.initialize() doit faire echouer le lifespan (fail-fast)."""
        from src.main import MCPServer

        mock_server = MagicMock(spec=MCPServer)
        mock_server.initialize = AsyncMock(side_effect=RuntimeError("qdrant down"))

        fake_app = MagicMock()
        fake_app.state = MagicMock()

        with (
            patch("src.main.MCPServer", return_value=mock_server),
            pytest.raises(RuntimeError, match="qdrant down"),
        ):
            async with lifespan(fake_app):
                pass


@pytest.mark.usefixtures("mocked_mcp_server")
class TestMCPEndpoint:
    """Tests pour le endpoint POST /mcp."""

    def test_mcp_endpoint_uses_app_state_server(
        self, test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """/mcp delegue handle_request au server attache a app.state."""
        from src.main import settings

        monkeypatch.setattr(settings, "API_KEY", "")
        monkeypatch.setattr(settings, "DEBUG", True)

        mock_server = MagicMock()
        mock_server.handle_request = AsyncMock(
            return_value={"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        )

        with test_client:
            test_client.app.state.mcp_server = mock_server
            response = test_client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )

        assert response.status_code == 200
        assert response.json() == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        mock_server.handle_request.assert_awaited_once()

    def test_mcp_endpoint_rejects_body_above_cap(
        self, test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un body > MAX_MCP_BODY_MB est rejete via le header content-length."""
        from src.main import settings

        monkeypatch.setattr(settings, "API_KEY", "")
        monkeypatch.setattr(settings, "DEBUG", True)

        big_payload = {"jsonrpc": "2.0", "id": 1, "data": "x" * (1 * 1024 * 1024 + 100)}
        body = json.dumps(big_payload)

        with test_client:
            test_client.app.state.mcp_server = MagicMock()
            response = test_client.post(
                "/mcp",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body) * settings.MAX_MCP_BODY_MB + 1),
                },
            )

        payload = response.json()
        assert payload.get("error", {}).get("message") == "Body too large"

    def test_mcp_endpoint_returns_parse_error_on_invalid_json(
        self, test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un body non-JSON renvoie une erreur JSON-RPC -32700."""
        from src.main import settings

        monkeypatch.setattr(settings, "API_KEY", "")
        monkeypatch.setattr(settings, "DEBUG", True)

        with test_client:
            test_client.app.state.mcp_server = MagicMock()
            response = test_client.post(
                "/mcp",
                content="not-json",
                headers={"Content-Type": "application/json"},
            )

        body = response.json()
        assert body["error"]["code"] == -32700


@pytest.mark.usefixtures("mocked_mcp_server")
class TestExceptionHandler:
    """Tests pour le handler global ZileoDocsError -> 400 + to_dict()."""

    def test_zileo_docs_error_serialized_as_400(
        self, test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Une ZileoDocsError levee dans une route retourne 400 + to_dict()."""
        from src.main import settings

        monkeypatch.setattr(settings, "API_KEY", "")
        monkeypatch.setattr(settings, "DEBUG", True)

        # On ajoute une route de test qui leve une ZileoDocsError
        @test_client.app.get("/__test_error")
        async def _trigger() -> dict[str, str]:
            raise ZileoDocsError(message="boom", code="TEST_CODE")

        with test_client:
            response = test_client.get("/__test_error")

        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "TEST_CODE"
        assert body["message"] == "boom"


class TestCreateApp:
    """Tests pour la fabrique create_app()."""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """create_app() retourne une instance FastAPI."""
        from fastapi import FastAPI

        result = create_app()

        assert isinstance(result, FastAPI)


class TestCorsMiddleware:
    """Tests pour le middleware CORS (S1: actif en DEBUG, retire en prod)."""

    def test_cors_middleware_active_in_debug(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """En mode DEBUG, le middleware CORS est present dans la stack."""
        from fastapi.middleware.cors import CORSMiddleware

        from src.main import settings

        monkeypatch.setattr(settings, "DEBUG", True)
        monkeypatch.setattr(settings, "API_KEY", "")

        test_app = create_app()

        middleware_classes = [m.cls for m in test_app.user_middleware]
        assert CORSMiddleware in middleware_classes

    def test_cors_middleware_absent_in_prod(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Hors mode DEBUG, le middleware CORS est absent (pas mount)."""
        from fastapi.middleware.cors import CORSMiddleware

        from src.main import settings

        monkeypatch.setattr(settings, "DEBUG", False)
        monkeypatch.setattr(settings, "API_KEY", "fake-key")

        test_app = create_app()

        middleware_classes = [m.cls for m in test_app.user_middleware]
        assert CORSMiddleware not in middleware_classes
