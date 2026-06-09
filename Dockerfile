# syntax=docker/dockerfile:1

# =============================================================================
# Zileo Docs - Dockerfile
# Multi-stage build pour une image optimisee
# =============================================================================

# --- Stage 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Installer les dependances systeme pour la compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Installer uv (pin de version pour reproductibilite)
COPY --from=ghcr.io/astral-sh/uv:0.9.21 /uv /uvx /usr/local/bin/

# Copier les fichiers de dependances et le lockfile
COPY pyproject.toml uv.lock ./

# Installer uniquement les dependances depuis le lockfile (reproductible)
# --no-install-project: on ne package pas src/, le runtime stage copie src/ directement
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/opt/venv/bin:$PATH"


# --- Stage 2: Runtime ---
FROM python:3.11-slim AS runtime

WORKDIR /app

ARG APP_VERSION=0.4.0

# Labels
LABEL org.opencontainers.image.title="Zileo Docs"
LABEL org.opencontainers.image.description="MCP Server for document processing (PDF, Excel, Word) with OCR and vector search"
LABEL org.opencontainers.image.version="${APP_VERSION}"

# Copier le venv du builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Variables d'environnement par defaut
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_NAME="Zileo Docs" \
    APP_VERSION="${APP_VERSION}" \
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
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

# Commande par defaut
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
