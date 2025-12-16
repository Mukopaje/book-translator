"""
Test diagram translation with the updated system
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from main import BookTranslator

# Test with the sample image
image_path = "images_to_process/1765f76e_PXL_20251213_120130976.jpg"
output_dir = "output"

print("=" * 60)
print("Testing Complete Translation Pipeline with Diagrams")
print("=" * 60)

translator = BookTranslator(image_path, output_dir)
results = translator.process_page(verbose=True)

print("\n" + "=" * 60)
if results['success']:
    print("✅ TEST PASSED!")
    print("=" * 60)
    
    # Show results
    steps = results['steps']
    print(f"\nResults Summary:")
    print(f"  OCR: {steps['ocr_extraction']['text_length']} characters")
    print(f"  Translation: {steps['translation']['text_length']} characters")
    
    if 'pdf_creation' in steps and steps['pdf_creation']['success']:
        pdf_info = steps['pdf_creation']
        print(f"  PDF: {pdf_info['output_file']}")
        print(f"  Diagrams translated: {pdf_info.get('diagrams_translated', 0)}")
    
    print(f"\n✅ Check output folder for:")
    print(f"     - {results['page_name']}_translated.pdf")
    print(f"     - {results['page_name']}_translation.txt")
    print(f"     - diagrams/ folder (if diagrams found)")
else:
    print("❌ TEST FAILED!")
    print("=" * 60)
    print(f"Error: {results.get('error', 'Unknown error')}")
    sys.exit(1)
