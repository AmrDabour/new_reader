import pytesseract
from PIL import Image
from langdetect import detect, LangDetectException
from app.config import get_settings
import cv2
import numpy as np

settings = get_settings()
pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

class OCRService:
    def __init__(self):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    def detect_text_in_region(self, image: Image.Image, box: tuple) -> tuple[str, float]:
        """
        Detect text within a specific region of the image using Tesseract OCR.
        """
        try:
            x1, y1, x2, y2 = [int(coord) for coord in box[:4]]
            region = image.crop((x1, y1, x2, y2))
            
            ocr_data = pytesseract.image_to_data(region, lang='ara+eng', output_type=pytesseract.Output.DICT)
            
            texts = [word for word in ocr_data['text'] if str(word).strip()]
            confidences = [conf for i, conf in enumerate(ocr_data['conf']) if str(ocr_data['text'][i]).strip()]
            
            if texts and confidences:
                avg_confidence = sum(confidences) / len(confidences)
                return " ".join(texts), avg_confidence
            return "", 0.0
        except Exception:
            return "", 0.0

    def detect_language_locally(self, image: Image.Image) -> str | None:
        """
        Uses local OCR (Tesseract) and language detection to determine form direction.
        """
        try:
            extracted_text = pytesseract.image_to_string(image, lang='ara+eng')
            if not extracted_text.strip():
                return None
            lang_code = detect(extracted_text)
            return 'rtl' if lang_code == 'ar' else 'ltr'
        except (pytesseract.TesseractNotFoundError, LangDetectException, Exception):
            return None 