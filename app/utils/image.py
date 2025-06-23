import cv2
import numpy as np
from PIL import Image

def correct_image_orientation(image: Image.Image) -> Image.Image:
    """
    Corrects image orientation by detecting edges and rotating the image accordingly.
    Args:
        image: PIL Image object
    Returns:
        PIL Image object with corrected orientation
    """
    # Convert PIL Image to OpenCV format
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Detect edges
    edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
    
    # Find lines using Hough transform
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
    
    if lines is not None:
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 != 0:  # Avoid division by zero
                angle = np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi
                if -45 <= angle <= 45:  # Consider only roughly horizontal lines
                    angles.append(angle)
        
        if angles:
            # Calculate median angle to avoid outliers
            median_angle = np.median(angles)
            
            # Get image center for rotation
            height, width = img_cv.shape[:2]
            center = (width // 2, height // 2)
            
            # Create rotation matrix
            rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            
            # Perform rotation
            rotated = cv2.warpAffine(img_cv, rotation_matrix, (width, height),
                                   flags=cv2.INTER_CUBIC,
                                   borderMode=cv2.BORDER_REPLICATE)
            
            # Convert back to PIL Image
            return Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
    
    # If no lines detected or something went wrong, return original image
    return image

def calculate_iou(box1: list, box2: list) -> float:
    """
    Calculates Intersection over Union (IoU) for two boxes.
    Box format: [x1, y1, x2, y2, ...]
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