# Configuration des clients MCP

Connecter un client MCP (Claude Desktop, Zileo Chat, custom) au serveur. Le serveur expose `POST http://localhost:8000/mcp` (JSON-RPC 2.0 sur HTTP).

## Prérequis

```bash
docker compose up -d
curl -H "X-API-Key: $API_KEY" http://localhost:8000/health
# {"status": "healthy", ...}
```

## Authentification

Le serveur protège les endpoints `/api/v1/*`, `/mcp` et `/health` (détaillé) via une clé API passée dans le header `X-API-Key`. Hors mode `DEBUG=true`, le démarrage échoue si la clé est vide.

### Générer la clé

La clé est **générée par toi** (pas une clé tierce). Choisir une commande :

```bash
# openssl (32 octets hex = 64 caractères)
openssl rand -hex 32

# Python (URL-safe base64)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Critères : ≥ 32 octets d'entropie (256 bits), une clé différente par environnement (dev / prod / CI), jamais commitée.

### Configurer le serveur

Dans `.env` :

```
API_KEY=8f3d9e2a4b7c1f6e5d8a9b2c3f4e7a1d6b9c8e2f5a3d7b4c1e9f6a2d8b5c3e7f
```

Redémarrer le container : `docker compose up -d`.

### Endpoints protégés vs publics

| Endpoint | Auth requise |
|----------|--------------|
| `POST /mcp` | Oui |
| `POST /api/v1/documents/index` | Oui |
| `GET /api/v1/documents` | Oui |
| `GET /api/v1/documents/{id}` | Oui |
| `DELETE /api/v1/documents/{id}` | Oui |
| `POST /api/v1/search` | Oui |
| `GET /health` (détaillé) | Oui |
| `GET /health/live` | **Non** (liveness Kubernetes) |
| `GET /health/ready` | **Non** (readiness Kubernetes) |

### Codes d'erreur

| HTTP | Cause |
|------|-------|
| `401 Unauthorized` | Header `X-API-Key` manquant |
| `403 Forbidden` | Clé invalide |

## Claude Desktop

### Fichier de configuration

| OS | Chemin |
|----|--------|
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

### Configuration

```json
{
  "mcpServers": {
    "zileo-docs": {
      "url": "http://localhost:8000/mcp",
      "transport": "http",
      "headers": {
        "X-API-Key": "ta_cle_api_ici"
      }
    }
  }
}
```

Remplacer `ta_cle_api_ici` par la valeur de `API_KEY` du fichier `.env` du serveur. Si d'autres serveurs sont déjà configurés, ajouter `zileo-docs` dans le `mcpServers` existant.

Redémarrer Claude Desktop. Les **13 outils** apparaissent dans l'icône d'outils.

### Dépannage

| Symptôme | Cause | Solution |
|----------|-------|----------|
| Outils non visibles | Config non rechargée | Redémarrer Claude Desktop |
| Erreur de connexion | Serveur arrêté | `docker compose ps` |
| Timeout | Port bloqué / firewall | `curl -H "X-API-Key: $API_KEY" http://localhost:8000/health` |
| Erreur JSON | Syntaxe invalide | `jq . config.json` |
| `401 Unauthorized` | Header `X-API-Key` manquant dans la config | Ajouter le bloc `headers` |
| `403 Forbidden` | Clé incorrecte | Vérifier que la clé du client correspond à `API_KEY` du `.env` |

## Zileo Chat

Zileo Chat ne lit pas de fichier `mcpServers` : la configuration se fait via un formulaire. Ouvrir **Réglages → MCP → Ajouter un serveur** et renseigner :

| Champ | Valeur |
|-------|--------|
| **Nom** | `zileo-docs` |
| **Méthode de déploiement** | `HTTP` |
| **Arguments** | l'URL de l'endpoint sur la première ligne — `http://localhost:8000/mcp` |
| **Authentification** | `Clé d'API` |
| **Nom de l'en-tête** | `X-API-Key` |
| **Valeur de la clé d'API** | la valeur de `API_KEY` du `.env` |

La valeur de la clé est stockée dans le trousseau du système d'exploitation : jamais en base en clair, jamais exportée. Seules les métadonnées non sensibles (le nom de l'en-tête) sont persistées.

### URL de l'endpoint selon l'emplacement

| Cas | URL |
|-----|-----|
| Même machine | `http://localhost:8000/mcp` |
| Zileo Chat dans Docker, même machine | `http://zileo-docs:8000/mcp` (voir « Même réseau Docker » ci-dessous) |
| Machine distante (LAN) | `http://<ip-serveur>:8000/mcp` — activer au préalable la bascule d'accès réseau LAN en haut de la page MCP |

### Même réseau Docker

Si Zileo Chat tourne dans Docker sur la même machine, utiliser le nom du container (`http://zileo-docs:8000/mcp`) et le brancher sur le réseau de Zileo Docs (dans son `docker-compose.yml`) :

```yaml
services:
  zileo-chat:
    networks:
      - zileo-docs_mcp-network

networks:
  zileo-docs_mcp-network:
    external: true
```

Le nom du réseau externe est `<projet>_mcp-network` (préfixe Docker Compose + nom du réseau).

## Autres clients MCP

Tout client compatible MCP peut se connecter :
- **URL** : `http://localhost:8000/mcp`
- **Transport** : HTTP POST
- **Protocole** : JSON-RPC 2.0
- **Pas de SSE, pas de WebSocket**

### Méthodes implémentées

| Méthode | Description |
|---------|-------------|
| `initialize` | Handshake. Retourne `protocolVersion: "2024-11-05"` et capabilities |
| `tools/list` | Liste les 13 outils avec leurs schemas |
| `tools/call` | Exécute un outil avec ses arguments |

### Exemples de requêtes

Toutes les requêtes vers `/mcp` doivent inclure le header `X-API-Key`.

```bash
# Handshake
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'

# Lister les outils
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}'

# Appeler un outil
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "list_available_documents",
      "arguments": {"source": "documents", "type_filter": "all"}
    }
  }'
```

## Outils disponibles (13)

### Indexation et recherche (8)

| Outil | Rôle |
|-------|------|
| `index_document` | Indexer PDF / Excel / Word |
| `search_hybrid` | Recherche hybride (dense + BM25 RRF) + garde-fou cosinus |
| `search_semantic` | Recherche sémantique pure (cosinus dense, défaut 0.7) |
| `get_document` | Métadonnées + aperçu chunks |
| `delete_document` | Supprimer de l'index |
| `list_indexed_documents` | Lister documents indexés |
| `read_document_content` | Contenu Markdown reconstitué |
| `get_excel_formulas` | Formules d'un Excel indexé |

### Génération et édition (3)

| Outil | Rôle |
|-------|------|
| `create_excel_document` | Créer .xlsx (data, styles, charts, validations) |
| `edit_excel_document` | Éditer .xlsx (13 opérations) |
| `create_word_document` | Créer .docx depuis Markdown |

### Utilitaires (2)

| Outil | Rôle |
|-------|------|
| `list_available_documents` | Lister fichiers (sources `documents` / `generated`) |
| `inspect_generated_file` | Inspecter structure d'un Excel généré |

## Sécurité

- Le serveur écoute sur `0.0.0.0:8000` dans le container, mappé sur `localhost:8000` par défaut.
- **Authentification obligatoire hors DEBUG** : tous les endpoints sensibles exigent `X-API-Key`. Le serveur refuse de démarrer si `API_KEY` est vide en production.
- **Ne pas exposer le port 8000 sur Internet** : la clé API protège l'accès, mais le projet n'est pas conçu pour un déploiement public.
- `MAX_MCP_BODY_MB` : taille max du body JSON-RPC (défaut 5 MB, protection DoS).
- Rate limiting `/mcp` : 30 req/min par défaut (configurable via `RATE_LIMIT_MCP`).
- CORS désactivé par défaut (activé uniquement si `DEBUG=true`).
- Pour un accès LAN, restreindre via firewall en plus de la clé API.
