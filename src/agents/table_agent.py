"""
TableAgent: detects tables and extracts structured cells.

Heuristic MVP:
- Clusters OCR boxes into rows by vertical proximity
- Derives columns by clustering x positions across rows
- Emits a single TableArtifact per detected grid with translated cell text
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import uuid

from artifacts.schemas import BBox, TableArtifact, TableCell


class TableAgent:
    def __init__(self) -> None:
        pass

    def detect_and_extract(
        self,
        image_path: str,
        ocr_boxes: List[Dict[str, Any]],
        translator: Any = None,
        book_context: Optional[str] = None,
    ) -> List[TableArtifact]:
        """
        Detect tables and extract cells as structured artifacts.

        Args:
            image_path: Path to the page image
            ocr_boxes: OCR text boxes from the page
            translator: Optional translator instance to translate cell text
            book_context: Optional global context (e.g. manual type)

        Returns:
            List of TableArtifact.
        """
        text = " ".join([b.get("text", "") for b in ocr_boxes])
        pipe_count = text.count('|')
        print(f"[TableAgent] Detected {pipe_count} pipe characters in page text.")
        
        # Use delimiter-based logic if enough pipes are found, otherwise fallback
        if pipe_count > 5:  # Lowered threshold to 5
            try:
                # This logic is more robust for pipe-delimited tables
                result = self._detect_with_delimiters(image_path, ocr_boxes, translator, book_context)
                # If delimiter method returns empty (quality check failed), fall back to spatial
                if result:
                    return result
                else:
                    print("[TableAgent] Delimiter method returned empty, falling back to spatial method.")
            except Exception as e:
                print(f"[TableAgent] Delimiter-based detection failed: {e}. Falling back to spatial method.")
                # Fallback to spatial method if delimiter logic fails
                pass
        
        # Original spatial detection logic starts here
        print("[TableAgent] Using spatial (heuristic) detection logic...")
        boxes = [b for b in ocr_boxes if b.get("text", "").strip()]
        
        if not boxes:
            return []

        # Basic stats
        hs = [max(1, int(b.get("h", 1))) for b in boxes]
        ws = [max(1, int(b.get("w", 1))) for b in boxes]
        median_h = sorted(hs)[len(hs)//2]
        median_w = sorted(ws)[len(ws)//2]

        # 1) Cluster into rows by vertical proximity
        rows: List[List[Dict[str, Any]]] = []
        sorted_by_y = sorted(boxes, key=lambda b: (int(b.get("y", 0)), int(b.get("x", 0))))
        row_thresh = max(12, int(median_h * 0.8))  # More generous threshold for complex tables
        for b in sorted_by_y:
            by = int(b.get("y", 0))
            placed = False
            for row in rows:
                # Compare to average y position of row elements for better alignment
                avg_y = sum(int(bb.get("y", 0)) for bb in row) // len(row)
                if abs(by - avg_y) <= row_thresh:
                    row.append(b)
                    placed = True
                    break
            if not placed:
                rows.append([b])

        # Keep rows that look like table rows (>= 2 items)
        # Accept single-column tables with >= 2 rows OR multi-column tables
        table_rows = [sorted(r, key=lambda b: int(b.get("x", 0))) for r in rows if len(r) >= 1]
        
        # Check if this looks like a table: either many rows or clear multi-column structure
        multi_col_rows = [r for r in table_rows if len(r) >= 3]
        is_likely_table = len(multi_col_rows) >= 2 or len(table_rows) >= 4
        
        if not is_likely_table:
            # Not enough structured content
            return []

        # 2) Derive columns by clustering x centers across rows
        x_centers: List[int] = []
        for r in table_rows:
            for b in r:
                x_centers.append(int(b.get("x", 0)) + int(b.get("w", 0)) // 2)
        x_centers.sort()
        col_tol = max(15, int(median_w * 0.6))  # More tolerant for tight columns
        col_centroids: List[int] = []
        for xc in x_centers:
            if not col_centroids or abs(xc - col_centroids[-1]) > col_tol:
                col_centroids.append(xc)
            else:
                # average into last cluster
                col_centroids[-1] = int((col_centroids[-1] + xc) / 2)
        num_cols = max(1, min(len(col_centroids), 24))  # Support up to 24 columns

        # Skip the expensive OpenCV line detection - it's too slow for large tables
        # The clustering logic above is sufficient
        print(f"[TableAgent] Using {num_cols} columns from text clustering (skipping edge detection for speed).")

        # 3) Build grid cells by mapping boxes to nearest column centroid
        all_cells: List[TableCell] = []
        
        # Keep track of boxes that are assigned to a cell
        assigned_boxes = set()

        for r_idx, row_boxes in enumerate(table_rows):
            for c_idx, centroid in enumerate(col_centroids):
                # Find all boxes in this row that belong to this column
                cell_boxes = []
                for box in row_boxes:
                    box_center_x = int(box.get("x", 0)) + int(box.get("w", 0)) // 2
                    # Assign box to the closest column centroid
                    if abs(box_center_x - centroid) < col_tol:
                        cell_boxes.append(box)
                        assigned_boxes.add(id(box))

                # Combine text from all boxes in the cell
                # Sort by x-coordinate to maintain original order
                cell_boxes.sort(key=lambda b: int(b.get("x", 0)))
                cell_text = " ".join([b.get("text", "") for b in cell_boxes]).strip()

                if cell_text:
                    all_cells.append(TableCell(
                        row=r_idx,
                        col=c_idx,
                        text=cell_text,
                        translation=None # Will be translated during PDF rendering
                    ))

        # Heuristic for merged cells: check for unassigned boxes that span multiple columns
        unassigned_boxes = [b for b in boxes if id(b) not in assigned_boxes]
        for box in unassigned_boxes:
            box_center_x = int(box.get("x", 0)) + int(box.get("w", 0)) // 2
            
            # Find which row this box belongs to (if any)
            for r_idx, row_boxes in enumerate(table_rows):
                if id(box) in [id(b) for b in row_boxes]:
                    # Find which column it starts in
                    start_col = -1
                    for c_idx, centroid in enumerate(col_centroids):
                        if abs(box_center_x - centroid) < col_tol:
                            start_col = c_idx
                            break
                    
                    if start_col != -1:
                        all_cells.append(TableCell(
                            row=r_idx,
                            col=start_col,
                            text=box.get("text", "").strip(),
                            translation=None
                        ))
                    break

        if not all_cells:
            return []

        # Create a single TableArtifact
        min_x = min(int(b.get("x", 0)) for b in boxes)
        min_y = min(int(b.get("y", 0)) for b in boxes)
        max_r = max(int(b.get("x", 0)) + int(b.get("w", 0)) for b in boxes)
        max_b = max(int(b.get("y", 0)) + int(b.get("h", 0)) for b in boxes)
        
        table_bbox = BBox(x=min_x, y=min_y, w=max_r - min_x, h=max_b - min_y)

        box_ids = [b.get("id") for b in assigned_boxes if b.get("id")]
        artifact = TableArtifact(
            id=str(uuid.uuid4()),
            bbox=table_bbox,
            rows=len(table_rows),
            cols=num_cols,
            cells=all_cells,
            meta={
                "detector": "spatial_heuristic_v3",
                "source": image_path,
                "box_ids": box_ids,
            },
        )
        
        print(f"[TableAgent] Created table artifact with {len(table_rows)} rows, {num_cols} cols, and {len(all_cells)} cells.")

        return [artifact]

    def _detect_with_delimiters(
        self,
        image_path: str,
        ocr_boxes: List[Dict[str, Any]],
        translator: Any,
        book_context: Optional[str]
    ) -> List[TableArtifact]:
        """
        Detects tables using '|' delimiters to define columns.
        """
        print("[TableAgent] Using new delimiter-based detection logic...")
        boxes = [b for b in ocr_boxes if b.get("text", "").strip()]
        if not boxes:
            return []

        # 1. Cluster into rows by vertical proximity
        hs = [max(1, int(b.get("h", 1))) for b in boxes]
        median_h = sorted(hs)[len(hs)//2]
        rows: List[List[Dict[str, Any]]] = []
        sorted_by_y = sorted(boxes, key=lambda b: (int(b.get("y", 0)), int(b.get("x", 0))))
        row_thresh = max(12, int(median_h * 0.8))
        for b in sorted_by_y:
            by = int(b.get("y", 0))
            placed = False
            for row in rows:
                avg_y = sum(int(bb.get("y", 0)) for bb in row) // len(row)
                if abs(by - avg_y) <= row_thresh:
                    row.append(b)
                    placed = True
                    break
            if not placed:
                rows.append([b])
        
        print(f"[TableAgent] Detected {len(rows)} potential rows.")
        table_rows = [sorted(r, key=lambda b: int(b.get("x", 0))) for r in rows if len(r) >= 1]

        # 2. Process rows to create a grid using dividers
        grid: List[List[str]] = []
        processed_boxes: List[Dict[str, Any]] = []

        for i, row in enumerate(table_rows):
            dividers = sorted([b for b in row if b.get("text", "").strip() == '|'], key=lambda b: int(b.get("x", 0)))
            print(f"[TableAgent] Row {i+1}: Found {len(dividers)} dividers.")
            content_boxes = [b for b in row if b.get("text", "").strip() != '|']
            
            if not dividers:
                # If a row has no dividers, treat it as a single cell or skip it
                # For simplicity, we'll make it a single cell if it has content
                if content_boxes:
                    full_text = " ".join(b.get("text", "") for b in content_boxes)
                    grid.append([full_text])
                    processed_boxes.extend(content_boxes)
                continue

            # Create column boundaries from dividers
            col_boundaries = [0]
            for j in range(len(dividers) - 1):
                # Midpoint between dividers
                mid_point = (int(dividers[j].get("x", 0)) + int(dividers[j+1].get("x", 0))) // 2
                col_boundaries.append(mid_point)
            
            # Use image width as the last boundary
            try:
                import cv2
                img = cv2.imread(image_path)
                page_width = img.shape[1]
                col_boundaries.append(page_width)
            except Exception:
                # Fallback if image read fails
                last_box_x = max(int(b.get("x", 0)) + int(b.get("w", 0)) for b in row) if row else 3000
                col_boundaries.append(last_box_x + 100)

            num_cols = len(dividers) + 1
            row_cells = [[] for _ in range(num_cols)]

            for box in content_boxes:
                box_center_x = int(box.get("x", 0)) + int(box.get("w", 0)) // 2
                
                # Find which column this box belongs to
                col_idx = 0
                for j in range(len(col_boundaries) - 1):
                    if col_boundaries[j] <= box_center_x < col_boundaries[j+1]:
                        col_idx = j
                        break
                else:
                    # If not found, assign to the last column it might fit in
                    if box_center_x >= col_boundaries[-1]:
                       col_idx = len(col_boundaries) - 2 # -2 because boundary list is one larger than cell list
                    
                if col_idx < len(row_cells):
                    row_cells[col_idx].append(box)

            # Join texts in each cell
            processed_row = []
            for cell_boxes in row_cells:
                cell_text = " ".join(sorted([b.get("text", "") for b in cell_boxes], key=lambda t: t)).strip()
                processed_row.append(cell_text)
                processed_boxes.extend(cell_boxes)
            
            grid.append(processed_row)

        if not grid:
            print("[TableAgent] No valid grid could be constructed from delimiters.")
            return []

        # 3. Quality check: If most rows have too few columns, fall back to spatial method
        max_cols = max(len(r) for r in grid) if grid else 0
        print(f"[TableAgent] Constructed a grid with {len(grid)} rows and {max_cols} columns.")
        
        # Check if the delimiter method produced poor results
        rows_with_data = sum(1 for row in grid if any(cell.strip() for cell in row))
        if max_cols < 4 and rows_with_data > 10:
            print(f"[TableAgent] Delimiter method produced only {max_cols} columns for {rows_with_data} data rows.")
            print("[TableAgent] This suggests OCR did not recognize pipe characters as text.")
            print("[TableAgent] Falling back to spatial detection method...")
            return []  # Return empty to trigger fallback in main detect_and_extract
        
        # Calculate bounding box from all OCR boxes used in the table
        all_boxes = [b for row in rows for b in row]
        if not all_boxes:
            print("[TableAgent] No bounding box could be calculated.")
            return []
        
        min_x = min(int(b.get("x", 0)) for b in all_boxes)
        min_y = min(int(b.get("y", 0)) for b in all_boxes)
        max_r = max(int(b.get("x", 0)) + int(b.get("w", 0)) for b in all_boxes)
        max_b = max(int(b.get("y", 0)) + int(b.get("h", 0)) for b in all_boxes)
        
        # Create a single table artifact with all cells
        all_cells: List[TableCell] = []
        for r_idx, row in enumerate(grid):
            for c_idx, cell_text in enumerate(row):
                # Skip translation during detection (too slow, will translate during PDF rendering)
                all_cells.append(TableCell(
                    row=r_idx, 
                    col=c_idx, 
                    text=cell_text if cell_text else "", 
                    translation=None  # Will be translated during PDF rendering
                ))
        
        # Create the table artifact
        table_bbox = BBox(x=min_x, y=min_y, w=max_r - min_x, h=max_b - min_y)
        
        box_ids = [b.get("id") for b in processed_boxes if b.get("id")]
        artifact = TableArtifact(
            id=str(uuid.uuid4()),
            bbox=table_bbox,
            rows=len(grid),
            cols=max_cols,
            cells=all_cells,
            meta={
                "detector": "delimiter_based",
                "source": image_path,
                "box_ids": box_ids,
            },
        )
        
        print(f"[TableAgent] Created table artifact with {len(grid)} rows and {max_cols} columns, {len(all_cells)} cells.")
        
        return [artifact]
