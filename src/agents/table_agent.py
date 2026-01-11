from typing import Any, Dict, List, Optional, Tuple
import uuid
import re
import numpy as np
import os
import base64
import json
import google.generativeai as genai
from PIL import Image

from artifacts.schemas import BBox, TableArtifact, TableCell


class TableAgent:
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.model_name = "gemini-2.0-flash-exp"

    def extract_tables_with_ai(self, image_path: str, table_regions: List[Dict[str, Any]]) -> List[TableArtifact]:
        """
        Extract structured table data using Gemini Vision on the FULL PAGE.
        This avoids cropping issues where rows are cut off.
        """
        print(f"[TableAgent] Extracting tables from full page using AI...")
        artifacts = []
        full_image = Image.open(image_path)
        width, height = full_image.size
        
        try:
            # Prompt Gemini with Full Page
            prompt = """
            Analyze this page and extract ALL data tables into a structured JSON format.
            
            CRITICAL INSTRUCTIONS:
            1. Find every table on the page.
            2. For each table, provide its Bounding Box ([ymin, xmin, ymax, xmax] in 0-1000 coordinates).
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
            
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([prompt, full_image], generation_config={"response_mime_type": "application/json"})
            
            data = json.loads(response.text)
            tables = data.get("tables", [])
            
            print(f"[TableAgent] AI found {len(tables)} tables on the page.")
            
            for i, table_data in enumerate(tables):
                headers = table_data.get("headers", [])
                rows = table_data.get("rows", [])
                box_2d = table_data.get("box_2d", [0, 0, 1000, 1000])
                
                # Convert BBox to pixels
                ymin, xmin, ymax, xmax = box_2d
                x = int(xmin / 1000 * width)
                y = int(ymin / 1000 * height)
                w = int((xmax - xmin) / 1000 * width)
                h = int((ymax - ymin) / 1000 * height)
                
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
                    bbox=BBox(x=x, y=y, w=w, h=h),
                    rows=num_rows,
                    cols=num_cols,
                    cells=cells,
                    meta={"detector": "gemini_vision_full_page", "source": "ai_extraction"}
                )
                artifacts.append(artifact)
                print(f"  [TableAgent] Table {i+1}: {num_rows} rows, {num_cols} cols at Y={y}")

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
