def is_arabic_text(text: str) -> bool:
    """
    Check if text contains Arabic characters
    """
    arabic_ranges = [
        (0x0600, 0x06FF),   # Arabic
        (0x0750, 0x077F),   # Arabic Supplement
        (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
    ]
    return any(
        any(ord(char) >= start and ord(char) <= end for start, end in arabic_ranges)
        for char in text
    )

def compare_boxes_rtl(item1: dict, item2: dict) -> int:
    """
    Custom comparison function to sort boxes in RTL reading order
    """
    b1 = item1['box']
    b2 = item2['box']
    
    y_center1 = b1[1] + b1[3] / 2
    y_center2 = b2[1] + b2[3] / 2
    
    # Y-tolerance to consider boxes on the same line (50% of average height)
    y_tolerance = (b1[3] + b2[3]) / 4

    if abs(y_center1 - y_center2) < y_tolerance:
        # Boxes are on the same line, sort from right to left
        return b2[0] - b1[0]
    else:
        # Boxes are on different lines, sort by Y coordinate
        return y_center1 - y_center2 