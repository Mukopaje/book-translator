"""
DiagramAgent: optional wrapper around diagram processing to emit artifacts.

MVP keeps behavior no-op because existing DiagramTranslator handles
diagram image/labels. This provides a normalized artifact output path for
future integration.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import uuid

from artifacts.schemas import BBox, DiagramArtifact, DiagramAnnotation


class DiagramAgent:
    def __init__(self) -> None:
        pass

    def from_translated_diagrams(
        self,
        translated_diagrams: Optional[List[Dict[str, Any]]]
    ) -> List[DiagramArtifact]:
        """
        Convert existing translated diagram results into artifacts.
        Each item in translated_diagrams is expected to include:
          - image (PIL.Image)
          - region {x,y,w,h}
          - annotations: [{x,y,w,h, text, original}]
        """
        if not translated_diagrams:
            return []

        artifacts: List[DiagramArtifact] = []
        for item in translated_diagrams:
            region = item.get("region", {})
            bbox = BBox(
                x=int(region.get("x", 0)),
                y=int(region.get("y", 0)),
                w=int(region.get("w", 0)),
                h=int(region.get("h", 0)),
            )
            anns_raw = item.get("annotations", []) or []
            anns = [
                DiagramAnnotation(
                    x=int(a.get("x", 0)),
                    y=int(a.get("y", 0)),
                    w=int(a.get("w", 0)),
                    h=int(a.get("h", 0)),
                    original=str(a.get("original", "")),
                    text=str(a.get("text", "")),
                )
                for a in anns_raw
            ]
            artifacts.append(
                DiagramArtifact(
                    id=str(uuid.uuid4()),
                    type="diagram",
                    bbox=bbox,
                    annotations=anns,
                )
            )
        return artifacts
