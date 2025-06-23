import pytesseract
from PIL import Image
from langdetect import detect, LangDetectException
from ..config import TESSERACT_CMD

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def detect_text_in_region(image: Image.Image, box: tuple) -> tuple[str, float]:
    """
    Detect text within a specific region of the image using Tesseract OCR.
    Args:
        image: PIL Image object
        box: Tuple of (x1, y1, x2, y2) coordinates
    Returns:
        Tuple of (detected text string, confidence score)
    """
    try:
        # Crop the image to the specified region
        x1, y1, x2, y2 = [int(coord) for coord in box[:4]]
        region = image.crop((x1, y1, x2, y2))
        
        # Get detailed OCR data including confidence scores
        ocr_data = pytesseract.image_to_data(region, lang='ara+eng', output_type=pytesseract.Output.DICT)
        
        # Combine all detected text and get average confidence
        texts = [word for word in ocr_data['text'] if str(word).strip()]
        confidences = [conf for i, conf in enumerate(ocr_data['conf']) if str(ocr_data['text'][i]).strip()]
        
        if texts and confidences:
            avg_confidence = sum(confidences) / len(confidences)
            return " ".join(texts), avg_confidence
        return "", 0.0
    except Exception as e:
        print(f"Error detecting text in region: {e}")
        return "", 0.0

def detect_language_locally(image: Image.Image) -> str | None:
    """
    Uses local OCR (Tesseract) and language detection to determine form direction.
    Returns 'rtl', 'ltr', or None if detection fails.
    """
    try:
        # Perform OCR on the image to extract text
        extracted_text = pytesseract.image_to_string(image, lang='ara+eng')
        
        # If no text is found, we can't determine the language
        if not extracted_text.strip():
            return None
            
        # Detect the language of the extracted text
        lang_code = detect(extracted_text)
        
        # Return direction based on language code
        if lang_code == 'ar':
            return 'rtl'
        else:
            return 'ltr'
            
    except Exception as e:
        print(f"Error in language detection: {e}")
        return None 