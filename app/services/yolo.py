from ultralytics import YOLO
from PIL import Image
import numpy as np
from typing import List
from ..config import BOXES_MODEL_PATH, DOT_LINE_MODEL_PATH

class YOLOService:
    def __init__(self):
        self.boxes_model = YOLO(BOXES_MODEL_PATH)
        self.dot_line_model = YOLO(DOT_LINE_MODEL_PATH)
    
    def detect_fields(self, image: Image.Image):
        """
        Detect form fields using both YOLO models
        Returns list of detected boxes with their types
        """
        # Convert PIL Image to numpy array
        arr = np.array(image)
        
        # Run both models
        boxes_result = self.boxes_model.predict(source=arr, classes=[0, 1, 2], conf=0.15, iou=0.02, stream=False)[0]
        dot_line_result = self.dot_line_model.predict(source=arr, classes=[8], conf=0.15, iou=0.1, stream=False)[0]
        
        # Process results
        all_detections = []
        
        # Process boxes model results
        for box in boxes_result.boxes:
            coords = box.xyxy[0].tolist()  # Get coordinates in [x1, y1, x2, y2] format
            confidence = box.conf[0].item()
            class_id = int(box.cls[0].item())
            class_name = boxes_result.names[class_id]
            
            all_detections.append({
                'coords': coords,
                'confidence': confidence,
                'type': class_name
            })
        
        # Process dot/line model results
        for box in dot_line_result.boxes:
            coords = box.xyxy[0].tolist()
            confidence = box.conf[0].item()
            class_id = int(box.cls[0].item())
            class_name = dot_line_result.names[class_id]
            
            all_detections.append({
                'coords': coords,
                'confidence': confidence,
                'type': class_name
            })
        
        return all_detections

    def calculate_iou(self, box1: List[float], box2: List[float]) -> float:
        """
        Calculate Intersection over Union for two boxes
        """
        x1_inter = max(box1[0], box2[0])
        y1_inter = max(box1[1], box2[1])
        x2_inter = min(box1[2], box2[2])
        y2_inter = min(box1[3], box2[3])

        inter_area = max(0, x2_inter - x1_inter) * max(0, y2_inter - y1_inter)
        if inter_area == 0:
            return 0.0

        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])

        union_area = box1_area + box2_area - inter_area
        if union_area == 0:
            return 0.0
            
        return inter_area / union_area 