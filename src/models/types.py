# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Types partagés pour éliminer Any (cf. project-patterns.yml)."""

from __future__ import annotations

from datetime import datetime
from typing import TypeAlias


# Valeur possible d'une cellule (Excel/Word table)
CellValue: TypeAlias = str | int | float | bool | datetime | None

# Résultat calculé d'une formule Excel
FormulaResult: TypeAlias = str | int | float | bool | None
