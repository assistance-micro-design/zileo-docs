# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Authentification par API key pour les endpoints proteges."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.core.config import settings


_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Annotated[str | None, Security(_api_key_header)] = None,
) -> str | None:
    """Verifie la cle API si configuree.

    Args:
        api_key: Valeur du header X-API-Key.

    Returns:
        La cle API validee, ou None si pas d'auth configuree.

    Raises:
        HTTPException: Si la cle est manquante ou invalide.
    """
    if not settings.API_KEY:
        return None

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header required",
        )

    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


ApiKeyDep = Annotated[str | None, Depends(verify_api_key)]
