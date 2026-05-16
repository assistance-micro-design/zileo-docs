# Third-Party Licenses

Zileo Docs depends on the following third-party libraries. Each library is listed with its version, license, and source.

## License compatibility note

This project is licensed under **AGPL-3.0-or-later**. This choice is **mandatory** because two core dependencies — **PyMuPDF** and **pymupdf4llm** — are distributed under AGPL-3.0 by Artifex Software, Inc. Any work that links these libraries must be distributed under AGPL-3.0 or a compatible license, or under a commercial license obtained from Artifex.

All other dependencies use permissive licenses (MIT, BSD-3-Clause, Apache-2.0, HPND) that are compatible with AGPL-3.0.

## Runtime dependencies

| Library | Version | License | Source |
|---------|---------|---------|--------|
| **PyMuPDF** | 1.27.x | AGPL-3.0 | https://github.com/pymupdf/PyMuPDF |
| **pymupdf4llm** | 1.27.x | AGPL-3.0 | https://github.com/pymupdf/RAG |
| fastapi | 0.136.x | MIT | https://github.com/fastapi/fastapi |
| uvicorn | 0.46.x | BSD-3-Clause | https://github.com/encode/uvicorn |
| pydantic | 2.13.x | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | 2.14.x | MIT | https://github.com/pydantic/pydantic-settings |
| mcp | 1.27.x | MIT | https://github.com/modelcontextprotocol/python-sdk |
| mistralai | 1.12.x | Apache-2.0 | https://github.com/mistralai/client-python |
| qdrant-client | 1.18.x | Apache-2.0 | https://github.com/qdrant/qdrant-client |
| fastembed | 0.8.x | Apache-2.0 | https://github.com/qdrant/fastembed |
| slowapi | 0.1.x | MIT | https://github.com/laurentS/slowapi |
| tiktoken | 0.12.x | MIT | https://github.com/openai/tiktoken |
| tenacity | 9.x | Apache-2.0 | https://github.com/jd/tenacity |
| python-multipart | 0.0.x | Apache-2.0 | https://github.com/Kludex/python-multipart |
| structlog | 25.x | Apache-2.0 / MIT (dual) | https://github.com/hynek/structlog |
| openpyxl | 3.1.x | MIT | https://foss.heptapod.net/openpyxl/openpyxl |
| xlrd | 2.0.x | BSD-3-Clause | https://github.com/python-excel/xlrd |
| docx2python | 3.6.x | MIT | https://github.com/ShayHill/docx2python |
| python-docx | 1.2.x | MIT | https://github.com/python-openxml/python-docx |
| Pillow | 12.x | HPND (MIT-like) | https://github.com/python-pillow/Pillow |

## Development dependencies

| Library | License | Source |
|---------|---------|--------|
| pytest | MIT | https://github.com/pytest-dev/pytest |
| pytest-asyncio | Apache-2.0 | https://github.com/pytest-dev/pytest-asyncio |
| pytest-cov | MIT | https://github.com/pytest-dev/pytest-cov |
| httpx | BSD-3-Clause | https://github.com/encode/httpx |
| ruff | MIT | https://github.com/astral-sh/ruff |
| mypy | MIT | https://github.com/python/mypy |

## External services (not bundled)

| Service | Role | Provider |
|---------|------|----------|
| Mistral API | Embeddings (1024d) + OCR | https://mistral.ai/ |
| Qdrant | Vector database (self-hosted via Docker) | https://qdrant.tech/ |

These services are accessed at runtime via their public APIs. Their use is governed by the providers' own terms of service.

## Updating this file

When adding or upgrading a dependency in `pyproject.toml`, update this file with the new library, its version range, and its license. License information can be checked with:

```bash
pip-licenses --format=markdown --with-urls
```
