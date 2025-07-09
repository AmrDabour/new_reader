from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from app.utils.arabic import is_arabic_text, reshape_arabic_text
from app.utils.amiri_font import amiri_manager
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

    def create_final_annotated_image(self, image: Image.Image, texts_dict: dict, ui_fields: list, signature_image_b64: Optional[str] = None, signature_field_id: Optional[str] = None):
        """
        Draws the user's final text, checkmarks, and signature onto the image.
        """
        if not texts_dict and not signature_image_b64:
            return image
            
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        
        # --- Font setup ---
        text_fields = [f for f in ui_fields if f.type == 'textbox' and f.box]
        if not text_fields:
            avg_height = 20
        else:
            avg_height = sum(f.box[3] for f in text_fields) / len(text_fields)
        default_font_size = max(12, int(avg_height * 0.6))  # Ensure minimum font size

        # Try multiple font options for better Arabic support
        arabic_font = None
        default_font = None
        
        # استخدام مدير خط Amiri للحصول على أفضل خط عربي
        arabic_font = amiri_manager.get_arabic_font(default_font_size)
        
        # خطوط افتراضية للنصوص الإنجليزية
        default_font_options = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "arial.ttf"
        ]
        
        # تحميل خط افتراضي للنصوص الإنجليزية
        default_font = None
        for font_path in default_font_options:
            try:
                default_font = ImageFont.truetype(font_path, default_font_size)
                break
            except (IOError, OSError):
                continue
        
        # الاحتياط في حالة عدم وجود خطوط
        if default_font is None:
            default_font = ImageFont.load_default()
            
        # طباعة معلومات الخطوط المحملة
        font_info = amiri_manager.get_font_info()
        print(f"🎯 نوع الخط المستخدم للعربية: {font_info['font_name']}")
        print(f"📍 مسار الخط: {font_info['best_font_path']}")

        # --- Signature Handling ---
        if signature_image_b64 and signature_field_id:
            try:
                sig_bytes = base64.b64decode(signature_image_b64)
                sig_image = Image.open(io.BytesIO(sig_bytes)).convert("RGBA")

                # Find the specific signature field by its ID
                signature_field_found = False
                for field in ui_fields:
                    if field.box_id == signature_field_id and field.box:
                        signature_field_found = True
                        x, y, w, h = map(int, field.box)  # Convert to integers
                        
                        # Resize signature to fit the box with better scaling
                        # Calculate aspect ratios
                        box_ratio = w / h
                        sig_ratio = sig_image.width / sig_image.height
                        
                        # Scale to fit within the box while maintaining aspect ratio
                        if sig_ratio > box_ratio:
                            # Signature is wider, scale by width
                            new_width = int(w * 0.8)  # Use 80% of box width for padding
                            new_height = int(new_width / sig_ratio)
                        else:
                            # Signature is taller, scale by height
                            new_height = int(h * 0.8)  # Use 80% of box height for padding
                            new_width = int(new_height * sig_ratio)
                        
                        # Resize the signature
                        sig_image = sig_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        
                        # Calculate position to center the signature in the box
                        paste_x = int(x + (w - new_width) // 2)
                        paste_y = int(y + (h - new_height) // 2)
                        
                        # Paste the signature
                        annotated.paste(sig_image, (paste_x, paste_y), sig_image)
                        
                        # Remove this field from text processing
                        if field.box_id in texts_dict:
                            del texts_dict[field.box_id]
                        break
                    
            except Exception as e:
                print(f"Error processing signature: {e}")
                import traceback
                traceback.print_exc()
        elif signature_image_b64:
            # Fallback: if signature_field_id is not provided, use the old method
            try:
                sig_bytes = base64.b64decode(signature_image_b64)
                sig_image = Image.open(io.BytesIO(sig_bytes)).convert("RGBA")

                for field in ui_fields:
                    if any(keyword in field.label.lower() for keyword in ["signature", "توقيع", "امضاء"]) and field.box:
                        x, y, w, h = map(int, field.box)  # Convert to integers
                        
                        # Apply the same improved scaling logic
                        box_ratio = w / h
                        sig_ratio = sig_image.width / sig_image.height
                        
                        if sig_ratio > box_ratio:
                            new_width = int(w * 0.8)
                            new_height = int(new_width / sig_ratio)
                        else:
                            new_height = int(h * 0.8)
                            new_width = int(new_height * sig_ratio)
                        
                        sig_image = sig_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        
                        paste_x = int(x + (w - new_width) // 2)
                        paste_y = int(y + (h - new_height) // 2)
                        
                        annotated.paste(sig_image, (paste_x, paste_y), sig_image)
                        
                        if field.box_id in texts_dict:
                            del texts_dict[field.box_id]
                        break
            except Exception as e:
                print(f"Error processing signature: {e}")

        # --- Text and Checkbox Drawing ---
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
                    
                    # Enhanced Arabic text processing using Amiri font manager
                    if is_arabic:
                        # استخدام الدالة الجديدة لمعالجة النص العربي بشكل صحيح
                        # نحتاج إلى إعادة تشكيل الحروف فقط بدون عكس الاتجاه
                        display_text = reshape_arabic_text(value, for_display=False)
                        font = arabic_font
                    else:
                        display_text = value
                        font = default_font
                    
                    # Calculate text size more accurately
                    try:
                        text_bbox = draw.textbbox((0, 0), display_text, font=font)
                        text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
                    except AttributeError:
                        # Fallback for older PIL versions
                        text_w, text_h = draw.textsize(display_text, font=font)
                    
                    # Adjust font size if text is too large for the box
                    if text_w > (w - 2*padding):
                        scale_factor = (w - 2*padding) / text_w
                        new_font_size = max(8, int(default_font_size * scale_factor))
                        
                        if is_arabic:
                            # استخدام مدير Amiri للحصول على خط بحجم جديد
                            font = amiri_manager.get_arabic_font(new_font_size)
                            print(f"🎯 تعديل حجم خط Amiri إلى: {new_font_size}")
                        else:
                            # تحديث الخط الافتراضي بالحجم الجديد
                            for font_path in default_font_options:
                                try:
                                    font = ImageFont.truetype(font_path, new_font_size)
                                    break
                                except (IOError, OSError):
                                    continue
                        
                        if font is None:
                            font = ImageFont.load_default()
                    
                    # Position text in the middle of the box
                    draw_y = y + h / 2
                    
                    if is_arabic:
                        # Right-align Arabic text and use correct text direction
                        # النص العربي تم إعادة تشكيله فقط وبالفعل في الاتجاه الصحيح من اليمين لليسار
                        draw.text((x + w - padding, draw_y), display_text, fill="black", font=font, anchor="rm")
                    else:
                        # Left-align English text
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