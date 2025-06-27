from ultralytics import YOLO
import numpy as np
from app.config import get_settings
from app.services.ocr import OCRService
from app.utils.image_helpers import calculate_iou
from app.utils.arabic import compare_boxes
import functools
from PIL import Image

settings = get_settings()

class YOLOService:
    def __init__(self):
        self.boxes_model = YOLO(settings.boxes_model_path)
        self.dot_line_model = YOLO(settings.dot_line_model_path)
        self.ocr_service = OCRService()

    def detect_fields(self, image: Image.Image):
        """
        Runs both YOLO models, combines results, filters overlapping boxes,
        and sorts them in reading order.
        """
        # 1. Run both YOLO models
        arr = np.array(image)
        r1 = self.boxes_model.predict(source=arr, classes=[0, 1, 2], conf=0.15, iou=0.02, stream=False)[0]
        r2 = self.dot_line_model.predict(source=arr, classes=[8], conf=0.15, iou=0.1, stream=False)[0]

        # 2. Combine and filter based on OCR (if text already exists)
        filtered_boxes = []
        for b in r1.boxes:
            box_coords = b.xyxy[0].tolist()
            detected_text, text_conf = self.ocr_service.detect_text_in_region(image, box_coords)
            if detected_text and text_conf > 50:
                continue
            filtered_boxes.append(box_coords + [b.conf[0].item(), r1.names.get(int(b.cls[0]))])
        
        for b in r2.boxes:
            box_coords = b.xyxy[0].tolist()
            filtered_boxes.append(box_coords + [b.conf[0].item(), r2.names.get(int(b.cls[0]))])

        # 3. Non-Maximum Suppression (NMS)
        def get_sort_key(box_data):
            confidence = box_data[4]
            class_name = str(box_data[5]).lower()
            priority = 1 if 'text' in class_name or 'line' in class_name else 0
            return (priority, confidence)
        filtered_boxes.sort(key=get_sort_key, reverse=True)
        
        final_boxes = []
        iou_threshold = 0.4
        while filtered_boxes:
            best_box = filtered_boxes.pop(0)
            final_boxes.append(best_box)
            filtered_boxes = [b for b in filtered_boxes if calculate_iou(best_box, b) < iou_threshold]

        # 4. Determine language and sort
        lang_direction = self.ocr_service.detect_language_locally(image) or 'ltr'
        is_rtl = (lang_direction == 'rtl')
        
        fields_data = []
        for b in final_boxes:
            x1, y1, x2, y2, _, class_name = b
            fields_data.append({"box": (int(x1), int(y1), int(x2 - x1), int(y2 - y1)), "class": class_name})
        
        fields_data.sort(key=functools.cmp_to_key(lambda item1, item2: compare_boxes(is_rtl, item1, item2)))
        
        return fields_data, lang_direction 