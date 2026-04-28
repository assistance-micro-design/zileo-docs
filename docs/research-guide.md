# Guide de recherche

Workflows pour indexer, rechercher et lire des documents (PDF, Excel, Word) via les outils MCP. Pour les schémas complets, voir [api-reference.md](api-reference.md).

## Workflow général

```
1. list_available_documents     → Quels fichiers sont disponibles ?
2. list_indexed_documents       → Quels documents sont déjà indexés ?
3. index_document (si besoin)   → Indexer ce qui ne l'est pas
4. search_documents             → Trouver les passages pertinents
5. read_document_content        → Lire le contexte complet
6. get_excel_formulas           → (Excel) Récupérer formules + résultats
```

## Lister les fichiers disponibles

```json
{"source": "documents", "type_filter": "all"}
```

| Param | Type | Défaut | Valeurs |
|-------|------|--------|---------|
| `source` | string | `documents` | `documents` (DOCUMENTS_PATH) ou `generated` (OUTPUT_PATH) |
| `type_filter` | string | `all` | `pdf`, `excel`, `word`, `all` |
| `subdirectory` | string | `""` | Sous-dossier relatif |
| `recursive` | bool | `true` | Récursif |

## Vérifier ce qui est déjà indexé (avant d'indexer)

`list_indexed_documents` ne prend aucun paramètre. **Toujours l'appeler avant `index_document`** pour éviter les doublons.

`index_document` est de toute façon idempotent :
- Si le filename existe déjà avec le même hash → retourne l'`already_indexed: true` + ID existant
- Si le filename existe mais hash différent → retourne `file_modified: true` (à toi de `delete_document` puis ré-indexer)

## Indexer un document

```json
{"file_path": "/app/documents/rapport.pdf"}
```

| Param | Type | Notes |
|-------|------|-------|
| `file_path` | string | Chemin absolu, doit être dans `DOCUMENTS_PATH` |
| `force_ocr` | bool | PDF uniquement |
| `sheets` | string[] | Excel : limiter à certaines feuilles |
| `table_format` | string | `markdown` (défaut) ou `html` |

Retour : `document_id`, `document_type`, `chunks_stored`, `has_tables`, `has_formulas`, `has_images`, `processing_time_seconds`.

## Recherche : `search_documents`

### Modes de recherche

| Mode | Comportement | `score_threshold` |
|------|--------------|-------------------|
| `hybrid` (défaut) | Vecteur dense (Mistral) + sparse BM25, fusion RRF native Qdrant | Ignoré (échelles différentes) |
| `semantic` | Vecteur dense seul (cosine similarity) | Appliqué (0.0-1.0) |

`hybrid` est plus robuste pour les requêtes mixant concepts et noms exacts. `semantic` est utile quand on veut filtrer strictement sur la similarité conceptuelle.

### Paramètres

```json
{
  "query": "prévisions chiffre d'affaires 2026",
  "top_k": 5,
  "score_threshold": 0.7,
  "search_mode": "hybrid",
  "filters": {"document_type": "pdf", "has_table": true}
}
```

| Param | Défaut | Description |
|-------|--------|-------------|
| `query` | — | Requête en langage naturel (obligatoire) |
| `top_k` | 5 | 1-100 |
| `score_threshold` | 0.7 | Mode `semantic` uniquement |
| `search_mode` | `hybrid` | `hybrid` ou `semantic` |
| `filters` | — | Voir ci-dessous |

### Filtres

| Filtre | Type | Usage |
|--------|------|-------|
| `document_id` | string | Restreindre à un document |
| `doc_filename` | string | Filtrer par nom de fichier |
| `document_type` | string | `pdf`, `excel`, `word` |
| `has_table` | bool | Passages avec tableaux |
| `has_image` | bool | Passages avec images |
| `has_formula` | bool | Excel : passages avec formules |
| `text_search` | string | Recherche full-text exacte (en plus du vecteur) |
| `sheet_name` | string | Excel : filtrer par feuille |

### Conseils

| Situation | Approche |
|-----------|----------|
| Question précise | `"taux de marge brute Q3"` |
| Thème général | `"politique de rémunération"` |
| Données chiffrées | `has_table: true` ou `has_formula: true` |
| Document spécifique | `document_id` ou `doc_filename` |
| Excel : feuille connue | `sheet_name` + `document_type: "excel"` |
| Noms propres dans Excel | `search_mode: "hybrid"` (défaut) ou bien `semantic` avec `score_threshold: 0.3` + `text_search` |

### Réglage `score_threshold` (mode `semantic`)

| Seuil | Usage |
|-------|-------|
| 0.8 - 1.0 | Haute précision, peu de résultats |
| 0.7 (défaut) | Équilibre |
| 0.5 - 0.7 | Recherche exploratoire |
| < 0.5 | Trop de bruit (rarement utile) |

## Lire le contenu : `read_document_content`

```json
{"document_id": "abc123", "page_start": 5, "page_end": 10}
```

| Param | Type | Description |
|-------|------|-------------|
| `document_id` | string | Obligatoire |
| `page_start` | int | Page début (1-indexed) |
| `page_end` | int | Page fin (1-indexed) |
| `include_chunks_detail` | bool | Métadonnées chunks (défaut `false`) |

| Cas | Paramètres |
|-----|------------|
| Petit doc (< 5 pages) | Aucun (lire tout) |
| Page trouvée par search | `page_start: 12, page_end: 12` |
| Section | `page_start: 5, page_end: 10` |
| Table des matières | `page_start: 1, page_end: 3` |

## Métadonnées : `get_document`

```json
{"document_id": "abc123"}
```

Retourne : `filename`, `title`, `author`, `total_pages`, `total_chunks`, `total_tokens`, `content_types`, `ingested_at`, `file_hash`, aperçu des chunks. Utile pour **évaluer la taille** avant de choisir une stratégie de lecture.

## Formules Excel : `get_excel_formulas`

```json
{"document_id": "abc123", "sheet": "Ventes", "cell_range": "A1:D10"}
```

Retour : `total_formulas`, `formulas[]` (`sheet`, `cell`, `formula`, `result`).

## Suppression : `delete_document`

Supprime de l'index Qdrant uniquement. **Ne touche pas au fichier source.** Utile pour ré-indexer après modification.

```json
{"document_id": "abc123"}
```

## Stratégie selon la taille

| Taille | Pages | Stratégie |
|--------|-------|-----------|
| Petit | 1-5 | `read_document_content` complet |
| Moyen | 6-50 | `search_documents` (top_k=10) → `read_document_content` ciblé |
| Grand | 51+ | `search_documents` uniquement, lire 3 pages autour des hits (score ≥ 0.85) |

Toujours appeler `get_document` d'abord pour connaître `total_pages`.

## Workflow type — résumer un document

```
1. list_indexed_documents       → vérifier si déjà indexé
2. index_document (si besoin)   → indexer
3. get_document                 → connaître la taille
4. (selon taille)
   - Petit : read_document_content (tout)
   - Moyen/grand : search_documents("résumé objectifs conclusions") + read_document_content sur les hits
5. Synthétiser
```

## Workflow type — recherche thématique

```
1. search_documents(query, top_k=10)
2. Pour chaque hit (score ≥ 0.8) :
   read_document_content(document_id, page_start=p, page_end=p+1)
3. Synthétiser avec sources (document, page)
```

## Workflow type — analyse Excel

```
1. index_document (si besoin)
2. get_document → identifier les feuilles
3. read_document_content → tableaux en Markdown
4. get_excel_formulas → formules + résultats calculés
5. Calculs dérivés (côté client) : pourcentages, écarts, projections
```
