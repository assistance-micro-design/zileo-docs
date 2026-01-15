# Traitement Multi-Format : Excel et Word

Ce document decrit l'extension du serveur MCP Zileo PDF pour traiter les documents Excel (.xlsx, .xls) et Word (.docx), en plus des PDF.

## Vue d'Ensemble

### Formats Supportes

| Format | Extension | Bibliotheque | Fonctionnalites |
|--------|-----------|--------------|-----------------|
| PDF | .pdf | PyMuPDF + Mistral OCR | Texte, tableaux, images, OCR |
| Excel moderne | .xlsx | openpyxl | Donnees, formules, styles |
| Excel legacy | .xls | xlrd | Donnees uniquement |
| Word moderne | .docx | docx2python | Texte, tableaux, images |

### Donnees Extraites

**Excel** :
- Valeurs des cellules (texte, nombres, dates, booleens)
- Formules brutes (`=SUM(A1:A10)`)
- Resultats calcules des formules
- Cellules fusionnees
- Noms de feuilles et plages nommees

**Word** :
- Paragraphes avec styles (titres, corps)
- Tableaux avec structure
- Images integrees (base64)
- Metadonnees du document

---

## Architecture

```
                          PIPELINE UNIFIE
+-----------------------------------------------------------------------------+
|                                                                             |
|  +----------+   +----------+   +----------+                                 |
|  |   PDF    |   |  Excel   |   |   Word   |                                 |
|  |  .pdf    |   |.xlsx/.xls|   |  .docx   |                                 |
|  +----+-----+   +----+-----+   +----+-----+                                 |
|       |              |              |                                       |
|       v              v              v                                       |
|  +--------------------------------------------------------------+          |
|  |              DocumentRouter (detection type)                 |          |
|  +--------------------------------------------------------------+          |
|       |              |              |                                       |
|       v              v              v                                       |
|  +----------+   +----------+   +----------+                                 |
|  |PDFExtract|   |ExcelExtr.|   |WordExtr. |                                 |
|  |(existant)|   |(nouveau) |   |(nouveau) |                                 |
|  +----+-----+   +----+-----+   +----+-----+                                 |
|       |              |              |                                       |
|       v              v              v                                       |
|  +--------------------------------------------------------------+          |
|  |              UnifiedContent (format commun)                  |          |
|  +--------------------------------------------------------------+          |
|       |                                                                     |
|       v                                                                     |
|  +----------+   +----------+   +----------+                                 |
|  | Chunker  |-->| Embedder |-->|  Qdrant  |                                 |
|  |(existant)|   |(existant)|   |(existant)|                                 |
|  +----------+   +----------+   +----------+                                 |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### Structure des Fichiers

```
src/
+-- services/
|   +-- document/                    # Abstraction multi-format
|   |   +-- __init__.py
|   |   +-- router.py               # Detection et routing par type
|   |   +-- base_extractor.py       # Interface commune
|   +-- excel/                       # Extraction Excel
|   |   +-- __init__.py
|   |   +-- extractor.py            # Extraction donnees + formules
|   |   +-- formula_parser.py       # Parsing des formules Excel
|   +-- word/                        # Extraction Word
|   |   +-- __init__.py
|   |   +-- extractor.py            # Extraction texte/tables/images
|   +-- pdf/                         # Existant (adapte)
|
+-- models/
|   +-- types.py                     # TypeAlias partages
|   +-- excel.py                     # Modeles Excel
|   +-- word.py                      # Modeles Word
|   +-- unified.py                   # Format unifie
|
+-- mcp/tools/
    +-- index_document.py           # Indexation unifiee
    +-- get_excel_formulas.py       # Formules Excel
    +-- list_available_documents.py # Liste multi-format
```

---

## Modeles de Donnees

### Types Partages

```python
# src/models/types.py
from datetime import datetime
from typing import TypeAlias

# Valeur possible d'une cellule (Excel/Word table)
CellValue: TypeAlias = str | int | float | bool | datetime | None

# Resultat calcule d'une formule Excel
FormulaResult: TypeAlias = str | int | float | bool | None

# Identifiants
DocumentId: TypeAlias = str
ChunkId: TypeAlias = str
```

### DocumentType

```python
class DocumentType(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    WORD = "word"
```

### UnifiedDocument

Format commun pour tous les types de documents :

```python
class UnifiedDocument(BaseModel):
    metadata: UnifiedMetadata
    content_markdown: str  # Contenu pour embedding
    structured_data: StructuredData  # Tables, formules, images
```

### Metadonnees Unifiees

```python
class UnifiedMetadata(BaseModel):
    document_id: str
    filename: str
    file_path: str
    document_type: DocumentType
    original_format: str  # .pdf, .xlsx, .docx

    # Contenu
    page_count: int | None  # Pages (PDF) ou feuilles (Excel)
    word_count: int

    # Drapeaux
    has_tables: bool
    has_images: bool
    has_formulas: bool  # Excel uniquement
    has_ocr_content: bool  # PDF uniquement

    # Specifique Excel
    sheet_names: list[str]
```

---

## Extraction Excel

### Modeles

**ExcelCell** : Cellule avec valeur et formule optionnelle
```python
class ExcelCell(BaseModel):
    row: int
    column: int
    column_letter: str  # A, B, C...
    value: CellValue
    formula: str | None
    cell_type: CellType  # text, number, date, boolean, formula, empty
```

**ExcelFormula** : Formule avec contexte
```python
class ExcelFormula(BaseModel):
    cell: str           # Reference (ex: C10)
    sheet: str          # Nom de la feuille
    formula: str        # Formule brute (ex: =SUM(A1:A10))
    result: FormulaResult
    dependencies: list[str]  # Cellules referencees
```

**ExcelSheet** : Feuille avec donnees structurees
```python
class ExcelSheet(BaseModel):
    name: str
    index: int
    cells: list[list[ExcelCell]]
    tables: list[ExcelTable]
    formulas: list[ExcelFormula]
    merged_cells: list[str]
```

### Extracteur

L'extracteur charge le fichier deux fois :
1. `data_only=False` : Pour les formules brutes
2. `data_only=True` : Pour les valeurs calculees

```python
class ExcelExtractor:
    async def extract(self, file_path: Path) -> ExcelDocument:
        if file_path.suffix == ".xlsx":
            return await self._extract_xlsx(file_path)
        elif file_path.suffix == ".xls":
            return await self._extract_xls(file_path)
```

### Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| .xls sans formules | Les formules ne sont pas recuperables | Documenter, afficher resultats |
| Graphiques | Non extraits | Future evolution |
| Macros VBA | Ignorees | Securite, non pertinent |
| Fichiers proteges | Erreur a l'ouverture | Demander mot de passe |

---

## Extraction Word

### Modeles

**WordParagraph** : Paragraphe avec style
```python
class WordParagraph(BaseModel):
    text: str
    style: str | None
    level: HeadingLevel  # BODY, HEADING_1..6
    is_bold: bool
    is_italic: bool
```

**WordTable** : Tableau avec cellules
```python
class WordTable(BaseModel):
    rows: list[list[WordTableCell]]
    headers: list[str] | None
```

**ContentBlock** : Bloc ordonne
```python
class ContentBlock(BaseModel):
    content_type: ContentType  # paragraph, heading, table, image
    order: int  # Position dans le document
    paragraph: WordParagraph | None
    table: WordTable | None
    image: WordImage | None
```

### Extracteur

```python
class WordExtractor:
    def __init__(self, extract_images: bool = True) -> None:
        self.extract_images = extract_images

    async def extract(self, file_path: Path) -> WordDocument:
        # Utilise docx2python pour extraction complete
```

### Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Format .doc non supporte | Fichiers Word 97-2003 ignores | Convertir en .docx |
| Styles complexes | Styles personnalises non detectes | Heuristiques sur le texte |
| Commentaires/Revisions | Non extraits | Future evolution |

---

## Outils MCP

### index_document

Indexe un document (PDF, Excel, Word) pour la recherche semantique.

**Parametres** :
| Parametre | Type | Description |
|-----------|------|-------------|
| `file_path` | string (requis) | Chemin absolu vers le document |
| `force_ocr` | boolean | PDF uniquement : forcer OCR |
| `sheets` | array | Excel uniquement : feuilles a indexer |
| `table_format` | string | Format des tableaux (markdown/html/json) |

**Retour** :
```json
{
  "document_id": "uuid",
  "document_type": "excel",
  "filename": "rapport.xlsx",
  "chunks_stored": 42,
  "has_tables": true,
  "has_formulas": true,
  "sheet_names": ["Donnees", "Calculs"]
}
```

### search_documents

Recherche semantique avec filtres multi-format.

**Nouveaux parametres** :
| Parametre | Type | Description |
|-----------|------|-------------|
| `score_threshold` | number | Seuil de similarite (0.0-1.0, defaut: 0.7) |
| `filters.document_type` | string | Filtrer par type : pdf, excel, word |
| `filters.has_formula` | boolean | Excel : chunks avec formules |
| `filters.sheet_name` | string | Excel : filtrer par feuille |
| `filters.text_search` | string | Recherche full-text exacte |

**Recommandations score_threshold** :
- Recherche de concepts : `0.7` (defaut)
- Recherche de noms propres : `0.5`
- Recherche tres large : `0.3`

**Exemple : rechercher une personne dans un Excel** :
```json
{
  "query": "informations du coproprietaire",
  "filters": {
    "text_search": "GRANDFOND",
    "document_type": "excel"
  },
  "score_threshold": 0.3
}
```

### get_excel_formulas

Recupere les formules d'un document Excel indexe.

**Parametres** :
| Parametre | Type | Description |
|-----------|------|-------------|
| `document_id` | string (requis) | ID du document Excel |
| `sheet` | string | Filtrer par nom de feuille |
| `cell_range` | string | Filtrer par plage (ex: A1:D10) |

**Retour** :
```json
{
  "document_id": "doc-abc123",
  "total_formulas": 15,
  "formulas": [
    {
      "sheet": "Calculs",
      "cell": "C10",
      "formula": "=SUM(C2:C9)",
      "result": 1500.0
    }
  ]
}
```

### list_available_documents

Liste les fichiers disponibles pour indexation.

**Parametres** :
| Parametre | Type | Description |
|-----------|------|-------------|
| `type_filter` | string | pdf, excel, word, all (defaut: all) |
| `subdirectory` | string | Sous-dossier a explorer |
| `recursive` | boolean | Explorer recursivement (defaut: true) |

**Retour** :
```json
{
  "total_files": 25,
  "by_type": {"pdf": 10, "excel": 8, "word": 7},
  "files": [
    {
      "filename": "rapport.xlsx",
      "path": "/data/docs/rapport.xlsx",
      "type": "excel",
      "size_mb": 1.5,
      "extension": ".xlsx"
    }
  ]
}
```

---

## Stockage Qdrant

### Metadonnees Etendues

Chaque chunk stocke des metadonnees specifiques au type :

```python
{
    "document_id": "uuid",
    "document_type": "excel|word|pdf",
    "filename": "rapport.xlsx",

    # Specifique Excel
    "sheet_name": "Feuille1",
    "has_formula": True,
    "formulas": [
        {"cell": "C10", "formula": "=SUM(C2:C9)", "result": 1500.0}
    ],

    # Specifique Word
    "has_image": True,
    "heading_level": 2,

    # Commun
    "has_table": True,
    "table_data": [...],
    "page_number": 1,  # ou sheet_index pour Excel
}
```

---

## Bugs Connus et Solutions

### Cellules non indexees sans Table officielle

**Symptome** : La recherche de noms propres dans un fichier Excel retourne 0 resultat.

**Cause** : La methode `get_text_content()` ne rendait que les "Tables officielles" Excel (creees via Insert > Table). Les fichiers Excel avec donnees brutes ne generaient aucun contenu pour l'embedding.

**Solution** : Ajout de `_cells_to_markdown()` dans `ExcelSheet` qui convertit les cellules brutes en tableau Markdown.

### Recherche semantique de noms propres

**Symptome** : La recherche de noms comme "GRANDFOND Helene" retourne 0 resultat meme avec un seuil bas.

**Solutions** :
1. Baisser `score_threshold` a 0.3-0.5
2. Utiliser le filtre `text_search` pour une recherche exacte
3. Combiner les deux approches

---

## Dependances

```toml
# pyproject.toml
[project.dependencies]
openpyxl = "^3.1.0"      # Excel .xlsx
xlrd = "^2.0.0"          # Excel .xls legacy
docx2python = "^2.0.0"   # Word .docx
python-docx = "^1.1.0"   # Creation fichiers test
Pillow = "^10.0.0"       # Traitement images
```

---

## Criteres de Succes

1. **Extraction complete** : Toutes les donnees sont extraites sans perte
2. **Formules preservees** : Les formules Excel sont stockees avec leur resultat
3. **Recherche unifiee** : Un seul `search_documents` pour tous les types
4. **Performance** : < 5s pour un document de 50 pages/feuilles
5. **Tests** : Couverture > 80%
