# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Instance partagee du rate limiter slowapi.

Une seule instance pour toute l'application : les routes declarent leurs
limites via @limiter.limit(...) et main.py l'enregistre dans app.state
pour le handler RateLimitExceeded.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address)
