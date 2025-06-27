from word2number import w2n

# This map can be expanded
ARABIC_NUMBER_MAP = {
    'صفر': '0', 'زيرو': '0',
    'واحد': '1', 'اثنين': '2', 'اثنان': '2',
    'ثلاثة': '3', 'ثلاثه': '3', 'أربعة': '4', 'اربعه': '4',
    'خمسة': '5', 'خمسه': '5', 'ستة': '6', 'سته': '6',
    'سبعة': '7', 'سبعه': '7', 'ثمانية': '8', 'ثمانيه': '8',
    'تسعة': '9', 'تسعه': '9', 'عشرة': '10', 'عشره': '10'
}

def process_transcript(text: str, lang: str) -> str:
    """
    Cleans up a transcript by removing punctuation and converting number words to digits.
    """
    processed_text = text.strip(".,;:\"'")
    words = processed_text.split()
    
    if lang == 'en':
        try:
            return str(w2n.word_to_num(processed_text))
        except ValueError:
            # Handle cases where not all words are numbers
            converted_words = [str(w2n.word_to_num(w)) if w in w2n.W2N.number_system else w for w in words]
            return " ".join(converted_words)
    
    elif lang == 'ar':
        converted_words = [ARABIC_NUMBER_MAP.get(w, w) for w in words]
        
        # Join adjacent digits
        final_text = []
        for i, word in enumerate(converted_words):
            if word.isdigit() and i > 0 and final_text[-1].isdigit():
                final_text[-1] += word
            else:
                final_text.append(word)
        return " ".join(final_text)

    return " ".join(words) 