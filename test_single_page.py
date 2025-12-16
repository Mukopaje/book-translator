#!/usr/bin/env python3
"""Test processing a single page with Google Vision overlay"""

from pathlib import Path
from src.main import BookTranslator
from PIL import Image
import numpy as np

print('Testing ONE page with Google Vision overlay\n')

img_path = 'images_to_process/1765f76e_PXL_20251213_120130976.jpg'
output_dir = 'output'

print(f'Processing: {img_path}\n')

translator = BookTranslator(img_path, output_dir)
result = translator.process_page(verbose=True)

print('\n' + '='*60)

if result['success']:
    print('✓ Processing completed successfully')
    
    # Check the output file
    output_file = 'output/1765f76e_PXL_20251213_120130976_translated_inplace.jpg'
    
    if Path(output_file).exists():
        img = Image.open(output_file)
        
        # Check for white pixels (indicates overlay)
        arr = np.array(img)
        white_pixels = np.all(arr == [255, 255, 255], axis=-1)
        white_count = np.sum(white_pixels)
        total = arr.shape[0] * arr.shape[1]
        
        print(f'\nOutput file: {output_file}')
        print(f'Image size: {img.size}')
        print(f'White pixels: {white_count:,} / {total:,} ({white_count/total*100:.2f}%)')
        
        if white_count > 1000:
            print('\n✓ SUCCESS - Overlay applied! English text should be visible.')
        else:
            print('\n✗ WARNING - No white rectangles found. Overlay may have failed.')
    else:
        print(f'\n✗ Output file not found: {output_file}')
else:
    print(f'✗ Processing failed: {result.get("error")}')

print('='*60)
