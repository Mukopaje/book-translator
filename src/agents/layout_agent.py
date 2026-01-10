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
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            print("Warning: GOOGLE_API_KEY not found. LayoutAgent will fail if called.")
        else:
            genai.configure(api_key=self.api_key)
            
        # Use the latest Flash model for speed and vision capabilities
        self.model_name = "gemini-2.0-flash-exp" 
        
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
            
            Output strictly valid JSON with this structure:
            {
                "regions": [
                    {
                        "type": "technical_diagram" | "chart" | "text_block" | "table" | "header_footer" | "caption",
                        "box_2d": [ymin, xmin, ymax, xmax],  // Normalized coordinates (0-1000)
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
                
                print(f"[LayoutAgent] Detected {len(converted_regions)} regions.")
                for r in converted_regions:
                    print(f"  - {r['type']}: {r['box_pixel']}")
                    
                return {"success": True, "regions": converted_regions}
                
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
