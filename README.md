# MCP Zileo RAG

Serveur MCP pour le traitement de documents PDF, Excel et Word avec OCR et recherche vectorielle.

> **Usage personnel uniquement** - Ce projet est concu pour une utilisation locale sur votre ordinateur personnel via Docker Desktop. Aucune garantie n'est fournie pour un deploiement public ou en production. L'auteur decline toute responsabilite en cas d'utilisation sur un reseau public ou expose a Internet.

## Formats Supportes

| Format | Extensions | Bibliotheque | Fonctionnalites |
|--------|------------|--------------|-----------------|
| PDF | `.pdf` | pymupdf4llm | Texte, tableaux, images, OCR |
| Excel moderne | `.xlsx` | openpyxl | Donnees, formules, styles |
| Excel legacy | `.xls` | xlrd | Donnees uniquement |
| Word moderne | `.docx` | docx2python | Texte, tableaux, images |

## Installation

```bash
pip install -e ".[dev]"
```

## Configuration

Copier `.env.example` vers `.env` et configurer les variables :

```bash
# Services externes
MISTRAL_API_KEY=your_key_here
QDRANT_URL=http://localhost:6333

# Chemins
DOCUMENTS_PATH=/app/documents

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Lancement

### Avec Docker (recommande)

```bash
docker-compose up -d
```

### En local

```bash
uvicorn src.main:app --reload
```

## Configuration MCP pour Claude Desktop

Pour utiliser ce serveur avec Claude Desktop, ajoutez la configuration suivante dans votre fichier de configuration Claude :

**Emplacement du fichier de configuration :**
- macOS : `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows : `%APPDATA%\Claude\claude_desktop_config.json`
- Linux : `~/.config/Claude/claude_desktop_config.json`

**Configuration a ajouter :**

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

**Etapes d'installation :**

1. **Demarrer le serveur** avec Docker Compose :
   ```bash
   docker-compose up -d
   ```

2. **Verifier que le serveur fonctionne** :
   ```bash
   curl http://localhost:8000/health
   ```

3. **Configurer Claude Desktop** en editant le fichier de configuration ci-dessus

4. **Redemarrer Claude Desktop** pour charger la nouvelle configuration

5. **Tester** en demandant a Claude de lister les documents disponibles :
   > "Liste les documents disponibles dans mon dossier"

**Variables importantes dans `.env` :**

```bash
# Chemin vers vos documents (monte en lecture seule)
DOCUMENTS_PATH=/chemin/vers/vos/documents

# Votre cle API Mistral (requise pour OCR et embeddings)
MISTRAL_API_KEY=votre_cle_api
```

## Outils MCP Disponibles

| Outil | Description |
|-------|-------------|
| `index_document` | Indexer un PDF, Excel ou Word |
| `search_documents` | Recherche semantique dans les documents indexes |
| `get_document` | Recuperer les metadonnees d'un document |
| `delete_document` | Supprimer un document de l'index |
| `list_indexed_documents` | Lister tous les documents indexes |
| `list_available_documents` | Lister les documents disponibles (PDF, Excel, Word) |
| `read_document_content` | Lire le contenu Markdown d'un document |
| `get_excel_formulas` | Recuperer les formules d'un Excel indexe |

## Tests

```bash
# Tous les tests
pytest tests/ -v

# Tests unitaires seulement
pytest tests/unit/ -v

# Tests E2E
pytest tests/e2e/ -v
```

## Validation

```bash
# Linting + formatting
ruff check src/ tests/
ruff format src/ tests/

# Type checking
mypy src/

# Tests
pytest tests/
```

## Architecture

```
src/
  api/          # Endpoints FastAPI REST
  mcp/          # Serveur MCP et tools
  services/     # Logique metier
    pdf/        # Extraction PDF
    excel/      # Extraction Excel
    word/       # Extraction Word
    document/   # Router multi-format
  models/       # Schemas Pydantic
tests/
  unit/
  integration/
  e2e/
```

## Documentation

- [Reference API](docs/api-reference.md)
- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Deploiement](docs/deployment.md)
