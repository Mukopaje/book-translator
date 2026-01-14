#!/usr/bin/env python3
"""
Test script for bilingual diagram overlay renderer.
Creates a sample diagram with overlay labels to verify functionality.
"""

import sys
import os
sys.path.insert(0, 'src')

from PIL import Image, ImageDraw, ImageFont
from diagram_overlay_renderer import DiagramOverlayRenderer

def create_sample_diagram():
    """Create a simple diagram for testing."""
    # Create a 800x600 image with some shapes
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)

    # Draw some diagram elements
    # Rectangle (component)
    draw.rectangle([100, 100, 300, 200], outline='black', width=3)
    draw.text((150, 140), 'エンジン', fill='black', font=None)

    # Circle (another component)
    draw.ellipse([400, 150, 550, 300], outline='black', width=3)
    draw.text((440, 210), 'ピストン', fill='black', font=None)

    # Arrow
    draw.line([300, 150, 400, 225], fill='black', width=2)
    draw.polygon([(390, 220), (400, 225), (395, 230)], fill='black')

    # Labels
    draw.text((150, 50), '燃料系統', fill='black', font=None)
    draw.text((450, 100), '圧力', fill='black', font=None)
    draw.text((100, 400), '温度センサー', fill='black', font=None)

    return img

def main():
    print("=" * 60)
    print("Bilingual Diagram Overlay Renderer - Test")
    print("=" * 60)

    # Create sample diagram
    print("\n1. Creating sample diagram...")
    sample_img = create_sample_diagram()
    sample_path = '/tmp/test_diagram_original.png'
    sample_img.save(sample_path)
    print(f"   Saved original diagram: {sample_path}")

    # Define text boxes with translations
    print("\n2. Defining text boxes with translations...")
    text_boxes = [
        {
            'bbox': (150, 50, 100, 20),
            'japanese': '燃料系統',
            'english': 'Fuel System',
            'orientation': 'horizontal',
            'font_size': 14
        },
        {
            'bbox': (150, 140, 80, 20),
            'japanese': 'エンジン',
            'english': 'Engine',
            'orientation': 'horizontal',
            'font_size': 14
        },
        {
            'bbox': (440, 210, 80, 20),
            'japanese': 'ピストン',
            'english': 'Piston',
            'orientation': 'horizontal',
            'font_size': 14
        },
        {
            'bbox': (450, 100, 60, 20),
            'japanese': '圧力',
            'english': 'Pressure',
            'orientation': 'horizontal',
            'font_size': 12
        },
        {
            'bbox': (100, 400, 120, 20),
            'japanese': '温度センサー',
            'english': 'Temp Sensor',
            'orientation': 'horizontal',
            'font_size': 12
        },
    ]

    print(f"   Defined {len(text_boxes)} text elements")

    # Create bilingual diagram
    print("\n3. Rendering bilingual diagram...")
    renderer = DiagramOverlayRenderer()
    output_path = '/tmp/test_diagram_bilingual.png'

    result = renderer.render_bilingual_diagram(
        original_image_path=sample_path,
        text_boxes=text_boxes,
        output_path=output_path
    )

    print(f"\n   ✅ Success! Bilingual diagram saved to: {result}")

    # Display results
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(f"Original:  {sample_path}")
    print(f"Bilingual: {output_path}")
    print("\nYou can view these images to compare:")
    print(f"  open {sample_path}")
    print(f"  open {output_path}")
    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
