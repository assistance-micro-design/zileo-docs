## Summary
Brief description of changes.

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change
- [ ] Refactoring
- [ ] Documentation update
- [ ] Security fix

## Changes Made
- Change 1
- Change 2

## Testing
- [ ] Unit tests added or updated (`pytest tests/unit/`)
- [ ] Integration tests pass (`pytest tests/integration/` — requires Qdrant)
- [ ] Coverage ≥ 80% (`pytest --cov=src --cov-fail-under=80`)
- [ ] Tested locally with a real MCP client (Claude Desktop, Zileo Chat) if MCP-facing

## Validation
- [ ] `ruff check src/ tests/` passes
- [ ] `ruff format --check src/ tests/` passes
- [ ] `mypy src/` passes (strict mode, no `# type: ignore` added)

## Checklist
- [ ] Code follows project style (no `else`, guard clauses, early return)
- [ ] No `TODO`/`FIXME` left in merged code
- [ ] No unused imports / variables / dead code
- [ ] Self-reviewed
- [ ] CHANGELOG.md updated if user-facing change
- [ ] Documentation updated if needed (`docs/`, `README.md`)
- [ ] No secrets committed (`.env`, API keys, tokens)
