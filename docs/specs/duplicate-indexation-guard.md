# Spec: Protection contre la double indexation

## Probleme

Quand le LLM appelle `index_document` plusieurs fois sur le meme fichier, le systeme :

1. **Genere un `document_id` UUID aleatoire a chaque appel** (pas de lien avec le fichier)
   - PDF : `src/services/pdf/analyzer.py:169` → `document_id=str(uuid.uuid4())`
   - Excel/Word : `src/models/unified.py:134` → `default_factory=lambda: str(uuid4())`
2. **Cree des chunks en doublon** dans Qdrant (les `chunk_id` sont aussi regeneres)
3. **Pollue les resultats** de `search_documents` avec des doublons

Le champ `file_hash` (SHA-256) existe dans le payload Qdrant (`doc_file_hash`) pour les PDF mais **n'est jamais consulte** avant indexation. Pour Excel/Word, il est vide (`""`).

## Objectif

Empecher la double indexation d'un meme fichier. Si le fichier est deja indexe, retourner une reponse claire au LLM avec le `document_id` existant.

## Solution

### Strategie de detection

Utiliser le **filename** (basename du fichier) comme cle de deduplication dans Qdrant.

**Pourquoi pas le `file_hash` ?**
- Le hash n'est calcule que pour les PDF (pas Excel/Word)
- Calculer le hash avant indexation ajoute un I/O pour chaque appel
- Le filename est deja stocke dans le payload Qdrant (`doc_filename`)
- Le filename est la donnee la plus naturelle et fiable : c'est ce que le LLM voit dans `list_available_documents`

**Limitation acceptee** : si un fichier est renomme et re-indexe, il sera traite comme nouveau. C'est le comportement correct (le LLM manipule des noms de fichiers, pas des hashs).

### Modification : `QdrantVectorStore.find_document_by_filename()`

Nouvelle methode dans `src/services/vector/qdrant_store.py` :

```
Input:  filename (str) - basename du fichier (ex: "rapport.pdf")
Output: dict | None - infos du document si trouve, None sinon
```

```python
async def find_document_by_filename(self, filename: str) -> dict[str, Any] | None:
    """Cherche un document deja indexe par son nom de fichier.

    Args:
        filename: Nom du fichier (basename).

    Returns:
        Dictionnaire avec document_id, filename, total_chunks ou None.
    """
    results, _next_offset = await asyncio.to_thread(
        self.client.scroll,
        collection_name=self.COLLECTION_NAME,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    field="doc_filename",
                    match=MatchValue(value=filename),
                ),
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )

    if not results:
        return None

    point = results[0]
    doc_id = point.payload.get("document_id", "")

    # Compter le nombre total de chunks pour ce document
    count_result = await asyncio.to_thread(
        self.client.count,
        collection_name=self.COLLECTION_NAME,
        count_filter=Filter(
            must=[
                FieldCondition(
                    field="document_id",
                    match=MatchValue(value=doc_id),
                ),
            ]
        ),
        exact=True,
    )

    return {
        "document_id": doc_id,
        "filename": filename,
        "total_chunks": count_result.count,
        "ingested_at": point.payload.get("ingested_at", ""),
    }
```

**Note** : le champ `doc_filename` est deja indexe en `KEYWORD` dans Qdrant (via `_create_indexes`), donc cette recherche est performante.

### Modification : `IndexDocumentTool._do_execute()`

Ajouter la verification **avant** tout traitement dans `src/mcp/tools/index_document.py` :

```python
async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
    params = UnifiedIndexDocumentParams(**arguments)
    file_path = Path(params.file_path)

    if not file_path.exists():
        raise PDFNotFoundError(str(file_path))

    # --- NOUVEAU : verification doublon ---
    existing = await self._vector_store.find_document_by_filename(file_path.name)
    if existing:
        logger.info(
            "Document deja indexe: %s (document_id=%s, chunks=%d)",
            file_path.name,
            existing["document_id"],
            existing["total_chunks"],
        )
        return {
            "already_indexed": True,
            "document_id": existing["document_id"],
            "filename": file_path.name,
            "total_chunks": existing["total_chunks"],
            "ingested_at": existing["ingested_at"],
            "message": (
                "Ce document est deja indexe. "
                "Utilisez le document_id pour search_documents. "
                "Pour re-indexer, supprimez d'abord avec delete_document."
            ),
        }
    # --- FIN NOUVEAU ---

    # ... reste du code inchange (detect_type, _index_pdf, _index_unified)
```

### Modification : description du tool `index_document`

Mettre a jour la description pour guider le LLM dans `src/mcp/tools/index_document.py` :

```python
description: ClassVar[str] = (
    "Extrait et indexe un document (PDF/Excel/Word) pour la recherche semantique. "
    "Etape obligatoire avant search_documents. "
    "IMPORTANT: Si le document est deja indexe, retourne l'ID existant sans re-indexer. "
    "Retourne: document_id, type, metadonnees, nombre de passages indexes."
)
```

### Injection de dependance

`IndexDocumentTool` cree deja son propre `QdrantVectorStore` dans `__init__`. La nouvelle methode `find_document_by_filename` est appelee sur cette instance existante (`self._vector_store`). Pas de changement d'architecture necessaire.

## Fichiers impactes

| Fichier | Modification |
|---------|-------------|
| `src/services/vector/qdrant_store.py` | Ajouter `find_document_by_filename()` |
| `src/mcp/tools/index_document.py` | Ajouter verification doublon dans `_do_execute()` + maj description |
| `tests/unit/mcp/test_index_document.py` | Tests doublon (already_indexed=True, nouveau fichier) |
| `tests/unit/services/test_qdrant_store.py` | Test `find_document_by_filename` |

## Schema de la reponse (cas doublon)

```json
{
  "already_indexed": true,
  "document_id": "abc-123-def",
  "filename": "rapport.pdf",
  "total_chunks": 42,
  "ingested_at": "2026-01-15T10:30:00+00:00",
  "message": "Ce document est deja indexe. Utilisez le document_id pour search_documents. Pour re-indexer, supprimez d'abord avec delete_document."
}
```

Le LLM recoit `already_indexed: true` et le `document_id` → il peut enchainer directement avec `search_documents` sans re-indexer.

## Schema de la reponse (cas normal, inchange)

```json
{
  "document_id": "new-uuid",
  "document_type": "pdf",
  "filename": "rapport.pdf",
  "chunks_stored": 42,
  "has_tables": true,
  "processing_time_seconds": 12.5
}
```

Pas de champ `already_indexed` (absent = faux). Retro-compatible.

## Tests

### Unit tests - `IndexDocumentTool`

```python
class TestDuplicateIndexationGuard:
    """Tests pour la protection contre la double indexation."""

    @pytest.mark.asyncio
    async def test_already_indexed_returns_existing(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """Si le fichier est deja indexe, retourne l'ID existant."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value={
                "document_id": "existing-doc-id",
                "filename": "rapport.pdf",
                "total_chunks": 42,
                "ingested_at": "2026-01-15T10:30:00+00:00",
            }
        )

        result = await tool_with_mocks.execute(
            {"file_path": "/data/docs/rapport.pdf"}
        )

        assert result["already_indexed"] is True
        assert result["document_id"] == "existing-doc-id"
        assert result["total_chunks"] == 42
        # Verification que le pipeline n'a PAS ete execute
        tool_with_mocks._pdf_orchestrator.process_and_index.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_file_indexes_normally(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """Si le fichier n'est pas indexe, pipeline normal."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value=None
        )

        result = await tool_with_mocks.execute(
            {"file_path": "/data/docs/nouveau.pdf"}
        )

        assert "already_indexed" not in result
        assert "document_id" in result
```

### Unit tests - `QdrantVectorStore`

```python
class TestFindDocumentByFilename:
    """Tests pour find_document_by_filename."""

    @pytest.mark.asyncio
    async def test_found(self, store_with_mock_client: QdrantVectorStore) -> None:
        """Retourne les infos si le document existe."""
        # Mock scroll retourne un point
        store_with_mock_client._client.scroll.return_value = (
            [MagicMock(payload={"document_id": "doc-1", "ingested_at": "..."})],
            None,
        )
        store_with_mock_client._client.count.return_value = MagicMock(count=42)

        result = await store_with_mock_client.find_document_by_filename("rapport.pdf")

        assert result is not None
        assert result["document_id"] == "doc-1"
        assert result["total_chunks"] == 42

    @pytest.mark.asyncio
    async def test_not_found(self, store_with_mock_client: QdrantVectorStore) -> None:
        """Retourne None si le document n'existe pas."""
        store_with_mock_client._client.scroll.return_value = ([], None)

        result = await store_with_mock_client.find_document_by_filename("inconnu.pdf")

        assert result is None
```

## Ce qui n'est PAS dans cette spec

- **Tracking `in_progress`** : Le tool MCP est synchrone (le LLM attend la reponse). Le cas de double appel concurrent est negligeable en usage MCP normal. Over-engineering pour l'instant.
- **Tool `get_indexing_status` separe** : Pas necessaire car `index_document` retourne deja l'info. Le LLM peut aussi utiliser `list_indexed_documents` pour verifier.
- **Deduplication par hash** : Le filename est suffisant pour le cas d'usage (le LLM raisonne en noms de fichiers, pas en hashs).
- **Re-indexation forcee** : Le LLM peut `delete_document` puis `index_document`. Le message de retour le guide explicitement.
