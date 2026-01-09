"""Artifact API endpoints: fetch per-page artifacts in JSON/CSV/HTML."""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
import requests

from app.database import get_db
from app.models.db_models import User, Project, Page
from app.api.dependencies import get_current_user
from app.services.storage import storage_service
from app.config import settings

router = APIRouter(prefix="/projects/{project_id}/pages/{page_id}/artifacts", tags=["artifacts"])


def _verify_access(project_id: int, user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_page(project_id: int, page_id: int, db: Session) -> Page:
    page = db.query(Page).filter(Page.id == page_id, Page.project_id == project_id).first()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return page


def _load_artifacts_json(project_id: int, page_number: int) -> Dict[str, Any]:
    """Load artifacts JSON from storage outputs."""
    blob_path = f"projects/{project_id}/outputs/page_{page_number}_artifacts.json"
    try:
        if settings.use_local_storage:
            local_path = storage_service.get_local_path(blob_path, is_output=True)
            if not local_path or not local_path.endswith(".json"):
                raise FileNotFoundError("Artifact JSON path invalid")
            with open(local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            signed = storage_service.get_signed_url(settings.gcs_bucket_outputs, blob_path, expiration=300)
            # Signed URL may be file:// for local mode; requests handles http/https
            data_path = signed.replace("file://", "")
            resp = requests.get(data_path)
            if resp.status_code != 200:
                raise FileNotFoundError(f"Artifact JSON not found: {resp.status_code}")
            return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else json.loads(resp.text)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artifacts not found: {e}")


@router.get("")
def get_artifacts(
    project_id: int,
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return artifacts JSON for a page (tables/charts/diagrams)."""
    _verify_access(project_id, current_user, db)
    page = _get_page(project_id, page_id, db)
    return _load_artifacts_json(project_id, page.page_number)


def _tables_to_csv(artifacts: Dict[str, Any]) -> str:
    tables: List[Dict[str, Any]] = artifacts.get("tables", [])
    if not tables:
        return ""
    # Concatenate all tables with blank line separation
    lines: List[str] = []
    for t in tables:
        rows = int(t.get("rows", 0))
        cols = int(t.get("cols", 0))
        cells = t.get("cells", [])
        grid: Dict[tuple, str] = {}
        for c in cells:
            r = int(c.get("row", 0))
            col = int(c.get("col", 0))
            txt = str(c.get("translation") or c.get("text") or "").replace("\n", " ")
            grid[(r, col)] = txt
        for r in range(rows):
            row_vals = [grid.get((r, c), "") for c in range(cols)]
            lines.append(",".join(row_vals))
        lines.append("")  # blank line between tables
    return "\n".join(lines).rstrip()


@router.get("/tables.csv")
def get_tables_csv(
    project_id: int,
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all tables as CSV (simple, concatenated)."""
    _verify_access(project_id, current_user, db)
    page = _get_page(project_id, page_id, db)
    artifacts = _load_artifacts_json(project_id, page.page_number)
    csv_text = _tables_to_csv(artifacts)
    return Response(content=csv_text, media_type="text/csv")


@router.get("/tables.html")
def get_tables_html(
    project_id: int,
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return simple HTML rendering of all tables."""
    _verify_access(project_id, current_user, db)
    page = _get_page(project_id, page_id, db)
    artifacts = _load_artifacts_json(project_id, page.page_number)
    tables = artifacts.get("tables", [])
    # Span-aware HTML table rendering
    html_parts: List[str] = ["<html><body>"]
    for t in tables:
        rows = int(t.get("rows", 0)); cols = int(t.get("cols", 0)); cells = t.get("cells", [])
        # Build cell map with spans
        cell_map: Dict[tuple, Dict[str, Any]] = {}
        for c in cells:
            r = int(c.get("row", 0)); col = int(c.get("col", 0))
            txt = str(c.get("translation") or c.get("text") or "")
            rs = int(c.get("row_span", 1)); cs = int(c.get("col_span", 1))
            cell_map[(r, col)] = {"text": txt, "row_span": rs, "col_span": cs}
        covered: set = set()
        html_parts.append("<table border='1' cellspacing='0' cellpadding='4' style='margin-bottom:12px;'>")
        for r in range(rows):
            html_parts.append("<tr>")
            for cidx in range(cols):
                if (r, cidx) in covered:
                    continue
                cell = cell_map.get((r, cidx))
                if not cell:
                    html_parts.append("<td></td>")
                    continue
                rs = max(1, int(cell.get("row_span", 1)))
                cs = max(1, int(cell.get("col_span", 1)))
                # Mark covered cells
                for rr in range(r, min(rows, r + rs)):
                    for cc in range(cidx, min(cols, cidx + cs)):
                        if rr == r and cc == cidx:
                            continue
                        covered.add((rr, cc))
                attrs = []
                if rs > 1:
                    attrs.append(f"rowspan='{rs}'")
                if cs > 1:
                    attrs.append(f"colspan='{cs}'")
                attr_str = (" " + " ".join(attrs)) if attrs else ""
                html_parts.append(f"<td{attr_str}>{cell.get('text','')}</td>")
            html_parts.append("</tr>")
        html_parts.append("</table>")
    html_parts.append("</body></html>")
    return Response(content="".join(html_parts), media_type="text/html")


def _diagram_lists_from_artifacts(artifacts: Dict[str, Any]) -> Dict[str, List[str]]:
    """Return diagram items classified into 'key' and 'on_image' lists.

    Prefer persisted render modes ('diagram_renderings'). Fallback to heuristic.
    """
    # Persisted rendering modes
    renderings = artifacts.get("diagram_renderings", []) or []
    if renderings:
        key_items: List[str] = []
        on_image: List[str] = []
        for entry in renderings:
            anns = entry.get('annotations', []) or []
            for a in anns:
                txt = str(a.get('text', ''))
                mode = str(a.get('mode', ''))
                if mode == 'key':
                    key_items.append(txt)
                elif mode in ('image', 'marker'):
                    on_image.append(txt)
        # De-duplicate preserving order
        def dedup(seq: List[str]) -> List[str]:
            seen = set(); out = []
            for s in seq:
                if s not in seen:
                    seen.add(s); out.append(s)
            return out
        return {"key": dedup(key_items), "on_image": dedup(on_image)}

    # Heuristic fallback
    diags = artifacts.get("diagrams", []) or []
    key_items: List[str] = []
    on_image: List[str] = []

    def is_critical(text: str) -> bool:
        import re
        if not text:
            return False
        cleaned = re.sub(r"[^A-Za-z0-9]", "", str(text)).lower()
        return cleaned in {"a","b","p","v","p1","p2","v1","v2","pa","pb","pc","va","vb","vc"}

    for d in diags:
        region = d.get("bbox") or d.get("region") or {}
        h = int(region.get("h", 0)) or int(region.get("height", 0))
        anns = d.get("annotations", []) or []
        for a in anns:
            txt = str(a.get("text", ""))
            orig = str(a.get("original", ""))
            ay = int(a.get("y", 0)); ah = int(a.get("h", 0))
            center_ratio = 0.5
            if h > 0:
                center_ratio = (ay + ah/2.0) / float(h)
            in_bottom_band = center_ratio > 0.75
            num_words = len(txt.split())
            is_short = len(txt) <= 10 and num_words <= 2
            # Key rule: bottom-band labels OR non-critical longer labels
            if in_bottom_band or (not is_critical(txt) and not is_short):
                key_items.append(txt)
            else:
                on_image.append(txt)
    # De-duplicate while preserving order
    seen = set(); ordered = []
    for item in key_items:
        if item not in seen:
            seen.add(item); ordered.append(item)
    ordered_on = []
    seen_on = set()
    for item in on_image:
        if item not in seen_on:
            seen_on.add(item); ordered_on.append(item)
    return {"key": ordered, "on_image": ordered_on}


@router.get("/diagrams/key")
def get_diagram_key(
    project_id: int,
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return computed Diagram Key items for a page."""
    _verify_access(project_id, current_user, db)
    page = _get_page(project_id, page_id, db)
    artifacts = _load_artifacts_json(project_id, page.page_number)
    lists = _diagram_lists_from_artifacts(artifacts)
    return lists
