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
import html
from diagram_overlay_renderer import DiagramOverlayRenderer


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

        # Configuration: Diagram rendering mode
        # 'overlay' = Bilingual labels (Google Translate style)
        # 'replace' = Replace Japanese with English (current method)
        self.diagram_mode = os.getenv('DIAGRAM_TRANSLATION_MODE', 'overlay')

        # Initialize diagram overlay renderer
        self.overlay_renderer = DiagramOverlayRenderer()

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

        # PDF settings - optimized for better content fitting
        self.page_width, self.page_height = A4
        self.margin_left = 50
        self.margin_right = 50
        self.margin_top = 50
        self.margin_bottom = 50
        self.font_size = 10  # Reduced from 11 for better fitting
        self.line_height = self.font_size * 1.4  # Tighter line height
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
            if box['w'] > page_width * 0.3:
                paragraph_boxes.append(box)
                continue
            has_neighbor = False
            is_short = box['w'] < page_width * 0.2
            v_thresh = box['h'] * (1.5 if is_short else 3.0)
            for j, other in enumerate(sorted_boxes):
                if i == j: continue
                y_dist = abs(box['y'] - other['y'])
                if y_dist > 0 and y_dist < v_thresh:
                    x_dist = abs(box['x'] - other['x'])
                    overlap_x = max(0, min(box['x'] + box['w'], other['x'] + other['w']) - max(box['x'], other['x']))
                    is_vertically_stacked = overlap_x > min(box['w'], other['w']) * 0.3
                    is_left_aligned = abs(box['x'] - other['x']) < 30
                    if is_vertically_stacked or is_left_aligned:
                        has_neighbor = True
                        break
            if has_neighbor:
                paragraph_boxes.append(box)
            elif box['w'] > page_width * 0.25:
                paragraph_boxes.append(box)
        return paragraph_boxes

    def _analyze_layout_structure(self, text_boxes):
        """Legacy heuristic analysis"""
        if not text_boxes:
            return {'paragraphs': [], 'diagram_regions': [], 'page_sections': []}
        filtered_boxes = self._filter_paragraph_boxes(text_boxes)
        page_sections = []
        current_section_boxes = []
        last_bottom = 0
        gap_threshold = 120
        boxes_to_analyze = sorted(filtered_boxes if filtered_boxes else text_boxes, key=lambda b: (b['y'], b['x']))
        
        for box in boxes_to_analyze:
            box_top = box['y']
            gap = box_top - last_bottom
            if gap > gap_threshold and current_section_boxes:
                section_start = current_section_boxes[0]['y']
                section_end = last_bottom
                page_sections.append({'type': 'text', 'boxes': [b for b in filtered_boxes if section_start <= b['y'] <= section_end], 'y_start': section_start, 'y_end': section_end})
                gap_start = section_end
                gap_end = box_top
                gap_boxes = [b for b in text_boxes if gap_start < b['y'] < gap_end]
                is_diagram = True
                if len(gap_boxes) >= 8:
                    long_text_count = 0
                    total_chars = 0
                    for b in gap_boxes:
                        text = b.get('text', '').strip()
                        total_chars += len(text)
                        if len(text) > 15: long_text_count += 1
                    avg_len = total_chars / len(gap_boxes) if gap_boxes else 0
                    long_ratio = long_text_count / len(gap_boxes)
                    if long_ratio > 0.3 or avg_len > 20: is_diagram = False
                
                if is_diagram:
                    page_sections.append({'type': 'diagram', 'y_start': gap_start, 'y_end': gap_end, 'height': gap_end - gap_start, 'x': 0, 'w': self.width})
                elif gap_boxes:
                    page_sections.append({'type': 'text', 'boxes': gap_boxes, 'y_start': gap_start, 'y_end': gap_end})
                current_section_boxes = [box]
            else:
                current_section_boxes.append(box)
            last_bottom = max(last_bottom, box['y'] + box['h'])
            
        if current_section_boxes:
            page_sections.append({'type': 'text', 'boxes': current_section_boxes, 'y_start': current_section_boxes[0]['y'], 'y_end': last_bottom})
        
        merged_sections = []
        if page_sections:
            merged_sections.append(page_sections[0])
            for i in range(1, len(page_sections)):
                prev = merged_sections[-1]
                curr = page_sections[i]
                if prev['type'] == 'diagram' and curr['type'] == 'diagram':
                    gap = curr['y_start'] - prev['y_end']
                    if gap < 300:
                        prev['y_end'] = max(prev['y_end'], curr['y_end'])
                        prev['height'] = prev['y_end'] - prev['y_start']
                        continue
                if prev['type'] == 'diagram' and curr['type'] == 'text':
                    text_height = curr['y_end'] - curr['y_start']
                    if text_height < 80:
                        prev['y_end'] = curr['y_end']
                        prev['height'] = prev['y_end'] - prev['y_start']
                        continue
                merged_sections.append(curr)
        page_sections = merged_sections

        paragraphs = []
        diagram_regions = []
        for section in page_sections:
            if section['type'] == 'text':
                para_groups = self._group_into_paragraphs(section['boxes'])
                for para in para_groups: paragraphs.append({'boxes': para, 'y_position': para[0]['y']})
            elif section['type'] == 'diagram':
                diagram_regions.append({'x': section.get('x', 0), 'y': section['y_start'], 'w': section.get('w', self.width), 'h': section['height'], 'position_in_flow': section['y_start']})
        return {'paragraphs': paragraphs, 'diagram_regions': diagram_regions, 'page_sections': page_sections}

    def reconstruct_from_layout_analysis(self, layout_data, text_boxes):
        print("[SmartLayout] Reconstructing from AI Layout Analysis...")
        regions = layout_data.get('regions', [])
        page_number = layout_data.get('page_number')  # Extract page number from AI
        if page_number:
            print(f"[SmartLayout] AI detected page number: {page_number}")
        page_sections = []
        regions.sort(key=lambda r: r['box_pixel']['y'])
        region_text_map = {id(r): [] for r in regions}
        unassigned_boxes = []
        for box in text_boxes:
            box_x, box_y, box_w, box_h = box['x'], box['y'], box['w'], box['h']
            box_area = box_w * box_h
            best_region = None
            max_intersection = 0
            for region in regions:
                r_box = region['box_pixel']
                ix = max(box_x, r_box['x'])
                iy = max(box_y, r_box['y'])
                iw = min(box_x + box_w, r_box['x'] + r_box['w']) - ix
                ih = min(box_y + box_h, r_box['y'] + r_box['h']) - iy
                if iw > 0 and ih > 0:
                    intersection = iw * ih
                    ioba = intersection / box_area
                    if ioba > 0.5 and intersection > max_intersection:
                        max_intersection = intersection
                        best_region = region
            if best_region: region_text_map[id(best_region)].append(box)
            else: unassigned_boxes.append(box)
            
        for region in regions:
            rtype = region.get('type')
            rbox = region.get('box_pixel')
            
            # --- Dedicated Pipeline Handling ---
            if rtype == 'technical_diagram' or rtype == 'diagram': 
                # DIAGRAM PIPELINE
                pad_x, pad_y = 30, 30
                x_start = max(0, rbox['x'] - pad_x)
                y_start = max(0, rbox['y'] - pad_y)
                x_end = min(self.width, rbox['x'] + rbox['w'] + pad_x)
                y_end = min(self.height, rbox['y'] + rbox['h'] + pad_y)
                page_sections.append({
                    'type': 'diagram',
                    'subtype': 'technical',
                    'x': x_start, 'y_start': y_start, 'y_end': y_end,
                    'w': x_end - x_start, 'height': y_end - y_start,
                    'boxes': region_text_map[id(region)]
                })
                # print(f"  [Layout] Added Technical Diagram at Y={y_start}")

            elif rtype == 'chart':
                # CHART PIPELINE
                pad_x, pad_y = 50, 50 # More padding for charts
                x_start = max(0, rbox['x'] - pad_x)
                y_start = max(0, rbox['y'] - pad_y)
                x_end = min(self.width, rbox['x'] + rbox['w'] + pad_x)
                y_end = min(self.height, rbox['y'] + rbox['h'] + pad_y)
                page_sections.append({
                    'type': 'chart', # Explicit CHART type
                    'x': x_start, 'y_start': y_start, 'y_end': y_end,
                    'w': x_end - x_start, 'height': y_end - y_start,
                    'boxes': region_text_map[id(region)]
                })
                # print(f"  [Layout] Added Chart at Y={y_start} with extra padding")

            elif rtype in ['text_block', 'caption', 'header_footer']:
                # TEXT PIPELINE
                assigned_boxes = region_text_map[id(region)]
                if assigned_boxes:
                    page_sections.append({'type': 'text', 'boxes': assigned_boxes, 'y_start': rbox['y'], 'y_end': rbox['y'] + rbox['h']})
            
            elif rtype == 'table':
                # TABLE PIPELINE
                # Don't include text boxes - the TableArtifact already has structured data
                # Including boxes here causes duplicate rendering (table + text)
                page_sections.append({
                    'type': 'table',
                    'x': rbox['x'], 'y_start': rbox['y'], 'y_end': rbox['y'] + rbox['h'],
                    'w': rbox['w'], 'height': rbox['h'],
                    'boxes': []  # Empty - table artifact has the data
                })
                print(f"  [Layout] Added Table at Y={rbox['y']}")

        # Merge Logic (Diagrams)
        merged_sections = []
        if page_sections:
            merged_sections.append(page_sections[0])
            for i in range(1, len(page_sections)):
                prev = merged_sections[-1]
                curr = page_sections[i]
                # Merge Diagram+Diagram
                if prev['type'] == 'diagram' and curr['type'] == 'diagram':
                    gap = curr['y_start'] - prev['y_end']
                    if gap < 300:
                        prev['y_end'] = max(prev['y_end'], curr['y_end'])
                        prev['height'] = prev['y_end'] - prev['y_start']
                        prev['boxes'].extend(curr.get('boxes', []))
                        continue
                merged_sections.append(curr)
        page_sections = merged_sections

        paragraphs = []
        diagram_regions = [] 
        chart_regions = []   
        
        for section in page_sections:
            if section['type'] == 'text':
                para_groups = self._group_into_paragraphs(section.get('boxes', []))
                for para in para_groups: paragraphs.append({'boxes': para, 'y_position': para[0]['y']})
            elif section['type'] == 'diagram':
                diagram_regions.append({'x': section['x'], 'y': section['y_start'], 'w': section['w'], 'h': section['height']})
            elif section['type'] == 'chart':
                chart_regions.append({'x': section['x'], 'y': section['y_start'], 'w': section['w'], 'h': section['height']})
                diagram_regions.append({'x': section['x'], 'y': section['y_start'], 'w': section['w'], 'h': section['height']})

        return {
            'paragraphs': paragraphs,
            'diagram_regions': diagram_regions,
            'chart_regions': chart_regions,
            'page_sections': page_sections,
            'page_number': page_number  # Pass page number through
        }

    def _group_into_paragraphs(self, boxes):
        if not boxes: return []
        paragraphs = []
        current_para = []
        last_y = None
        line_height_tolerance = 50
        sorted_boxes = sorted(boxes, key=lambda b: (b['y'], b['x']))
        for box in sorted_boxes:
            if last_y is None or abs(box['y'] - last_y) <= line_height_tolerance:
                current_para.append(box)
            else:
                if current_para: paragraphs.append(current_para)
                current_para = [box]
            last_y = box['y']
        if current_para: paragraphs.append(current_para)
        return paragraphs
    
    def _combine_paragraph_text(self, paragraph_boxes):
        sorted_boxes = sorted(paragraph_boxes, key=lambda b: (b['y'], b['x']))
        lines = []
        current_line = []
        last_y = None
        tolerance = 20
        for box in sorted_boxes:
            if 'translation' not in box or not box['translation']: continue
            if last_y is None or abs(box['y'] - last_y) <= tolerance:
                current_line.append(box)
                last_y = box['y'] if last_y is None else last_y
            else:
                if current_line: lines.append(current_line)
                current_line = [box]
                last_y = box['y']
        if current_line: lines.append(current_line)
        paragraph_text = []
        for line in lines:
            line_boxes = sorted(line, key=lambda b: b['x'])
            line_text = ' '.join([b['translation'].strip() for b in line_boxes if b['translation'].strip()])
            if line_text: paragraph_text.append(line_text)
        return ' '.join(paragraph_text)
    
    def _translate_paragraphs_individually(self, paragraphs, translator):
        translations = []
        for i, para in enumerate(paragraphs):
            japanese_texts = []
            for box in para['boxes']:
                if 'text' in box and box['text']: japanese_texts.append(box['text'])
            paragraph_japanese = ' '.join(japanese_texts)
            if paragraph_japanese.strip():
                try:
                    para_translation = translator.translate_text(paragraph_japanese, context="technical manual", source_lang='ja', target_lang='en')
                    translations.append(para_translation)
                except: translations.append(paragraph_japanese)
            else: translations.append("")
        return translations
    
    def _calculate_text_expansion(self, text_boxes, full_page_japanese):
        """
        Calculate the expansion ratio from Japanese to English.
        Returns a scaling factor to apply to font size and line height.
        """
        try:
            # Count Japanese characters (from OCR)
            japanese_char_count = 0
            if full_page_japanese:
                # Remove whitespace for character count
                japanese_char_count = len(re.sub(r'\s+', '', full_page_japanese))

            # Count English characters (from translations)
            english_char_count = 0
            for box in text_boxes:
                if box.get('translation'):
                    english_char_count += len(re.sub(r'\s+', '', box['translation']))

            if japanese_char_count == 0 or english_char_count == 0:
                return 1.0  # No adjustment if we can't calculate

            # Calculate expansion ratio
            expansion_ratio = english_char_count / japanese_char_count

            print(f"[PDF Scaling] Japanese: {japanese_char_count} chars, English: {english_char_count} chars")
            print(f"[PDF Scaling] Expansion ratio: {expansion_ratio:.2f}x")

            # Apply scaling based on expansion
            # If English is 130% or more of Japanese, start reducing font/spacing
            if expansion_ratio >= 1.3:
                # Scale down by up to 20% for very long expansions
                # expansion_ratio 1.3 → scale 0.95 (5% reduction)
                # expansion_ratio 1.5 → scale 0.85 (15% reduction)
                # expansion_ratio 2.0+ → scale 0.80 (20% reduction, max)
                scale_factor = max(0.80, 1.0 - (expansion_ratio - 1.0) * 0.25)
                print(f"[PDF Scaling] Applying scale factor: {scale_factor:.2f}")
                return scale_factor

            return 1.0  # No scaling needed

        except Exception as e:
            print(f"[PDF Scaling] Error calculating expansion: {e}")
            return 1.0  # Safe default

    def reconstruct_pdf(self, text_boxes, output_path, translator=None, full_page_japanese=None, translated_diagrams=None, translated_charts=None, book_context=None, table_artifacts=None, chart_artifacts=None, render_capture=None, translated_paragraphs=None, layout=None):
        def _is_critical_label(text):
            if not text: return False
            cleaned = re.sub(r"[^A-Za-z0-9]", "", str(text)).lower()
            if not cleaned: return False
            return re.match(r"^\d+$", cleaned) or re.match(r"^[a-z]\d*$", cleaned)

        print(f"Analyzing document layout structure...")

        # Try to get page number from layout (AI-detected), otherwise try OCR extraction
        page_number = None
        if layout and 'page_number' in layout:
            page_number = layout.get('page_number')
            if page_number:
                print(f"[PDF] Using AI-detected page number: {page_number}")

        # Fallback: Try to extract from OCR text if not found by AI
        if not page_number and text_boxes:
            sorted_boxes = sorted(text_boxes, key=lambda b: (b.get('y', 0), b.get('x', 0)))
            for box in sorted_boxes[:20]:
                text = box.get('text', '').strip()
                if not text: continue
                # FIX: Check left side page numbers too
                if (box.get('x', 0) > self.width * 0.7 or box.get('x', 0) < self.width * 0.3) and box.get('y', 0) < self.height * 0.15:
                    if re.search(r"(?:-|\u2014)\s*(\d{1,3})\s*(?:-|\u2014)", text):
                        page_number = re.search(r"(\d+)", text).group(1)
                        print(f"[PDF] Extracted page number from OCR: {page_number}")
                        break

        if not layout: layout = self._analyze_layout_structure(text_boxes)

        # Calculate dynamic scaling based on text expansion
        content_scale = self._calculate_text_expansion(text_boxes, full_page_japanese)

        # Create PDF
        c = canvas.Canvas(output_path, pagesize=A4)
        self.canvas = c
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
        c.setFillColor(black)

        # Apply dynamic scaling to font size and line height
        base_font_size = 10
        font_size = base_font_size * content_scale
        c.setFont(self.font_name, font_size)

        # Adjust line height: tighter for longer content
        base_line_height_multiplier = 1.4
        if content_scale < 0.95:
            # If we're scaling down, also tighten line spacing slightly
            line_height_multiplier = max(1.2, base_line_height_multiplier * 0.9)
        else:
            line_height_multiplier = base_line_height_multiplier

        line_height = font_size * line_height_multiplier
        current_y = self.page_height - self.margin_top
        at_page_top = True
        paragraph_index = 0
        legend_items = []
        
        # INITIALIZE table_queue
        table_queue = list(table_artifacts or [])
        
        def _render_table(table_artifact):
            nonlocal current_y, font_size, line_height
            print(f"Render Table: {table_artifact.id}")
            
            rows = table_artifact.rows
            cols = table_artifact.cols
            cells = table_artifact.cells
            
            if not cells: return

            data = [["" for _ in range(cols)] for _ in range(rows)]
            span_commands = []
            styles = getSampleStyleSheet()
            style = styles['Normal']
            style.fontName = self.font_name
            style.fontSize = 7  # Slightly smaller for better table fitting
            style.leading = 9

            for cell in cells:
                r, c_idx = cell.row, cell.col
                if r >= rows or c_idx >= cols or r < 0 or c_idx < 0: continue
                text = cell.translation or cell.text or ""
                data[r][c_idx] = Paragraph(text.replace('\\n', '<br/>'), style)
                row_span = getattr(cell, 'row_span', 1)
                col_span = getattr(cell, 'col_span', 1)
                if row_span > 1 or col_span > 1:
                    if r + row_span <= rows and c_idx + col_span <= cols:
                        span_commands.append(('SPAN', (c_idx, r), (c_idx + col_span - 1, r + row_span - 1)))

            available_width = self.page_width - self.margin_left - self.margin_right
            col_width = max(10, available_width / max(1, cols))
            col_widths = [col_width] * cols
            
            try:
                table = Table(data, colWidths=col_widths, repeatRows=1)
                style_list = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
                    ('FONTNAME', (0, 1), (-1, -1), self.font_name),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                    ('TOPPADDING', (0, 0), (-1, 0), 4),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                    ('TOPPADDING', (0, 1), (-1, -1), 2),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('FONTSIZE', (0, 0), (-1, -1), 7),
                ]
                table.setStyle(TableStyle(style_list))
                if span_commands:
                    for cmd in span_commands: table.setStyle(TableStyle([cmd]))

                w, h = table.wrapOn(self.canvas, available_width, self.page_height)
                if current_y - h < self.margin_bottom:
                    self.canvas.showPage()
                    self.canvas.setFont(self.font_name, font_size)
                    current_y = self.page_height - self.margin_top

                table.drawOn(self.canvas, self.margin_left, current_y - h)
                current_y -= (h + line_height)
            except Exception as e:
                print(f"Table render error: {e}")

        def _render_diagram_at(section, c, pdf_width, pdf_height, render_y_top, translated_diagrams, is_chart=False):
            nonlocal current_y, at_page_top, legend_items, font_size
            section_y_start = section.get('y_start', 0)
            section_height = section.get('height', 200)

            # Find match
            diagram_image = None
            diagram_annotations = []
            original_crop = None  # For overlay mode

            source_list = translated_charts if is_chart else translated_diagrams

            if source_list:
                best_match = None
                best_overlap = 0
                best_match_idx = -1
                for idx, trans_diag in enumerate(source_list):
                    # Skip if this diagram was already used
                    if trans_diag.get('_used', False):
                        continue
                    region = trans_diag['region']
                    # Calculate overlap with BOTH y and x coordinates for better matching
                    overlap_y_start = max(section_y_start, region['y'])
                    overlap_y_end = min(section_y_start + section_height, region['y'] + region['h'])
                    overlap_h = max(0, overlap_y_end - overlap_y_start)

                    # Also check x overlap for multi-diagram pages
                    section_x = section.get('x', 0)
                    section_w = section.get('w', 10000)  # Default to large if not specified
                    overlap_x_start = max(section_x, region['x'])
                    overlap_x_end = min(section_x + section_w, region['x'] + region['w'])
                    overlap_w = max(0, overlap_x_end - overlap_x_start)

                    # Total overlap area
                    overlap_area = overlap_h * overlap_w

                    if overlap_area > best_overlap:
                        best_overlap = overlap_area
                        best_match = trans_diag
                        best_match_idx = idx

                # Mark the matched diagram as used to prevent double-matching
                if best_match and best_match_idx >= 0:
                    source_list[best_match_idx]['_used'] = True
                    print(f"[DEBUG] Matched diagram {best_match_idx} with overlap area {best_overlap}")

                if best_match:
                    # Store both the translated image and original crop
                    diagram_image = best_match['image']
                    diagram_annotations = best_match.get('annotations', [])
                    # Get original crop for overlay mode
                    region = best_match['region']
                    original_crop = self.image.crop((region['x'], region['y'],
                                                     region['x'] + region['w'],
                                                     region['y'] + region['h']))
            
            if not diagram_image:
                # Fallback crop
                original_crop = self.image.crop((section['x'], section['y_start'], section['x']+section['w'], section['y_end']))
                diagram_image = original_crop

            # OVERLAY MODE: Create bilingual diagram if enabled
            print(f"[DEBUG] diagram_mode={self.diagram_mode}, has_annotations={bool(diagram_annotations)}, has_crop={bool(original_crop)}")
            if self.diagram_mode == 'overlay' and diagram_annotations and original_crop:
                print(f"[DiagramOverlay] Creating bilingual diagram for {'chart' if is_chart else 'diagram'} "
                      f"with {len(diagram_annotations)} labels")

                # Prepare text boxes for overlay renderer
                text_boxes_for_overlay = []
                for anno in diagram_annotations:
                    # Convert annotation to overlay format
                    text_boxes_for_overlay.append({
                        'bbox': (anno['x'], anno['y'], anno['w'], anno['h']),
                        'original': anno.get('original_text', '???'),  # Original text (source language)
                        'translation': anno['text'],  # Translated text (target language)
                        'orientation': 'horizontal',  # Default, could be detected
                        'font_size': anno['h'] * 0.7  # Estimate font size
                    })

                # Create bilingual overlay diagram
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    bilingual_path = tmp.name

                # Render bilingual diagram with original image
                self.overlay_renderer.render_bilingual_diagram(
                    original_image_path=None,
                    text_boxes=text_boxes_for_overlay,
                    output_path=bilingual_path,
                    original_image=original_crop  # Pass image directly
                )

                # Load bilingual diagram instead of translated one
                diagram_image = Image.open(bilingual_path)

            # Scale and Draw - use consistent margins
            diagram_width_pdf = self.page_width - (self.margin_left + self.margin_right)
            scale = diagram_width_pdf / diagram_image.width if diagram_image.width > 0 else 1.0
            diagram_height_pdf = diagram_image.height * scale

            # Check if diagram needs new page
            if diagram_height_pdf > (current_y - self.margin_bottom):
                 c.showPage()
                 c.setFillColorRGB(1, 1, 1)
                 c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
                 c.setFillColor(black)
                 c.setFont(self.font_name, font_size)
                 current_y = self.page_height - self.margin_top
                 at_page_top = True

            diagram_y = current_y - diagram_height_pdf
            diagram_x = self.margin_left
            
            if hasattr(diagram_image, 'mode') and diagram_image.mode != 'RGB':
                diagram_image = diagram_image.convert('RGB')
            img_reader = ImageReader(diagram_image)
            c.drawImage(img_reader, diagram_x, diagram_y, width=diagram_width_pdf, height=diagram_height_pdf, preserveAspectRatio=True, mask='auto')
            
            # Annotations
            # Only draw annotations if NOT in overlay mode (since overlay mode already has them in the image)
            if self.diagram_mode != 'overlay':
                for note in diagram_annotations:
                    pdf_x = diagram_x + (note['x'] * scale)
                    pdf_y = diagram_y + (diagram_image.height - note['y'] - note['h']/2) * scale
                    text = note['text']
                    
                    # FONT SCALING (Different for Charts)
                    if is_chart:
                        # Smaller font for charts
                        font_sz = max(4, min(int(note['h'] * 0.7 * scale), 10))
                    else:
                        font_sz = max(6, min(int(note['h'] * 0.6 * scale), 10))
                    
                    c.setFont(self.font_name, font_sz)
                    c.drawString(pdf_x, pdf_y, text)

            current_y = diagram_y - 20
            at_page_top = False

        print(f"Processing {len(layout['page_sections'])} sections...")
        for i, section in enumerate(layout['page_sections']):
            if section['type'] == 'text':
                if at_page_top and page_number:
                     c.drawString(self.page_width/2, self.page_height - 30, f"Page {page_number}")
                     current_y = self.page_height - self.margin_top
                     at_page_top = False
                
                # Render Paragraphs
                section_para_count = len(self._group_into_paragraphs(section.get('boxes', [])))
                for _ in range(section_para_count):
                    if paragraph_index >= len(translated_paragraphs): break
                    para_text = translated_paragraphs[paragraph_index]
                    paragraph_index += 1
                    
                    para_text_clean = para_text.strip()
                    para_text_no_html = re.sub(r'<\s*br\s*/?>', '\n', para_text_clean, flags=re.IGNORECASE)
                    para_text_no_html = re.sub(r'<[^>]+>', '', para_text_no_html)
                    para_blocks = [block.strip() for block in re.split(r'\n\s*\n', para_text_no_html) if block.strip()]
                    
                    for block in para_blocks:
                        block_escaped = html.escape(block, quote=False)
                        para_html = block_escaped.replace('\\n', '<br/>').replace('\n', '<br/>')
                        try:
                            # Use smaller font and tighter leading for better fitting
                            para_obj = Paragraph(para_html, ParagraphStyle('Body', fontName=self.font_name, fontSize=10, leading=14))
                            w, h = para_obj.wrap(self.page_width - self.margin_left - self.margin_right, self.page_height)
                            if current_y - h < self.margin_bottom:
                                c.showPage()
                                c.setFillColorRGB(1, 1, 1)
                                c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
                                c.setFillColor(black)
                                c.setFont(self.font_name, font_size)
                                current_y = self.page_height - self.margin_top
                                at_page_top = True
                            para_obj.drawOn(c, self.margin_left, current_y - h)
                            current_y -= (h + 10)
                        except: pass

            elif section['type'] == 'diagram':
                _render_diagram_at(section, c, self.page_width, self.page_height, current_y, translated_diagrams, is_chart=False)
            
            elif section['type'] == 'chart':
                _render_diagram_at(section, c, self.page_width, self.page_height, current_y, translated_charts, is_chart=True)
                
            elif section['type'] == 'table':
                # Attempt to render table from queue if any exist
                if table_queue:
                    _render_table(table_queue.pop(0))
                else:
                    # Fallback to image if no artifact found
                     _render_diagram_at(section, c, self.page_width, self.page_height, current_y, translated_diagrams, is_chart=False)

        c.save()
        return output_path
