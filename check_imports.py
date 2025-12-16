
try:
    import cv2
    import numpy as np
    print("OpenCV and NumPy are available.")
except ImportError as e:
    print(f"Import failed: {e}")
