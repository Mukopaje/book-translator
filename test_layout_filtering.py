
import sys
from pathlib import Path
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from smart_layout_reconstructor import SmartLayoutReconstructor

class TestLayoutFiltering(unittest.TestCase):
    def setUp(self):
        # Mock image path (doesn't need to exist for this test as we mock the image object if needed, 
        # but SmartLayoutReconstructor opens it. We can mock the class or just point to a dummy file)
        # Actually SmartLayoutReconstructor opens the image in __init__.
        # Let's create a dummy image.
        from PIL import Image
        self.dummy_image_path = "dummy_test_image.jpg"
        img = Image.new('RGB', (1000, 1000), color = 'white')
        img.save(self.dummy_image_path)
        
        self.reconstructor = SmartLayoutReconstructor(self.dummy_image_path)
        
    def tearDown(self):
        import os
        if os.path.exists(self.dummy_image_path):
            os.remove(self.dummy_image_path)

    def test_filter_paragraph_boxes(self):
        # Create dummy text boxes
        boxes = []
        
        # Paragraph 1 (y=100 to 160)
        boxes.append({'x': 50, 'y': 100, 'w': 800, 'h': 20, 'text': 'Line 1'})
        boxes.append({'x': 50, 'y': 125, 'w': 800, 'h': 20, 'text': 'Line 2'})
        boxes.append({'x': 50, 'y': 150, 'w': 600, 'h': 20, 'text': 'Line 3'})
        
        # Diagram Label (y=300) - Isolated and short
        boxes.append({'x': 400, 'y': 300, 'w': 100, 'h': 20, 'text': 'Label'})
        
        # Paragraph 2 (y=500 to 560)
        boxes.append({'x': 50, 'y': 500, 'w': 800, 'h': 20, 'text': 'Line 4'})
        boxes.append({'x': 50, 'y': 525, 'w': 800, 'h': 20, 'text': 'Line 5'})
        boxes.append({'x': 50, 'y': 550, 'w': 700, 'h': 20, 'text': 'Line 6'})
        
        # Run filter
        filtered = self.reconstructor._filter_paragraph_boxes(boxes)
        
        # Check results
        print(f"\nOriginal boxes: {len(boxes)}")
        print(f"Filtered boxes: {len(filtered)}")
        
        # We expect 6 boxes (paragraphs), label should be removed
        self.assertEqual(len(filtered), 6)
        
        # Verify the label is gone
        for box in filtered:
            self.assertNotEqual(box['text'], 'Label')
            
        # Verify layout analysis finds the gap
        layout = self.reconstructor._analyze_layout_structure(boxes)
        diagram_regions = layout['diagram_regions']
        
        print(f"Diagram regions found: {len(diagram_regions)}")
        self.assertTrue(len(diagram_regions) >= 1)
        
        # Check if diagram region covers the label area (around y=300)
        found_diagram = False
        for region in diagram_regions:
            print(f"Region: y={region['y']} h={region['h']}")
            if region['y'] < 300 and (region['y'] + region['h']) > 300:
                found_diagram = True
                break
        
        self.assertTrue(found_diagram, "Should find a diagram region covering the label")

if __name__ == '__main__':
    unittest.main()
