# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-05-16

### BREAKING CHANGES
- **Project renamed from `mcp-zileo-rag` to `zileo-docs`**. The new name reflects the full scope (RAG indexing/search + document generation), and the `mcp-` prefix is dropped (redundant).
- Python package name: `mcp-zileo-rag` -> `zileo-docs` (PyPI distribution name).
- `APP_NAME` env/setting default: `"MCP Zileo RAG"` -> `"Zileo Docs"`.
- Exception class `MCPZileoError` -> `ZileoDocsError` (subclass hierarchy unchanged).
- Docker container names: `mcp-zileo-rag` -> `zileo-docs`, `mcp-zileo-rag-qdrant` -> `zileo-docs-qdrant`. Docker Compose `name:` fixed at `zileo-docs` (decouples from project directory name).
- MCP client config key renamed in examples (`zileo-rag` -> `zileo-docs`). Existing client configs must be updated.
- GitHub repository URL: `assistance-micro-design/mcp-zileo-rag` -> `assistance-micro-design/zileo-docs`.

### Security
- CORS middleware removed in production mode (`allow_origins=[]` was ambiguous — a technical config active without any whitelisted domain)
- Rate limiting extended to `GET/DELETE /api/v1/documents/{id}`, `GET /api/v1/documents`, `GET /health` (`RATE_LIMIT_DEFAULT`); `/health/live` and `/health/ready` deliberately remain unauthenticated (Kubernetes/Docker probes)
- Lifespan fail-fast: `MCPServer.initialize()` no longer swallows errors silently (a Qdrant outage or misconfigured Mistral now prevents startup)
- Anti-DoS variables exposed: `MISTRAL_TIMEOUT_S` and `MAX_DECOMPRESSED_MB` documented in `.env.example` and `docker-compose.yml`
- `_orchestrator_error_to_http` no longer leaks `str(exc)` to the client: unknown exceptions are logged server-side and the client receives `"Internal server error"`

### Quality
- **BREAKING (LLM-side)**: `extra="forbid"` applied to all 10 MCP `*Params` models (`GetDocumentParams`, `DeleteDocumentParams`, `ReadDocumentContentParams`, `UnifiedIndexDocumentParams`, `GetExcelFormulasParams`, `CreateExcelParams`, `EditExcelParams`, `CreateWordParams`, `ListAvailableDocumentsParams`, `InspectGeneratedFileParams`). A client sending an unknown field now receives `VALIDATION_ERROR` instead of silent acceptance.
- `model_config` unified via typesafe `ConfigDict(...)` on `CreateExcelParams`, `EditExcelParams`, `CreateWordParams` (previously raw dicts)
- `BaseDocumentGenerator.persist_and_verify(callable, path, filename)` factors out the "write then verify size" pattern shared between Excel and Word; redundant `__init__` of `ExcelGenerator`/`WordGenerator` removed (now inherit directly)

### Architecture
- **BREAKING (import)**: `TableData`/`ImageData` from `src/models/unified.py` renamed to `UnifiedTableData`/`UnifiedImageData` to avoid collision with the native-PDF versions in `src/models/extraction.py`
- `src/services/document/router.py`: 8 lazy `models.unified` imports hoisted to the top of the file (no real circular import); comment and `noqa PLC0415` removed
- `src/services/vector/payload.py` renamed to `payload_reader.py` (to distinguish it from `payload_builder.py`)
- New `tests/unit/services/vector/test_payload_reader.py` covers `extract_doc_summary` (nominal case, partial payload, empty dict)

### Migration

Update local clones and MCP client configs:

```bash
# 1. Rename the project directory (optional but recommended)
mv Mcp-Zileo-Rag Zileo-Docs

# 2. Rebuild containers under the new names
docker compose down && docker compose up -d --build

# 3. Update MCP client config (e.g. .mcp.json or Claude Desktop)
#    Replace the "zileo-rag" key with "zileo-docs"
```

## [0.3.0] - 2026-05-15

### BREAKING CHANGES
- MCP tool `search_documents` removed. Replaced by two dedicated tools with non-ambiguous schemas:
  - `search_hybrid`: `query` + `top_k` + `filters` + `min_cosine_relevance` (RRF scale hidden, cosine guard 0.72 against off-domain results)
  - `search_semantic`: `query` + `top_k` + `filters` + `score_threshold` (pure cosine similarity, default 0.7)
- Pydantic model `SearchDocumentsParams` removed; replaced by `SearchHybridParams` and `SearchSemanticParams`
- Method `DocumentPipelineOrchestrator.search_documents` removed (dead code, unused)

### Added
- Abstract base class `BaseSearchTool(VectorStoreMCPTool)` in `src/mcp/tools/search_base.py` factors out the shared logic (DI, Pydantic validation, query embedding, response formatting)
- Eval `scripts/eval_rag.py` now accepts `--tool search_hybrid|search_semantic` (replaces `--mode`)

### Changed
- REST API `POST /api/v1/search` **unchanged**: keeps `search_mode` as a low-level parameter. The REST/MCP asymmetry is intentional (REST = low-level, MCP = agent-oriented)
- Error message of the `index_document` tool (already-indexed case) now references `search_hybrid`/`search_semantic`

### Migration
- MCP caller: replace `search_documents` (hybrid mode) with `search_hybrid`; replace `search_documents` (semantic mode) with `search_semantic`
- Response format is identical (chunk_id, score, page_numbers, etc.) — only the name and input schema change

## [0.2.0] - 2026-04-28

### Added
- Hybrid search RRF: `hybrid_search` combines dense (vector) and full-text using Reciprocal Rank Fusion
- BM25 sparse embeddings via `fastembed` (Qdrant-native prefetch)
- `search_mode` parameter (hybrid/semantic) on MCP `search_documents` and REST `/api/v1/search`
- SHA-256 file hash (`compute_file_hash`) for Excel/Word deduplication
- Modified-file detection: hash comparison on `index_document`
- `file_hash` field in `UnifiedMetadata` and Qdrant payload
- MCP tool `create_word_document`: Word (`.docx`) generation from Markdown
- GitHub community files: `SECURITY.md`, `CONTRIBUTORS.md`, `NOTICE`, `THIRD_PARTY_LICENSES.md`
- GitHub Actions CI: `validate.yml` (ruff, mypy, pytest unit), `dependabot.yml` (pip + docker + actions)
- Issue templates (bug, feature) and pull request template

### Changed
- `IndexDocumentTool` uses dependency injection (vector_store, embedder)
- Default search mode: `hybrid` (previously: semantic only)
- `_create_indexes` refactored with module-level constants
- `_extract_excel`/`_extract_word` reuse already-initialized extractors
- Project status: Alpha → Beta
- Renamed `LICENSE.txt` → `LICENSE` (GitHub convention)
- Default branch: `master` → `main`

### Removed
- Dead code `_VALID_TYPES_BY_SOURCE` in `ListAvailableDocumentsParams`

## [0.1.0] - 2026-02-28

First functional release of MCP Zileo RAG.

### Added
- 8 MCP tools over JSON-RPC 2.0: `index_document`, `search_documents`, `get_document`, `delete_document`, `list_indexed_documents`, `list_available_documents`, `read_document_content`, `get_excel_formulas`
- Multi-format support: PDF (native + Mistral OCR), Excel (`.xlsx`/`.xls`), Word (`.docx`)
- REST API with health, documents, and search endpoints
- Extraction pipeline: analysis -> extraction -> chunking -> embedding -> vector storage
- Mistral embeddings (1024 dimensions) and Qdrant storage
- Smart OCR: automatic detection of text vs. image pages
- Smart chunking with Markdown structure preservation
- Double-indexing protection (duplicate guard)
- Configurable rate limiting (`slowapi`)
- Path-traversal protection on MCP tools
- Docker deployment (multi-stage, non-root, healthchecks)
- 319 unit tests (>80% coverage)
- AGPL-3.0-or-later license
