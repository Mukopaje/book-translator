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
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
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
            font_path_bold = "C:/Windows/Fonts/arialbd.ttf"
            if os.path.exists(font_path) and os.path.exists(font_path_bold):
                pdfmetrics.registerFont(TTFont('Arial', font_path))
                pdfmetrics.registerFont(TTFont('Arial-Bold', font_path_bold))
                self.font_name = 'Arial'
                self.font_name_bold = 'Arial-Bold'
            else:
                self.font_name = 'Helvetica'
                self.font_name_bold = 'Helvetica-Bold'
        except:
            self.font_name = 'Helvetica'
            self.font_name_bold = 'Helvetica-Bold'

        # PDF settings
        self.page_width, self.page_height = A4
        self.margin_left = 60
        self.margin_right = 60
        self.margin_top = 80
        self.margin_bottom = 80
        self.font_size = 11
        self.line_height = self.font_size * 1.5
        self.canvas = None
        self.styles = getSampleStyleSheet()
    
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
            v_thresh = box['h'] * 3.0  # Increased threshold to 3.0
            
            for j, other in enumerate(sorted_boxes):
                if i == j: continue
                
                # Check if 'other' is vertically close
                y_dist = abs(box['y'] - other['y'])
                if y_dist > 0 and y_dist < v_thresh:
                    # If they are vertically close, they are likely part of the same text flow
                    # No longer requiring horizontal overlap as list markers are often offset
                    has_neighbor = True
                    break
            
            if has_neighbor:
                paragraph_boxes.append(box)
            elif box['w'] > page_width * 0.15: # Also keep slightly shorter but isolated lines
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
        
        # Use UNFILTERED boxes for vertical gap detection to avoid missing lists
        sorted_boxes_all = sorted(text_boxes, key=lambda b: (b['y'], b['x']))
        
        # Identify vertical gaps (potential diagram regions)
        page_sections = []
        current_section_boxes = []
        last_bottom = 0
        gap_threshold = 120  # pixels - slightly more conservative
        
        for box in sorted_boxes_all:
            box_top = box['y']
            gap = box_top - last_bottom
            
            if gap > gap_threshold and current_section_boxes:
                # Large gap detected - candidate for diagram
                # Check how many boxes were in this candidate "gap" from the unfiltered set
                # (Actually, in this loop, we just ending the text section)
                section_start = current_section_boxes[0]['y']
                section_end = last_bottom
                page_sections.append({
                    'type': 'text',
                    'boxes': [b for b in filtered_boxes if section_start <= b['y'] <= section_end],
                    'y_start': section_start,
                    'y_end': section_end
                })
                
                # Check for content in the gap itself
                gap_start = section_end
                gap_end = box_top
                gap_boxes = [b for b in text_boxes if gap_start < b['y'] < gap_end]
                
                # DIAGRAM VETO: If there are many text boxes in the gap, it's not a diagram
                if len(gap_boxes) < 8: # Very strict - diagrams should be mostly empty of OCR text
                    page_sections.append({
                        'type': 'diagram',
                        'y_start': gap_start,
                        'y_end': gap_end,
                        'height': gap_end - gap_start,
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
            
        # --- NEW: Detect Side-Diagrams (e.g. Page 22) ---
        for section in page_sections:
            if section['type'] == 'text':
                boxes = section['boxes']
                if not boxes: continue
                
                min_x = min(b['x'] for b in boxes)
                max_x = max(b['x'] + b['w'] for b in boxes)
                
                # If text is confined to one side (less than 75% width)
                # and there's a significant empty space on the other side
                if (max_x < self.width * 0.75) and (self.width - max_x > 200):
                    # Potential diagram on the RIGHT
                    section['side_diagram'] = {
                        'type': 'diagram',
                        'y_start': section['y_start'],
                        'y_end': section['y_end'],
                        'height': section['y_end'] - section['y_start'],
                        'x': max_x + 20,
                        'w': self.width - max_x - 40,
                        'side': 'right'
                    }
                elif (min_x > self.width * 0.25) and (min_x > 200):
                    # Potential diagram on the LEFT
                    section['side_diagram'] = {
                        'type': 'diagram',
                        'y_start': section['y_start'],
                        'y_end': section['y_end'],
                        'height': section['y_end'] - section['y_start'],
                        'x': 20,
                        'w': min_x - 40,
                        'side': 'left'
                    }
                
                # --- NEW: Detect Vertical Seams (Two-Column Text) ---
                if 'side_diagram' not in section and len(boxes) >= 4:
                    # Check for a vertical seam (empty space) in the middle of the section
                    mid_start = self.width * 0.35
                    mid_end = self.width * 0.65
                    
                    has_mid_content = False
                    for b in boxes:
                        # Box midpoint
                        bcx = b['x'] + b['w'] / 2
                        if mid_start < bcx < mid_end:
                            has_mid_content = True
                            break
                    
                    if not has_mid_content:
                        # Double check: do we have content on BOTH sides?
                        has_left = any(b['x'] + b['w'] < self.width * 0.45 for b in boxes)
                        has_right = any(b['x'] > self.width * 0.55 for b in boxes)
                        
                        if has_left and has_right:
                            section['is_multi_column'] = True
                            print(f"  [Reconstructor] Detected two-column layout (seam) at Y={section['y_start']}")
        
        # If there's a large gap at the bottom of the page after the last text,
        # treat it as a potential diagram region as well.
        remaining_gap = self.height - last_bottom
        if remaining_gap > gap_threshold:
            diag_start = last_bottom
            diag_end = self.height
            page_sections.append({
                'type': 'diagram',
                'y_start': diag_start,
                'y_end': diag_end,
                'height': diag_end - diag_start,
                'x': 0,
                'w': self.width
            })

        merged_sections = []
        if page_sections:
            merged_sections.append(page_sections[0])
            for i in range(1, len(page_sections)):
                prev = merged_sections[-1]
                curr = page_sections[i]
                
                # Merge logic: if two diagrams are separated by a very small gap OR
                # by very short text that is likely a label/dimension between parts.
                if prev['type'] == 'diagram' and curr['type'] == 'diagram':
                    gap = curr['y_start'] - prev['y_end']
                    if gap < 200: # Tightened gap to 200px
                        prev['y_end'] = curr['y_end']
                        prev['height'] = prev['y_end'] - prev['y_start']
                        continue
                
                if (prev['type'] == 'diagram' and curr['type'] == 'text' and 
                    i + 1 < len(page_sections) and page_sections[i+1]['type'] == 'diagram'):
                    
                    # Merge if the text section is very small (captions between diagram views)
                    if (curr['y_end'] - curr['y_start'] < 60): # Very small caption/dimension
                        next_diag = page_sections[i+1]
                        prev['y_end'] = next_diag['y_end']
                        prev['height'] = prev['y_end'] - prev['y_start']
                        continue

                merged_sections.append(curr)
        
        # Clean up diagram bounds: ensure they don't overwrite text
        # (Though current logic is strict start/end, merging can overlap)
        # Refine diagram sections using all OCR boxes to avoid truncation and
        # give extra space at the bottom of figures.
        if merged_sections:
            paragraph_box_ids = set(id(b) for b in filtered_boxes)
            for section in merged_sections:
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
                bottom_pad = 200  # INCREASED from 140 to 200 to avoid truncation (Page 41 fix)

                refined_y_start = max(0, content_top - top_pad)
                refined_y_end = min(self.height, content_bottom + bottom_pad)

                # For full-width diagrams, use refined Y. For side-diagrams, keep original Y band.
                if section.get('x', 0) == 0 and section.get('w', self.width) == self.width:
                    section['y_start'] = refined_y_start
                    section['y_end'] = refined_y_end
                
                section['height'] = section['y_end'] - section['y_start']

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
        for section in merged_sections:
            if section['type'] == 'text':
                para_groups = self._group_into_paragraphs(section['boxes'])
                for para in para_groups:
                    paragraphs.append({
                        'boxes': para,
                        'y_position': para[0]['y']
                    })
        
        # Identify diagram regions
        diagram_regions = []
        for section in merged_sections:
            if section['type'] == 'diagram':
                diagram_regions.append({
                    'x': section.get('x', 0),
                    'y': section['y_start'],
                    'w': section.get('w', self.width),
                    'h': section['height'],
                    'position_in_flow': section['y_start']
                })
        
        return {'paragraphs': paragraphs, 'diagram_regions': diagram_regions, 'page_sections': merged_sections}
    
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
    
    def reconstruct_pdf(self, text_boxes, output_path, translator=None, full_page_japanese=None, translated_diagrams=None, book_context=None, table_artifacts=None, chart_artifacts=None, render_capture=None, translated_paragraphs=None):
        """
        Intelligently reconstruct the PDF with proper layout
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
            # Include single digits, digits in brackets/circles, and more technical codes
            critical_patterns = [
                r"^\d+$",               # Pure numbers
                r"^\(\d+\)$",           # (1), (2), etc
                r"^\[\d+\]$",           # [1], [2], etc
                r"^[a-z]\d*$",          # a, b, v1, p2, etc
                r"^[a-z]{2}\d*$"        # pa, pb, va, vb, etc
            ]
            for pattern in critical_patterns:
                if re.match(pattern, cleaned):
                    return True
            return False

        print(f"Analyzing document layout structure...")
        page_number = None
        
        # Try to extract page number from text boxes first (before layout analysis)
        # Look for page number in top-right area of page (common location)
        if text_boxes:
            # Sort boxes by y position (top to bottom)
            sorted_boxes = sorted(text_boxes, key=lambda b: (b.get('y', 0), b.get('x', 0)))
            # Check first 20 boxes (top of page)
            for box in sorted_boxes[:20]:
                text = box.get('text', '').strip()
                if not text:
                    continue
                # Check if box is in top-right area (right 30% of page, top 15% of page)
                box_x = box.get('x', 0)
                box_y = box.get('y', 0)
                if box_x > self.width * 0.7 and box_y < self.height * 0.15:
                    # Try to match page number pattern: "- 25 -" or "— 25 —"
                    m = re.search(r"(?:-|\u2014)\s*(\d{1,3})\s*(?:-|\u2014)", text)
                    if m:
                        page_number = m.group(1)
                        print(f"  Found page number from OCR box: {page_number}")
                        break
                    # Also try bare number if it's isolated
                    if re.match(r"^\s*\d{1,3}\s*$", text):
                        val = int(text.strip())
                        if 1 <= val <= 999:
                            page_number = text.strip()
                            print(f"  Found page number from OCR box: {page_number}")
                            break
        
        # Analyze the layout
        layout = self._analyze_layout_structure(text_boxes)
        
        print(f"  Found {len(layout['paragraphs'])} paragraphs")
        print(f"  Found {len(layout['diagram_regions'])} diagram regions")
        print(f"  Total sections: {len(layout['page_sections'])}")
        
        # If page number not found from text boxes, try from full_page_japanese if available
        if page_number is None and full_page_japanese:
            lines = full_page_japanese.split('\n')
            # Pass 1: Find the page number line - format "- NN -" or "— NN —"
            for idx, line in enumerate(lines[:8]):  # Check only first 8 lines
                stripped = line.strip()
                m = re.search(r"(?:^|\s)(?:-|\u2014)\s*(\d{1,3})\s*(?:-|\u2014)(?:\s|$)", stripped)
                if m:
                    page_number = m.group(1)
                    print(f"  Found page number from full_page_japanese: {page_number}")
                    break
        
        # Decide which translated paragraphs to use
        if translated_paragraphs is not None:
            print(f"  Using pre-translated paragraphs ({len(translated_paragraphs)} items)")
        elif translator and full_page_japanese:
            print(f"  Translating full page text with complete context...")
            print(f"  Japanese text: {len(full_page_japanese)} characters")

            lines = full_page_japanese.split('\n')

            # Pass 1: Find the page number line and mark its index
            # High priority: format "- NN -" or "— NN —" (canonical manual style)
            page_number_line_idx = None
            for idx, line in enumerate(lines[:8]):  # Check only first 8 lines
                stripped = line.strip()
                # Strict pattern: dashes or em-dashes around 1-3 digits
                m = re.search(r"(?:^|\s)(?:-|\u2014)\s*(\d{1,3})\s*(?:-|\u2014)(?:\s|$)", stripped)
                if m:
                    page_number = m.group(1)
                    page_number_line_idx = idx
                    break
                
            # Pass 2: If no dashed format, try bare 1-3 digit number BUT it must be line 1 or 2
            # and it must NOT look like a dimension (no decimal points, no units)
            if page_number is None:
                for idx, line in enumerate(lines[:3]):
                    stripped = re.sub(r"[()\[\]\s]", "", line)
                    if re.match(r"^\d{1,3}$", stripped):
                        # Ensure it's not a common coordinate/dimension like 0 or 1000
                        val = int(stripped)
                        if 1 <= val <= 999:
                            # Final check: it should be isolated
                            if re.match(r"^\s*[()\[\]\s]*\d{1,3}[()\[\]\s]*$", line):
                                page_number = stripped
                                page_number_line_idx = idx
                                break

            # Pass 3: Build cleaned lines, skipping the page-number line and initial noise
            cleaned_lines = []
            for idx, line in enumerate(lines):
                if idx == page_number_line_idx:
                    continue
                # Skip empty lines or noise symbols at the very start
                if idx < 3 and line.strip() in ['()', '( )', '[]', '[ ]', '']:
                    continue
                cleaned_lines.append(line)

            cleaned_japanese = "\n".join(cleaned_lines)

            # Add book context to translation request
            trans_context = "technical manual - preserve paragraph breaks and structure"
            if book_context:
                trans_context = f"{trans_context}. Book Context: {book_context}"
            
            try:
                full_translation = translator.translate_text(
                    cleaned_japanese,
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
        self.canvas = c
        
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
        legend_items = []  # Initialize legend items list for diagram annotations
        
        # Helpers to render artifacts
        def _render_table(table_artifact):
            nonlocal current_y
            print(f"[Reconstructor] ⚠️  RENDERING TABLE ARTIFACT: {table_artifact.id} ({table_artifact.rows}x{table_artifact.cols})")
            print(f"[Reconstructor] ⚠️  Table has {len(table_artifact.cells)} cells")
            print(f"[Reconstructor] ⚠️  Sample cells: {[c.text[:20] for c in table_artifact.cells[:5]]}")
            rows = table_artifact.rows
            cols = table_artifact.cols
            cells = table_artifact.cells
            
            if not cells:
                return

            # Prepare data in a list of lists format for ReportLab Table
            data = [["" for _ in range(cols)] for _ in range(rows)]
            span_commands = []
            
            # Use a style for paragraphs to allow for text wrapping
            styles = getSampleStyleSheet()
            style = styles['Normal']
            style.fontName = self.font_name
            style.fontSize = 8
            style.leading = 10

            for cell in cells:
                r, c_idx = cell.row, cell.col
                # Safety check: skip cells that fall outside the grid (should be handled by agent, but stay safe)
                if r >= rows or c_idx >= cols or r < 0 or c_idx < 0:
                    continue
                    
                text = cell.translation or cell.text or ""
                # Wrap cell content in a Paragraph object
                data[r][c_idx] = Paragraph(text.replace('\\n', '<br/>'), style)
                
                # Handle spans if they exist (though our current detector doesn't find them)
                row_span = getattr(cell, 'row_span', 1)
                col_span = getattr(cell, 'col_span', 1)
                if row_span > 1 or col_span > 1:
                    # Final safety check for span range
                    if r + row_span <= rows and c_idx + col_span <= cols:
                        span_commands.append(('SPAN', (c_idx, r), (c_idx + col_span - 1, r + row_span - 1)))

            # Create the ReportLab table object
            # Set available width for the table (page width - margins)
            available_width = self.page_width - self.margin_left - self.margin_right
            
            # Explicitly calculate column widths to avoid ReportLab "negative availWidth" errors
            # and ensure column widths are at least 10 points
            col_width = max(10, available_width / max(1, cols))
            col_widths = [col_width] * cols
            
            try:
                # Create table and apply styles
                table = Table(data, colWidths=col_widths, repeatRows=1)
                
                # Professional styling
                style_list = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E0E0E0")), # Header background
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold), # Header font
                    ('FONTNAME', (0, 1), (-1, -1), self.font_name), # Body font
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                    ('TOPPADDING', (0, 0), (-1, 0), 4),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                    ('TOPPADDING', (0, 1), (-1, -1), 2),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black), # Grid lines
                    ('FONTSIZE', (0, 0), (-1, -1), 7), # Smaller font for tables
                ]
                
                table.setStyle(TableStyle(style_list))
                
                # Add span commands if any
                if span_commands:
                    for cmd in span_commands:
                        table.setStyle(TableStyle([cmd]))

                # Calculate the required height of the table on the page
                w, h = table.wrapOn(self.canvas, available_width, self.page_height)

                # If there's not enough space, start a new page
                if current_y - h < self.margin_bottom:
                    self.canvas.showPage()
                    self.canvas.setFont(self.font_name, self.font_size)
                    current_y = self.page_height - self.margin_top

                # Draw the table on the canvas
                table.drawOn(self.canvas, self.margin_left, current_y - h)
                
                # Update the current y-position
                current_y -= (h + self.line_height)
            except Exception as table_err:
                print(f"  ! Warning: Table rendering failed: {table_err}")
                # Fallback: just draw a placeholder text so the whole PDF doesn't fail
                self.canvas.setFont(self.font_name_bold, 10)
                self.canvas.drawString(self.margin_left, current_y, "[Table Data - Error Rendering]")
                current_y -= 20

        def _render_diagram_at(section, c, pdf_width, pdf_height, render_y_top, translated_diagrams):
            nonlocal current_y, at_page_top, legend_items
            
            # Determine if this is a very small inline diagram
            # Safely get section dimensions
            section_y_start = section.get('y_start', 0)
            section_y_end = section.get('y_end', section_y_start + 100)
            section_height = section.get('height', section_y_end - section_y_start)
            small_diagram = section_height < self.height * 0.18
            
            # Always define section coordinates for use in matching and fallback
            section_x = section.get('x', 0)
            section_y = section_y_start
            section_w = section.get('w', self.width)
            section_h = section_height
            
            # Find matching translated diagram if available
            diagram_image = None
            diagram_annotations = []
            
            if translated_diagrams:
                # Match by area overlap instead of just y-position for better accuracy
                
                best_match = None
                best_overlap = 0
                
                for trans_diag in translated_diagrams:
                    region = trans_diag['region']
                    reg_x = region.get('x', 0)
                    reg_y = region.get('y', 0)
                    reg_w = region.get('w', 0)
                    reg_h = region.get('h', 0)
                    
                    # Calculate overlap area
                    overlap_x = max(section_x, reg_x)
                    overlap_y = max(section_y, reg_y)
                    overlap_w = max(0, min(section_x + section_w, reg_x + reg_w) - overlap_x)
                    overlap_h = max(0, min(section_y + section_h, reg_y + reg_h) - overlap_y)
                    overlap_area = overlap_w * overlap_h
                    
                    # Calculate union area
                    section_area = section_w * section_h
                    reg_area = reg_w * reg_h
                    union_area = section_area + reg_area - overlap_area
                    
                    # Calculate IoU (Intersection over Union)
                    if union_area > 0:
                        iou = overlap_area / union_area
                        # Also check vertical position as secondary criterion (more tolerant)
                        y_dist = abs(section_y - reg_y)
                        # If IoU is good OR vertical position is close (within 100px), consider it a match
                        if iou > 0.3 or (iou > 0.1 and y_dist < 100):
                            if iou > best_overlap:
                                best_overlap = iou
                                best_match = trans_diag
                
                if best_match:
                    diagram_image = best_match['image']
                    diagram_annotations = best_match.get('annotations', [])
                    print(f"[Reconstructor] Matched diagram: IoU={best_overlap:.3f}, section_y={section_y}, region_y={reg_y}")
                else:
                    print(f"[Reconstructor] No diagram match found for section at y={section_y} (checked {len(translated_diagrams)} diagrams)")
            
            # Fallback to original crop if no translation available
            if diagram_image is None:
                # Use section coordinates (already defined above)
                # Ensure coordinates are within image bounds
                try:
                    # Recalculate section dimensions from section dict for fallback
                    section_x = section.get('x', 0)
                    section_y = section_y_start
                    section_w = section.get('w', self.width)
                    section_h = section_height
                    
                    # Ensure coordinates are within image bounds
                    section_x = max(0, min(int(section_x), self.width - 1))
                    section_y = max(0, min(int(section_y), self.height - 1))
                    section_w = max(1, min(int(section_w), self.width - section_x))
                    section_h = max(1, min(int(section_h), self.height - section_y))
                    
                    # Validate dimensions are positive
                    if section_w <= 0 or section_h <= 0:
                        print(f"[Reconstructor] Warning: Invalid diagram dimensions (w={section_w}, h={section_h}), skipping diagram.")
                        print(f"  Section: {section}")
                        print(f"  Image size: {self.width}x{self.height}")
                        return
                    
                    # Validate crop coordinates
                    crop_right = min(section_x + section_w, self.width)
                    crop_bottom = min(section_y + section_h, self.height)
                    
                    print(f"[Reconstructor] Using fallback diagram crop: x={section_x}, y={section_y}, w={section_w}, h={section_h}")
                    print(f"[Reconstructor] Crop bounds: ({section_x}, {section_y}) to ({crop_right}, {crop_bottom})")
                    print(f"[Reconstructor] Original image size: {self.width}x{self.height}")
                    
                    diagram_image = self.image.crop((
                        section_x,
                        section_y,
                        crop_right,
                        crop_bottom
                    ))
                    
                    print(f"[Reconstructor] Cropped diagram size: {diagram_image.width}x{diagram_image.height}")
                    
                    # Verify crop is not empty
                    if diagram_image.width <= 0 or diagram_image.height <= 0:
                        print(f"[Reconstructor] Error: Cropped diagram is empty ({diagram_image.width}x{diagram_image.height})")
                        return
                        
                except Exception as e:
                    print(f"[Reconstructor] Error cropping fallback diagram: {e}")
                    print(f"  Section: {section}")
                    print(f"  Image size: {self.width}x{self.height}")
                    import traceback
                    traceback.print_exc()
                    # Create a small placeholder image to prevent complete failure
                    from PIL import Image
                    diagram_image = Image.new('RGB', (100, 100), color='white')
            
            # Calculate scaled dimensions
            # Ensure diagram_image exists and has valid dimensions
            if diagram_image is None:
                print(f"[Reconstructor] Warning: No diagram image available, skipping diagram rendering")
                return
                
            if diagram_image.width <= 0 or diagram_image.height <= 0:
                print(f"[Reconstructor] Warning: Invalid diagram image dimensions ({diagram_image.width}x{diagram_image.height}), skipping")
                return
                
            side = section.get('side') # 'left', 'right' or None
            if side:
                # Side diagram: use 40% of available width
                diagram_width_pdf = (pdf_width - 120) * 0.4
                scale = diagram_width_pdf / diagram_image.width if diagram_image.width > 0 else 1.0
                diagram_height_pdf = diagram_image.height * scale
                
                if side == 'right':
                    diagram_x = pdf_width - 60 - diagram_width_pdf
                else: # left
                    diagram_x = 60
                
                # Use render_y_top (aligned with text block)
                diagram_y = render_y_top - diagram_height_pdf
            else:
                # Full-width diagram - use actual diagram image dimensions for proper scaling
                diagram_width_pdf = pdf_width - 120
                scale = 1.0  # Initialize scale to avoid NameError
                
                if diagram_image.width > 0 and diagram_image.height > 0:
                    # Calculate scale based on width constraint
                    scale_width = diagram_width_pdf / diagram_image.width
                    # Calculate resulting height
                    diagram_height_pdf = diagram_image.height * scale_width
                    
                    # Check if diagram fits on current page
                    available_height = current_y - 80  # Space from current_y to bottom margin
                    max_page_height = pdf_height - 160  # Maximum diagram height on a page (top+bottom margins)
                    
                    # If diagram doesn't fit on current page, check if we should:
                    # 1. Start new page if there's significant content above (not at top)
                    # 2. Shrink to fit current page if at top or diagram is too large for any page
                    
                    if diagram_height_pdf > available_height:
                        # Check if diagram is too large even for a fresh page
                        if diagram_height_pdf > max_page_height:
                            # Diagram is too large even for a fresh page - shrink to fit
                            scale_height = max_page_height / diagram_image.height
                            scale = min(scale_width, scale_height)
                            diagram_height_pdf = diagram_image.height * scale
                            diagram_width_pdf = diagram_image.width * scale
                            print(f"[Reconstructor] Diagram too large for any page, shrinking to fit: {diagram_width_pdf:.1f}x{diagram_height_pdf:.1f}")
                        # Only start new page if:
                        # 1. We're NOT at top of page (have significant content above)
                        # 2. Available space is very limited (<20% of page)
                        # 3. Shrinking would make diagram too small (<60% of original size)
                        elif (not at_page_top and 
                              available_height < max_page_height * 0.2 and
                              (available_height / diagram_image.height) < 0.6):
                            # Start new page only if shrinking would make it too small
                            print(f"[Reconstructor] Starting new page for diagram (available={available_height:.1f}, would shrink to {(available_height/diagram_image.height)*100:.1f}%)")
                            c.showPage()
                            c.setFillColorRGB(1, 1, 1)
                            c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
                            c.setFillColor(black)
                            c.setFont(self.font_name, font_size)
                            current_y = pdf_height - 80
                            at_page_top = True
                            
                            # Render page number on new page if available
                            if page_number is not None:
                                header_text = f"Page {page_number}"
                                c.setFont(self.font_name, 11)
                                header_width = c.stringWidth(header_text, self.font_name, 11)
                                header_y = pdf_height - 40
                                center_x = (pdf_width - header_width) / 2
                                c.drawString(center_x, header_y, header_text)
                                print(f"[Reconstructor] Rendered page number on new diagram page: {header_text}")
                                c.setFont(self.font_name, font_size)
                                current_y = header_y - 20  # Space below page number
                                at_page_top = False
                            
                            # Recalculate with new current_y
                            available_height = current_y - 80
                            # Recalculate scale for new page
                            scale_width = diagram_width_pdf / diagram_image.width
                            if diagram_height_pdf > available_height:
                                scale_height = available_height / diagram_image.height
                                scale = min(scale_width, scale_height)
                                diagram_height_pdf = diagram_image.height * scale
                                diagram_width_pdf = diagram_image.width * scale
                                print(f"[Reconstructor] Diagram on new page: {diagram_width_pdf:.1f}x{diagram_height_pdf:.1f}")
                        else:
                            # Shrink to fit current page (preferred approach)
                            scale_height = available_height / diagram_image.height
                            scale = min(scale_width, scale_height)
                            diagram_height_pdf = diagram_image.height * scale
                            diagram_width_pdf = diagram_image.width * scale
                            shrink_percent = (scale / scale_width) * 100
                            print(f"[Reconstructor] Shrinking diagram to fit current page: {diagram_width_pdf:.1f}x{diagram_height_pdf:.1f} ({shrink_percent:.1f}% of original size)")
                    else:
                        # Diagram fits - use width-based scale
                        scale = scale_width
                else:
                    print(f"[Reconstructor] Warning: Diagram image has invalid dimensions ({diagram_image.width}x{diagram_image.height})")
                    scale = 1.0
                    diagram_height_pdf = section_height if section_height > 0 else 200
                    if diagram_image.width > 0:
                        diagram_width_pdf = diagram_image.width * scale
                
                # Position diagram
                diagram_y = current_y - diagram_height_pdf
                diagram_x = (pdf_width - diagram_width_pdf) / 2
                
                # Ensure diagram doesn't go below bottom margin
                if diagram_y < 80:
                    print(f"[Reconstructor] Warning: Diagram would overflow bottom margin (y={diagram_y:.1f}), adjusting...")
                    diagram_y = 80
                    # Recalculate height to fit
                    available_from_top = current_y - 80
                    if available_from_top > 0:
                        scale_height = available_from_top / diagram_image.height
                        scale = min(scale, scale_height)
                        diagram_height_pdf = diagram_image.height * scale
                        diagram_width_pdf = diagram_image.width * scale

            # Draw the image - use preserveAspectRatio and better quality settings
            # Convert to RGB if needed for better rendering quality
            if hasattr(diagram_image, 'mode') and diagram_image.mode != 'RGB':
                diagram_image = diagram_image.convert('RGB')
            
            img_reader = ImageReader(diagram_image)
            print(f"[Reconstructor] Drawing diagram: x={diagram_x:.1f}, y={diagram_y:.1f}, w={diagram_width_pdf:.1f}, h={diagram_height_pdf:.1f}")
            print(f"[Reconstructor] Diagram image: {diagram_image.width}x{diagram_image.height}, scale={scale:.3f}")
            
            # Use preserveAspectRatio=True to ensure diagram maintains aspect ratio
            # mask='auto' handles transparency, showBoundary=0 removes border
            # Better quality rendering by ensuring proper image format
            c.drawImage(
                img_reader, 
                diagram_x, 
                diagram_y, 
                width=diagram_width_pdf, 
                height=diagram_height_pdf,
                preserveAspectRatio=True,
                mask='auto',
                showBoundary=0
            )
            
            # Draw annotations
            local_legend = []
            if diagram_annotations:
                for note in diagram_annotations:
                    orig_x, orig_y, orig_w, orig_h = note['x'], note['y'], note['w'], note['h']
                    pdf_x = diagram_x + (orig_x * scale)
                    pdf_y = diagram_y + (diagram_image.height - orig_y - orig_h/2) * scale
                    
                    text = note['text']
                    note_font_size = max(6, min(int(orig_h * 0.6 * scale), 10))
                    text_width = c.stringWidth(text, self.font_name, note_font_size)
                    box_width_pdf = orig_w * scale
                    
                    is_critical = _is_critical_label(text) or _is_critical_label(note.get('original', ''))
                    is_short = len(text) <= 20 and len(text.split()) <= 3
                    
                    if not is_critical and not small_diagram and (note_font_size < 7 or (not is_short and text_width > box_width_pdf * 1.5)):
                        marker = f"[{len(legend_items) + 1}]"
                        legend_items.append(f"{marker} {text}")
                        c.setFont(self.font_name, 8)
                        c.setFillColorRGB(1, 0, 0)
                        c.drawString(pdf_x + (box_width_pdf - c.stringWidth(marker, self.font_name, 8))/2, pdf_y, marker)
                    else:
                        c.setFont(self.font_name, note_font_size)
                        c.setFillColor(black)
                        c.drawString(pdf_x + (box_width_pdf - text_width)/2, pdf_y, text)
            
            # Update current_y only if NOT a side diagram (side diagrams are 'floating' next to text)
            if not side:
                current_y = diagram_y - line_height
            
            at_page_top = False

        def _render_chart_placeholder(artifact):
            # NO-OP: charts were requested to be removed to keep layout clean
            pass

        # Prepare artifact lists
        table_queue = list(table_artifacts or [])
        chart_queue = list(chart_artifacts or [])
        print(f"[Reconstructor] DEBUG: Received {len(table_queue)} table artifacts, {len(chart_queue)} chart artifacts")
        if table_queue:
            for i, t in enumerate(table_queue):
                print(f"[Reconstructor] DEBUG: Table {i}: {t.rows}x{t.cols} with {len(t.cells)} cells")

        # Process each section in order
        print(f"[Reconstructor] Reconstructing PDF from {len(layout['page_sections'])} sections...")
        for i, section in enumerate(layout['page_sections']):
            print(f"  [Section {i}] type={section['type']} y_range={section.get('y_start', 'N/A')}-{section.get('y_end', 'N/A')}")
            if section['type'] == 'text':
                # If we're at the start of a PDF page and we captured an
                # original page number from the Japanese text, render it as a
                # centered header (e.g., "Page 25") above the content.
                if at_page_top and page_number is not None:
                    header_text = f"Page {page_number}"
                    c.setFont(self.font_name, 11)
                    header_width = c.stringWidth(header_text, self.font_name, 11)
                    header_y = pdf_height - 40
                    center_x = (pdf_width - header_width) / 2
                    c.drawString(center_x, header_y, header_text)
                    print(f"[Reconstructor] Rendered page number header: {header_text} at y={header_y}")
                    c.setFont(self.font_name, font_size)
                    current_y = header_y - 20  # Add space below page number
                    at_page_top = False

                # NEW: Calculate how many paragraphs belong to THIS specific section
                section_para_count = len(self._group_into_paragraphs(section['boxes']))
                # If this is the last text section, just take all remaining paragraphs to be safe
                if section == [s for s in layout['page_sections'] if s['type'] == 'text'][-1]:
                    section_para_count = len(translated_paragraphs) - paragraph_index
                
                # Check for side diagram and calculate text wrap width
                side_diag = section.get('side_diagram')
                section_max_width = max_text_width
                section_margin_left = margin_left  # Always start with standard left margin
                
                if side_diag:
                    # Adjust text width to leave room for side diagram
                    available_space = pdf_width - 120 # total horizontal space inside margins (60px margins on each side)
                    # Give 60% to text, 40% to diagram (roughly)
                    if side_diag['side'] == 'right':
                        # Diagram on right, text on left - keep standard left margin
                        section_max_width = available_space * 0.6
                        section_margin_left = margin_left  # Keep at 60px
                    else: # side is 'left'
                        # Diagram on left, text on right - shift text margin right
                        section_max_width = available_space * 0.6
                        section_margin_left = margin_left + (available_space * 0.4) + 20  # Shift right by diagram width + gap
                else:
                    # No side diagram - use full width with standard margins
                    section_max_width = max_text_width
                    section_margin_left = margin_left

                # Process text paragraphs for THIS section
                start_para_idx = paragraph_index
                
                if section.get('is_multi_column'):
                    # Multi-column handling: split boxes into left and right
                    mid_line = self.width / 2
                    left_boxes = [b for b in section['boxes'] if b['x'] + b['w']/2 < mid_line]
                    right_boxes = [b for b in section['boxes'] if b['x'] + b['w']/2 > mid_line]
                    
                    lp_count = len(self._group_into_paragraphs(left_boxes))
                    rp_count = len(self._group_into_paragraphs(right_boxes))
                    
                    # Pull translated text for both columns
                    left_paras = []
                    for _ in range(lp_count):
                        if paragraph_index < len(translated_paragraphs):
                            left_paras.append(translated_paragraphs[paragraph_index])
                            paragraph_index += 1
                    
                    right_paras = []
                    for _ in range(rp_count):
                        if paragraph_index < len(translated_paragraphs):
                            right_paras.append(translated_paragraphs[paragraph_index])
                            paragraph_index += 1
                    
                    # Render side-by-side using Table to preserve alignment
                    col_width = (pdf_width - 130) / 2
                    p_style = self.styles['Normal']
                    p_style.fontName = self.font_name
                    p_style.fontSize = font_size
                    p_style.leading = line_height
                    
                    left_html = "<br/><br/>".join([p.replace('\n', '<br/>') for p in left_paras])
                    right_html = "<br/><br/>".join([p.replace('\n', '<br/>') for p in right_paras])
                    
                    data = [[
                        Paragraph(left_html, p_style),
                        Paragraph(right_html, p_style)
                    ]]
                    
                    t = Table(data, colWidths=[col_width, col_width])
                    t.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'TOP'),
                        ('LEFTPADDING', (0,0), (-1,-1), 0),
                        ('RIGHTPADDING', (0,0), (-1,-1), 10),
                    ]))
                    tw, th = t.wrap(pdf_width - 120, pdf_height)
                    
                    if current_y - th < 80:
                        c.showPage()
                        c.setFillColorRGB(1, 1, 1)
                        c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
                        c.setFillColor(black)
                        c.setFont(self.font_name, font_size)
                        current_y = pdf_height - 80
                        at_page_top = True
                    
                    t.drawOn(c, 60, current_y - th)
                    current_y -= (th + line_height)
                else:
                    # Standard Single-Column Paragraph rendering
                    for _ in range(section_para_count):
                        if paragraph_index >= len(translated_paragraphs):
                            break
                        
                        para_text = translated_paragraphs[paragraph_index]
                        paragraph_index += 1
                        
                        if not para_text.strip():
                            continue
                        
                        # Use ReportLab Paragraph for better text rendering with proper word wrapping
                        from reportlab.platypus import Paragraph as RParagraph
                        
                        # Create paragraph style with proper spacing and no indentation
                        # Create from scratch rather than inheriting to avoid unwanted styles
                        para_style = ParagraphStyle(
                            'CustomBody',
                            fontName=self.font_name,
                            fontSize=font_size,
                            leading=line_height,
                            alignment=TA_LEFT,
                            leftIndent=0,  # Explicitly set to 0 - no left indentation
                            rightIndent=0,  # No right indentation
                            firstLineIndent=0,  # No first line indentation
                            spaceBefore=0,
                            spaceAfter=line_height * 0.3,  # Small space after paragraph
                            wordWrap='CJK',  # Better word wrapping for mixed content
                            textColor=colors.black,
                        )
                        
                        # Wrap paragraph in HTML for proper rendering
                        # Escape any HTML-like content that might interfere
                        para_text_clean = para_text.strip()
                        para_html = para_text_clean.replace('\n', '<br/>').replace('<', '&lt;').replace('>', '&gt;')
                        
                        try:
                            para_obj = RParagraph(para_html, para_style)
                            
                            # Calculate height needed for this paragraph
                            para_width = section_max_width
                            para_height = para_obj.wrap(para_width, pdf_height)[1]
                            
                            # Check if we need a new page
                            if current_y - para_height < 80:
                                c.showPage()
                                c.setFillColorRGB(1, 1, 1)
                                c.rect(0, 0, pdf_width, pdf_height, fill=1, stroke=0)
                                c.setFillColor(black)
                                c.setFont(self.font_name, font_size)
                                current_y = pdf_height - 80
                                at_page_top = True
                                
                                # Render page number on new page if available
                                if page_number is not None and at_page_top:
                                    header_text = f"Page {page_number}"
                                    c.setFont(self.font_name, 11)
                                    header_width = c.stringWidth(header_text, self.font_name, 11)
                                    header_y = pdf_height - 40
                                    center_x = (pdf_width - header_width) / 2
                                    c.drawString(center_x, header_y, header_text)
                                    print(f"[Reconstructor] Rendered page number on new text page: {header_text}")
                                    c.setFont(self.font_name, font_size)
                                    current_y = header_y - 20
                                    at_page_top = False
                                    # Recalculate para height with new current_y
                                    para_height = para_obj.wrap(para_width, pdf_height)[1]
                            
                            # Draw paragraph at correct position (no extra indentation)
                            print(f"[Reconstructor] Drawing paragraph at x={section_margin_left}, y={current_y - para_height}, width={para_width:.1f}, height={para_height:.1f}")
                            para_obj.drawOn(c, section_margin_left, current_y - para_height)
                            current_y -= (para_height + line_height * 0.3)  # Space after paragraph
                            
                        except Exception as e:
                            print(f"[Reconstructor] Error rendering paragraph with ReportLab Paragraph: {e}")
                            # Fallback to simple text rendering
                            words = para_text.split()
                            current_line_words = []
                            
                            for word in words:
                                test_line = ' '.join(current_line_words + [word])
                                text_width = c.stringWidth(test_line, self.font_name, font_size)
                                
                                if text_width <= section_max_width:
                                    current_line_words.append(word)
                                else:
                                    if current_line_words:
                                        c.drawString(section_margin_left, current_y, ' '.join(current_line_words))
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
                                c.drawString(section_margin_left, current_y, ' '.join(current_line_words))
                                current_y -= line_height
                            
                            # Space between paragraphs
                            current_y -= line_height * 0.3
                
                # Render the side diagram, if any
                if side_diag:
                    diag_y_top = current_y + (paragraph_index - start_para_idx) * (line_height * 2) # rough estimate of top
                    # Actually, we want to render it at the Y band where it was on the original page
                    # if possible, or relative to the current text block.
                    # Best: Put it at the current_y but slightly up to align with the text block
                    para_height = (paragraph_index - start_para_idx) * (line_height * 1.8)
                    diag_render_y_top = current_y + para_height
                    
                    _render_diagram_at(
                        side_diag, 
                        c, 
                        pdf_width, 
                        pdf_height, 
                        diag_render_y_top,
                        translated_diagrams
                    )

                # After a text section, render one table and one chart if available
                if table_queue:
                    print(f"[Reconstructor] DEBUG: About to render table from queue ({len(table_queue)} remaining)")
                    _render_table(table_queue.pop(0))
                if chart_queue:
                    _render_chart_placeholder(chart_queue.pop(0))
                    
            elif section['type'] == 'diagram':
                # Render using the unified helper
                _render_diagram_at(
                    section, 
                    c, 
                    pdf_width, 
                    pdf_height, 
                    current_y, 
                    translated_diagrams
                )
                # Draw Legend if needed
                if legend_items:
                    current_y -= 10
                    c.setFont(self.font_name_bold, 9)
                    c.drawString(60, current_y, "Diagram Key:")
                    current_y -= 12
                    c.setFont(self.font_name, 8)
                    
                    for item in legend_items:
                        if current_y < 80:
                            c.showPage()
                            current_y = pdf_height - 80
                            c.setFont(self.font_name, 8)
                        c.drawString(70, current_y, item)
                        current_y -= 12
                    
                    legend_items = []
                    current_y -= 10

        # If any remaining artifacts, render them at the end
        while table_queue:
            _render_table(table_queue.pop(0))
        while chart_queue:
            _render_chart_placeholder(chart_queue.pop(0))
        
        c.save()
        print(f"[OK] Smart layout PDF created: {output_path}")
        return output_path
