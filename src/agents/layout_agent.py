"""
Layout Analysis Agent using Gemini Vision
Uses AI to perform semantic document layout analysis instead of heuristics.
"""
import os
import json
import base64
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from PIL import Image

class LayoutAgent:
    """
    Agent responsible for analyzing page layout using Vision Models.
    Identifies regions: Diagrams, Text Blocks, Tables, Headers/Footers.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("Warning: GOOGLE_API_KEY/GEMINI_API_KEY not found. LayoutAgent will fail if called.")
        else:
            genai.configure(api_key=self.api_key)
            
        # Use the latest Pro model for best layout understanding (text/diagram distinction)
        self.model_name = "gemini-3-pro-preview"
        
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def detect_layout(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze the page and return structured layout regions.
        
        Returns dict with keys:
        - regions: List of {type, box_2d, content_description}
        - status: success/failure
        """
        try:
            print(f"[LayoutAgent] Analyzing layout for {os.path.basename(image_path)} using {self.model_name}...")
            
            # Prepare the prompt
            prompt = """
            You are a Document Layout Analysis expert. Analyze this technical manual page.

            Identify and return bounding boxes for the following semantic regions:
            1. "text_block": Main prose text (paragraphs, lists). NOT labels inside diagrams.
            2. "technical_diagram": Engineering drawings, schematics, cross-sections (e.g. engine parts). IMPORTANT: Include ALL associated labels, callouts, and keys/legends within this box.
            3. "chart": Data visualization, graphs with X/Y axes, line plots, bar charts. IMPORTANT: Include the axes labels and titles within the box.
            4. "table": Structured data tables with rows/columns.
            5. "header_footer": Page numbers, running titles.
            6. "caption": Text explicitly describing a figure or table (usually starts with "Fig" or "Table").

            CRITICAL:
            - Distinguish between "technical_diagram" (schematic) and "chart" (data plot).
            - Distinguish between "text_block" (prose) and "diagram labels" (short text pointing to parts).
            - Diagram labels MUST be included inside the "technical_diagram" or "chart" region box. Do NOT mark them as "text_block".
            - If a page is mostly a large diagram with many labels, return one large "technical_diagram" region that covers them all.

            MULTI-COLUMN LAYOUT DETECTION:
            - Determine if the page uses a multi-column layout (e.g., 2-column, 3-column)
            - If columns exist, assign each region a "column" number (1, 2, 3, etc.) from left to right
            - The "column" field indicates which column the region belongs to
            - Single-column pages should use column=1 for all regions
            - Regions that span multiple columns (like full-width diagrams or tables) should use column=0

            READING ORDER:
            - Assign a "reading_order" number to each region (1, 2, 3, etc.)
            - For multi-column layouts: Process left column top-to-bottom, then right column top-to-bottom
            - Example 2-column: Left col regions get order 1,2,3, then right col gets 4,5,6
            - For single-column: Simply top-to-bottom (1, 2, 3, etc.)

            PAGE NUMBER EXTRACTION:
            - Look for the page number on this page. It will typically be:
              * A standalone number at the top or bottom of the page
              * The FIRST number you see at the very top (before main content)
              * OR the LAST number at the very bottom (after main content)
              * It might be surrounded by dashes (e.g., "- 123 -") or standalone
            - If you find a page number, include it in the "page_number" field
            - If no page number is visible, set "page_number" to null

            Output strictly valid JSON with this structure:
            {
                "page_number": 123 | null,
                "layout_columns": 1 | 2 | 3,  // Number of columns detected
                "regions": [
                    {
                        "type": "technical_diagram" | "chart" | "text_block" | "table" | "header_footer" | "caption",
                        "box_2d": [ymin, xmin, ymax, xmax],  // Normalized coordinates (0-1000)
                        "column": 0 | 1 | 2 | 3,  // Which column (0=spans all, 1=left, 2=middle/right, etc.)
                        "reading_order": 1,  // Order to read this region (1, 2, 3, ...)
                        "confidence": 0-1.0
                    }
                ]
            }
            """
            
            # Load image
            img = Image.open(image_path)
            
            # Call Gemini
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([
                prompt,
                img
            ], generation_config={"response_mime_type": "application/json"})
            
            # Parse response
            try:
                result = json.loads(response.text)

                # Extract page number and layout info
                page_number = result.get("page_number")
                layout_columns = result.get("layout_columns", 1)

                if page_number:
                    print(f"[LayoutAgent] Detected page number: {page_number}")
                if layout_columns > 1:
                    print(f"[LayoutAgent] Detected {layout_columns}-column layout")

                # Convert normalized coordinates (0-1000) to pixel coordinates
                width, height = img.size
                regions = result.get("regions", [])

                converted_regions = []
                for r in regions:
                    # Gemini returns [ymin, xmin, ymax, xmax] in 0-1000 scale
                    box = r.get("box_2d", [])
                    if len(box) == 4:
                        ymin, xmin, ymax, xmax = box
                        pixel_box = {
                            "y": int(ymin / 1000 * height),
                            "x": int(xmin / 1000 * width),
                            "h": int((ymax - ymin) / 1000 * height),
                            "w": int((xmax - xmin) / 1000 * width)
                        }
                        r["box_pixel"] = pixel_box
                        converted_regions.append(r)

                # Sort regions by reading order if provided
                if all('reading_order' in r for r in converted_regions):
                    converted_regions.sort(key=lambda r: r.get('reading_order', 999))
                    print(f"[LayoutAgent] Detected {len(converted_regions)} regions (sorted by reading order).")
                else:
                    print(f"[LayoutAgent] Detected {len(converted_regions)} regions.")

                for r in converted_regions:
                    column_info = f", col={r.get('column', 1)}" if layout_columns > 1 else ""
                    order_info = f", order={r.get('reading_order', '?')}" if 'reading_order' in r else ""
                    print(f"  - {r['type']}{column_info}{order_info}: {r['box_pixel']}")

                return {
                    "success": True,
                    "regions": converted_regions,
                    "page_number": page_number,
                    "layout_columns": layout_columns
                }
                
            except json.JSONDecodeError as e:
                print(f"[LayoutAgent] Error parsing JSON response: {e}")
                print(f"Response text: {response.text}")
                return {"success": False, "error": "Invalid JSON response"}
                
        except Exception as e:
            print(f"[LayoutAgent] Layout analysis failed: {e}")
            return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # Test script
    import sys
    if len(sys.argv) > 1:
        agent = LayoutAgent()
        res = agent.detect_layout(sys.argv[1])
        print(json.dumps(res, indent=2))
