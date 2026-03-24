# Guide de recherche et analyse — Documents

Guide complet pour utiliser les outils MCP de recherche, lecture et analyse de documents (PDF, Excel, Word). Destine au LLM qui appelle les tools, avec tous les workflows, strategies et exemples.

---

## Table des matieres

- [Gestion des documents](#gestion-des-documents)
- [Recherche semantique](#recherche-semantique)
- [Lecture de contenu](#lecture-de-contenu)
- [Formules Excel](#formules-excel)
- [Workflows recommandes](#workflows-recommandes)
- [Adaptation selon la taille du document](#adaptation-selon-la-taille-du-document)
- [Reference des filtres et parametres](#reference-des-filtres-et-parametres)

---

## Gestion des documents

### Verifier les documents disponibles

Avant toute operation, lister les fichiers disponibles pour savoir ce qui peut etre indexe.

#### Tool : `list_available_documents`

```json
{"source": "documents"}
```

| Parametre | Type | Defaut | Description |
|-----------|------|--------|-------------|
| `source` | string | `documents` | `documents` (PDF/Excel/Word), `generated` (fichiers crees), `templates`, `images` |
| `type_filter` | string | `all` | `pdf`, `excel`, `word`, `presentation`, `all` |
| `subdirectory` | string | None | Sous-dossier relatif |
| `recursive` | bool | true | Explorer les sous-dossiers |

Retourne la liste des fichiers avec chemin, type, taille.

---

### Verifier si un document est deja indexe (OBLIGATOIRE)

**IMPORTANT** : Avant d'indexer un document, TOUJOURS verifier s'il est deja indexe. Cela evite les doublons et le traitement inutile.

#### Procedure obligatoire

```
1. list_indexed_documents
2. Chercher le filename dans la liste retournee
3. Si trouve → utiliser le document_id existant, NE PAS re-indexer
4. Si non trouve → proceder a l'indexation
```

#### Tool : `list_indexed_documents`

```json
{}
```

Aucun parametre. Retourne :

```json
{
  "total_documents": 3,
  "documents": [
    {
      "document_id": "abc123",
      "filename": "rapport-annuel.pdf",
      "title": "Rapport Annuel 2025",
      "total_pages": 42,
      "total_chunks": 128,
      "ingested_at": "2026-03-01T10:00:00Z"
    }
  ]
}
```

#### Exemple de verification

```
User: "Resume le fichier budget-2026.xlsx"

Etapes :
1. list_indexed_documents → chercher "budget-2026.xlsx"
2a. Trouve avec document_id "xyz789" → passer directement a la lecture
2b. Non trouve → indexer d'abord avec index_document
```

---

### Indexer un nouveau document

Utiliser UNIQUEMENT si le document n'est pas deja indexe (voir verification ci-dessus).

#### Tool : `index_document`

```json
{
  "file_path": "/chemin/absolu/vers/document.pdf"
}
```

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `file_path` | string | Oui | Chemin absolu vers le fichier |
| `force_ocr` | bool | Non | PDF uniquement — forcer la reconnaissance OCR |
| `sheets` | array[string] | Non | Excel uniquement — noms des feuilles a indexer |
| `table_format` | string | Non | `markdown` (defaut) ou `html` pour les tableaux |

Retourne :

```json
{
  "document_id": "abc123",
  "document_type": "pdf",
  "filename": "rapport.pdf",
  "chunks_stored": 45,
  "has_tables": true,
  "has_formulas": false,
  "has_images": true,
  "total_pages": 12,
  "processing_time_seconds": 3.2
}
```

> **Si le document est deja indexe**, le tool retourne directement l'ID existant sans re-traitement.

---

### Consulter les details d'un document indexe

#### Tool : `get_document`

```json
{"document_id": "abc123"}
```

Retourne les metadonnees completes : filename, title, author, total_pages, total_chunks, total_tokens, content_types, date d'indexation, hash du fichier, et un apercu des chunks.

Utile pour :
- Verifier le nombre de pages avant de choisir la strategie de lecture
- Connaitre les types de contenu (tables, images, formules)
- Recuperer le titre et l'auteur du document

---

### Supprimer un document de l'index

#### Tool : `delete_document`

```json
{"document_id": "abc123"}
```

Supprime le document de l'index vectoriel (Qdrant). **Ne supprime PAS le fichier source.**

Utile pour :
- Re-indexer un document apres modification du fichier source
- Nettoyer l'index

---

## Recherche semantique

### Tool : `search_documents`

Recherche en langage naturel dans tous les documents indexes.

```json
{
  "query": "quelles sont les previsions de chiffre d'affaires pour 2026 ?",
  "top_k": 5,
  "score_threshold": 0.7
}
```

| Parametre | Type | Defaut | Description |
|-----------|------|--------|-------------|
| `query` | string | — | Question en langage naturel |
| `top_k` | int | 5 | Nombre de passages (1-100) |
| `score_threshold` | float | 0.7 | Score minimum de similarite (0.0-1.0) |
| `filters` | object | None | Filtres avances (voir ci-dessous) |

### Filtres disponibles

```json
{
  "filters": {
    "document_id": "abc123",
    "doc_filename": "rapport.pdf",
    "document_type": "pdf",
    "has_table": true,
    "has_image": false,
    "has_formula": true,
    "text_search": "budget",
    "sheet_name": "Ventes"
  }
}
```

| Filtre | Type | Description |
|--------|------|-------------|
| `document_id` | string | Restreindre a un document specifique |
| `doc_filename` | string | Filtrer par nom de fichier |
| `document_type` | string | `pdf`, `excel`, `word` |
| `has_table` | bool | Passages contenant des tableaux |
| `has_image` | bool | Passages contenant des images |
| `has_formula` | bool | Passages contenant des formules Excel |
| `text_search` | string | Recherche textuelle exacte en complement |
| `sheet_name` | string | Excel — filtrer par feuille |

### Retour

```json
{
  "query": "previsions CA 2026",
  "total_results": 3,
  "results": [
    {
      "chunk_id": "...",
      "document_id": "abc123",
      "filename": "rapport.pdf",
      "page": 12,
      "score": 0.92,
      "text": "Le chiffre d'affaires previsionnel pour 2026...",
      "metadata": { "has_table": false }
    }
  ]
}
```

### Conseils pour les requetes

| Situation | Approche |
|-----------|----------|
| Question precise | `"quel est le taux de marge brute au Q3 ?"` |
| Theme general | `"politique de remuneration et avantages salaries"` |
| Donnees chiffrees | Ajouter `has_table: true` ou `has_formula: true` |
| Document specifique | Ajouter `document_id` ou `doc_filename` |
| Excel specifique | Ajouter `sheet_name` et/ou `document_type: "excel"` |

### Ajuster le seuil de similarite

| Seuil | Usage |
|-------|-------|
| `0.8 - 1.0` | Haute precision — peu de resultats mais tres pertinents |
| `0.7` (defaut) | Equilibre precision/rappel |
| `0.5 - 0.7` | Recherche exploratoire — plus de resultats, moins precis |
| `< 0.5` | Rarement utile — trop de bruit |

---

## Lecture de contenu

### Tool : `read_document_content`

Lit le contenu Markdown complet d'un document ou d'une plage de pages.

```json
{
  "document_id": "abc123",
  "page_start": 1,
  "page_end": 5
}
```

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document indexe |
| `page_start` | int | Non | Page de debut (1-indexed) |
| `page_end` | int | Non | Page de fin (1-indexed) |
| `include_chunks_detail` | bool | Non | Inclure les metadonnees des chunks |

### Retour

```json
{
  "document_id": "abc123",
  "filename": "rapport.pdf",
  "total_pages": 42,
  "pages_returned": "1-5",
  "total_tokens": 12500,
  "tokens_returned": 1800,
  "content": "# Titre du document\n\nContenu en Markdown..."
}
```

### Quand utiliser page_start / page_end

| Cas | Parametres |
|-----|------------|
| Lire tout le document (petit doc) | Aucun — lire tout |
| Lire une page specifique trouvee par search | `page_start: 12, page_end: 12` |
| Lire une section | `page_start: 5, page_end: 10` |
| Lire les premieres pages (table des matieres) | `page_start: 1, page_end: 3` |

---

## Formules Excel

### Tool : `get_excel_formulas`

Recupere toutes les formules d'un document Excel indexe.

```json
{
  "document_id": "abc123",
  "sheet": "Ventes",
  "cell_range": "A1:D10"
}
```

| Parametre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `document_id` | string | Oui | ID du document Excel indexe |
| `sheet` | string | Non | Filtrer par nom de feuille |
| `cell_range` | string | Non | Filtrer par plage (ex: `A1:D10`) |

### Retour

```json
{
  "document_id": "abc123",
  "total_formulas": 8,
  "formulas": [
    {
      "cell": "E2",
      "sheet": "Ventes",
      "formula": "=SUM(B2:D2)",
      "result": 45000
    }
  ]
}
```

### Utilisation avec la calculatrice

Quand les formules Excel retournent des valeurs, la **calculatrice** de Zileo Chat permet de faire des calculs derives :

```
Workflow :
1. get_excel_formulas → recuperer les valeurs
2. Calculatrice → faire des calculs supplementaires

Exemples :
- Formule Excel donne CA = 450000, Charges = 320000
  → Calculatrice : marge = (450000 - 320000) / 450000 = 28.9%
- Formule Excel donne Q1 = 120000, Q2 = 135000, Q3 = 148000
  → Calculatrice : croissance Q2/Q1 = (135000 - 120000) / 120000 = 12.5%
  → Calculatrice : projection Q4 = tendance lineaire
```

---

## Workflows recommandes

### 1. Resumer un document

Produire un resume structure d'un document.

```
Etape 1 : Verifier si deja indexe
  → list_indexed_documents
  → Chercher le filename

Etape 2 : Indexer si necessaire
  → index_document (seulement si non trouve a l'etape 1)

Etape 3 : Evaluer la taille
  → get_document → lire total_pages

Etape 4 : Lire le contenu
  Si <= 5 pages (petit document) :
    → read_document_content (tout lire, sans page_start/page_end)
    → Resumer l'ensemble

  Si > 5 pages (document moyen/grand) :
    → read_document_content(page_start=1, page_end=3) pour la table des matieres / introduction
    → search_documents(query="resume objectifs conclusions", document_id=...) pour les passages cles
    → read_document_content sur les pages retournees par la recherche
    → Synthetiser les informations collectees

Etape 5 : Produire le resume
  → Format structure avec sections, points cles, chiffres importants
```

---

### 2. Recherche thematique — "Quelles infos sur tel sujet ?"

Trouver toutes les informations pertinentes sur un sujet precis.

```
Etape 1 : Recherche initiale
  → search_documents(query="le sujet demande", top_k=10)

Etape 2 : Analyser les resultats
  → Identifier les pages et documents pertinents
  → Grouper par document si multi-documents

Etape 3 : Approfondir
  Pour chaque passage pertinent (score >= 0.8) :
    → read_document_content(document_id, page_start=page, page_end=page+1)
    → Lire le contexte complet autour du passage

Etape 4 : Synthetiser
  → Rapport structure avec :
    - Sources (document, page)
    - Extraits pertinents
    - Synthese par theme
```

#### Exemple concret

```
User: "Quelles sont les conditions de resiliation dans le contrat ?"

1. search_documents(query="conditions resiliation contrat", top_k=10)
   → Resultats : page 8 (score 0.95), page 14 (score 0.88), page 22 (score 0.72)

2. read_document_content(document_id, page_start=8, page_end=9)
   → Lecture du contexte complet de la page 8

3. read_document_content(document_id, page_start=14, page_end=15)
   → Lecture du contexte complet de la page 14

4. Synthese :
   "Les conditions de resiliation sont definies aux pages 8-9 et 14-15 :
    - Resiliation a l'echeance : preavis de 3 mois (p.8)
    - Resiliation anticipee : indemnite de 20% du montant restant (p.14)
    - ..."
```

---

### 3. Analyse de donnees Excel

Exploiter les donnees et formules d'un fichier Excel.

```
Etape 1 : Verifier si deja indexe
  → list_indexed_documents
  → Chercher le filename

Etape 2 : Indexer si necessaire
  → index_document(file_path, table_format="markdown")

Etape 3 : Explorer la structure
  → get_document(document_id)
  → Identifier les feuilles, le nombre de pages

Etape 4 : Lire les donnees
  → read_document_content(document_id) pour les tableaux en Markdown
  → get_excel_formulas(document_id) pour les formules et leurs resultats

Etape 5 : Calculer si necessaire
  → Utiliser la calculatrice pour les calculs derives :
    - Pourcentages, marges, ecarts
    - Moyennes, tendances
    - Comparaisons entre periodes

Etape 6 : Presenter les resultats
  → Tableau de synthese
  → Chiffres cles avec sources (feuille, cellule)
```

#### Exemple concret

```
User: "Analyse le budget 2026 et calcule les ecarts avec 2025"

1. list_indexed_documents → "budget-2026.xlsx" trouve, document_id = "xyz789"

2. get_excel_formulas(document_id="xyz789")
   → Total 2026 : 1 250 000 (cellule E15, feuille "Budget")
   → Total 2025 : 980 000 (cellule E15, feuille "Historique")

3. Calculatrice :
   → Ecart = 1 250 000 - 980 000 = 270 000
   → Progression = 270 000 / 980 000 = 27.6%

4. read_document_content(document_id="xyz789") pour les details par poste

5. Rapport :
   "Le budget 2026 s'eleve a 1 250 000 EUR, en hausse de 27.6% par rapport
    a 2025 (980 000 EUR). Les principaux ecarts :
    - Poste X : +150 000 (source : feuille Budget, ligne 5)
    - Poste Y : +80 000 (source : feuille Budget, ligne 8)
    - ..."
```

---

### 4. Analyse comparative multi-documents

Comparer les informations entre plusieurs documents.

```
Etape 1 : Identifier les documents
  → list_indexed_documents
  → Selectionner les documents a comparer

Etape 2 : Recherche croisee
  → search_documents(query="le theme", filters={document_id: "doc1"})
  → search_documents(query="le theme", filters={document_id: "doc2"})

Etape 3 : Lecture ciblee
  → read_document_content sur les pages pertinentes de chaque document

Etape 4 : Comparer et synthetiser
  → Tableau comparatif avec sources
  → Points communs et divergences
```

---

### 5. Generer un rapport a partir d'une analyse

Combiner recherche/analyse avec les outils de generation (voir generation-guide.md).

```
Etape 1 : Analyse avec les tools de recherche (ce guide)
  → Recherche, lecture, formules, calculs

Etape 2 : Creer un livrable avec les tools de generation
  → create_excel_document pour un rapport chiffre
  → create_presentation pour une synthese visuelle

Voir generation-guide.md pour les details de creation.
```

---

## Adaptation selon la taille du document

La strategie de recherche et lecture depend du nombre de pages du document. Toujours verifier la taille avec `get_document` avant de choisir l'approche.

### Petit document (1 a 5 pages)

```
Strategie : lecture integrale

1. get_document(document_id) → confirmer <= 5 pages
2. read_document_content(document_id) → lire TOUT le contenu
3. Analyser / resumer directement a partir du contenu complet
```

| Avantages | Inconvenients |
|-----------|---------------|
| Aucune information manquee | Impossible sur les gros documents |
| Pas besoin de search | — |
| Reponse exhaustive | — |

**Cas d'usage** : resumes, questions ouvertes, verifications completes.

---

### Document moyen (6 a 50 pages)

```
Strategie : recherche + lecture ciblee

1. get_document(document_id) → confirmer 6-50 pages
2. search_documents(query, document_id, top_k=10) → identifier les pages pertinentes
3. read_document_content(page_start, page_end) → lire les sections pertinentes
4. Si resume demande :
   → lire aussi les premieres pages (introduction / table des matieres)
   → lire les dernieres pages (conclusion)
```

| Avantages | Inconvenients |
|-----------|---------------|
| Bon equilibre precision/couverture | Peut manquer des passages non indexes |
| Raisonnable en tokens | Necessite plusieurs appels |

**Cas d'usage** : recherche thematique, questions precises, analyse de sections.

---

### Grand document (51+ pages)

```
Strategie : recherche semantique uniquement + drill-down progressif

1. get_document(document_id) → confirmer 51+ pages
2. search_documents(query, document_id, top_k=10, score_threshold=0.75)
   → Premiere passe : identifier les zones pertinentes
3. Pour les meilleurs resultats (score >= 0.85) :
   → read_document_content(page_start=page-1, page_end=page+1)
   → Lire 3 pages autour du passage (contexte)
4. Si necessaire, affiner avec une seconde recherche :
   → search_documents avec une query reformulee ou des filtres supplementaires
5. Utiliser la calculatrice si des calculs sont necessaires
   sur les donnees extraites
```

| Avantages | Inconvenients |
|-----------|---------------|
| Efficace en tokens | Resume exhaustif difficile |
| Fonctionne sur des documents tres longs | Depend de la qualite de l'indexation |

**Cas d'usage** : questions precises dans un rapport annuel, recherche de clauses dans un contrat long.

---

### Tableau recapitulatif

| Taille | Pages | Strategie | Tool principal |
|--------|-------|-----------|----------------|
| Petit | 1-5 | Lecture integrale | `read_document_content` (tout) |
| Moyen | 6-50 | Recherche + lecture ciblee | `search_documents` + `read_document_content` (pages) |
| Grand | 51+ | Recherche seule + drill-down | `search_documents` + `read_document_content` (3 pages max) |

---

## Reference des filtres et parametres

### Filtres search_documents

| Filtre | Type | Valeurs | Usage |
|--------|------|---------|-------|
| `document_id` | string | ID du document | Restreindre a un document |
| `doc_filename` | string | Nom du fichier | Filtrer par nom |
| `document_type` | string | `pdf`, `excel`, `word` | Filtrer par type |
| `has_table` | bool | true/false | Passages avec tableaux |
| `has_image` | bool | true/false | Passages avec images |
| `has_formula` | bool | true/false | Passages avec formules Excel |
| `text_search` | string | Texte libre | Recherche exacte en complement |
| `sheet_name` | string | Nom de feuille | Excel — filtrer par feuille |

### Sources list_available_documents

| Source | Contenu | Usage |
|--------|---------|-------|
| `documents` | PDF, Excel, Word dans le dossier source | Fichiers a indexer |
| `generated` | Excel, PowerPoint crees par les tools | Fichiers generes |
| `templates` | Templates PowerPoint | Pour create_presentation |
| `images` | Images pour slides | Pour content_with_image |

### Types de documents supportes

| Type | Extensions | Particularites |
|------|-----------|----------------|
| PDF | `.pdf` | OCR disponible (`force_ocr`). Contient texte, tableaux, images |
| Excel | `.xlsx` | Feuilles multiples, formules, `table_format` configurable |
| Word | `.docx` | Texte structure, tableaux, images |

### Parametres d'indexation par type

| Parametre | PDF | Excel | Word |
|-----------|-----|-------|------|
| `force_ocr` | Oui | — | — |
| `sheets` | — | Oui (noms des feuilles) | — |
| `table_format` | Oui | Oui | Oui |
