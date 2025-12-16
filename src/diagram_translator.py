"""
Diagram Translator
Extracts diagram regions, translates text labels, and creates translated diagrams
"""

from PIL import Image, ImageDraw, ImageFont
import os
import cv2
import numpy as np
from google_ocr import GoogleOCR


class DiagramTranslator:
    """
    Handles diagram extraction and translation:
    - Extracts diagram regions from images
    - Runs OCR on diagrams to find text labels
    - Translates labels using provided translator
    - Creates clean diagram images with translated labels
    """
    
    def __init__(self, google_credentials_path=None):
        """Initialize with Google OCR for diagram text extraction"""
        # GoogleOCR handles credentials internally via env vars, so we don't pass path
        self.ocr = GoogleOCR()
        
        # Setup font for overlays
        try:
            self.font_path = "C:/Windows/Fonts/arial.ttf"
            if not os.path.exists(self.font_path):
                self.font_path = "C:/Windows/Fonts/calibri.ttf"
        except:
            self.font_path = None

    def _inpaint_text_regions(self, pil_image, text_boxes):
        """
        Remove text from the image using OpenCV inpainting for a cleaner look.
        """
        try:
            # Convert PIL to OpenCV (RGB -> BGR)
            img_np = np.array(pil_image)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            
            # Create mask
            mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
            
            for box in text_boxes:
                x, y, w, h = box['x'], box['y'], box['w'], box['h']
                # Expand slightly to cover artifacts
                padding = 4
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(img_bgr.shape[1] - x, w + 2*padding)
                h = min(img_bgr.shape[0] - y, h + 2*padding)
                
                cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
                
            # Inpaint
            inpainted = cv2.inpaint(img_bgr, mask, 3, cv2.INPAINT_TELEA)
            
            # Convert back to PIL (BGR -> RGB)
            img_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)
            return Image.fromarray(img_rgb)
        except Exception as e:
            print(f"  Warning: Inpainting failed ({e}), returning original")
            return pil_image
    
    def _enhance_diagram_quality(self, pil_image):
        """
        Enhance diagram with advanced background removal.
        - Uses adaptive thresholding to create a clean black & white image.
        """
        try:
            img_np = np.array(pil_image.convert('L'))  # Convert to grayscale
            
            # 1. Denoise first to remove paper grain/noise
            # GaussianBlur is fast and effective for this
            img_blur = cv2.GaussianBlur(img_np, (5, 5), 0)
            
            # 2. Adaptive Thresholding
            # Increased block size (21) and constant (15) to be less sensitive to noise
            img_thresh = cv2.adaptiveThreshold(
                img_blur, 
                255,  # Max value
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY,  # Output is black or white
                25,  # Block size for analysis (larger = more robust to local variations)
                15   # Constant subtracted from mean (larger = less noise)
            )
            
            # 3. Noise reduction
            # Use morphological opening to remove small noise artifacts
            kernel = np.ones((2,2), np.uint8)
            img_clean = cv2.morphologyEx(img_thresh, cv2.MORPH_OPEN, kernel)
            
            # 4. Invert if needed (we want black objects on white background)
            # Check average color - if mostly black, it's inverted.
            if np.mean(img_clean) < 128:
                img_clean = cv2.bitwise_not(img_clean)
            
            return Image.fromarray(img_clean)
            
        except Exception as e:
            print(f"  Warning: Advanced image enhancement failed: {e}")
            return pil_image
    
    def extract_and_translate_diagram(self, image_path, diagram_region, translator, output_path=None):
        """
        Extract a diagram region, translate its text labels, and create translated version
        
        Args:
            image_path: Path to full page image
            diagram_region: Dict with 'x', 'y', 'w', 'h' defining the diagram area
            translator: Translator instance with translate_text method
            output_path: Optional path to save translated diagram
        
        Returns:
            PIL Image with translated labels
        """
        # Load and crop diagram region
        full_image = Image.open(image_path)
        diagram = full_image.crop((
            diagram_region['x'],
            diagram_region['y'],
            diagram_region['x'] + diagram_region['w'],
            diagram_region['y'] + diagram_region['h']
        ))
        
        # Save temporary diagram for OCR
        temp_path = output_path.replace('.png', '_temp.png') if output_path else 'temp_diagram.png'
        diagram.save(temp_path)
        
        try:
            # Run OCR on diagram to find text labels
            ocr_result = self.ocr.extract_text_with_boxes(temp_path)
            text_boxes = ocr_result.get('text_boxes', [])
            
            if not text_boxes:
                print(f"  No text found in diagram region")
                return diagram
            
            print(f"  Found {len(text_boxes)} text elements in diagram")
            
            # Use inpainting to remove original text cleanly
            overlay_image = self._inpaint_text_regions(diagram, text_boxes)
            
            # Enhance quality (whitening background)
            overlay_image = self._enhance_diagram_quality(overlay_image)
            
            draw = ImageDraw.Draw(overlay_image)
            
            # Process each text box
            text_annotations = []
            for box in text_boxes:
                japanese_text = box['text'].strip()
                
                if not japanese_text or len(japanese_text) < 2:
                    continue
                
                # Translate the text
                try:
                    english_text = translator.translate_text(
                        japanese_text,
                        context="technical diagram label",
                        source_lang='ja',
                        target_lang='en'
                    )
                except Exception as e:
                    print(f"    Translation failed for '{japanese_text}': {e}")
                    english_text = japanese_text
                
                x, y, w, h = box['x'], box['y'], box['w'], box['h']
                
                # Store annotation for vector rendering later
                text_annotations.append({
                    'text': english_text,
                    'x': x,
                    'y': y,
                    'w': w,
                    'h': h,
                    'original': japanese_text
                })
                
                # Determine font size based on original text height
                font_size = max(10, min(int(h * 0.8), 16))
                
                try:
                    if self.font_path and os.path.exists(self.font_path):
                        font = ImageFont.truetype(self.font_path, font_size)
                    else:
                        font = ImageFont.load_default()
                except:
                    font = ImageFont.load_default()
                
                # Calculate text size
                try:
                    text_bbox = draw.textbbox((0, 0), english_text, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                except:
                    # Fallback for older Pillow
                    text_width = len(english_text) * font_size * 0.5
                    text_height = font_size
                
                # Center text in the original box
                text_x = x + (w - text_width) // 2
                text_y = y + (h - text_height) // 2
                
                # Draw text with white outline for visibility (since we removed the white box)
                outline_color = "white"
                text_color = "black"
                stroke_width = 2
                
                # Draw outline
                for adj_x in range(-stroke_width, stroke_width+1):
                    for adj_y in range(-stroke_width, stroke_width+1):
                        draw.text((text_x+adj_x, text_y+adj_y), english_text, font=font, fill=outline_color)
                
                # Draw main text
                draw.text((text_x, text_y), english_text, fill=text_color, font=font)
                
                print(f"    '{japanese_text}' → '{english_text}'")
            
            # Save translated diagram
            if output_path:
                overlay_image.save(output_path)
                print(f"  Saved translated diagram: {output_path}")
            
            # Return both the image and the annotations
            return overlay_image, text_annotations
            
        finally:
            # Cleanup temp file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    def process_diagrams(self, image_path, diagram_regions, translator, output_dir):
        """
        Process multiple diagram regions and save translated versions
        
        Args:
            image_path: Path to full page image
            diagram_regions: List of diagram region dicts
            translator: Translator instance
            output_dir: Directory to save translated diagrams
        
        Returns:
            List of paths to translated diagram images
        """
        os.makedirs(output_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        translated_diagrams = []
        
        for i, region in enumerate(diagram_regions):
            print(f"\nTranslating diagram {i+1}/{len(diagram_regions)}...")
            
            output_path = os.path.join(output_dir, f"{base_name}_diagram_{i+1}.png")
            
            try:
                # Unpack tuple (image, annotations)
                translated_diagram, annotations = self.extract_and_translate_diagram(
                    image_path,
                    region,
                    translator,
                    output_path
                )
                
                # Store path and position info
                translated_diagrams.append({
                    'path': output_path,
                    'image': translated_diagram,
                    'region': region,
                    'index': i,
                    'annotations': annotations  # Pass annotations to PDF generator
                })
                
            except Exception as e:
                print(f"  Error translating diagram {i+1}: {e}")
                # Fallback to original crop
                full_image = Image.open(image_path)
                original_crop = full_image.crop((
                    region['x'],
                    region['y'],
                    region['x'] + region['w'],
                    region['y'] + region['h']
                ))
                original_crop.save(output_path)
                translated_diagrams.append({
                    'path': output_path,
                    'image': original_crop,
                    'region': region,
                    'index': i,
                    'annotations': []
                })
        
        return translated_diagrams
