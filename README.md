# MCP Zileo RAG

[![Version](https://img.shields.io/badge/version-0.2.0-orange)](https://github.com/assistance-micro-design/mcp-zileo-rag)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-beta-yellow)](https://github.com/assistance-micro-design/mcp-zileo-rag)

> Serveur MCP (Model Context Protocol) pour l'indexation, la recherche semantique et la generation de documents. Expose 12 outils via JSON-RPC 2.0 pour permettre a un LLM de chercher dans vos fichiers PDF, Excel et Word, et de creer/editer des fichiers Excel et Word.

**Developed by** [Assistance Micro Design](https://www.assistancemicrodesign.net/)

**Built with** [Claude Code](https://claude.com/claude-code) by Anthropic

---

> **Usage personnel uniquement** - Concu pour une utilisation locale via Docker. Aucune garantie pour un deploiement public. L'auteur decline toute responsabilite en cas d'exposition a Internet.

## Fonctionnement

1. Vous montez un dossier de documents dans le container Docker
2. Le LLM (Claude, etc.) appelle `index_document` pour extraire et vectoriser un fichier
3. Le contenu est decoupe en chunks, converti en embeddings via Mistral, et stocke dans Qdrant
4. Le LLM peut ensuite chercher dans les documents indexes via `search_hybrid` (defaut) ou `search_semantic` (cosinus pur)
5. Le LLM peut aussi creer et editer des fichiers Excel via les outils de generation

## Formats supportes

| Format | Extensions | Bibliotheque | Remarques |
|--------|------------|--------------|-----------|
| PDF | `.pdf` | PyMuPDF4LLM + Mistral OCR | Texte natif ou OCR selon la page |
| Excel | `.xlsx` | openpyxl | Donnees, formules, styles |
| Excel legacy | `.xls` | xlrd | Donnees uniquement (pas de formules) |
| Word | `.docx` | docx2python | Texte, tableaux, images |

## Prerequis

- Docker et Docker Compose
- Une cle API Mistral (pour les embeddings et l'OCR)

## Installation

```bash
git clone https://github.com/assistance-micro-design/mcp-zileo-rag.git
cd mcp-zileo-rag
cp .env.example .env

# Editer .env : renseigner MISTRAL_API_KEY, DOCUMENTS_PATH
# Generer une cle API pour proteger le serveur :
echo "API_KEY=$(openssl rand -hex 32)" >> .env

docker compose up -d
```

> **Note sur `API_KEY`** : la cle protege les endpoints `/api/v1/*`, `/mcp` et `/health`. Hors mode `DEBUG=true`, le serveur refuse de demarrer si la cle est vide. Voir [docs/mcp-client-setup.md](docs/mcp-client-setup.md#authentification) pour la passer aux clients MCP.

Verifier que le serveur fonctionne :

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/health
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
      "transport": "http",
      "headers": {
        "X-API-Key": "ta_cle_api_ici"
      }
    }
  }
}
```

Remplacer `ta_cle_api_ici` par la valeur de `API_KEY` definie dans `.env`. Redemarrer Claude Desktop apres modification. Les 12 outils apparaitront automatiquement dans l'interface.

### Zileo Chat

Ajouter dans la configuration MCP de Zileo Chat (`config.json` ou panneau de configuration) :

```json
{
  "mcpServers": {
    "zileo-rag": {
      "url": "http://localhost:8000/mcp",
      "transport": "http",
      "headers": {
        "X-API-Key": "ta_cle_api_ici"
      }
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
      "transport": "http",
      "headers": {
        "X-API-Key": "ta_cle_api_ici"
      }
    }
  }
}
```

### Autres clients MCP

Tout client compatible MCP peut se connecter en HTTP Streamable vers `http://localhost:8000/mcp`. Le serveur implemente les methodes standard :

- `initialize` — Handshake et capabilities
- `tools/list` — Liste des 12 outils disponibles
- `tools/call` — Execution d'un outil

Le transport utilise HTTP POST avec des requetes JSON-RPC 2.0. Pas de SSE, pas de WebSocket.

## Outils MCP

### Indexation et recherche

| Outil | Description |
|-------|-------------|
| `index_document` | Extraire et indexer un PDF, Excel ou Word dans Qdrant |
| `search_hybrid` | Recherche hybride (dense + BM25 RRF) avec garde-fou cosinus anti hors-domaine |
| `search_semantic` | Recherche semantique pure (cosinus dense, defaut 0.7) |
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
| `create_word_document` | Creer un fichier Word (.docx) a partir d'un contenu Markdown |

### Utilitaires

| Outil | Description |
|-------|-------------|
| `list_available_documents` | Lister les fichiers disponibles (2 sources : documents, generated) |
| `inspect_generated_file` | Inspecter la structure d'un Excel genere |

## Configuration

Variables d'environnement principales (voir [docs/configuration.md](docs/configuration.md) pour la liste complete) :

| Variable | Requis | Description |
|----------|--------|-------------|
| `MISTRAL_API_KEY` | Oui | Cle API Mistral (embeddings + OCR) |
| `API_KEY` | Oui (hors DEBUG) | Cle d'authentification pour les endpoints proteges. Generer via `openssl rand -hex 32`. Vide accepte uniquement si `DEBUG=true`. |
| `DOCUMENTS_PATH` | Oui | Chemin local vers vos documents |
| `OUTPUT_PATH` | Non | Dossier de sortie des fichiers generes (defaut: `./output`) |
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
    tools/             # 12 outils MCP
  services/
    pdf/               # Analyse, extraction native, OCR Mistral
    excel/             # Extraction + generation + edition
    word/              # Extraction docx2python
    inspection/        # Inspection fichiers generes
    document/          # Routeur multi-format
    chunking/          # Decoupage en chunks
    embedding/         # Embeddings Mistral (1024 dim)
    vector/            # Stockage Qdrant
  models/              # Schemas Pydantic
```

## Documentation

- [Configuration clients MCP](docs/mcp-client-setup.md) — Claude Desktop, Zileo Chat, autres clients
- [Guide de recherche](docs/research-guide.md) — Indexation, recherche hybride, lecture
- [Guide de generation Excel & Word](docs/generation-guide.md) — Options, design, exemples
- [Reference API](docs/api-reference.md) — Endpoints REST et 12 outils MCP
- [Architecture](docs/architecture.md) — Pipeline de traitement et composants
- [Configuration](docs/configuration.md) — Variables d'environnement
- [Deploiement](docs/deployment.md) — Docker et developpement local
- [Multi-format](docs/multi-format.md) — Support PDF, Excel, Word
- [Code style](docs/code-style.md) — Conventions de code

## Licence

Distribue sous la licence [GNU Affero General Public License v3.0 ou ulterieure](LICENSE).

Cette licence est **obligatoire** car le projet depend de [PyMuPDF](https://github.com/pymupdf/PyMuPDF) et [pymupdf4llm](https://github.com/pymupdf/RAG) (Artifex Software, Inc.) qui sont distribues sous AGPL-3.0. Voir [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) pour l'inventaire complet.

## Securite

Pour signaler une vulnerabilite, voir [SECURITY.md](SECURITY.md). **Ne pas creer d'issue publique.**

## Contribuer

Voir [CONTRIBUTORS.md](CONTRIBUTORS.md) et [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).
