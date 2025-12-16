
import sys
sys.path.insert(0, 'src')

from main import BookTranslator

translator = BookTranslator('images_to_process/technical_manual_page.jpg', 'output')

# Modify the process to use English text extraction instead of Japanese
# This will test all the other components
import cv2
translator.text_extractor.extract_text = lambda img, lang='eng': '''
LOCOMOTIVE ENGINE CONTROL SYSTEM

The engine control system consists of:
1. Power Supply Unit
2. Control Module  
3. Sensor Array
4. Output Interface

Operating Modes:
- Self: Auto start mode for engine initiation
- Off: Complete shutdown of all systems
- Other 1: Standby mode for auxiliary operations
- Other 2: Maintenance mode with diagnostics

The system monitors critical parameters and ensures safe operation.
'''

# Run the pipeline
results = translator.process_page(verbose=True)
print("\n" + "="*70)
print("FINAL RESULTS")
print("="*70)
print(f"Success: {results['success']}")
for step, details in results['steps'].items():
    print(f"\n{step}:")
    for key, val in details.items():
        print(f"  {key}: {val}")
