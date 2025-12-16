"""
Google Cloud Vision OCR Module
Uses Google Cloud Vision API for superior Japanese OCR accuracy
"""

import os
from pathlib import Path
from google.cloud import vision
from dotenv import load_dotenv


class GoogleOCR:
    """Extracts text from images using Google Cloud Vision API"""
    
    def __init__(self):
        """Initialize Google Cloud Vision client"""
        # Load environment to get credentials path
        load_dotenv()
        
        # Google Cloud Vision uses GOOGLE_APPLICATION_CREDENTIALS env var
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if creds_path and not os.path.isabs(creds_path):
            # If relative path, make it absolute from project root
            project_root = Path(__file__).parent.parent
            creds_path = str(project_root / creds_path)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
        
        try:
            self.client = vision.ImageAnnotatorClient()
            self.available = True
        except Exception as e:
            print(f"Warning: Google Cloud Vision not available: {e}")
            print("Will fall back to Tesseract OCR")
            self.available = False
            self.client = None
    
    def extract_text(self, image_path: str) -> str:
        """
        Extract text from image using Google Cloud Vision
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text as string
        """
        if not self.available:
            raise RuntimeError("Google Cloud Vision API not available")
        
        # Read image file
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        # Perform text detection with language hints for Japanese
        response = self.client.document_text_detection(
            image=image,
            image_context=vision.ImageContext(
                language_hints=['ja']  # Japanese language hint
            )
        )
        
        if response.error.message:
            raise Exception(f"Google Vision API error: {response.error.message}")
        
        # Get the full text
        if response.full_text_annotation:
            return response.full_text_annotation.text
        else:
            return ""
    
    def extract_text_with_boxes(self, image_path: str):
        """
        Extract text with bounding boxes
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dict with full_text and text_boxes list
        """
        if not self.available:
            raise RuntimeError("Google Cloud Vision API not available")
        
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        response = self.client.document_text_detection(
            image=image,
            image_context=vision.ImageContext(language_hints=['ja'])
        )
        
        if response.error.message:
            raise Exception(f"Google Vision API error: {response.error.message}")
        
        text_boxes = []
        full_text = ""
        
        if response.full_text_annotation:
            full_text = response.full_text_annotation.text
            
            # Extract bounding boxes for each word/block
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            # Get word text
                            word_text = ''.join([symbol.text for symbol in word.symbols])
                            
                            # Get bounding box
                            vertices = word.bounding_box.vertices
                            xs = [v.x for v in vertices]
                            ys = [v.y for v in vertices]
                            
                            x = min(xs)
                            y = min(ys)
                            w = max(xs) - x
                            h = max(ys) - y
                            
                            # Get confidence
                            confidence = word.confidence * 100 if hasattr(word, 'confidence') else 100
                            
                            text_boxes.append({
                                'text': word_text,
                                'x': x,
                                'y': y,
                                'w': w,
                                'h': h,
                                'confidence': confidence
                            })
        
        return {
            'full_text': full_text,
            'text_boxes': text_boxes
        }


if __name__ == "__main__":
    # Test the Google OCR
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python google_ocr.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    try:
        ocr = GoogleOCR()
        if not ocr.available:
            print("Google Cloud Vision not available. Check credentials.")
            sys.exit(1)
        
        print(f"Extracting text from: {image_path}")
        text = ocr.extract_text(image_path)
        
        print(f"\n=== Extracted Text ({len(text)} chars) ===")
        print(text)
        
        # Save to file
        output_path = "output/google_ocr_result.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"\nSaved to: {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
