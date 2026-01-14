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
    """

    def __init__(self):
        """Initialize renderer with default styling."""
        # Font settings
        self.label_font_name = "Helvetica"
        self.label_size_ratio = 1.2  # 120% of original text size
        self.min_font_size = 32  # Large minimum (will be scaled down in PDF)
        self.max_font_size = 48  # Large maximum (will be scaled down in PDF)

        # Overlay styling
        self.bg_color = (255, 255, 255)  # Pure white
        self.bg_opacity = 0.98  # 98% opacity - almost solid for clean background
        self.text_color = (0, 0, 0)  # Pure black for maximum contrast
        self.border_color = (100, 100, 100)  # Darker border for definition
        self.border_width = 1

        # Spacing and padding
        self.padding_x = 6  # More padding for clarity
        self.padding_y = 4
        self.gap_from_original = 3  # Gap between Japanese and English

        # Collision detection
        self.min_distance = 5  # Minimum distance between labels

    def render_bilingual_diagram(
        self,
        original_image_path: Optional[str],
        text_boxes: List[Dict],
        output_path: str,
        original_image: Optional[Image.Image] = None
    ) -> str:
        """
        Create bilingual diagram with overlay labels.

        Args:
            original_image_path: Path to original diagram image (can be None if original_image provided)
            text_boxes: List of dictionaries with:
                - 'bbox': (x, y, w, h) in pixels
                - 'japanese': '日本語' (original text)
                - 'english': 'English' (translation)
                - 'orientation': 'horizontal' | 'vertical' (optional)
                - 'font_size': float (optional, detected font size)
            output_path: Where to save the bilingual diagram
            original_image: PIL Image object (alternative to path)

        Returns:
            Path to rendered bilingual diagram
        """
        # print(f"[BilingualOverlay] Creating bilingual diagram: {output_path}")
        # print(f"[BilingualOverlay] Processing {len(text_boxes)} text elements")

        # Load original image (RGBA mode for transparency support)
        if original_image is not None:
            img = original_image.convert('RGBA')
        elif original_image_path:
            img = Image.open(original_image_path).convert('RGBA')
        else:
            raise ValueError("Either original_image_path or original_image must be provided")
        width, height = img.size

        # Create transparent overlay layer
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        # Calculate optimal positions for all labels
        overlay_positions = self._calculate_overlay_positions(
            (width, height), text_boxes
        )

        # Render each English label
        for i, (text_box, position) in enumerate(zip(text_boxes, overlay_positions)):
            if text_box.get('english'):
                self._render_overlay_label(
                    draw,
                    text_box['english'],
                    position,
                    text_box.get('orientation', 'horizontal')
                )
                # print(f"  [BilingualOverlay] Label {i+1}/{len(text_boxes)}: "
                #       f"'{text_box['japanese'][:20]}...' -> '{text_box['english'][:20]}...'")

        # Composite overlay onto original image
        result = Image.alpha_composite(img, overlay)

        # Convert back to RGB for saving
        result_rgb = result.convert('RGB')
        result_rgb.save(output_path, quality=95)


        # print(f"[BilingualOverlay] Saved bilingual diagram: {output_path}")
        return output_path

    def _calculate_overlay_positions(
        self,
        image_size: Tuple[int, int],
        text_boxes: List[Dict]
    ) -> List[Dict]:
        """
        Calculate optimal positions for overlay labels with collision detection.

        Returns list of position dictionaries with:
            - 'x', 'y': Top-left corner coordinates
            - 'width', 'height': Label dimensions
            - 'font_size': Calculated font size
        """
        width, height = image_size
        positions = []
        occupied_regions = []  # Track where labels are already placed

        for box in text_boxes:
            if not box.get('english'):
                positions.append(None)
                continue

            x, y, w, h = box['bbox']
            orientation = box.get('orientation', 'horizontal')
            english_text = box['english']

            # Determine font size - CRITICAL: Must be LARGE because image gets scaled down in PDF
            # Diagrams are typically scaled down 2-3x when placed in PDF
            # So we need to render at 2-3x the final desired size
            # Target: 12pt readable in PDF = need 24-36px in source image
            base_font_size = 32  # Large base to survive scaling
            original_font_size = box.get('font_size', base_font_size)
            label_font_size = max(
                base_font_size,  # Always at least 32px before scaling
                min(48, original_font_size * self.label_size_ratio)  # Max 48px
            )

            # Calculate English text dimensions
            try:
                font = ImageFont.truetype(self.label_font_name, int(label_font_size))
            except:
                font = ImageFont.load_default()

            # Get text bounding box
            temp_img = Image.new('RGBA', (1, 1))
            temp_draw = ImageDraw.Draw(temp_img)
            bbox = temp_draw.textbbox((0, 0), english_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Add padding
            label_width = text_width + 2 * self.padding_x
            label_height = text_height + 2 * self.padding_y

            # Calculate primary position based on orientation
            if orientation == 'vertical':
                # Place to the right of Japanese text
                primary_x = x + w + self.gap_from_original
                primary_y = y
            else:  # horizontal (default)
                # Place below Japanese text
                primary_x = x
                primary_y = y + h + self.gap_from_original

            # Create candidate positions (in order of preference)
            candidates = [
                {'x': primary_x, 'y': primary_y, 'anchor': 'primary'},
                {'x': x, 'y': y - label_height - self.gap_from_original, 'anchor': 'above'},
                {'x': x - label_width - self.gap_from_original, 'y': y, 'anchor': 'left'},
                {'x': x + w + self.gap_from_original, 'y': y, 'anchor': 'right'},
            ]

            # Find first position without collision
            final_position = None
            for candidate in candidates:
                candidate_rect = {
                    'x': candidate['x'],
                    'y': candidate['y'],
                    'width': label_width,
                    'height': label_height
                }

                # Check if within image bounds
                if (candidate['x'] < 0 or candidate['y'] < 0 or
                    candidate['x'] + label_width > width or
                    candidate['y'] + label_height > height):
                    continue

                # Check collision with occupied regions
                if not self._has_collision(candidate_rect, occupied_regions):
                    final_position = candidate_rect
                    final_position['font_size'] = label_font_size
                    final_position['anchor'] = candidate['anchor']
                    break

            # Fallback: use primary position even if collision (best effort)
            if final_position is None:
                final_position = {
                    'x': max(0, min(primary_x, width - label_width)),
                    'y': max(0, min(primary_y, height - label_height)),
                    'width': label_width,
                    'height': label_height,
                    'font_size': label_font_size,
                    'anchor': 'fallback'
                }

            positions.append(final_position)
            occupied_regions.append(final_position)

        return positions

    def _has_collision(self, rect: Dict, occupied: List[Dict]) -> bool:
        """Check if rectangle collides with any occupied region."""
        for occ in occupied:
            # Check for overlap with minimum distance
            if not (rect['x'] + rect['width'] + self.min_distance < occ['x'] or
                    rect['x'] > occ['x'] + occ['width'] + self.min_distance or
                    rect['y'] + rect['height'] + self.min_distance < occ['y'] or
                    rect['y'] > occ['y'] + occ['height'] + self.min_distance):
                return True
        return False

    def _render_overlay_label(
        self,
        draw: ImageDraw.Draw,
        text: str,
        position: Dict,
        orientation: str
    ):
        """
        Render a single overlay label with semi-transparent background.

        Args:
            draw: PIL ImageDraw object
            text: English text to render
            position: Position dict with x, y, width, height, font_size
            orientation: 'horizontal' or 'vertical'
        """
        if position is None:
            return

        x = position['x']
        y = position['y']
        label_width = position['width']
        label_height = position['height']
        font_size = position['font_size']

        # Load font
        try:
            font = ImageFont.truetype(self.label_font_name, int(font_size))
        except:
            font = ImageFont.load_default()

        # Draw semi-transparent background
        bg_rect = (
            x,
            y,
            x + label_width,
            y + label_height
        )

        # Create semi-transparent background
        bg_alpha = int(255 * self.bg_opacity)
        draw.rectangle(
            bg_rect,
            fill=(*self.bg_color, bg_alpha)
        )

        # Draw subtle border
        if self.border_width > 0:
            draw.rectangle(
                bg_rect,
                outline=(*self.border_color, 255),
                width=self.border_width
            )

        # Draw English text
        text_x = x + self.padding_x
        text_y = y + self.padding_y

        draw.text(
            (text_x, text_y),
            text,
            fill=(*self.text_color, 255),
            font=font
        )


def create_bilingual_diagram(
    original_image_path: str,
    text_boxes: List[Dict],
    output_path: str
) -> str:
    """
    Convenience function to create bilingual diagram.

    Args:
        original_image_path: Path to original diagram
        text_boxes: List of text elements with translations
        output_path: Where to save result

    Returns:
        Path to bilingual diagram
    """
    renderer = DiagramOverlayRenderer()
    return renderer.render_bilingual_diagram(
        original_image_path,
        text_boxes,
        output_path
    )
