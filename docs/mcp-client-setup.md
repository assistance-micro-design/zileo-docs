# Configuration des clients MCP

Guide de connexion des clients MCP (Claude Desktop, Zileo Chat, autres) au serveur MCP Zileo RAG.

## Prerequis

Le serveur MCP Zileo RAG doit etre demarre et accessible :

```bash
docker compose up -d
curl http://localhost:8000/health
# {"status": "healthy", ...}
```

L'endpoint MCP est `POST http://localhost:8000/mcp` (JSON-RPC 2.0 sur HTTP).

---

## Claude Desktop

### Localisation du fichier de configuration

| OS | Chemin |
|----|--------|
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

### Configuration

Ajouter (ou creer) le fichier avec le contenu suivant :

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

Si d'autres serveurs MCP sont deja configures, ajouter `zileo-rag` dans l'objet `mcpServers` existant :

```json
{
  "mcpServers": {
    "autre-serveur": {
      "command": "node",
      "args": ["autre-serveur/index.js"]
    },
    "zileo-rag": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

### Verification

1. Redemarrer Claude Desktop
2. Dans une nouvelle conversation, les 11 outils MCP apparaissent dans l'icone d'outils
3. Tester avec un prompt : *"Liste les documents disponibles"* — Claude appellera `list_available_documents`

### Depannage Claude Desktop

| Symptome | Cause probable | Solution |
|----------|---------------|----------|
| Outils non visibles | Config non rechargee | Redemarrer Claude Desktop |
| Erreur de connexion | Serveur non demarre | `docker compose ps` pour verifier |
| Timeout | Port bloque | Verifier `curl http://localhost:8000/health` |
| Erreur JSON | Syntaxe JSON invalide | Valider le fichier avec `jq . config.json` |

---

## Zileo Chat

### Configuration locale (meme machine)

Dans la configuration MCP de Zileo Chat :

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

### Configuration Docker (meme reseau)

Si Zileo Chat et MCP Zileo RAG tournent dans le meme reseau Docker, utiliser le nom du container :

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

Pour connecter Zileo Chat au reseau Docker de MCP Zileo RAG, ajouter dans le `docker-compose.yml` de Zileo Chat :

```yaml
services:
  zileo-chat:
    # ... config existante ...
    networks:
      - mcp-zileo-rag_mcp-network

networks:
  mcp-zileo-rag_mcp-network:
    external: true
```

Le nom du reseau externe est `mcp-zileo-rag_mcp-network` (prefixe du projet Docker Compose + nom du reseau).

### Configuration reseau distant

Si Zileo Chat tourne sur une autre machine du reseau local :

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

Remplacer `192.168.1.X` par l'IP de la machine qui heberge MCP Zileo RAG.

### Verification

1. Recharger la configuration Zileo Chat
2. Les 11 outils MCP doivent apparaitre
3. Tester : *"Indexe le fichier rapport.pdf"* — Zileo Chat appellera `index_document`

---

## Autres clients MCP

Tout client compatible MCP peut se connecter au serveur. La configuration minimale est :

- **URL** : `http://localhost:8000/mcp`
- **Transport** : HTTP (POST)
- **Protocole** : JSON-RPC 2.0

### Methodes implementees

| Methode | Description |
|---------|-------------|
| `initialize` | Handshake initial, retourne les capabilities du serveur |
| `notifications/initialized` | Notification post-handshake (pas de reponse) |
| `tools/list` | Liste les 11 outils avec leurs schemas |
| `tools/call` | Execute un outil avec les arguments fournis |

### Exemple de requete manuelle

```bash
# Handshake
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-11-25",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'

# Lister les outils
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'

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

---

## Outils disponibles

Une fois connecte, le client MCP a acces aux 11 outils suivants :

### Indexation et recherche

| Outil | Description |
|-------|-------------|
| `index_document` | Indexer un PDF, Excel ou Word (extraction + embeddings + Qdrant) |
| `search_documents` | Recherche semantique dans les documents indexes |
| `get_document` | Metadonnees et chunks d'un document |
| `delete_document` | Supprimer un document de l'index |
| `list_indexed_documents` | Lister les documents indexes |
| `read_document_content` | Contenu Markdown d'un document indexe |
| `get_excel_formulas` | Formules d'un Excel indexe |

### Generation et edition

| Outil | Description |
|-------|-------------|
| `create_excel_document` | Creer un fichier Excel (.xlsx) |
| `edit_excel_document` | Editer un Excel existant (13 operations) |

### Utilitaires

| Outil | Description |
|-------|-------------|
| `list_available_documents` | Lister les fichiers (2 sources) |
| `inspect_generated_file` | Inspecter la structure d'un fichier genere |

---

## Securite

- Le serveur ecoute sur toutes les interfaces (`0.0.0.0:8000`) dans le container Docker
- Le port 8000 est mappe sur `localhost:8000` par defaut (accessible uniquement depuis la machine hote)
- **Ne pas exposer le port 8000 sur Internet** sans authentification
- Rate limiting : 30 requetes/minute sur `/mcp` par defaut
- CORS desactive par defaut (active uniquement avec `DEBUG=true`)
- Pour un acces reseau local, configurer le firewall pour limiter l'acces au port 8000
