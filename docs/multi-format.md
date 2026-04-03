# Support multi-format : Excel et Word

Le support Excel et Word a ete ajoute apres le PDF. Le PDF reste le format le plus teste et le plus complet. Excel et Word sont supportes en extraction/indexation et en generation/edition.

## Formats supportes

| Format | Extension | Bibliotheque | Ce qui est extrait |
|--------|-----------|--------------|-------------------|
| PDF | `.pdf` | PyMuPDF4LLM + Mistral OCR | Texte, tableaux, images, equations |
| Excel | `.xlsx` | openpyxl | Donnees, formules, resultats calcules, cellules fusionnees |
| Excel legacy | `.xls` | xlrd | Donnees uniquement |
| Word | `.docx` | docx2python | Texte, tableaux, images (base64) |

## Comment ca fonctionne

### Routage

`DocumentRouter` detecte le format a partir de l'extension du fichier et delegue a l'extracteur correspondant :

```python
SUPPORTED_EXTENSIONS = {".pdf": PDF, ".xlsx": EXCEL, ".xls": EXCEL, ".docx": WORD}
```

Les formats `.doc` (Word 97-2003) et `.xlsb` ne sont pas supportes.

### Extraction Excel

L'extracteur charge le fichier `.xlsx` deux fois via openpyxl :
1. `data_only=False` pour recuperer les formules brutes (`=SUM(A1:A10)`)
2. `data_only=True` pour recuperer les valeurs calculees

Pour les fichiers `.xls`, seul xlrd est utilise. Les formules ne sont pas recuperables dans ce format.

Donnees extraites :
- Valeurs des cellules (texte, nombres, dates, booleens)
- Formules brutes et resultats calcules
- Cellules fusionnees
- Noms de feuilles
- Tables officielles Excel (creees via Insert > Table)

### Extraction Word

L'extracteur utilise `docx2python` pour extraire :
- Paragraphes avec detection du niveau de heading (par regex sur le texte, pas par style Word)
- Tableaux avec structure lignes/colonnes
- Images integrees (converties en base64)
- Metadonnees du document (auteur, titre, etc.)

### Chunking Excel/Word

Le chunking pour Excel et Word n'utilise pas `SmartChunker`. Il est fait directement dans `IndexDocumentTool` avec une logique specifique :

- **Chunk principal** : contenu Markdown du document, tronque a 8000 caracteres
- **Chunks de debordement** : si le contenu depasse 8000 caracteres, decoupage en blocs de 4000 caracteres avec 200 caracteres d'overlap
- **Chunk de formules** : chunk separe contenant les 50 premieres formules du document (Excel uniquement)

Ce chunking est plus simple que celui du PDF. Il ne detecte pas les regions protegees (tableaux, code) et ne preserve pas la hierarchie de sections.

## Modeles de donnees

### UnifiedDocument

Tous les formats sont convertis en `UnifiedDocument`, qui contient :
- `metadata` : `UnifiedMetadata` avec type de document, compteurs, drapeaux
- `content_markdown` : Le contenu en Markdown (pour l'embedding)
- `structured_data` : Tables, formules et images en format structure

### Modeles Excel

- `ExcelCell` : Cellule avec position, valeur, formule, type (`CellType`)
- `ExcelFormula` : Formule avec reference de cellule, feuille, formule brute, resultat, dependances
- `ExcelSheet` : Feuille avec grille de cellules, tables, formules, cellules fusionnees
- `ExcelDocument` : Document complet avec liste de feuilles

### Modeles Word

- `WordParagraph` : Paragraphe avec texte, niveau de heading, style
- `WordTable` : Tableau avec grille de `WordTableCell`
- `WordImage` : Image avec nom, type MIME, taille, contenu base64
- `ContentBlock` : Bloc ordonne (paragraphe, heading, tableau ou image)
- `WordDocument` : Document complet avec liste de blocs de contenu

## Generation et edition Excel

En plus de l'extraction/indexation, le serveur MCP permet de creer et editer des fichiers Excel via deux outils dedies.

### Architecture

```
LLM (Claude, etc.)
    |
    v (tools/call)
+-------------------+     +-------------------+
| CreateExcelTool   |---->| ExcelGenerator    |  -> fichier .xlsx
+-------------------+     +-------------------+
| EditExcelTool     |---->| ExcelEditor       |  -> fichier .xlsx modifie
+-------------------+     +-------------------+
                               |
                               v (composition)
                          ExcelGenerator
                          (reutilise pour styles, charts, validations)
```

Les fichiers sont crees/edites dans `OUTPUT_PATH` (defaut: `/app/output`).

### create_excel_document

Cree un fichier `.xlsx` a partir de definitions de feuilles (`SheetDef`). Chaque feuille peut contenir :
- Donnees (headers + rows, max 10 000 lignes par feuille)
- Styles (police, couleur, bordures, format de nombre)
- Graphiques (bar, line, pie, scatter, area, column)
- Validations de donnees (listes, entiers, decimaux, dates, longueur de texte)
- Cellules fusionnees
- Proprietes de feuille (auto-filtre, volets figes, couleur d'onglet)

### edit_excel_document

Edite un fichier existant via une liste d'operations (`EditOp`). Les operations utilisent un **discriminated union** Pydantic avec le champ `op` comme discriminateur.

**13 operations disponibles** :

| Op | Description |
|----|-------------|
| `update_cells` | Modifier les valeurs de cellules |
| `insert_rows` | Inserer des lignes |
| `delete_rows` | Supprimer des lignes |
| `apply_styles` | Appliquer des styles |
| `add_sheet` | Ajouter une feuille |
| `delete_sheet` | Supprimer une feuille |
| `rename_sheet` | Renommer une feuille |
| `add_chart` | Ajouter un graphique |
| `remove_charts` | Supprimer tous les graphiques d'une feuille |
| `add_data_validation` | Ajouter une validation de donnees |
| `merge_cells` | Fusionner des cellules |
| `unmerge_cells` | Defusionner des cellules |
| `set_sheet_properties` | Modifier les proprietes d'une feuille |

Les operations sont appliquees en sequence. Les erreurs de graphique sont gerees en degradation gracieuse (comptees comme `skipped`).

### Modeles de donnees (generation/edition)

- `SheetDef` : Definition de feuille (headers, rows, styles, charts, validations, merged_cells)
- `ChartDef` : Definition de graphique (type, data_range, categories_range, position, axes)
- `CellStyleDef` : Definition de style (range, police, couleur, bordure, alignement)
- `DataValidationDef` : Definition de validation (range, type, operator, formulas, messages)
- `MergedCellDef` : Definition de fusion (range, value optionnelle)
- `EditOp` : Union discriminee des 13 types d'operations (discriminator: `op`)

Ces modeles sont definis dans `src/models/excel_generation.py` et `src/models/excel_edit.py`.

## Inspection de fichiers generes

L'outil `inspect_generated_file` permet d'inspecter la structure d'un fichier Excel cree par les outils de generation/edition.

### Fonctionnement

Le service `FileInspector` (`src/services/inspection/file_inspector.py`) ouvre le fichier et retourne sa structure dans un format compatible avec les outils d'edition, facilitant ainsi le workflow : creer → inspecter → editer.

**Pour Excel** : retourne les feuilles, colonnes, donnees (echantillon), graphiques, validations, proprietes.

### Parametres

- `filename` : Nom du fichier dans `OUTPUT_PATH` (`.xlsx`)
- `max_rows_per_sheet` : Nombre max de lignes echantillon par feuille Excel (defaut: 10, max: 100)

### Securite

- Validation anti-traversal sur `filename` (pas de `..`, `/`, `\`)
- Le fichier doit exister dans `OUTPUT_PATH`

## Outils MCP specifiques

### index_document

Accepte tous les formats. Detecte le type par extension. Parametres specifiques :
- `sheets` : Excel uniquement, permet de limiter l'indexation a certaines feuilles
- `force_ocr` : PDF uniquement

### get_excel_formulas

Recupere les formules stockees dans les chunks d'un document Excel. Permet de filtrer par feuille et par plage de cellules.

### create_excel_document

Cree un fichier Excel dans OUTPUT_PATH. Voir la section "Generation et edition Excel" ci-dessus.

### edit_excel_document

Edite un fichier Excel existant dans OUTPUT_PATH. Voir la section "Generation et edition Excel" ci-dessus.

### inspect_generated_file

Inspecte la structure d'un fichier Excel genere. Voir la section "Inspection de fichiers generes" ci-dessus.

### list_available_documents

Liste les fichiers disponibles dans 2 sources differentes :

| Source | Chemin | Description | Types valides |
|--------|--------|-------------|---------------|
| `documents` (defaut) | `DOCUMENTS_PATH` | Documents indexables | pdf, excel, word, all |
| `generated` | `OUTPUT_PATH` | Fichiers generes par les tools | excel, all |

Parametres : `source`, `type_filter`, `subdirectory`, `recursive`.

## Limitations connues

### Excel (indexation)
- `.xls` : Pas d'extraction de formules (limitation de xlrd)
- Graphiques : Non extraits lors de l'indexation
- Macros VBA : Ignorees
- Fichiers proteges par mot de passe : Erreur a l'ouverture
- Fichiers sans "Tables officielles" Excel : Les donnees brutes sont extraites via `_cells_to_markdown()` (correctif ajoute)

### Excel (generation/edition)
- Taille maximum du fichier genere : `MAX_OUTPUT_FILE_SIZE_MB` (defaut: 10 Mo)
- Maximum 50 feuilles par fichier, 10 000 lignes par feuille
- Maximum 100 operations par appel a `edit_excel_document`
- Les graphiques utilisent openpyxl : certains types avances ne sont pas supportes
- Les erreurs de graphique sont gerees en degradation gracieuse (non bloquantes)

### Word
- `.doc` (Word 97-2003) : Non supporte, convertir en `.docx`
- Styles personnalises : La detection des headings se fait par regex sur le texte, pas par les styles Word
- Commentaires et revisions : Non extraits
- Mise en page complexe (colonnes, sections) : Non prise en compte

### Recherche
- La recherche semantique de noms propres dans des fichiers Excel donne de mauvais resultats avec le seuil par defaut (0.7). Utiliser `score_threshold: 0.3` et combiner avec le filtre `text_search` pour une recherche exacte.
