# MCP Zileo RAG

Serveur MCP (Model Context Protocol) pour l'indexation et la recherche semantique de documents. Expose 8 outils via JSON-RPC 2.0 pour permettre a un LLM de chercher dans vos fichiers PDF, Excel et Word.

> **Usage personnel uniquement** - Concu pour une utilisation locale via Docker. Aucune garantie pour un deploiement public. L'auteur decline toute responsabilite en cas d'exposition a Internet.

## Fonctionnement

1. Vous montez un dossier de documents dans le container Docker
2. Le LLM (Claude, etc.) appelle `index_document` pour extraire et vectoriser un fichier
3. Le contenu est decoupe en chunks, converti en embeddings via Mistral, et stocke dans Qdrant
4. Le LLM peut ensuite chercher dans les documents indexes via `search_documents`

## Formats supportes

| Format | Extensions | Bibliotheque | Remarques |
|--------|------------|--------------|-----------|
| PDF | `.pdf` | PyMuPDF4LLM + Mistral OCR | Texte natif ou OCR selon la page |
| Excel | `.xlsx` | openpyxl | Donnees, formules, styles |
| Excel legacy | `.xls` | xlrd | Donnees uniquement (pas de formules) |
| Word | `.docx` | docx2python | Texte, tableaux, images |

Le support multi-format (Excel, Word) a ete ajoute apres le PDF. Le PDF est le format le plus teste.

## Prerequis

- Docker et Docker Compose
- Une cle API Mistral (pour les embeddings et l'OCR)

## Installation

```bash
cp .env.example .env
# Editer .env : renseigner MISTRAL_API_KEY et DOCUMENTS_PATH
docker-compose up -d
```

Verifier que le serveur fonctionne :

```bash
curl http://localhost:8000/health
```

## Configuration MCP pour Claude Desktop

Ajouter dans le fichier de configuration Claude Desktop :

- Linux : `~/.config/Claude/claude_desktop_config.json`
- macOS : `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows : `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "zileo-rag": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

Redemarrer Claude Desktop apres modification.

## Outils MCP

| Outil | Description |
|-------|-------------|
| `index_document` | Extraire et indexer un document dans Qdrant |
| `search_documents` | Recherche semantique dans les documents indexes |
| `get_document` | Recuperer les metadonnees et chunks d'un document |
| `delete_document` | Supprimer un document de l'index (pas le fichier source) |
| `list_indexed_documents` | Lister les documents deja indexes |
| `list_available_documents` | Lister les fichiers disponibles dans le dossier monte |
| `read_document_content` | Lire le contenu Markdown reconstitue d'un document |
| `get_excel_formulas` | Recuperer les formules d'un fichier Excel indexe |

## Configuration

Variables d'environnement principales (voir [docs/configuration.md](docs/configuration.md) pour la liste complete) :

| Variable | Requis | Description |
|----------|--------|-------------|
| `MISTRAL_API_KEY` | Oui | Cle API Mistral (embeddings + OCR) |
| `DOCUMENTS_PATH` | Oui | Chemin local vers vos documents |
| `QDRANT_HOST` | Non | Hote Qdrant (defaut: `localhost`, `qdrant` en Docker) |
| `DEBUG` | Non | Active Swagger UI et CORS (defaut: `false`) |

## Developpement local

```bash
pip install -e ".[dev]"
docker-compose up -d qdrant   # Qdrant seul
uvicorn src.main:app --reload
```

## Tests

```bash
pytest tests/unit/ -v          # Tests unitaires
pytest tests/integration/ -v   # Necessite Qdrant
pytest tests/e2e/ -v           # Pipeline complet
```

## Validation

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest --cov=src --cov-fail-under=80
```

## Architecture

```
src/
  main.py           # FastAPI app + endpoint /mcp
  core/             # Config, exceptions, logging
  api/routes/       # Endpoints REST (health, documents, search)
  mcp/
    server.py       # Routeur JSON-RPC 2.0
    tools/          # 8 outils MCP
  services/
    pdf/            # Analyse, extraction native, OCR Mistral
    excel/          # Extraction openpyxl/xlrd
    word/           # Extraction docx2python
    document/       # Routeur multi-format
    chunking/       # Decoupage en chunks
    embedding/      # Embeddings Mistral (1024 dim)
    vector/         # Stockage Qdrant
  models/           # Schemas Pydantic
```

## Documentation

- [Architecture](docs/architecture.md) - Pipeline de traitement et composants
- [Reference API](docs/api-reference.md) - Endpoints REST et outils MCP
- [Configuration](docs/configuration.md) - Variables d'environnement
- [Deploiement](docs/deployment.md) - Docker et developpement local
- [Multi-format](docs/multi-format.md) - Support Excel et Word
- [Code style](docs/code-style.md) - Conventions de code

## Licence

AGPL-3.0-or-later
