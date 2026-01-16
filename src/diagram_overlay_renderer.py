"""
Bilingual Diagram Overlay Renderer
Keeps original diagrams/charts intact and adds English translations as overlay labels.
Similar to Google Translate's image translation feature.
"""

import os
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
import numpy as np


class DiagramOverlayRenderer:
    """
    Renders bilingual diagrams with overlay labels.
    Keeps original diagram 100% intact, adds English translations alongside Japanese.
    Features intelligent collision detection and leader lines for crowded diagrams.
    """

    def __init__(self):
        """Initialize renderer with default styling."""
        # Font settings
        self.label_font_path = self._get_best_font_path()
        self.label_size_ratio = 1.0  # 100% of original text size - Match original
        self.min_font_size = 12  # Readable minimum (reduced for crowded diagrams)
        self.max_font_size = 48  # Reasonable maximum

        # Overlay styling
        self.bg_color = (255, 255, 255)  # Pure white
        self.bg_opacity = 0.98  # More solid for maximum readability
        self.text_color = (0, 0, 0)  # Pure black for maximum contrast
        self.border_color = (80, 80, 80)  # Darker border for better definition
        self.border_width = 1

        # Leader line styling
        self.leader_color = (220, 50, 50)  # Brighter, distinct red for clarity
        self.leader_width = 2 # Thicker line for better visibility

        # Spacing and padding
        self.padding_x = 4
        self.padding_y = 2
        self.gap_from_original = 4  # Gap between Japanese and English
        self.min_distance = 3  # Minimum distance between labels

    def _get_best_font_path(self):
        """Find the best available font on the system"""
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
        
        for path in font_candidates:
            if os.path.exists(path):
                return path
        return None

    def render_bilingual_diagram(
        self,
        original_image_path: Optional[str],
        text_boxes: List[Dict],
        output_path: str,
        original_image: Optional[Image.Image] = None
    ) -> str:
        """
        Create bilingual diagram with overlay labels and leader lines.
        """
        # Load original image
        if original_image is not None:
            img = original_image.convert('RGBA')
        elif original_image_path:
            img = Image.open(original_image_path).convert('RGBA')
        else:
            raise ValueError("Either original_image_path or original_image must be provided")
        
        width, height = img.size
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        # 1. Calculate optimal positions with collision detection
        overlay_positions = self._calculate_overlay_positions((width, height), text_boxes)

        # 2. Render leader lines first (so they go under labels)
        for i, (box, pos) in enumerate(zip(text_boxes, overlay_positions)):
            if pos and pos.get('needs_leader'):
                self._draw_leader_line(draw, box['bbox'], pos)

        # 3. Render each translated label
        for i, (text_box, position) in enumerate(zip(text_boxes, overlay_positions)):
            if text_box.get('translation') and position:
                is_identical = text_box['original'].strip() == text_box['translation'].strip()
                self._render_overlay_label(
                    draw,
                    text_box['translation'],
                    position
                )
                
                # if i < 5:
                #     status_msg = " [SAME]" if is_identical else ""
                #     print(f"  [BilingualOverlay] Label {i+1}/{len(text_boxes)}{status_msg}: "
                #           f"'{text_box['original'][:15]}' -> '{text_box['translation'][:15]}'")

        # Composite and save
        result = Image.alpha_composite(img, overlay)
        result.convert('RGB').save(output_path, quality=95)
        return output_path

    def _calculate_overlay_positions(
        self,
        image_size: Tuple[int, int],
        text_boxes: List[Dict]
    ) -> List[Dict]:
        """
        Calculate positions using a greedy collision avoidance algorithm.
        """
        width, height = image_size
        positions = []
        # Include original text boxes in occupied regions to avoid covering them if possible
        occupied_regions = []
        for box in text_boxes:
             x, y, w, h = box['bbox']
             occupied_regions.append({'x': x, 'y': y, 'width': w, 'height': h})

        for box in text_boxes:
            if not box.get('translation'):
                positions.append(None)
                continue

            x, y, w, h = box['bbox']
            translated_text = box['translation']
            
            # 1. Determine base font size
            target_size = max(self.min_font_size, min(self.max_font_size, height * 0.018))
            original_fs = box.get('font_size', 0)
            if original_fs > 0:
                target_size = max(target_size, original_fs * 0.9)
            
            # 2. Try to fit the label, shrinking if necessary
            best_pos = None
            for current_fs in [target_size, target_size * 0.8, target_size * 0.6]:
                current_fs = max(self.min_font_size, current_fs)
                
                font = self._get_font(int(current_fs))
                temp_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
                bbox = temp_draw.textbbox((0, 0), translated_text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                lw, lh = tw + 2 * self.padding_x, th + 2 * self.padding_y

                # Candidate spots: Below, Above, Right, Left, then Farther out
                candidates = [
                    # Near spots (prefer no leader)
                    {'x': x, 'y': y + h + self.gap_from_original, 'leader': False},
                    {'x': x, 'y': y - lh - self.gap_from_original, 'leader': False},
                    {'x': x + w + self.gap_from_original, 'y': y, 'leader': False},
                    {'x': x - lw - self.gap_from_original, 'y': y, 'leader': False},
                    # Far spots (require leader lines)
                    {'x': x + w + 40, 'y': y + 20, 'leader': True},
                    {'x': x - lw - 40, 'y': y - 20, 'leader': True},
                    {'x': x, 'y': y + h + 60, 'leader': True},
                    {'x': x, 'y': y - lh - 60, 'leader': True},
                ]

                for cand in candidates:
                    rect = {'x': cand['x'], 'y': cand['y'], 'width': lw, 'height': lh}
                    
                    # Bounds check
                    if (rect['x'] < 0 or rect['y'] < 0 or 
                        rect['x'] + lw > width or rect['y'] + lh > height):
                        continue
                    
                    # Collision check
                    if not self._has_collision(rect, occupied_regions):
                        best_pos = rect
                        best_pos['font_size'] = current_fs
                        best_pos['needs_leader'] = cand['leader']
                        break
                
                if best_pos: break

            # Fallback
            if not best_pos:
                best_pos = {
                    'x': max(0, min(x, width - 20)), 
                    'y': max(0, min(y + h + 2, height - 10)),
                    'width': 20, 'height': 10, 'font_size': self.min_font_size, 'needs_leader': True
                }

            positions.append(best_pos)
            occupied_regions.append(best_pos)

        return positions

    def _has_collision(self, rect: Dict, occupied: List[Dict]) -> bool:
        for occ in occupied:
            if not (rect['x'] + rect['width'] + self.min_distance < occ['x'] or
                    rect['x'] > occ['x'] + occ['width'] + self.min_distance or
                    rect['y'] + rect['height'] + self.min_distance < occ['y'] or
                    rect['y'] > occ['y'] + occ['height'] + self.min_distance):
                return True
        return False

    def _get_font(self, size: int):
        try:
            if self.label_font_path:
                return ImageFont.truetype(self.label_font_path, size)
            return ImageFont.load_default()
        except:
            return ImageFont.load_default()

    def _draw_leader_line(self, draw: ImageDraw.Draw, source_bbox: Tuple, target_pos: Dict):
        """Draw a leader line with an arrow head for maximum clarity."""
        sx, sy, sw, sh = source_bbox
        tx, ty, tw, th = target_pos['x'], target_pos['y'], target_pos['width'], target_pos['height']
        
        # Center of original
        start_pt = (sx + sw // 2, sy + sh // 2)
        # Edge of translation
        if tx > sx + sw: # Translation is to the right
            end_pt = (tx, ty + th // 2)
        elif tx + tw < sx: # Translation is to the left
            end_pt = (tx + tw, ty + th // 2)
        elif ty > sy + sh: # Translation is below
            end_pt = (tx + tw // 2, ty)
        else: # Translation is above
            end_pt = (tx + tw // 2, ty + th)
            
        # Draw main leader line
        draw.line([start_pt, end_pt], fill=(*self.leader_color, 255), width=self.leader_width)
        
        # Draw a small circle or arrow head at the source (Japanese text) to anchor it visually
        r = 3
        draw.ellipse([start_pt[0]-r, start_pt[1]-r, start_pt[0]+r, start_pt[1]+r],
                     fill=(*self.leader_color, 255))

    def _render_overlay_label(self, draw, text, pos):
        x, y, lw, lh, fs = pos['x'], pos['y'], pos['width'], pos['height'], pos['font_size']
        font = self._get_font(int(fs))
        
        # Draw background with slightly rounded feel (via double rect)
        bg_alpha = int(255 * self.bg_opacity)
        draw.rectangle([x, y, x + lw, y + lh], fill=(*self.bg_color, bg_alpha), outline=(*self.border_color, 255), width=1)
        
        # Text center-aligned in box
        draw.text((x + self.padding_x, y + self.padding_y), text, fill=(*self.text_color, 255), font=font)


def create_bilingual_diagram(original_image_path: str, text_boxes: List[Dict], output_path: str) -> str:
    renderer = DiagramOverlayRenderer()
    return renderer.render_bilingual_diagram(original_image_path, text_boxes, output_path)
