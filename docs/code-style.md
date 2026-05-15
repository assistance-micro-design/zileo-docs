# Code Style

Conventions de code obligatoires pour ce projet. Tout doit passer `ruff` (configuration dans `pyproject.toml`) et `mypy --strict`.

## Principes

- Python 3.11+ avec `from __future__ import annotations` en première ligne
- Type hints partout (params + retour). Mode `mypy strict`
- Pas de `else` : guard clauses, early return, ternaire, expression `or`
- Fonctions < 50 lignes (split sinon)
- Pas de `TODO`/`FIXME`, code mort, imports inutilisés ou variables inutilisées dans le code merge

## Pas de `else`

### Guard clause (validation)

```python
def process(data: Data | None) -> Result | None:
    if not data:
        return None
    if not data.is_valid:
        return None
    return do_work(data)
```

### Early return

```python
def get_status(qdrant: str, mistral: str) -> str:
    if "unhealthy" in (qdrant, mistral):
        return "degraded"
    return "healthy"
```

### Expression `or` (defaut)

```python
headers = self.headers or [cell.text for cell in self.rows[0]]
```

### Dict dispatch (3+ cas)

```python
HANDLERS: dict[str, Callable[[], Any]] = {
    "pdf": handle_pdf,
    "excel": handle_excel,
    "word": handle_word,
}
result = HANDLERS.get(doc_type, handle_default)()
```

## Nommage

| Element | Convention | Exemple |
|---------|------------|---------|
| Fichiers | `snake_case.py` | `vector_store.py` |
| Classes | `PascalCase` | `QdrantVectorStore` |
| Fonctions / methodes | `snake_case` | `get_document()` |
| Constantes | `UPPER_SNAKE_CASE` | `MAX_CHUNK_SIZE` |
| Prive | `_snake_case` | `_compute_status()` |

### Suffixes des modèles Pydantic

| Contexte | Suffixe | Exemple |
|----------|---------|---------|
| Paramètres MCP tool | `*Params` | `SearchHybridParams`, `SearchSemanticParams` |
| Request API REST | `*Request` | `IndexDocumentRequest` |
| Résultat opération | `*Result` | `IndexResult` |
| Réponse HTTP | `*Response` | `SearchResponse` |
| Item dans une liste | `*Item` | `SearchResultItem` |
| Objet domaine interne | (aucun) | `DocumentChunk` |

## Imports (ordre ruff `I`)

```python
from __future__ import annotations

# stdlib
import logging
from pathlib import Path

# third-party
from fastapi import HTTPException
from pydantic import BaseModel

# local (premier-party : src.*)
from src.core.config import settings
from src.models.document import DocumentMetadata
```

## Type hints

```python
# Union moderne (pas Optional / Union)
def process(data: str | None = None) -> dict[str, Any]: ...

# ClassVar pour attributs de classe
class MyTool(BaseMCPTool):
    name: ClassVar[str] = "my_tool"

# TypeAlias pour types complexes
from typing import TypeAlias
RequestId: TypeAlias = str | int | None
```

## Pydantic

```python
from typing import Annotated
from pydantic import BaseModel, Field

class SearchParams(BaseModel):
    query: Annotated[str, Field(min_length=1, description="Search query")]
    top_k: Annotated[int, Field(default=5, ge=1, le=100)]
```

`description=` est **obligatoire** sur tout champ exposé au LLM (apparaît dans `input_schema`).

## Async

Toute opération I/O est async :

```python
async def fetch_data(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

- `asyncio.to_thread(fn, ...)` pour wrapper des APIs synchrones (openpyxl, docx2python)
- `asyncio.gather(...)` pour opérations parallèles indépendantes
- Pas de `time.sleep()` — utiliser `await asyncio.sleep()`

## Logging

```python
logger = logging.getLogger(__name__)

# Format %-style avec contexte
logger.info("Document indexed: %s (%d chunks)", doc_id, len(chunks))
```

Jamais de `print()` en production. Jamais logger de secret (clé API, token).

## Pathlib

Toujours `Path`, jamais `os.path` :

```python
from pathlib import Path

config_path = Path(settings.DOCUMENTS_PATH) / "rapport.pdf"
with config_path.open("rb") as f:
    data = f.read()
```

## Docstrings (Google style)

```python
def process_document(path: Path, options: dict[str, Any] | None = None) -> ProcessResult:
    """Traite un document et retourne le résultat.

    Args:
        path: Chemin vers le document.
        options: Options de traitement optionnelles.

    Returns:
        Résultat avec metadata.

    Raises:
        DocumentNotFoundError: Si le document n'existe pas.
    """
```

## Interdictions absolues

- `except: pass` ou `except Exception: pass`
- `from x import *`
- `print()` en production (utiliser `logging`)
- `# type: ignore` sans code spécifique (`# type: ignore[attr-defined]`)
- `Any` sauf pour JSON dynamique (`dict[str, Any]`)
- `time.sleep()` (utiliser `asyncio.sleep()`)
- `else` dans la mesure du possible (cf. patterns ci-dessus)
- TODO/FIXME dans le code merge

## Validation avant commit

```bash
ruff check --fix src/ tests/
ruff format src/ tests/
mypy src/
pytest --cov=src --cov-fail-under=80
```

Échec sur l'une de ces commandes = pas de merge.
