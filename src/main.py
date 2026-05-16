# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Point d'entree principal de l'application MCP Zileo RAG.

Ce module configure et lance le serveur FastAPI avec:
- API REST pour les documents et la recherche
- Serveur MCP pour l'integration avec Claude
- Health checks pour monitoring
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.auth import verify_api_key
from src.api.routes import documents, health, search
from src.core.config import settings
from src.core.exceptions import MCPZileoError
from src.core.logging import setup_logging
from src.mcp.server import MCPServer


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestion du cycle de vie de l'application.

    Initialise les services au demarrage et les nettoie a l'arret.

    Args:
        app: Instance FastAPI (l'instance MCPServer est attachee a app.state).

    Yields:
        None pendant l'execution de l'application.
    """
    # Startup
    logger.info(
        "Starting %s v%s",
        settings.APP_NAME,
        settings.APP_VERSION,
    )

    if settings.DEBUG:
        logger.warning("APPLICATION EN MODE DEBUG - NE PAS UTILISER EN PRODUCTION")

    if not settings.DEBUG and not settings.API_KEY:
        msg = "API_KEY non configuree en mode production: les endpoints proteges sont ouverts"
        raise RuntimeError(msg)

    # Instancier et initialiser le serveur MCP, l'attacher a app.state.
    # Fail-fast si l'init echoue: cohérent avec le RuntimeError sur API_KEY ci-dessus.
    mcp = MCPServer()
    await mcp.initialize()
    logger.info("MCP Server initialized successfully")
    app.state.mcp_server = mcp

    yield

    # Shutdown
    logger.info("Shutting down %s", settings.APP_NAME)


def create_app() -> FastAPI:
    """Cree et configure l'application FastAPI.

    Returns:
        Instance FastAPI configuree.
    """
    setup_logging()

    limiter = Limiter(key_func=get_remote_address)

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Serveur MCP pour l'extraction et la vectorisation de documents (PDF, Excel, Word). "
            "Expose une API REST et un serveur MCP JSON-RPC 2.0."
        ),
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    _configure_middleware(app, limiter)
    _register_routes(app, limiter)

    return app


def _configure_middleware(app: FastAPI, limiter: Limiter) -> None:
    """Configure les middlewares (rate limiting, CORS).

    CORS n'est monte qu'en mode DEBUG. En production, le serveur est destine
    a etre consomme par des clients backend (MCP, scripts), pas des navigateurs.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    if not settings.DEBUG:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-API-Key"],
    )


def _register_routes(app: FastAPI, limiter: Limiter) -> None:
    """Enregistre les routes API, MCP et les handlers d'erreur."""
    app.include_router(health.router)
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")

    @app.exception_handler(MCPZileoError)
    async def mcp_exception_handler(_request: Request, exc: MCPZileoError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=exc.to_dict())

    max_mcp_body_bytes = settings.MAX_MCP_BODY_MB * 1024 * 1024

    @app.post("/mcp", dependencies=[Depends(verify_api_key)])
    @limiter.limit(settings.RATE_LIMIT_MCP)  # type: ignore[untyped-decorator]
    async def mcp_endpoint(request: Request) -> dict[str, Any]:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_mcp_body_bytes:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Body too large"},
            }
        try:
            raw = await request.body()
            if len(raw) > max_mcp_body_bytes:
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Body too large"},
                }
            body = await request.json()
            mcp: MCPServer = request.app.state.mcp_server
            return await mcp.handle_request(body)
        except Exception as e:
            logger.exception("MCP request error: %s", e)
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs" if settings.DEBUG else "disabled",
            "health": "/health",
            "mcp": "/mcp",
        }


# Instance de l'application
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
