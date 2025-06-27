import pytesseract
from PIL import Image
from langdetect import detect, LangDetectException
from app.config import get_settings
import cv2
import numpy as np

# Configure pytesseract globally when the module is imported
settings = get_settings()
pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

class OCRService:
    """
    A service class for handling Optical Character Recognition (OCR) tasks.
    """

    def detect_text_in_region(self, image: Image.Image, box: tuple) -> tuple[str, float]:
        """
        Detects text within a specified bounding box of an image.
        """
        try:
            cropped_image = image.crop(box)
            text = pytesseract.image_to_string(cropped_image, lang='ara+eng').strip()
            conf_data = pytesseract.image_to_data(cropped_image, output_type=pytesseract.Output.DICT, lang='ara+eng')
            
            text_conf = [int(c) for i, c in enumerate(conf_data['conf']) if conf_data['text'][i].strip() != '']
            avg_conf = sum(text_conf) / len(text_conf) if text_conf else 0
            
            return text, avg_conf
        except (pytesseract.TesseractNotFoundError, LangDetectException, Exception):
            return None, 0

    def correct_image_orientation(self, image: Image.Image) -> Image.Image:
        """
        Corrects the orientation of an image based on OCR data.
        This is a placeholder and currently returns the original image.
        """
        # Note: A full implementation would use pytesseract.image_to_osd
        # to detect orientation and then rotate the image accordingly.
        return image

    def detect_language_locally(self, image: Image.Image) -> str | None:
        """
        Uses local OCR (Tesseract) and language detection to determine form direction.
        """
        try:
            # Extract text from the entire image to get a language sample
            extracted_text = pytesseract.image_to_string(image, lang='ara+eng')
            if not extracted_text.strip():
                return None # Not enough text to detect
            # Detect language from the extracted text
            lang_code = detect(extracted_text)
            return 'rtl' if lang_code == 'ar' else 'ltr'
        except (pytesseract.TesseractNotFoundError, LangDetectException, Exception):
            return None # Return None on any error
