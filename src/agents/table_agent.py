from typing import Any, Dict, List, Optional, Tuple
import uuid
import re
import numpy as np
import os
import base64
import json
import concurrent.futures
from google import genai
from PIL import Image

from artifacts.schemas import BBox, TableArtifact, TableCell


class TableAgent:
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
        # Use 2.5 Flash (newest, reliable JSON output, good for complex tables)
        # Set TABLE_MODEL env var to override
        self.model_name = os.getenv("TABLE_MODEL", "gemini-2.5-flash")

    def extract_tables_with_ai(self, image_path: str, table_regions: List[Dict[str, Any]]) -> List[TableArtifact]:
        """
        Extract structured table data using Gemini Vision.
        Uses Smart Cropping:
        - If a table region is huge (>70% page), scans the full page to avoid fragmentation.
        - Otherwise, crops the image to the region (with padding) for higher resolution.
        """
        print(f"[TableAgent] Extracting tables with Smart Cropping...")
        artifacts = []
        full_image = Image.open(image_path)
        width, height = full_image.size
        page_area = width * height
        
        # 1. Strategy Selection
        use_full_page = False
        
        if not table_regions:
            print("[TableAgent] No regions provided. Fallback to full page scan.")
            use_full_page = True
        else:
            # Check if any region is "Huge"
            for region in table_regions:
                box = region.get('box_pixel') or self._get_pixel_box(region, width, height)
                area = box['w'] * box['h']
                if area > (page_area * 0.7):
                    print(f"[TableAgent] Huge table detected ({int(area/page_area*100)}% coverage). Using full page scan.")
                    use_full_page = True
                    break
        
        if use_full_page:
            return self._extract_from_image(full_image, is_full_page=True, parent_width=width, parent_height=height)
        
        # 2. Process Regions (Smart Cropping) in Parallel
        print(f"[TableAgent] Processing {len(table_regions)} table regions with padded crops (Parallel)...")
        
        def process_region(idx, region):
            try:
                box = region.get('box_pixel') or self._get_pixel_box(region, width, height)
                
                # Add Padding (50px) to ensure borders/headers aren't cut
                padding = 50
                x1 = max(0, box['x'] - padding)
                y1 = max(0, box['y'] - padding)
                x2 = min(width, box['x'] + box['w'] + padding)
                y2 = min(height, box['y'] + box['h'] + padding)
                
                # Avoid zero-size crops
                if x2 <= x1 or y2 <= y1:
                    print(f"  [TableAgent] Skipping invalid crop dimensions: {x1},{y1} to {x2},{y2}")
                    return []

                crop_img = full_image.crop((x1, y1, x2, y2))
                print(f"  [TableAgent] Region {idx+1}: Cropping to ({x1},{y1},{x2},{y2}) ({x2-x1}x{y2-y1})")
                
                # Extract
                return self._extract_from_image(
                    crop_img,
                    is_full_page=False,
                    offset_x=x1,
                    offset_y=y1,
                    parent_width=width,
                    parent_height=height
                )
            except Exception as e:
                print(f"  [TableAgent] Error processing region {idx+1}: {e}")
                return []

        # Use ThreadPoolExecutor for parallel processing
        # Max workers = 5 to avoid rate limits while maximizing speed
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_region, i, r) for i, r in enumerate(table_regions)]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    region_artifacts = future.result()
                    artifacts.extend(region_artifacts)
                except Exception as e:
                    print(f"  [TableAgent] Thread exception: {e}")
            
        return artifacts

    def _get_pixel_box(self, region: Dict[str, Any], width: int, height: int) -> Dict[str, int]:
        """Helper to get pixel box from region (handling 0-1000 norm or existing pixel box)."""
        if 'box_pixel' in region:
            return region['box_pixel']
        
        # Fallback to normalized box_2d
        box = region.get('box_2d', [0, 0, 1000, 1000])
        ymin, xmin, ymax, xmax = box
        return {
            "y": int(ymin / 1000 * height),
            "x": int(xmin / 1000 * width),
            "h": int((ymax - ymin) / 1000 * height),
            "w": int((xmax - xmin) / 1000 * width)
        }

    def _extract_from_image(self, image: Image.Image, is_full_page: bool, offset_x: int = 0, offset_y: int = 0, parent_width: int = 0, parent_height: int = 0) -> List[TableArtifact]:
        """Internal method to call Gemini on a specific image (full or crop)."""
        artifacts = []
        try:
            prompt = """
            Analyze this image and extract ALL data tables into a structured JSON format.
            
            CRITICAL INSTRUCTIONS:
            1. Find every table in the image.
            2. For each table, provide its Bounding Box ([ymin, xmin, ymax, xmax] in 0-1000 coordinates RELATIVE TO THIS IMAGE).
            3. EXTRACT EVERY SINGLE ROW. Do not skip any rows. Do not summarize.
            4. Scan the table from top to bottom and transcribe every row of data.
            5. Identify the headers correctly.
            6. TRANSLATE all Japanese text to English.
            7. Preserve all numbers and codes (e.g. 'CN1', 'DB32A') exactly.
            8. If a cell is empty or has a ditto mark ("), repeat the value from above or leave empty.
            
            Output JSON format:
            {
                "tables": [
                    {
                        "box_2d": [ymin, xmin, ymax, xmax],
                        "headers": ["Header 1", "Header 2"],
                        "rows": [
                            ["Row 1 Col 1", "Row 1 Col 2"],
                            ["Row 2 Col 1", "Row 2 Col 2"]
                        ]
                    }
                ]
            }
            """
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, image],
                config={"response_mime_type": "application/json"}
            )
            
            try:
                data = json.loads(response.text)
            except json.JSONDecodeError:
                # Retry once if JSON is malformed
                print(f"[TableAgent] Malformed JSON, retrying...")
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, image],
                    config={"response_mime_type": "application/json"}
                )
                data = json.loads(response.text)

            tables = data.get("tables", [])
            print(f"  [TableAgent] Gemini found {len(tables)} tables in this scan.")
            
            crop_width, crop_height = image.size
            
            for i, table_data in enumerate(tables):
                headers = table_data.get("headers", [])
                rows = table_data.get("rows", [])
                box_2d = table_data.get("box_2d", [0, 0, 1000, 1000])
                
                # Convert Local BBox (0-1000 relative to crop) to Global Pixels
                ymin, xmin, ymax, xmax = box_2d
                
                # Local pixels
                local_x = int(xmin / 1000 * crop_width)
                local_y = int(ymin / 1000 * crop_height)
                local_w = int((xmax - xmin) / 1000 * crop_width)
                local_h = int((ymax - ymin) / 1000 * crop_height)
                
                # Global pixels (add offsets)
                global_x = offset_x + local_x
                global_y = offset_y + local_y
                global_w = local_w
                global_h = local_h
                
                # Reconstruct full grid
                full_grid = [headers] + rows if headers else rows
                num_cols = max(len(r) for r in full_grid) if full_grid else 0
                num_rows = len(full_grid)
                
                cells = []
                for r_idx, row in enumerate(full_grid):
                    for c_idx, text in enumerate(row):
                        cells.append(TableCell(
                            row=r_idx,
                            col=c_idx,
                            text=str(text),
                            translation=str(text)
                        ))
                
                artifact = TableArtifact(
                    id=str(uuid.uuid4()),
                    bbox=BBox(x=global_x, y=global_y, w=global_w, h=global_h),
                    rows=num_rows,
                    cols=num_cols,
                    cells=cells,
                    meta={"detector": "gemini_vision_smart_crop", "source": "ai_extraction", "is_crop": not is_full_page}
                )
                artifacts.append(artifact)
                print(f"    + Extracted table: {num_rows} rows, {num_cols} cols at Global Y={global_y}")

        except Exception as e:
            print(f"[TableAgent] Error extracting tables: {e}")
            import traceback
            traceback.print_exc()
            
        return artifacts

    def detect_and_extract(
        self,
        image_path: str,
        ocr_boxes: List[Dict[str, Any]],
        translator: Any = None,
        book_context: Optional[str] = None,
    ) -> List[TableArtifact]:
        """Legacy spatial detection (Fallback)"""
        # ... (Legacy code omitted for brevity, but method signature kept for interface compatibility)
        return []

    def _is_list_marker(self, text: str) -> bool:
        return False
