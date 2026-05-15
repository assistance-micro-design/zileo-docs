# Référence API

Endpoints REST + 12 outils MCP. Pour les options détaillées de génération Excel/Word, voir [generation-guide.md](generation-guide.md).

## REST

| Méthode | Path | Description | Rate limit |
|---------|------|-------------|------------|
| GET | `/` | Info service (nom, version) | — |
| GET | `/health` | Health complet (Qdrant + config Mistral) | — |
| GET | `/health/live` | Liveness probe | — |
| GET | `/health/ready` | Readiness probe (vérifie Qdrant) | — |
| POST | `/api/v1/documents/index` | Upload + indexation PDF (multipart, **PDF seul**) | 10/min |
| GET | `/api/v1/documents/{id}` | Chunks + métadonnées | — |
| DELETE | `/api/v1/documents/{id}` | Supprimer de l'index | — |
| GET | `/api/v1/documents` | Stats collection | — |
| POST | `/api/v1/search` | Recherche (body JSON) | 30/min |
| GET | `/api/v1/search` | Recherche (query params) | 30/min |

Pour indexer Excel ou Word : utiliser le tool MCP `index_document`.

### Exemple recherche

```json
POST /api/v1/search
{
  "query": "comment configurer X ?",
  "top_k": 5,
  "score_threshold": 0.7,
  "search_mode": "hybrid",
  "filters": {"document_type": "pdf", "has_table": true}
}
```

Réponse : `query`, `total_results`, `results[]` (chunk_id, document_id, content, score, page_numbers, section_title, content_type, doc_filename, document_type, has_formula, sheet_names).

## MCP (JSON-RPC 2.0)

`POST /mcp`. Rate limit : 30/min.

| Méthode | Description |
|---------|-------------|
| `initialize` | Handshake → `protocolVersion: "2024-11-05"` + capabilities |
| `tools/list` | Liste les **12 outils** avec leurs schemas |
| `tools/call` | Exécute un outil par nom |

## Outils MCP

### `index_document`

Indexe PDF / Excel / Word. Idempotent (hash dédup). Si fichier modifié : `file_modified: true` (à supprimer puis ré-indexer).

| Param | Type | Requis | Description |
|-------|------|--------|-------------|
| `file_path` | string | ✅ | Chemin absolu dans `DOCUMENTS_PATH` |
| `force_ocr` | boolean | | PDF : forcer OCR |
| `sheets` | string[] | | Excel : feuilles à indexer |
| `table_format` | string | | `markdown` / `html` |

Retour : `document_id`, `document_type`, `filename`, `chunks_stored`, `has_tables`, `has_formulas`, `has_images`, `processing_time_seconds`.

### `search_hybrid`

Recherche hybride : vecteur dense (Mistral 1024d) + BM25 sparse, fusion RRF native Qdrant. Échelle de score RRF masquée au caller (non-interprétable cross-corpus).

| Param | Type | Défaut | Description |
|-------|------|--------|-------------|
| `query` | string | — | Requête en langage naturel |
| `top_k` | int | 5 | 1-100 |
| `min_cosine_relevance` | float | — | Opt-in (0.0-1.0). Garde-fou anti hors-domaine : si le top-1 cosinus dense < seuil, retourne `[]`. Calibre empirique : 0.72 |
| `filters` | object | — | Voir ci-dessous |

**Filtres** : `document_id`, `doc_filename`, `document_type` (`pdf`/`excel`/`word`), `has_table`, `has_image`, `has_formula`, `text_search`, `sheet_name`.

### `search_semantic`

Recherche sémantique pure : similarité cosinus dense uniquement (Mistral 1024d).

| Param | Type | Défaut | Description |
|-------|------|--------|-------------|
| `query` | string | — | Requête en langage naturel |
| `top_k` | int | 5 | 1-100 |
| `score_threshold` | float | 0.7 | Seuil cosinus (0.0-1.0) |
| `filters` | object | — | Mêmes filtres que `search_hybrid` |

> Choix : utilise `search_hybrid` par défaut (mix concepts + mots-clés). `search_semantic` est utile pour les questions purement conceptuelles ou pour calibrer un seuil cosinus strict.

### `get_document`, `delete_document`, `list_indexed_documents`

| Tool | Param | Retour |
|------|-------|--------|
| `get_document` | `document_id` ✅ | Métadonnées + aperçu chunks |
| `delete_document` | `document_id` ✅ | `chunks_deleted`, `status`. **Supprime de l'index Qdrant uniquement** |
| `list_indexed_documents` | (aucun) | `total_documents`, `documents[]` |

### `list_available_documents`

Liste les fichiers du disque accessibles au serveur.

| Param | Type | Défaut | Description |
|-------|------|--------|-------------|
| `source` | string | `documents` | `documents` (DOCUMENTS_PATH) ou `generated` (OUTPUT_PATH) |
| `type_filter` | string | `all` | `pdf`, `excel`, `word`, `all` |
| `subdirectory` | string | `""` | Sous-dossier relatif |
| `recursive` | boolean | `true` | Récursif |

Retour : `source`, `base_path`, `total_files`, `by_type`, `files[]` avec `filename`, `path`, `relative_path`, `type`, `size_mb`, `extension`, `editable_with`.

### `read_document_content`

Lit le contenu Markdown reconstitué d'un document indexé.

| Param | Type | Description |
|-------|------|-------------|
| `document_id` ✅ | string | |
| `page_start` | int | Page de début (1-indexed) |
| `page_end` | int | Page de fin (1-indexed) |
| `include_chunks_detail` | bool | Métadonnées chunks (défaut `false`) |

### `get_excel_formulas`

| Param | Type | Description |
|-------|------|-------------|
| `document_id` ✅ | string | Document Excel |
| `sheet` | string | Filtrer par feuille |
| `cell_range` | string | Filtrer par plage (`A1:D10`) |

Retour : `total_formulas`, `formulas[]` (`sheet`, `cell`, `formula`, `result`).

### `create_excel_document`

Crée un `.xlsx` dans `OUTPUT_PATH`. Schéma Pydantic complet via `tools/list`.

| Param | Type | Requis | Limites |
|-------|------|--------|---------|
| `filename` | string | ✅ | doit finir par `.xlsx` |
| `sheets` | SheetDef[] | ✅ | 1 à 50 feuilles |
| `author` | string | | max 255 chars |

`SheetDef` : `name`, `headers`, `rows` (max 10 000 / 500 colonnes), `styles`, `charts` (`bar`/`line`/`pie`/`scatter`/`area`/`column`), `data_validations`, `merged_cells`, `column_widths`, `auto_filter`, `freeze_panes`, `tab_color`.

Retour : `file_path`, `filename`, `sheets_created`, `total_rows`, `total_charts`, `file_size_bytes`, `overwritten`.

### `edit_excel_document`

Édite un `.xlsx` existant. Liste d'opérations appliquées en séquence.

| Param | Type | Requis | Limites |
|-------|------|--------|---------|
| `filename` | string | ✅ | fichier dans `OUTPUT_PATH` |
| `operations` | EditOp[] | ✅ | 1 à 100 |

**13 opérations** (champ `op` discriminant) : `update_cells`, `insert_rows`, `delete_rows`, `apply_styles`, `add_sheet`, `delete_sheet`, `rename_sheet`, `add_chart`, `remove_charts`, `add_data_validation`, `merge_cells`, `unmerge_cells`, `set_sheet_properties`. Détails : [generation-guide.md](generation-guide.md).

Retour : `operations_applied`, `operations_skipped`, `file_size_bytes`. Les erreurs de graphique sont non bloquantes (`skipped`).

### `create_word_document`

Crée un `.docx` à partir de Markdown.

| Param | Type | Requis | Limites |
|-------|------|--------|---------|
| `filename` | string | ✅ | doit finir par `.docx` |
| `content` | string | ✅ | Markdown, max 500 000 chars |
| `title` | string | | max 255 chars |
| `author` | string | | max 255 chars |

Markdown supporté : headings (`#`-`######`), `**bold**`, `*italic*`, listes à puces / numérotées (imbriquables), tables, blocs de code (` ``` `), citations (`>`), saut de page (`---`).

Retour : `file_path`, `filename`, `file_size_bytes`, `overwritten`.

### `inspect_generated_file`

| Param | Type | Description |
|-------|------|-------------|
| `filename` ✅ | string | Fichier dans `OUTPUT_PATH` |
| `max_rows_per_sheet` | int | Excel : 1-100, défaut 10 |

Retour : `filename`, `type`, `editable_with`, `sheets[]` (name, headers, sample_data, formulas, charts, merged_cells, column_widths, freeze_panes). **Workflow** : `list_available_documents(source='generated')` → `inspect_generated_file` → `edit_excel_document`.

## Codes d'erreur

| HTTP | JSON-RPC | Sens |
|------|----------|------|
| 400 | -32600 | Requête invalide |
| 404 | — | Non trouvé |
| 413 | — | Fichier trop volumineux |
| 422 | -32602 | Validation Pydantic / params invalides |
| 429 | — | Rate limit |
| 500 | -32603 | Erreur interne |
| — | -32601 | Méthode JSON-RPC inconnue |

### Format d'erreur MCP (LLM-aware)

```
ERROR [PDF_NOT_FOUND]: Fichier PDF introuvable: /bad/path.pdf
SUGGESTION: Vérifier le chemin. Utiliser un chemin absolu.
PARAMETER: file_path
RETRY: True
```

Pour les `ValidationError` Pydantic, des **hints contextuels** sont ajoutés (liste des `op` valides pour `edit_excel_document`, rappel du format `chart`, etc.).
