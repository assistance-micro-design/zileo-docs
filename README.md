# MCP Zileo RAG

Serveur MCP (Model Context Protocol) pour l'indexation, la recherche semantique et la generation de documents. Expose 13 outils via JSON-RPC 2.0 pour permettre a un LLM de chercher dans vos fichiers PDF, Excel et Word, et de creer/editer des fichiers Excel et PowerPoint.

> **Usage personnel uniquement** - Concu pour une utilisation locale via Docker. Aucune garantie pour un deploiement public. L'auteur decline toute responsabilite en cas d'exposition a Internet.

## Fonctionnement

1. Vous montez un dossier de documents dans le container Docker
2. Le LLM (Claude, etc.) appelle `index_document` pour extraire et vectoriser un fichier
3. Le contenu est decoupe en chunks, converti en embeddings via Mistral, et stocke dans Qdrant
4. Le LLM peut ensuite chercher dans les documents indexes via `search_documents`
5. Le LLM peut aussi creer et editer des fichiers Excel et PowerPoint via les outils de generation

## Formats supportes

| Format | Extensions | Bibliotheque | Remarques |
|--------|------------|--------------|-----------|
| PDF | `.pdf` | PyMuPDF4LLM + Mistral OCR | Texte natif ou OCR selon la page |
| Excel | `.xlsx` | openpyxl | Donnees, formules, styles |
| Excel legacy | `.xls` | xlrd | Donnees uniquement (pas de formules) |
| Word | `.docx` | docx2python | Texte, tableaux, images |
| PowerPoint | `.pptx` | python-pptx | Generation et edition uniquement (pas d'indexation) |

## Prerequis

- Docker et Docker Compose
- Une cle API Mistral (pour les embeddings et l'OCR)

## Installation

```bash
git clone <repository-url>
cd Mcp-Zileo-Rag
cp .env.example .env
# Editer .env : renseigner MISTRAL_API_KEY et DOCUMENTS_PATH
docker compose up -d
```

Verifier que le serveur fonctionne :

```bash
curl http://localhost:8000/health
# {"status": "healthy", ...}
```

## Configuration MCP

Le serveur MCP est accessible via l'endpoint `POST /mcp` (JSON-RPC 2.0 sur HTTP).

### Claude Desktop

Ajouter dans le fichier de configuration Claude Desktop :

| OS | Chemin |
|----|--------|
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

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

Redemarrer Claude Desktop apres modification. Les 13 outils apparaitront automatiquement dans l'interface.

### Zileo Chat

Ajouter dans la configuration MCP de Zileo Chat (`config.json` ou panneau de configuration) :

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

Si Zileo Chat et MCP Zileo RAG tournent dans le meme reseau Docker, utiliser le nom du service a la place de `localhost` :

```json
{
  "mcpServers": {
    "zileo-rag": {
      "url": "http://mcp-zileo-rag:8000/mcp",
      "transport": "http"
    }
  }
}
```

### Autres clients MCP

Tout client compatible MCP peut se connecter en HTTP Streamable vers `http://localhost:8000/mcp`. Le serveur implemente les methodes standard :

- `initialize` — Handshake et capabilities
- `tools/list` — Liste des 13 outils disponibles
- `tools/call` — Execution d'un outil

Le transport utilise HTTP POST avec des requetes JSON-RPC 2.0. Pas de SSE, pas de WebSocket.

## Outils MCP

### Indexation et recherche

| Outil | Description |
|-------|-------------|
| `index_document` | Extraire et indexer un PDF, Excel ou Word dans Qdrant |
| `search_documents` | Recherche semantique dans les documents indexes |
| `get_document` | Recuperer les metadonnees et chunks d'un document |
| `delete_document` | Supprimer un document de l'index (pas le fichier source) |
| `list_indexed_documents` | Lister les documents deja indexes |
| `read_document_content` | Lire le contenu Markdown reconstitue d'un document |
| `get_excel_formulas` | Recuperer les formules d'un fichier Excel indexe |

### Generation et edition

| Outil | Description |
|-------|-------------|
| `create_excel_document` | Creer un fichier Excel (.xlsx) avec donnees, styles, graphiques |
| `edit_excel_document` | Editer un fichier Excel existant (13 operations) |
| `create_presentation` | Creer un fichier PowerPoint (.pptx) avec 8 layouts |
| `edit_presentation` | Editer un fichier PowerPoint existant (11 operations) |

### Utilitaires

| Outil | Description |
|-------|-------------|
| `list_available_documents` | Lister les fichiers disponibles (4 sources : documents, generated, templates, images) |
| `inspect_generated_file` | Inspecter la structure d'un Excel ou PowerPoint genere |

## Configuration

Variables d'environnement principales (voir [docs/configuration.md](docs/configuration.md) pour la liste complete) :

| Variable | Requis | Description |
|----------|--------|-------------|
| `MISTRAL_API_KEY` | Oui | Cle API Mistral (embeddings + OCR) |
| `DOCUMENTS_PATH` | Oui | Chemin local vers vos documents |
| `OUTPUT_PATH` | Non | Dossier de sortie des fichiers generes (defaut: `./output`) |
| `TEMPLATES_PPTX_PATH` | Non | Dossier des templates PowerPoint |
| `IMAGES_POWERPOINT_PATH` | Non | Dossier des images pour les slides |
| `QDRANT_HOST` | Non | Hote Qdrant (defaut: `localhost`, `qdrant` en Docker) |
| `DEBUG` | Non | Active Swagger UI et CORS (defaut: `false`) |

## Developpement local

```bash
pip install -e ".[dev]"
docker compose up -d qdrant   # Qdrant seul
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
  main.py              # FastAPI app + endpoint /mcp
  core/                # Config, exceptions, logging
  api/routes/          # Endpoints REST (health, documents, search)
  mcp/
    server.py          # Routeur JSON-RPC 2.0
    tools/             # 13 outils MCP
  services/
    pdf/               # Analyse, extraction native, OCR Mistral
    excel/             # Extraction + generation + edition
    word/              # Extraction docx2python
    presentation/      # Generation + edition PowerPoint
    inspection/        # Inspection fichiers generes
    document/          # Routeur multi-format
    chunking/          # Decoupage en chunks
    embedding/         # Embeddings Mistral (1024 dim)
    vector/            # Stockage Qdrant
  models/              # Schemas Pydantic
```

## Documentation

- [Configuration clients MCP](docs/mcp-client-setup.md) — Claude Desktop, Zileo Chat, autres clients
- [Architecture](docs/architecture.md) — Pipeline de traitement et composants
- [Reference API](docs/api-reference.md) — Endpoints REST et outils MCP
- [Configuration](docs/configuration.md) — Variables d'environnement
- [Deploiement](docs/deployment.md) — Docker et developpement local
- [Multi-format](docs/multi-format.md) — Support Excel, Word et PowerPoint
- [Code style](docs/code-style.md) — Conventions de code

## Licence

AGPL-3.0-or-later
