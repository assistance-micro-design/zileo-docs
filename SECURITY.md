# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.4.x   | ✅ |
| < 0.4   | ❌ |

## Reporting a Vulnerability

**Do NOT create public GitHub issues for security vulnerabilities.**

Please report vulnerabilities via:
- [GitHub Security Advisories](https://github.com/assistance-micro-design/zileo-docs/security/advisories/new)

We will respond within 7 days and work with you to understand and resolve the issue.

## Security Measures

Zileo Docs implements the following security measures:

- **API Key Storage**: Secrets read from environment variables only (`MISTRAL_API_KEY`, `QDRANT_API_KEY`). Never logged, never persisted to disk.
- **Input Validation**: Pydantic schemas on all REST and MCP inputs.
- **File Validation**: Magic-number check (`%PDF-`, `PK\x03\x04`) before processing. Size and page-count limits enforced.
- **Path Traversal Prevention**: `Path.resolve().is_relative_to(documents_path)` on every file access.
- **Excel Formula Injection**: Blacklist of dangerous patterns (`DDE`, `CMD`, `SYSTEM`, `EXEC`, `CALL`, `REGISTER`, `+cmd|`, `-cmd|`, `@...cmd|`). Standard formulas (`=SUM`, `=IF`) remain a feature.
- **Rate Limiting**: `slowapi` per endpoint (default 60/min, index 10/min, MCP 30/min).
- **CORS Hardening**: Restrictive in production (`DEBUG=false`).
- **API Key Auth**: Optional bearer auth for REST endpoints.
- **No Telemetry**: No data leaves the host except for the Mistral API calls you trigger explicitly.
- **Docker Hardening**: Non-root user (`appuser`), `python:3.11-slim` base image, healthchecks.

## Scope

### In Scope

| Area | Examples |
|------|----------|
| **Authentication** | API key bypass, header injection |
| **MCP Tool Execution** | Argument validation bypass, unauthorized tool invocation |
| **File Validation** | Magic-number bypass, path traversal, symlink attacks |
| **Excel Generation** | Formula injection beyond the blacklist, ZIP-bomb in `.xlsx` |
| **Word/PDF Extraction** | Memory exhaustion, malicious payloads in embedded objects |
| **Qdrant Queries** | Injection in filter builders, payload tampering |
| **Rate Limiting** | Bypass of `slowapi` limits |
| **Docker Image** | Privilege escalation, secret leakage in layers |

### Out of Scope

Report these to the respective maintainers:

| Area | Report To |
|------|-----------|
| Mistral API | [Mistral AI](https://mistral.ai/) |
| Qdrant engine | [Qdrant Security](https://github.com/qdrant/qdrant/security) |
| PyMuPDF / pymupdf4llm | [Artifex Security](https://github.com/pymupdf/PyMuPDF/security) |
| FastAPI / Pydantic / uvicorn | Respective project security teams |
| Python runtime | [Python Security](https://www.python.org/news/security/) |

### Not Applicable

- The README states the server is **designed for personal local use** behind Docker. Exposing this server on a public network without an additional auth layer is explicitly out of scope.
- DoS by sending oversized files within the configured limits is a feature trade-off, not a vulnerability.

## Disclosure

We follow a coordinated disclosure model. Once a fix is released, we publish an advisory describing the issue, the affected versions, and the mitigation.
