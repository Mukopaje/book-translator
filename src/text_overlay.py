"""
Text Overlay Module for Book Translator
Overlays translated text onto the original image at detected text positions
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from typing import Dict, List, Tuple
import os
from pathlib import Path


class TextOverlay:
    """Overlays translated text onto image replacing Japanese text with English"""
    
    def __init__(self, image_path: str):
        """
        Initialize the text overlay
        
        Args:
            image_path: Path to the image
        """
        self.image_path = image_path
        self.image_cv = cv2.imread(image_path)
        self.image_pil = Image.open(image_path).convert('RGB')
        
        if self.image_cv is None:
            raise ValueError(f"Could not read image: {image_path}")
        # determine tessdata dir (prefer env TESSDATA_PREFIX then project-local tessdata)
        env_tess = os.getenv('TESSDATA_PREFIX')
        proj_tess = Path(__file__).resolve().parents[1] / 'tessdata'
        if env_tess and Path(env_tess).is_dir():
            self.tessdata_dir = str(env_tess)
        elif proj_tess.is_dir():
            self.tessdata_dir = str(proj_tess)
        else:
            # fallback to common installation path
            common = r"C:\Program Files\Tesseract-OCR\tessdata"
            self.tessdata_dir = common if Path(common).is_dir() else ''
        # set tesseract command if path provided in env
        tesseract_path = os.getenv('TESSERACT_PATH')
        if tesseract_path and Path(tesseract_path).exists():
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    def get_text_boxes(self, language: str = 'jpn') -> List[Dict]:
        """
        Extract text boxes with positions and content using Tesseract
        
        Args:
            language: OCR language code
            
        Returns:
            List of dicts with 'text', 'box' (x,y,w,h), 'conf' (confidence)
        """
        # Convert to grayscale and preprocess
        gray = cv2.cvtColor(self.image_cv, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Upscale for better OCR
        scale_percent = 200
        width = int(binary.shape[1] * scale_percent / 100)
        height = int(binary.shape[0] * scale_percent / 100)
        binary_scaled = cv2.resize(binary, (width, height), interpolation=cv2.INTER_CUBIC)
        
        # Ensure TESSDATA_PREFIX is set so Tesseract can load languages
        if self.tessdata_dir:
            # normalize and set env var
            tesspath = str(Path(self.tessdata_dir).resolve())
            os.environ['TESSDATA_PREFIX'] = tesspath
        # Get data with boxes
        # Avoid passing tessdata path via config string (handles spaces poorly);
        # rely on TESSDATA_PREFIX environment variable which we set above.
        data = pytesseract.image_to_data(binary_scaled, lang=language, output_type=pytesseract.Output.DICT)
        
        # Scale back to original
        scale_factor = 100 / scale_percent
        
        text_boxes = []
        for i in range(len(data['text'])):
            if data['conf'][i] > 20 and data['text'][i].strip():  # Only include high-confidence text
                box = {
                    'text': data['text'][i],
                    'x': int(data['left'][i] * scale_factor),
                    'y': int(data['top'][i] * scale_factor),
                    'w': int(data['width'][i] * scale_factor),
                    'h': int(data['height'][i] * scale_factor),
                    'conf': data['conf'][i]
                }
                text_boxes.append(box)
        
        return text_boxes
    
    def overlay_text(self, text_mapping: Dict[str, str], output_path: str = None):
        """
        Overlay translated text onto the image, replacing detected text boxes
        
        Args:
            text_mapping: Dict mapping Japanese text -> English translation
            output_path: Path to save the result (optional)
            
        Returns:
            PIL Image with overlaid text
        """
        # Get text boxes
        boxes = self.get_text_boxes(language='jpn')
        
        # Create a copy to work with
        result_img = self.image_pil.copy()
        draw = ImageDraw.Draw(result_img)
        
        # Try to load a reasonable font
        try:
                        # Prefer using the project's TextExtractor which already handles tessdata/runtime
            font = ImageFont.truetype("arial.ttf", 12)
            font_small = ImageFont.truetype("arial.ttf", 10)
        except Exception:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            except Exception:
                font = ImageFont.load_default()
                font_small = font
        
        # Overlay translations
        for box in boxes:
            japanese_text = box['text'].strip()
            x, y, w, h = box['x'], box['y'], box['w'], box['h']
            
            # Look for this text in the mapping
            english_text = text_mapping.get(japanese_text, japanese_text)
            
            if english_text != japanese_text:  # Only if we have a translation
                # Draw white background to cover original text
                draw.rectangle([x, y, x + w, y + h], fill='white', outline='white')
                
                # Draw English text
                text_font = font if len(english_text) < 20 else font_small
                draw.text((x + 2, y + 2), english_text, fill='black', font=text_font)
        
        if output_path:
            result_img.save(output_path)
        
        return result_img
    
    def create_translated_page(self, full_translation: str, output_path: str = None):
        """
        Create a full translated page by overlaying all detected text with translation
        
        Args:
            full_translation: Full translated text (will be mapped intelligently to boxes)
            output_path: Path to save result
            
        Returns:
            PIL Image with full translation overlay
        """
        # Ensure TESSDATA_PREFIX is set so Tesseract can load languages
        if self.tessdata_dir:
            os.environ['TESSDATA_PREFIX'] = self.tessdata_dir
        boxes = self.get_text_boxes(language='jpn')
        
        # Simple approach: try to map translated text back to original boxes
        # (In production, you'd use a more sophisticated alignment algorithm)
        result_img = self.image_pil.copy()
        draw = ImageDraw.Draw(result_img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 11)
            font_small = ImageFont.truetype("arial.ttf", 9)
        except Exception:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
            except Exception:
                font = ImageFont.load_default()
                font_small = font
        
        # For now, overlay a footer or watermark with the translation
        # (A more sophisticated approach would align translated paragraphs to text regions)
        if full_translation:
            # Extract first 500 chars of translation for display
            trans_snippet = full_translation[:500] + ("..." if len(full_translation) > 500 else "")
            
            # Draw translation as annotation in corner
            # This is a placeholder - in production, use layout analysis to place text properly
            y_offset = 20
            max_line_width = 80
            lines = [trans_snippet[i:i+max_line_width] for i in range(0, len(trans_snippet), max_line_width)]
            
            for line in lines[:5]:  # Show first 5 lines
                draw.text((10, y_offset), line, fill='darkblue', font=font_small)
                y_offset += 20
        
        if output_path:
            result_img.save(output_path)
        
        return result_img
    
    def _group_boxes_into_lines(self, boxes):
        """Group text boxes that are on the same horizontal line"""
        if not boxes:
            return []
        
        # Sort by vertical position (y)
        sorted_boxes = sorted(boxes, key=lambda b: (b['y'], b['x']))
        
        # Group boxes that are roughly on the same line (within height tolerance)
        lines = []
        current_line = [sorted_boxes[0]]
        
        for box in sorted_boxes[1:]:
            prev = current_line[-1]
            # If boxes are on roughly the same line (y within 1.5x height)
            y_tolerance = prev['h'] * 1.5
            if abs(box['y'] - prev['y']) <= y_tolerance:
                current_line.append(box)
            else:
                # Start new line
                lines.append(current_line)
                current_line = [box]
        
        if current_line:
            lines.append(current_line)
        
        # Convert each line to a single box with combined text
        grouped = []
        for line in lines:
            # Sort boxes in line by x position (left to right)
            line.sort(key=lambda b: b['x'])
            
            # Combine text with spaces
            combined_text = ' '.join([b['text'] for b in line])
            
            # Calculate bounding box for entire line
            xs = [b['x'] for b in line]
            ys = [b['y'] for b in line]
            widths = [b['x'] + b['w'] for b in line]
            heights = [b['y'] + b['h'] for b in line]
            
            grouped.append({
                'text': combined_text,
                'x': min(xs),
                'y': min(ys),
                'w': max(widths) - min(xs),
                'h': max(heights) - min(ys),
                'conf': sum([b['conf'] for b in line]) / len(line)
            })
        
        return grouped

    def overlay_boxes_with_translation(self, translator, output_path: str = None, lang: str = 'jpn'):
        """
        Extract boxes via Google Vision if available (or tesseract CLI fallback), 
        translate each box with provided translator,
        and overlay translated text back into each box (preserving diagrams).

        Args:
            translator: an object with method `translate_text(text, context=None)`
            output_path: path to save the resulting image
            lang: OCR language code

        Returns:
            PIL Image with translations overlaid per-box
        """
        boxes = []
        
        # Try Google Vision first for better box detection
        try:
            from src.google_ocr import GoogleOCR
            google_ocr = GoogleOCR()
            if google_ocr.available:
                print('[Overlay] Using Google Vision for box detection...')
                result = google_ocr.extract_text_with_boxes(self.image_path)
                word_boxes = result['text_boxes']
                # Convert Google Vision format to our box format
                for box_data in word_boxes:
                    boxes.append({
                        'text': box_data['text'],
                        'x': box_data['x'],
                        'y': box_data['y'],
                        'w': box_data['w'],
                        'h': box_data['h'],
                        'conf': box_data.get('confidence', 90)
                    })
                print(f'[Overlay] Found {len(boxes)} text boxes from Google Vision')
            else:
                raise RuntimeError('Google Vision not available')
        except Exception as e:
            print(f'[Overlay] Google Vision failed ({e}), falling back to Tesseract...')
            # Fallback to Tesseract CLI
            tess_cmd = pytesseract.pytesseract.tesseract_cmd
            if not tess_cmd:
                tess_cmd = os.getenv('TESSERACT_PATH', 'tesseract')

            tessdata_arg = []
            if self.tessdata_dir:
                tessdata_arg = ['--tessdata-dir', self.tessdata_dir]

            cmd = [tess_cmd] + tessdata_arg + [self.image_path, 'stdout', '-l', lang, 'tsv']

            try:
                import subprocess
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                tsv = proc.stdout.decode('utf-8', errors='ignore')
            except Exception as e:
                raise RuntimeError(f"Tesseract CLI failed: {e}\n{getattr(e, 'stderr', '')}")

            # Parse TSV
            lines = [l for l in tsv.splitlines() if l.strip()]
            header = lines[0].split('\t')
            rows = [l.split('\t') for l in lines[1:]]
            for r in rows:
                try:
                    level = int(r[0])
                    text = r[-1].strip()
                    if not text:
                        continue
                    left = int(r[6])
                    top = int(r[7])
                    width = int(r[8])
                    height = int(r[9])
                    conf = float(r[10]) if r[10] != '-1' else -1
                    if conf < 10:
                        continue
                    boxes.append({'text': text, 'x': left, 'y': top, 'w': width, 'h': height, 'conf': conf})
                except Exception:
                    continue
            print(f'[Overlay] Found {len(boxes)} text boxes from Tesseract')

        # Group nearby boxes into lines/paragraphs to reduce translation calls
        if len(boxes) > 20:
            print(f'[Overlay] Grouping {len(boxes)} boxes into lines to reduce API calls...')
            grouped_boxes = self._group_boxes_into_lines(boxes)
            print(f'[Overlay] Grouped into {len(grouped_boxes)} lines')
        else:
            grouped_boxes = boxes

        # Translate each group
        translations = {}
        print(f'[Overlay] Translating {len(grouped_boxes)} text groups...')
        for i, b in enumerate(grouped_boxes):
            j = b['text']
            if i % 10 == 0 and i > 0:
                print(f'  Progress: {i}/{len(grouped_boxes)}...')
            try:
                tr = translator.translate_text(j, context='technical manual')
            except Exception:
                tr = j
            translations[j] = tr

        # Helper: choose a font that likely supports CJK + Latin
        def _load_font(size: int):
            candidates = [
                "NotoSansCJK-Regular.ttc",
                "NotoSansCJKjp-Regular.otf",
                "arialuni.ttf",
                "arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            for f in candidates:
                try:
                    return ImageFont.truetype(f, size)
                except Exception:
                    continue
            return ImageFont.load_default()
        
        def _get_text_size(font, text):
            """Get text size using getbbox (Pillow 10+) or fallback to getsize"""
            try:
                bbox = font.getbbox(text)
                return (bbox[2] - bbox[0], bbox[3] - bbox[1])
            except AttributeError:
                return font.getsize(text)

        def _wrap_cjk(text: str, font: ImageFont.ImageFont, max_width: int):
            # For CJK text, wrap by character groups to fit pixel width
            lines = []
            cur = ""
            for ch in text:
                test = cur + ch
                w, _ = _get_text_size(font, test)
                if w <= max_width:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = ch
            if cur:
                lines.append(cur)
            return lines

        # Draw onto image
        result_img = self.image_pil.copy()
        draw = ImageDraw.Draw(result_img)

        for b in boxes:
            j = b['text']
            eng = translations.get(j, j)
            x, y, w, h = b['x'], b['y'], b['w'], b['h']

            # Small padding to avoid erasing thin diagram strokes
            pad = max(2, int(min(w, h) * 0.04))
            cover_box = [x - pad, y - pad, x + w + pad, y + h + pad]
            draw.rectangle(cover_box, fill='white')

            # Determine if vertical layout is likely (taller than wide)
            is_vertical = h > (w * 1.6)

            # Start with a font size that fits box height and shrink until it fits
            # Use pixel-based sizing loop
            font_size = max(10, min(int(h * 0.8), int(w * 1.2)))
            font = _load_font(font_size)

            # For CJK, wrapping by characters; for Latin, wrap by words
            if is_vertical:
                # For vertical, draw characters stacked top->bottom
                # Find max chars per column (approx)
                # Shrink font until it fits vertically
                while font_size > 6:
                    font = _load_font(font_size)
                    line_height = _get_text_size(font, 'あ')[1]
                    if line_height * len(eng) <= h + 2:
                        break
                    font_size -= 1
                # Draw each character centered in column
                cx = x + w // 2
                cy = y + pad
                for ch in eng:
                    wch, hch = _get_text_size(font, ch)
                    draw.text((cx - wch // 2, cy), ch, fill='black', font=font)
                    cy += hch
            else:
                # Horizontal layout: wrap into lines that fit width
                # Decrease font size until wrapped height fits box
                wrapped = []
                while font_size > 6:
                    font = _load_font(font_size)
                    # If text contains CJK characters, use CJK wrap
                    if any('\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff' for c in eng):
                        wrapped = _wrap_cjk(eng, font, w - 2)
                    else:
                        # simple word wrap for Latin
                        import textwrap
                        avg_char_w = max(4, _get_text_size(font, 'abcdefghijklmnopqrstuvwxyz')[0] / 26)
                        max_chars = max(1, int((w - 2) / avg_char_w))
                        wrapped = textwrap.wrap(eng, width=max_chars)

                    total_h = sum(_get_text_size(font, line)[1] + 1 for line in wrapped)
                    if total_h <= h + 2:
                        break
                    font_size -= 1

                # Draw wrapped lines, vertically centered within box
                total_h = sum(_get_text_size(font, line)[1] + 1 for line in wrapped)
                ty = y + max(0, (h - total_h) // 2)
                for ln in wrapped:
                    lw, lh = _get_text_size(font, ln)
                    draw.text((x + 2, ty + 1), ln, fill='black', font=font)
                    ty += lh + 1

        if output_path:
            result_img.save(output_path)

        return result_img


if __name__ == "__main__":
    # Example usage
    test_image = "images_to_process/page_sample.jpg"
    
    if os.path.exists(test_image):
        overlay = TextOverlay(test_image)
        boxes = overlay.get_text_boxes(language='jpn')
        print(f"Found {len(boxes)} text boxes")
        for box in boxes[:5]:
            print(f"  '{box['text']}' at ({box['x']}, {box['y']})")
    else:
        print(f"Test image not found at {test_image}")
