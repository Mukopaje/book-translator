"""
Diagram Processing Module for Book Translator
Cleans diagrams and applies translated labels
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, List, Dict
import os


class DiagramProcessor:
    """Processes and cleans diagrams, then applies translated labels"""
    
    def __init__(self, image_path: str):
        """
        Initialize the diagram processor
        
        Args:
            image_path: Path to the diagram image
        """
        self.image_path = image_path
        self.image = cv2.imread(image_path)
        self.pil_image = Image.open(image_path)

    def extract_region(self, x: int, y: int, w: int, h: int):
        """
        Extract a region (PIL Image) from the original image
        """
        return self.pil_image.crop((x, y, x + w, y + h))
    
    def detect_text_in_diagram(self) -> List[Tuple[int, int, int, int]]:
        """
        Detect text regions in a diagram for removal
        
        Returns:
            List of bounding boxes for detected text
        """
        # Use preprocessing to improve detection
        gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 3)

        # Adaptive threshold to handle variable backgrounds
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 11, 2)

        # Morphological ops to join text components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

        # Find connected components via pytesseract data as fallback
        text_boxes = []
        try:
            import pytesseract
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
            n = len(data['text'])
            for i in range(n):
                txt = data['text'][i].strip()
                conf = int(data['conf'][i]) if data['conf'][i] != '-1' else -1
                if txt and conf > 20:
                    x = int(data['left'][i])
                    y = int(data['top'][i])
                    w = int(data['width'][i])
                    h = int(data['height'][i])
                    # filter sizes
                    if 3 < w < self.image.shape[1] and 3 < h < self.image.shape[0]:
                        text_boxes.append((x, y, w, h))
        except Exception:
            # Fallback to contour method
            contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if 5 < w < 400 and 5 < h < 200:
                    text_boxes.append((x, y, w, h))

        # Merge overlapping boxes
        boxes = []
        for box in text_boxes:
            x, y, w, h = box
            placed = False
            for i, (xx, yy, ww, hh) in enumerate(boxes):
                # overlap test
                if not (x > xx + ww or xx > x + w or y > yy + hh or yy > y + h):
                    nx = min(x, xx)
                    ny = min(y, yy)
                    nw = max(x + w, xx + ww) - nx
                    nh = max(y + h, yy + hh) - ny
                    boxes[i] = (nx, ny, nw, nh)
                    placed = True
                    break
            if not placed:
                boxes.append((x, y, w, h))

        return boxes
    
    def remove_text_inpaint(self, text_boxes: List[Tuple[int, int, int, int]]) -> np.ndarray:
        """
        Remove text from diagram using inpainting
        
        Args:
            text_boxes: List of bounding boxes for text to remove
            
        Returns:
            Image with text removed
        """
        result = self.image.copy()
        
        # Create a mask for the text regions
        mask = np.zeros(self.image.shape[:2], dtype=np.uint8)
        
        for x, y, w, h in text_boxes:
            # Expand the bounding box slightly
            expansion = 2
            x = max(0, x - expansion)
            y = max(0, y - expansion)
            w = min(self.image.shape[1] - x, w + 2 * expansion)
            h = min(self.image.shape[0] - y, h + 2 * expansion)
            
            cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
        
        # Apply inpainting
        result = cv2.inpaint(result, mask, 3, cv2.INPAINT_TELEA)
        
        return result
    
    def add_text_labels(self, image: np.ndarray, labels: Dict[str, Tuple[int, int]]) -> np.ndarray:
        """
        Add translated text labels to the diagram
        
        Args:
            image: The diagram image
            labels: Dictionary with label text and positions {text: (x, y), ...}
            
        Returns:
            Image with added labels
        """
        # Convert to PIL for better text rendering
        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        # Try to use a nice font, fall back to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()
        
        # Add each label
        for text, (x, y) in labels.items():
            # Add black text
            draw.text((x, y), text, fill=(0, 0, 0), font=font)
            
            # Optionally add a white outline for better visibility
            draw.text((x-1, y-1), text, fill=(255, 255, 255), font=font)
            draw.text((x+1, y-1), text, fill=(255, 255, 255), font=font)
            draw.text((x-1, y+1), text, fill=(255, 255, 255), font=font)
            draw.text((x+1, y+1), text, fill=(255, 255, 255), font=font)
        
        # Convert back to OpenCV format
        result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        
        return result
    
    def clean_diagram(self, output_path: str = None) -> np.ndarray:
        """
        Clean a diagram by removing text
        
        Args:
            output_path: Optional path to save the cleaned diagram
            
        Returns:
            Cleaned diagram image
        """
        text_boxes = self.detect_text_in_diagram()
        cleaned = self.remove_text_inpaint(text_boxes)
        
        if output_path:
            cv2.imwrite(output_path, cleaned)
            print(f"Cleaned diagram saved to {output_path}")
        
        return cleaned
    
    def relabel_diagram(self, cleaned_image: np.ndarray, labels: Dict[str, Tuple[int, int]], 
                       output_path: str = None) -> np.ndarray:
        """
        Add translated labels to a cleaned diagram
        
        Args:
            cleaned_image: The cleaned diagram image
            labels: Dictionary with {english_text: (x, y), ...}
            output_path: Optional path to save the relabeled diagram
            
        Returns:
            Diagram with new labels
        """
        relabeled = self.add_text_labels(cleaned_image, labels)
        
        if output_path:
            cv2.imwrite(output_path, relabeled)
            print(f"Relabeled diagram saved to {output_path}")
        
        return relabeled
    
    def process_complete(self, labels: Dict[str, Tuple[int, int]], 
                        output_path: str = None) -> np.ndarray:
        """
        Complete processing: clean text and add new labels
        
        Args:
            labels: Dictionary with {english_text: (x, y), ...}
            output_path: Optional path to save the final result
            
        Returns:
            Processed diagram
        """
        cleaned = self.clean_diagram()
        relabeled = self.relabel_diagram(cleaned, labels)
        
        if output_path:
            cv2.imwrite(output_path, relabeled)
            print(f"Processed diagram saved to {output_path}")
        
        return relabeled


if __name__ == "__main__":
    # Example usage
    test_image = "images_to_process/page_sample.jpg"
    
    if os.path.exists(test_image):
        processor = DiagramProcessor(test_image)
        
        # Clean the diagram
        cleaned = processor.clean_diagram("output/diagram_cleaned.jpg")
        
        # Example labels (in English, with their positions)
        example_labels = {
            "Self": (100, 100),
            "Off": (200, 100),
            "Other 1": (300, 100),
            "Other 2": (400, 100)
        }
        
        # Add labels to cleaned diagram
        relabeled = processor.relabel_diagram(cleaned, example_labels, "output/diagram_relabeled.jpg")
        
        print("Diagram processing complete!")
    else:
        print(f"Test image not found at {test_image}")
