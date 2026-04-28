# Configuration des clients MCP

Connecter un client MCP (Claude Desktop, Zileo Chat, custom) au serveur. Le serveur expose `POST http://localhost:8000/mcp` (JSON-RPC 2.0 sur HTTP).

## Prérequis

```bash
docker compose up -d
curl http://localhost:8000/health
# {"status": "healthy", ...}
```

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
    "zileo-rag": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

Si d'autres serveurs sont déjà configurés, ajouter `zileo-rag` dans le `mcpServers` existant.

Redémarrer Claude Desktop. Les **12 outils** apparaissent dans l'icône d'outils.

### Dépannage

| Symptôme | Cause | Solution |
|----------|-------|----------|
| Outils non visibles | Config non rechargée | Redémarrer Claude Desktop |
| Erreur de connexion | Serveur arrêté | `docker compose ps` |
| Timeout | Port bloqué / firewall | `curl http://localhost:8000/health` |
| Erreur JSON | Syntaxe invalide | `jq . config.json` |

## Zileo Chat

### Même machine (localhost)

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

### Même réseau Docker

Si Zileo Chat tourne dans Docker sur la même machine, utiliser le nom du container :

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

Et brancher Zileo Chat sur le réseau de MCP Zileo RAG (dans son `docker-compose.yml`) :

```yaml
services:
  zileo-chat:
    networks:
      - mcp-zileo-rag_mcp-network

networks:
  mcp-zileo-rag_mcp-network:
    external: true
```

Le nom du réseau externe est `<projet>_mcp-network` (préfixe Docker Compose + nom du réseau).

### Machine distante (LAN)

```json
{
  "mcpServers": {
    "zileo-rag": {
      "url": "http://192.168.1.X:8000/mcp",
      "transport": "http"
    }
  }
}
```

Remplacer `192.168.1.X` par l'IP de la machine qui héberge MCP Zileo RAG.

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
| `notifications/initialized` | Notification post-handshake (pas de réponse) |
| `tools/list` | Liste les 12 outils avec leurs schemas |
| `tools/call` | Exécute un outil avec ses arguments |

### Exemples de requêtes

```bash
# Handshake
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
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
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}'

# Appeler un outil
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
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

## Outils disponibles (12)

### Indexation et recherche (7)

| Outil | Rôle |
|-------|------|
| `index_document` | Indexer PDF / Excel / Word |
| `search_documents` | Recherche hybride (défaut) ou sémantique |
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
- **Ne pas exposer le port 8000 sur Internet** sans authentification (le projet est destiné à un usage local).
- Rate limiting `/mcp` : 30 req/min par défaut (configurable via `RATE_LIMIT_MCP`).
- CORS désactivé par défaut (activé uniquement si `DEBUG=true`).
- Pour un accès LAN, restreindre via firewall.
