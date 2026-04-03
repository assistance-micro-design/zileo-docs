# Guide de generation et edition — Excel

Guide complet pour utiliser les outils MCP de creation et edition de fichiers Excel (.xlsx). Destine au LLM qui appelle les tools, avec toutes les options, particularites et exemples.

---

## Table des matieres

- [Excel — Creation](#excel--creation)
- [Excel — Edition](#excel--edition)
- [Inspection de fichiers](#inspection-de-fichiers)
- [Workflow recommande](#workflow-recommande)
- [Reference des couleurs et formats](#reference-des-couleurs-et-formats)
- [Limites et securite](#limites-et-securite)

---

## Excel — Creation

### Tool : `create_excel_document`

Cree un fichier `.xlsx` dans `OUTPUT_PATH`.

### Parametres

```json
{
  "filename": "rapport.xlsx",
  "author": "Zileo",
  "sheets": [ ... ]
}
```

| Parametre | Type | Requis | Limites |
|-----------|------|--------|---------|
| `filename` | string | Oui | Doit finir par `.xlsx` |
| `author` | string | Non | Max 255 caracteres |
| `sheets` | array[SheetDef] | Oui | 1 a 50 feuilles |

### Definition d'une feuille (SheetDef)

```json
{
  "name": "Ventes",
  "headers": ["Produit", "Q1", "Q2", "Q3", "Q4"],
  "rows": [
    ["Widget A", 100, 150, 200, 180],
    ["Widget B", 80, 90, 110, 120],
    ["Total", "=SUM(B2:B3)", "=SUM(C2:C3)", "=SUM(D2:D3)", "=SUM(E2:E3)"]
  ],
  "column_widths": {"A": 20, "B": 12, "C": 12, "D": 12, "E": 12},
  "styles": [ ... ],
  "charts": [ ... ],
  "data_validations": [ ... ],
  "merged_cells": [ ... ],
  "auto_filter": true,
  "freeze_panes": "A2",
  "tab_color": "4472C4"
}
```

| Champ | Type | Defaut | Description |
|-------|------|--------|-------------|
| `name` | string | — | Nom de la feuille (1-31 caracteres) |
| `headers` | list[string] | None | En-tetes (max 500 colonnes). Mis en gras automatiquement |
| `rows` | list[list] | [] | Donnees (max 10 000 lignes, 500 colonnes par ligne) |
| `column_widths` | dict | None | Largeur des colonnes. Ex: `{"A": 20, "B": 15}` |
| `styles` | list[CellStyleDef] | [] | Styles a appliquer |
| `charts` | list[ChartDef] | [] | Graphiques a inserer |
| `data_validations` | list[DataValidationDef] | [] | Regles de validation |
| `merged_cells` | list[MergedCellDef] | [] | Cellules fusionnees |
| `auto_filter` | bool | false | Active le filtre automatique sur les en-tetes |
| `freeze_panes` | string | None | Fige les volets. Ex: `"A2"` fige la premiere ligne |
| `tab_color` | string | None | Couleur de l'onglet (hex 6 caracteres sans `#`) |

### Valeurs de cellules

Les cellules acceptent les types suivants :

| Type | Exemple | Rendu Excel |
|------|---------|-------------|
| string | `"Texte"` | Texte brut |
| int | `42` | Nombre entier |
| float | `3.14` | Nombre decimal |
| bool | `true` | VRAI/FAUX |
| null | `null` | Cellule vide |
| formule | `"=SUM(A1:A10)"` | Formule Excel (commence par `=`) |

Les formules Excel standard sont supportees : `=SUM()`, `=AVERAGE()`, `=IF()`, `=VLOOKUP()`, `=COUNT()`, etc.

> **Securite** : Les formules dangereuses (DDE, CMD, SYSTEM, EXEC, CALL) sont bloquees automatiquement.

---

### Styles (CellStyleDef)

Applique un style visuel a une plage de cellules.

```json
{
  "range": "A1:E1",
  "bold": true,
  "italic": false,
  "font_size": 14,
  "font_color": "FFFFFF",
  "bg_color": "4472C4",
  "number_format": "#,##0.00",
  "alignment": "center",
  "wrap_text": true,
  "border": true
}
```

| Option | Type | Valeurs possibles |
|--------|------|-------------------|
| `range` | string | `"A1"`, `"A1:D1"`, `"B2:B100"` |
| `bold` | bool | `true` / `false` |
| `italic` | bool | `true` / `false` |
| `font_size` | int | Taille en points (ex: 10, 12, 14, 18, 24) |
| `font_color` | string | Hex 6 chars sans `#` (ex: `"FF0000"` = rouge) |
| `bg_color` | string | Hex 6 chars sans `#` (ex: `"4472C4"` = bleu) |
| `number_format` | string | Format Excel (voir table ci-dessous) |
| `alignment` | string | `"left"`, `"center"`, `"right"` |
| `wrap_text` | bool | Retour a la ligne automatique |
| `border` | bool | Bordure fine sur les 4 cotes |

#### Formats de nombre courants

| Format | Rendu | Usage |
|--------|-------|-------|
| `General` | Automatique | Defaut |
| `0` | `1234` | Entier sans separateur |
| `#,##0` | `1 234` | Entier avec separateur milliers |
| `#,##0.00` | `1 234,56` | Decimal 2 chiffres |
| `0%` | `75%` | Pourcentage entier |
| `0.00%` | `75,50%` | Pourcentage decimal |
| `0.00E+00` | `1,23E+03` | Notation scientifique |
| `mm-dd-yy` | `03-05-26` | Date US |
| `dd/mm/yyyy` | `05/03/2026` | Date FR |
| `yyyy-mm-dd` | `2026-03-05` | Date ISO |
| `h:mm` | `14:30` | Heure 24h |
| `h:mm:ss` | `14:30:45` | Heure avec secondes |
| `#,##0.00 "EUR"` | `1 234,56 EUR` | Devise personnalisee |
| `@` | Texte brut | Force le type texte |

---

### Graphiques (ChartDef)

Insere un graphique dans la feuille.

```json
{
  "type": "column",
  "title": "Ventes trimestrielles",
  "data_range": "B1:E3",
  "categories_range": "A2:A3",
  "position": "G2",
  "x_axis_title": "Trimestre",
  "y_axis_title": "Montant (EUR)",
  "style": 10,
  "width": 18,
  "height": 12
}
```

#### Types de graphiques Excel

| Type | Description | Usage typique |
|------|-------------|---------------|
| `bar` | Barres horizontales | Comparaison de categories |
| `column` | Barres verticales | Tendances par periode |
| `line` | Courbe | Evolution temporelle |
| `pie` | Camembert | Repartition en pourcentage |
| `scatter` | Nuage de points | Correlation entre 2 variables |
| `area` | Aire remplie | Evolution avec volume |

#### Options

| Option | Type | Defaut | Description |
|--------|------|--------|-------------|
| `type` | string | — | Type de graphique (voir table) |
| `title` | string | None | Titre affiche au-dessus |
| `data_range` | string | — | Plage des donnees. Ex: `"B1:E5"` |
| `categories_range` | string | None | Labels axe X. Ex: `"A2:A5"` |
| `position` | string | `"H2"` | Cellule d'ancrage (coin superieur gauche) |
| `x_axis_title` | string | None | Titre de l'axe X |
| `y_axis_title` | string | None | Titre de l'axe Y |
| `style` | int | None | Style visuel Excel (1-48) |
| `width` | float | 15.0 | Largeur en cm (5-40) |
| `height` | float | 10.0 | Hauteur en cm (5-30) |

#### Styles de graphique recommandes

| Style | Rendu | Recommandation |
|-------|-------|----------------|
| 2 | Colore, fond blanc | Presentations colorees |
| 10 | Epure, minimal | **Usage general recommande** |
| 11 | Fond clair, grilles subtiles | Rapports professionnels |
| 26 | Moderne avec accents | Dashboards |
| 34-40 | Fonds sombres | Themes dark |

> **Conseil** : `data_range` inclut generalement les en-tetes en premiere ligne pour que les series soient automatiquement nommees.

---

### Validations de donnees (DataValidationDef)

Ajoute des regles de validation sur une plage de cellules.

```json
{
  "range": "C2:C100",
  "type": "list",
  "values": ["En cours", "Termine", "Annule"],
  "error_message": "Choisir un statut valide",
  "prompt_message": "Selectionner le statut"
}
```

#### Types de validation

| Type | Description | Parametres utilises |
|------|-------------|---------------------|
| `list` | Liste deroulante | `values` (shortcut) ou `formula1` |
| `whole` | Nombre entier | `operator`, `formula1`, `formula2` |
| `decimal` | Nombre decimal | `operator`, `formula1`, `formula2` |
| `date` | Date | `operator`, `formula1`, `formula2` |
| `textLength` | Longueur de texte | `operator`, `formula1`, `formula2` |
| `custom` | Formule personnalisee | `formula1` |

#### Operateurs (pour whole, decimal, date, textLength)

| Operateur | Signification | Formules requises |
|-----------|---------------|-------------------|
| `between` | Entre formula1 et formula2 | formula1 + formula2 |
| `notBetween` | Pas entre | formula1 + formula2 |
| `equal` | Egal a | formula1 |
| `notEqual` | Different de | formula1 |
| `greaterThan` | Superieur a | formula1 |
| `greaterThanOrEqual` | Superieur ou egal | formula1 |
| `lessThan` | Inferieur a | formula1 |
| `lessThanOrEqual` | Inferieur ou egal | formula1 |

#### Exemples courants

```json
// Liste deroulante
{"range": "B2:B100", "type": "list", "values": ["Oui", "Non"]}

// Entier entre 1 et 100
{"range": "C2:C100", "type": "whole", "operator": "between", "formula1": "1", "formula2": "100"}

// Decimal > 0
{"range": "D2:D100", "type": "decimal", "operator": "greaterThan", "formula1": "0"}

// Date apres aujourd'hui
{"range": "E2:E100", "type": "date", "operator": "greaterThan", "formula1": "=TODAY()"}

// Texte max 50 caracteres
{"range": "A2:A100", "type": "textLength", "operator": "lessThanOrEqual", "formula1": "50"}
```

---

### Cellules fusionnees (MergedCellDef)

```json
{"range": "A1:D1", "value": "Rapport trimestriel"}
```

La valeur est optionnelle. Si fournie, elle est ecrite dans la cellule superieure gauche de la fusion.

---

### Freeze panes (volets figes)

| Valeur | Effet |
|--------|-------|
| `"A2"` | Fige la ligne 1 (en-tetes) |
| `"B1"` | Fige la colonne A |
| `"B2"` | Fige la ligne 1 ET la colonne A |
| `"C3"` | Fige les lignes 1-2 ET les colonnes A-B |

---

### Exemple complet de creation Excel

```json
{
  "filename": "rapport-ventes-q1.xlsx",
  "author": "Zileo Analytics",
  "sheets": [
    {
      "name": "Ventes Q1",
      "headers": ["Region", "Janvier", "Fevrier", "Mars", "Total"],
      "rows": [
        ["Nord", 15000, 18000, 22000, "=SUM(B2:D2)"],
        ["Sud", 12000, 14000, 16000, "=SUM(B3:D3)"],
        ["Est", 9000, 11000, 13000, "=SUM(B4:D4)"],
        ["Ouest", 20000, 23000, 25000, "=SUM(B5:D5)"],
        ["Total", "=SUM(B2:B5)", "=SUM(C2:C5)", "=SUM(D2:D5)", "=SUM(E2:E5)"]
      ],
      "column_widths": {"A": 15, "B": 12, "C": 12, "D": 12, "E": 14},
      "styles": [
        {
          "range": "A1:E1",
          "bold": true,
          "font_color": "FFFFFF",
          "bg_color": "2F5496",
          "alignment": "center"
        },
        {
          "range": "A6:E6",
          "bold": true,
          "bg_color": "D6E4F0",
          "border": true
        },
        {
          "range": "B2:E6",
          "number_format": "#,##0",
          "alignment": "right"
        }
      ],
      "charts": [
        {
          "type": "column",
          "title": "Ventes par region — Q1 2026",
          "data_range": "B1:D5",
          "categories_range": "A2:A5",
          "position": "G2",
          "style": 10,
          "y_axis_title": "Montant (EUR)"
        }
      ],
      "auto_filter": true,
      "freeze_panes": "A2",
      "tab_color": "2F5496"
    },
    {
      "name": "Parametres",
      "headers": ["Parametre", "Valeur"],
      "rows": [
        ["Devise", "EUR"],
        ["Periode", "Q1 2026"],
        ["Genere par", "Zileo Analytics"]
      ],
      "tab_color": "70AD47"
    }
  ]
}
```

---

## Excel — Edition

### Tool : `edit_excel_document`

Edite un fichier `.xlsx` existant dans `OUTPUT_PATH`.

### Parametres

```json
{
  "filename": "rapport-ventes-q1.xlsx",
  "operations": [ ... ]
}
```

| Parametre | Type | Limites |
|-----------|------|---------|
| `filename` | string | Fichier existant dans OUTPUT_PATH |
| `operations` | array[EditOp] | 1 a 100 operations |

Les operations sont appliquees en sequence. Chaque operation a un champ `op` qui determine son type.

### Les 13 operations

#### 1. `update_cells` — Modifier des cellules

```json
{
  "op": "update_cells",
  "sheet": "Ventes Q1",
  "cells": {
    "B2": 16000,
    "C2": 19500,
    "F1": "Commentaire",
    "F2": "Hausse de 7%"
  }
}
```

#### 2. `insert_rows` — Inserer des lignes

```json
{
  "op": "insert_rows",
  "sheet": "Ventes Q1",
  "at_row": 5,
  "rows": [
    ["Centre", 11000, 13000, 15000, "=SUM(B5:D5)"]
  ]
}
```

- `at_row` : insere avant cette ligne (1-indexed). Omis = ajoute a la fin.

#### 3. `delete_rows` — Supprimer des lignes

```json
{
  "op": "delete_rows",
  "sheet": "Ventes Q1",
  "start_row": 4,
  "end_row": 4
}
```

- `end_row` doit etre >= `start_row`.

#### 4. `apply_styles` — Appliquer des styles

```json
{
  "op": "apply_styles",
  "sheet": "Ventes Q1",
  "styles": [
    {"range": "F1:F6", "italic": true, "font_color": "808080"}
  ]
}
```

Memes options que `CellStyleDef` (voir section Styles ci-dessus).

#### 5. `add_sheet` — Ajouter une feuille

```json
{
  "op": "add_sheet",
  "name": "Synthese",
  "headers": ["Indicateur", "Valeur"],
  "rows": [
    ["CA total", "='Ventes Q1'!E6"],
    ["Marge", "15%"]
  ]
}
```

#### 6. `delete_sheet` — Supprimer une feuille

```json
{"op": "delete_sheet", "name": "Parametres"}
```

#### 7. `rename_sheet` — Renommer une feuille

```json
{"op": "rename_sheet", "name": "Ventes Q1", "new_name": "Ventes Janvier-Mars"}
```

#### 8. `add_chart` — Ajouter un graphique

```json
{
  "op": "add_chart",
  "sheet": "Ventes Q1",
  "chart": {
    "type": "pie",
    "title": "Repartition par region",
    "data_range": "E2:E5",
    "categories_range": "A2:A5",
    "position": "G12"
  }
}
```

#### 9. `remove_charts` — Supprimer tous les graphiques

```json
{"op": "remove_charts", "sheet": "Ventes Q1"}
```

> Supprime **tous** les graphiques de la feuille. Pas de suppression individuelle.

#### 10. `add_data_validation` — Ajouter une validation

```json
{
  "op": "add_data_validation",
  "sheet": "Ventes Q1",
  "validation": {
    "range": "A7:A100",
    "type": "list",
    "values": ["Nord", "Sud", "Est", "Ouest", "Centre"]
  }
}
```

#### 11. `merge_cells` — Fusionner des cellules

```json
{
  "op": "merge_cells",
  "sheet": "Synthese",
  "merge": {"range": "A1:B1", "value": "Synthese des ventes"}
}
```

#### 12. `unmerge_cells` — Defusionner des cellules

```json
{"op": "unmerge_cells", "sheet": "Synthese", "range": "A1:B1"}
```

#### 13. `set_sheet_properties` — Modifier les proprietes

```json
{
  "op": "set_sheet_properties",
  "sheet": "Ventes Q1",
  "column_widths": {"F": 20},
  "auto_filter": true,
  "freeze_panes": "B2",
  "tab_color": "FF6600"
}
```

Seuls les champs fournis sont modifies. Les autres restent inchanges.

---

---

## Inspection de fichiers

### Tool : `inspect_generated_file`

Inspecte la structure d'un fichier Excel pour preparer une edition.

```json
{
  "filename": "rapport-ventes-q1.xlsx",
  "max_rows_per_sheet": 5
}
```

| Parametre | Type | Defaut | Description |
|-----------|------|--------|-------------|
| `filename` | string | — | Fichier dans OUTPUT_PATH (.xlsx) |
| `max_rows_per_sheet` | int | 10 | Lignes echantillon par feuille (1-100) |

### Retour pour Excel

- Liste des feuilles avec colonnes, donnees echantillon, graphiques, validations, proprietes

> Utilisez `inspect_generated_file` avant `edit_excel_document` pour connaitre la structure actuelle du fichier.

---

## Workflow recommande

### Creation simple

```
1. create_excel_document
2. inspect_generated_file  (verifier le resultat)
3. edit_excel_document  (ajuster si necessaire)
```

### Creation iterative

```
1. create_excel_document  (structure initiale)
2. inspect_generated_file
3. edit_excel_document  (corrections)
4. inspect_generated_file  (re-verifier)
5. edit_excel_document  (finitions)
```

### Consultation avant edition

```
1. list_available_documents(source="generated")  (trouver le fichier)
2. inspect_generated_file  (voir la structure)
3. edit_excel_document  (editer en connaissance de cause)
```

---

## Reference des couleurs et formats

### Couleurs courantes

Toutes les couleurs sont en hexadecimal 6 caracteres **sans** le `#`.

| Couleur | Hex | Usage typique |
|---------|-----|---------------|
| Noir | `000000` | Texte standard |
| Blanc | `FFFFFF` | Texte sur fond sombre |
| Rouge | `FF0000` | Alertes, negatif |
| Vert | `00B050` | Positif, succes |
| Bleu fonce | `1F4E79` | Titres corporate |
| Bleu Office | `4472C4` | Accent principal |
| Bleu clair | `D6E4F0` | Fond de ligne alternee |
| Orange | `ED7D31` | Accent secondaire |
| Gris fonce | `404040` | Sous-titres |
| Gris moyen | `808080` | Texte secondaire |
| Gris clair | `D9D9D9` | Bordures, fonds discrets |
| Vert Office | `70AD47` | Indicateur positif |
| Violet | `7030A0` | Accent tertiaire |
| Jaune | `FFC000` | Mise en evidence |

### Palette Excel "Office"

| Couleur | Hex |
|---------|-----|
| Bleu | `4472C4` |
| Orange | `ED7D31` |
| Gris | `A5A5A5` |
| Jaune | `FFC000` |
| Bleu fonce | `5B9BD5` |
| Vert | `70AD47` |

---

## Limites et securite

### Limites de taille

| Limite | Valeur |
|--------|--------|
| Taille max fichier genere | `MAX_OUTPUT_FILE_SIZE_MB` (defaut: 10 Mo) |
| Feuilles par fichier Excel | 50 |
| Lignes par feuille | 10 000 |
| Colonnes par ligne | 500 |
| Operations par edition | 100 |

### Securite

| Protection | Description |
|------------|-------------|
| Formula injection | Les formules DDE, CMD, SYSTEM, EXEC, CALL sont bloquees |
| Path traversal | `..`, `/`, `\` sont interdits dans les noms de fichiers |
| Author constraint | Max 255 caracteres |
| File size check | Le fichier genere est verifie apres ecriture |

### Comportement en cas d'erreur

| Type | Comportement |
|------|-------------|
| Fichier non trouve | Erreur bloquante avec suggestion |
| Feuille inexistante | Erreur bloquante avec liste des feuilles |
| Graphique invalide | **Non bloquant** — compte comme `skipped`, les autres operations continuent |
| Formule dangereuse | Erreur bloquante |
| Taille depassee | Erreur bloquante apres generation |
