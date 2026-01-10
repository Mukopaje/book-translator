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
import re
import numpy as np

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

        # Keep rows that look like table rows - REQUIRE at least 2 items per row for table structure
        # Single-item rows are usually just regular text lines, not table rows
        table_rows = [sorted(r, key=lambda b: int(b.get("x", 0))) for r in rows if len(r) >= 2]
        
        if len(table_rows) < 3:
            # Need at least 3 rows with 2+ columns to be considered a table
            print(f"[TableAgent] Table vetoed: insufficient rows with multiple columns ({len(table_rows)} < 3).")
            return []
        
        # Check if this looks like a table: either many rows or clear multi-column structure
        # Technical manuals often have 2-column lists that aren't really tables.
        # We want to be more conservative.
        multi_col_rows = [r for r in table_rows if len(r) >= 3]
        two_col_rows = [r for r in table_rows if len(r) == 2]
        
        # Stricter criteria: require either:
        # 1. At least 4 rows with 3+ columns each (clear table structure)
        # 2. At least 6 rows with 2+ columns AND at least 2 rows with 3+ columns (structured data)
        # 3. At least 10 rows with 2+ columns (long lists might be tables, but be cautious)
        is_likely_table = False
        if len(multi_col_rows) >= 4:
            is_likely_table = True
        elif len(table_rows) >= 6 and len(multi_col_rows) >= 2:
            is_likely_table = True
        elif len(table_rows) >= 10 and len(multi_col_rows) >= 1:
            # For long lists, require at least one row with 3+ columns to avoid false positives
            is_likely_table = True
            
        # Final sanity check: if it's mostly empty (noise) OR looks like a list, reject it
        if is_likely_table:
            # Estimate density
            if len([r for r in table_rows if len(r) > 1]) < len(table_rows) * 0.4:
                # If less than 40% of rows have more than one item, it's likely a list
                print("[TableAgent] Table vetoed: low multi-item row density (likely a list).")
                is_likely_table = False
            else:
                # Count list markers to detect component lists
                # BUT: Table of Contents (TOC) pages have list markers AND are valid tables
                list_marker_count = 0
                cell_count = 0
                for row in table_rows:
                    for box in row:
                        cell_count += 1
                        if self._is_list_marker(box.get("text", "")):
                            list_marker_count += 1
                
                # Only veto if high list marker density AND it's a narrow single-column structure
                # TOCs typically have 2+ columns (sections on left, page numbers on right)
                avg_cols_per_row = sum(len(r) for r in table_rows) / len(table_rows) if table_rows else 0
                
                if cell_count > 0 and (list_marker_count / cell_count) > 0.3:
                    if avg_cols_per_row < 2.5:
                        # Single-column numbered list - not a table
                        print(f"[TableAgent] Table vetoed: high list marker density ({list_marker_count}/{cell_count}) in narrow structure.")
                        is_likely_table = False
                    else:
                        # Multi-column structure with numbering (likely a TOC) - keep it
                        print(f"[TableAgent] Multi-column structure with numbering detected (likely TOC), keeping as table.")
        
        if not is_likely_table:
            # Not enough structured content to justify a table layout
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
        
        # SPECIAL CASE: Table of Contents detection
        # TOCs have many list markers and often >8 columns (due to scattered page numbers)
        # They render better as formatted text than as tables
        list_marker_ratio = 0
        if cell_count > 0:
            list_marker_ratio = list_marker_count / cell_count
        
        if list_marker_ratio > 0.4 and len(col_centroids) > 8:
            print(f"[TableAgent] Table vetoed: high list marker density ({list_marker_ratio:.2f}) with many columns ({len(col_centroids)}) suggests Table of Contents - should render as formatted text, not table.")
            return []
        
        num_cols = max(1, min(len(col_centroids), 12))  # Support up to 12 columns (ReportLab stability)
        col_centroids = col_centroids[:num_cols] # Ensure centroids match the cap

        if num_cols < 3:
            print(f"[TableAgent] Table vetoed: too few columns ({num_cols}) for spatial heuristic.")
            return []

        # Skip the expensive OpenCV line detection - it's too slow for large tables
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

        # --- VISUAL CONTENT CHECK (DIAGRAM vs TABLE DETECTION) ---
        # If the region has significant visual content (lines, shapes), it's a diagram, not a table
        try:
            import cv2
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                # Extract the bounding box region
                min_x = min(int(b.get("x", 0)) for b in boxes)
                min_y = min(int(b.get("y", 0)) for b in boxes)
                max_x = max(int(b.get("x", 0)) + int(b.get("w", 0)) for b in boxes)
                max_y = max(int(b.get("y", 0)) + int(b.get("h", 0)) for b in boxes)
                
                # Ensure bounds are valid
                min_x = max(0, min_x)
                min_y = max(0, min_y)
                max_x = min(img.shape[1], max_x)
                max_y = min(img.shape[0], max_y)
                
                if max_x > min_x and max_y > min_y:
                    region = img[min_y:max_y, min_x:max_x]
                    
                    # Edge detection to find visual content (diagrams have many edges)
                    edges = cv2.Canny(region, 50, 150)
                    edge_density = np.count_nonzero(edges) / (region.shape[0] * region.shape[1])
                    
                    # Diagrams typically have >3% edge density from shapes and lines
                    if edge_density > 0.03:
                        print(f"[TableAgent] Table vetoed: high edge density ({edge_density:.3f}) suggests this is a DIAGRAM with text labels, not a table.")
                        return []
        except Exception as e:
            print(f"[TableAgent] Warning: Visual content check failed: {e}")

        # --- STRICTOR VETO LOGIC (GHOST TABLE PROTECTION) ---
        # Use logical cell count rather than raw boxes for density
        total_potential_cells = len(table_rows) * num_cols
        logical_density = len(all_cells) / total_potential_cells if total_potential_cells > 0 else 0
        avg_cells_per_row = len(all_cells) / len(table_rows) if table_rows else 0
        
        # NEW: Check total text content and meaningful content
        total_text_length = sum(len(cell.text) for cell in all_cells)
        avg_text_per_cell = total_text_length / len(all_cells) if all_cells else 0
        
        # Count cells with meaningful text (more than just numbers/symbols)
        meaningful_cells = sum(1 for cell in all_cells if len(cell.text.strip()) > 3 and any(c.isalpha() for c in cell.text))
        meaningful_ratio = meaningful_cells / len(all_cells) if all_cells else 0
        
        print(f"[TableAgent] Logical Veto Check: density={logical_density:.2f}, avg_cells={avg_cells_per_row:.2f}, rows={len(table_rows)}, cols={num_cols}, cells={len(all_cells)}, avg_text_len={avg_text_per_cell:.1f}, meaningful_ratio={meaningful_ratio:.2f}")
            
        # STRICTER: Require higher density for tables
        if logical_density < 0.25:
            print(f"[TableAgent] Table vetoed: low logical grid density ({logical_density:.2f} < 0.25).")
            return []
            
        # STRICTER: Require more cells per row on average
        if avg_cells_per_row < 1.5:
            print(f"[TableAgent] Table vetoed: low average logical cells per row ({avg_cells_per_row:.2f} < 1.5).")
            return []
        
        # STRICTER VETO: Reject tables with very short or meaningless text
        if avg_text_per_cell < 3.0 and total_text_length < 50:
            print(f"[TableAgent] Table vetoed: insufficient text content (avg={avg_text_per_cell:.1f} chars/cell, total={total_text_length} chars).")
            return []
        
        # NEW VETO: Require at least 30% of cells to have meaningful text (not just numbers/symbols)
        if meaningful_ratio < 0.3:
            print(f"[TableAgent] Table vetoed: too few meaningful cells ({meaningful_ratio:.2f} < 0.3) - likely OCR noise or diagram labels.")
            return []

        # Create a single TableArtifact
        min_x = min(int(b.get("x", 0)) for b in boxes)
        min_y = min(int(b.get("y", 0)) for b in boxes)
        max_r = max(int(b.get("x", 0)) + int(b.get("w", 0)) for b in boxes)
        max_b = max(int(b.get("y", 0)) + int(b.get("h", 0)) for b in boxes)
        
        table_bbox = BBox(x=min_x, y=min_y, w=max_r - min_x, h=max_b - min_y)

        # Translate cells if translator is provided
        if translator:
            print(f"[TableAgent] Translating {len(all_cells)} table cells...")
            for i, cell in enumerate(all_cells):
                if cell.text and cell.text.strip():
                    try:
                        # Simple context for table cells
                        ctx = "table cell"
                        if book_context:
                            ctx = f"{ctx}. Book Context: {book_context}"
                            
                        # If cell is just a number or symbol, skip translation
                        # (Translator might do this check, but good to check here too)
                        stripped = cell.text.strip()
                        if any(c.isalpha() for c in stripped):
                            translation = translator.translate_text(
                                stripped,
                                context=ctx,
                                source_lang='ja',
                                target_lang='en'
                            )
                            cell.translation = translation
                        else:
                             cell.translation = stripped
                    except Exception as e:
                        print(f"  Warning: Cell translation failed: {e}")
                        cell.translation = cell.text

        box_ids = [b.get("id") for b in boxes if id(b) in assigned_boxes and b.get("id")]
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
        
        # Translate cells if translator is provided
        if translator:
             print(f"[TableAgent] Translating {sum(len(r) for r in grid)} table cells (delimiter method)...")

        for r_idx, row in enumerate(grid):
            for c_idx, cell_text in enumerate(row):
                translation = None
                if cell_text and cell_text.strip() and translator:
                    try:
                        ctx = "table cell"
                        if book_context:
                            ctx = f"{ctx}. Book Context: {book_context}"
                        
                        if any(c.isalpha() for c in cell_text):
                            translation = translator.translate_text(
                                cell_text, 
                                context=ctx,
                                source_lang='ja',
                                target_lang='en'
                            )
                        else:
                            translation = cell_text
                    except Exception as e:
                        print(f"  Warning: Cell translation failed: {e}")
                        translation = cell_text
                
                all_cells.append(TableCell(
                    row=r_idx, 
                    col=c_idx, 
                    text=cell_text if cell_text else "", 
                    translation=translation 
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

    def _is_list_marker(self, text: str) -> bool:
        """Check if text looks like a structured list marker (e.g. (1), 1., [A])"""
        if not text:
            return False
        clean = text.strip()
        # Fuzzy matching: marker at the START of the string (no $ anchor)
        patterns = [
            r'^\(\d{1,3}\)',  # (1), (2)
            r'^\d{1,3}\.',    # 1., 2.
            r'^\[\d{1,3}\]',  # [1], [2]
            r'^\([a-zA-Z]\)',  # (a), (b)
            r'^[a-zA-Z]\.',    # a., b.
            r'^\[[a-zA-Z]\]',  # [A], [B]
            r'^\d{1,3}(?!\d)'  # 1, 2 (bare number, not start of larger number)
        ]
        for p in patterns:
            if re.match(p, clean):
                return True
        return False
