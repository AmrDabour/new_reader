import functools
import arabic_reshaper
from bidi.algorithm import get_display

def is_arabic_text(text):
    """Checks if a string contains Arabic characters."""
    arabic_ranges = [
        (0x0600, 0x06FF),   # Arabic
        (0x0750, 0x077F),   # Arabic Supplement
        (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
    ]
    return any(any(ord(char) >= start and ord(char) <= end for start, end in arabic_ranges) for char in text)

def reshape_arabic_text(text, for_display=False, base_dir='R'):
    """
    Process Arabic text for correct display using arabic_reshaper
    
    المعاملات:
        text: Original text
        for_display: If True, applies get_display to reverse text direction (useful for environments that don't support RTL)
        base_dir: Base text direction ('R' for RTL or 'L' for LTR)
    
    العودة:
        Text after reshaping Arabic characters (with/without direction reversal)
    """
    try:
        # Clean text
        cleaned_text = text.strip()
        
        # Reshape Arabic text
        reshaped_text = arabic_reshaper.reshape(cleaned_text)
        
        # If we're displaying text in environment that needs direction reversal
        if for_display:
            return get_display(reshaped_text, base_dir=base_dir)
            
        # Otherwise return text after character reshaping only
        return reshaped_text
    except Exception as e:
        return text

def compare_boxes(is_rtl, item1, item2):
    """
    Custom comparison function to sort boxes in natural reading order (LTR or RTL).
    """
    b1 = item1['box'] # (x, y, w, h)
    b2 = item2['box']
    
    y_center1 = b1[1] + b1[3] / 2
    y_center2 = b2[1] + b2[3] / 2
    
    # Y-tolerance to consider boxes on the same line
    y_tolerance = (b1[3] + b2[3]) / 4

    if abs(y_center1 - y_center2) < y_tolerance:
        # Boxes are on the same line
        if is_rtl:
            return b2[0] - b1[0]  # Right-to-left
        else:
            return b1[0] - b2[0]  # Left-to-right
    else:
        # Boxes are on different lines, sort top-to-bottom
        return y_center1 - y_center2 