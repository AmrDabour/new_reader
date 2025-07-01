from word2number import w2n
import re
from typing import List, Tuple

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

    # إزالة الأرقام المنفردة في بداية النص
    text = re.sub(r'^\s*\d+\s+', '', text)

    # تحويل علامات التنسيق المكتوبة كنص إلى علامات حقيقية
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    text = text.replace('\\r', '\r')
    
    # إزالة علامات التنسيق المتكررة
    text = re.sub(r'[\r\n]+', '\n', text)
    
    # تقسيم النص إلى جمل وتحديد نوعها
    sentences_with_types = _split_into_sentences(text)
    
    # تجميع الجمل في فقرات
    paragraphs = _group_sentences_into_paragraphs(sentences_with_types)
    
    # تنظيف نهاية النص من علامات التنسيق
    formatted_text = '\n\n'.join(paragraphs).strip()
    formatted_text = re.sub(r'[\r\n]+$', '', formatted_text)
    
    return formatted_text

def _split_into_sentences(text: str) -> List[Tuple[str, str]]:
    """
    تقسيم النص إلى جمل مع تحديد نوع كل جملة
    Returns: List of tuples (sentence, type)
    Types: 'title', 'list_item', 'normal', 'quote'
    """
    # تنظيف المسافات الزائدة
    text = ' '.join(text.split())
    
    sentences_with_types = []
    current_sentence = []
    
    # تقسيم النص إلى كلمات
    words = text.replace('\n', ' ').split(' ')
    
    for word in words:
        # تخطي الأرقام المنفردة
        if re.match(r'^\d+$', word):
            continue
            
        current_sentence.append(word)
        
        # التحقق من نهاية الجملة
        if word and word[-1] in '.!?؟':
            if current_sentence:
                sentence = ' '.join(current_sentence)
                sentence_type = _determine_sentence_type(sentence)
                sentences_with_types.append((sentence, sentence_type))
                current_sentence = []
    
    # إضافة آخر جملة إذا كانت موجودة
    if current_sentence:
        sentence = ' '.join(current_sentence)
        sentence_type = _determine_sentence_type(sentence)
        sentences_with_types.append((sentence, sentence_type))
    
    return sentences_with_types

def _determine_sentence_type(sentence: str) -> str:
    """
    تحديد نوع الجملة بناءً على خصائصها
    """
    sentence = sentence.strip()
    
    # التحقق من العناوين
    if (sentence.isupper() or 
        (len(sentence.split()) <= 5 and sentence[0].isupper())):
        return 'title'
    
    # التحقق من عناصر القائمة
    if (sentence[0] in '•-*#' or 
        re.match(r'^\d+\.', sentence)):
        return 'list_item'
    
    # التحقق من الاقتباسات
    if sentence.startswith('"') and sentence.endswith('"'):
        return 'quote'
    
    return 'normal'

def _group_sentences_into_paragraphs(sentences_with_types: List[Tuple[str, str]]) -> List[str]:
    """
    تجميع الجمل في فقرات بناءً على نوعها والسياق
    """
    paragraphs = []
    current_paragraph = []
    current_type = None
    
    for sentence, sentence_type in sentences_with_types:
        # تجاهل الجمل الفارغة
        if not sentence.strip():
            continue
            
        # بدء فقرة جديدة إذا:
        # 1. تغير نوع الجملة
        # 2. الجملة الحالية عنوان
        # 3. الجملة الحالية عنصر قائمة
        # 4. وصلنا للحد الأقصى للجمل في الفقرة
        if (sentence_type != current_type or
            sentence_type in ['title', 'list_item'] or
            len(current_paragraph) >= 3):
            
            if current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
            
            current_type = sentence_type
        
        # إضافة الجملة للفقرة الحالية
        current_paragraph.append(sentence)
        
        # إضافة فقرة جديدة بعد الاقتباسات والعناوين مباشرة
        if sentence_type in ['quote', 'title']:
            if current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
                current_type = None
    
    # إضافة آخر فقرة
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
    # إزالة الفقرات الفارغة والأرقام المنفردة
    return [p for p in paragraphs if p and not re.match(r'^\d+$', p)] 