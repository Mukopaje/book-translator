"""
Smart Layout Reconstructor
Uses intelligent analysis to preserve original document structure
"""

import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import re


class SmartLayoutReconstructor:
    """
    Intelligently reconstructs document layout:
    - Identifies paragraph boundaries
    - Detects diagram/image regions
    - Preserves original spacing and flow
    - Creates clean PDF with proper formatting
    """
    
    def __init__(self, image_path):
        self.image_path = image_path
        self.image = Image.open(image_path)
        self.width, self.height = self.image.size
        
        # Setup font
        try:
            font_path = "C:/Windows/Fonts/arial.ttf"
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Arial', font_path))
                self.font_name = 'Arial'
            else:
                self.font_name = 'Helvetica'
        except:
            self.font_name = 'Helvetica'
    
    def _filter_paragraph_boxes(self, text_boxes):
        """
        Filter text boxes to identify main paragraph content vs diagram labels.
        Returns boxes that are likely part of the main text flow.
        """
        if not text_boxes:
            return []
            
        # Calculate page width statistics if possible, or use image width
        page_width = self.width
        
        paragraph_boxes = []
        sorted_boxes = sorted(text_boxes, key=lambda b: b['y'])
        
        for i, box in enumerate(sorted_boxes):
            # Criteria 1: Width
            # If text is wide (e.g. > 30% of page), it's likely a sentence/paragraph line
            if box['w'] > page_width * 0.3:
                paragraph_boxes.append(box)
                continue
                
            # Criteria 2: Connectivity (Vertical neighbors)
            has_neighbor = False
            v_thresh = box['h'] * 2.5  # Allow for some line spacing
            
            for j, other in enumerate(sorted_boxes):
                if i == j: continue
                
                # Check if 'other' is vertically close
                y_dist = abs(box['y'] - other['y'])
                if y_dist > 0 and y_dist < v_thresh:
                    # Check horizontal alignment (left aligned or centered)
                    # Overlap check
                    if (box['x'] < other['x'] + other['w'] and box['x'] + box['w'] > other['x']):
                        has_neighbor = True
                        break
            
            if has_neighbor:
                paragraph_boxes.append(box)
            
            # Note: Short, isolated text is likely a diagram label and is filtered out
            
        return paragraph_boxes

    def _analyze_layout_structure(self, text_boxes):
        """
        Analyze the document structure to identify:
        - Text regions grouped into paragraphs
        - Empty regions (likely diagrams/images)
        - Reading order and flow
        """
        if not text_boxes:
            return {'paragraphs': [], 'diagram_regions': [], 'page_sections': []}
        
        # Filter out diagram labels to find main structure
        # This ensures that text inside diagrams doesn't break the diagram region detection
        filtered_boxes = self._filter_paragraph_boxes(text_boxes)
        
        # Sort boxes top to bottom
        sorted_boxes = sorted(filtered_boxes, key=lambda b: (b['y'], b['x']))
        
        # Identify vertical gaps (potential diagram regions)
        page_sections = []
        current_section_boxes = []
        last_bottom = 0
        gap_threshold = 100  # pixels - significant gap indicates new section
        padding = 40  # NEW: Increased padding to 40px to avoid cutting edges
        
        for box in sorted_boxes:
            box_top = box['y']
            gap = box_top - last_bottom
            
            if gap > gap_threshold and current_section_boxes:
                # Large gap detected - end current section
                page_sections.append({
                    'type': 'text',
                    'boxes': current_section_boxes,
                    'y_start': current_section_boxes[0]['y'],
                    'y_end': last_bottom
                })
                
                # Add gap section (likely diagram)
                # Expand region slightly to avoid cutting
                # Increased padding to 100px to ensure full diagram capture (especially bottom labels)
                diag_start = max(0, last_bottom - 100)
                diag_end = min(self.height, box_top + 100)
                
                page_sections.append({
                    'type': 'diagram',
                    'y_start': diag_start,
                    'y_end': diag_end,
                    'height': diag_end - diag_start,
                    'x': 0,
                    'w': self.width
                })
                
                current_section_boxes = [box]
            else:
                current_section_boxes.append(box)
            
            last_bottom = max(last_bottom, box['y'] + box['h'])
        
        # Add final text section, if any
        if current_section_boxes:
            page_sections.append({
                'type': 'text',
                'boxes': current_section_boxes,
                'y_start': current_section_boxes[0]['y'],
                'y_end': last_bottom
            })
        
        # If there's a large gap at the bottom of the page after the last text,
        # treat it as a potential diagram region as well.
        remaining_gap = self.height - last_bottom
        if remaining_gap > gap_threshold:
            diag_start = max(0, last_bottom - 100)
            diag_end = self.height
            page_sections.append({
                'type': 'diagram',
                'y_start': diag_start,
                'y_end': diag_end,
                'height': diag_end - diag_start,
                'x': 0,
                'w': self.width
            })
        
        # Refine diagram sections using all OCR boxes to avoid truncation and
        # give extra space at the bottom of figures.
        if page_sections:
            paragraph_box_ids = set(id(b) for b in filtered_boxes)
            for section in page_sections:
                if section['type'] != 'diagram':
                    continue

                y0 = section['y_start']
                y1 = section['y_end']

                # Use all boxes intersecting this vertical band to estimate content bounds
                boxes_in_band = [
                    b for b in text_boxes
                    if (b['y'] + b['h'] > y0) and (b['y'] < y1)
                ]

                if not boxes_in_band:
                    # Ensure defaults for horizontal span
                    section.setdefault('x', 0)
                    section.setdefault('w', self.width)
                    continue

                content_top = min(b['y'] for b in boxes_in_band)
                content_bottom = max(b['y'] + b['h'] for b in boxes_in_band)

                top_pad = 60
                bottom_pad = 140  # extra bottom room to avoid truncating shapes

                refined_y_start = max(0, content_top - top_pad)
                refined_y_end = min(self.height, content_bottom + bottom_pad)

                section['y_start'] = refined_y_start
                section['y_end'] = refined_y_end
                section['height'] = refined_y_end - refined_y_start

                # Now tighten horizontal span around non-paragraph (likely diagram) boxes
                label_boxes = [
                    b for b in boxes_in_band
                    if id(b) not in paragraph_box_ids and b.get('text', '').strip()
                ]

                if label_boxes:
                    min_x = min(b['x'] for b in label_boxes)
                    max_x = max(b['x'] + b['w'] for b in label_boxes)
                    pad_x = 40
                    new_x = max(0, min_x - pad_x)
                    new_right = min(self.width, max_x + pad_x)
                    section['x'] = new_x
                    section['w'] = max(0, new_right - new_x)
                else:
                    section.setdefault('x', 0)
                    section.setdefault('w', self.width)
        
        # Group text sections into paragraphs
        paragraphs = []
        for section in page_sections:
            if section['type'] == 'text':
                para_groups = self._group_into_paragraphs(section['boxes'])
                for para in para_groups:
                    paragraphs.append({
                        'boxes': para,
                        'y_position': para[0]['y']
                    })
        
        # Identify diagram regions
        diagram_regions = []
        for section in page_sections:
            if section['type'] == 'diagram':
                diagram_regions.append({
                    'x': section.get('x', 0),
                    'y': section['y_start'],
                    'w': section.get('w', self.width),
                    'h': section['height'],
                    'position_in_flow': section['y_start']
                })
        
        return {
            'paragraphs': paragraphs,
            'diagram_regions': diagram_regions,
            'page_sections': page_sections
        }
    
    def _group_into_paragraphs(self, boxes):
        """Group text boxes into logical paragraphs based on positioning"""
        if not boxes:
            return []
        
        paragraphs = []
        current_para = []
        last_y = None
        line_height_tolerance = 50  # Tolerance for same paragraph
        
        sorted_boxes = sorted(boxes, key=lambda b: (b['y'], b['x']))
        
        for box in sorted_boxes:
            if last_y is None or abs(box['y'] - last_y) <= line_height_tolerance:
                current_para.append(box)
            else:
                # New paragraph detected
                if current_para:
                    paragraphs.append(current_para)
                current_para = [box]
            
            last_y = box['y']
        
        if current_para:
            paragraphs.append(current_para)
        
        return paragraphs
    
    def _combine_paragraph_text(self, paragraph_boxes):
        """Combine text from paragraph boxes into coherent text"""
        # Sort by position
        sorted_boxes = sorted(paragraph_boxes, key=lambda b: (b['y'], b['x']))
        
        # Group into lines
        lines = []
        current_line = []
        last_y = None
        tolerance = 20
        
        for box in sorted_boxes:
            if 'translation' not in box or not box['translation']:
                continue
            
            if last_y is None or abs(box['y'] - last_y) <= tolerance:
                current_line.append(box)
                last_y = box['y'] if last_y is None else last_y
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [box]
                last_y = box['y']
        
        if current_line:
            lines.append(current_line)
        
        # Combine lines into paragraph text
        paragraph_text = []
        for line in lines:
            line_boxes = sorted(line, key=lambda b: b['x'])
            line_text = ' '.join([b['translation'].strip() for b in line_boxes if b['translation'].strip()])
            if line_text:
                paragraph_text.append(line_text)
        
        return ' '.join(paragraph_text)
    
    def _translate_paragraphs_individually(self, paragraphs, translator):
        """Fallback: translate each paragraph individually"""
        translations = []
        for i, para in enumerate(paragraphs):
            japanese_texts = []
            for box in para['boxes']:
                if 'text' in box and box['text']:
                    japanese_texts.append(box['text'])
            
            paragraph_japanese = ' '.join(japanese_texts)
            
            if paragraph_japanese.strip():
                try:
                    para_translation = translator.translate_text(
                        paragraph_japanese,
                        context="technical manual",
                        source_lang='ja',
                        target_lang='en'
                    )
                    translations.append(para_translation)
                except:
                    translations.append(paragraph_japanese)
            else:
                translations.append("")
        
        return translations
    
    def reconstruct_pdf(self, text_boxes, output_path, translator=None, full_page_japanese=None, translated_diagrams=None, book_context=None):
        """
        Intelligently reconstruct the PDF with proper layout
        If translator and full_page_japanese provided, translates entire page with full context
        If translated_diagrams provided, uses them instead of extracting from original image
        
        Args:
            translated_diagrams: List of dicts with 'image' (PIL Image) and 'region' (position info)
            book_context: Optional global context about the book
        """
        def _is_critical_label(text):
            """Return True for short, important diagram tokens like A, B, P1, P2, V1, V2.

            Both current English text and original text are checked by the
            caller. Non-alphanumeric chars are stripped before comparison.
            """
            if not text:
                return False
            cleaned = re.sub(r"[^A-Za-z0-9]", "", str(text)).lower()
            if not cleaned:
                return False
            return cleaned in {
                "a", "b", "p", "v",
                "p1", "p2", "v1", "v2",
                "pa", "pb", "pc", "va", "vb", "vc"
            }

        print(f"Analyzing document layout structure...")
        
        # Analyze the layout
        layout = self._analyze_layout_structure(text_boxes)
        
        print(f"  Found {len(layout['paragraphs'])} paragraphs")
        print(f"  Found {len(layout['diagram_regions'])} diagram regions")
        print(f"  Total sections: {len(layout['page_sections'])}")
        
        # Better approach: Translate the entire page text with full context (like OpenAI approach)
        if translator and full_page_japanese:
            print(f"  Translating full page text with complete context...")
            print(f"  Japanese text: {len(full_page_japanese)} characters")
            
            # Add book context to translation request
            trans_context = "technical manual - preserve paragraph breaks and structure"
            if book_context:
                trans_context = f"{trans_context}. Book Context: {book_context}"
            
            try:
                full_translation = translator.translate_text(
                    full_page_japanese,
                    context=trans_context,
                    source_lang='ja',
                    target_lang='en'
                )
                print(f"  English text: {len(full_translation)} characters")
                
                # Split translation into paragraphs
                translated_paragraphs = [p.strip() for p in full_translation.split('\n\n') if p.strip()]
                if not translated_paragraphs:
                    translated_paragraphs = [p.strip() for p in full_translation.split('\n') if p.strip()]
                
                print(f"  Split into {len(translated_paragraphs)} translated paragraphs")
                
            except Exception as e:
                print(f"  Warning: Full page translation failed: {e}")
                print(f"  Falling back to paragraph-by-paragraph translation...")
                translated_paragraphs = self._translate_paragraphs_individually(layout['paragraphs'], translator)
        else:
            # Fallback to paragraph translation
            translated_paragraphs = self._translate_paragraphs_individually(layout['paragraphs'], translator)
        
        # Create PDF
        pdf_width, pdf_height = A4
        c = canvas.Canvas(output_path, pagesize=A4)
        
        # White background
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
        
        # Setup text
        c.setFillColor(black)
        font_size = 11
        c.setFont(self.font_name, font_size)
        line_height = font_size * 1.5
        
        margin_left = 60
        margin_right = pdf_width - 60
        max_text_width = margin_right - margin_left
        current_y = pdf_height - 80
        at_page_top = True
        
        paragraph_index = 0
        
        # Process each section in order
        for section in layout['page_sections']:
            if section['type'] == 'text':
                # Process text paragraphs
                for i in range(len(layout['paragraphs'])):
                    if paragraph_index >= len(translated_paragraphs):
                        break
                    
                    para_text = translated_paragraphs[paragraph_index]
                    paragraph_index += 1
                    
                    if not para_text.strip():
                        continue

                    # If we are at the very top of a page, look for a
                    # leading "-NN-" pattern (e.g., "-28- Text...") and
                    # treat it as a page header instead of mixing it with the
                    # paragraph content.
                    if at_page_top:
                        m = re.match(r"^\s*-(\d+)-\s*(.*)$", para_text)
                        if m:
                            page_num = m.group(1)
                            remaining = m.group(2).strip()

                            # Render a clean numeric header (e.g., "28")
                            header_text = page_num
                            c.setFont(self.font_name, 9)
                            header_width = c.stringWidth(header_text, self.font_name, 9)
                            header_y = pdf_height - 40
                            center_x = (pdf_width - header_width) / 2
                            c.drawString(center_x, header_y, header_text)
                            c.setFont(self.font_name, font_size)

                            at_page_top = False

                            # Use remaining text as the actual paragraph
                            para_text = remaining
                            if not para_text:
                                # No more content in this paragraph
                                continue
                    
                    # Word wrap and render paragraph
                    words = para_text.split()
                    current_line_words = []
                    
                    for word in words:
                        test_line = ' '.join(current_line_words + [word])
                        text_width = c.stringWidth(test_line, self.font_name, font_size)
                        
                        if text_width <= max_text_width:
                            current_line_words.append(word)
                        else:
                            if current_line_words:
                                c.drawString(margin_left, current_y, ' '.join(current_line_words))
                                current_y -= line_height
                                
                                if current_y < 80:
                                    c.showPage()
                                    c.setFillColorRGB(1, 1, 1)
                                    c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
                                    c.setFillColor(black)
                                    c.setFont(self.font_name, font_size)
                                    current_y = pdf_height - 80
                                    at_page_top = True
                            
                            current_line_words = [word]
                    
                    if current_line_words:
                        c.drawString(margin_left, current_y, ' '.join(current_line_words))
                        current_y -= line_height
                    
                    # Extra space between paragraphs
                    current_y -= line_height * 0.8
                    at_page_top = False
                    
            elif section['type'] == 'diagram':
                # Determine if this is a very small inline diagram (e.g. a tiny
                # PV sketch or formula). For such diagrams we prefer to draw
                # labels directly and avoid creating a separate Diagram Key.
                section_height = section.get('height', section['y_end'] - section['y_start'])
                small_diagram = section_height < self.height * 0.18

                # Find matching translated diagram if available
                diagram_image = None
                diagram_annotations = []
                
                if translated_diagrams:
                    # Match by y position
                    for trans_diag in translated_diagrams:
                        if abs(trans_diag['region']['y'] - section['y_start']) < 50:
                            diagram_image = trans_diag['image']
                            diagram_annotations = trans_diag.get('annotations', [])
                            print(f"  Using translated diagram at y={section['y_start']}")
                            break
                
                # Fallback to original crop if no translation available
                if diagram_image is None:
                    print(f"  Using original diagram at y={section['y_start']} (no translation)")
                    diagram_image = self.image.crop((
                        0,
                        section['y_start'],
                        self.width,
                        section['y_end']
                    ))
                
                # Calculate scaled dimensions
                diagram_height_pdf = section['height'] * (pdf_width / self.width)
                
                if current_y - diagram_height_pdf < 80:
                    # Start new page if diagram doesn't fit
                    c.showPage()
                    c.setFillColorRGB(1, 1, 1)
                    c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
                    c.setFillColor(black)
                    c.setFont(self.font_name, font_size)
                    current_y = pdf_height - 80
                    at_page_top = True
                
                # Scale to fit page width
                diagram_width = pdf_width - 120  # margins
                scale = diagram_width / diagram_image.width
                diagram_height_scaled = diagram_image.height * scale
                
                # Draw the diagram image (cleaned background, no text)
                img_reader = ImageReader(diagram_image)
                diagram_y = current_y - diagram_height_scaled
                c.drawImage(
                    img_reader,
                    60,
                    diagram_y,
                    width=diagram_width,
                    height=diagram_height_scaled
                )
                
                # Draw vector text annotations on top
                legend_items = []
                if diagram_annotations:
                    c.setFillColor(black)
                    for note in diagram_annotations:
                        # Scale coordinates
                        # Note: 'x' and 'y' are relative to the diagram crop
                        # We need to scale them and position them relative to the PDF page
                        
                        # Original coordinates in diagram crop
                        orig_x = note['x']
                        orig_y = note['y']
                        orig_w = note['w']
                        orig_h = note['h']
                        
                        # Scale to PDF dimensions
                        pdf_x = 60 + (orig_x * scale)
                        # PDF y is from bottom up, image y is from top down
                        # diagram_y is the bottom of the image in PDF coords
                        # We need to add (height - y) * scale
                        pdf_y = diagram_y + (diagram_image.height - orig_y - orig_h/2) * scale
                        
                        # Calculate font size
                        note_font_size = max(6, min(int(orig_h * 0.6 * scale), 10))

                        # Auto-hybrid decision: short labels go directly on the
                        # diagram, longer ones use markers + Diagram Key.
                        text = note['text']
                        original_text = note.get('original', '')
                        is_critical = _is_critical_label(text) or _is_critical_label(original_text)
                        text_width = c.stringWidth(text, self.font_name, note_font_size)
                        box_width_pdf = orig_w * scale

                        # Treat very short labels (<= 10 chars, <= 2 words) as
                        # safe to draw directly if they roughly fit the box.
                        num_words = len(text.split())
                        is_short = len(text) <= 10 and num_words <= 2

                        use_marker = False
                        # Never use markers for critical tokens (A, B, P1, P2,
                        # etc.) or for very small inline diagrams; always draw
                        # them directly on the figure.
                        if not is_critical and not small_diagram:
                            if note_font_size < 7:
                                use_marker = True
                            elif not is_short and text_width > box_width_pdf * 1.3:
                                use_marker = True

                        if use_marker:
                            # Create a marker (e.g., [1], [A])
                            marker = f"[{len(legend_items) + 1}]"
                            legend_items.append(f"{marker} {text}")
                            
                            # Draw marker on diagram
                            c.setFont(self.font_name, 8)
                            c.setFillColorRGB(1, 0, 0) # Red for visibility
                            c.drawString(pdf_x + (box_width_pdf - c.stringWidth(marker, self.font_name, 8))/2, pdf_y, marker)
                            c.setFillColor(black)
                        else:
                            # Draw text normally
                            c.setFont(self.font_name, note_font_size)
                            c.setFillColor(black)
                            c.drawString(pdf_x + (box_width_pdf - text_width)/2, pdf_y, text)
                    
                    # Reset font
                    c.setFont(self.font_name, font_size)
                
                current_y -= diagram_height_scaled + line_height
                at_page_top = False
                
                # Draw Legend if needed
                # For very small inline diagrams we suppress a separate
                # Diagram Key block to avoid cluttering the page with extra
                # legends for tiny sketches.
                if legend_items and not small_diagram:
                    c.setFont(self.font_name, 9)
                    current_y -= 10
                    c.drawString(60, current_y, "Diagram Key:")
                    current_y -= 12
                    
                    for item in legend_items:
                        # Wrap long legend items
                        if c.stringWidth(item, self.font_name, 9) > max_text_width:
                            # Simple truncation for now, could be improved
                            c.drawString(70, current_y, item[:100] + "...")
                        else:
                            c.drawString(70, current_y, item)
                        current_y -= 12
                        
                        # Page break check
                        if current_y < 80:
                            c.showPage()
                            c.setFillColorRGB(1, 1, 1)
                            c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
                            c.setFillColor(black)
                            c.setFont(self.font_name, 9)
                            current_y = pdf_height - 80
                            at_page_top = True
                    
                    current_y -= line_height
        
        c.save()
        print(f"[OK] Smart layout PDF created: {output_path}")
        return output_path
