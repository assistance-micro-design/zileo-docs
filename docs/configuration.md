# Configuration

Toute la configuration se fait via variables d'environnement. Copier `.env.example` vers `.env` et ajuster les valeurs.

## Variables d'environnement

### Application

| Variable | Defaut | Description |
|----------|--------|-------------|
| `DEBUG` | `false` | Active Swagger UI (`/docs`, `/redoc`), CORS et hot-reload |
| `LOG_LEVEL` | `INFO` | Niveau de log : DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | `json` | Format des logs : `json` ou `text` |

### Mistral API (requis)

| Variable | Defaut | Description |
|----------|--------|-------------|
| `MISTRAL_API_KEY` | - | Cle API Mistral. Requise pour les embeddings et l'OCR. |
| `MISTRAL_OCR_MODEL` | `mistral-ocr-latest` | Modele utilise pour l'OCR des pages PDF complexes |
| `MISTRAL_EMBED_MODEL` | `mistral-embed` | Modele utilise pour les embeddings (1024 dimensions) |

### Qdrant

| Variable | Defaut | Description |
|----------|--------|-------------|
| `QDRANT_HOST` | `localhost` | Hote Qdrant (`qdrant` en mode Docker) |
| `QDRANT_PORT` | `6333` | Port HTTP Qdrant |
| `QDRANT_COLLECTION` | `documents` | Nom de la collection Qdrant |
| `QDRANT_API_KEY` | - | Optionnel. Pour Qdrant Cloud uniquement. |

### Traitement

| Variable | Defaut | Description |
|----------|--------|-------------|
| `CHUNK_SIZE` | `512` | Taille cible des chunks en tokens (tiktoken cl100k_base) |
| `CHUNK_OVERLAP` | `50` | Nombre de tokens d'overlap entre chunks consecutifs |
| `OCR_DPI` | `300` | Resolution de conversion PDF -> image pour l'OCR |
| `OCR_MAX_CONCURRENT` | `5` | Nombre maximum de requetes OCR paralleles vers Mistral |
| `OCR_TABLE_FORMAT` | `markdown` | Format des tableaux extraits par OCR : `markdown` ou `html` |

### Limites

| Variable | Defaut | Description |
|----------|--------|-------------|
| `MAX_FILE_SIZE_MB` | `50` | Taille maximum d'un fichier en Mo |
| `MAX_PAGES` | `1000` | Nombre maximum de pages par document |

### Chemins

| Variable | Defaut | Description |
|----------|--------|-------------|
| `DOCUMENTS_PATH` | `/app/documents` | Dossier contenant les documents (PDF, Excel, Word) accessibles pour indexation |

### Rate limiting

| Variable | Defaut | Description |
|----------|--------|-------------|
| `RATE_LIMIT_DEFAULT` | `60/minute` | Limite par defaut pour les endpoints non specifies |
| `RATE_LIMIT_INDEX` | `10/minute` | Limite pour l'indexation (POST /api/v1/documents/index) |
| `RATE_LIMIT_MCP` | `30/minute` | Limite pour l'endpoint MCP (POST /mcp) |
| `RATE_LIMIT_SEARCH` | `30/minute` | Limite pour la recherche (POST /api/v1/search) |

Format : `"X/minute"` ou `"X/hour"`. Implemente via slowapi.

---

## Exemple minimal

```
MISTRAL_API_KEY=sk-...
DOCUMENTS_PATH=/home/user/Documents
```

En mode Docker, `QDRANT_HOST` est automatiquement `qdrant` via le reseau Docker interne.

## Exemple complet

```
# Application
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json

# Mistral
MISTRAL_API_KEY=sk-...
MISTRAL_OCR_MODEL=mistral-ocr-latest
MISTRAL_EMBED_MODEL=mistral-embed

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=documents

# Traitement
CHUNK_SIZE=512
CHUNK_OVERLAP=50
OCR_DPI=300
OCR_MAX_CONCURRENT=5
OCR_TABLE_FORMAT=markdown

# Limites
MAX_FILE_SIZE_MB=50
MAX_PAGES=1000

# Chemins
DOCUMENTS_PATH=/home/user/Documents

# Rate limiting
RATE_LIMIT_DEFAULT=60/minute
RATE_LIMIT_INDEX=10/minute
RATE_LIMIT_MCP=30/minute
RATE_LIMIT_SEARCH=30/minute
```

---

## Docker

En mode Docker, les variables sont passees via le fichier `.env` (lu automatiquement par docker-compose).

### Volumes montes

| Volume | Container | Description |
|--------|-----------|-------------|
| `./data` | `/app/data` | Donnees persistantes de l'application |
| `$DOCUMENTS_PATH` | `/app/documents` | Documents accessibles (monte en lecture seule) |
| `qdrant_storage` | `/qdrant/storage` | Donnees Qdrant (volume Docker nomme) |

### Variables forcees en Docker

`QDRANT_HOST` est fixe a `qdrant` dans `docker-compose.yml` (nom du service Docker). La valeur dans `.env` est ignoree pour cette variable en mode Docker.

---

## Cout Mistral

Estimation indicative (tarifs susceptibles de changer) :

| Operation | Prix approximatif |
|-----------|-------------------|
| OCR | ~$2 / 1000 pages |
| Embeddings | ~$0.10 / million tokens |

Les pages en texte pur sont extraites localement via PyMuPDF4LLM (gratuit). Seules les pages complexes (scans, tableaux, images) sont envoyees a l'OCR Mistral. Les embeddings sont generes pour tous les chunks.
