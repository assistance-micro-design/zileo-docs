# Plan de Refactoring - MCP Zileo PDF

> Date: 2026-01-15
> Status: ✅ Implementé
> Auteur: Claude Code

## Contexte

Analyse du codebase pour identifier les opportunités de refactoring visant à améliorer:
- La maintenabilité
- La réduction de duplication
- La testabilité
- Les performances (connexions partagées)

---

## 🔴 Priorité Haute

### 1. Extract Base Class pour les MCP Tools

**Fichiers concernés:**
- `src/mcp/tools/index_document.py`
- `src/mcp/tools/search.py`
- `src/mcp/tools/get_document.py`
- `src/mcp/tools/delete_document.py`
- `src/mcp/tools/list_indexed_documents.py`
- `src/mcp/tools/list_available_pdfs.py`

**Problème:**
Les 6 tools MCP ont une structure quasi-identique avec duplication significative:

```python
# Pattern répété dans chaque tool:
name: ClassVar[str] = "..."
description: ClassVar[str] = "..."
input_schema: ClassVar[dict[str, Any]] = {...}
_initialized = False

def __init__(self) -> None:
    self._service = SomeService()
    self._initialized = False

async def initialize(self) -> None:
    if not self._initialized:
        await self._service.initialize()
        self._initialized = True

async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
    if not self._initialized:
        await self.initialize()
    # ...
```

**Solution:**
Créer une classe de base abstraite `BaseMCPTool`:

```python
# src/mcp/tools/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class BaseMCPTool(ABC):
    """Classe de base pour tous les tools MCP.
    
    Fournit:
    - Structure commune (name, description, input_schema)
    - Gestion de l'initialisation lazy
    - Pattern template method pour execute()
    """
    
    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]
    
    def __init__(self) -> None:
        self._initialized = False
    
    @abstractmethod
    async def _do_initialize(self) -> None:
        """Hook pour l'initialisation spécifique au tool.
        
        À implémenter par les sous-classes pour initialiser
        leurs dépendances (vector store, embedder, etc.).
        """
    
    async def initialize(self) -> None:
        """Initialise le tool si nécessaire.
        
        Pattern idempotent: peut être appelé plusieurs fois
        sans effet de bord.
        """
        if not self._initialized:
            await self._do_initialize()
            self._initialized = True
    
    async def _ensure_initialized(self) -> None:
        """S'assure que le tool est initialisé avant exécution."""
        if not self._initialized:
            await self.initialize()
    
    @abstractmethod
    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Logique d'exécution spécifique au tool.
        
        Args:
            arguments: Paramètres validés du tool.
            
        Returns:
            Résultat de l'exécution.
        """
    
    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute le tool avec initialisation automatique.
        
        Args:
            arguments: Paramètres du tool.
            
        Returns:
            Résultat de l'exécution.
        """
        await self._ensure_initialized()
        return await self._do_execute(arguments)
```

**Exemple de migration (GetDocumentTool):**

```python
# Avant
class GetDocumentTool:
    name: ClassVar[str] = "get_document"
    # ... répétition du pattern
    
    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._initialized:
            await self.initialize()
        # logique...

# Après
class GetDocumentTool(BaseMCPTool):
    name: ClassVar[str] = "get_document"
    description: ClassVar[str] = "..."
    input_schema: ClassVar[dict[str, Any]] = {...}
    
    def __init__(self, vector_store: QdrantVectorStore | None = None) -> None:
        super().__init__()
        self._vector_store = vector_store or QdrantVectorStore()
    
    async def _do_initialize(self) -> None:
        await self._vector_store.initialize()
    
    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        # Logique métier uniquement
        params = GetDocumentParams(**arguments)
        # ...
```

**Bénéfices:**
- Réduction de ~30 lignes par tool
- Comportement cohérent garanti
- Facilite l'ajout de nouveaux tools
- Meilleure testabilité (mock de la base class)

**Estimation:** 2-3h

---

### 2. Simplifier l'initialisation dans MCPServer

**Fichier:** `src/mcp/server.py` (lignes 63-74)

**Problème:**
Répétition manuelle pour initialiser chaque tool:

```python
async def initialize(self) -> None:
    if not self._initialized:
        await self._index_document.initialize()
        await self._search_documents.initialize()
        await self._get_document.initialize()
        await self._delete_document.initialize()
        await self._list_indexed_documents.initialize()
        await self._list_available_pdfs.initialize()
        self._initialized = True
```

**Solution:**
Utiliser le registry existant avec `asyncio.gather`:

```python
async def initialize(self) -> None:
    """Initialise tous les tools en parallèle."""
    if not self._initialized:
        await asyncio.gather(
            *(tool.initialize() for tool in self.tools.values())
        )
        self._initialized = True
        logger.info("MCP Server services initialized")
```

**Bénéfices:**
- Code plus maintenable (ajout de tool = 0 changement ici)
- Initialisation parallèle = plus rapide
- Moins de risque d'oubli

**Estimation:** 15min

---

## 🟡 Priorité Moyenne

### 3. Dependency Injection pour QdrantVectorStore

**Fichiers concernés:**
- `src/mcp/tools/search.py`
- `src/mcp/tools/get_document.py`
- `src/mcp/tools/delete_document.py`
- `src/mcp/tools/list_indexed_documents.py`
- `src/mcp/server.py`

**Problème:**
4 tools instancient leur propre `QdrantVectorStore`:

```python
# Dans chaque tool:
def __init__(self) -> None:
    self._vector_store = QdrantVectorStore()
```

Conséquences:
- 4 connexions Qdrant au lieu d'une
- Impossible de mocker pour les tests
- Couplage fort

**Solution:**
Injecter les dépendances depuis MCPServer:

```python
# src/mcp/server.py
class MCPServer:
    def __init__(self) -> None:
        # Dépendances partagées
        self._shared_vector_store = QdrantVectorStore()
        self._shared_embedder = MistralEmbedder()
        
        # Injection dans les tools
        self._search_documents = SearchDocumentsTool(
            vector_store=self._shared_vector_store,
            embedder=self._shared_embedder,
        )
        self._get_document = GetDocumentTool(
            vector_store=self._shared_vector_store,
        )
        self._delete_document = DeleteDocumentTool(
            vector_store=self._shared_vector_store,
        )
        self._list_indexed_documents = ListIndexedDocumentsTool(
            vector_store=self._shared_vector_store,
        )
```

```python
# src/mcp/tools/get_document.py
class GetDocumentTool(BaseMCPTool):
    def __init__(self, vector_store: QdrantVectorStore | None = None) -> None:
        super().__init__()
        self._vector_store = vector_store or QdrantVectorStore()
```

**Bénéfices:**
- Une seule connexion Qdrant
- Testabilité améliorée (injection de mocks)
- Réduction mémoire/ressources

**Estimation:** 1h

---

### 4. Consolidation des Modèles Pydantic

**Fichier:** `src/models/api.py`

**Problème:**
Duplication entre modèles Request et Params:

```python
class ExtractPDFRequest(BaseModel):
    file_path: str
    force_ocr: bool = False
    table_format: str = "markdown"

class ExtractPDFParams(BaseModel):  # Quasi-identique!
    file_path: str
    force_ocr: bool = False
    table_format: TableFormat = TableFormat.MARKDOWN
```

**Analyse requise:**
- Identifier les différences réelles entre Request et Params
- Déterminer les usages (API REST vs MCP tools)

**Solutions possibles:**

**Option A - Héritage:**
```python
class ExtractPDFParams(BaseModel):
    """Modèle de base pour extraction PDF."""
    file_path: str
    force_ocr: bool = False
    table_format: TableFormat = TableFormat.MARKDOWN

class ExtractPDFRequest(ExtractPDFParams):
    """Version API REST avec validations supplémentaires."""
    pass  # Ou ajout de champs spécifiques API
```

**Option B - Suppression:**
Si les Request ne sont pas utilisés par l'API REST, les supprimer.

**Estimation:** 30min (après analyse)

---

## 🟢 Priorité Basse

### 5. Optimiser le routing dans MCPServer

**Fichier:** `src/mcp/server.py` (lignes 143-160)

**Problème:**
Le dictionnaire de handlers est recréé à chaque requête:

```python
async def _route_request(self, ...):
    # Recréé à chaque appel!
    handlers: dict[str, Any] = {
        "initialize": lambda: self._handle_initialize(...),
        "tools/list": lambda: self._handle_tools_list(...),
        "tools/call": lambda: self._handle_tools_call(...),
    }
```

**Solution:**
Définir les routes en attribut d'instance:

```python
def __init__(self) -> None:
    # ... existing code ...
    
    self._method_handlers: dict[str, Callable] = {
        "initialize": self._handle_initialize,
        "tools/list": self._handle_tools_list,
        "tools/call": self._handle_tools_call,
    }

async def _route_request(self, request_id, method, request):
    # Validation...
    
    handler = self._method_handlers.get(method)
    if handler:
        return await handler(request_id, request.get("params", {}))
    
    return self._error_response(request_id, -32601, f"Method not found: {method}")
```

**Note:** Nécessite d'harmoniser les signatures des handlers.

**Estimation:** 30min

---

### 6. Extraire le formatage d'erreurs MCP

**Fichier:** `src/mcp/server.py` (lignes 270-310)

**Problème:**
Logique de formatage d'erreur inline dans `_handle_tools_call`:

```python
except MCPZileoPDFError as e:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": e.to_llm_format()}],
            "isError": True,
        },
    }
except Exception as e:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": f"ERROR..."}],
            "isError": True,
        },
    }
```

**Solution:**
Extraire en méthode privée:

```python
def _tool_error_response(
    self,
    request_id: Any,
    error: Exception,
) -> dict[str, Any]:
    """Construit une réponse d'erreur pour un tool MCP.
    
    Args:
        request_id: ID de la requête.
        error: Exception levée.
        
    Returns:
        Réponse JSON-RPC avec isError=True.
    """
    if isinstance(error, MCPZileoPDFError):
        error_text = error.to_llm_format()
    else:
        logger.exception("Tool execution error: %s", error)
        error_text = (
            f"ERROR [INTERNAL_ERROR]: {error!s}\n"
            "SUGGESTION: Erreur inattendue. Réessayer ou contacter le support."
        )
    
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": error_text}],
            "isError": True,
        },
    }
```

**Estimation:** 15min

---

## 📊 Tableau Récapitulatif

| # | Refactoring | Priorité | Complexité | Impact | Fichiers | Estimation |
|---|------------|----------|------------|--------|----------|------------|
| 1 | Base class tools | 🔴 Haute | Moyenne | Élevé | 7 | 2-3h |
| 2 | Simplifier init server | 🔴 Haute | Faible | Moyen | 1 | 15min |
| 3 | DI vector store | 🟡 Moyenne | Moyenne | Moyen | 5 | 1h |
| 4 | Consolider modèles | 🟡 Moyenne | Faible | Faible | 1 | 30min |
| 5 | Routing MCPServer | 🟢 Basse | Faible | Faible | 1 | 30min |
| 6 | Extract error format | 🟢 Basse | Faible | Faible | 1 | 15min |

**Total estimé:** 5-6h

---

## 📋 Ordre d'implémentation recommandé

1. **#2 - Simplifier init server** (quick win, prépare le terrain)
2. **#1 - Base class tools** (refactoring majeur)
3. **#3 - DI vector store** (améliore testabilité)
4. **#6 - Extract error format** (quick win)
5. **#5 - Routing MCPServer** (optionnel)
6. **#4 - Consolider modèles** (après analyse usage API)

---

## ✅ Checklist avant chaque refactoring

- [ ] Tests existants passent
- [ ] Backup/commit avant modification
- [ ] Appliquer le pattern approprié
- [ ] Tests passent après
- [ ] Pas de régression de comportement
- [ ] Code review
- [ ] Commit atomique

---

## Notes

- Chaque refactoring doit être validé avec `/check` avant commit
- Privilégier les petits commits atomiques
- Documenter les changements d'API si nécessaire
