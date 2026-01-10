
import os
import sys
import shutil
from pathlib import Path

# Add src to path so imports work like in production
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PIL import Image, ImageDraw
from smart_layout_reconstructor import SmartLayoutReconstructor
from diagram_translator import DiagramTranslator
from translator import TextTranslator
from google_ocr import GoogleOCR

# Mock translator to avoid API costs during reproduction
class MockTranslator:
    def translate_text(self, text, context=None, source_lang=None, target_lang=None):
        return f"[TR] {text}"

# Mock OCR to avoid API permission issues and costs
class MockOCR:
    def extract_text_with_boxes(self, image_path):
        # Simulate a page structure:
        # 0-200: Top text
        # 200-600: Diagram (empty of paragraph text, but has labels)
        # 600-800: Bottom text
        
        boxes = []
        
        # Top paragraph
        boxes.append({'text': 'This is the top paragraph.', 'x': 50, 'y': 50, 'w': 500, 'h': 20})
        boxes.append({'text': 'It continues here.', 'x': 50, 'y': 80, 'w': 500, 'h': 20})
        
        # Diagram labels (inside the 200-600 gap)
        # Label 1: Simple label
        boxes.append({'text': 'Diagram Label A', 'x': 100, 'y': 300, 'w': 100, 'h': 20})
        # Label 2: Another label
        boxes.append({'text': 'Diagram Label B', 'x': 300, 'y': 400, 'w': 100, 'h': 20})
        
        # Bottom paragraph
        boxes.append({'text': 'This is the bottom paragraph.', 'x': 50, 'y': 650, 'w': 500, 'h': 20})
        
        return {
            'full_text': "This is the top paragraph.\nIt continues here.\nDiagram Label A\nDiagram Label B\nThis is the bottom paragraph.",
            'text_boxes': boxes
        }

def reproduce_issue():
    # Use the real image if it exists, otherwise create a dummy one
    image_path = "storage/originals/projects/2/originals/page_2_WhatsApp Image 2025-12-18 at 20.23.48.jpeg"
    if not os.path.exists(image_path):
        print(f"Image not found at {image_path}, creating dummy image...")
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        img = Image.new('RGB', (600, 850), color='white')
        d = ImageDraw.Draw(img)
        # Draw some "diagram" lines
        d.rectangle([100, 250, 500, 550], outline='black', width=2)
        d.line([100, 250, 500, 550], fill='black', width=2)
        # Draw some "text" to overlap
        d.text((100, 300), "Diagram Label A", fill='black')
        d.text((300, 400), "Diagram Label B", fill='black')
        img.save(image_path)
    
    output_dir = "reproduction_output"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Processing {image_path}...")
    
    # Initialize components
    reconstructor = SmartLayoutReconstructor(image_path)
    # Monkey patch GoogleOCR to use MockOCR
    import diagram_translator
    diagram_translator.GoogleOCR = MockOCR
    
    diagram_translator_instance = DiagramTranslator()
    translator = MockTranslator()
    ocr = MockOCR()
    
    # 1. Get OCR Text Boxes
    print("Running OCR...")
    ocr_result = ocr.extract_text_with_boxes(image_path)
    text_boxes = ocr_result.get('text_boxes', [])
    full_text = ocr_result.get('full_text', '')
    
    # 2. Analyze Layout
    print("Analyzing layout...")
    layout = reconstructor._analyze_layout_structure(text_boxes)
    
    # Print layout sections to debug "cutting" issue
    print("\n--- Layout Analysis ---")
    for i, section in enumerate(layout['page_sections']):
        height = section.get('height', section.get('y_end', 0) - section.get('y_start', 0))
        print(f"Section {i}: Type={section['type']}, Y={section['y_start']}-{section['y_end']}, Height={height}")
        if section['type'] == 'diagram':
            print(f"  Diagram Region: x={section.get('x', 0)}, w={section.get('w', 'full')}")
            
    # 3. Process Diagrams (to debug text strikethrough)
    print("\n--- Diagram Processing ---")
    translated_diagrams = []
    
    # Extract diagram regions from layout
    diagram_regions = []
    for section in layout['page_sections']:
        if section['type'] == 'diagram':
             diagram_regions.append({
                'x': section.get('x', 0),
                'y': section['y_start'],
                'w': section.get('w', reconstructor.width),
                'h': section['height']
            })
            
    # Process each diagram
    for i, region in enumerate(diagram_regions):
        print(f"Processing Diagram {i} at {region['y']}...")
        output_path = os.path.join(output_dir, f"diagram_{i}.png")
        
        # This calls extract_and_translate_diagram which handles inpainting
        translated_diagram, annotations = diagram_translator_instance.extract_and_translate_diagram(
            image_path,
            region,
            translator,
            output_path
        )
        
        translated_diagrams.append({
            'path': output_path,
            'image': translated_diagram,
            'region': region,
            'index': i,
            'annotations': annotations
        })
        print(f"  Saved to {output_path}")

    # 4. Reconstruct PDF
    print("\n--- Reconstructing PDF ---")
    output_pdf = os.path.join(output_dir, "reproduction.pdf")
    
    # Use mock translated paragraphs
    mock_paragraphs = []
    for para in layout['paragraphs']:
         mock_paragraphs.append("[TR] Mock Paragraph Content")

    reconstructor.reconstruct_pdf(
        text_boxes, 
        output_pdf, 
        translator=translator, 
        full_page_japanese=full_text,
        translated_diagrams=translated_diagrams,
        translated_paragraphs=mock_paragraphs
    )
    
    print(f"\nReproduction complete. Check {output_dir}")

if __name__ == "__main__":
    reproduce_issue()
