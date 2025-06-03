# filepath: c:\Users\moham\OneDrive\Desktop\new_reader\image_utils.py
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
from google.cloud import vision
import os
import tempfile

def correct_perspective(image_path):
    """
    تصحيح منظور الصورة إذا كانت مأخوذة بزاوية
    """
    try:
        # قراءة الصورة
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # تطبيق Gaussian blur لتقليل الضوضاء
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # اكتشاف الحواف
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
        
        # العثور على الخطوط باستخدام Hough Transform
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        if lines is not None and len(lines) > 4:
            # العثور على الزوايا الأربع للمستند
            corners = find_document_corners(lines, img.shape)
            
            if corners is not None:
                # تطبيق تصحيح المنظور
                corrected_img = apply_perspective_correction(img, corners)
                
                # حفظ الصورة المصححة
                corrected_path = image_path.replace('.', '_corrected.')
                cv2.imwrite(corrected_path, corrected_img)
                return corrected_path
        
        # إذا فشل تصحيح المنظور، إرجاع الصورة الأصلية
        return image_path
        
    except Exception as e:
        print(f"Error in perspective correction: {e}")
        return image_path

def find_document_corners(lines, img_shape):
    """
    العثور على زوايا المستند من الخطوط المكتشفة
    """
    try:
        height, width = img_shape[:2]
        
        # تصنيف الخطوط إلى أفقية وعمودية
        horizontal_lines = []
        vertical_lines = []
        
        for line in lines:
            rho, theta = line[0]
            angle = np.degrees(theta)
            
            if abs(angle) < 30 or abs(angle - 180) < 30:  # خطوط أفقية
                horizontal_lines.append((rho, theta))
            elif abs(angle - 90) < 30:  # خطوط عمودية
                vertical_lines.append((rho, theta))
        
        if len(horizontal_lines) >= 2 and len(vertical_lines) >= 2:
            # العثور على أقصى خطوط
            h_top = min(horizontal_lines, key=lambda x: abs(x[0]))
            h_bottom = max(horizontal_lines, key=lambda x: abs(x[0]))
            v_left = min(vertical_lines, key=lambda x: abs(x[0]))
            v_right = max(vertical_lines, key=lambda x: abs(x[0]))
            
            # حساب نقاط التقاطع
            corners = []
            for h_line in [h_top, h_bottom]:
                for v_line in [v_left, v_right]:
                    intersection = line_intersection(h_line, v_line)
                    if intersection is not None:
                        corners.append(intersection)
            
            if len(corners) == 4:
                return np.array(corners, dtype=np.float32)
        
        return None
        
    except Exception as e:
        print(f"Error finding corners: {e}")
        return None

def line_intersection(line1, line2):
    """
    حساب نقطة تقاطع خطين
    """
    try:
        rho1, theta1 = line1
        rho2, theta2 = line2
        
        A = np.array([
            [np.cos(theta1), np.sin(theta1)],
            [np.cos(theta2), np.sin(theta2)]
        ])
        b = np.array([[rho1], [rho2]])
        
        x0 = np.linalg.solve(A, b)
        x, y = int(np.round(x0[0])), int(np.round(x0[1]))
        
        return (x, y)
        
    except:
        return None

def apply_perspective_correction(img, corners):
    """
    تطبيق تصحيح المنظور باستخدام النقاط الأربع
    """
    try:
        # ترتيب النقاط: أعلى يسار، أعلى يمين، أسفل يمين، أسفل يسار
        corners = order_points(corners)
        
        # حساب العرض والارتفاع الجديدين
        width = max(
            np.linalg.norm(corners[0] - corners[1]),
            np.linalg.norm(corners[2] - corners[3])
        )
        height = max(
            np.linalg.norm(corners[0] - corners[3]),
            np.linalg.norm(corners[1] - corners[2])
        )
        
        # النقاط المستهدفة (مستطيل مثالي)
        dst_points = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1]
        ], dtype=np.float32)
        
        # حساب مصفوفة التحويل
        matrix = cv2.getPerspectiveTransform(corners, dst_points)
        
        # تطبيق التحويل
        corrected = cv2.warpPerspective(img, matrix, (int(width), int(height)))
        
        return corrected
        
    except Exception as e:
        print(f"Error applying perspective correction: {e}")
        return img

def order_points(pts):
    """
    ترتيب النقاط بالترتيب الصحيح
    """
    # ترتيب النقاط حسب مجموع إحداثياتها
    sum_pts = pts.sum(axis=1)
    diff_pts = np.diff(pts, axis=1)
    
    rect = np.zeros((4, 2), dtype=np.float32)
    
    # أعلى يسار = أقل مجموع
    rect[0] = pts[np.argmin(sum_pts)]
    # أسفل يمين = أكبر مجموع
    rect[2] = pts[np.argmax(sum_pts)]
    # أعلى يمين = أقل فرق
    rect[1] = pts[np.argmin(diff_pts)]
    # أسفل يسار = أكبر فرق
    rect[3] = pts[np.argmax(diff_pts)]
    
    return rect

def extract_field_positions_with_vision(image_path):
    """
    استخدام Google Vision API لاكتشاف مواضع النصوص والحقول في الصورة
    مع تحسينات لتجميع الحقول ذات الصلة
    """
    try:
        # تطبيق تصحيح المنظور أولاً
        corrected_image_path = correct_perspective(image_path)
        
        client = vision.ImageAnnotatorClient()
        
        with open(corrected_image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        
        if response.error.message:
            raise Exception(f'{response.error.message}')
        
        field_positions = []
        
        # تجاهل النص الأول لأنه يحتوي على كامل النص
        for text in texts[1:]:
            vertices = text.bounding_poly.vertices
            x_coords = [vertex.x for vertex in vertices]
            y_coords = [vertex.y for vertex in vertices]
            
            # تصفية النصوص القصيرة جداً أو التي تحتوي على أرقام فقط
            text_content = text.description.strip()
            if len(text_content) < 2 or text_content.isdigit():
                continue
            
            # البحث عن علامات تدل على أن هذا حقل (مثل النقطتين أو الشرطة)
            is_field = any(char in text_content for char in [':', '_', '___', '...', '____'])
            
            center_x = sum(x_coords) // len(x_coords)
            center_y = sum(y_coords) // len(y_coords)
            text_width = max(x_coords) - min(x_coords)
            
            # تحديد موضع الكتابة
            if is_field:
                # إذا كان حقل، نكتب في نفس الموضع
                write_x = center_x
                write_y = center_y
            else:
                # إذا كان تسمية، نكتب بجانبه
                write_x = max(x_coords) + 20
                write_y = center_y
            
            field_positions.append({
                'label': text_content,
                'x': write_x,
                'y': write_y,
                'confidence': text.confidence if hasattr(text, 'confidence') else 1.0,
                'is_field': is_field,
                'bounds': {
                    'left': min(x_coords),
                    'top': min(y_coords),
                    'right': max(x_coords),
                    'bottom': max(y_coords)
                }
            })
        
        # تنظيف ملف الصورة المؤقت
        if corrected_image_path != image_path:
            try:
                os.unlink(corrected_image_path)
            except:
                pass
        
        return field_positions
        
    except Exception as e:
        print(f"Error in Vision API: {e}")
        return []

def write_text_on_image(image, field_positions, responses):
    """
    كتابة النصوص على الصورة في المواضع المحددة
    
    Args:
        image: صورة PIL
        field_positions: قائمة بمواضع الحقول
        responses: قاموس الإجابات
    
    Returns:
        صورة PIL مع النصوص المكتوبة
    """
    try:
        # نسخ الصورة لتجنب تعديل الأصل
        img_copy = image.copy()
        
        # تحويل إلى RGB إذا كانت RGBA
        if img_copy.mode == 'RGBA':
            img_copy = img_copy.convert('RGB')
        
        draw = ImageDraw.Draw(img_copy)
        
        # محاولة استخدام خط مناسب
        try:
            # حجم الخط بناءً على حجم الصورة
            font_size = max(12, min(24, img_copy.width // 50))
            font = ImageFont.truetype("arial.ttf", size=font_size)
        except:
            try:
                font = ImageFont.load_default()
            except:
                font = None
        
        # كتابة كل إجابة في موضعها
        for field_data in field_positions:
            field_label = field_data['label']
            
            # البحث عن الإجابة المناسبة
            response_text = None
            for response_key, response_value in responses.items():
                if response_value and (
                    response_key.lower() in field_label.lower() or
                    field_label.lower() in response_key.lower() or
                    calculate_text_similarity(response_key.lower(), field_label.lower()) > 0.6
                ):
                    response_text = str(response_value)
                    break
            
            if response_text:
                x = field_data['x']
                y = field_data['y']
                
                # التأكد من أن النص داخل حدود الصورة
                x = max(5, min(x, img_copy.width - 100))
                y = max(15, min(y, img_copy.height - 15))
                
                # إضافة خلفية بيضاء للنص لجعله أكثر وضوحاً
                if font:
                    bbox = draw.textbbox((x, y), response_text, font=font)
                    draw.rectangle(bbox, fill='white', outline='lightgray')
                
                # كتابة النص باللون الأزرق الداكن
                draw.text((x, y), response_text, fill=(0, 0, 139), font=font)
        
        return img_copy
        
    except Exception as e:
        print(f"Error writing text on image: {e}")
        return image

def prepare_image_for_word(image):
    """
    تحضير الصورة لإدراجها في ملف Word
    
    Args:
        image: صورة PIL
        
    Returns:
        صورة PIL محسّنة
    """
    try:
        # نسخ الصورة
        img_copy = image.copy()
        
        # تحويل إلى RGB إذا لزم الأمر
        if img_copy.mode != 'RGB':
            img_copy = img_copy.convert('RGB')
        
        # تقليل الحجم إذا كانت الصورة كبيرة (أكثر من 1000 بكسل عرضاً)
        max_width = 800
        if img_copy.width > max_width:
            ratio = max_width / img_copy.width
            new_height = int(img_copy.height * ratio)
            img_copy = img_copy.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        return img_copy
        
    except Exception as e:
        print(f"Error preparing image for Word: {e}")
        return image

def detect_form_fields(image_path):
    """
    اكتشاف الحقول الفارغة في النموذج باستخدام تحليل الصورة
    """
    try:
        # قراءة الصورة
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # اكتشاف الخطوط الأفقية (قد تكون حقول للكتابة)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        
        # اكتشاف المستطيلات (قد تكون صناديق للاختيار)
        contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        fields = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # فلترة المناطق الصغيرة جداً أو الكبيرة جداً
            if w > 50 and h > 5 and w < 500 and h < 50:
                fields.append({
                    'x': x,
                    'y': y + h//2,  # وسط الحقل
                    'width': w,
                    'height': h,
                    'type': 'text_field'
                })
        
        return fields
        
    except Exception as e:
        print(f"Error detecting form fields: {e}")
        return []

def find_best_text_position(image_path, detected_text, target_field):
    """
    العثور على أفضل موضع لكتابة النص بناءً على الحقل المطلوب
    """
    try:
        # استخدام Vision API للعثور على النص
        field_positions = extract_field_positions_with_vision(image_path)
        
        # البحث عن أقرب تطابق للحقل المطلوب
        best_match = None
        best_score = 0
        
        for detected_field, position in field_positions.items():
            # حساب التشابه بين الحقل المكتشف والحقل المطلوب
            similarity = calculate_text_similarity(detected_field.lower(), target_field.lower())
            if similarity > best_score:
                best_score = similarity
                best_match = position
        
        if best_match and best_score > 0.3:  # حد أدنى للتشابه
            return best_match
        
        # إذا لم نجد تطابق جيد، نستخدم موضع افتراضي
        return {'x': 100, 'y': 100}
        
    except Exception as e:
        print(f"Error finding text position: {e}")
        return {'x': 100, 'y': 100}

def calculate_text_similarity(text1, text2):
    """
    حساب التشابه بين نصين
    """
    from difflib import SequenceMatcher
    return SequenceMatcher(None, text1, text2).ratio()