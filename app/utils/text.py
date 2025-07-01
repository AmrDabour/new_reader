from word2number import w2n
import re
from typing import List

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
            # First, try to convert the whole string
            return str(w2n.word_to_num(processed_text))
        except ValueError:
            # If that fails, try converting word by word
            converted_words = []
            for word in words:
                try:
                    converted_words.append(str(w2n.word_to_num(word)))
                except ValueError:
                    converted_words.append(word)
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

def clean_and_format_text(text: str) -> str:
    """
    تنظيف وتنسيق النص لجعله أكثر قابلية للقراءة
    """
    if not text:
        return ""

    # تحويل علامات التنسيق المكتوبة كنص إلى علامات حقيقية
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    text = text.replace('\\r', '\r')
    
    # إزالة علامات التنسيق المتكررة
    text = re.sub(r'[\r\n]+', '\n', text)
    
    # تقسيم النص إلى جمل
    sentences = _split_into_sentences(text)
    
    # تجميع الجمل في فقرات
    paragraphs = _group_sentences_into_paragraphs(sentences)
    
    # تنسيق النص النهائي
    return '\n\n'.join(paragraphs).strip()

def _split_into_sentences(text: str) -> List[str]:
    """
    تقسيم النص إلى جمل مع الحفاظ على علامات الترقيم
    """
    # تنظيف المسافات الزائدة
    text = ' '.join(text.split())
    
    # تقسيم النص إلى جمل
    sentences = []
    current_sentence = []
    
    # تقسيم النص إلى كلمات مع الحفاظ على علامات الترقيم
    words = text.replace('\n', ' ').split(' ')
    
    for word in words:
        current_sentence.append(word)
        
        # التحقق من نهاية الجملة
        if word and word[-1] in '.!?؟':
            sentences.append(' '.join(current_sentence))
            current_sentence = []
    
    # إضافة آخر جملة إذا كانت موجودة
    if current_sentence:
        sentences.append(' '.join(current_sentence))
    
    return sentences

def _group_sentences_into_paragraphs(sentences: List[str]) -> List[str]:
    """
    تجميع الجمل في فقرات
    """
    paragraphs = []
    current_paragraph = []
    
    for sentence in sentences:
        # تنظيف الجملة
        clean_sentence = sentence.strip()
        if not clean_sentence:
            continue
            
        # بدء فقرة جديدة للعناوين والقوائم
        if (clean_sentence.isupper() or 
            clean_sentence[0] in '•-*#' or 
            re.match(r'^\d+\.', clean_sentence)):
            if current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
            paragraphs.append(clean_sentence)
            continue
        
        current_paragraph.append(clean_sentence)
        
        # إنشاء فقرة جديدة بعد عدد معين من الجمل
        if len(current_paragraph) >= 5:
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []
    
    # إضافة آخر فقرة إذا كانت موجودة
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    
    return paragraphs

def extract_paragraphs(text: str) -> List[str]:
    """
    استخراج الفقرات من النص
    """
    # تنظيف النص أولاً
    cleaned_text = clean_and_format_text(text)
    # تقسيم النص إلى فقرات
    paragraphs = [p.strip() for p in cleaned_text.split('\n\n')]
    # إزالة الفقرات الفارغة
    return [p for p in paragraphs if p] 