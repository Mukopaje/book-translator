"""
ChartAgent: generates charts (e.g., Vega-Lite specs).

MVP implementation converts simple two-column tables into a basic chart
spec (bar or line) for Streamlit rendering.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import uuid
import re
from datetime import datetime

from artifacts.schemas import BBox, ChartArtifact


class ChartAgent:
    def __init__(self) -> None:
        pass

    def detect_and_extract(
        self,
        image_path: str,
        ocr_boxes: List[Dict[str, Any]],
        translator: Any = None,
        book_context: Optional[str] = None,
    ) -> List[ChartArtifact]:
        """Placeholder: chart detection from OCR boxes not implemented."""
        return []

    def from_tables(self, tables: List[Any]) -> List[ChartArtifact]:
        """
        Generate charts from tables with smarter heuristics.

        - Requires at least 2 rows and 2 columns.
        - Uses first column for x (labels/dates) and remaining columns as series.
        - Detects header row to name axes and series, parses units from headers.
        - Chooses line for temporal x; for categorical x with numeric y, uses bar (stacked for multi-series).
        - Adds timeUnit and axis format for temporal x (year, yearmonth, or full date).
        """
        artifacts: List[ChartArtifact] = []
        if not tables:
            return artifacts

        # Helper functions (local)
        def try_parse_number(s: str) -> Optional[float]:
            try:
                sc = (s or "").replace(',', '').strip()
                if sc.endswith('%'):
                    sc = sc[:-1]
                return float(sc)
            except Exception:
                return None

        def is_numeric(s: str) -> bool:
            return try_parse_number(s) is not None

        date_patterns = [
            r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$",  # YYYY-MM-DD variants
            r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{4}$",  # DD-MM-YYYY variants
            r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}$",
            r"^\d{4}$",
        ]

        def looks_like_date(s: str) -> bool:
            ss = (s or "").strip()
            for pat in date_patterns:
                if re.match(pat, ss, flags=re.IGNORECASE):
                    return True
            return False

        def normalize_date_and_granularity(s: str) -> Tuple[Optional[str], Optional[str]]:
            ss = (s or "").strip()
            for fmt in [
                "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
                "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
            ]:
                try:
                    return datetime.strptime(ss, fmt).strftime("%Y-%m-%d"), "date"
                except Exception:
                    pass
            for fmt in ["%B %Y", "%b %Y"]:
                try:
                    dt = datetime.strptime(ss, fmt)
                    return dt.strftime("%Y-%m-01"), "yearmonth"
                except Exception:
                    pass
            if re.match(r"^\d{4}$", ss):
                return f"{ss}-01-01", "year"
            return None, None

        def extract_units(label: str) -> Optional[str]:
            m = re.search(r"\(([^)]+)\)", label or "")
            return m.group(1).strip() if m else None

        def majority(items: List[str], default: Optional[str] = None) -> Optional[str]:
            if not items:
                return default
            counts: Dict[str, int] = {}
            for it in items:
                if it is None:
                    continue
                counts[it] = counts.get(it, 0) + 1
            if not counts:
                return default
            return max(counts, key=counts.get)

        for t in tables:
            # Handle both TableArtifact objects and dictionaries
            if hasattr(t, 'rows'):
                # It's a TableArtifact object
                rows = int(t.rows)
                cols = int(t.cols)
                cells = t.cells
            else:
                # It's a dictionary
                rows = int(t.get('rows', 0))
                cols = int(t.get('cols', 0))
                cells = t.get('cells', [])
            
            if rows < 2 or cols < 2:
                continue

            # Build grid
            grid: Dict[tuple, Any] = {}
            for c in cells:
                if hasattr(c, 'row'):
                    # It's a TableCell object
                    r = int(c.row)
                    col = int(c.col)
                    txt = c.translation or c.text
                else:
                    # It's a dictionary
                    r = int(c.get('row', 0))
                    col = int(c.get('col', 0))
                    txt = c.get('translation') or c.get('text', '')
                grid[(r, col)] = str(txt)

            # Two-column tables: treat as single-series
            if cols == 2:
                x_vals: List[str] = [grid.get((r, 0), '') for r in range(rows)]
                y_vals_raw: List[str] = [grid.get((r, 1), '') for r in range(rows)]

                # Header detection: both first-row cells non-numeric
                has_header = (not is_numeric(x_vals[0])) and (not is_numeric(y_vals_raw[0]))
                x_title = x_vals[0] if has_header else "x"
                y_title = y_vals_raw[0] if has_header else "y"
                y_units = extract_units(y_title)

                # Numeric ratio for y
                y_nums: List[Optional[float]] = [try_parse_number(v) for v in y_vals_raw]
                numeric_ratio = sum(1 for v in y_nums if v is not None) / max(1, len(y_vals_raw))

                # Temporal detection on x
                x_is_temporal = sum(1 for v in x_vals if looks_like_date(v)) / max(1, len(x_vals)) >= 0.7

                # Normalize dates + find granularity
                gran_samples: List[str] = []
                data_values: List[Dict[str, Any]] = []
                start_row = 1 if has_header else 0
                for i in range(start_row, rows):
                    xv = x_vals[i]
                    if x_is_temporal:
                        iso, gran = normalize_date_and_granularity(xv)
                        gran_samples.append(gran or "")
                        xv_out = iso or xv
                    else:
                        xv_out = xv
                    yv = y_nums[i] if y_nums[i] is not None else y_vals_raw[i]
                    data_values.append({"x": xv_out, "y": yv})

                time_unit_map = {"year": "year", "yearmonth": "yearmonth", "date": "yearmonthdate"}
                axis_format_map = {"year": "%Y", "yearmonth": "%b %Y", "date": "%d %b %Y"}
                dominant_gran = majority(gran_samples)
                x_type = "temporal" if x_is_temporal else "ordinal"
                mark_type = "line" if x_is_temporal else ("bar" if numeric_ratio >= 0.7 else "line")

                spec: Dict[str, Any] = {"mark": mark_type, "encoding": {}}
                enc_x: Dict[str, Any] = {"field": "x", "type": x_type, "axis": {"title": x_title}}
                if x_is_temporal and dominant_gran:
                    enc_x["timeUnit"] = time_unit_map.get(dominant_gran, "yearmonthdate")
                    enc_x["axis"]["format"] = axis_format_map.get(dominant_gran, "%d %b %Y")
                enc_y: Dict[str, Any] = {
                    "field": "y",
                    "type": "quantitative" if numeric_ratio >= 0.7 else "nominal",
                    "axis": {"title": y_title if not y_units else f"{y_title} [{y_units}]"},
                }
                spec["encoding"]["x"] = enc_x
                spec["encoding"]["y"] = enc_y

                artifacts.append(
                    ChartArtifact(
                        id=str(uuid.uuid4()),
                        bbox=BBox(x=0, y=0, w=0, h=0),
                        spec=spec,
                        meta={
                            "source": "table_to_chart_v2",
                            "numeric_ratio": numeric_ratio,
                            "x_is_temporal": x_is_temporal,
                            "timeUnit": enc_x.get("timeUnit"),
                            "data_values": data_values,
                        },
                    )
                )
                continue

            # 3+ columns: multi-series
            # Detect header row by non-numeric cells in row 0 (excluding first column)
            row0_non_numeric = sum(1 for c in range(1, cols) if not is_numeric(grid.get((0, c), ''))) if rows > 0 else 0
            has_header = row0_non_numeric >= max(1, (cols - 1) // 2)

            start_row = 1 if has_header else 0
            x_title = grid.get((0, 0), "x") if has_header else "x"

            # Check temporal nature and granularity from sample of x
            x_samples = [grid.get((r, 0), '') for r in range(start_row, min(rows, start_row + 6))]
            x_is_temporal = sum(1 for xv in x_samples if looks_like_date(xv)) / max(1, len(x_samples)) >= 0.7
            gran_samples: List[str] = []

            series_names: List[str] = []
            data_values: List[Dict[str, Any]] = []
            y_numeric_count = 0
            y_total_count = 0
            percent_like_values = 0

            for c in range(1, cols):
                name = grid.get((0, c), f"Series {c}") if has_header else f"Series {c}"
                series_names.append(name)
                for r in range(start_row, rows):
                    xv = grid.get((r, 0), '')
                    if x_is_temporal:
                        iso, gran = normalize_date_and_granularity(xv)
                        if gran:
                            gran_samples.append(gran)
                        xv_out = iso or xv
                    else:
                        xv_out = xv
                    yv_raw = grid.get((r, c), '')
                    num = try_parse_number(yv_raw)
                    if num is not None:
                        y_numeric_count += 1
                        if isinstance(yv_raw, str) and yv_raw.strip().endswith('%'):
                            percent_like_values += 1
                        yv = num
                    else:
                        yv = yv_raw
                    y_total_count += 1
                    data_values.append({"x": xv_out, "series": name, "y": yv})

            x_type = "temporal" if x_is_temporal else "ordinal"
            dominant_gran = majority(gran_samples)
            time_unit_map = {"year": "year", "yearmonth": "yearmonth", "date": "yearmonthdate"}
            axis_format_map = {"year": "%Y", "yearmonth": "%b %Y", "date": "%d %b %Y"}

            # Mark & stacking
            y_numeric_ratio = y_numeric_count / max(1, y_total_count)
            y_is_percentage = percent_like_values / max(1, y_total_count) >= 0.7
            if x_is_temporal:
                mark = "line"
                stack = None
            else:
                # categorical x
                if y_numeric_ratio >= 0.7:
                    mark = "bar"
                    stack = "normalize" if y_is_percentage else "zero"
                else:
                    mark = "line"
                    stack = None

            spec = {"mark": mark, "encoding": {}}
            enc_x: Dict[str, Any] = {"field": "x", "type": x_type, "axis": {"title": x_title}}
            if x_is_temporal and dominant_gran:
                enc_x["timeUnit"] = time_unit_map.get(dominant_gran, "yearmonthdate")
                enc_x["axis"]["format"] = axis_format_map.get(dominant_gran, "%d %b %Y")
            enc_y: Dict[str, Any] = {"field": "y", "type": "quantitative", "axis": {"title": "Value"}}
            if stack:
                enc_y["stack"] = stack
            spec["encoding"]["x"] = enc_x
            spec["encoding"]["y"] = enc_y
            spec["encoding"]["color"] = {"field": "series", "type": "nominal"}

            artifacts.append(
                ChartArtifact(
                    id=str(uuid.uuid4()),
                    bbox=BBox(x=0, y=0, w=0, h=0),
                    spec=spec,
                    meta={
                        "source": "table_to_chart_multi_v2",
                        "series": series_names,
                        "x_is_temporal": x_is_temporal,
                        "timeUnit": enc_x.get("timeUnit"),
                        "stack": stack,
                        "data_values": data_values,
                    },
                )
            )

        return artifacts
