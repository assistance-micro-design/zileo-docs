# Guide de génération — Excel & Word

Référence pour les outils MCP de création / édition de fichiers (`OUTPUT_PATH`). Pour la liste complète des paramètres, voir [api-reference.md](api-reference.md).

## Excel — création (`create_excel_document`)

### Structure

```json
{
  "filename": "rapport.xlsx",
  "author": "Zileo",
  "sheets": [
    {
      "name": "Ventes",
      "headers": ["Région", "Q1", "Q2", "Total"],
      "rows": [
        ["Nord", 15000, 18000, "=SUM(B2:C2)"],
        ["Sud", 12000, 14000, "=SUM(B3:C3)"],
        ["Total", "=SUM(B2:B3)", "=SUM(C2:C3)", "=SUM(D2:D3)"]
      ],
      "column_widths": {"A": 15, "B": 12, "C": 12, "D": 14},
      "auto_filter": true,
      "freeze_panes": "A2",
      "tab_color": "4472C4"
    }
  ]
}
```

### Limites

| Élément | Limite |
|---------|--------|
| Feuilles par fichier | 50 |
| Lignes par feuille | 10 000 |
| Colonnes par ligne | 500 |
| Taille fichier | `MAX_OUTPUT_FILE_SIZE_MB` (défaut 10 Mo) |

### Valeurs de cellules

| Type | Exemple | Rendu |
|------|---------|-------|
| string | `"Texte"` | Texte brut |
| int / float | `42`, `3.14` | Nombre |
| bool | `true` | VRAI / FAUX |
| null | `null` | Cellule vide |
| formule | `"=SUM(A1:A10)"` | Formule Excel (commence par `=`) |

> **Sécurité** : `=DDE`, `=CMD`, `=SYSTEM`, `=EXEC`, `=CALL`, `=REGISTER`, `+cmd|`, `-cmd|`, `@...cmd|` sont bloqués. Les formules standard (`=SUM`, `=IF`, `=VLOOKUP`, etc.) sont autorisées.

### Styles (`CellStyleDef`)

```json
{
  "range": "A1:E1",
  "bold": true,
  "font_size": 14,
  "font_color": "FFFFFF",
  "bg_color": "4472C4",
  "number_format": "#,##0.00",
  "alignment": "center",
  "wrap_text": true,
  "border": true
}
```

Couleurs en hex 6 chars **sans** `#`.

#### Formats de nombre courants

`#,##0` entier, `#,##0.00` décimal, `0%` / `0.00%` pourcentage, `dd/mm/yyyy` / `yyyy-mm-dd` date, `h:mm` heure, `#,##0.00 "EUR"` devise, `@` force texte.

### Graphiques (`ChartDef`)

```json
{
  "type": "column",
  "title": "Ventes Q1",
  "data_range": "B1:D5",
  "categories_range": "A2:A5",
  "position": "G2",
  "y_axis_title": "Montant (EUR)",
  "style": 10
}
```

| Type | Usage |
|------|-------|
| `bar` | Barres horizontales — comparer catégories |
| `column` | Barres verticales — tendances par période |
| `line` | Évolution temporelle |
| `pie` | Répartition en pourcentage |
| `scatter` | Corrélation 2 variables |
| `area` | Évolution avec volume |

`style` : 1-48. Recommandés : `10` (général), `11` (rapports pro), `26` (dashboards). `width` (5-40 cm) et `height` (5-30 cm) optionnels.

### Validations de données (`DataValidationDef`)

```json
{"range": "B2:B100", "type": "list", "values": ["Oui", "Non"]}
{"range": "C2:C100", "type": "whole", "operator": "between", "formula1": "1", "formula2": "100"}
{"range": "D2:D100", "type": "decimal", "operator": "greaterThan", "formula1": "0"}
{"range": "E2:E100", "type": "date", "operator": "greaterThan", "formula1": "=TODAY()"}
{"range": "A2:A100", "type": "textLength", "operator": "lessThanOrEqual", "formula1": "50"}
```

Types : `list` (shortcut `values`), `whole`, `decimal`, `date`, `textLength`, `custom`. Opérateurs : `between`, `notBetween`, `equal`, `notEqual`, `greaterThan`, `greaterThanOrEqual`, `lessThan`, `lessThanOrEqual`.

### Cellules fusionnées et freeze

```json
{"range": "A1:D1", "value": "Rapport trimestriel"}
```

`freeze_panes` : `"A2"` fige la ligne 1, `"B1"` fige la colonne A, `"B2"` fige les deux.

## Excel — édition (`edit_excel_document`)

13 opérations appliquées en séquence. Chaque opération porte un champ `op`.

| Op | Description | Champs principaux |
|----|-------------|-------------------|
| `update_cells` | Modifier des cellules | `sheet`, `cells: {"A1": 42}` |
| `insert_rows` | Insérer des lignes | `sheet`, `at_row`, `rows` (omit `at_row` = append) |
| `delete_rows` | Supprimer des lignes | `sheet`, `start_row`, `end_row` |
| `apply_styles` | Appliquer des styles | `sheet`, `styles[]` |
| `add_sheet` | Ajouter une feuille | `name`, `headers`, `rows` |
| `delete_sheet` | Supprimer une feuille | `sheet` |
| `rename_sheet` | Renommer | `sheet`, `new_name` |
| `add_chart` | Ajouter un graphique | `sheet`, `chart` (ChartDef) |
| `remove_charts` | Supprimer **tous** les graphiques d'une feuille | `sheet` |
| `add_data_validation` | Ajouter une validation | `sheet`, `validation` |
| `merge_cells` | Fusionner | `sheet`, `merge: {range, value?}` |
| `unmerge_cells` | Défusionner | `sheet`, `range` |
| `set_sheet_properties` | Modifier propriétés (seuls les champs fournis) | `sheet`, `column_widths`, `auto_filter`, `freeze_panes`, `tab_color` |

Exemple :

```json
{"filename": "rapport.xlsx", "operations": [
  {"op": "update_cells", "sheet": "Ventes", "cells": {"B2": 16000}},
  {"op": "add_chart", "sheet": "Ventes", "chart": {"type": "pie", "data_range": "D2:D5", "categories_range": "A2:A5"}},
  {"op": "delete_rows", "sheet": "Ventes", "start_row": 10, "end_row": 12}
]}
```

Limites : 1 à 100 opérations par appel. Erreurs de graphique : non bloquantes (`skipped`).

## Word — création (`create_word_document`)

Convertit du **Markdown** en `.docx`.

```json
{
  "filename": "rapport.docx",
  "title": "Rapport mensuel",
  "author": "Zileo",
  "content": "# Titre\n\n## Section\n\nTexte **gras** et *italique*.\n\n- item 1\n- item 2\n  - sous-item\n\n| Col A | Col B |\n|-------|-------|\n| 1 | 2 |\n\n```\nbloc code\n```\n\n> citation\n\n---\n\nNouvelle page."
}
```

### Markdown supporté

| Markdown | Word |
|----------|------|
| `# H1` à `###### H6` | Heading 1-6 |
| `**bold**`, `*italic*` | Formatage inline |
| `- item` / `1. item` (imbriquables) | Liste à puces / numérotée |
| Table Markdown | Table Word |
| ` ```code``` ` | Bloc de code (monospace) |
| `> citation` | Citation |
| `---` | Saut de page |

### Limites Word

`content` 500 000 caractères max, taille fichier `MAX_OUTPUT_FILE_SIZE_MB` (défaut 10 Mo), filename `[\w\-. ()]+\.docx` (pas de `..`, `/`, `\`).

## Inspection (`inspect_generated_file`)

Inspecte un fichier Excel généré et retourne sa structure dans le **vocabulaire des opérations d'édition**, ce qui permet d'enchaîner directement vers `edit_excel_document`.

```json
{"filename": "rapport.xlsx", "max_rows_per_sheet": 5}
```

Retour : feuilles, headers, échantillon de données, formules, graphiques, validations, propriétés.

## Workflows recommandés

| Cas | Enchaînement |
|-----|--------------|
| Création simple | `create_excel_document` → `inspect_generated_file` → `edit_excel_document` |
| Création itérative | Boucler `inspect_generated_file` ↔ `edit_excel_document` |
| Édition d'un fichier inconnu | `list_available_documents(source="generated")` → `inspect_generated_file` → `edit_excel_document` |

## Palette de couleurs (Office)

`4472C4` bleu, `1F4E79` bleu foncé, `D6E4F0` bleu clair, `ED7D31` orange, `70AD47` vert, `FF0000` rouge, `404040` gris foncé, `808080` gris moyen, `D9D9D9` gris clair, `FFC000` jaune. Toujours en hex 6 chars sans `#`.
