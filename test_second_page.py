from pathlib import Path
from src.main import BookTranslator

img = 'images_to_process/2d514874_PXL_20251213_120130976.jpg'
print(f'Processing {Path(img).name}...')
t = BookTranslator(img, 'output')
r = t.process_page(verbose=True)
print(f'\nResult: {"SUCCESS" if r["success"] else "FAILED"}')
