# Code Style - Patterns et Conventions

## Vue d'Ensemble

Ce projet suit des conventions de code strictes pour maintenir la lisibilite et la maintenabilite. Ce document detaille les patterns recommandes.

## Elimination des `else`

Le projet favorise l'elimination des blocs `else` au profit de patterns plus lisibles.

### Patterns Recommandes

| Pattern | Cas d'Usage | Exemple |
|---------|-------------|---------|
| **Guard clause** | Validation/cas d'erreur | `if invalid: return` |
| **Early return** | Cas simple en premier | `if simple_case: return result` |
| **Early continue** | Dans les boucles | `if skip_condition: continue` |
| **Expression `or`** | Valeur par defaut | `value = x or default` |
| **Ternaire** | 2 options simples | `x if cond else y` |
| **Dict dispatch** | 3+ cas de routing | `handlers[key]()` |
| **Default + override** | Configuration | Valeur par defaut puis modification conditionnelle |

### Guard Clause

```python
# AVANT - Nested logic
def process(data):
    if data:
        if data.is_valid:
            return do_work(data)
        else:
            return None
    else:
        return None

# APRES - Guard clauses
def process(data):
    if not data:
        return None
    if not data.is_valid:
        return None
    return do_work(data)
```

### Early Return

```python
# AVANT
def get_status(qdrant: str, mistral: str) -> str:
    if qdrant == "healthy" and mistral == "healthy":
        status = "healthy"
    elif qdrant == "unhealthy" or mistral == "unhealthy":
        status = "degraded"
    else:
        status = "healthy"
    return status

# APRES
def get_status(qdrant: str, mistral: str) -> str:
    if "unhealthy" in (qdrant, mistral):
        return "degraded"
    return "healthy"
```

### Early Continue

```python
# AVANT
for item in items:
    if condition_a:
        process_a(item)
    else:
        process_b(item)

# APRES
for item in items:
    if condition_a:
        process_a(item)
        continue
    process_b(item)
```

### Expression `or`

```python
# AVANT
if self.headers:
    headers = self.headers
else:
    headers = [cell.text for cell in self.rows[0]]

# APRES
headers = self.headers or [cell.text for cell in self.rows[0]]
```

### Ternaire

```python
# Acceptable pour 2 options courtes
renderer = (
    JSONRenderer()
    if settings.LOG_FORMAT == "json"
    else ConsoleRenderer(colors=True)
)
```

### Dict Dispatch

```python
# Pour 3+ cas de routing
HANDLERS: dict[str, Callable[[], Any]] = {
    "pdf": handle_pdf,
    "excel": handle_excel,
    "word": handle_word,
}

handler = HANDLERS.get(doc_type, handle_default)
result = handler()
```

### Default + Override

```python
# AVANT
if options.get("force_ocr", False):
    pages_native = []
    pages_ocr = all_pages
else:
    pages_native = analysis.native_pages
    pages_ocr = analysis.ocr_pages

# APRES
pages_native = analysis.native_pages
pages_ocr = analysis.ocr_pages

if options.get("force_ocr", False):
    pages_native = []
    pages_ocr = all_pages
```

## Comparaison des Patterns

| Critere | Dict Dispatch | Guard Clause | Ternaire |
|---------|---------------|--------------|----------|
| Nombre de cas | 3+ | 2 | 2 |
| Extensibilite | Haute | Moyenne | Basse |
| Lisibilite | Moyenne | Haute | Haute (si court) |
| Performance | O(1) | O(n) | O(1) |

## Conventions Generales

### Imports

```python
from __future__ import annotations

# stdlib
import asyncio
from pathlib import Path

# third-party
from fastapi import HTTPException
from pydantic import BaseModel

# local
from src.core.config import settings
```

### Nommage

| Element | Convention | Exemple |
|---------|------------|---------|
| Fichiers | `snake_case.py` | `vector_store.py` |
| Classes | `PascalCase` | `QdrantVectorStore` |
| Fonctions | `snake_case` | `get_document()` |
| Constantes | `UPPER_SNAKE_CASE` | `MAX_CHUNK_SIZE` |
| Fonctions privees | `_snake_case` | `_compute_status()` |

### Docstrings (Google Style)

```python
def process_document(
    path: Path,
    options: dict[str, Any] | None = None,
) -> ProcessResult:
    """Traite un document et retourne le resultat.

    Args:
        path: Chemin vers le document.
        options: Options de traitement optionnelles.

    Returns:
        Resultat du traitement avec metadata.

    Raises:
        DocumentNotFoundError: Si le document n'existe pas.
        ProcessingError: Si le traitement echoue.
    """
```

### Async/Await

Toutes les operations I/O utilisent async :

```python
async def fetch_data() -> Data:
    async with aiohttp.ClientSession() as session:
        response = await session.get(url)
        return await response.json()
```

### Validation Pydantic

Tous les inputs sont valides via Pydantic :

```python
class IndexParams(BaseModel):
    file_path: Path
    force_ocr: bool = False
    chunk_size: int = Field(default=512, ge=100, le=2000)
```

## Validation du Code

Avant chaque commit :

```bash
# Linting + formatting
ruff check src/ --fix
ruff format src/

# Type checking strict
mypy src/

# Tests
pytest tests/
```
