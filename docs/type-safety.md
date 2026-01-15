# Type Safety

Guide pour le typage statique du projet MCP Zileo PDF.

## Vue d'Ensemble

Le projet utilise un typage statique strict avec mypy. L'objectif est d'eliminer les utilisations non necessaires de `Any` pour :
- Ameliorer la detection d'erreurs a la compilation
- Faciliter la maintenance du code
- Documenter les types attendus

## Types Personnalises

### RequestId (MCP)

```python
# src/mcp/types.py
from typing import TypeAlias

# JSON-RPC 2.0 request identifier
RequestId: TypeAlias = str | int | None
```

Conforme a la specification JSON-RPC 2.0 :
- `string` : Identifiant textuel
- `number` : Identifiant numerique (entier recommande)
- `null` : Pour les notifications (pas de reponse attendue)

Reference: https://www.jsonrpc.org/specification#request_object

## Politique sur les Types `Any`

### Usages Acceptes

| Pattern | Exemple | Raison |
|---------|---------|--------|
| JSON dynamique | `dict[str, Any]` | Structure inconnue a la compilation |
| JSON Schema | `input_schema: dict[str, Any]` | Schema defini dynamiquement |
| Interop libs | `fitz.Document` sans stubs | Librairies sans types |

### Usages Rejetes

| Pattern | Remplacement | Statut |
|---------|--------------|--------|
| `request_id: Any` | `RequestId` | Termine |
| `-> Any` (retour) | Type precis ou TypedDict | A faire |
| `page_content: Any` | `fitz.Page` ou Protocol | A faire |

## Strategies de Correction

### 1. Type Alias Simple

Pour les unions de types primitifs :

```python
from typing import TypeAlias

RequestId: TypeAlias = str | int | None
PageNumber: TypeAlias = int
DocumentId: TypeAlias = str
```

### 2. TypedDict

Pour les structures JSON fixes :

```python
from typing import TypedDict

class ChunkMetadata(TypedDict):
    chunk_id: str
    page_numbers: list[int]
    token_count: int
```

### 3. Protocol

Pour le duck typing avec librairies externes :

```python
from typing import Protocol, Any

class PageLike(Protocol):
    def get_text(self) -> str: ...
    def get_pixmap(self) -> Any: ...
```

## Plan d'Implementation

### Sprint 1 : OCR (Haute Priorite) - A Faire

| Fichier | Correction |
|---------|------------|
| `ocr_processor.py:151` | `-> Any` → Type precis |
| `ocr_processor.py:273` | `page_content: Any` → `fitz.Page` |

### Sprint 2 : MCP (Moyenne Priorite) - Termine

| Fichier | Correction | Statut |
|---------|------------|--------|
| `src/mcp/types.py` | Creer `RequestId` | Done |
| `src/mcp/server.py` | 7x `Any` → `RequestId` | Done |

**Resultats** :
- mypy : Success (no issues found)
- Tests MCP : 29 passed
- Tests integration : 24 passed, 2 skipped

### Sprint 3 : Validation Finale - A Faire

- Executer `/check` complet
- 0 erreur mypy sur tout le projet
- 0 warning ruff

## Commandes de Validation

```bash
# Fichier specifique
mypy src/mcp/server.py

# Module complet
mypy src/mcp/

# Projet entier
mypy src/

# Validation complete
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest tests/ -v
```

## Rollback Plan

En cas de probleme :

| Probleme | Solution |
|----------|----------|
| Erreur mypy inattendue | Utiliser `cast()` ou revoir le type |
| Test echoue | Verifier le type reel a l'execution |
| Import circulaire | Deplacer types dans module separe |

## References

- [Architecture](architecture.md) - Structure du projet
- [API Reference](api-reference.md) - Endpoints et schemas
- [JSON-RPC 2.0 Spec](https://www.jsonrpc.org/specification)
