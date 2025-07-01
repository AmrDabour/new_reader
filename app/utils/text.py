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
    
    # إزالة المسافات الزائدة في بداية ونهاية كل سطر
    lines = [line.strip() for line in text.split('\n')]
    
    # إزالة الأسطر الفارغة في البداية والنهاية
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    
    # دمج الأسطر القصيرة التي تنتهي بدون علامات ترقيم
    formatted_lines = []
    current_line = ""
    
    for line in lines:
        # تخطي الأسطر التي تحتوي على أرقام صفحات فقط
        if re.match(r'^\d+$', line.strip()):
            continue
            
        if not line:
            if current_line:
                formatted_lines.append(current_line)
                current_line = ""
            formatted_lines.append("")
            continue
            
        # إذا كان السطر الحالي ينتهي بعلامة ترقيم أو كان طويلاً
        if (current_line and 
            (current_line[-1] in '.!?،؛:' or 
             len(current_line) > 100 or
             # لا تدمج الأسطر التي تبدأ بعلامات خاصة
             line[0] in '•-*#' or
             # لا تدمج العناوين
             line.isupper() or
             # لا تدمج الأسطر التي تبدأ بأرقام متبوعة بنقطة
             re.match(r'^\d+\.', line)
             )):
            formatted_lines.append(current_line)
            current_line = line
        else:
            if current_line:
                current_line += ' ' + line
            else:
                current_line = line
    
    if current_line:
        formatted_lines.append(current_line)
    
    # تجميع الأسطر مع مراعاة المسافات بين الفقرات
    formatted_text = '\n\n'.join(
        '\n'.join(group) 
        for group in _group_lines(formatted_lines)
    )
    
    return formatted_text.strip()

def _group_lines(lines: List[str]) -> List[List[str]]:
    """
    تجميع الأسطر في مجموعات (فقرات)
    """
    groups = []
    current_group = []
    
    for line in lines:
        if not line and current_group:
            groups.append(current_group)
            current_group = []
        elif line:
            current_group.append(line)
            
    if current_group:
        groups.append(current_group)
        
    return groups

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