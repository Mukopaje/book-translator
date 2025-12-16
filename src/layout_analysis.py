"""
Layout Analysis Module for Book Translator
Analyzes page images to identify and separate text blocks from diagrams
"""

import cv2
import numpy as np
from typing import List, Tuple
import os


class LayoutAnalyzer:
    """Analyzes document layouts to identify text regions and diagrams"""
    
    def __init__(self, image_path: str):
        """
        Initialize the layout analyzer with an image
        
        Args:
            image_path: Path to the image file to analyze
        """
        self.image_path = image_path
        self.image = cv2.imread(image_path)
        self.gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        self.height, self.width = self.gray.shape
        
    def detect_text_regions(self) -> List[Tuple[int, int, int, int]]:
        """
        Detect regions that likely contain text using morphological operations
        
        Returns:
            List of bounding boxes (x, y, w, h) for detected text regions
        """
        # Apply threshold
        _, binary = cv2.threshold(self.gray, 127, 255, cv2.THRESH_BINARY)
        
        # Apply morphological operations to find connected components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(binary, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Extract bounding boxes
        bboxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter out very small regions (noise)
            if w > 30 and h > 20:
                # Filter out very large regions (likely the page border)
                if w < self.width * 0.95 and h < self.height * 0.95:
                    bboxes.append((x, y, w, h))
        
        return bboxes
    
    def extract_region(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """
        Extract a region from the image
        
        Args:
            x, y, w, h: Bounding box coordinates and dimensions
            
        Returns:
            The extracted region as a numpy array
        """
        return self.image[y:y+h, x:x+w]
    
    def save_region(self, region: np.ndarray, output_path: str):
        """
        Save an extracted region to a file
        
        Args:
            region: The image region to save
            output_path: Path where to save the region
        """
        cv2.imwrite(output_path, region)
    
    def visualize_regions(self, output_path: str):
        """
        Create a visualization of detected regions
        
        Args:
            output_path: Path to save the visualization
        """
        bboxes = self.detect_text_regions()
        
        # Draw bounding boxes on a copy of the image
        visualization = self.image.copy()
        for x, y, w, h in bboxes:
            cv2.rectangle(visualization, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        cv2.imwrite(output_path, visualization)
        print(f"Visualization saved to {output_path}")
        print(f"Detected {len(bboxes)} regions")


if __name__ == "__main__":
    # Example usage
    test_image = "images_to_process/page_sample.jpg"
    
    if os.path.exists(test_image):
        analyzer = LayoutAnalyzer(test_image)
        
        # Detect regions
        regions = analyzer.detect_text_regions()
        print(f"Found {len(regions)} text/diagram regions")
        
        # Create visualization
        analyzer.visualize_regions("output/regions_visualization.jpg")
        
        # Extract first few regions as examples
        for i, (x, y, w, h) in enumerate(regions[:3]):
            region = analyzer.extract_region(x, y, w, h)
            analyzer.save_region(region, f"output/region_{i}.jpg")
            print(f"Extracted region {i}: size {w}x{h}")
    else:
        print(f"Test image not found at {test_image}")
        print("Please place an image in the 'images_to_process' folder")
