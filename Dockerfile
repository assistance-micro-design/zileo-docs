# syntax=docker/dockerfile:1

# =============================================================================
# MCP Zileo PDF - Dockerfile
# Multi-stage build pour une image optimisee
# =============================================================================

# --- Stage 1: Builder ---
FROM python:3.11-slim as builder

WORKDIR /app

# Installer les dependances systeme pour la compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dependances
COPY pyproject.toml README.md ./

# Installer les dependances dans un venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .


# --- Stage 2: Runtime ---
FROM python:3.11-slim as runtime

WORKDIR /app

# Labels
LABEL org.opencontainers.image.title="MCP Zileo PDF"
LABEL org.opencontainers.image.description="MCP Server for PDF processing with OCR and vector search"
LABEL org.opencontainers.image.version="0.1.0"

# Copier le venv du builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Variables d'environnement par defaut
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_NAME="MCP Zileo PDF" \
    APP_VERSION="0.1.0" \
    LOG_LEVEL="INFO" \
    LOG_FORMAT="json"

# Creer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copier le code source
COPY --chown=appuser:appuser src/ ./src/

# Changer vers l'utilisateur non-root
USER appuser

# Port expose
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Commande par defaut
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
