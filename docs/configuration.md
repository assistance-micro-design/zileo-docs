# Configuration

## Variables d'Environnement

Toutes les configurations se font via variables d'environnement. Copier `.env.example` vers `.env` et ajuster les valeurs.

### Application

| Variable | Defaut | Description |
|----------|--------|-------------|
| `DEBUG` | `false` | Mode debug (active /docs et /redoc) |
| `LOG_LEVEL` | `INFO` | Niveau de log (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | `json` | Format des logs (json, text) |

### Mistral API (Requis)

| Variable | Defaut | Description |
|----------|--------|-------------|
| `MISTRAL_API_KEY` | - | Cle API Mistral (requis) |
| `MISTRAL_OCR_MODEL` | `mistral-ocr-latest` | Modele OCR |
| `MISTRAL_EMBED_MODEL` | `mistral-embed` | Modele d'embeddings |

### Qdrant

| Variable | Defaut | Description |
|----------|--------|-------------|
| `QDRANT_HOST` | `localhost` | Hote Qdrant |
| `QDRANT_PORT` | `6333` | Port Qdrant |
| `QDRANT_COLLECTION` | `pdf_documents` | Nom de la collection |
| `QDRANT_API_KEY` | - | Cle API (optionnel, pour Qdrant Cloud) |

### Traitement PDF

| Variable | Defaut | Description |
|----------|--------|-------------|
| `CHUNK_SIZE` | `512` | Taille des chunks en tokens |
| `CHUNK_OVERLAP` | `50` | Overlap entre chunks en tokens |
| `OCR_DPI` | `300` | Resolution pour conversion image |
| `OCR_MAX_CONCURRENT` | `5` | Requetes OCR paralleles max |
| `OCR_TABLE_FORMAT` | `markdown` | Format tableaux (markdown, html) |

### Limites

| Variable | Defaut | Description |
|----------|--------|-------------|
| `MAX_PDF_SIZE_MB` | `50` | Taille max d'un PDF en MB |
| `MAX_PDF_PAGES` | `1000` | Nombre max de pages par PDF |

---

## Exemple de Configuration

Fichier `.env` minimal :

```
MISTRAL_API_KEY=votre_cle_api
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

Configuration complete pour production :

```
# Application
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json

# Mistral
MISTRAL_API_KEY=votre_cle_api
MISTRAL_OCR_MODEL=mistral-ocr-latest
MISTRAL_EMBED_MODEL=mistral-embed

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=pdf_documents

# Processing
CHUNK_SIZE=512
CHUNK_OVERLAP=50
OCR_DPI=300
OCR_MAX_CONCURRENT=5

# Limits
MAX_PDF_SIZE_MB=50
MAX_PDF_PAGES=1000
```

---

## Configuration Docker

En mode Docker, les variables sont passees via `docker-compose.yml` ou fichier `.env`.

Le service Qdrant est configure automatiquement avec le hostname `qdrant` dans le reseau Docker.

---

## Estimation des Couts Mistral

| Operation | Prix |
|-----------|------|
| OCR Standard | $2 / 1000 pages |
| OCR Batch | $1 / 1000 pages |
| Embeddings | $0.10 / million tokens |

Exemple : 100 PDFs de 50 pages = environ $5-10
