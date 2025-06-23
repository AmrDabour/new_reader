from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from typing import Dict, List, Tuple, Optional

class ImageService:
    def __init__(self):
        self.default_font = None
        self.arabic_font = None
        try:
            self.default_font = ImageFont.truetype("arial.ttf", 32)
            self.arabic_font = ImageFont.truetype("arialbd.ttf", 32)
        except Exception:
            self.default_font = ImageFont.load_default()
            self.arabic_font = ImageFont.load_default()

    def create_annotated_image(
        self,
        img: Image.Image,
        texts_dict: Dict[str, str],
        ui_fields: List[Dict]
    ) -> Optional[Image.Image]:
        """
        Draw user inputs onto the original image
        """
        if not img or not texts_dict or not ui_fields:
            return None
            
        annotated = img.copy()
        draw = ImageDraw.Draw(annotated)
        
        # Calculate default font size based on average field height
        total_height = 0
        field_count = 0
        for field in ui_fields:
            if field['type'] == 'textbox':
                _, _, _, h = field['original_box']
                total_height += h
                field_count += 1
        
        default_font_size = int((total_height / max(1, field_count)) * 0.5)
        
        try:
            default_font = ImageFont.truetype("arial.ttf", default_font_size)
            arabic_font = ImageFont.truetype("arialbd.ttf", default_font_size)
        except Exception:
            default_font = ImageFont.load_default()
            arabic_font = default_font

        for field in ui_fields:
            box_id = field['box_id']
            value = texts_dict.get(box_id)
            
            if value:
                x, y, w, h = field['original_box']
                field_type = field['type']

                if field_type == 'checkbox' and value is True:
                    self._draw_checkbox(draw, x, y, w, h)
                elif field_type == 'textbox' and isinstance(value, str) and value.strip():
                    self._draw_text(draw, value, x, y, w, h, default_font, arabic_font)

        return annotated

    def _draw_checkbox(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        w: int,
        h: int
    ):
        """Draw a checkmark in a checkbox"""
        checkmark_char = '✓'
        font_size = int(min(w, h) * 0.9)
        
        try:
            font = ImageFont.truetype("seguisym.ttf", font_size)
        except IOError:
            try:
                font = ImageFont.truetype("arialbd.ttf", font_size)
            except IOError:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except IOError:
                    font = ImageFont.load_default()

        try:
            text_bbox = draw.textbbox((0, 0), checkmark_char, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_w, text_h = draw.textsize(checkmark_char, font=font)

        text_x = x + (w - text_w) / 2
        text_y = y + (h - text_h) / 2 - (h * 0.05)
        
        draw.text((text_x, text_y), checkmark_char, fill="black", font=font)

    def _draw_text(
        self,
        draw: ImageDraw.Draw,
        text: str,
        x: int,
        y: int,
        w: int,
        h: int,
        default_font: ImageFont.FreeTypeFont,
        arabic_font: ImageFont.FreeTypeFont
    ):
        """Draw text in a field"""
        padding = 4
        is_arabic = any(ord(c) >= 0x0600 and ord(c) <= 0x06FF for c in text)
        
        if is_arabic:
            display_text = get_display(arabic_reshaper.reshape(text))
            current_font = arabic_font
        else:
            display_text = text
            current_font = default_font

        try:
            # Try to use modern Pillow's anchor-based text drawing
            draw_y = y + h / 2
            if is_arabic:
                draw.text((x + w - padding, draw_y), display_text,
                         fill="black", font=current_font, anchor="rm")
            else:
                draw.text((x + padding, draw_y), display_text,
                         fill="black", font=current_font, anchor="lm")
        except TypeError:
            # Fallback for older Pillow versions
            try:
                bbox = draw.textbbox((0, 0), display_text, font=current_font)
                text_height = bbox[3] - bbox[1]
                text_width = bbox[2] - bbox[0]
            except AttributeError:
                text_width, text_height = draw.textsize(display_text, font=current_font)

            draw_y = y + (h - text_height) / 2
            if is_arabic:
                draw_x = x + w - text_width - padding
            else:
                draw_x = x + padding
            draw.text((draw_x, draw_y), display_text, fill="black", font=current_font) 