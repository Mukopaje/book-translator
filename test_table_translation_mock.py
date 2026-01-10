
import sys
import os
sys.path.insert(0, os.path.abspath("src"))

from agents.table_agent import TableAgent
from unittest.mock import MagicMock

def test_table_translation():
    print("Testing TableAgent translation logic...")
    
    # Mock translator
    translator = MagicMock()
    translator.translate_text.side_effect = lambda text, **kwargs: f"[EN]{text}"
    
    # Mock OCR boxes (simple 2x2 grid)
    # Row 1: "Header1" | "Header2"
    # Row 2: "Val1"    | "Val2"
    boxes = [
        {'text': 'Header1', 'x': 10, 'y': 10, 'w': 50, 'h': 20},
        {'text': 'Header2', 'x': 70, 'y': 10, 'w': 50, 'h': 20},
        {'text': 'Header3', 'x': 130, 'y': 10, 'w': 50, 'h': 20},
        {'text': 'Val1', 'x': 10, 'y': 40, 'w': 50, 'h': 20},
        {'text': 'Val2', 'x': 70, 'y': 40, 'w': 50, 'h': 20},
        {'text': 'Val3', 'x': 130, 'y': 40, 'w': 50, 'h': 20},
    ]
    
    agent = TableAgent()
    artifacts = agent.detect_and_extract(
        image_path="dummy.jpg",
        ocr_boxes=boxes,
        translator=translator,
        book_context="test context"
    )
    
    if not artifacts:
        print("FAILED: No table detected")
        return
        
    table = artifacts[0]
    print(f"Detected table with {table.rows} rows and {table.cols} cols")
    
    # Check translations
    for cell in table.cells:
        print(f"Cell ({cell.row},{cell.col}): '{cell.text}' -> '{cell.translation}'")
        if cell.translation != f"[EN]{cell.text}":
            print("FAILED: Translation mismatch")
            return

    print("SUCCESS: Table translation verification passed")

if __name__ == "__main__":
    test_table_translation()
