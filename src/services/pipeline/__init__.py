# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Service d'orchestration du pipeline PDF.

Ce module contient l'orchestrateur qui coordonne les phases
d'analyse, extraction native et OCR.
"""

from __future__ import annotations

from src.services.pipeline.orchestrator import (
    DocumentPipelineOrchestrator,
    ProcessingResult,
)


__all__ = [
    "DocumentPipelineOrchestrator",
    "ProcessingResult",
]
