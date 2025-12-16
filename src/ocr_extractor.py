"""
OCR Module for Book Translator
Extracts Japanese text from images using Tesseract OCR
"""

import pytesseract
import cv2
import numpy as np
from typing import List, Tuple, Dict
import os
from pathlib import Path
import subprocess
from dotenv import load_dotenv

# Try to import Google OCR
try:
    from google_ocr import GoogleOCR
    GOOGLE_OCR_AVAILABLE = True
except ImportError:
    GOOGLE_OCR_AVAILABLE = False


class TextExtractor:
    """Extracts text from images using Tesseract OCR"""
    
    def __init__(self):
        """
        Initialize the text extractor
        """
        # Try to initialize Google OCR first (much better for Japanese)
        self.google_ocr = None
        if GOOGLE_OCR_AVAILABLE:
            try:
                self.google_ocr = GoogleOCR()
                if self.google_ocr.available:
                    print("[OK] Using Google Cloud Vision API for OCR (high quality)")
                else:
                    self.google_ocr = None
            except Exception as e:
                print(f"Google OCR init failed: {e}")
                self.google_ocr = None
        
        if not self.google_ocr:
            print("[WARNING] Using Tesseract OCR (lower quality for Japanese)")
        
        # Load environment variables to get Tesseract path (fallback)
        load_dotenv()
        tesseract_path = os.getenv('TESSERACT_PATH')
        
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

            # Ensure TESSDATA_PREFIX is set so tesseract can find language data
            tessdata_dir = os.path.join(os.path.dirname(tesseract_path), 'tessdata')
            # Only set TESSDATA_PREFIX here if it's not already set (respect .env or user overrides)
            if not os.getenv('TESSDATA_PREFIX'):
                if os.path.isdir(tessdata_dir):
                    os.environ['TESSDATA_PREFIX'] = tessdata_dir
                else:
                    # Fallback: set to parent directory of executable (some installs use this)
                    os.environ['TESSDATA_PREFIX'] = os.path.dirname(tesseract_path)
        else:
            print("Warning: TESSERACT_PATH not found or invalid in .env file. "
                  "Assuming 'tesseract' is in the system PATH.")

            # Try a common installation tessdata path as a last resort
            common_tessdata = "C:\\Program Files\\Tesseract-OCR\\tessdata"
            if os.path.isdir(common_tessdata):
                os.environ['TESSDATA_PREFIX'] = common_tessdata

        # Determine tessdata dir to pass explicitly to tesseract calls
        project_root = Path(__file__).resolve().parents[1]
        project_tess = project_root / 'tessdata'
        env_tess = os.getenv('TESSDATA_PREFIX')
        # Prefer explicit env var if set and valid
        if env_tess and os.path.isdir(env_tess):
            self.tessdata_dir = env_tess
        # Prefer project-local tessdata if it exists (we may have downloaded traineddata here)
        elif project_tess.is_dir():
            self.tessdata_dir = str(project_tess)
        else:
            # fallback to any common installed tessdata directory
            common_tessdata = "C:\\Program Files\\Tesseract-OCR\\tessdata"
            if os.path.isdir(common_tessdata):
                self.tessdata_dir = common_tessdata
            else:
                self.tessdata_dir = str(project_tess)
        # store tesseract command path to use in subprocess calls
        if tesseract_path and os.path.exists(tesseract_path):
            self.tesseract_cmd = tesseract_path
        else:
            self.tesseract_cmd = pytesseract.pytesseract.tesseract_cmd
    
    def extract_text(self, image_path: str, language: str = 'jpn') -> str:
        """
        Extract text from an image
        
        Args:
            image_path: Path to the image file
            language: OCR language code (jpn for Japanese, eng for English)
            
        Returns:
            Extracted text as a string
        """
        # Try Google Cloud Vision first (much better accuracy)
        if self.google_ocr:
            try:
                text = self.google_ocr.extract_text(image_path)
                return text
            except Exception as e:
                print(f"Google OCR failed, falling back to Tesseract: {e}")
        
        # Fall back to Tesseract OCR
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")
        
        # Convert to grayscale for better OCR
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Enhanced preprocessing for phone photos
        # 1. Resize to reasonable size first (phone photos are often huge)
        max_dim = 2400
        h, w = gray.shape
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        
        # 2. Increase contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # 3. Simple binary threshold (Otsu's method - automatic threshold selection)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Try using tesseract CLI with explicit tessdata dir and PSM mode for better results
        try:
            # Save preprocessed image to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                cv2.imwrite(tmp_path, binary)
            
            # Use PSM 4 (single column of text) which works well for book pages
            cmd = [self.tesseract_cmd, '--tessdata-dir', self.tessdata_dir, tmp_path, 'stdout', '-l', language, '--psm', '4']
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            text = proc.stdout.decode('utf-8', errors='ignore')
            
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return text
        except Exception as e:
            # Fallback to pytesseract if CLI call fails
            config = '--psm 4'
            return pytesseract.image_to_string(binary, lang=language, config=config)
    
    def extract_text_with_boxes(self, image_path: str, language: str = 'jpn') -> Dict:
        """
        Extract text and get bounding boxes for each detected text element
        
        Args:
            image_path: Path to the image file
            language: OCR language code
            
        Returns:
            Dictionary containing text and bounding box information
        """
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply preprocessing
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Upscale image
        scale_percent = 200
        width = int(binary.shape[1] * scale_percent / 100)
        height = int(binary.shape[0] * scale_percent / 100)
        binary_scaled = cv2.resize(binary, (width, height), interpolation=cv2.INTER_CUBIC)
        
        # Get detailed data
        config = f'--tessdata-dir "{self.tessdata_dir}"'
        data = pytesseract.image_to_data(binary_scaled, lang=language, config=config, output_type=pytesseract.Output.DICT)
        
        # Scale back the coordinates to original image size
        scale_factor = 100 / scale_percent
        
        text_boxes = []
        for i in range(len(data['text'])):
            if data['conf'][i] > 30:  # Only include text with confidence > 30%
                box = {
                    'text': data['text'][i],
                    'x': int(data['left'][i] * scale_factor),
                    'y': int(data['top'][i] * scale_factor),
                    'w': int(data['width'][i] * scale_factor),
                    'h': int(data['height'][i] * scale_factor),
                    'confidence': data['conf'][i]
                }
                text_boxes.append(box)
        
        full_text = pytesseract.image_to_string(binary_scaled, lang=language, config=config)
        return {
            'full_text': full_text,
            'text_boxes': text_boxes
        }
    
    def extract_text_from_region(self, image: np.ndarray, language: str = 'jpn') -> str:
        """
        Extract text from a numpy array (image region)
        
        Args:
            image: Image as numpy array
            language: OCR language code
            
        Returns:
            Extracted text
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Apply preprocessing
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Upscale
        scale_percent = 200
        width = int(binary.shape[1] * scale_percent / 100)
        height = int(binary.shape[0] * scale_percent / 100)
        binary_scaled = cv2.resize(binary, (width, height), interpolation=cv2.INTER_CUBIC)
        
        # Try using tesseract CLI on a temporary file to ensure tessdata dir is honored
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                from PIL import Image
                Image.fromarray(binary_scaled).save(tmp_path)
            cmd = [self.tesseract_cmd, '--tessdata-dir', self.tessdata_dir, tmp_path, 'stdout', '-l', language]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            text = proc.stdout.decode('utf-8', errors='ignore')
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return text
        except Exception:
            config = f'--tessdata-dir "{self.tessdata_dir}"'
            return pytesseract.image_to_string(binary_scaled, lang=language, config=config)
    
    def save_ocr_results(self, text: str, output_path: str):
        """
        Save extracted text to a file
        
        Args:
            text: The extracted text
            output_path: Path where to save the text
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"OCR results saved to {output_path}")


if __name__ == "__main__":
    # Example usage
    test_image = "images_to_process/page_sample.jpg"
    
    if os.path.exists(test_image):
        extractor = TextExtractor()
        
        # Extract text
        text = extractor.extract_text(test_image, language='jpn')
        print("=== Extracted Japanese Text ===")
        print(text[:500])  # Print first 500 characters
        
        # Save results
        extractor.save_ocr_results(text, "output/extracted_text_jpn.txt")
        
        # Extract with bounding boxes
        result = extractor.extract_text_with_boxes(test_image, language='jpn')
        print(f"\n=== Found {len(result['text_boxes'])} text elements ===")
        for i, box in enumerate(result['text_boxes'][:5]):
            print(f"Element {i}: '{box['text']}' at ({box['x']}, {box['y']})")
    else:
        print(f"Test image not found at {test_image}")
        print("Please place an image in the 'images_to_process' folder")
        print("\nNote: Tesseract OCR must be installed separately")
        print("Download from: https://github.com/UB-Mannheim/tesseract/wiki")
