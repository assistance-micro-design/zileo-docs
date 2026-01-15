# MCP Zileo RAG - Tools Reference

**Serveur MCP**: `MCP Zileo RAG`
**Version**: `0.1.0`
**Protocole**: JSON-RPC 2.0

## Tools disponibles

| Tool | Description |
|------|-------------|
| `index_document` | Indexer un document (PDF/Excel/Word) |
| `search_documents` | Recherche sémantique |
| `get_document` | Infos d'un document indexé |
| `delete_document` | Supprimer de l'index |
| `list_indexed_documents` | Lister les documents indexés |
| `list_available_documents` | Lister les fichiers disponibles |
| `get_excel_formulas` | Formules Excel |
| `read_document_content` | Lire le contenu Markdown |

---

## index_document

Extrait et indexe un document pour la recherche sémantique. Étape obligatoire avant `search_documents`.

**Formats supportés**: PDF, Excel (.xlsx, .xls), Word (.docx)

### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `file_path` | string | Oui | Chemin absolu vers le document |
| `force_ocr` | boolean | Non | PDF: forcer OCR même si texte natif (défaut: false) |
| `sheets` | array[string] | Non | Excel: feuilles à indexer (toutes si vide) |
| `table_format` | string | Non | Format tableaux: `markdown` ou `html` (défaut: markdown) |

### Retour

```json
{
  "document_id": "doc-abc123",
  "document_type": "pdf|excel|word",
  "filename": "rapport.pdf",
  "chunks_stored": 42,
  "has_tables": true,
  "has_formulas": false,
  "has_images": true,
  "processing_time_seconds": 12.5
}
```

---

## search_documents

Recherche dans les documents indexés par similarité sémantique.

### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `query` | string | Oui | Question en langage naturel |
| `top_k` | integer | Non | Nombre de résultats (1-100, défaut: 5) |
| `score_threshold` | number | Non | Score minimum (0.0-1.0, défaut: 0.7) |
| `filters` | object | Non | Filtres optionnels (voir ci-dessous) |

### Filtres disponibles

| Filtre | Type | Description |
|--------|------|-------------|
| `document_id` | string | Limiter à un document |
| `doc_filename` | string | Filtrer par nom de fichier |
| `document_type` | string | `pdf`, `excel` ou `word` |
| `has_table` | boolean | Passages avec tableaux |
| `has_image` | boolean | Passages avec images |
| `has_formula` | boolean | Excel: chunks avec formules |
| `text_search` | string | Recherche full-text exacte |
| `sheet_name` | string | Excel: filtrer par feuille |

### Retour

```json
{
  "query": "comment configurer X?",
  "total_results": 5,
  "results": [
    {
      "chunk_id": "chunk-123",
      "document_id": "doc-abc",
      "content": "...",
      "score": 0.89,
      "page_numbers": [1, 2],
      "document_type": "pdf"
    }
  ]
}
```

---

## get_document

Récupère les informations d'un document déjà indexé.

### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document (retourné par `index_document`) |

### Retour

```json
{
  "document_id": "doc-abc123",
  "filename": "rapport.pdf",
  "title": "Rapport annuel",
  "total_pages": 50,
  "total_chunks": 42,
  "total_tokens": 15000,
  "chunks": [...]
}
```

---

## delete_document

Supprime un document de l'index vectoriel (Qdrant). Ne supprime **pas** le fichier source.

### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document à supprimer |

### Retour

```json
{
  "document_id": "doc-abc123",
  "chunks_deleted": 42,
  "status": "deleted"
}
```

---

## list_indexed_documents

Liste tous les documents indexés dans Qdrant.

### Paramètres

Aucun paramètre requis.

### Retour

```json
{
  "total_documents": 10,
  "documents": [
    {
      "document_id": "doc-abc123",
      "filename": "rapport.pdf",
      "total_chunks": 42,
      "ingested_at": "2026-01-15T10:30:00Z"
    }
  ]
}
```

---

## list_available_documents

Liste les fichiers disponibles pour indexation dans le dossier monté.

### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `type_filter` | string | Non | `pdf`, `excel`, `word` ou `all` (défaut: all) |
| `subdirectory` | string | Non | Sous-dossier à explorer |
| `recursive` | boolean | Non | Explorer récursivement (défaut: true) |

### Retour

```json
{
  "base_path": "/app/documents",
  "total_files": 25,
  "files": [
    {
      "filename": "rapport.xlsx",
      "path": "/app/documents/rapport.xlsx",
      "type": "excel",
      "size_bytes": 102400
    }
  ]
}
```

---

## get_excel_formulas

Récupère les formules d'un document Excel indexé.

### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document Excel |
| `sheet` | string | Non | Filtrer par nom de feuille |
| `cell_range` | string | Non | Filtrer par plage (ex: `A1:D10`) |

### Retour

```json
{
  "document_id": "doc-excel123",
  "total_formulas": 15,
  "formulas": [
    {
      "sheet": "Feuil1",
      "cell": "B5",
      "formula": "=SUM(A1:A4)",
      "result": 100
    }
  ]
}
```

---

## read_document_content

Lit le contenu Markdown complet d'un document indexé.

### Paramètres

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document |
| `page_start` | integer | Non | Page de début (1-indexed) |
| `page_end` | integer | Non | Page de fin (1-indexed) |
| `include_chunks_detail` | boolean | Non | Inclure métadonnées des chunks (défaut: false) |

### Retour

```json
{
  "document_id": "doc-abc123",
  "filename": "rapport.pdf",
  "content": "# Titre\n\nContenu Markdown...",
  "total_tokens": 5000,
  "pages_included": [1, 2, 3]
}
```
