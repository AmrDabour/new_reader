from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Tuple, Optional
import arabic_reshaper
from bidi.algorithm import get_display
from .arabic import is_arabic_text

def create_annotated_image(img: Image.Image, texts_dict: Dict, ui_fields: List[Dict]) -> Optional[Image.Image]:
    """
    Draws user inputs onto the original image for preview.
    """
    if not img or not texts_dict or not ui_fields:
        return None
        
    annotated = img.copy()
    draw = ImageDraw.Draw(annotated)
    
    # Calculate the default font size based on average field height
    total_height = 0
    field_count = 0
    for field in ui_fields:
        if field['type'] == 'textbox':
            _, _, _, h = field['original_box']
            total_height += h
            field_count += 1
    
    # Default font size is 50% of average field height
    default_font_size = int((total_height / max(1, field_count)) * 0.5)
    
    # Try to load Arabic font first, then fall back to regular fonts
    try:
        default_font = ImageFont.truetype("arial.ttf", default_font_size)
        arabic_font = ImageFont.truetype("arialbd.ttf", default_font_size)  # Arial Bold works better for Arabic
    except Exception:
        default_font = ImageFont.load_default()
        arabic_font = default_font
    
    # Function to get text dimensions
    def get_text_dimensions(text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            return draw.textsize(text, font=font)
    
    for field in ui_fields:
        box_id = field['box_id']
        value = texts_dict.get(box_id)
        
        if value:
            x, y, w, h = field['original_box']
            field_type = field['type']

            if field_type == 'checkbox' and value is True:
                # Draw a better and more natural checkmark
                checkmark_char = '✓'
                
                # Make font size proportional to the box size for a good fit
                font_size = int(min(w, h) * 0.9)
                
                try:
                    # Segoe UI Symbol font has a good checkmark character
                    font = ImageFont.truetype("seguisym.ttf", font_size)
                except IOError:
                    try:
                        # Try to load a bold font for a thicker checkmark
                        font = ImageFont.truetype("arialbd.ttf", font_size)
                    except IOError:
                        try:
                            # Fallback to regular arial
                            font = ImageFont.truetype("arial.ttf", font_size)
                        except IOError:
                            # Final fallback
                            font = ImageFont.load_default()

                # Get text size for centering
                try: # Modern Pillow
                    text_bbox = draw.textbbox((0, 0), checkmark_char, font=font)
                    text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
                except AttributeError: # Older Pillow
                    text_w, text_h = draw.textsize(checkmark_char, font=font)

                # Calculate position for centering the checkmark inside the box
                text_x = x + (w - text_w) / 2
                text_y = y + (h - text_h) / 2 - (h * 0.05)
                
                # Draw the checkmark
                draw.text((text_x, text_y), checkmark_char, fill="black", font=font)
            elif field_type == 'textbox' and isinstance(value, str) and value.strip():
                padding = 4  # Padding from field edges
                
                is_arabic = is_arabic_text(value)
                current_font = arabic_font if is_arabic else default_font
                
                display_text = get_display(arabic_reshaper.reshape(value)) if is_arabic else value
                
                # --- Find optimal font size that fits ---
                # This logic is extracted to avoid duplication and find the best font.
                def find_optimal_font(text_to_check: str, initial_size: int) -> ImageFont.ImageFont:
                    min_font_size, max_font_size = 8, initial_size
                    font_to_use = None
                    
                    # Check if the initial font already fits
                    try:
                        font_candidate = ImageFont.truetype("arialbd.ttf" if is_arabic else "arial.ttf", initial_size)
                        bbox = draw.textbbox((0, 0), text_to_check, font=font_candidate)
                        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                        if text_w <= (w - 2 * padding) and text_h <= (h - 2 * padding):
                            return font_candidate # Initial size is perfect
                    except Exception:
                        pass # Font loading might fail, proceed to binary search

                    # Binary search for the best font size if initial size is too large
                    while min_font_size <= max_font_size:
                        current_size = (min_font_size + max_font_size) // 2
                        try:
                            font_candidate = ImageFont.truetype("arialbd.ttf" if is_arabic else "arial.ttf", current_size)
                            bbox = draw.textbbox((0, 0), text_to_check, font=font_candidate)
                            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                            
                            if text_w <= (w - 2 * padding) and text_h <= (h - 2 * padding):
                                font_to_use = font_candidate
                                min_font_size = current_size + 1
                            else:
                                max_font_size = current_size - 1
                        except Exception:
                            max_font_size = current_size - 1 # Font may not support this size

                    return font_to_use or ImageFont.load_default()

                current_font = find_optimal_font(display_text, default_font_size)

                # --- Draw text using robust 'anchor' alignment ---
                # This method is more reliable than manual calculations.
                try:
                    # Vertically center the text in the middle of the field's height
                    draw_y = y + h / 2
                    if is_arabic:
                        # For Arabic, align text to the right, centered vertically
                        draw.text((x + w - padding, draw_y), display_text, fill="black", font=current_font, anchor="rm")
                    else:
                        # For LTR, align text to the left, centered vertically
                        draw.text((x + padding, draw_y), display_text, fill="black", font=current_font, anchor="lm")

                except TypeError:
                    # --- Fallback for older Pillow versions without 'anchor' support ---
                    try: # Get accurate bounding box
                        bbox = draw.textbbox((0, 0), display_text, font=current_font)
                        text_height = bbox[3] - bbox[1]
                        text_width = bbox[2] - bbox[0]
                    except AttributeError: # Fallback to less accurate textsize
                        text_width, text_height = draw.textsize(display_text, font=current_font)

                    # Manually calculate position
                    draw_y = y + (h - text_height) / 2 # Vertically center
                    if is_arabic:
                        draw_x = x + w - text_width - padding
                        draw.text((draw_x, draw_y), display_text, fill="black", font=current_font)
                    else:
                        draw_x = x + padding
                        draw.text((draw_x, draw_y), display_text, fill="black", font=current_font)

    return annotated 