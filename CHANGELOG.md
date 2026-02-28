# Changelog

Toutes les modifications notables de ce projet sont documentees dans ce fichier.

Le format est base sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhere au [Semantic Versioning](https://semver.org/lang/fr/).

## [0.1.0] - 2026-02-28

Premiere version fonctionnelle du serveur MCP Zileo RAG.

### Added
- 8 outils MCP via JSON-RPC 2.0 : `index_document`, `search_documents`, `get_document`, `delete_document`, `list_indexed_documents`, `list_available_documents`, `read_document_content`, `get_excel_formulas`
- Support multi-format : PDF (natif + OCR Mistral), Excel (.xlsx/.xls), Word (.docx)
- API REST avec endpoints health, documents, search
- Pipeline d'extraction : analyse -> extraction -> chunking -> embedding -> stockage vectoriel
- Embeddings Mistral (1024 dimensions) et stockage Qdrant
- OCR intelligent : detection automatique pages texte vs image
- Smart chunking avec preservation de la structure Markdown
- Protection contre la double indexation (guard doublon)
- Rate limiting configurable (slowapi)
- Protection anti-path-traversal sur les outils MCP
- Deploiement Docker (multi-stage, non-root, healthchecks)
- 319 tests unitaires (couverture > 80%)
- Licence AGPL-3.0-or-later
