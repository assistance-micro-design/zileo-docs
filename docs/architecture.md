# Architecture

## Vue d'ensemble

MCP Zileo RAG est un serveur FastAPI qui expose des outils via JSON-RPC 2.0 (protocole MCP). Il extrait le contenu de documents PDF, Excel et Word, le decoupe en chunks, genere des embeddings via Mistral, et stocke le tout dans Qdrant pour la recherche semantique.

Le serveur MCP est une implementation custom de JSON-RPC 2.0. Il n'utilise pas le SDK MCP officiel pour le serveur — le package `mcp` est installe comme dependance mais le routing JSON-RPC est fait manuellement dans `MCPServer`.

## Composants

### Points d'entree

- `POST /mcp` — Endpoint JSON-RPC 2.0 principal (rate limited a 30/minute)
- `GET /api/v1/*` — API REST pour l'indexation, la recherche et la gestion de documents
- `GET /health/*` — Health checks (liveness, readiness)
- `GET /` — Info service

### Pipeline de traitement

```
Document (PDF/Excel/Word)
        |
        v
+-----------------------+
| Detection du format   |  DocumentRouter.detect_type()
+-----------------------+
   |          |         |
   v          v         v
+------+  +-------+  +------+
| PDF  |  | Excel |  | Word |
+------+  +-------+  +------+
   |          |         |
   v          v         v
+-----------------------+
| Chunks + Embeddings   |  Mistral embed (1024 dim)
+-----------------------+
        |
        v
+-----------------------+
| Qdrant                |  Collection "documents"
+-----------------------+
```

La collection Qdrant s'appelle `documents` et stocke les embeddings de tous les formats (PDF, Excel, Word).

### Pipeline PDF (5 phases)

| Phase | Composant | Role |
|-------|-----------|------|
| 1 | `DocumentAnalyzer` | Ouvre le PDF, classifie chaque page (texte pur, tableaux, images, scan) |
| 2 | `NativeContentExtractor` | Extrait le texte des pages simples via PyMuPDF4LLM (gratuit) |
| 3 | `MistralOCRProcessor` | Envoie les pages complexes a l'API OCR Mistral (payant) |
| 4 | `SmartChunker` + `MistralEmbedder` | Decoupe le contenu et genere les embeddings |
| 5 | `QdrantVectorStore` | Stocke les chunks avec metadata dans Qdrant |

Le pipeline PDF est coordonne par `PDFPipelineOrchestrator`.

### Pipeline Excel / Word

Pour Excel et Word, le pipeline est plus simple :
1. `ExcelExtractor` ou `WordExtractor` extrait le contenu
2. Conversion en `UnifiedDocument` (format commun)
3. `IndexDocumentTool` cree les chunks directement (pas via `SmartChunker`)
4. Embedding et stockage dans Qdrant

Le chunking Excel/Word est fait dans `IndexDocumentTool` avec une logique specifique : chunk principal de 8000 caracteres, chunks de debordement de 4000 caracteres, chunk de formules separe (max 50 formules).

### Classification des pages PDF

L'analyseur classifie chaque page selon des heuristiques :

| Type | Critere | Extraction |
|------|---------|------------|
| TEXT_ONLY | Texte natif suffisant, pas d'images significatives | PyMuPDF4LLM |
| HAS_TABLES | Tables detectees | Mistral OCR |
| HAS_IMAGES | Images couvrant >20% de la page | Mistral OCR |
| HAS_CHARTS | >50 dessins vectoriels et peu de texte | Mistral OCR |
| SCANNED | Pas de texte natif, image >80% de la page | Mistral OCR |
| MIXED | Tables et images presentes | Mistral OCR |

Seuils configures en constantes dans `DocumentAnalyzer` : `MIN_TEXT_FOR_NATIVE=50`, `SIGNIFICANT_IMAGE_RATIO=0.05`, `CHART_DRAWING_THRESHOLD=50`.

### Chunking

Le `SmartChunker` decoupe le contenu en chunks de `CHUNK_SIZE` tokens (defaut 512) avec un overlap de `CHUNK_OVERLAP` tokens (defaut 50).

Comportement :
- Les tableaux, blocs de code et equations LaTeX sont identifies comme "regions protegees" et ne sont jamais coupes
- Les headers Markdown declenchent des limites de chunks
- Chaque chunk recoit un `content_with_context` qui prepend la hierarchie de sections pour ameliorer la qualite des embeddings
- Le comptage de tokens utilise tiktoken (`cl100k_base`)

Le chunking est base sur la structure Markdown (headers). Il n'y a pas d'analyse semantique du contenu.

## Architecture des outils MCP

### BaseMCPTool

Tous les outils heritent de `BaseMCPTool` :

```python
class BaseMCPTool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]

    async def execute(self, arguments) -> dict[str, Any]:
        await self._ensure_initialized()
        return await self._do_execute(arguments)
```

`VectorStoreMCPTool` est une sous-classe qui injecte automatiquement un `QdrantVectorStore`.

### Injection de dependances

`MCPServer` cree une instance partagee de `QdrantVectorStore` et `MistralEmbedder`, et les injecte dans les outils qui en ont besoin.

**Exception** : `IndexDocumentTool` ne suit pas ce pattern. Il cree ses propres instances dans son `__init__`. C'est une inconsistance connue.

### Liste des outils

| Outil | Classe parente | Dependances injectees |
|-------|----------------|----------------------|
| `index_document` | `BaseMCPTool` | Aucune (cree ses propres instances) |
| `search_documents` | `VectorStoreMCPTool` | VectorStore, Embedder |
| `get_document` | `VectorStoreMCPTool` | VectorStore |
| `delete_document` | `VectorStoreMCPTool` | VectorStore |
| `list_indexed_documents` | `VectorStoreMCPTool` | VectorStore |
| `list_available_documents` | `BaseMCPTool` | Aucune (acces filesystem) |
| `get_excel_formulas` | `VectorStoreMCPTool` | VectorStore |
| `read_document_content` | `VectorStoreMCPTool` | VectorStore |
| `create_excel_document` | `BaseMCPTool` | Aucune (ExcelGenerator interne) |
| `edit_excel_document` | `BaseMCPTool` | Aucune (ExcelEditor interne) |
| `inspect_generated_file` | `BaseMCPTool` | Aucune (FileInspector interne) |

### Securite

- **Path traversal** : `IndexDocumentTool` et `ListAvailableDocumentsTool` verifient que les chemins restent dans `DOCUMENTS_PATH` via `Path.is_relative_to()`
- **Rate limiting** : slowapi applique des limites sur `/mcp` (30/min), l'indexation (10/min), et la recherche (30/min)
- **Validation** : Les parametres MCP sont valides via des modeles Pydantic dedies

## Services externes

| Service | Usage | Cout |
|---------|-------|------|
| Mistral OCR (`mistral-ocr-latest`) | OCR des pages PDF complexes | ~$2/1000 pages |
| Mistral Embed (`mistral-embed`) | Embeddings 1024 dimensions | ~$0.10/million tokens |
| Qdrant | Stockage vectoriel, recherche par similarite | Auto-heberge (gratuit) |

## Gestion des erreurs

Les erreurs heritent de `MCPZileoError` et fournissent un format `to_llm_format()` pour les reponses MCP. Ce format inclut un code d'erreur, un message, une suggestion d'action corrective, et un indicateur de retry.

Hierarchie :
```
MCPZileoError
  +-- PDFError (SourceFileNotFoundError, PDFCorruptedError, PDFTooLargeError, PDFTooManyPagesError)
  +-- OCRError (OCRAPIError, OCRRateLimitError)
  +-- EmbeddingError (EmbeddingAPIError)
  +-- VectorStoreError (VectorStoreConnectionError, CollectionNotFoundError, DocumentNotFoundError)
  +-- ExcelGenerationError (ExcelOutputTooLargeError, ExcelChartError, ExcelFileNotFoundError, ExcelSheetNotFoundError)
  +-- ValidationError (EmptyQueryError)
  +-- NoResultsError
```

Les erreurs Pydantic (`ValidationError`) sont egalement interceptees dans `MCPServer._format_validation_error()` avec des hints contextuels pour guider le LLM.

## Structure du projet

```
src/
+-- main.py                     # FastAPI app, endpoint /mcp, lifecycle
+-- core/
|   +-- config.py               # Settings (pydantic-settings)
|   +-- exceptions.py           # Hierarchie d'erreurs
|   +-- logging.py              # Configuration structlog
+-- api/
|   +-- dependencies.py         # DI FastAPI (get_orchestrator, etc.)
|   +-- routes/
|       +-- health.py           # /health, /health/live, /health/ready
|       +-- documents.py        # /api/v1/documents/*
|       +-- search.py           # /api/v1/search
+-- mcp/
|   +-- server.py               # MCPServer (routeur JSON-RPC)
|   +-- types.py                # RequestId TypeAlias
|   +-- tools/
|       +-- base.py             # BaseMCPTool, VectorStoreMCPTool
|       +-- index_document.py
|       +-- search.py
|       +-- get_document.py
|       +-- delete_document.py
|       +-- list_indexed_documents.py
|       +-- list_available_documents.py
|       +-- get_excel_formulas.py
|       +-- read_document_content.py
|       +-- create_excel.py      # Cree un fichier Excel
|       +-- edit_excel.py        # Edite un fichier Excel existant
|       +-- inspect_generated_file.py # Inspecte structure Excel
+-- services/
|   +-- pipeline/orchestrator.py  # PDFPipelineOrchestrator
|   +-- pdf/
|   |   +-- analyzer.py          # Classification des pages
|   |   +-- native_extractor.py   # Extraction PyMuPDF4LLM
|   |   +-- ocr_processor.py     # OCR via API Mistral
|   +-- chunking/chunker.py      # SmartChunker
|   +-- embedding/mistral_embedder.py
|   +-- vector/qdrant_store.py   # QdrantVectorStore
|   +-- document/router.py       # DocumentRouter (multi-format)
|   +-- excel/extractor.py       # ExcelExtractor (lecture/indexation)
|   +-- excel/generator.py      # ExcelGenerator (creation .xlsx)
|   +-- excel/editor.py         # ExcelEditor (edition .xlsx existant)
|   +-- inspection/
|   |   +-- file_inspector.py   # FileInspector (inspection Excel)
|   +-- word/extractor.py        # WordExtractor
+-- models/
    +-- document.py    # DocumentMetadata, PageAnalysis, PageType
    +-- extraction.py  # ExtractedContent, OCRResult, TableData, etc.
    +-- chunk.py       # ChunkMetadata, DocumentChunk
    +-- unified.py     # UnifiedDocument, UnifiedMetadata, DocumentType
    +-- excel.py            # ExcelDocument, ExcelSheet, ExcelCell, ExcelFormula
    +-- excel_generation.py # SheetDef, ChartDef, CellStyleDef, DataValidationDef
    +-- excel_edit.py       # EditOp (discriminated union de 13 operations)
    +-- word.py             # WordDocument, WordParagraph, WordTable, ContentBlock
    +-- search.py           # SearchQuery, SearchFilters, SearchResponse
    +-- api.py              # Pydantic models pour parametres MCP et reponses REST
    +-- types.py            # TypeAlias partages (CellValue, FormulaResult)
```
