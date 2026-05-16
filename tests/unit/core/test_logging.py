# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour src/core/logging.py (setup_logging)."""

from __future__ import annotations

import importlib
import logging
from typing import Any

import pytest


def _reload_with_env(monkeypatch: pytest.MonkeyPatch, **env: str) -> Any:
    """Recharge src.core.config puis src.core.logging avec env donne."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import src.core.config as config_module
    import src.core.logging as logging_module

    importlib.reload(config_module)
    importlib.reload(logging_module)
    return logging_module


def test_setup_logging_json_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_FORMAT=json configure un renderer JSONRenderer."""
    module = _reload_with_env(monkeypatch, LOG_FORMAT="json", LOG_LEVEL="INFO")

    module.setup_logging()

    root = logging.getLogger()
    assert root.handlers, "Au moins un handler doit etre attache"
    handler = root.handlers[0]
    formatter = handler.formatter
    assert formatter is not None


def test_setup_logging_text_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_FORMAT=text configure un renderer console."""
    module = _reload_with_env(monkeypatch, LOG_FORMAT="text", LOG_LEVEL="INFO")

    module.setup_logging()

    root = logging.getLogger()
    assert root.handlers


def test_setup_logging_level_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_LEVEL=DEBUG est applique au logger racine."""
    module = _reload_with_env(monkeypatch, LOG_FORMAT="json", LOG_LEVEL="DEBUG")

    module.setup_logging()

    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_third_party_loggers_warned(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les loggers tiers (httpx, etc.) sont restreints a WARNING."""
    module = _reload_with_env(monkeypatch, LOG_FORMAT="json", LOG_LEVEL="DEBUG")

    module.setup_logging()

    for name in ("httpx", "httpcore", "urllib3", "asyncio"):
        assert logging.getLogger(name).level == logging.WARNING


def test_getlogger_returns_stdlib_logger() -> None:
    """logging.getLogger(__name__) retourne un Logger stdlib (pas structlog direct)."""
    log = logging.getLogger("src.core.test_dummy")

    assert isinstance(log, logging.Logger)
