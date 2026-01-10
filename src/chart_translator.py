"""
Chart Translator
Fork of DiagramTranslator specialized for Data Charts/Graphs.
"""

import re
from PIL import Image, ImageDraw, ImageFont
import os
import cv2
import numpy as np
from google_ocr import GoogleOCR

class ChartTranslator:
    """
    Handles CHART extraction and translation:
    - Optimized for graphs, plots, and data visualizations.
    - Preserves numbers and units strictly.
    - Uses enhanced cleaning for grid lines.
    """
    
    def __init__(self, processing_mode="enhanced"):
        self.ocr = GoogleOCR()
        self.processing_mode = processing_mode
        
        try:
            self.font_path = "C:/Windows/Fonts/arial.ttf"
            if not os.path.exists(self.font_path):
                self.font_path = "C:/Windows/Fonts/calibri.ttf"
        except:
            self.font_path = None

    def _inpaint_text_regions(self, pil_image, text_boxes, fill_with_white=True, padding=4):
        """
        Remove text. For charts, we almost always want fill_with_white=True 
        because backgrounds are usually white. Padding is generous (4px) to catch tick marks.
        """
        try:
            img_np = np.array(pil_image)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
            
            for box in text_boxes:
                x, y, w, h = box['x'], box['y'], box['w'], box['h']
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(img_bgr.shape[1] - x, w + 2*padding)
                h = min(img_bgr.shape[0] - y, h + 2*padding)
                
                # Always paint white for charts to preserve grid lines around text
                cv2.rectangle(img_bgr, (x, y), (x + w, y + h), (255, 255, 255), -1)

            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            return Image.fromarray(img_rgb)
        except Exception as e:
            print(f"  [Chart] Inpainting warning: {e}")
            return pil_image

    def _cluster_text_boxes(self, text_boxes):
        """
        Charts often have vertical text (Y-axis). 
        We should clustering logic to support vertical stacking?
        For MVP, standard clustering is usually okay if labels are horizontal.
        """
        # ... Reuse standard logic for now ...
        if not text_boxes:
            return []
        boxes = sorted(text_boxes, key=lambda b: (b['y'], b['x']))
        clusters = []
        current = None
        for b in boxes:
            if current is None:
                current = {'x': b['x'], 'y': b['y'], 'w': b['w'], 'h': b['h'], 'text': b.get('text', '')}
                continue
            
            # Standard horizontal merge
            same_line = abs(b['y'] - current['y']) <= 8
            current_right = current['x'] + current['w']
            gap = b['x'] - current_right
            if same_line and gap >= 0 and gap <= 15: # increased gap tolerance for spaced chart titles
                new_right = max(current_right, b['x'] + b['w'])
                current['w'] = new_right - current['x']
                current['h'] = max(current['h'], b['h'])
                current['text'] = (current.get('text', '') + b.get('text', '')).strip()
            else:
                clusters.append(current)
                current = {'x': b['x'], 'y': b['y'], 'w': b['w'], 'h': b['h'], 'text': b.get('text', '')}
        if current:
            clusters.append(current)
        return clusters

    def _enhance_chart_quality(self, pil_image):
        """
        Charts need crisp lines. Binarization is good.
        """
        try:
            img_np = np.array(pil_image.convert('L'))
            # Mild blur to reduce JPEG artifacts
            img_blur = cv2.GaussianBlur(img_np, (3, 3), 0)
            # Adaptive thresholding for crisp lines
            img_thresh = cv2.adaptiveThreshold(img_blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            return Image.fromarray(img_thresh)
        except:
            return pil_image

    def extract_and_translate_chart(self, image_path, region, translator, output_path=None, book_context=None):
        # 1. Crop
        full_image = Image.open(image_path)
        chart = full_image.crop((region['x'], region['y'], region['x'] + region['w'], region['y'] + region['h']))
        
        # 2. OCR on Crop
        temp_path = "temp_chart_ocr.png"
        chart.save(temp_path)
        
        try:
            ocr_result = self.ocr.extract_text_with_boxes(temp_path)
            raw_boxes = ocr_result.get('text_boxes', [])
            text_boxes = self._cluster_text_boxes(raw_boxes)
            
            if not raw_boxes:
                return chart, []
            
            # 3. Clean Background (Strict White Fill)
            cleaned = self._inpaint_text_regions(chart, raw_boxes, fill_with_white=True)
            # Enhance lines
            overlay_image = self._enhance_chart_quality(cleaned)
            
            # 4. Translate Labels
            annotations = []
            for box in text_boxes:
                original = box['text'].strip()
                if not original: continue
                
                # --- CHART SPECIFIC FILTERS ---
                # 1. Pure Numbers -> KEEP (Don't translate)
                if re.match(r'^[\d\.,\-\~]+$', original):
                    english_text = original # Keep numbers
                # 2. Units -> Keep/Simple map
                elif re.match(r'^[a-zA-Z0-9/%]+$', original):
                    english_text = original
                else:
                    # Translate
                    context = "chart axis label or data point"
                    if book_context: context += f". Book: {book_context}"
                    try:
                        english_text = translator.translate_text(original, context=context, source_lang='ja', target_lang='en')
                    except:
                        english_text = original
                
                if not english_text or not english_text.strip(): continue
                
                # Save Annotation
                annotations.append({
                    'text': english_text,
                    'x': box['x'], 'y': box['y'], 'w': box['w'], 'h': box['h'],
                    'original': original
                })
                print(f"  [Chart] '{original}' -> '{english_text}'")

            if output_path:
                overlay_image.save(output_path)
                
            return overlay_image, annotations
            
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

    def process_charts(self, image_path, chart_regions, translator, output_dir, book_context=None):
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        results = []
        
        for i, region in enumerate(chart_regions):
            print(f"Processing Chart {i+1}...")
            out_path = os.path.join(output_dir, f"{base_name}_chart_{i+1}.png")
            try:
                img, anns = self.extract_and_translate_chart(image_path, region, translator, out_path, book_context)
                results.append({
                    'path': out_path,
                    'image': img,
                    'region': region,
                    'annotations': anns,
                    'type': 'chart'
                })
            except Exception as e:
                print(f"Chart error: {e}")
                # Fallback?
        return results
