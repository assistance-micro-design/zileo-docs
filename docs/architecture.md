# Architecture

Serveur FastAPI exposant 12 outils MCP via JSON-RPC 2.0 (`POST /mcp`) et une API REST. Indexe des documents (PDF, Excel, Word) dans Qdrant via embeddings Mistral, puis les retrouve par recherche hybride (dense + BM25 sparse).

## Pipeline de traitement

```
Document (PDF/Excel/Word)
        |
        v
+-----------------------+
| DocumentRouter        |  detect_type() via extension
+-----------------------+
   |          |         |
   v          v         v
+------+  +-------+  +------+
| PDF  |  | Excel |  | Word |
+------+  +-------+  +------+
   |          |         |
   v          v         v
+--------------------------------+
| Chunks (SmartChunker / unifie) |
+--------------------------------+
        |
        v
+--------------------------------+
| Embeddings dense + sparse      |  Mistral (1024d) + fastembed BM25
+--------------------------------+
        |
        v
+--------------------------------+
| Qdrant collection "documents"  |  named vectors: text + bm25
+--------------------------------+
```

## Pipeline PDF (`PDFPipelineOrchestrator`)

| Phase | Composant | Rôle |
|-------|-----------|------|
| 1 | `DocumentAnalyzer` | Classifie chaque page (texte, tables, images, scan) |
| 2 | `NativeContentExtractor` | Texte natif via PyMuPDF4LLM (gratuit) |
| 3 | `MistralOCRProcessor` | OCR pour pages complexes (payant) |
| 4 | `SmartChunker` + `MistralEmbedder` | Découpe + embeddings dense |
| 5 | `SparseEmbedder` | Embeddings BM25 (en parallèle) |
| 6 | `QdrantVectorStore` | Stockage avec metadata |

### Classification des pages PDF

| Type | Critère | Extraction |
|------|---------|------------|
| `TEXT_ONLY` | Texte natif suffisant, pas d'images significatives | PyMuPDF4LLM |
| `HAS_TABLES` | Tables détectées | Mistral OCR |
| `HAS_IMAGES` | Images > 5% de la page | Mistral OCR |
| `HAS_CHARTS` | > 50 dessins vectoriels et peu de texte | Mistral OCR |
| `SCANNED` | Pas de texte natif, image > 80% | Mistral OCR |
| `MIXED` | Tables + images | Mistral OCR |

Seuils dans `DocumentAnalyzer` : `MIN_TEXT_FOR_NATIVE=50`, `SIGNIFICANT_IMAGE_RATIO=0.05`, `CHART_DRAWING_THRESHOLD=50`.

## Pipeline Excel / Word (unifié)

```
ExcelExtractor / WordExtractor
        |
        v
UnifiedDocument (content_markdown + structured_data)
        |
        v
IndexDocumentTool._create_chunks_from_unified()
        |
        v
[main chunk (8000 chars), overflow chunks (4000 chars + 200 overlap), formula chunk (Excel, max 50 formules)]
```

Chunking simple, basé sur la taille en caractères. Pas d'analyse Markdown, pas de régions protégées (contrairement au PDF).

## Recherche

Deux tools MCP dédiés (depuis 0.3.0) héritent de `BaseSearchTool(VectorStoreMCPTool)` :

| Tool | Comportement | Garde-fou |
|------|--------------|-----------|
| `search_hybrid` | Prefetch Qdrant natif : dense (Mistral) + sparse (BM25), fusion RRF | `min_cosine_relevance` opt-in (calibre empirique 0.72 — anti hors-domaine) |
| `search_semantic` | Vecteur dense seul (cosine similarity) | `score_threshold` (défaut 0.7) |

L'API REST `POST /api/v1/search` conserve le paramètre `search_mode` (asymétrie REST/MCP volontaire : REST = bas niveau, MCP = orientée agent).

Filtres Qdrant communs : `document_id`, `doc_filename`, `document_type`, `has_table`, `has_image`, `has_formula`, `text_search`, `sheet_name`.

## Outils MCP (13)

Tous héritent de `BaseMCPTool` (`src/mcp/tools/base.py`). Les outils ayant besoin de Qdrant héritent de `VectorStoreMCPTool`. Toutes les dépendances (vector store, embedder, sparse embedder) sont injectées par `MCPServer.__init__()`.

### Indexation et recherche

| Outil | Classe parente | Rôle |
|-------|----------------|------|
| `index_document` | `BaseMCPTool` | Indexer PDF/Excel/Word (DI complète) |
| `search_hybrid` | `BaseSearchTool` | Recherche hybride (dense+BM25 RRF) + garde-fou cosinus |
| `search_semantic` | `BaseSearchTool` | Recherche sémantique pure (cosinus dense, défaut 0.7) |
| `get_document` | `VectorStoreMCPTool` | Métadonnées + aperçu chunks |
| `delete_document` | `VectorStoreMCPTool` | Supprimer de l'index (pas du disque) |
| `list_indexed_documents` | `VectorStoreMCPTool` | Lister documents indexés |
| `read_document_content` | `VectorStoreMCPTool` | Contenu Markdown reconstitué |
| `get_excel_formulas` | `VectorStoreMCPTool` | Formules d'un Excel indexé |

### Génération et édition

| Outil | Classe parente | Rôle |
|-------|----------------|------|
| `create_excel_document` | `BaseMCPTool` | Créer .xlsx (data, styles, charts, validations) |
| `edit_excel_document` | `BaseMCPTool` | Éditer .xlsx (13 opérations) |
| `create_word_document` | `BaseMCPTool` | Créer .docx depuis Markdown |

### Utilitaires

| Outil | Classe parente | Rôle |
|-------|----------------|------|
| `list_available_documents` | `BaseMCPTool` | Lister fichiers (sources `documents` ou `generated`) |
| `inspect_generated_file` | `BaseMCPTool` | Inspecter structure Excel généré |

## Sécurité

- **Path traversal** : `Path.resolve().is_relative_to(DOCUMENTS_PATH)` sur tout accès fichier (`index_document`, `list_available_documents`)
- **Magic numbers** : `validate_file_magic()` vérifie `%PDF-`, `PK\x03\x04` avant traitement
- **Hash dedup** : `compute_file_hash()` SHA-256 stocké dans `UnifiedMetadata.file_hash` pour détecter doublons et fichiers modifiés
- **Excel injection** : `ExcelGenerator.check_cell_value_safety()` bloque `=DDE`, `=CMD`, `=SYSTEM`, `=EXEC`, `=CALL`, `=REGISTER`, `+cmd|`, `-cmd|`, `@...cmd|`
- **Rate limiting** : `slowapi` — `/mcp` (30/min), `/api/v1/documents/index` (10/min), `/api/v1/search` (30/min)
- **Validation** : tous les inputs validés via Pydantic

## Erreurs

Toutes les erreurs métier héritent de `MCPZileoError` et exposent `to_llm_format()` pour des réponses MCP guidant le LLM (code, message, suggestion, retry).

```
MCPZileoError
├── PDFError (SourceFileNotFoundError, PDFCorruptedError, PDFTooLargeError, PDFTooManyPagesError)
├── OCRError (OCRAPIError, OCRRateLimitError)
├── EmbeddingError (EmbeddingAPIError)
├── VectorStoreError (VectorStoreConnectionError, CollectionNotFoundError, DocumentNotFoundError)
├── ExcelGenerationError (ExcelOutputTooLargeError, ExcelChartError, ExcelFileNotFoundError, ...)
├── ValidationError (EmptyQueryError)
└── NoResultsError
```

`MCPServer._format_validation_error()` intercepte aussi les `pydantic.ValidationError` avec hints contextuels (ex: liste des `op` valides pour `edit_excel_document`).

## Services externes

| Service | Modèle | Usage |
|---------|--------|-------|
| Mistral OCR | `mistral-ocr-latest` | Pages PDF complexes (~$2 / 1000 pages) |
| Mistral Embed | `mistral-embed` (1024d) | Embeddings dense (~$0.10 / M tokens) |
| Qdrant | local | Vecteurs + payload + sparse BM25 |
| fastembed | `Qdrant/bm25` | Sparse embeddings (local, gratuit) |

## Structure du projet

```
src/
├── main.py                         # FastAPI app + endpoint /mcp
├── core/
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── exceptions.py               # Hierarchie MCPZileoError
│   ├── file_validation.py          # validate_file_magic, compute_file_hash
│   └── logging.py                  # structlog config
├── api/routes/                     # health, documents, search
├── mcp/
│   ├── server.py                   # MCPServer (router JSON-RPC)
│   └── tools/                      # 12 outils
├── services/
│   ├── pipeline/orchestrator.py    # PDFPipelineOrchestrator
│   ├── pdf/                        # analyzer, native_extractor, ocr_processor
│   ├── chunking/chunker.py         # SmartChunker (PDF)
│   ├── embedding/                  # mistral_embedder, sparse_embedder
│   ├── vector/qdrant_store.py      # QdrantVectorStore (named vectors)
│   ├── document/router.py          # DocumentRouter (multi-format)
│   ├── excel/                      # extractor, generator, editor
│   ├── word/                       # extractor, generator
│   └── inspection/file_inspector.py
└── models/                         # 15 schemas Pydantic
```
