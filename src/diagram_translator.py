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
    
    def __init__(self, google_credentials_path=None, processing_mode="enhanced"):
        """Initialize with Google OCR for diagram text extraction
        
        Args:
            google_credentials_path: kept for backward compatibility (not used)
            processing_mode: "enhanced" | "light" | "raw". Controls how aggressively
                the background is processed. Default is "enhanced" for highest
                contrast and clean white background.
        """
        # GoogleOCR handles credentials internally via env vars, so we don't pass path
        self.ocr = GoogleOCR()

        # How diagrams are processed visually
        self.processing_mode = processing_mode
        
        # Setup font for overlays
        try:
            self.font_path = "C:/Windows/Fonts/arial.ttf"
            if not os.path.exists(self.font_path):
                self.font_path = "C:/Windows/Fonts/calibri.ttf"
        except:
            self.font_path = None

    def _inpaint_text_regions(self, pil_image, text_boxes, fill_with_white=False):
        """Remove or neutralize text regions in the image.

        If fill_with_white is False, use OpenCV inpainting to synthesize
        background texture. If True, simply paint the regions solid white
        to avoid introducing extra noise.
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

                if fill_with_white:
                    # Paint solid white to keep background plain
                    cv2.rectangle(img_bgr, (x, y), (x + w, y + h), (255, 255, 255), -1)
                else:
                    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)

            if fill_with_white:
                # No inpainting, just return the modified image
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                return Image.fromarray(img_rgb)

            # Inpaint using the mask
            inpainted = cv2.inpaint(img_bgr, mask, 3, cv2.INPAINT_TELEA)
            
            # Convert back to PIL (BGR -> RGB)
            img_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)
            return Image.fromarray(img_rgb)
        except Exception as e:
            print(f"  Warning: Inpainting failed ({e}), returning original")
            return pil_image
    
    def _enhance_diagram_quality(self, pil_image):
        """Enhance diagram with stronger background removal.

        This is the "enhanced" mode that uses adaptive thresholding to
        produce very high contrast black-and-white diagrams.
        """
        try:
            img_np = np.array(pil_image.convert('L'))  # Convert to grayscale
            
            # 1. Denoise first to remove paper grain/noise
            img_blur = cv2.GaussianBlur(img_np, (5, 5), 0)
            
            # 2. Adaptive Thresholding
            img_thresh = cv2.adaptiveThreshold(
                img_blur,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                25,
                15
            )
            
            # 3. Noise reduction
            kernel = np.ones((2, 2), np.uint8)
            img_clean = cv2.morphologyEx(img_thresh, cv2.MORPH_OPEN, kernel)
            
            # 4. Invert if needed (we want black objects on white background)
            if np.mean(img_clean) < 128:
                img_clean = cv2.bitwise_not(img_clean)
            
            return Image.fromarray(img_clean)
            
        except Exception as e:
            print(f"  Warning: Advanced image enhancement failed: {e}")
            return pil_image

    def _light_normalize_diagram(self, pil_image):
        """Light background normalization to keep a plain, clean look.

        This mode flattens the paper background towards white without
        harsh binarization, preserving diagram lines while reducing noise.
        """
        try:
            gray = np.array(pil_image.convert('L'))

            # Estimate background brightness via a high percentile
            bg = np.percentile(gray, 90)
            if bg <= 0:
                return pil_image

            scale = 255.0 / bg
            normalized = np.clip(gray * scale, 0, 255).astype(np.uint8)

            # Push near-white pixels to pure white to flatten paper texture
            result = normalized.copy()
            result[result > 235] = 255

            # Light denoising
            result = cv2.medianBlur(result, 3)

            return Image.fromarray(result)

        except Exception as e:
            print(f"  Warning: Light normalization failed: {e}")
            return pil_image
    
    def extract_and_translate_diagram(self, image_path, diagram_region, translator, output_path=None, book_context=None):
        """
        Extract a diagram region, translate its text labels, and create translated version
        
        Args:
            image_path: Path to full page image
            diagram_region: Dict with 'x', 'y', 'w', 'h' defining the diagram area
            translator: Translator instance with translate_text method
            output_path: Optional path to save translated diagram
            book_context: Optional global context about the book
        
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

            # Decide how aggressively to process the diagram background
            if self.processing_mode == "raw":
                # No background work: keep original crop, just draw translated labels
                overlay_image = diagram.copy()
            elif self.processing_mode == "light":
                # Fill text areas with white and lightly normalize background
                cleaned = self._inpaint_text_regions(diagram, text_boxes, fill_with_white=True)
                overlay_image = self._light_normalize_diagram(cleaned)
            else:
                # Enhanced mode: inpaint then strong thresholding
                cleaned = self._inpaint_text_regions(diagram, text_boxes)
                overlay_image = self._enhance_diagram_quality(cleaned)
            
            draw = ImageDraw.Draw(overlay_image)
            
            # Process each text box
            text_annotations = []
            for box in text_boxes:
                japanese_text = box['text'].strip()
                
                # Allow single characters (like A, B, P, V) if they are alphanumeric
                if not japanese_text:
                    continue
                
                # Filter out long text blocks (likely paragraphs that shouldn't be in diagram labels)
                # If text is very long (> 50 chars) or has multiple lines, it might be a paragraph
                if len(japanese_text) > 50 or japanese_text.count('\n') > 2:
                    print(f"    Skipping long text block in diagram: {japanese_text[:30]}...")
                    continue

                # Translate the text
                try:
                    # Skip translation for single latin characters/numbers to preserve them exactly
                    if len(japanese_text) == 1 and japanese_text.isalnum():
                        english_text = japanese_text
                    else:
                        # Add book context to translation request
                        trans_context = "technical diagram label"
                        if book_context:
                            trans_context = f"{trans_context}. Book Context: {book_context}"
                            
                        english_text = translator.translate_text(
                            japanese_text,
                            context=trans_context,
                            source_lang='ja',
                            target_lang='en'
                        )
                except Exception as e:
                    print(f"    Translation failed for '{japanese_text}': {e}")
                    english_text = japanese_text
                
                # Filter out empty or whitespace-only translations
                if not english_text or not english_text.strip():
                    print(f"    Skipping empty translation for '{japanese_text}'")
                    continue

                # Filter out overly long English labels which are likely
                # paragraph fragments rather than true diagram labels.
                if len(english_text) > 40 or english_text.count(" ") > 4:
                    print(f"    Skipping long translated label: '{english_text[:60]}'")
                    continue
                
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
    
    def process_diagrams(self, image_path, diagram_regions, translator, output_dir, book_context=None):
        """
        Process multiple diagram regions and save translated versions
        
        Args:
            image_path: Path to full page image
            diagram_regions: List of diagram region dicts
            translator: Translator instance
            output_dir: Directory to save translated diagrams
            book_context: Optional global context about the book
        
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
                    output_path,
                    book_context=book_context
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
