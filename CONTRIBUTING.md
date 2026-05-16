# Contributing to Zileo Docs

Thank you for considering a contribution. This document captures the conventions specific to this repository — please read it end-to-end before opening your first PR.

## Prerequisites

- Python 3.11 or newer
- [uv](https://github.com/astral-sh/uv) 0.9 or newer (the project's package manager)
- Docker and Docker Compose v2 (Qdrant runs in a container during integration tests)
- A Mistral API key for any test that exercises embedding or OCR

Install development dependencies:

```bash
uv sync --extra dev
```

## Branch and commit convention

- Branch from `main`. Use a descriptive prefix: `feat/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/`, `security/`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): subject` in the imperative, lowercase, no trailing period. Example: `feat(mcp): add cosine relevance guard`.
- One commit = one concern. Do not bundle unrelated changes. Squash trivial fixups before opening the PR.
- Mark breaking changes with `!` after the type/scope: `refactor(mcp)!: split search_documents into search_hybrid + search_semantic`.

## Required checks before opening a PR

All four must pass locally. The same commands run in CI on every pull request.

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
uv run pytest --cov=src --cov-fail-under=80
```

If your change touches the MCP tool surface, also run a manual smoke test against a real client (Claude Desktop, Zileo Chat, or `curl` to `POST /mcp`) — unit tests do not catch JSON-RPC contract regressions.

## CHANGELOG

Every user-facing change goes under `## [Unreleased]` in `CHANGELOG.md`, in the appropriate subsection (`Security`, `Quality`, `Architecture`, `Added`, `Changed`, `Fixed`, `Removed`). Use one bullet per change, written in the imperative.

Do **not** create a new versioned section — only the maintainer cuts releases and bumps versions at tag time.

## What contributors must NOT touch

- `pyproject.toml` `version = "..."` — bumped only at release time.
- The version badge in `README.md` — same rule.
- `## [Unreleased]` heading in `CHANGELOG.md` — add bullets under it; never rename it or create a new versioned section.
- `LICENSE` — AGPL-3.0-or-later is mandatory due to PyMuPDF/pymupdf4llm dependencies.
- `NOTICE` — copyright and attribution block.
- `THIRD_PARTY_LICENSES.md` — only edit when you add or upgrade a dependency in `pyproject.toml`.
- `.github/workflows/*` — open a separate discussion before changing CI behavior.
- `uv.lock` — regenerate via `uv lock` rather than hand-editing.
- `.env`, `.env.local`, any file matching `*.local.env` — never commit secrets.

## Opening the PR

1. Fork the repository and push your branch to your fork.
2. Open a PR against `main` in `assistance-micro-design/zileo-docs`.
3. Fill the [pull request template](.github/PULL_REQUEST_TEMPLATE.md) — every checkbox must be addressed.
4. Link any related issue with `Closes #N` or `Refs #N`.
5. Keep the PR focused. If review uncovers an unrelated issue, file a separate issue rather than expanding scope.

## Code style cheat sheet

These rules are enforced by `ruff`, `mypy`, or by reviewers. The full set lives in `.claude/rules/`.

- Type hints on every public function and method (`mypy --strict` passes).
- `from __future__ import annotations` at the top of every module.
- No `else` branches — use guard clauses and early return.
- No `TODO`/`FIXME` left in merged code.
- No unused imports, variables, or commented-out code.
- No premature abstraction. Three similar lines is better than a wrong base class.
- Pydantic models for every public input (REST request bodies, MCP tool params).
- All MCP `*Params` models declare `model_config = ConfigDict(extra="forbid")`.
- Qdrant filters built with `FieldCondition` / `Filter` builders — never via string interpolation.
- Logging via `logging.getLogger(__name__)`. Never log secrets, tokens, API keys, or user-supplied input values (RGPD).
- Tests: pytest, async via `pytest-asyncio` (`asyncio_mode = "auto"`). Place unit tests under `tests/unit/`, integration under `tests/integration/`, end-to-end under `tests/e2e/`.

## License

By contributing, you agree that your contributions will be licensed under the GNU Affero General Public License v3.0 or later, the same license as this project.
