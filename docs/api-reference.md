# Reference API

## Endpoints REST

### Health Checks

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/` | GET | Information du service |
| `/health/live` | GET | Liveness probe |
| `/health/ready` | GET | Readiness probe avec statut des dependances |
| `/health` | GET | Health check complet |

### Documents

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/api/v1/documents/index` | POST | Indexer un nouveau PDF |
| `/api/v1/documents/{document_id}` | GET | Informations d'un document |
| `/api/v1/documents/{document_id}` | DELETE | Supprimer un document de l'index |
| `/api/v1/documents` | GET | Statistiques de la collection |

#### POST /api/v1/documents/index

Indexe un fichier PDF dans le systeme.

**Parametres (multipart/form-data)** :
- `file` : Fichier PDF a indexer

**Reponse** :
- `document_id` : Identifiant unique du document
- `filename` : Nom du fichier
- `total_pages` : Nombre de pages
- `chunks_created` : Nombre de chunks generes
- `processing_time_seconds` : Temps de traitement

### Recherche

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/api/v1/search` | GET | Recherche avec query param |
| `/api/v1/search` | POST | Recherche avec body JSON |

#### GET /api/v1/search

**Parametres** :
- `q` (requis) : Requete de recherche
- `top_k` : Nombre de resultats (defaut: 5)
- `score_threshold` : Seuil de score (defaut: 0.0)

#### POST /api/v1/search

**Body JSON** :
- `query` (requis) : Texte de recherche
- `top_k` : Nombre de resultats
- `score_threshold` : Seuil de pertinence
- `filters` : Filtres optionnels (document_id, content_type, page_range, has_table)

**Reponse** :
- `query` : Requete originale
- `results` : Liste de resultats avec score, contenu, et metadata

---

## Serveur MCP (JSON-RPC 2.0)

Endpoint : `POST /mcp`

### Methodes Disponibles

| Methode | Description |
|---------|-------------|
| `initialize` | Initialise la session MCP |
| `tools/list` | Liste les outils disponibles |
| `tools/call` | Execute un outil |

### Tools MCP

| Tool | Description |
|------|-------------|
| `index_document` | Extrait et indexe un document (PDF, Excel, Word) |
| `search_documents` | Recherche semantique dans les documents indexes |
| `get_document` | Recupere les metadonnees d'un document |
| `delete_document` | Supprime un document de l'index |
| `list_indexed_documents` | Liste tous les documents indexes |
| `list_available_documents` | Liste les documents disponibles (PDF, Excel, Word) |
| `list_available_pdfs` | Alias de list_available_documents (compatibilite) |
| `read_document_content` | Lit le contenu Markdown complet d'un document |
| `get_excel_formulas` | Recupere les formules d'un Excel indexe |

#### index_document

Extrait et indexe un document (PDF, Excel, Word) pour la recherche semantique.
Etape obligatoire avant search_documents.

**Formats supportes** :
- PDF (.pdf) : texte, tableaux, images, OCR
- Excel (.xlsx, .xls) : donnees, formules, feuilles multiples
- Word (.docx) : texte, tableaux, images

**Parametres** :
- `file_path` (requis) : Chemin absolu vers le document. Ex: /data/docs/rapport.xlsx
- `force_ocr` : PDF uniquement - Forcer OCR meme si texte natif (defaut: false)
- `sheets` : Excel uniquement - Noms des feuilles a indexer (toutes si vide)
- `table_format` : Format des tableaux: 'markdown', 'html' ou 'json' (defaut: markdown)

**Retour** :
- `document_id` : Identifiant unique
- `document_type` : Type detecte (pdf, excel, word)
- `filename` : Nom du fichier
- `chunks_stored` : Nombre de chunks indexes
- `has_tables` : Presence de tableaux
- `has_formulas` : Excel - Presence de formules
- `has_images` : Presence d'images
- `sheet_names` : Excel - Liste des feuilles

#### search_documents

Recherche dans les documents indexes par similarite semantique.
Requiert: documents indexes via index_document.

**Parametres** :
- `query` (requis) : Question en langage naturel. Ex: 'comment configurer X?'
- `top_k` : Nombre de passages a retourner (1-100, defaut: 5)
- `filters` : Filtres optionnels :
  - `document_id` : Limiter a un document specifique
  - `doc_filename` : Filtrer par nom de fichier
  - `document_type` : Filtrer par type (pdf, excel, word)
  - `has_table` : Chunks contenant des tableaux
  - `has_image` : Chunks contenant des images
  - `has_formula` : Excel - Chunks avec formules
  - `sheet_name` : Excel - Filtrer par feuille

**Retour** : Passages pertinents avec score et numero de page

#### get_document

Recupere les infos d'un document deja indexe.
Utiliser pour verifier si un document existe ou voir son contenu.

**Parametres** :
- `document_id` (requis) : ID du document (retourne par index_document)

**Retour** : Metadonnees, nombre de pages, apercu des passages

#### delete_document

Supprime un document de l'index vectoriel (Qdrant).
Ne supprime PAS le fichier PDF source.

**Parametres** :
- `document_id` (requis) : ID du document a supprimer

**Retour** : Nombre de chunks supprimes, statut (deleted/not_found)

#### list_indexed_documents

Liste tous les documents deja indexes dans Qdrant.
Utiliser pour connaitre les document_id disponibles.

**Parametres** : Aucun

**Retour** : Liste des documents avec document_id, filename, title, total_chunks, ingested_at

#### list_available_documents

Liste les fichiers disponibles pour indexation (PDF, Excel, Word).
Utiliser pour savoir quels documents peuvent etre indexes.

**Parametres** :
- `type_filter` (optionnel) : Filtrer par type: 'pdf', 'excel', 'word', 'all' (defaut: all)
- `subdirectory` (optionnel) : Sous-dossier relatif a scanner
- `recursive` (optionnel) : Scanner recursivement (defaut: true)

**Retour** :
- `base_path` : Chemin du dossier scanne
- `total_files` : Nombre total de fichiers
- `by_type` : Statistiques par type {pdf: N, excel: M, ...}
- `files` : Liste des fichiers avec:
  - `filename` : Nom du fichier
  - `path` : Chemin absolu (pour index_document)
  - `relative_path` : Chemin relatif
  - `type` : Type de document (pdf, excel, word)
  - `size_mb` : Taille en MB
  - `extension` : Extension du fichier

#### list_available_pdfs

Alias de `list_available_documents` pour compatibilite.
Utiliser `list_available_documents` de preference.

#### get_excel_formulas

Recupere toutes les formules d'un document Excel indexe.
Requiert: document Excel indexe via index_document.

**Parametres** :
- `document_id` (requis) : ID du document Excel (retourne par index_document)
- `sheet` (optionnel) : Filtrer par nom de feuille
- `cell_range` (optionnel) : Filtrer par plage de cellules. Ex: 'A1:D10'

**Retour** :
- `document_id` : ID du document
- `total_formulas` : Nombre de formules trouvees
- `formulas` : Liste des formules avec:
  - `sheet` : Nom de la feuille
  - `cell` : Reference de cellule (ex: C10)
  - `formula` : Formule brute (ex: =SUM(C2:C9))
  - `result` : Resultat calcule

**Exemple d'utilisation** :

```json
// Toutes les formules
{"document_id": "doc-abc123"}

// Formules de la feuille "Data"
{"document_id": "doc-abc123", "sheet": "Data"}

// Formules dans la plage A1:D10
{"document_id": "doc-abc123", "cell_range": "A1:D10"}
```

#### read_document_content

Lit le contenu Markdown complet d'un document indexe.
Utiliser pour lire/analyser un document entier ou des pages specifiques.

**Parametres** :
- `document_id` (requis) : ID du document (retourne par index_document ou list_indexed_documents)
- `page_start` (optionnel) : Page de debut (1-indexed, inclus)
- `page_end` (optionnel) : Page de fin (1-indexed, inclus)
- `include_chunks_detail` (optionnel) : Inclure les metadonnees de chaque chunk (defaut: false)

**Retour** :
- `document_id`, `filename` : Identifiants du document
- `total_pages`, `total_chunks`, `total_tokens` : Statistiques du document complet
- `pages_returned`, `chunks_returned`, `tokens_returned` : Statistiques de la selection
- `content` : Contenu Markdown complet
- `chunks_detail` : Metadonnees par chunk (si demande)

**Exemple d'utilisation** :

```json
// Lire tout le document
{"document_id": "doc-abc123"}

// Lire pages 5 a 10
{"document_id": "doc-abc123", "page_start": 5, "page_end": 10}

// Lire avec details des chunks
{"document_id": "doc-abc123", "include_chunks_detail": true}
```

---

## Filtres de Recherche

Les filtres suivants sont disponibles pour affiner les recherches :

| Filtre | Type | Description |
|--------|------|-------------|
| `document_id` | string | Limiter a un document |
| `content_type` | string | Type de contenu (text, table, code) |
| `page_range` | tuple | Plage de pages (start, end) |
| `has_table` | boolean | Chunks contenant des tableaux |
| `has_image` | boolean | Chunks contenant des images |
| `section_title` | string | Titre de section specifique |
| `doc_filename` | string | Nom de fichier du document |

---

## Codes d'Erreur

| Code | Description |
|------|-------------|
| 400 | Requete invalide |
| 404 | Document non trouve |
| 413 | Fichier trop volumineux |
| 422 | Erreur de validation |
| 500 | Erreur interne |

### Erreurs JSON-RPC

| Code | Message |
|------|---------|
| -32600 | Invalid Request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |

### Format d'Erreur pour LLM

Les erreurs MCP sont formatees pour etre actionnables par un LLM :

```
ERROR [CODE]: Message d'erreur
SUGGESTION: Action corrective recommandee
PARAMETER: Parametre concerne (si applicable)
RETRY: Corriger et reessayer (si applicable)
```

**Exemple** :

```
ERROR [PDF_NOT_FOUND]: Fichier PDF introuvable: /bad/path.pdf
SUGGESTION: Verifier le chemin. Utiliser un chemin absolu commencant par /.
PARAMETER: file_path
RETRY: Corriger et reessayer
```

**Codes d'erreur applicatifs** :

| Code | Description | Retry |
|------|-------------|-------|
| `FILE_NOT_FOUND` | Fichier introuvable | Oui |
| `INVALID_PDF` | PDF invalide ou corrompu | Non |
| `DOCUMENT_NOT_INDEXED` | Document non indexe | Non |
| `EMPTY_QUERY` | Requete de recherche vide | Oui |
| `NO_RESULTS` | Aucun resultat trouve | Oui |
| `INVALID_FORMAT` | Format non supporte | Oui |
| `INVALID_PARAMETER` | Parametre invalide | Oui |
| `SERVICE_UNAVAILABLE` | Service externe indisponible | Oui |

---

## Patterns de Description d'Outils MCP

Cette section definit les bonnes pratiques pour les descriptions d'outils MCP, optimisees pour les LLM.

### Objectif

Les descriptions doivent permettre aux LLM de :
1. **Choisir le bon tool** rapidement
2. **Comprendre les erreurs** et ne pas les repeter
3. **Passer les bons parametres** du premier coup

### Structure de Description

```
[VERBE D'ACTION] + [CONTEXTE D'USAGE] + [FORMAT RETOUR]
```

**Regles :**
- Max 150 caracteres pour la description principale
- Commencer par un verbe d'action (Extrait, Recherche, Indexe, Recupere)
- Inclure "Utiliser quand..." si confusion possible avec un autre tool
- Eviter le jargon technique (pas "chunks", dire "passages")

**Exemple** :

```python
# Mauvais
description = (
    "Extrait le contenu structure d'un fichier PDF. "
    "Retourne le texte en Markdown avec tableaux, images et metadata."
)

# Bon
description = (
    "Extrait le texte d'un PDF sans l'indexer. "
    "Utiliser pour lire un PDF une seule fois. "
    "Retourne: markdown, tableaux, metadonnees."
)
```

### Pattern de Descriptions de Parametres

```python
{
    "param_name": {
        "type": "string",
        "description": "[CE QUE C'EST] [FORMAT ATTENDU] [EXEMPLE]",
    }
}
```

**Exemples** :

```python
# Mauvais
"file_path": {"description": "Chemin vers le fichier PDF"}

# Bon
"file_path": {"description": "Chemin absolu vers le PDF. Ex: /data/rapport.pdf"}

# Mauvais
"top_k": {"description": "Nombre de resultats"}

# Bon
"top_k": {"description": "Nombre de passages a retourner (1-100, defaut: 5)"}
```

---

## Structure ToolError

Les erreurs sont structurees pour guider le LLM vers une correction.

```python
@dataclass
class ToolError:
    """Erreur structuree pour guider le LLM."""

    code: str           # Code unique, ex: "FILE_NOT_FOUND"
    message: str        # Description courte du probleme
    suggestion: str     # Action corrective pour le LLM
    parameter: str | None = None  # Parametre concerne
    retry: bool = False  # True si le LLM peut reessayer
```

### Factory Functions

| Fonction | Code | Usage |
|----------|------|-------|
| `file_not_found_error(path)` | FILE_NOT_FOUND | Fichier introuvable |
| `invalid_pdf_error(path)` | INVALID_PDF | PDF invalide |
| `document_not_indexed_error(id)` | DOCUMENT_NOT_INDEXED | Document non indexe |
| `empty_query_error()` | EMPTY_QUERY | Requete vide |
| `no_results_error(query)` | NO_RESULTS | Aucun resultat |
| `invalid_format_error(value, options)` | INVALID_FORMAT | Format non supporte |
| `invalid_parameter_error(param, msg, suggestion)` | INVALID_PARAMETER | Parametre invalide |
| `service_unavailable_error(service)` | SERVICE_UNAVAILABLE | Service indisponible |

### Exemple Complet

```python
# Entree erronee du LLM
{"name": "search_documents", "arguments": {"query": ""}}

# Reponse erreur
{
    "content": [{
        "type": "text",
        "text": (
            "ERROR [EMPTY_QUERY]: La requete de recherche est vide\n"
            "SUGGESTION: Fournir une requete en langage naturel.\n"
            "PARAMETER: query\n"
            "RETRY: Oui"
        )
    }],
    "isError": True
}
```

---

## References

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Anthropic Tool Use Best Practices](https://docs.anthropic.com/en/docs/tool-use)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
