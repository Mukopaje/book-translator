"""
Artifact schemas for structured content extracted from a page.

Lightweight models with simple dict interoperability so they can be
returned in API responses or saved as JSON alongside page outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple, ClassVar


@dataclass
class BBox:
    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class TextBox:
    x: int
    y: int
    w: int
    h: int
    text: str
    translation: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TextBox":
        return cls(
            x=int(d.get("x", 0)),
            y=int(d.get("y", 0)),
            w=int(d.get("w", 0)),
            h=int(d.get("h", 0)),
            text=str(d.get("text", "")),
            translation=d.get("translation"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactBase:
    id: str
    bbox: BBox
    meta: Dict[str, Any] = field(default_factory=dict)
    # Class-level type identifier (not part of dataclass fields)
    type: ClassVar[str] = "artifact"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["type"] = getattr(self.__class__, "type", "artifact")
        d["bbox"] = self.bbox.to_dict()
        return d


@dataclass
class TableCell:
    row: int
    col: int
    text: str
    translation: Optional[str] = None
    row_span: int = 1
    col_span: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableArtifact(ArtifactBase):
    type: ClassVar[str] = "table"
    rows: int = 0
    cols: int = 0
    cells: List[TableCell] = field(default_factory=list)

    def to_html(self) -> str:
        grid: Dict[Tuple[int, int], str] = {}
        for c in self.cells:
            grid[(c.row, c.col)] = c.translation or c.text
        html_rows = []
        for r in range(self.rows):
            tds = []
            for c in range(self.cols):
                tds.append(f"<td>{grid.get((r,c), '')}</td>")
            html_rows.append("<tr>" + "".join(tds) + "</tr>")
        return "<table>" + "".join(html_rows) + "</table>"

    def to_csv(self, delimiter: str = ",") -> str:
        grid: Dict[Tuple[int, int], str] = {}
        for c in self.cells:
            grid[(c.row, c.col)] = (c.translation or c.text).replace("\n", " ")
        lines = []
        for r in range(self.rows):
            line = delimiter.join(grid.get((r, c), "") for c in range(self.cols))
            lines.append(line)
        return "\n".join(lines)


@dataclass
class DiagramAnnotation:
    x: int
    y: int
    w: int
    h: int
    original: str
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiagramArtifact(ArtifactBase):
    type: ClassVar[str] = "diagram"
    # Optional vector annotations; image is handled elsewhere (PDF composer or storage)
    annotations: List[DiagramAnnotation] = field(default_factory=list)


@dataclass
class ChartArtifact(ArtifactBase):
    type: ClassVar[str] = "chart"
    # Vega-Lite or similar spec
    spec: Dict[str, Any] = field(default_factory=dict)


def artifacts_to_dict(artifacts: List[ArtifactBase]) -> List[Dict[str, Any]]:
    return [a.to_dict() for a in artifacts]
