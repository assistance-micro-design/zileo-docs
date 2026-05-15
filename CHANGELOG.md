# Changelog

Toutes les modifications notables de ce projet sont documentees dans ce fichier.

Le format est base sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhere au [Semantic Versioning](https://semver.org/lang/fr/).

## [Unreleased]

## [0.3.0] - 2026-05-15

### BREAKING CHANGES
- Tool MCP `search_documents` supprime. Remplace par deux tools dedies avec schemas non-ambigus :
  - `search_hybrid` : `query` + `top_k` + `filters` + `min_cosine_relevance` (echelle RRF masquee, garde-fou cosinus 0.72 anti hors-domaine)
  - `search_semantic` : `query` + `top_k` + `filters` + `score_threshold` (similarite cosinus pure, defaut 0.7)
- Model Pydantic `SearchDocumentsParams` supprime ; remplace par `SearchHybridParams` + `SearchSemanticParams`
- Methode `DocumentPipelineOrchestrator.search_documents` supprimee (code mort, non utilise)

### Added
- Classe abstraite `BaseSearchTool(VectorStoreMCPTool)` dans `src/mcp/tools/search_base.py` factorise la logique partagee (DI, validation Pydantic, embedding query, formatage reponse)
- Eval `scripts/eval_rag.py` accepte desormais `--tool search_hybrid|search_semantic` (remplace `--mode`)

### Changed
- API REST `POST /api/v1/search` **inchangee** : conserve `search_mode` comme parametre bas niveau. L'asymetrie REST/MCP est volontaire (REST = bas niveau, MCP = orientee agent)
- Message d'erreur du tool `index_document` (deja indexe) reference desormais `search_hybrid`/`search_semantic`

### Migration
- Caller MCP : remplacer `search_documents` (mode hybrid) par `search_hybrid` ; remplacer `search_documents` (mode semantic) par `search_semantic`
- Le format de reponse est identique (chunk_id, score, page_numbers, etc.) — seuls le nom et le schema d'entree changent

## [0.2.0] - 2026-04-28

### Added
- Recherche hybride RRF : `hybrid_search` combine dense (vecteur) + full-text avec Reciprocal Rank Fusion
- Sparse embeddings BM25 via `fastembed` (prefetch natif Qdrant)
- Parametre `search_mode` (hybrid/semantic) sur MCP `search_documents` et REST `/api/v1/search`
- Hash SHA-256 de fichier (`compute_file_hash`) pour deduplication Excel/Word
- Detection de fichier modifie : comparaison hash lors de `index_document`
- Champ `file_hash` dans `UnifiedMetadata` et payload Qdrant
- Outil MCP `create_word_document` : generation Word (.docx) depuis Markdown
- Fichiers communaute GitHub : `SECURITY.md`, `CONTRIBUTORS.md`, `NOTICE`, `THIRD_PARTY_LICENSES.md`
- CI GitHub Actions : `validate.yml` (ruff, mypy, pytest unit), `dependabot.yml` (pip + docker + actions)
- Templates issue (bug, feature) et pull request

### Changed
- `IndexDocumentTool` utilise injection de dependances (vector_store, embedder)
- Mode de recherche par defaut : `hybrid` (avant: semantic uniquement)
- `_create_indexes` refactorise avec constantes de module
- `_extract_excel`/`_extract_word` reutilisent les extracteurs deja initialises
- Statut projet : Alpha → Beta
- Renommage `LICENSE.txt` → `LICENSE` (convention GitHub)
- Branche par defaut : `master` → `main`

### Removed
- Code mort `_VALID_TYPES_BY_SOURCE` dans `ListAvailableDocumentsParams`

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
