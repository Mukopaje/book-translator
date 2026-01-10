"""
Diagram Translator
Extracts diagram regions, translates text labels, and creates translated diagrams
"""

import re
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

    def _inpaint_text_regions(self, pil_image, text_boxes, fill_with_white=False, padding=2):
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
                # Use provided padding
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

    def _cluster_text_boxes(self, text_boxes, line_tol=8, gap_tol=10):
        """Cluster raw OCR boxes into logical labels.

        Many OCR engines return one box per character. This groups nearby
        boxes on the same line into a single label box with concatenated text.
        """
        if not text_boxes:
            return []

        # Sort top-to-bottom, then left-to-right
        boxes = sorted(text_boxes, key=lambda b: (b['y'], b['x']))

        clusters = []
        current = None

        for b in boxes:
            if current is None:
                current = {
                    'x': b['x'],
                    'y': b['y'],
                    'w': b['w'],
                    'h': b['h'],
                    'text': b.get('text', '')
                }
                continue

            # Check if b is on approximately the same line as current
            same_line = abs(b['y'] - current['y']) <= line_tol
            # Horizontal gap from current right edge to new box left
            current_right = current['x'] + current['w']
            gap = b['x'] - current_right

            if same_line and gap >= 0 and gap <= gap_tol:
                # Merge into current cluster
                new_right = max(current_right, b['x'] + b['w'])
                current['w'] = new_right - current['x']
                current['h'] = max(current['h'], b['h'])
                current['text'] = (current.get('text', '') + b.get('text', '')).strip()
            else:
                clusters.append(current)
                current = {
                    'x': b['x'],
                    'y': b['y'],
                    'w': b['w'],
                    'h': b['h'],
                    'text': b.get('text', '')
                }

        if current is not None:
            clusters.append(current)

        return clusters
    
    def _enhance_diagram_quality(self, pil_image):
        """Enhance diagram with stronger background removal.

        This is the "enhanced" mode that uses adaptive thresholding to
        produce very high contrast black-and-white diagrams.
        """
        try:
            img_np = np.array(pil_image.convert('L'))  # Convert to grayscale
            
            # 1. Denoise first to remove paper grain/noise
            img_blur = cv2.GaussianBlur(img_np, (5, 5), 0)
            
            # 2. Adaptive Thresholding - using slightly larger block size to reduce salt-and-pepper noise
            img_thresh = cv2.adaptiveThreshold(
                img_blur,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31, # Increased from 25
                18  # Increased from 15
            )
            
            # 3. Noise reduction
            kernel = np.ones((2, 2), np.uint8)
            img_clean = cv2.morphologyEx(img_thresh, cv2.MORPH_OPEN, kernel)
            
            # 4. Invert if needed (we want black objects on white background)
            if np.mean(img_clean) < 128:
                img_clean = cv2.bitwise_not(img_clean)

            # 5. Remove tiny isolated specks using connected components.
            # This keeps real diagram lines while cleaning random dots.
            try:
                # Ensure binary image (0 or 255)
                _, binary = cv2.threshold(img_clean, 200, 255, cv2.THRESH_BINARY)

                # Work on inverted image so foreground (ink) is 255
                inv = cv2.bitwise_not(binary)
                num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)

                min_area = 40  # pixels; increased to remove larger noise specks
                for label in range(1, num_labels):  # skip background label 0
                    area = stats[label, cv2.CC_STAT_AREA]
                    if area < min_area:
                        inv[labels == label] = 0  # remove small speck

                # Invert back to black ink on white
                img_clean = cv2.bitwise_not(inv)
            except Exception as cc_e:
                print(f"  Warning: speckle removal failed: {cc_e}")
            
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
            raw_boxes = ocr_result.get('text_boxes', [])

            # Cluster char-level boxes into logical labels for translation
            text_boxes = self._cluster_text_boxes(raw_boxes)
            
            if not raw_boxes:
                print(f"  No text found in diagram region")
                return diagram, []
            
            print(f"  Found {len(text_boxes)} text labels in diagram")

            # Decide how aggressively to process the diagram background
            if self.processing_mode == "raw":
                # No background work: keep original crop, just draw translated labels
                overlay_image = diagram.copy()
            else:
                # Use RAW boxes for inpainting to ensure every speck of ink is covered
                # Increase padding slightly (4px) to ensure edges are gone
                cleaned = self._inpaint_text_regions(diagram, raw_boxes, fill_with_white=True, padding=4)
                
                if self.processing_mode == "light":
                    overlay_image = self._light_normalize_diagram(cleaned)
                else:
                    # Enhanced mode: adaptive thresholding
                    overlay_image = self._enhance_diagram_quality(cleaned)
            
            # Process each text box
            text_annotations = []
            for box in text_boxes:
                japanese_text = box['text'].strip()
                if not japanese_text:
                    continue
                
                # Filter out obvious noise or non-text artifacts
                if len(japanese_text) == 1 and not any('\u3040' <= c <= '\u9fff' for c in japanese_text) and not japanese_text.isalnum():
                    continue

                # Translate the text
                try:
                    # Preserve technical codes exactly
                    # e.g. DE101, 14150, 2350
                    is_technical = (
                        japanese_text.lower().startswith('de') or 
                        (japanese_text.isdigit() and len(japanese_text) >= 2) or
                        (japanese_text.replace('.', '').isdigit())
                    )
                    
                    if is_technical:
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
                    continue

                english_text = english_text.strip()
                
                # Filter out diagnostic or helper phrases
                lower_text = english_text.lower()
                diagnostic_fragments = [
                    "(no content to translate)",
                    "(no text provided)",
                    "no translation needed",
                    "provided japanese text"
                ]
                if any(fragment in lower_text for fragment in diagnostic_fragments):
                    continue
                
                x, y, w, h = box['x'], box['y'], box['w'], box['h']

                # Bottom band check (usually contains body text leaking into crop)
                # But be careful with dimensions!
                center_y = y + h / 2.0
                diag_height = diagram.height
                if diag_height and center_y > diag_height * 0.9 and len(english_text) > 20: # Keep short ones
                    print(f"    Skipping likely-leaked body text: '{english_text}'")
                    continue
                
                # Store annotation for vector rendering later (PDF overlay).
                # We deliberately do NOT draw text directly onto the diagram
                # image here to avoid double-rendering (raster + PDF vector),
                # which created a "shadow" effect in the final output.
                text_annotations.append({
                    'text': english_text,
                    'x': x,
                    'y': y,
                    'w': w,
                    'h': h,
                    'original': japanese_text
                })
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
