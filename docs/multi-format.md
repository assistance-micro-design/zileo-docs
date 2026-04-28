# Support multi-format

Le serveur indexe et génère des documents PDF, Excel et Word. Le PDF est le format le plus mature (pipeline dédié avec OCR), Excel et Word utilisent un pipeline unifié plus simple.

## Formats supportés

| Format | Extension | Bibliothèque | Indexation | Génération |
|--------|-----------|--------------|------------|------------|
| PDF | `.pdf` | PyMuPDF4LLM + Mistral OCR | ✅ Texte, tables, images, équations | ❌ |
| Excel | `.xlsx` | openpyxl | ✅ Données, formules, valeurs calculées | ✅ via `create_excel_document` |
| Excel legacy | `.xls` | xlrd | ✅ Données (pas de formules) | ❌ |
| Word | `.docx` | docx2python (lecture) / python-docx (écriture) | ✅ Texte, tables, images | ✅ via `create_word_document` |

Non supporté : `.doc` (Word 97-2003), `.xlsb`, `.ppt(x)`.

## Routage

`DocumentRouter` détecte le format depuis l'extension :

```python
SUPPORTED_EXTENSIONS = {".pdf": PDF, ".xlsx": EXCEL, ".xls": EXCEL, ".docx": WORD}
```

## Extraction Excel

`ExcelExtractor` ouvre le fichier `.xlsx` deux fois via openpyxl :
1. `data_only=False` → formules brutes (`=SUM(A1:A10)`)
2. `data_only=True` → valeurs calculées

Pour `.xls` : seul xlrd, formules non récupérables.

Données extraites :
- Valeurs de cellules (texte, nombres, dates, booléens)
- Formules + résultats calculés
- Cellules fusionnées
- Noms de feuilles
- Tables officielles Excel (créées via Insert > Table). Si absent, fallback sur extraction brute via `_cells_to_markdown()`.

## Extraction Word

`WordExtractor` utilise `docx2python` :
- Paragraphes avec détection de heading (regex sur le texte, pas sur les styles Word)
- Tables (lignes/colonnes)
- Images embeddées (encodées en base64)
- Métadonnées (auteur, titre)

## Chunking Excel/Word (unifié)

Pas de `SmartChunker`. Logique dans `IndexDocumentTool._create_chunks_from_unified()` :

| Chunk | Contenu | Limite |
|-------|---------|--------|
| Principal | `content_markdown` du document | 8 000 caractères |
| Overflow | Suite du contenu si > 8 000 | Blocs de 4 000, overlap 200 |
| Formulas (Excel) | Liste des formules avec résultats | 50 formules max |

Pas de régions protégées (tables, code), pas de hiérarchie de sections (contrairement au PDF).

## Modèles de données

### `UnifiedDocument`

Conteneur commun pour Excel/Word :

| Champ | Type | Rôle |
|-------|------|------|
| `metadata` | `UnifiedMetadata` | type, compteurs, drapeaux (`has_tables`, `has_formulas`, `has_images`), `file_hash` |
| `content_markdown` | `str` | Contenu pour embedding |
| `structured_data` | `StructuredData` | Tables, formules, images |

### Excel

| Modèle | Rôle |
|--------|------|
| `ExcelCell` | position + valeur + formule + type |
| `ExcelFormula` | référence cellule + feuille + formule + résultat |
| `ExcelSheet` | grille de cellules + tables + formules + cellules fusionnées |
| `ExcelDocument` | document complet |

### Word

| Modèle | Rôle |
|--------|------|
| `WordParagraph` | texte + niveau de heading + style |
| `WordTable` | grille de `WordTableCell` |
| `WordImage` | nom + MIME + taille + base64 |
| `ContentBlock` | bloc ordonné (paragraphe / heading / table / image) |
| `WordDocument` | document complet |

## Génération Excel

```
LLM → CreateExcelTool → ExcelGenerator → fichier .xlsx
LLM → EditExcelTool   → ExcelEditor    → fichier .xlsx modifié
                                ↓
                         (composition avec
                          ExcelGenerator pour
                          styles/charts/validations)
```

Fichiers créés dans `OUTPUT_PATH`.

`create_excel_document` accepte :
- Données (`headers` + `rows`, max 10 000 lignes / 500 colonnes)
- Styles (police, couleur, bordures, format de nombre)
- Graphiques (`bar`, `column`, `line`, `pie`, `scatter`, `area`)
- Validations (listes, entiers, décimaux, dates, longueur de texte)
- Cellules fusionnées
- Propriétés (auto-filtre, volets figés, couleur d'onglet)

`edit_excel_document` applique une liste d'opérations (`EditOp`, discriminated union via le champ `op`). Voir [generation-guide.md](generation-guide.md) pour les 13 opérations détaillées.

## Génération Word

```
LLM → CreateWordTool → WordGenerator → fichier .docx
```

`create_word_document` reçoit du **Markdown** et le convertit :

| Markdown | Word |
|----------|------|
| `# H1` à `###### H6` | Heading 1-6 |
| `**bold**`, `*italic*` | Formatage inline |
| `- item` / `1. item` (imbriquables) | Listes à puces / numérotées |
| Tables Markdown | Tables Word |
| ` ``` ` | Bloc de code (police monospace) |
| `> quote` | Citation |
| `---` | Saut de page |

Métadonnées : `title`, `author`. Limite : `content` < 500 000 caractères.

## Inspection

`inspect_generated_file` ouvre un fichier Excel généré et retourne sa structure dans le **vocabulaire des opérations d'édition**, ce qui permet au LLM d'enchaîner directement `inspect → edit` sans transformation.

Retour pour Excel : feuilles, colonnes, échantillon de données, graphiques, validations, propriétés.

Paramètres :
- `filename` : fichier dans `OUTPUT_PATH` (`.xlsx`)
- `max_rows_per_sheet` : 1-100, défaut 10

## Limitations connues

### Excel (indexation)
- `.xls` : pas de formules (xlrd)
- Graphiques : non extraits
- Macros VBA : ignorées
- Fichiers protégés par mot de passe : erreur à l'ouverture

### Excel (génération/édition)
- Taille max : `MAX_OUTPUT_FILE_SIZE_MB` (défaut 10 Mo)
- 50 feuilles max / 10 000 lignes max / 500 colonnes max par feuille
- 100 opérations max par appel à `edit_excel_document`
- Erreurs de graphique : non bloquantes (comptées comme `skipped`)

### Word
- `.doc` non supporté → convertir en `.docx`
- Détection des headings par regex (pas par styles)
- Commentaires, révisions, mise en page complexe (colonnes, sections) : non extraits
- Génération : tables limitées au modèle simple (pas de cellules fusionnées)

### Recherche
- Recherche sémantique de **noms propres** dans Excel : mauvais résultats au seuil par défaut. Utiliser `search_mode: hybrid` (défaut) ou baisser `score_threshold` à 0.3 et ajouter `text_search`.
