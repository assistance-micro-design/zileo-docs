# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Routes de health check pour l'API."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from qdrant_client import QdrantClient

from src.core.config import settings
from src.models.api import HealthResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check",
    description="Verifie l'etat de sante du service et de ses dependances.",
)
async def health_check() -> HealthResponse:
    """Verifie l'etat de sante du service.

    Returns:
        HealthResponse avec le statut de chaque composant.
    """
    # Verifier Qdrant
    qdrant_status = await _check_qdrant()

    # Verifier Mistral API (via cle API configuree)
    mistral_status = _check_mistral_config()

    # Determiner le statut global (guard clause - une seule condition)
    overall_status = _compute_health_status(qdrant_status, mistral_status)

    return HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        qdrant_status=qdrant_status,
        mistral_status=mistral_status,
    )


@router.get(
    "/live",
    summary="Liveness check",
    description="Verifie que le service est en vie (pour Kubernetes).",
)
async def liveness() -> dict[str, str]:
    """Liveness probe pour Kubernetes.

    Returns:
        Dictionnaire simple indiquant que le service est vivant.
    """
    return {"status": "alive"}


@router.get(
    "/ready",
    summary="Readiness check",
    description="Verifie que le service est pret a recevoir du trafic.",
)
async def readiness() -> dict[str, str]:
    """Readiness probe pour Kubernetes.

    Verifie que les dependances critiques sont accessibles.

    Returns:
        Dictionnaire avec le statut de readiness.
    """
    qdrant_status = await _check_qdrant()

    if qdrant_status == "healthy":
        return {"status": "ready"}
    return {"status": "not_ready", "reason": "qdrant_unavailable"}


def _compute_health_status(qdrant: str, mistral: str) -> str:
    """Calcule le statut global de sante.

    Args:
        qdrant: Statut Qdrant (healthy/unhealthy/unknown).
        mistral: Statut Mistral (healthy/unhealthy/unknown).

    Returns:
        Statut global: healthy ou degraded.
    """
    if "unhealthy" in (qdrant, mistral):
        return "degraded"
    return "healthy"


async def _check_qdrant() -> str:
    """Verifie la connexion a Qdrant.

    Returns:
        "healthy" si connecte, "unhealthy" sinon.
    """
    try:
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY,
        )
        await asyncio.to_thread(client.get_collections)
        return "healthy"
    except Exception as e:
        logger.warning("Qdrant health check failed: %s", e)
        return "unhealthy"


def _check_mistral_config() -> str:
    """Verifie que la configuration Mistral est presente.

    Returns:
        "healthy" si la cle API est configuree, "not_configured" sinon.
    """
    if settings.MISTRAL_API_KEY:
        return "healthy"
    return "not_configured"
