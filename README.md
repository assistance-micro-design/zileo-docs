# Zileo Docs

[![Version](https://img.shields.io/badge/version-0.4.0-orange)](https://github.com/assistance-micro-design/zileo-docs)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-beta-yellow)](https://github.com/assistance-micro-design/zileo-docs)

> MCP (Model Context Protocol) server for indexing, semantic search, and generation of multi-format documents. Exposes 13 tools over JSON-RPC 2.0 so an LLM can search your local PDF, Excel, and Word files, and create or edit Excel and Word documents.

**Developed by** [Assistance Micro Design](https://www.assistancemicrodesign.net/)

**Built with** [Claude Code](https://claude.com/claude-code) by Anthropic

---

## Beta Warning

This project is in beta. Use at your own risk and review the trade-offs before relying on it.

| Risk | Description |
|------|-------------|
| **API Costs** | Every `index_document` call triggers Mistral embeddings (and OCR for image pages). Indexing large PDFs can generate non-trivial billing. |
| **Breaking Changes** | The MCP tool surface evolves between minor versions. Version 0.3.0 split `search_documents` into `search_hybrid` and `search_semantic`; expect similar adjustments before 1.0. |
| **Security** | Designed for **personal local use** behind Docker. The author declines responsibility if exposed to the public internet without an additional auth layer. |
| **Instability** | Schemas validated with `extra="forbid"` since 0.4.0 — clients sending unknown fields now receive `VALIDATION_ERROR` instead of silent acceptance. |
| **No SLA** | No guaranteed availability, no support contract. File issues via GitHub. |

**Recommendation:** Run behind a private network, set `API_KEY`, and pin the Docker image to a tagged version.

---

## Description

Zileo Docs ingests heterogeneous office documents, extracts their content (native text or Mistral OCR), chunks the result while preserving Markdown structure, embeds each chunk with Mistral (1024-dim dense vectors plus BM25 sparse vectors), and stores them in Qdrant. An LLM connected over MCP can then search the indexed corpus, read full documents, and generate new Excel or Word files — all from natural-language tool calls.

### Key Features

- 13 MCP tools over JSON-RPC 2.0 / HTTP (`POST /mcp`)
- Multi-format ingestion: PDF (native + OCR), Excel `.xlsx`/`.xls`, Word `.docx`
- Hybrid search (dense + BM25 RRF) with cosine relevance guard against off-domain results
- Semantic-only search with explicit `score_threshold`
- Excel and Word generation from structured input (data, formulas, styles, charts)
- Path traversal, formula-injection, and ZIP-bomb protections
- Per-endpoint rate limiting (`slowapi`) and API-key authentication
- Docker multi-stage image, non-root runtime, health-checked

---

## Prerequisites

| Dependency | Purpose | Installation |
|------------|---------|--------------|
| Docker Engine >= 24 | Container runtime | https://docs.docker.com/engine/install/ |
| Docker Compose v2 | Service orchestration | Bundled with Docker Desktop or the `docker compose` CLI plugin |
| Mistral API key | Embeddings (1024d) + OCR | https://console.mistral.ai/ |

---

## Build Requirements

Required only when developing outside Docker (the container ships everything else).

| Tool | Min version | Verify |
|------|-------------|--------|
| Python | 3.11 | `python3 --version    # >= 3.11` |
| uv | 0.9 | `uv --version    # >= 0.9` |

---

## Installation

```bash
git clone https://github.com/assistance-micro-design/zileo-docs.git
cd zileo-docs
cp .env.example .env

# Edit .env: set MISTRAL_API_KEY and DOCUMENTS_PATH
# Generate an API key to protect the server:
echo "API_KEY=$(openssl rand -hex 32)" >> .env

docker compose up -d
```

> **About `API_KEY`** — Protects `/api/v1/*`, `/mcp`, and `/health`. Outside `DEBUG=true`, the server refuses to start with an empty key. See [docs/mcp-client-setup.md](docs/mcp-client-setup.md#authentication) for passing it to MCP clients.

Verify the server is up:

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/health
# {"status": "healthy", ...}
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Web framework | FastAPI |
| MCP runtime | `mcp` SDK (JSON-RPC 2.0 over HTTP) |
| Dense embeddings | Mistral (`mistral-embed`, 1024 dim) |
| Sparse embeddings | fastembed (BM25) |
| Vector store | Qdrant 1.16.3 |
| OCR | Mistral OCR API |
| PDF extraction | PyMuPDF + pymupdf4llm |
| Excel I/O | openpyxl, xlrd |
| Word I/O | docx2python, python-docx |
| Packaging | uv + Hatchling |
| Runtime | Docker Compose (multi-stage, non-root) |

---

## MCP Configuration

The MCP endpoint is `POST /mcp` (JSON-RPC 2.0 over HTTP).

### Claude Desktop

Add to the Claude Desktop config:

| OS | Path |
|----|------|
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "zileo-docs": {
      "url": "http://localhost:8000/mcp",
      "transport": "http",
      "headers": {
        "X-API-Key": "your_api_key_here"
      }
    }
  }
}
```

Replace `your_api_key_here` with the `API_KEY` from `.env`. Restart Claude Desktop after editing.

### Zileo Chat

In Zileo Chat, open **Settings → MCP → Add server** and fill in the form:

| Field | Value |
|-------|-------|
| **Name** | `zileo-docs` |
| **Deployment method** | `HTTP` |
| **Arguments** | the endpoint URL on the first line — `http://localhost:8000/mcp` |
| **Authentication** | `API key` |
| **Header name** | `X-API-Key` |
| **API key value** | the `API_KEY` from your `.env` |

The API-key value is stored in your OS keychain — never written to the database in plain text, never exported. Only non-sensitive metadata (the header name) is persisted.

Set the endpoint URL according to where Zileo Chat runs relative to the server:

| Scenario | Endpoint URL |
|----------|--------------|
| Same host | `http://localhost:8000/mcp` |
| Zileo Chat in Docker, same host | `http://zileo-docs:8000/mcp` — join the `zileo-docs_mcp-network` network |
| Remote host (LAN) | `http://<server-ip>:8000/mcp` — enable the LAN access toggle at the top of the MCP settings first |

Then **Save**. See [docs/mcp-client-setup.md](docs/mcp-client-setup.md#zileo-chat) for details.

### Other MCP clients

Any MCP-compatible client can connect over HTTP Streamable to `http://localhost:8000/mcp`. The server implements:

- `initialize` — Handshake and capabilities
- `tools/list` — Lists the 13 available tools
- `tools/call` — Invokes a tool

Transport is HTTP POST with JSON-RPC 2.0 payloads. No SSE, no WebSocket.

---

## MCP Tools

### Indexing and search

| Tool | Description |
|------|-------------|
| `index_document` | Extract and index a PDF, Excel, or Word file into Qdrant |
| `search_hybrid` | Hybrid search (dense + BM25 RRF) with cosine relevance guard against off-domain hits |
| `search_semantic` | Pure semantic search (cosine, default threshold 0.7) |
| `get_document` | Fetch the metadata and chunks for a document |
| `delete_document` | Remove a document from the index (source file untouched) |
| `list_indexed_documents` | List documents already indexed |
| `read_document_content` | Read the reconstructed Markdown content of a document |
| `get_excel_formulas` | Fetch the formulas from an indexed Excel file |

### Generation and editing

| Tool | Description |
|------|-------------|
| `create_excel_document` | Create an Excel file (`.xlsx`) with data, styles, and charts |
| `edit_excel_document` | Edit an existing Excel file (13 operations) |
| `create_word_document` | Create a Word file (`.docx`) from Markdown content |

### Utilities

| Tool | Description |
|------|-------------|
| `list_available_documents` | List source files (two sources: documents, generated) |
| `inspect_generated_file` | Inspect the structure of a generated Excel file |

---

## Configuration

Main environment variables (see [docs/configuration.md](docs/configuration.md) for the full list):

| Variable | Required | Description |
|----------|----------|-------------|
| `MISTRAL_API_KEY` | Yes | Mistral API key (embeddings + OCR) |
| `API_KEY` | Yes (outside DEBUG) | Authentication key for protected endpoints. Generate via `openssl rand -hex 32`. Empty value accepted only when `DEBUG=true`. |
| `DOCUMENTS_PATH` | Yes | Local path to your source documents |
| `OUTPUT_PATH` | No | Output directory for generated files (default: `/app/output`) |
| `QDRANT_HOST` | No | Qdrant host (default: `localhost`, `qdrant` inside Docker) |
| `DEBUG` | No | Enables Swagger UI and CORS (default: `false`) |

---

## Local Development

```bash
uv sync --extra dev
docker compose up -d qdrant   # Qdrant only
uv run uvicorn src.main:app --reload
```

### Tests

```bash
uv run pytest tests/unit/ -v          # Unit tests
uv run pytest tests/integration/ -v   # Requires Qdrant
uv run pytest tests/e2e/ -v           # Full pipeline
```

### Validation

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest --cov=src --cov-fail-under=80
```

### RAG evaluation

Offline evaluation of search quality against the golden set (`tests/eval/golden_questions.yml`). Requires the server running with indexed documents.

```bash
uv run python3 scripts/eval_rag.py --tool search_hybrid    # or search_semantic
# Metrics: recall@1, recall@5, MRR, false-positive rate (off-domain), mean results
```

---

## Architecture

```
src/
  main.py              # FastAPI app + /mcp endpoint
  core/                # Config, exceptions, logging
  api/routes/          # REST endpoints (health, documents, search)
  mcp/
    server.py          # JSON-RPC 2.0 router
    tools/             # 13 MCP tools
  services/
    pdf/               # Analysis, native extraction, Mistral OCR
    excel/             # Extraction + generation + editing
    word/              # docx2python extraction
    inspection/        # Generated-file inspection
    document/          # Multi-format router
    chunking/          # Chunk splitting
    embedding/         # Mistral embeddings (1024 dim)
    vector/            # Qdrant storage
  models/              # Pydantic schemas
```

---

## Documentation

- [MCP client setup](docs/mcp-client-setup.md) — Claude Desktop, Zileo Chat, other clients
- [Research guide](docs/research-guide.md) — Indexing, hybrid search, reading
- [Generation guide](docs/generation-guide.md) — Excel and Word options, design, examples
- [API reference](docs/api-reference.md) — REST endpoints and 13 MCP tools
- [Architecture](docs/architecture.md) — Processing pipeline and components
- [Configuration](docs/configuration.md) — Environment variables
- [Deployment](docs/deployment.md) — Docker and local development
- [Multi-format support](docs/multi-format.md) — PDF, Excel, Word
- [Code style](docs/code-style.md) — Conventions

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

Quick path:

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Commit with a conventional message (`git commit -m "feat(scope): summary"`)
4. Push and open a Pull Request against `main`
5. Ensure CI is green and the PR checklist is satisfied

---

## Security

To report a vulnerability, see [SECURITY.md](SECURITY.md). **Do not open public issues for security reports.**

---

## License

Distributed under the [GNU Affero General Public License v3.0 or later](LICENSE).

```
Copyright 2025-2026 Assistance Micro Design
Licensed under the GNU Affero General Public License v3.0 or later
```

This license is **mandatory** because the project depends on [PyMuPDF](https://github.com/pymupdf/PyMuPDF) and [pymupdf4llm](https://github.com/pymupdf/RAG) (Artifex Software, Inc.), both distributed under AGPL-3.0. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for the complete inventory and [NOTICE](NOTICE) for attribution.

---

## Acknowledgments

- [Mistral AI](https://mistral.ai/) — Embeddings and OCR
- [Qdrant](https://qdrant.tech/) — Vector database
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) and [pymupdf4llm](https://github.com/pymupdf/RAG) — PDF extraction
- [FastAPI](https://github.com/fastapi/fastapi) — Web framework
- [Model Context Protocol](https://modelcontextprotocol.io/) — Tool protocol
- Built with [Claude Code](https://claude.com/claude-code) by [Anthropic](https://anthropic.com)

---

[Assistance Micro Design](https://www.assistancemicrodesign.net/) | [GitHub](https://github.com/assistance-micro-design)
