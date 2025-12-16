"""
PDF Page Reconstructor
Creates clean PDF pages with diagrams in position and English text (no overlays)
"""

import os
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import black
import numpy as np


class PDFPageReconstructor:
    """
    Reconstructs a translated page as a clean PDF with:
    - Diagrams extracted and placed at their original positions
    - English text in text regions (no white box overlays)
    """
    
    def __init__(self, image_path):
        """
        Initialize with the original page image
        
        Args:
            image_path: Path to the original page image
        """
        self.image_path = image_path
        self.image = Image.open(image_path)
        self.width, self.height = self.image.size
        
        # Try to register a font that supports English text
        try:
            # Try to use Arial if available on Windows
            font_path = "C:/Windows/Fonts/arial.ttf"
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Arial', font_path))
                self.font_name = 'Arial'
            else:
                self.font_name = 'Helvetica'
        except:
            self.font_name = 'Helvetica'
    
    def _detect_diagram_regions(self, text_boxes):
        """
        Detect regions that contain diagrams (non-text areas with actual content)
        
        Args:
            text_boxes: List of text boxes with 'x', 'y', 'w', 'h' keys
            
        Returns:
            List of diagram regions as (x, y, w, h) tuples
        """
        # Convert image to grayscale for analysis
        img_gray = np.array(self.image.convert('L'))
        
        # Create a mask of text regions to exclude
        text_mask = np.zeros((self.height, self.width), dtype=np.uint8)
        
        for box in text_boxes:
            x, y, w, h = int(box['x']), int(box['y']), int(box['w']), int(box['h'])
            # Expand text boxes to exclude nearby areas
            padding = 20
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(self.width, x + w + padding)
            y2 = min(self.height, y + h + padding)
            text_mask[y1:y2, x1:x2] = 255
        
        # Find regions with actual visual content (not just white background)
        # Use edge detection to find areas with diagrams/graphics
        from PIL import ImageFilter
        edges = self.image.convert('L').filter(ImageFilter.FIND_EDGES)
        edge_array = np.array(edges)
        
        # Threshold to find regions with significant edges (diagrams)
        edge_mask = (edge_array > 30).astype(np.uint8) * 255
        
        # Remove text regions from edge mask
        edge_mask[text_mask > 0] = 0
        
        # Find bounding boxes of diagram regions
        diagram_regions = []
        
        # Simple approach: find vertical sections that contain diagrams
        # Divide page into horizontal bands and detect which ones have content
        band_height = self.height // 10  # Divide into 10 bands
        
        for i in range(10):
            y_start = i * band_height
            y_end = min((i + 1) * band_height, self.height)
            band = edge_mask[y_start:y_end, :]
            
            # If this band has significant edges, it likely contains a diagram
            if np.sum(band > 0) > 1000:  # At least 1000 edge pixels
                diagram_regions.append((0, y_start, self.width, y_end - y_start))
        
        # Merge adjacent regions
        merged_regions = []
        if diagram_regions:
            current = list(diagram_regions[0])
            for region in diagram_regions[1:]:
                # If adjacent or overlapping, merge
                if region[1] <= current[1] + current[3]:
                    current[3] = region[1] + region[3] - current[1]
                else:
                    merged_regions.append(tuple(current))
                    current = list(region)
            merged_regions.append(tuple(current))
        
        return merged_regions if merged_regions else []
    
    def _extract_diagram_image(self, region):
        """
        Extract diagram image from a region
        
        Args:
            region: (x, y, w, h) tuple
            
        Returns:
            PIL Image of the diagram region
        """
        x, y, w, h = region
        return self.image.crop((x, y, x + w, y + h))
    
    def _wrap_text(self, text, max_width, font_size):
        """
        Wrap text to fit within a maximum width
        
        Args:
            text: Text to wrap
            max_width: Maximum width in points
            font_size: Font size in points
            
        Returns:
            List of text lines
        """
        words = text.split()
        lines = []
        current_line = []
        
        # Approximate character width (adjust based on font)
        avg_char_width = font_size * 0.6
        max_chars = int(max_width / avg_char_width)
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if len(test_line) <= max_chars:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def reconstruct_as_pdf(self, text_boxes_with_translation, output_path):
        """
        Reconstruct the page as a clean PDF with proper paragraph formatting
        Groups text into readable paragraphs spanning full A4 width
        
        Args:
            text_boxes_with_translation: List of dicts with 'x', 'y', 'w', 'h', 'text', 'translation'
            output_path: Path to save the output PDF
            
        Returns:
            Path to the created PDF
        """
        print(f"Creating clean PDF with proper text formatting: {output_path}")
        print(f"  Processing {len(text_boxes_with_translation)} text boxes")
        
        from reportlab.lib.pagesizes import A4
        pdf_width, pdf_height = A4
        
        c = canvas.Canvas(output_path, pagesize=A4)
        
        # Pure white background
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
        
        if not text_boxes_with_translation:
            c.save()
            return output_path
        
        # Collect all translations in order
        sorted_boxes = sorted(text_boxes_with_translation, key=lambda b: (b['y'], b['x']))
        
        # Combine all text into paragraphs
        all_text = []
        for box in sorted_boxes:
            if 'translation' in box and box['translation']:
                all_text.append(box['translation'].strip())
        
        # Join and split into paragraphs (detect paragraph breaks)
        full_text = ' '.join(all_text)
        
        print(f"  Total text length: {len(full_text)} characters")
        
        # Setup text formatting
        c.setFillColor(black)
        font_size = 12  # Readable font size
        c.setFont(self.font_name, font_size)
        line_height = font_size * 1.6
        
        # Use generous margins for A4
        margin_left = 72  # 1 inch
        margin_right = pdf_width - 72
        margin_top = 72
        margin_bottom = 72
        current_y_pos = pdf_height - margin_top
        
        max_text_width = margin_right - margin_left
        
        # Split text into words and wrap to page width
        words = full_text.split()
        current_line_words = []
        
        for word in words:
            # Test if adding this word exceeds line width
            test_line = ' '.join(current_line_words + [word])
            text_width = c.stringWidth(test_line, self.font_name, font_size)
            
            if text_width <= max_text_width:
                current_line_words.append(word)
            else:
                # Draw current line and start new one
                if current_line_words:
                    line_text = ' '.join(current_line_words)
                    c.drawString(margin_left, current_y_pos, line_text)
                    current_y_pos -= line_height
                    
                    if current_y_pos < margin_bottom:
                        # Start new page if needed
                        c.showPage()
                        c.setFillColorRGB(1, 1, 1)
                        c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
                        c.setFillColor(black)
                        c.setFont(self.font_name, font_size)
                        current_y_pos = pdf_height - margin_top
                
                current_line_words = [word]
        
        # Draw last line
        if current_line_words:
            line_text = ' '.join(current_line_words)
            c.drawString(margin_left, current_y_pos, line_text)
        
        print(f"  Text formatted across full A4 width")
        
        c.save()
        print(f"[OK] PDF created successfully: {output_path}")
        return output_path
    
    def reconstruct_clean_pdf(self, text_boxes_with_translation, output_path):
        """
        Alternative approach: Create a completely clean PDF by detecting and preserving only diagrams
        
        Args:
            text_boxes_with_translation: List of dicts with 'x', 'y', 'w', 'h', 'text', 'translation'
            output_path: Path to save the output PDF
            
        Returns:
            Path to the created PDF
        """
        print(f"Creating clean PDF reconstruction: {output_path}")
        
        pdf_width = self.width
        pdf_height = self.height
        
        c = canvas.Canvas(output_path, pagesize=(pdf_width, pdf_height))
        
        # White background
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
        
        # Detect diagram regions (areas without text)
        diagram_regions = self._detect_diagram_regions(text_boxes_with_translation)
        
        # Place diagrams
        for region in diagram_regions:
            x, y, w, h = region
            diagram_img = self._extract_diagram_image(region)
            img_reader = ImageReader(diagram_img)
            
            # Convert to PDF coordinates
            pdf_y = pdf_height - y - h
            c.drawImage(img_reader, x, pdf_y, width=w, height=h)
        
        # Add English text
        c.setFillColor(black)
        
        for box in text_boxes_with_translation:
            if 'translation' not in box or not box['translation']:
                continue
            
            x = box['x']
            y = box['y']
            w = box['w']
            h = box['h']
            translation = box['translation']
            
            pdf_y = pdf_height - y - h
            
            font_size = min(h * 0.7, 12)
            font_size = max(font_size, 8)
            
            c.setFont(self.font_name, font_size)
            
            lines = self._wrap_text(translation, w - 4, font_size)
            
            line_height = font_size * 1.2
            text_y = pdf_y + h - line_height
            
            for line in lines:
                if text_y < pdf_y:
                    break
                c.drawString(x + 2, text_y, line)
                text_y -= line_height
        
        c.save()
        
        print(f"[OK] Clean PDF created successfully: {output_path}")
        return output_path
