from typing import Dict

ARABIC_NUMBER_MAP: Dict[str, str] = {
    'صفر': '0', 'زيرو': '0',
    'واحد': '1',
    'اثنين': '2', 'اثنان': '2',
    'ثلاثة': '3', 'ثلاثه': '3',
    'أربعة': '4', 'اربعه': '4',
    'خمسة': '5', 'خمسه': '5',
    'ستة': '6', 'سته': '6',
    'سبعة': '7', 'سبعه': '7',
    'ثمانية': '8', 'ثمانيه': '8',
    'تسعة': '9', 'تسعه': '9',
    'عشرة': '10', 'عشره': '10'
}

def process_transcript(text: str, lang: str) -> str:
    """
    Cleans up a transcript by removing punctuation and converting number words to digits.
    """
    from word2number import w2n

    # Strip leading/trailing whitespace and punctuation
    punctuation_to_remove = ".,;:\"'"
    for p in punctuation_to_remove:
        text = text.replace(p, '')
    processed_text = text.strip()

    # Convert number words to digits
    words = processed_text.split()
    
    if lang == 'en':
        try:
            return str(w2n.word_to_num(processed_text))
        except ValueError:
            converted_words = []
            for word in words:
                try:
                    converted_words.append(str(w2n.word_to_num(word)))
                except ValueError:
                    converted_words.append(word)
            return " ".join(converted_words)
    
    elif lang == 'ar':
        converted_words = []
        for word in words:
            converted_words.append(ARABIC_NUMBER_MAP.get(word, word))
        
        # Join adjacent digits, but keep spaces around non-digits
        final_text = []
        for i, word in enumerate(converted_words):
            is_digit = word.isdigit()
            is_prev_digit = (i > 0 and converted_words[i-1].isdigit())
            
            if is_digit and is_prev_digit:
                final_text[-1] += word # Append to the previous digit string
            else:
                final_text.append(word) # Add as a new item
        
        return " ".join(final_text)

    # Fallback for any other case
    return " ".join(words) 