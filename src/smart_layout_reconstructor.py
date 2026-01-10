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
            
            # Dynamic threshold: stricter for short text to avoid connecting diagram labels
            # Long text (paragraphs) can have larger gaps (paragraph breaks).
            # Short text (labels) must be tight (e.g. a bullet list) to be considered text flow.
            # If short text is spaced out (> 1.5 line heights), it's likely labels on a diagram.
            is_short = box['w'] < page_width * 0.2
            v_thresh = box['h'] * (1.5 if is_short else 3.0)
            
            for j, other in enumerate(sorted_boxes):
                if i == j: continue
                
                # Check if 'other' is vertically close
                y_dist = abs(box['y'] - other['y'])
                if y_dist > 0 and y_dist < v_thresh:
                    # STRICTER CHECK: To be a paragraph neighbor, it must also be:
                    # 1. Horizontally close (same column) OR
                    # 2. Horizontally aligned (bullet list)
                    
                    # Horizontal overlap or proximity
                    x_dist = abs(box['x'] - other['x'])
                    # Check if they visually overlap in X (one is above the other)
                    overlap_x = max(0, min(box['x'] + box['w'], other['x'] + other['w']) - max(box['x'], other['x']))
                    is_vertically_stacked = overlap_x > min(box['w'], other['w']) * 0.3
                    
                    # Check for left-alignment (typical for lists/paragraphs)
                    is_left_aligned = abs(box['x'] - other['x']) < 30
                    
                    # If they are just randomly near each other in Y but far apart in X (like diagram labels),
                    # they are NOT paragraph neighbors.
                    if is_vertically_stacked or is_left_aligned:
                        has_neighbor = True
                        break
            
            if has_neighbor:
                paragraph_boxes.append(box)
            elif box['w'] > page_width * 0.25: # Increased threshold from 0.15 to 0.25 for isolated lines
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
        
        # Use filtered_boxes for main structure detection to avoid labels breaking diagrams
        # But we must ensure we don't miss any critical text.
        # Fallback: if filtered_boxes is empty but text_boxes isn't, use text_boxes
        boxes_to_analyze = filtered_boxes if filtered_boxes else text_boxes
        
        # We need them sorted by Y
        boxes_to_analyze = sorted(boxes_to_analyze, key=lambda b: (b['y'], b['x']))
        
        for box in boxes_to_analyze:
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
                
                # DIAGRAM VETO: If there are many text boxes in the gap, it MIGHT not be a diagram.
                # HOWEVER, charts often have many small labels (numbers, axis text).
                # We should only veto if the text looks like "Prose" (long sentences).
                
                is_diagram = True
                if len(gap_boxes) >= 8:
                    # Analyze the content of the boxes
                    long_text_count = 0
                    total_chars = 0
                    
                    for b in gap_boxes:
                        text = b.get('text', '').strip()
                        total_chars += len(text)
                        # A box with > 15 chars is likely part of a sentence/paragraph
                        # (Diagram labels are usually short: "Fig 1", "500", "Valve")
                        if len(text) > 15:
                            long_text_count += 1
                    
                    # Heuristic:
                    # If more than 30% of boxes are "long", it's likely a text paragraph we missed.
                    # Or if the average length is high.
                    avg_len = total_chars / len(gap_boxes) if gap_boxes else 0
                    long_ratio = long_text_count / len(gap_boxes)
                    
                    if long_ratio > 0.3 or avg_len > 20:
                        is_diagram = False
                        print(f"  [Layout] Vetoed diagram candidate at Y={gap_start}-{gap_end}: Too much prose (avg_len={avg_len:.1f}, long_ratio={long_ratio:.2f})")
                    else:
                        print(f"  [Layout] Accepted diagram candidate at Y={gap_start}-{gap_end} despite {len(gap_boxes)} boxes (likely chart/labels)")

                if is_diagram:
                    page_sections.append({
                        'type': 'diagram',
                        'y_start': gap_start,
                        'y_end': gap_end,
                        'height': gap_end - gap_start,
                        'x': 0,
                        'w': self.width
                    })
                else:
                    # It was rejected as a diagram, so treat it as text flow
                    # We need to append these boxes to the previous text section or start a new one?
                    # Actually, the logic above splits sections based on gaps.
                    # If we reject this gap as a diagram, it effectively means the gap wasn't "real"
                    # in terms of structure, but we already closed the previous section.
                    # So we should create a new text section for this "gap" content.
                    if gap_boxes:
                        page_sections.append({
                            'type': 'text',
                            'boxes': gap_boxes,
                            'y_start': gap_start,
                            'y_end': gap_end
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

                # NEW: Merge Diagram -> Small Text (captions, axis labels)
                if prev['type'] == 'diagram' and curr['type'] == 'text':
                    # If text is short (likely a caption or axis numbers)
                    text_height = curr['y_end'] - curr['y_start']
                    if text_height < 80:  # Threshold for single/double line caption
                        prev['y_end'] = curr['y_end']
                        prev['height'] = prev['y_end'] - prev['y_start']
                        # Add these boxes to the previous section so they are used for content bounds
                        # But we don't strictly track boxes for diagram sections, just bounds.
                        # The refinement step (using all boxes in band) will pick them up 
                        # because we extended y_end.
                        continue

                merged_sections.append(curr)
        
        page_sections = merged_sections

        # 4. Generate Output Structure
        paragraphs = []
        diagram_regions = []
        
        for section in page_sections:
            if section['type'] == 'text':
                para_groups = self._group_into_paragraphs(section['boxes'])
                for para in para_groups:
                    paragraphs.append({
                        'boxes': para,
                        'y_position': para[0]['y']
                    })
            elif section['type'] == 'diagram':
                diagram_regions.append({
                    'x': section.get('x', 0),
                    'y': section['y_start'],
                    'w': section.get('w', self.width),
                    'h': section['height'],
                    'position_in_flow': section['y_start']
                })

        return {'paragraphs': paragraphs, 'diagram_regions': diagram_regions, 'page_sections': page_sections}

    def reconstruct_from_layout_analysis(self, layout_data, text_boxes):
        """
        Reconstruct layout using AI-detected regions instead of heuristics.
        
        Args:
            layout_data: Dictionary from LayoutAgent with 'regions' list
            text_boxes: List of OCR text boxes
            
        Returns:
            Dict compatible with reconstruct_pdf expectation:
            {'paragraphs': [], 'diagram_regions': [], 'page_sections': []}
        """
        print("[SmartLayout] Reconstructing from AI Layout Analysis...")
        
        regions = layout_data.get('regions', [])
        page_sections = []
        
        # Sort regions top-to-bottom
        regions.sort(key=lambda r: r['box_pixel']['y'])
        
        # 1. Map OCR boxes to Regions
        # We need to know which text boxes belong to diagrams (labels) vs text blocks (paragraphs)
        region_text_map = {id(r): [] for r in regions}
        unassigned_boxes = []
        
        for box in text_boxes:
            box_x = box['x']
            box_y = box['y']
            box_w = box['w']
            box_h = box['h']
            box_area = box_w * box_h
            
            best_region = None
            max_intersection = 0
            
            for region in regions:
                r_box = region['box_pixel']
                
                # Calculate intersection
                ix = max(box_x, r_box['x'])
                iy = max(box_y, r_box['y'])
                iw = min(box_x + box_w, r_box['x'] + r_box['w']) - ix
                ih = min(box_y + box_h, r_box['y'] + r_box['h']) - iy
                
                if iw > 0 and ih > 0:
                    intersection = iw * ih
                    # Calculate Intersection over Box Area (how much of the text box is inside the region)
                    # We care if the text is inside the region, not if the region is inside the text.
                    ioba = intersection / box_area
                    
                    if ioba > 0.5 and intersection > max_intersection:
                        max_intersection = intersection
                        best_region = region
            
            if best_region:
                region_text_map[id(best_region)].append(box)
            else:
                unassigned_boxes.append(box)
                
        # 2. Build Page Sections
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
                print(f"  [Layout] Added Technical Diagram at Y={y_start}")

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
                print(f"  [Layout] Added Chart at Y={y_start} with extra padding")

            elif rtype in ['text_block', 'caption', 'header_footer']:
                # TEXT PIPELINE
                assigned_boxes = region_text_map[id(region)]
                if assigned_boxes:
                    page_sections.append({'type': 'text', 'boxes': assigned_boxes, 'y_start': rbox['y'], 'y_end': rbox['y'] + rbox['h']})
            
            elif rtype == 'table':
                # TABLE PIPELINE (Preserve as image for now/placeholder)
                page_sections.append({
                    'type': 'diagram', # Fallback to image for safety
                    'x': rbox['x'], 'y_start': rbox['y'], 'y_end': rbox['y'] + rbox['h'],
                    'w': rbox['w'], 'height': rbox['h'],
                    'boxes': region_text_map[id(region)]
                })

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
                        prev['boxes'].extend(curr['boxes'])
                        continue
                merged_sections.append(curr)
        page_sections = merged_sections

        paragraphs = []
        diagram_regions = [] # Used for legacy text filtering
        chart_regions = []   # New
        
        for section in page_sections:
            if section['type'] == 'text':
                para_groups = self._group_into_paragraphs(section['boxes'])
                for para in para_groups: paragraphs.append({'boxes': para, 'y_position': para[0]['y']})
            elif section['type'] == 'diagram':
                diagram_regions.append({'x': section['x'], 'y': section['y_start'], 'w': section['w'], 'h': section['height']})
            elif section['type'] == 'chart':
                chart_regions.append({'x': section['x'], 'y': section['y_start'], 'w': section['w'], 'h': section['height']})
                # Add to diagram_regions too so text is filtered out from prose
                diagram_regions.append({'x': section['x'], 'y': section['y_start'], 'w': section['w'], 'h': section['height']})

        return {'paragraphs': paragraphs, 'diagram_regions': diagram_regions, 'chart_regions': chart_regions, 'page_sections': page_sections}

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
    
    def reconstruct_pdf(self, text_boxes, output_path, translator=None, full_page_japanese=None, translated_diagrams=None, translated_charts=None, book_context=None, table_artifacts=None, chart_artifacts=None, render_capture=None, translated_paragraphs=None, layout=None):
        def _is_critical_label(text):
            if not text: return False
            cleaned = re.sub(r"[^A-Za-z0-9]", "", str(text)).lower()
            if not cleaned: return False
            return re.match(r"^\d+$", cleaned) or re.match(r"^[a-z]\d*$", cleaned)

        print(f"Analyzing document layout structure...")
        page_number = None
        if text_boxes:
            sorted_boxes = sorted(text_boxes, key=lambda b: (b.get('y', 0), b.get('x', 0)))
            for box in sorted_boxes[:20]:
                text = box.get('text', '').strip()
                if not text: continue
                if box.get('x', 0) > self.width * 0.7 and box.get('y', 0) < self.height * 0.15:
                    if re.search(r"(?:-|\u2014)\s*(\d{1,3})\s*(?:-|\u2014)", text):
                        page_number = re.search(r"(\d+)", text).group(1)
                        break
        
        if not layout: layout = self._analyze_layout_structure(text_boxes)
        
        # Create PDF
        c = canvas.Canvas(output_path, pagesize=A4)
        self.canvas = c
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
        c.setFillColor(black)
        font_size = 11
        c.setFont(self.font_name, font_size)
        line_height = font_size * 1.5
        current_y = self.page_height - 80
        at_page_top = True
        paragraph_index = 0
        legend_items = []
        
        table_queue = list(table_artifacts or [])
        
        def _render_table(table_artifact):
            nonlocal current_y
            print(f"Render Table: {table_artifact.id}")
            # Placeholder implementation

        def _render_diagram_at(section, c, pdf_width, pdf_height, render_y_top, translated_diagrams, is_chart=False):
            nonlocal current_y, at_page_top, legend_items
            section_y_start = section.get('y_start', 0)
            section_height = section.get('height', 200)
            
            # Find match
            diagram_image = None
            diagram_annotations = []
            
            source_list = translated_charts if is_chart else translated_diagrams
            
            if source_list:
                best_match = None
                best_overlap = 0
                for trans_diag in source_list:
                    region = trans_diag['region']
                    # Overlap logic
                    overlap_y = max(section_y_start, region['y'])
                    overlap_h = max(0, min(section_y_start + section_height, region['y'] + region['h']) - overlap_y)
                    if overlap_h > 0:
                        best_match = trans_diag
                        break # First match
                
                if best_match:
                    diagram_image = best_match['image']
                    diagram_annotations = best_match.get('annotations', [])
            
            if not diagram_image:
                # Fallback crop
                diagram_image = self.image.crop((section['x'], section['y_start'], section['x']+section['w'], section['y_end']))

            # Scale and Draw
            diagram_width_pdf = self.page_width - 120
            scale = diagram_width_pdf / diagram_image.width if diagram_image.width > 0 else 1.0
            diagram_height_pdf = diagram_image.height * scale
            
            if diagram_height_pdf > (current_y - 80):
                 c.showPage()
                 c.setFillColorRGB(1, 1, 1)
                 c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
                 c.setFillColor(black)
                 c.setFont(self.font_name, font_size)
                 current_y = self.page_height - 80
                 at_page_top = True
            
            diagram_y = current_y - diagram_height_pdf
            diagram_x = 60
            
            if hasattr(diagram_image, 'mode') and diagram_image.mode != 'RGB':
                diagram_image = diagram_image.convert('RGB')
            img_reader = ImageReader(diagram_image)
            c.drawImage(img_reader, diagram_x, diagram_y, width=diagram_width_pdf, height=diagram_height_pdf, preserveAspectRatio=True, mask='auto')
            
            # Annotations
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
                     c.drawString(self.page_width/2, self.page_height-40, f"Page {page_number}")
                     current_y = self.page_height - 80
                     at_page_top = False
                
                # Render Paragraphs
                section_para_count = len(self._group_into_paragraphs(section['boxes']))
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
                            para_obj = Paragraph(para_html, ParagraphStyle('Body', fontName=self.font_name, fontSize=11, leading=16))
                            w, h = para_obj.wrap(self.page_width - 120, self.page_height)
                            if current_y - h < 80:
                                c.showPage()
                                c.setFillColorRGB(1, 1, 1)
                                c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
                                c.setFillColor(black)
                                c.setFont(self.font_name, font_size)
                                current_y = self.page_height - 80
                                at_page_top = True
                            para_obj.drawOn(c, 60, current_y - h)
                            current_y -= (h + 10)
                        except: pass

            elif section['type'] == 'diagram':
                _render_diagram_at(section, c, self.page_width, self.page_height, current_y, translated_diagrams, is_chart=False)
            
            elif section['type'] == 'chart':
                _render_diagram_at(section, c, self.page_width, self.page_height, current_y, translated_charts, is_chart=True)

        c.save()
        return output_path
