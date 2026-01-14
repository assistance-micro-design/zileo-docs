# Architecture MCP Zileo PDF

## Vue d'Ensemble

MCP Zileo PDF est un serveur pour l'extraction et la vectorisation de documents PDF. Il expose ses fonctionnalites via une API REST FastAPI et un serveur MCP (Model Context Protocol) en JSON-RPC 2.0.

## Composants Principaux

### Couche API

- **REST API** (`/api/v1/*`) : Endpoints pour l'indexation et la recherche de documents
- **MCP Server** (`/mcp`) : Serveur JSON-RPC 2.0 pour integration avec les LLMs
- **Health Checks** (`/health/*`) : Endpoints de monitoring

### Couche Services

Le traitement des PDF suit un pipeline en 5 phases :

| Phase | Composant | Description |
|-------|-----------|-------------|
| 1 | Analyzer | Analyse du document et classification des pages |
| 2 | Native Extractor | Extraction du texte natif (PyMuPDF4LLM) |
| 3 | OCR Processor | OCR Mistral pour pages complexes |
| 4 | Chunker + Embedder | Decoupage semantique et generation d'embeddings |
| 5 | Vector Store | Stockage dans Qdrant avec metadata riche |

### Orchestrateur

Le `PDFPipelineOrchestrator` coordonne l'execution du pipeline :

1. Analyse le document pour classifier chaque page
2. Extrait le texte natif des pages simples
3. Applique l'OCR aux pages complexes (tableaux, images, scans)
4. Fusionne et decoupe le contenu en chunks semantiques
5. Genere les embeddings et stocke dans Qdrant

## Services Externes

| Service | Utilisation |
|---------|-------------|
| **Mistral OCR** | Extraction de contenu des pages complexes |
| **Mistral Embed** | Generation d'embeddings (1024 dimensions) |
| **Qdrant** | Base de donnees vectorielle |

## Classification des Pages

L'analyseur classifie chaque page selon son contenu :

| Type | Methode d'extraction |
|------|---------------------|
| TEXT_ONLY | PyMuPDF4LLM (gratuit, rapide) |
| HAS_TABLES | Mistral OCR |
| HAS_IMAGES | Mistral OCR |
| HAS_CHARTS | Mistral OCR |
| SCANNED | Mistral OCR |
| MIXED | Mistral OCR |

## Chunking Semantique

Le chunker preserve l'integrite du contenu :

- **Tableaux** : Gardes intacts, jamais coupes
- **Blocs de code** : Preserves en entier
- **Equations** : Non fragmentees
- **Sections** : Hierarchie preservee dans les metadonnees
- **Overlap** : 50 tokens entre chunks pour continuite

## Metadata des Chunks

Chaque chunk stocke des metadonnees riches pour le filtrage :

- Identifiants (chunk_id, document_id)
- Localisation (pages, position dans le document)
- Structure (titre de section, hierarchie)
- Type de contenu (texte, tableau, equation)
- Statistiques (tokens, caracteres, mots)
- Contexte environnant

## Structure du Projet

```
src/
├── api/           # Endpoints REST
├── mcp/           # Serveur MCP et tools
├── services/      # Logique metier (pipeline)
├── models/        # Schemas Pydantic
└── core/          # Configuration et exceptions

tests/
├── unit/          # Tests unitaires
├── integration/   # Tests avec services externes
└── e2e/           # Tests bout-en-bout
```
