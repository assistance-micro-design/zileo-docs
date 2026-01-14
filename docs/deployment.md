# Deploiement

## Prerequis

- Docker et Docker Compose
- Cle API Mistral

## Deploiement Docker

### 1. Configuration

Copier le fichier d'exemple et configurer :

```bash
cp .env.example .env
```

Editer `.env` avec votre cle API Mistral.

### 2. Lancement

```bash
docker-compose up -d
```

Cela demarre :
- L'application sur le port 8000
- Qdrant sur les ports 6333 (HTTP) et 6334 (gRPC)

### 3. Verification

```bash
curl http://localhost:8000/health/ready
```

---

## Services Docker

### Application (mcp-zileo-pdf)

- **Port** : 8000
- **Image** : Build local via Dockerfile
- **Dependances** : qdrant

### Qdrant

- **Port HTTP** : 6333
- **Port gRPC** : 6334
- **Image** : `qdrant/qdrant:latest`
- **Volume** : `qdrant_storage` pour persistance

---

## Commandes Utiles

| Action | Commande |
|--------|----------|
| Demarrer | `docker-compose up -d` |
| Arreter | `docker-compose down` |
| Logs app | `docker-compose logs -f app` |
| Logs qdrant | `docker-compose logs -f qdrant` |
| Rebuild | `docker-compose build --no-cache` |
| Supprimer volumes | `docker-compose down -v` |

---

## Developpement Local

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

---

## Validation

Avant deploiement, executer la validation complete :

```bash
ruff check src/ tests/ --fix
ruff format src/ tests/
mypy src/ --strict
pytest tests/ -v
```

---

## Monitoring

### Health Checks

| Endpoint | Description |
|----------|-------------|
| `/health/live` | Application vivante |
| `/health/ready` | Dependances prates |
| `/health` | Status complet |

### Metriques Qdrant

Accessible via l'API Qdrant sur le port 6333 :
- Collection info
- Points count
- Index status

---

## Production

Pour un deploiement production :

1. Desactiver le mode DEBUG
2. Configurer LOG_FORMAT=json pour parsing des logs
3. Ajuster OCR_MAX_CONCURRENT selon les limites API
4. Configurer un reverse proxy (nginx, traefik)
5. Activer TLS/HTTPS
6. Configurer les backups Qdrant
