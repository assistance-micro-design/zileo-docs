# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Types MCP pour le serveur JSON-RPC 2.0.

Ce module définit les types personnalisés utilisés par le serveur MCP,
notamment le type RequestId conforme à la spécification JSON-RPC 2.0.
"""

from __future__ import annotations

from typing import TypeAlias


# JSON-RPC 2.0 request identifier
# Selon la spec, l'id peut être:
# - String
# - Number (entier recommandé)
# - null (pour les notifications, mais non supporté dans notre implémentation)
# Référence: https://www.jsonrpc.org/specification#request_object
RequestId: TypeAlias = str | int | None
