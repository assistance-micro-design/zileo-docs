# Guide de generation et edition — Excel et PowerPoint

Guide complet pour utiliser les outils MCP de creation et edition de fichiers Excel (.xlsx) et PowerPoint (.pptx). Destine au LLM qui appelle les tools, avec toutes les options, particularites et exemples.

---

## Table des matieres

- [Excel — Creation](#excel--creation)
- [Excel — Edition](#excel--edition)
- [PowerPoint — Creation](#powerpoint--creation)
- [PowerPoint — Edition](#powerpoint--edition)
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

## PowerPoint — Creation

### Tool : `create_presentation`

Cree un fichier `.pptx` dans `OUTPUT_PATH`.

### Parametres

```json
{
  "filename": "presentation.pptx",
  "author": "Zileo",
  "template": "template-corporate.pptx",
  "slides": [ ... ]
}
```

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `filename` | string | Oui | Doit finir par `.pptx` |
| `author` | string | Non | Max 255 caracteres |
| `template` | string | Non | Fichier `.pptx` dans `TEMPLATES_PPTX_PATH` |
| `slides` | array[SlideDef] | Oui | 1 a 100 slides |
| `template_slide_map` | array[int] | Non | Clone les slides du template par index (meme longueur que `slides`) |

> **Template simple** : Si `template` est fourni sans `template_slide_map`, les layouts natifs du template sont utilises (titres, placeholders). Utile pour les templates Office standard.
>
> **Template riche (clone)** : Si `template_slide_map` est fourni, chaque slide clone un slide existant du template, preservant tout le design (fonds, images, formes, polices). Utiliser `inspect_template` pour voir les slides disponibles et choisir les bons index.

### Workflow avec template riche

1. **Lister les templates** : `list_available_documents(source="templates")`
2. **Inspecter le template** : `inspect_template(template="mon-template.pptx")` — retourne les slides avec leurs text shapes (texte, font, taille, couleur, position), images, decorations, groupes et notes
3. **Choisir les slides de reference** : identifier quel slide du template cloner pour chaque nouveau slide
4. **Creer la presentation** : utiliser `template_slide_map` pour mapper chaque slide a un slide du template
5. **Adapter le texte** : respecter le nombre de mots et la structure du slide de reference (title = plus grand shape, body = shapes suivants par taille decroissante)

```json
{
  "filename": "rapport.pptx",
  "template": "StocksTradingBusinessPlan.pptx",
  "template_slide_map": [0, 5, 3, 14],
  "slides": [
    {"layout": "title_slide", "title": "MON TITRE", "subtitle": "Sous-titre"},
    {"layout": "content_bullets", "title": "POINTS CLES", "bullets": [...]},
    {"layout": "section_header", "title": "SECTION 1", "subtitle": "Description"},
    {"layout": "closing", "title": "MERCI", "subtitle": "contact@email.com"}
  ]
}
```

> **Important** : lors du clonage, le texte est remplace dans les shapes par ordre de taille (area). Le plus grand shape recoit le titre, les suivants recoivent les body texts dans l'ordre. Les shapes excessifs sont vides. Adapter le nombre et la longueur des textes au slide de reference.

### Les 8 layouts de slides

Chaque slide a un `layout` qui determine sa structure. Tous les layouts supportent `notes` (notes du presentateur, max 5000 caracteres).

---

#### 1. `title_slide` — Slide de titre

La slide d'ouverture de la presentation.

```json
{
  "layout": "title_slide",
  "title": "Rapport Annuel 2026",
  "subtitle": "Zileo — Division Analytics",
  "title_style": {"bold": true, "font_size": 40, "font_color": "2F5496"},
  "notes": "Introduction du rapport. Duree: 2 min."
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `title` | string | Oui | 1-200 caracteres |
| `subtitle` | string | Non | Texte sous le titre |
| `title_style` | TextStyle | Non | Style du titre |
| `notes` | string | Non | Notes du presentateur |

---

#### 2. `content_bullets` — Contenu avec puces

Le layout le plus courant pour presenter du contenu.

```json
{
  "layout": "content_bullets",
  "title": "Points cles",
  "bullets": [
    {"text": "Croissance de 25% du CA", "level": 0, "bold": true},
    {"text": "Tirée par le segment Enterprise", "level": 1},
    {"text": "Expansion sur 3 nouveaux marches", "level": 0, "bold": true},
    {"text": "Allemagne, Italie, Espagne", "level": 1},
    {"text": "Marge operationnelle a 18%", "level": 0}
  ]
}
```

**BulletItem** :

| Champ | Type | Defaut | Description |
|-------|------|--------|-------------|
| `text` | string | — | Texte de la puce (1-500 chars) |
| `level` | int | 0 | Niveau d'indentation (0-3) |
| `bold` | bool | false | Texte en gras |

- Level 0 : puce principale (taille 18pt)
- Level 1 : sous-puce (taille 16pt)
- Level 2 : sous-sous-puce (taille 14pt)
- Level 3 : detail (taille 12pt)

Max 20 puces par slide.

---

#### 3. `content_with_image` — Contenu + image

Puces a gauche, image a droite.

```json
{
  "layout": "content_with_image",
  "title": "Notre equipe",
  "bullets": [
    {"text": "120 collaborateurs"},
    {"text": "4 bureaux en Europe"},
    {"text": "15 nationalites"}
  ],
  "image": {
    "filename": "equipe-photo.jpg",
    "width_cm": 12,
    "height_cm": 9
  }
}
```

**ImageDef** :

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `filename` | string | Oui | Nom du fichier dans `IMAGES_POWERPOINT_PATH` |
| `width_cm` | float | Non | Largeur en cm (1-33.87). Si omis, proportionnel |
| `height_cm` | float | Non | Hauteur en cm (1-19.05). Si omis, proportionnel |

Formats d'image supportes : **PNG**, **JPG/JPEG**, **GIF**, **BMP**, **SVG**.

Max 10 puces pour ce layout (espace reduit par l'image).

---

#### 4. `section_header` — Separateur de section

```json
{
  "layout": "section_header",
  "title": "Partie 2 : Resultats financiers",
  "subtitle": "Exercice 2025-2026"
}
```

Texte centre. Utilisez pour structurer la presentation en parties.

---

#### 5. `two_columns` — Deux colonnes

```json
{
  "layout": "two_columns",
  "title": "Comparaison",
  "left_bullets": [
    {"text": "Avant", "bold": true},
    {"text": "Process manuels"},
    {"text": "Delai 2 semaines"},
    {"text": "Taux erreur 5%"}
  ],
  "right_bullets": [
    {"text": "Apres", "bold": true},
    {"text": "Automatisation complete"},
    {"text": "Delai 2 jours"},
    {"text": "Taux erreur 0.1%"}
  ]
}
```

Max 10 puces par colonne.

---

#### 6. `image_full` — Image plein ecran

```json
{
  "layout": "image_full",
  "image": {"filename": "dashboard-screenshot.png"},
  "title": "Dashboard en temps reel",
  "caption": "Capture du 5 mars 2026"
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `image` | ImageDef | Oui | L'image occupe toute la slide (20cm) |
| `title` | string | Non | Titre optionnel en haut |
| `caption` | string | Non | Legende en bas (italique, gris) |

---

#### 7. `chart_slide` — Graphique

```json
{
  "layout": "chart_slide",
  "title": "Evolution du CA",
  "chart": {
    "chart_type": "line",
    "title": "CA mensuel 2026",
    "categories": ["Jan", "Fev", "Mar", "Avr", "Mai", "Jun"],
    "series": [
      {
        "name": "Reel",
        "values": [120, 135, 150, 148, 162, 175]
      },
      {
        "name": "Budget",
        "values": [110, 120, 130, 140, 150, 160]
      }
    ]
  }
}
```

**PresentationChartDef** :

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `chart_type` | string | Oui | Type de graphique (voir table) |
| `title` | string | Non | Titre affiche sur le graphique |
| `categories` | list[string] | Oui | Labels axe X (1-50) |
| `series` | list[ChartSeriesDef] | Oui | Series de donnees (1-10) |

**ChartSeriesDef** : `name` (string) + `values` (list[int|float], 1-50 valeurs).

#### Types de graphiques PowerPoint

| Type | Description | Usage typique |
|------|-------------|---------------|
| `bar` | Barres horizontales | Comparaison de categories |
| `column` | Barres verticales | Tendances par periode |
| `line` | Courbe | Evolution temporelle |
| `pie` | Camembert | Repartition (1 seule serie) |
| `area` | Aire | Evolution avec volume |
| `scatter` | Nuage de points | Correlation |
| `doughnut` | Donut | Repartition avec centre vide |

> **Difference avec Excel** : Les graphiques PowerPoint sont integres directement avec les donnees (pas de reference a une plage de cellules). Le type `doughnut` est disponible en PowerPoint mais pas en Excel.

---

#### 8. `closing` — Slide de cloture

```json
{
  "layout": "closing",
  "title": "Merci",
  "subtitle": "Questions ?",
  "bullets": [
    {"text": "contact@zileo.fr"},
    {"text": "www.zileo.fr"}
  ]
}
```

Titre centre en grand. Subtitle et bullets optionnels.

---

### Style de texte (TextStyle)

Applicable sur les titres de toutes les slides.

```json
{
  "bold": true,
  "italic": false,
  "font_size": 36,
  "font_color": "2F5496"
}
```

| Champ | Type | Defaut | Limites |
|-------|------|--------|---------|
| `bold` | bool | false | — |
| `italic` | bool | false | — |
| `font_size` | int | None | 8-96 pt |
| `font_color` | string | None | Hex 6 chars sans `#` |

---

### Exemple complet de creation PowerPoint

```json
{
  "filename": "revue-trimestrielle-q1.pptx",
  "author": "Zileo Analytics",
  "slides": [
    {
      "layout": "title_slide",
      "title": "Revue Trimestrielle Q1 2026",
      "subtitle": "Zileo — Direction Commerciale",
      "title_style": {"bold": true, "font_size": 40, "font_color": "1F4E79"}
    },
    {
      "layout": "section_header",
      "title": "1. Faits marquants"
    },
    {
      "layout": "content_bullets",
      "title": "Resultats cles",
      "bullets": [
        {"text": "CA : 2.4M EUR (+25%)", "level": 0, "bold": true},
        {"text": "Objectif depasse de 15%", "level": 1},
        {"text": "Nouveaux clients : 47", "level": 0, "bold": true},
        {"text": "Dont 12 grands comptes", "level": 1},
        {"text": "NPS : 72 (+8 pts)", "level": 0}
      ],
      "notes": "Insister sur la surperformance vs budget. Mentionner le deal Acme Corp."
    },
    {
      "layout": "chart_slide",
      "title": "Evolution du CA",
      "chart": {
        "chart_type": "column",
        "title": "CA mensuel (k EUR)",
        "categories": ["Janvier", "Fevrier", "Mars"],
        "series": [
          {"name": "2025", "values": [650, 720, 780]},
          {"name": "2026", "values": [780, 810, 850]}
        ]
      }
    },
    {
      "layout": "two_columns",
      "title": "Points forts / Points d'attention",
      "left_bullets": [
        {"text": "Points forts", "bold": true},
        {"text": "Pipeline record"},
        {"text": "Equipe stabilisee"},
        {"text": "Produit bien recu"}
      ],
      "right_bullets": [
        {"text": "Attention", "bold": true},
        {"text": "Delais de livraison"},
        {"text": "Turnover support"},
        {"text": "Marche allemand lent"}
      ]
    },
    {
      "layout": "content_with_image",
      "title": "Nouveau dashboard client",
      "bullets": [
        {"text": "Temps reel"},
        {"text": "Self-service"},
        {"text": "Deploye chez 80% des clients"}
      ],
      "image": {"filename": "dashboard.png", "width_cm": 14}
    },
    {
      "layout": "closing",
      "title": "Merci",
      "subtitle": "Questions et discussion",
      "bullets": [
        {"text": "Prochaine revue : Juillet 2026"}
      ]
    }
  ]
}
```

---

## PowerPoint — Edition

### Tool : `edit_presentation`

Edite un fichier `.pptx` existant dans `OUTPUT_PATH`.

### Parametres

```json
{
  "filename": "revue-trimestrielle-q1.pptx",
  "operations": [ ... ]
}
```

| Parametre | Type | Limites |
|-----------|------|---------|
| `filename` | string | Fichier existant dans OUTPUT_PATH |
| `operations` | array[PresentationEditOp] | 1 a 100 operations |

Les operations sont appliquees en sequence. Les indices de slides sont **0-indexed** (premiere slide = 0).

### Les 11 operations

#### 1. `update_title` — Modifier un titre

```json
{
  "op": "update_title",
  "slide_index": 0,
  "title": "Revue Trimestrielle Q1-Q2 2026",
  "style": {"bold": true, "font_color": "1F4E79"}
}
```

> Si la slide n'a pas de shape titre, un textbox est cree automatiquement.

#### 2. `update_subtitle` — Modifier un sous-titre

```json
{"op": "update_subtitle", "slide_index": 0, "subtitle": "Mise a jour Avril 2026"}
```

#### 3. `update_bullets` — Modifier les puces

```json
{
  "op": "update_bullets",
  "slide_index": 2,
  "bullets": [
    {"text": "CA : 5.1M EUR (+28%)", "level": 0, "bold": true},
    {"text": "Objectif depasse de 18%", "level": 1},
    {"text": "Nouveaux clients : 94", "level": 0, "bold": true}
  ]
}
```

> Remplace **toutes** les puces existantes.

#### 4. `add_slide` — Ajouter une slide

```json
{
  "op": "add_slide",
  "at_index": 3,
  "slide": {
    "layout": "content_bullets",
    "title": "Nouvelle slide inseree",
    "bullets": [{"text": "Contenu a completer"}]
  }
}
```

- `at_index` : position d'insertion (0-indexed). Omis = ajoute a la fin.
- `slide` : meme format que pour la creation (les 8 layouts sont disponibles).

#### 5. `delete_slide` — Supprimer une slide

```json
{"op": "delete_slide", "slide_index": 5}
```

> Attention : les indices changent apres suppression. Si vous supprimez plusieurs slides, procedez du plus grand indice au plus petit.

#### 6. `reorder_slide` — Deplacer une slide

```json
{"op": "reorder_slide", "from_index": 4, "to_index": 1}
```

- `from_index` et `to_index` doivent etre differents.

#### 7. `replace_image` — Remplacer une image

```json
{
  "op": "replace_image",
  "slide_index": 5,
  "image": {"filename": "dashboard-v2.png", "width_cm": 14}
}
```

> Remplace la **premiere** image trouvee sur la slide.

#### 8. `add_image` — Ajouter une image

```json
{
  "op": "add_image",
  "slide_index": 2,
  "image": {"filename": "logo.png", "width_cm": 5, "height_cm": 3}
}
```

#### 9. `update_notes` — Modifier les notes

```json
{"op": "update_notes", "slide_index": 2, "notes": "Parler du deal Acme. Max 3 min."}
```

Notes du presentateur (1-5000 caracteres).

#### 10. `update_chart` — Modifier un graphique

```json
{
  "op": "update_chart",
  "slide_index": 3,
  "chart": {
    "chart_type": "column",
    "title": "CA mensuel (k EUR) — Mise a jour",
    "categories": ["Jan", "Fev", "Mar", "Avr"],
    "series": [
      {"name": "2025", "values": [650, 720, 780, 800]},
      {"name": "2026", "values": [780, 810, 850, 890]}
    ]
  }
}
```

> Remplace le **premier** graphique trouve sur la slide par un nouveau.

#### 11. `set_background` — Couleur de fond

```json
{"op": "set_background", "slide_index": 0, "color": "1F4E79"}
```

Couleur unie. Hex 6 caracteres sans `#`.

---

## Inspection de fichiers

### Tool : `inspect_generated_file`

Inspecte la structure d'un fichier Excel ou PowerPoint pour preparer une edition.

```json
{
  "filename": "rapport-ventes-q1.xlsx",
  "max_rows_per_sheet": 5
}
```

| Parametre | Type | Defaut | Description |
|-----------|------|--------|-------------|
| `filename` | string | — | Fichier dans OUTPUT_PATH (.xlsx ou .pptx) |
| `max_rows_per_sheet` | int | 10 | Lignes echantillon par feuille (1-100) |

### Retour pour Excel

- Liste des feuilles avec colonnes, donnees echantillon, graphiques, validations, proprietes

### Retour pour PowerPoint

- Liste des slides avec titre, sous-titre, puces, images, graphiques, notes

> Utilisez `inspect_generated_file` avant `edit_excel_document` ou `edit_presentation` pour connaitre la structure actuelle du fichier.

---

## Workflow recommande

### Creation simple

```
1. create_excel_document / create_presentation
2. inspect_generated_file  (verifier le resultat)
3. edit_excel_document / edit_presentation  (ajuster si necessaire)
```

### Creation iterative

```
1. create_presentation  (structure initiale)
2. inspect_generated_file
3. edit_presentation  (corrections)
4. inspect_generated_file  (re-verifier)
5. edit_presentation  (finitions)
```

### Consultation avant edition

```
1. list_available_documents(source="generated")  (trouver le fichier)
2. inspect_generated_file  (voir la structure)
3. edit_excel_document / edit_presentation  (editer en connaissance de cause)
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
| Slides par presentation | 100 |
| Operations par edition | 100 |
| Puces par slide | 20 |
| Series par graphique (PPTX) | 10 |
| Valeurs par serie (PPTX) | 50 |
| Categories par graphique (PPTX) | 50 |

### Securite

| Protection | Description |
|------------|-------------|
| Formula injection | Les formules DDE, CMD, SYSTEM, EXEC, CALL sont bloquees |
| Path traversal | `..`, `/`, `\` sont interdits dans les noms de fichiers |
| Author constraint | Max 255 caracteres |
| Image isolation | Seules les images dans `IMAGES_POWERPOINT_PATH` sont accessibles |
| Template isolation | Seuls les templates dans `TEMPLATES_PPTX_PATH` sont accessibles |
| File size check | Le fichier genere est verifie apres ecriture |

### Comportement en cas d'erreur

| Type | Comportement |
|------|-------------|
| Fichier non trouve | Erreur bloquante avec suggestion |
| Feuille/slide inexistante | Erreur bloquante avec liste des feuilles/slides |
| Graphique invalide | **Non bloquant** — compte comme `skipped`, les autres operations continuent |
| Formule dangereuse | Erreur bloquante |
| Taille depassee | Erreur bloquante apres generation |
| Template non trouve | Erreur bloquante avec liste des templates disponibles |
| Image non trouvee | Erreur bloquante avec liste des images disponibles |
