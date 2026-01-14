# MCP Zileo PDF - Instructions Claude Code

## Projet

Serveur MCP pour le traitement de documents PDF, expose via FastAPI et deploye en Docker.

## Stack Technique

- **Backend**: FastAPI + Python 3.11
- **Protocol**: MCP (Model Context Protocol) via JSON-RPC 2.0
- **Deploy**: Docker
- **Tests**: pytest + pytest-asyncio

## Structure

```
src/
  api/          # Endpoints FastAPI REST
  mcp/          # Serveur MCP et tools
  services/     # Logique metier
  models/       # Schemas Pydantic
tests/
  unit/
  integration/
```

## Conventions

### Code Style
- Fichiers: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Docstrings: Google style

### Imports
```python
from __future__ import annotations

# stdlib
# third-party
# local
```

### Error Handling
- API: `HTTPException` avec codes HTTP standard
- MCP: JSON-RPC 2.0 error format

## Commandes Disponibles

- `/brainstorming` - Concevoir une nouvelle fonctionnalite
- `/commit` - Creer un commit structure
- `/review` - Revue de code
- `/check` - Validation complete (ruff + mypy + pytest)
- `/test` - Patterns de test
- `/debug` - Workflow de debug
- `/refactor` - Guide de refactoring
- `/learn` - Capturer un nouveau pattern
- `/improve` - Auto-ameliorer les commandes
- `/status` - Etat du projet
- `/fastapi-patterns` - Patterns FastAPI
- `/security-patterns` - Regles de securite
- `/mcp-jsonrpc` - Reference MCP/JSON-RPC

## Workflow de Developpement

1. **Nouvelle feature**: `/brainstorming` -> implementation -> `/check` -> `/commit`
2. **Bug fix**: `/debug` -> fix -> `/check` -> `/commit`
3. **Refactoring**: `/refactor` -> implementation -> `/check` -> `/commit`

## Validation (0 warning, 0 erreur)

Toujours executer `/check` avant de commit:
- **ruff**: Linting + formatting automatique
- **mypy**: Type checking strict
- **pytest**: Tests unitaires et integration

Hook automatique: ruff s'execute apres chaque edition de fichier Python.

## Fichiers Learning

Les fichiers `.claude/learning/` contiennent:
- `project-patterns.yml` - Architecture et patterns du projet
- `error-solutions.yml` - Erreurs connues et solutions
- `reusable-functions.yml` - Snippets reutilisables
- `security-checklist.yml` - Checklist securite
- `mcp-jsonrpc-spec.yml` - Spec JSON-RPC

Ces fichiers sont enrichis au fur et a mesure avec `/learn`.

## Regles Importantes

1. **Toujours async** pour les operations I/O
2. **Validation Pydantic** pour tous les inputs
3. **Tests** avant merge
4. **JSON-RPC 2.0** strict pour MCP
5. **Pas de secrets en dur** - utiliser variables d'environnement
