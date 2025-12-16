"""
Test PDF reconstruction on a single page
"""

import sys
sys.path.insert(0, 'src')

from main import BookTranslator

# Test with the first page
image_path = "images_to_process/1765f76e_PXL_20251213_120130976.jpg"

print("="*60)
print("Testing PDF Reconstruction")
print("="*60)

translator = BookTranslator(image_path, "output")
results = translator.process_page(verbose=True)

if results['success']:
    print("\n" + "="*60)
    print("PDF reconstruction test completed successfully!")
    print("="*60)
    print("\nCheck the output folder for the PDF file:")
    print("  output/1765f76e_PXL_20251213_120130976_translated.pdf")
else:
    print("\n[ERROR] PDF reconstruction test failed")
    if 'error' in results:
        print(f"Error: {results['error']}")
