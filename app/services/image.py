from PIL import Image, ImageDraw, ImageFont
from app.utils.arabic import is_arabic_text
from bidi.algorithm import get_display
import arabic_reshaper
import cv2
import numpy as np
import io, base64

class ImageService:
    def correct_image_orientation(self, image: Image.Image) -> Image.Image:
        """
        Corrects image orientation by detecting edges and rotating the image.
        """
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
        
        if lines is not None:
            angles = [np.arctan2(l[0][3] - l[0][1], l[0][2] - l[0][0]) * 180 / np.pi for l in lines if l[0][2] - l[0][0] != 0]
            if angles:
                median_angle = np.median([angle for angle in angles if -45 <= angle <= 45])
                h, w = img_cv.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                rotated = cv2.warpAffine(img_cv, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                return Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
        return image

    def create_annotated_image_for_gpt(self, image: Image.Image, fields_data: list, with_numbers=True):
        """
        Draws numbered boxes on the image for analysis by the AI model.
        """
        base_img = image.copy().convert("RGBA")
        overlay = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        sorted_boxes = [f['box'] for f in fields_data]
        
        for i, (x, y, w_box, h_box) in enumerate(sorted_boxes):
            draw.rectangle([x, y, x + w_box, y + h_box], fill=(0, 100, 255, 100))
            if with_numbers:
                text = str(i + 1)
                font_size = max(15, int(h_box * 0.7))
                try:
                    font = ImageFont.truetype("arialbd.ttf", font_size)
                except IOError:
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except IOError:
                        font = ImageFont.load_default()
                
                try:
                    text_bbox = draw.textbbox((0, 0), text, font=font)
                    text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
                except AttributeError:
                    text_w, text_h = draw.textsize(text, font=font)
                    
                text_x = x + (w_box - text_w) / 2
                text_y = y + (h_box - text_h) / 2
                draw.text((text_x, text_y), text, fill="red", font=font)

        return Image.alpha_composite(base_img, overlay)

    def create_final_annotated_image(self, image: Image.Image, texts_dict: dict, ui_fields: list):
        """
        Draws the user's final text and checkmarks onto the image.
        This function is a combination of logic from the original app.py
        """
        if not texts_dict or not ui_fields:
            return image
            
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        
        # Calculate default font size based on average field height
        text_fields = [f for f in ui_fields if f.type == 'textbox' and f.box]
        if not text_fields:
            avg_height = 20 # default
        else:
            avg_height = sum(f.box[3] for f in text_fields) / len(text_fields)
        default_font_size = int(avg_height * 0.5)

        try:
            default_font = ImageFont.truetype("arial.ttf", default_font_size)
            arabic_font = ImageFont.truetype("arialbd.ttf", default_font_size)
        except Exception:
            default_font = ImageFont.load_default()
            arabic_font = default_font

        for field in ui_fields:
            box_id = field.box_id
            value = texts_dict.get(box_id)
            field_box = field.box
            
            if value and field_box:
                x, y, w, h = field_box
                field_type = field.type

                if field_type == 'checkbox' and value is True:
                    checkmark_char = '✓'
                    font_size = int(min(w, h) * 0.9)
                    try: font = ImageFont.truetype("seguisym.ttf", font_size)
                    except IOError: font = ImageFont.load_default()
                    
                    try:
                        text_bbox = draw.textbbox((0, 0), checkmark_char, font=font)
                        text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
                    except AttributeError:
                        text_w, text_h = draw.textsize(checkmark_char, font=font)
                    
                    text_x = x + (w - text_w) / 2
                    text_y = y + (h - text_h) / 2
                    draw.text((text_x, text_y), checkmark_char, fill="black", font=font)

                elif field_type == 'textbox' and isinstance(value, str) and value.strip():
                    padding = 4
                    is_arabic = is_arabic_text(value)
                    display_text = get_display(arabic_reshaper.reshape(value)) if is_arabic else value
                    
                    # Very simplified font sizing for now
                    font = arabic_font if is_arabic else default_font
                    
                    draw_y = y + h / 2
                    if is_arabic:
                        draw.text((x + w - padding, draw_y), display_text, fill="black", font=font, anchor="rm")
                    else:
                        draw.text((x + padding, draw_y), display_text, fill="black", font=font, anchor="lm")
        return annotated

    def combine_yolo_and_gpt_results(self, fields_data, gpt_results):
        """
        Merges the results from YOLO (box coordinates) and GPT (labels).
        """
        final_fields = []
        gpt_map = {res['id']: res['label'] for res in gpt_results if 'id' in res and 'label' in res}
        
        for i, field_data in enumerate(fields_data):
            box_number = i + 1
            label = gpt_map.get(box_number)
            if label:
                class_name = str(field_data['class']).lower()
                field_type = "textbox" if 'text' in class_name or 'line' in class_name else "checkbox"
                final_fields.append({
                    'box_id': f"box_{i}", 
                    'label': label,
                    'type': field_type,
                    'box': field_data['box']
                })
        return final_fields 