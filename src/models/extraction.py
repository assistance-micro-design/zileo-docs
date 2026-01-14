"""Models pour les resultats d'extraction de contenu."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HeaderInfo:
    """Information sur un header detecte.

    Attributes:
        level: Niveau du header (1-6).
        text: Texte du header.
        position: Position dans le document.
    """

    level: int
    text: str
    position: int

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "level": self.level,
            "text": self.text,
            "position": self.position,
        }


@dataclass
class ListInfo:
    """Information sur une liste detectee.

    Attributes:
        type: Type de liste ("bullet" | "numbered").
        items: Elements de la liste.
    """

    type: str  # "bullet" | "numbered"
    items: list[str]

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "type": self.type,
            "items": self.items,
        }


@dataclass
class TablePlaceholder:
    """Placeholder pour un tableau detecte lors de l'extraction native.

    Attributes:
        id: Identifiant unique du tableau.
        position: Position dans le texte.
        rows: Nombre de lignes.
        cols: Nombre de colonnes.
        raw_content: Contenu brut avant traitement OCR.
    """

    id: str
    position: int
    rows: int
    cols: int
    raw_content: str

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "id": self.id,
            "position": self.position,
            "rows": self.rows,
            "cols": self.cols,
            "raw_content": self.raw_content,
        }


@dataclass
class ImagePlaceholder:
    """Placeholder pour une image detectee lors de l'extraction native.

    Attributes:
        id: Identifiant unique de l'image.
        position: Position dans le texte.
        alt_text: Texte alternatif.
        path: Chemin vers l'image extraite.
    """

    id: str
    position: int
    alt_text: str
    path: str

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "id": self.id,
            "position": self.position,
            "alt_text": self.alt_text,
            "path": self.path,
        }


@dataclass
class ExtractedContent:
    """Contenu extrait d'une page (Phase 2 - extraction native).

    Attributes:
        page_number: Numero de la page (1-indexed).
        markdown_content: Contenu au format Markdown.
        extraction_method: Methode utilisee pour l'extraction.
    """

    page_number: int
    markdown_content: str
    extraction_method: str = "pymupdf4llm"

    # Structure
    headers: list[HeaderInfo] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    lists: list[ListInfo] = field(default_factory=list)

    # Placeholders
    table_placeholders: list[TablePlaceholder] = field(default_factory=list)
    image_placeholders: list[ImagePlaceholder] = field(default_factory=list)

    # Stats
    char_count: int = 0
    word_count: int = 0

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "page_number": self.page_number,
            "markdown_content": self.markdown_content,
            "extraction_method": self.extraction_method,
            "headers": [h.to_dict() for h in self.headers],
            "paragraphs": self.paragraphs,
            "lists": [lst.to_dict() for lst in self.lists],
            "table_placeholders": [t.to_dict() for t in self.table_placeholders],
            "image_placeholders": [i.to_dict() for i in self.image_placeholders],
            "char_count": self.char_count,
            "word_count": self.word_count,
        }


# === OCR Results (Phase 3) ===


@dataclass
class TableData:
    """Tableau extrait par OCR.

    Attributes:
        id: Identifiant unique du tableau.
        markdown: Representation Markdown.
        html: Representation HTML.
        headers: En-tetes des colonnes.
        rows: Nombre de lignes.
        cols: Nombre de colonnes.
        data: Donnees du tableau (liste de lignes).
    """

    id: str
    markdown: str
    html: str
    headers: list[str]
    rows: int
    cols: int
    data: list[list[str]]

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "id": self.id,
            "markdown": self.markdown,
            "html": self.html,
            "headers": self.headers,
            "rows": self.rows,
            "cols": self.cols,
            "data": self.data,
        }


@dataclass
class ImageData:
    """Image extraite par OCR.

    Attributes:
        id: Identifiant unique de l'image.
        description: Description generee par l'OCR.
        bounding_box: Coordonnees [x1, y1, x2, y2].
        base64: Image encodee en base64.
    """

    id: str
    description: str
    bounding_box: list[float] | None = None
    base64: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "id": self.id,
            "description": self.description,
            "bounding_box": self.bounding_box,
            "base64": self.base64,
        }


@dataclass
class ChartData:
    """Graphique detecte par OCR.

    Attributes:
        id: Identifiant unique du graphique.
        chart_type: Type de graphique (bar, line, pie, etc.).
        description: Description du graphique.
        data_points: Points de donnees extraits.
    """

    id: str
    chart_type: str
    description: str
    data_points: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "id": self.id,
            "chart_type": self.chart_type,
            "description": self.description,
            "data_points": self.data_points,
        }


@dataclass
class EquationData:
    """Equation LaTeX extraite par OCR.

    Attributes:
        id: Identifiant unique de l'equation.
        latex: Code LaTeX de l'equation.
        type: Type d'equation ("inline" | "block").
    """

    id: str
    latex: str
    type: str  # "inline" | "block"

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "id": self.id,
            "latex": self.latex,
            "type": self.type,
        }


@dataclass
class OCRResult:
    """Resultat OCR d'une page (Phase 3).

    Attributes:
        page_number: Numero de la page (1-indexed).
        markdown_content: Contenu Markdown genere par l'OCR.
    """

    page_number: int
    markdown_content: str

    # Elements structures
    tables: list[TableData] = field(default_factory=list)
    images: list[ImageData] = field(default_factory=list)
    charts: list[ChartData] = field(default_factory=list)
    equations: list[EquationData] = field(default_factory=list)

    # Qualite
    confidence_score: float = 0.0
    processing_time_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "page_number": self.page_number,
            "markdown_content": self.markdown_content,
            "tables": [t.to_dict() for t in self.tables],
            "images": [i.to_dict() for i in self.images],
            "charts": [c.to_dict() for c in self.charts],
            "equations": [e.to_dict() for e in self.equations],
            "confidence_score": self.confidence_score,
            "processing_time_ms": self.processing_time_ms,
        }
