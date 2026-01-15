# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Classe de base abstraite pour les tools MCP.

Ce module fournit une classe de base qui standardise le comportement
de tous les tools MCP du serveur Zileo PDF.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class BaseMCPTool(ABC):
    """Classe de base pour tous les tools MCP.

    Fournit:
    - Structure commune (name, description, input_schema)
    - Gestion de l'initialisation lazy
    - Pattern template method pour execute()

    Les sous-classes doivent implementer:
    - _do_initialize(): Initialisation specifique au tool
    - _do_execute(): Logique d'execution du tool

    Attributes:
        name: Nom unique du tool MCP.
        description: Description pour le LLM.
        input_schema: Schema JSON des parametres.

    Example:
        >>> class MyTool(BaseMCPTool):
        ...     name = "my_tool"
        ...     description = "Description du tool"
        ...     input_schema = {"type": "object", "properties": {}}
        ...
        ...     async def _do_initialize(self) -> None:
        ...         # Initialiser les dependances
        ...         pass
        ...
        ...     async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        ...         return {"result": "ok"}
    """

    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]

    def __init__(self) -> None:
        """Initialise le tool avec l'etat non-initialise."""
        self._initialized = False

    @abstractmethod
    async def _do_initialize(self) -> None:
        """Hook pour l'initialisation specifique au tool.

        A implementer par les sous-classes pour initialiser
        leurs dependances (vector store, embedder, etc.).
        """

    async def initialize(self) -> None:
        """Initialise le tool si necessaire.

        Pattern idempotent: peut etre appele plusieurs fois
        sans effet de bord.
        """
        if not self._initialized:
            await self._do_initialize()
            self._initialized = True

    async def _ensure_initialized(self) -> None:
        """S'assure que le tool est initialise avant execution."""
        if not self._initialized:
            await self.initialize()

    @abstractmethod
    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Logique d'execution specifique au tool.

        Args:
            arguments: Parametres valides du tool.

        Returns:
            Resultat de l'execution.
        """

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute le tool avec initialisation automatique.

        Args:
            arguments: Parametres du tool.

        Returns:
            Resultat de l'execution.
        """
        await self._ensure_initialized()
        return await self._do_execute(arguments)
