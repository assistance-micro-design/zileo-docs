# Deploiement

## Prerequis

- Docker et Docker Compose
- Une cle API Mistral

## Docker Compose

### 1. Configuration

```bash
cp .env.example .env
```

Editer `.env` : renseigner `MISTRAL_API_KEY` et `DOCUMENTS_PATH`.

### 2. Lancement

```bash
docker-compose up -d
```

Deux services demarrent :
- **app** (`mcp-zileo-rag`) : Application FastAPI sur le port 8000
- **qdrant** (`mcp-zileo-rag-qdrant`) : Base vectorielle sur les ports 6333 (HTTP) et 6334 (gRPC)

Les services communiquent via un reseau Docker interne (`mcp-network`). L'application attend que Qdrant soit healthy avant de demarrer (`depends_on: condition: service_healthy`).

### 3. Verification

```bash
curl http://localhost:8000/health/ready
```

Reponse attendue : `{"status": "ready"}`.

### Commandes utiles

| Action | Commande |
|--------|----------|
| Demarrer | `docker-compose up -d` |
| Arreter | `docker-compose down` |
| Logs application | `docker-compose logs -f app` |
| Logs Qdrant | `docker-compose logs -f qdrant` |
| Rebuild (apres modification du code) | `docker-compose build --no-cache` |
| Supprimer volumes (perte de donnees) | `docker-compose down -v` |

---

## Developpement local

### Installation

```bash
pip install -e ".[dev]"
```

### Demarrer Qdrant seul

```bash
docker-compose up -d qdrant
```

### Lancer l'application

```bash
uvicorn src.main:app --reload --port 8000
```

En local, `QDRANT_HOST` doit rester `localhost` (pas `qdrant`).

---

## Validation avant deploiement

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest tests/ -v
```

---

## Health checks

| Endpoint | Usage | Verifie |
|----------|-------|---------|
| `/health/live` | Liveness probe | L'application repond |
| `/health/ready` | Readiness probe | La connexion Qdrant fonctionne |
| `/health` | Status complet | Qdrant + configuration Mistral |

L'image Docker inclut un healthcheck qui appelle `/health` toutes les 30 secondes.

---

## Configuration des clients MCP

Une fois le serveur demarre, configurer vos clients MCP (Claude Desktop, Zileo Chat, etc.) pour se connecter a `http://localhost:8000/mcp`.

Voir le guide complet : [Configuration clients MCP](mcp-client-setup.md)

---

## Notes

- L'application tourne avec l'utilisateur `appuser` (non-root) dans le container
- Le dossier de documents est monte en lecture seule (`:ro`)
- Le dossier de sortie (`OUTPUT_PATH`) est monte en lecture-ecriture pour les fichiers Excel generes
- Qdrant utilise un volume Docker nomme (`qdrant_storage`) pour la persistance
- Les logs sont en JSON par defaut (`LOG_FORMAT=json`)
- `DEBUG=true` active Swagger UI sur `/docs` et le CORS avec `allow_origins=["*"]` — ne pas utiliser en production
