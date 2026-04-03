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
| `tools/list` | Lister les 11 outils disponibles avec leurs schemas |
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

Liste les fichiers disponibles dans le projet. Supporte 2 sources differentes.

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `source` | string | Non | `documents` (defaut), `generated` |
| `type_filter` | string | Non | `pdf`, `excel`, `word` ou `all` (defaut: all) |
| `subdirectory` | string | Non | Sous-dossier relatif a explorer |
| `recursive` | boolean | Non | Explorer recursivement (defaut: true) |

**Sources** :
- `documents` : Fichiers PDF/Excel/Word a indexer (dans `DOCUMENTS_PATH`)
- `generated` : Fichiers crees par `create_excel_document` (dans `OUTPUT_PATH`)

Retour : `source`, `base_path`, `total_files`, `by_type` (comptage par format), `files` (liste avec `filename`, `path`, `relative_path`, `type`, `size_mb`, `extension` et champs contextuels `editable_with`).

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

#### create_excel_document

Cree un fichier Excel (.xlsx) avec donnees, styles, graphiques et validations de donnees. Le fichier est cree dans `OUTPUT_PATH`.

**Parametres** :

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `filename` | string | Oui | Nom du fichier (doit se terminer par `.xlsx`) |
| `sheets` | array[SheetDef] | Oui | Definitions des feuilles (1 a 50) |
| `author` | string | Non | Auteur du classeur (metadonnee) |

**Structure d'une feuille (SheetDef)** :

| Champ | Type | Description |
|-------|------|-------------|
| `name` | string | Nom de la feuille (1-31 caracteres) |
| `headers` | array[string] | En-tetes de colonnes |
| `rows` | array[array] | Lignes de donnees (max 10 000) |
| `styles` | array[CellStyleDef] | Styles (police, couleur, bordure) |
| `charts` | array[ChartDef] | Graphiques (type requis: bar\|line\|pie\|scatter\|area\|column) |
| `data_validations` | array | Regles de validation |
| `merged_cells` | array | Cellules a fusionner |
| `column_widths` | object | Largeurs de colonnes (`{"A": 20}`) |
| `auto_filter` | boolean | Activer l'auto-filtre |
| `freeze_panes` | string | Figer les volets (`"A2"`) |

**Exemple** :

```json
{
  "filename": "report.xlsx",
  "sheets": [
    {
      "name": "Data",
      "headers": ["Name", "Value"],
      "rows": [["Item A", 100], ["Item B", 200]],
      "charts": [
        {
          "type": "bar",
          "data_range": "B1:B3",
          "categories_range": "A2:A3",
          "title": "Values"
        }
      ]
    }
  ]
}
```

**Retour** :

```json
{
  "file_path": "/app/output/report.xlsx",
  "filename": "report.xlsx",
  "sheets_created": 1,
  "total_rows": 2,
  "total_charts": 1,
  "file_size_bytes": 8542,
  "overwritten": false
}
```

#### edit_excel_document

Edite un fichier Excel (.xlsx) existant dans `OUTPUT_PATH`. Le fichier doit avoir ete cree par `create_excel_document`. Chaque operation doit avoir un champ `op` qui determine le type d'operation.

**Parametres** :

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `filename` | string | Oui | Nom du fichier existant dans OUTPUT_PATH |
| `operations` | array[EditOp] | Oui | Operations a appliquer en ordre (1 a 100) |

**Operations disponibles (champ `op`)** :

| Op | Description | Champs principaux |
|----|-------------|-------------------|
| `update_cells` | Modifier des cellules | `sheet`, `cells` (`{"A1": 42, "B1": "hello"}`) |
| `insert_rows` | Inserer des lignes | `sheet`, `row_index`, `rows` |
| `delete_rows` | Supprimer des lignes | `sheet`, `start_row`, `end_row` |
| `apply_styles` | Appliquer des styles | `sheet`, `styles` (liste de CellStyleDef) |
| `add_sheet` | Ajouter une feuille | `name`, `headers`, `rows` |
| `delete_sheet` | Supprimer une feuille | `sheet` |
| `rename_sheet` | Renommer une feuille | `sheet`, `new_name` |
| `add_chart` | Ajouter un graphique | `sheet`, `chart` (ChartDef) |
| `remove_charts` | Supprimer tous les graphiques | `sheet` |
| `add_data_validation` | Ajouter une validation | `sheet`, `validation` |
| `merge_cells` | Fusionner des cellules | `sheet`, `range` |
| `unmerge_cells` | Defusionner des cellules | `sheet`, `range` |
| `set_sheet_properties` | Proprietes de feuille | `sheet`, `tab_color`, `auto_filter`, `freeze_panes` |

**Exemple** :

```json
{
  "filename": "report.xlsx",
  "operations": [
    {"op": "update_cells", "sheet": "Sheet1", "cells": {"A1": 42, "B1": "hello"}},
    {
      "op": "add_chart",
      "sheet": "Sheet1",
      "chart": {"type": "bar", "data_range": "A1:B5", "title": "Sales"}
    },
    {"op": "delete_rows", "sheet": "Sheet1", "start_row": 10, "end_row": 12}
  ]
}
```

**Retour** :

```json
{
  "file_path": "/app/output/report.xlsx",
  "filename": "report.xlsx",
  "operations_applied": 3,
  "operations_skipped": 0,
  "file_size_bytes": 9120
}
```

**Note** : Les erreurs de graphique (ChartDef invalide) sont gerees en degradation gracieuse : l'operation est comptee comme `skipped` et les autres operations continuent.

#### inspect_generated_file

Inspecte la structure d'un fichier Excel cree par `create_excel_document`. Retourne la structure dans le vocabulaire des tools d'edition pour permettre la construction directe d'operations.

**Parametres** :

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `filename` | string | Oui | Nom du fichier dans OUTPUT_PATH (.xlsx) |
| `max_rows_per_sheet` | integer | Non | Excel : nombre max de lignes a afficher par feuille (1-100, defaut: 10) |

**Retour** : `filename`, `type`, `editable_with`, `sheets` (avec `name`, `headers`, `sample_data`, `formulas`, `charts`, `merged_cells`, `column_widths`, `freeze_panes`).

**Workflow recommande** : `list_available_documents(source='generated')` → `inspect_generated_file` → `edit_excel_document`.

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

Ce format est genere par la hierarchie d'exceptions `MCPZileoError` dans `src/core/exceptions.py`. Chaque exception porte un code, un message, une suggestion, et un indicateur de retry.

### Format d'erreur de validation

Les erreurs de validation Pydantic (`ValidationError`) sont interceptees et formatees avec des hints contextuels pour guider le LLM :

```
ERROR [VALIDATION_ERROR]: 2 erreur(s) de validation.
  - operations -> 0: Unable to extract tag using discriminator 'op'
  - operations -> 1: Unable to extract tag using discriminator 'op'
RETRY: Corriger et reessayer.
HINT: Chaque operation doit avoir un champ 'op'.
Available 'op' values: update_cells, insert_rows, delete_rows, apply_styles, ...
Example update_cells: {"op": "update_cells", "sheet": "Sheet1", "cells": {"A1": 42}}.
```

Les hints sont contextuels :
- **Discriminated union** (`edit_excel_document`) : Liste les valeurs `op` valides avec exemples
- **Charts** (`create_excel_document`) : Rappelle que `type` et `data_range` sont requis
