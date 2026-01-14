# MCP Zileo PDF

Serveur MCP pour le traitement de documents PDF avec OCR et recherche vectorielle.

## Installation

```bash
pip install -e ".[dev]"
```

## Configuration

Copier `.env.example` vers `.env` et configurer les variables.

## Lancement

```bash
# Avec Docker
docker-compose up -d

# En local
uvicorn src.main:app --reload
```

## Tests

```bash
pytest tests/ -v
```
