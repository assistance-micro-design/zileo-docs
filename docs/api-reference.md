# Reference API

## Endpoints REST

### Health checks

| Methode | Path | Description |
|---------|------|-------------|
| GET | `/` | Info du service (nom, version) |
| GET | `/health` | Health check complet (Qdrant + config Mistral) |
| GET | `/health/live` | Liveness probe (toujours 200) |
| GET | `/health/ready` | Readiness probe (verifie la connexion Qdrant) |

### Documents

| Methode | Path | Description |
|---------|------|-------------|
| POST | `/api/v1/documents/index` | Indexer un fichier PDF (upload multipart) |
| GET | `/api/v1/documents/{document_id}` | Recuperer les chunks et metadata d'un document |
| DELETE | `/api/v1/documents/{document_id}` | Supprimer un document de l'index |
| GET | `/api/v1/documents` | Statistiques de la collection Qdrant |

#### POST /api/v1/documents/index

Upload et indexation d'un PDF. L'API REST ne supporte que le PDF (upload multipart). Pour indexer des Excel ou Word, utiliser l'outil MCP `index_document` qui accepte un chemin fichier.

**Parametres (multipart/form-data)** :
- `file` : Fichier PDF
- `force_ocr` : Forcer OCR sur toutes les pages (query param, defaut: false)
- `table_format` : Format des tableaux, `markdown` ou `html` (query param, defaut: markdown)

**Reponse** : `document_id`, `filename`, `total_pages`, `chunks_created`, `processing_time_seconds`

Rate limit : 10 requetes/minute.

### Recherche

| Methode | Path | Description |
|---------|------|-------------|
| POST | `/api/v1/search` | Recherche semantique (body JSON) |
| GET | `/api/v1/search` | Recherche semantique (query params) |

Rate limit : 30 requetes/minute.

#### POST /api/v1/search

**Body JSON** :

```json
{
  "query": "comment configurer X ?",
  "top_k": 5,
  "score_threshold": 0.7,
  "filters": {
    "document_id": "uuid",
    "content_type": "text",
    "has_table": true,
    "doc_filename": "rapport.pdf"
  }
}
```

#### GET /api/v1/search

**Query params** : `q` (requis), `top_k`, `score_threshold`, `document_id`, `content_type`, `has_table`, `has_image`

**Reponse** :

```json
{
  "query": "...",
  "total_results": 5,
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "content": "...",
      "content_preview": "...",
      "score": 0.89,
      "page_numbers": [1, 2],
      "section_title": "...",
      "content_type": "text",
      "doc_filename": "rapport.pdf"
    }
  ],
  "processing_time_ms": 120
}
```

---

## Serveur MCP (JSON-RPC 2.0)

Endpoint : `POST /mcp`
Rate limit : 30 requetes/minute.

### Methodes JSON-RPC

| Methode | Description |
|---------|-------------|
| `initialize` | Initialiser la session MCP, retourne les capabilities du serveur |
| `tools/list` | Lister les 8 outils disponibles avec leurs schemas |
| `tools/call` | Executer un outil par nom |

### Outils MCP

#### index_document

Extrait et indexe un document pour la recherche semantique. Le fichier doit etre accessible dans le dossier monte (`DOCUMENTS_PATH`).

Si un document avec le meme nom de fichier est deja indexe, retourne l'ID existant sans re-indexer.

**Parametres** :

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `file_path` | string | Oui | Chemin absolu vers le document (doit etre dans DOCUMENTS_PATH) |
| `force_ocr` | boolean | Non | PDF : forcer OCR meme si texte natif (defaut: false) |
| `sheets` | array[string] | Non | Excel : noms des feuilles a indexer (toutes si omis) |
| `table_format` | string | Non | Format des tableaux : `markdown` ou `html` (defaut: markdown) |

**Retour** :

```json
{
  "document_id": "uuid",
  "document_type": "pdf",
  "filename": "rapport.pdf",
  "chunks_stored": 42,
  "has_tables": true,
  "has_formulas": false,
  "has_images": true,
  "processing_time_seconds": 12.5
}
```

#### search_documents

Recherche dans les documents indexes par similarite vectorielle. Necessite au moins un document indexe.

**Parametres** :

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `query` | string | Oui | Question en langage naturel |
| `top_k` | integer | Non | Nombre de resultats (1-100, defaut: 5) |
| `score_threshold` | number | Non | Score minimum de similarite (0.0-1.0, defaut: 0.7) |
| `filters` | object | Non | Filtres (voir ci-dessous) |

**Filtres disponibles** :

| Filtre | Type | Description |
|--------|------|-------------|
| `document_id` | string | Limiter a un document |
| `doc_filename` | string | Filtrer par nom de fichier |
| `document_type` | string | `pdf`, `excel` ou `word` |
| `has_table` | boolean | Chunks contenant des tableaux |
| `has_image` | boolean | Chunks contenant des images |
| `has_formula` | boolean | Chunks avec formules (Excel) |
| `text_search` | string | Recherche full-text dans le contenu |
| `sheet_name` | string | Filtrer par feuille (Excel) |

**Note sur score_threshold** : Le defaut (0.7) est adapte a la recherche de concepts. Pour des noms propres ou des termes specifiques, baisser a 0.3-0.5 et combiner avec `text_search` pour de meilleurs resultats.

#### get_document

Recupere les metadonnees et un apercu des chunks d'un document indexe.

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document |

#### delete_document

Supprime un document de l'index Qdrant. Ne supprime **pas** le fichier source sur le disque.

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document |

Retour : `chunks_deleted` (nombre), `status` (`deleted` ou `not_found`).

#### list_indexed_documents

Liste tous les documents indexes dans Qdrant. Aucun parametre.

Retour : liste de documents avec `document_id`, `filename`, `total_chunks`, `ingested_at`.

#### list_available_documents

Liste les fichiers disponibles pour indexation dans le dossier monte.

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `type_filter` | string | Non | `pdf`, `excel`, `word` ou `all` (defaut: all) |
| `subdirectory` | string | Non | Sous-dossier relatif a explorer |
| `recursive` | boolean | Non | Explorer recursivement (defaut: true) |

Retour : `base_path`, `total_files`, `by_type` (comptage par format), `files` (liste avec `filename`, `path`, `relative_path`, `type`, `size_mb`, `extension`).

#### read_document_content

Lit le contenu Markdown reconstitue d'un document indexe, en concatenant ses chunks.

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document |
| `page_start` | integer | Non | Page de debut (1-indexed) |
| `page_end` | integer | Non | Page de fin (1-indexed) |
| `include_chunks_detail` | boolean | Non | Inclure les metadata de chaque chunk (defaut: false) |

#### get_excel_formulas

Recupere les formules d'un document Excel indexe. Les formules sont stockees dans des chunks dedies lors de l'indexation.

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document Excel |
| `sheet` | string | Non | Filtrer par nom de feuille |
| `cell_range` | string | Non | Filtrer par plage de cellules (ex: `A1:D10`) |

Retour : `total_formulas`, `formulas` (liste avec `sheet`, `cell`, `formula`, `result`).

---

## Codes d'erreur

### HTTP

| Code | Description |
|------|-------------|
| 400 | Requete invalide |
| 404 | Document non trouve |
| 413 | Fichier trop volumineux |
| 422 | Erreur de validation |
| 429 | Rate limit depasse |
| 500 | Erreur interne |

### JSON-RPC

| Code | Message |
|------|---------|
| -32600 | Invalid Request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |

### Format d'erreur MCP

Les erreurs MCP utilisent `to_llm_format()` qui produit un texte structure pour guider le LLM :

```
ERROR [PDF_NOT_FOUND]: Fichier PDF introuvable: /bad/path.pdf
SUGGESTION: Verifier le chemin. Utiliser un chemin absolu commencant par /.
PARAMETER: file_path
RETRY: Corriger et reessayer
```

Ce format est genere par la hierarchie d'exceptions `MCPZileoPDFError` dans `src/core/exceptions.py`. Chaque exception porte un code, un message, une suggestion, et un indicateur de retry.
